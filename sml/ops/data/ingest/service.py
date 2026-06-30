# SPDX-License-Identifier: LicenseRef-MSLA
# @file service.py
# @brief Continuous file-watcher ingestion service for Databricks.
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
Continuous file-watcher ingestion service for Databricks.
"""

import fnmatch
import logging
import os
import queue
import re
import subprocess
import threading
import time
import uuid
import wave
from pathlib import Path
from typing import Callable, Optional

from .config import IngestConfig
from .ingestor import DataIngestor

logger = logging.getLogger("CloudIngestor")

_hw_cache: dict[str, Optional[str]] = {"name": None, "id": None}
_hw_lock = threading.Lock()

_DEFAULT_COMMANDER_PATH = str(
    Path.home() / "Desktop/SimplicityCommander-Linux/commander-cli/commander-cli"
)


def get_hw_info(commander_path: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Return part number and unique ID from a connected board via commander-cli."""
    global _hw_cache

    path = commander_path or os.getenv("COMMANDER_PATH", _DEFAULT_COMMANDER_PATH)

    with _hw_lock:
        if _hw_cache["name"] is not None:
            return _hw_cache["name"], _hw_cache["id"]

        if not Path(path).exists():
            return None, None

        try:
            out = subprocess.check_output(
                [path, "adapter", "list"], stderr=subprocess.STDOUT
            ).decode()
            sn_match = re.search(r"serialNumber=(\d+)", out)
            if not sn_match:
                return None, None
            sn = sn_match.group(1)

            out = subprocess.check_output(
                [path, "device", "info", "--serialno", sn],
                stderr=subprocess.STDOUT,
            ).decode()
            part_match = re.search(r"Part Number\s+:\s+(.+)", out)
            uid_match = re.search(r"Unique ID\s+:\s+(.+)", out)

            part = part_match.group(1).strip() if part_match else None
            uid = uid_match.group(1).strip() if uid_match else None

            _hw_cache["name"] = part
            _hw_cache["id"] = uid
            return part, uid
        except Exception:
            return None, None


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        return "audio/wav"
    if suffix in (".json",):
        return "application/json"
    if suffix in (".csv",):
        return "text/csv"
    return "application/octet-stream"


def build_wav_metadata(
    file_path: Path,
    commander_path: Optional[str] = None,
) -> dict:
    """Build metadata for a WAV file (label from filename, sample rate from header)."""
    fname = file_path.name
    parts = fname.replace(".wav", "").split("_")
    label = parts[0] if parts else "unknown"

    file_sample_rate = 16000
    try:
        with wave.open(str(file_path), "rb") as wf:
            file_sample_rate = wf.getframerate()
    except Exception as e:
        logger.error("Could not read WAV header for %s: %s", fname, e)

    hw_name, hw_id = get_hw_info(commander_path)
    if hw_name and hw_id:
        device_id = hw_id
        device_name = hw_name
    else:
        device_id = f"Pi-{uuid.getnode():x}"
        device_name = "Raspberry Pi Voice Gateway"

    return {
        "device_id": device_id,
        "device_name": device_name,
        "file_name": fname,
        "class_label": label,
        "content_type": "audio/wav",
        "sample_rate": file_sample_rate,
        "duration_ms": 1000,
    }


def build_generic_metadata(file_path: Path) -> dict:
    """Build minimal metadata for non-audio files."""
    hw_name, hw_id = get_hw_info()
    if hw_name and hw_id:
        device_id = hw_id
        device_name = hw_name
    else:
        device_id = f"Pi-{uuid.getnode():x}"
        device_name = "Raspberry Pi Voice Gateway"

    return {
        "device_id": device_id,
        "device_name": device_name,
        "file_name": file_path.name,
        "content_type": _guess_content_type(file_path),
        "ingest_ts": int(time.time() * 1_000_000),
    }


def default_metadata_builder(
    file_path: Path,
    commander_path: Optional[str] = None,
) -> dict:
    """Use WAV-specific metadata when the file is a .wav, otherwise generic."""
    if file_path.suffix.lower() == ".wav":
        return build_wav_metadata(file_path, commander_path=commander_path)
    return build_generic_metadata(file_path)


class IngestionService:
    """Watch a directory for new files and upload them to Databricks via ZeroBus."""

    def __init__(
        self,
        config: IngestConfig,
        monitor_dir: str,
        volume_path: str,
        pattern: str = "*.wav",
        workers: int = 4,
        commander_path: Optional[str] = None,
        metadata_builder: Optional[Callable[[Path], dict]] = None,
        poll_interval: float = 1.0,
        log: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.monitor_dir = Path(monitor_dir)
        self.volume_path = volume_path.rstrip("/")
        self.pattern = pattern
        self.workers = max(1, workers)
        self.commander_path = commander_path
        self.poll_interval = poll_interval
        self._log = log or (lambda msg: logger.info(msg))

        if metadata_builder is not None:
            self._metadata_builder = metadata_builder
        else:
            self._metadata_builder = lambda p: default_metadata_builder(
                p, commander_path=self.commander_path
            )

        self._stop_event = threading.Event()
        self._file_queue: queue.Queue[str] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._started = False

    def _emit(self, message: str, level: str = "info") -> None:
        self._log(message)
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def _matches_pattern(self, filename: str) -> bool:
        return fnmatch.fnmatch(filename.lower(), self.pattern.lower())

    def _directory_monitor(self) -> None:
        self._emit(f"Monitor started on {self.monitor_dir}")
        seen_files: set[str] = set()

        while not self._stop_event.is_set():
            try:
                self.monitor_dir.mkdir(parents=True, exist_ok=True)
                files = [
                    f
                    for f in os.listdir(self.monitor_dir)
                    if self._matches_pattern(f)
                ]
                for f in files:
                    fpath = self.monitor_dir / f
                    fpath_str = str(fpath)
                    if fpath_str not in seen_files:
                        self._emit(f"New file detected: {f}")
                        self._file_queue.put(fpath_str)
                        seen_files.add(fpath_str)

                current_paths = {str(self.monitor_dir / f) for f in files}
                seen_files &= current_paths
            except Exception as e:
                self._emit(f"Monitor error: {e}", level="error")

            self._stop_event.wait(self.poll_interval)

    def _uploader(self, worker_id: int) -> None:
        self._emit(f"Worker-{worker_id} started")
        ingestor = DataIngestor(self.config)

        while not self._stop_event.is_set():
            try:
                fpath = self._file_queue.get(timeout=self.poll_interval)
            except queue.Empty:
                continue

            try:
                path = Path(fpath)
                if not path.exists():
                    continue

                fname = path.name
                dest_path = f"{self.volume_path}/{fname}"
                metadata = self._metadata_builder(path)

                self._emit(f"Worker-{worker_id} uploading {fname}...")
                success = ingestor.file_ingest(
                    file_path=fpath, volume_path=dest_path, metadata=metadata
                )

                if success:
                    self._emit(f"Worker-{worker_id} successfully processed {fname}")
                    if os.path.exists(fpath):
                        os.remove(fpath)
                        self._emit(f"Removed local file {fname}")
                else:
                    self._emit(
                        f"Worker-{worker_id} failed to process {fname}, keeping local copy",
                        level="error",
                    )
            except Exception as e:
                self._emit(
                    f"Worker-{worker_id} error processing {fpath}: {e}",
                    level="error",
                )
            finally:
                self._file_queue.task_done()

    def start(self) -> "IngestionService":
        """Start monitor and uploader threads (non-blocking)."""
        if self._started:
            return self

        self._stop_event.clear()
        self._threads = []

        monitor = threading.Thread(target=self._directory_monitor, daemon=True)
        monitor.start()
        self._threads.append(monitor)

        for i in range(self.workers):
            worker = threading.Thread(target=self._uploader, args=(i,), daemon=True)
            worker.start()
            self._threads.append(worker)

        self._started = True
        self._emit(
            f"Ingestion service running with {self.workers} worker(s). "
            "Press Ctrl+C to stop."
        )
        return self

    def stop(self, join_timeout: float = 5.0) -> None:
        """Signal threads to stop and optionally wait for them."""
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=join_timeout)
        self._threads.clear()
        self._started = False
        self._emit("Ingestion service stopped.")

    def wait(self) -> None:
        """Block until KeyboardInterrupt, then stop."""
        try:
            while not self._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self._emit("Stopping...")
            self.stop()
