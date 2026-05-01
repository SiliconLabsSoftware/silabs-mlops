# SPDX-License-Identifier: LicenseRef-MSLA
# @file profiler.py
# @brief Wrapper for Silicon Labs ML profiler run and parse.
#
# # License
# Copyright 2026 Silicon Laboratories Inc. www.silabs.com
#
# The licensor of this software is Silicon Laboratories Inc. Your use of this
# software is governed by the terms of Silicon Labs Master Software License
# Agreement (MSLA) available at
# www.silabs.com/about-us/legal/master-software-license-agreement. This
# software is distributed to you in Source Code format and is governed by the
# sections of the MSLA applicable to Source Code.
#
# By installing, copying or otherwise using this software, you agree to the
# terms of the MSLA.

"""
Provides a Python wrapper around Silicon Labs' ML profiler for running and parsing model profiling.
"""

import os
import json
import yaml
import subprocess
import shutil
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import tempfile
import requests
from sml.ops.config import Config
from sml.ops.logs import Logger


@dataclass
class LayerProfile:
    """Profiling data for a single model layer."""

    name: str
    input_shape: str
    output_shape: str
    mcu_cycles: int
    mcu_stalls: int
    acc_cycles: int
    acc_stalls: int
    time_ms: float


@dataclass
class ProfileResult:
    """Structured result from an ML Model profiling session."""

    model_name: str
    model_path: str
    device_id: str
    output_dir: str
    # Session summary
    arena_size_kb: Optional[float] = None
    total_macs: Optional[int] = None
    board: Optional[str] = None
    # Layer breakdown
    layers: List[LayerProfile] = field(default_factory=list)
    # Output artifact paths
    summary_txt_path: Optional[str] = None
    report_json_path: Optional[str] = None
    pftrace_path: Optional[str] = None
    captured_packets_path: Optional[str] = None
    history_log_path: Optional[str] = None
    # Raw report data
    raw_report: Optional[Dict[str, Any]] = None


@dataclass
class DeviceInfo:
    """Information about a connected Silicon Labs development board."""

    device_id: str
    board: Optional[str] = None
    connection_type: Optional[str] = None
    raw: str = ""


class NPUProfiler:
    """
    Integrates the Silicon Labs ML model profiler (mvp_profiler/mvp_profiler.exe)
    into the SiLabs MLOps CLI.
    """

    # Candidate binary names for mvp_profiler
    _PROFILER_CANDIDATES = ["mvp_profiler", "mvp_profiler.exe"]

    def __init__(self):
        """Initialize the profiler and the centralized CLI logger."""
        self.logger = Logger()

    def _resolve_binary(
        self, candidates: List[str], override: Optional[str] = None
    ) -> Optional[str]:
        """Resolve a binary path, using override or searching PATH."""
        if override:
            p = Path(override)
            if p.is_file():
                return str(p)
            raise FileNotFoundError(f"Profiler binary not found at: {override}")
        for name in candidates:
            found = shutil.which(name)
            if found:
                return found
        return None

    def _resolve_profiler(self, profiler_path: Optional[str] = None) -> List[str]:
        """Resolve the profiler command, returning a list [cmd, arg1, ...]"""
        # 1. Try explicit path
        if profiler_path:
            p = Path(profiler_path)
            if p.is_file():
                return [str(p)]
            raise FileNotFoundError(f"Profiler binary not found at: {profiler_path}")

        # 2. Try mvp_profiler in PATH
        for name in self._PROFILER_CANDIDATES:
            found = shutil.which(name)
            if found:
                return [found]

        # 3. Try python -m npu_toolkit.profiler
        try:
            # Quick check if module exists
            subprocess.run(
                ["python", "-m", "npu_toolkit.profiler", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            return ["python", "-m", "npu_toolkit.profiler"]
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            pass

        # 4. Fallback: Search relative to sdm
        sdm_path = shutil.which("sdm")
        if sdm_path:
            sdm_bin = Path(sdm_path)
            for name in self._PROFILER_CANDIDATES:
                candidate = sdm_bin.parent / name
                if candidate.is_file():
                    return [str(candidate)]

        raise EnvironmentError(
            "Silicon Labs MVP Profiler (mvp_profiler) not found.\n"
            "Please ensure npu_toolkit is installed or mvp_profiler is in your PATH."
        )

    def _resolve_sdm(self, profiler_path: Optional[str] = None) -> Optional[str]:
        """Resolve the sdm binary path (optional, for device discovery)."""
        if profiler_path:
            p = Path(profiler_path)
            if p.is_file():
                for name in ["sdm", "sdm.exe"]:
                    sdm_candidate = p.parent / name
                    if sdm_candidate.is_file():
                        return str(sdm_candidate)
        return self._resolve_binary(["sdm", "sdm.exe"])

    def discover_devices(self, profiler_path: Optional[str] = None) -> List[DeviceInfo]:
        """
        Discover connected Silicon Labs development boards using `sdm adapter list`.

        Returns:
            List of DeviceInfo objects. Empty list if no boards are connected.
        """
        sdm = self._resolve_sdm(profiler_path)
        if not sdm:
            msg = "sdm binary not found. Cannot auto-discover devices. Please find your device ID manually."
            print(f"WARNING: {msg}")
            self.logger.log_model_profiling(message=msg, level="Warning")
            return []

        try:
            result = subprocess.run(
                [sdm, "adapter", "list"], capture_output=True, text=True, timeout=15
            )
            output = result.stdout + result.stderr
            return self._parse_adapter_list(output)
        except subprocess.TimeoutExpired:
            msg = "Device discovery timed out."
            print(f"WARNING: {msg}")
            self.logger.log_model_profiling(message=msg, level="Warning")
            return []
        except Exception as e:
            msg = f"Device discovery failed: {e}"
            print(f"WARNING: {msg}")
            self.logger.log_model_profiling(message=msg, level="Error")
            return []

    def _parse_adapter_list(self, output: str) -> List[DeviceInfo]:
        """
        Parse `sdm adapter list` output.

        Typical examples:
            Total adapter count: 2
              -> something [ usb wstk 440339411 BRD2608A 127.0.0.1 ]
              * another    [ usb wstk 123456789 BRD2608B 127.0.0.1 ]

        We only rely on the bracketed section:
        [ <conn_type> <tag> <device_id> <board> ... ]

        """
        devices = []
        # Match lines with device entries using a generic prefix pattern.
        # The prefix non-alphanumeric characters (bullets/arrows) are consumed by [^\w\s]+.
        pattern = re.compile(
            r"[^\w\s]+\s+\S+\s+\[\s*(\S+)\s+(\S+)\s+(\d{7,})\s+(\S+)", re.UNICODE
        )
        for line in output.splitlines():
            m = pattern.search(line)
            if m:
                conn_type = m.group(1)  # e.g. "usb"
                _wstk = m.group(2)
                device_id = m.group(3)
                board = m.group(4)
                devices.append(
                    DeviceInfo(
                        device_id=device_id,
                        board=board,
                        connection_type=conn_type,
                        raw=line.strip(),
                    )
                )
            else:
                # Fallback: Identify standard 9-digit numeric device IDs.
                ids = re.findall(r"\b(\d{7,12})\b", line)
                for dev_id in ids:
                    if not any(d.device_id == dev_id for d in devices):
                        devices.append(DeviceInfo(device_id=dev_id, raw=line.strip()))
        return devices

    def profile(
        self,
        model_path: str,
        device_id: Optional[str] = None,
        output_dir: Optional[str] = None,
        profiler_path: Optional[str] = None,
        gui: bool = False,
        timeout: int = 600,
        accelerator: str = "mvpv1",
        platform: Optional[str] = None,
        weights_paging: bool = False,
        use_simulator: bool = False,
        volume_path: Optional[str] = None,
    ) -> ProfileResult:
        """
        Profile a model using the MVP Profiler (mvp_profiler).

        Args:
            model_path:     Path to the .tflite or compiled .zip model file.
            device_id:      (Optional) J-Link serial number or IP address.
                            If None and device indexing is requested, attempts auto-discovery.
            output_dir:     Directory to save profiling artifacts.
            profiler_path:  Explicit path to profiler binary.
            gui:            If True, launches the Profiler GUI web server.
            timeout:        Execution timeout.
            accelerator:    Hardware accelerator target (default: mvpv1).
            platform:       Target platform (e.g., brd2605).
            weights_paging: Enable weights paging.
            use_simulator:  If True, runs profiling in local simulation mode (no hardware required).
            volume_path:    If provided, uploads results to Databricks Volumes and deletes local files.

        Returns:
            ProfileResult dataclass with all profiling metrics and output paths.

        Raises:
            FileNotFoundError: If model_path does not exist.
            EnvironmentError:  If profiler binary is not found.
            RuntimeError:      If the profiler subprocess fails.
        """
        # Validate model file
        model_p = Path(model_path)
        if not gui and not model_p.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Automatically log the action start
        action_msg = f"Started profiling model: {model_p.name}"
        if device_id:
            action_msg += f" on device ID {device_id}"
        elif use_simulator:
            action_msg += " (Local Simulation)"

        self.logger.log_model_profiling(message=action_msg, level="Info")

        # Resolve profiler command
        profiler_cmd = self._resolve_profiler(profiler_path)
        print(f"Using profiler command: {' '.join(profiler_cmd)}")

        # Resolve output directory (uses a temporary directory if volume_path is specified)
        is_temp_dir = False
        if volume_path:
            output_dir = tempfile.mkdtemp(prefix="npu_prof_")
            is_temp_dir = True
        elif not output_dir:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = str(
                Path.cwd() / "profiling_results" / f"{model_p.stem or 'gui'}-{ts}"
            )

        out_p = Path(output_dir)
        if not gui:
            out_p.mkdir(parents=True, exist_ok=True)

        # Construct the mvp_profiler command string
        cmd = list(profiler_cmd)

        if gui:
            # Start GUI server
            cmd += ["--host", "8080", "--launch"]
        else:
            cmd += [str(model_p.absolute())]
            cmd += ["--accelerator", accelerator]
            if platform:
                cmd += ["--platform", platform]
            if weights_paging:
                cmd += ["--weights-paging"]
            if output_dir:
                cmd += ["--output", str(out_p.absolute())]

            # Device selection and discovery.
            # Avoid appending --device if use_simulator is enabled to run locally.
            if not use_simulator:
                if device_id:
                    cmd += ["--device", "--serial-number", device_id]
                else:
                    # Default to device profiling with auto-discovery if no device_id
                    cmd += ["--device"]
            else:
                print("  Mode:      Simulator (Local)")

        print(f"\n{'=' * 60}")
        print(f"  SILICON LABS ML MODEL PROFILER")
        print(f"{'=' * 60}")
        print(f"  Model:     {model_p.name}")
        print(f"  Device ID: {device_id}")
        print(f"  Output:    {output_dir}")
        print(f"{'=' * 60}\n")
        print(f"Running: {' '.join(cmd)}\n")

        # Execute the profiler and stream the standard output
        history_file_path = out_p / "profiling_history.log"
        if not gui:
            print(f"Logging profiling history to: {history_file_path}\n")

        profiler_error = None
        try:
            if gui:
                # GUI server runs indefinitely unless interrupted
                proc = subprocess.run(cmd, text=True, timeout=None)
            else:
                # Stream output to the console and simultaneously log to the history file
                with open(history_file_path, "w", encoding="utf-8") as history_file:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,  # Merge stderr stream into stdout
                        text=True,
                        bufsize=1,
                    )

                    # Write line to console and flush to the log file
                    for line in proc.stdout:
                        print(line, end="")
                        history_file.write(line)
                        history_file.flush()

                    try:
                        proc.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                        raise subprocess.TimeoutExpired(cmd, timeout)

                if proc.returncode != 0:
                    profiler_error = RuntimeError(
                        f"Profiler exited with code {proc.returncode}.\n"
                        "Check tool logs and hardware connection."
                    )
        except subprocess.TimeoutExpired:
            profiler_error = RuntimeError(
                f"Profiler timed out after {timeout} seconds."
            )
        except Exception as e:
            if not profiler_error:
                profiler_error = RuntimeError(f"Failed to launch profiler: {e}")

        if gui:
            if profiler_error:
                raise profiler_error
            return ProfileResult(
                model_name="GUI", model_path="", device_id="", output_dir=""
            )

        # Parse results from the output directory, capturing the history log even on failure
        result = self._collect_results(model_p, device_id or "auto", out_p)

        # Upload artifacts to Databricks Volume if configured, regardless of exit status
        if volume_path and not gui:
            remote_url = self._upload_to_volume(out_p, model_p.stem, volume_path)
            result.output_dir = remote_url
            if is_temp_dir:
                shutil.rmtree(out_p, ignore_errors=True)

        # Generate and display the profiling summary
        self._print_summary(result)

        # Re-raise profiler exceptions after logs are processed and uploaded
        if profiler_error:
            self.logger.log_model_profiling(
                message=f"Profiling failed for {model_p.name} - Exit code {proc.returncode if 'proc' in locals() else 'Unknown'}",
                level="Error",
            )
            # Include the remote URL in the error message for log visibility
            raise RuntimeError(
                f"{profiler_error}\nFailed profiling logs uploaded to: {result.output_dir}"
            )

        self.logger.log_model_profiling(
            message=f"Successfully profiled {model_p.name} - Arena: {result.arena_size_kb or 0} KB, MACs: {result.total_macs or 0}",
            level="Success",
        )
        return result

    def _upload_to_volume(
        self, local_dir: Path, model_stem: str, custom_volume_path: str
    ) -> str:
        """Uploads profiling artifacts to Databricks Unity Catalog Volume."""
        if not (
            Config.ZEROBUS_WORKSPACE_URL
            and Config.ZEROBUS_CLIENT_ID
            and Config.ZEROBUS_CLIENT_SECRET
        ):
            print("[warn] Missing ZEROBUS credentials. Cannot upload to Volumes.")
            return str(local_dir)

        # Normalize DBX path
        p = str(custom_volume_path).replace("\\", "/")
        parts = [seg for seg in p.split("/") if seg]
        p = "/" + "/".join(parts)
        if not p.startswith("/Volumes/"):
            print("[warn] Volume path must start with /Volumes/. Skipping upload.")
            return str(local_dir)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_base = f"{p}/{model_stem}-{ts}"

        try:
            # 1. Get OAuth Token
            token_url = f"{Config.ZEROBUS_WORKSPACE_URL.rstrip('/')}/oidc/v1/token"
            r = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": Config.ZEROBUS_CLIENT_ID,
                    "client_secret": Config.ZEROBUS_CLIENT_SECRET,
                    "scope": "all-apis",
                },
            )
            r.raise_for_status()
            token = r.json()["access_token"]

            # 2. Upload Files
            print(f"\n[dbx] Uploading results to Databricks Volume: {remote_base}")
            uploaded: int = 0
            for root, _, files in os.walk(local_dir):
                for f in files:
                    local_f = Path(root) / f
                    rel_f = local_f.relative_to(local_dir).as_posix()
                    dest_f = f"{remote_base}/{rel_f}"
                    dest_dir = str(Path(dest_f).parent.as_posix())

                    # Create remote directory structure
                    req_dir = requests.put(
                        f"{Config.ZEROBUS_WORKSPACE_URL.rstrip('/')}/api/2.0/fs/directories{dest_dir}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if req_dir.status_code not in (200, 201, 204):
                        continue

                    # Upload file object
                    with open(local_f, "rb") as file_bytes:
                        req_put = requests.put(
                            f"{Config.ZEROBUS_WORKSPACE_URL.rstrip('/')}/api/2.0/fs/files{dest_f}",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/octet-stream",
                            },
                            data=file_bytes,
                            params={"overwrite": "true"},
                        )
                        if req_put.status_code in (200, 204):
                            uploaded += 1

            print(f"[dbx] Successfully uploaded {uploaded} files.")
            return remote_base

        except Exception as e:
            print(f"[warn] Volume upload failed: {e}")
            return str(local_dir)

    def _collect_results(
        self, model_p: Path, device_id: str, out_p: Path
    ) -> ProfileResult:
        """
        Collect and parse profiling artifacts from the output directory.
        The profiler may create a timestamped subdirectory; search recursively.
        """
        result = ProfileResult(
            model_name=model_p.stem,
            model_path=str(model_p),
            device_id=device_id,
            output_dir=str(out_p),
        )

        # Search for primary output files (may be nested in a timestamped subdir)
        def find_file(name: str) -> Optional[Path]:
            matches = list(out_p.rglob(name))
            return matches[0] if matches else None

        # Search for primary output files
        summary_file = find_file(f"{model_p.stem}-profiling_summary.txt")
        report_file = find_file(f"{model_p.stem}-profiling_results.yaml")
        history_log_file = find_file("profiling_history.log")

        # Fallbacks for generic names
        if not summary_file:
            summary_file = find_file("summary.txt")
        if not report_file:
            report_file = find_file("report.json") or find_file("results.yaml")

        if summary_file:
            result.summary_txt_path = str(summary_file)
        if report_file:
            result.report_json_path = str(report_file)
        if history_log_file:
            result.history_log_path = str(history_log_file)

        # Parse results for structured data
        if report_file and report_file.exists():
            try:
                with open(report_file) as f:
                    if report_file.suffix.lower() in [".yaml", ".yml"]:
                        raw = yaml.safe_load(f)
                    else:
                        raw = json.load(f)

                result.raw_report = raw
                # Extract common fields (structure may vary by toolkit version)
                # Try multiple keys for memory/arena size
                arena_bytes = (
                    raw.get("arena_size_kb", 0) * 1024
                    or raw.get("arena_size", 0)
                    or raw.get("region_sizes", {}).get("sram", 0)
                    or raw.get("runtime_buffer_size", 0)
                )
                result.arena_size_kb = arena_bytes / 1024 if arena_bytes else 0

                # Try multiple keys for MACs
                result.total_macs = (
                    raw.get("total_macs")
                    or raw.get("macs")
                    or raw.get("multiply_accumulate_count")
                )

                result.board = (
                    raw.get("board")
                    or raw.get("device", {}).get("board")
                    or raw.get("platform")
                )

                layers_raw = raw.get("layers") or raw.get("per_layer") or []
                result.layers = self._parse_layers(layers_raw)
            except Exception as e:
                msg = f"Could not fully parse report file {report_file.name}: {e}"
                print(f"NOTE: {msg}")
                self.logger.log_model_profiling(message=msg, level="Warning")

        # Fallback: parse summary.txt for arena/MACs
        if summary_file and summary_file.exists() and not result.arena_size_kb:
            self._parse_summary_txt(summary_file, result)

        return result

    def _parse_layers(self, layers_raw: list) -> List[LayerProfile]:
        """Parse per-layer data from report.json."""
        layers = []
        for lr in layers_raw:
            try:
                layers.append(
                    LayerProfile(
                        name=lr.get("name", lr.get("layer", "?")),
                        input_shape=str(lr.get("input_shape", lr.get("input", "?"))),
                        output_shape=str(lr.get("output_shape", lr.get("output", "?"))),
                        mcu_cycles=int(
                            lr.get("mcu_cycles", lr.get("mcu", {}).get("cycles", 0))
                        ),
                        mcu_stalls=int(
                            lr.get("mcu_stalls", lr.get("mcu", {}).get("stalls", 0))
                        ),
                        acc_cycles=int(
                            lr.get("acc_cycles", lr.get("acc", {}).get("cycles", 0))
                        ),
                        acc_stalls=int(
                            lr.get("acc_stalls", lr.get("acc", {}).get("stalls", 0))
                        ),
                        time_ms=float(lr.get("time_ms", lr.get("time", 0))),
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                # Allow the error to propagate so the caller can log it natively
                raise ValueError(f"Failed to parse layer profile: {e}") from e
        return layers

    def _parse_summary_txt(self, summary_file: Path, result: ProfileResult):
        """Extract key metrics from summary.txt if report.json parsing failed."""
        try:
            text = summary_file.read_text(errors="replace")
            # Arena size
            m = re.search(
                r"(?:Arena size|Runtime buffer size.*?)\s*[:\|]\s*([\d.]+)\s*([KMG]?B|k)",
                text,
                re.IGNORECASE,
            )
            if m:
                val = float(m.group(1))
                unit = m.group(2).lower()
                if unit == "k" or unit.startswith("k"):
                    result.arena_size_kb = val
                elif unit.startswith("m"):
                    result.arena_size_kb = val * 1024
                else:  # assumed bytes
                    result.arena_size_kb = val / 1024
            # Total MACs
            m = re.search(
                r"(?:Total.*?MACs?|Multiply-Accumulate Count)\s*[:\|]\s*([\d,.]+)\s*([KMG]?)",
                text,
                re.IGNORECASE,
            )
            if m:
                val_str = m.group(1).replace(",", "")
                multiplier = 1
                if m.group(2).upper() == "K":
                    multiplier = 1e3
                elif m.group(2).upper() == "M":
                    multiplier = 1e6
                elif m.group(2).upper() == "G":
                    multiplier = 1e9
                result.total_macs = int(float(val_str) * multiplier)
            # Board
            m = re.search(r"(?:Board|Platform)\s*[:\|]\s*(\S+)", text, re.IGNORECASE)
            if m:
                result.board = m.group(1)
        except Exception as e:
            msg = f"Failed to parse summary.txt: {e}"
            self.logger.log_model_profiling(message=msg, level="Warning")

    def _print_summary(self, result: ProfileResult):
        """Print a human-readable summary of profiling results."""
        print(f"\n{'=' * 60}")
        print(f"  PROFILING COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Model:      {result.model_name}")
        if result.board:
            print(f"  Board:      {result.board}")
        if result.arena_size_kb:
            print(f"  Arena Size: {result.arena_size_kb:.1f} KB")
        if result.total_macs:
            print(f"  Total MACs: {result.total_macs:,}")
        print(f"\n  Output artifacts saved to:")
        print(f"    {result.output_dir}")
        if result.summary_txt_path:
            print(f"    [OK] summary.txt")
        if result.report_json_path:
            print(f"    [OK] report.json")
        if result.history_log_path:
            print(f"    [OK] {Path(result.history_log_path).name}")
        if result.pftrace_path:
            print(f"    [OK] {Path(result.pftrace_path).name} (Perfetto trace)")
        if result.captured_packets_path:
            print(f"    [OK] captured-packets.json")
        print(f"{'=' * 60}\n")
