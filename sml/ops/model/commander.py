# SPDX-License-Identifier: LicenseRef-MSLA
# @file commander.py
# @brief Installer for Silicon Labs Simplicity Commander (commander-cli).
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
Downloads and installs the Silicon Labs Simplicity Commander (commander-cli) binary.
"""

import os
import shutil
import stat
import platform
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional

import requests

from sml.ops.config import USER_AGENT
from sml.ops.logs import Logger


class CommanderInstaller:
    """
    Downloads the official Simplicity Commander archive for the current platform,
    extracts the matching ``commander-cli`` package, and installs it under ~/.sml/bin.
    """

    _DOWNLOAD_BASE = "https://www.silabs.com/documents/public/software"
    _ZIP_BY_OS = {
        "windows": "SimplicityCommander-Windows.zip",
        "darwin": "SimplicityCommander-Mac.zip",
        "linux": "SimplicityCommander-Linux.zip",
    }

    # Architecture tokens as they appear inside the nested archive names.
    _ARCH_TOKENS = {
        "x86_64": ["x86_64", "amd64"],
        "amd64": ["x86_64", "amd64"],
        "aarch64": ["arm64", "aarch64"],
        "arm64": ["arm64", "aarch64"],
        "armv7l": ["arm_32", "aarch32", "arm32"],
        "armv6l": ["arm_32", "aarch32", "arm32"],
    }

    # Candidate binary names, in install preference order (commander-cli first).
    _BIN_CANDIDATES = ["commander-cli", "commander-cli.exe", "commander", "commander.exe"]
    _INSTALL_DIR = Path.home() / ".sml" / "bin"

    def __init__(self):
        """Initialize the installer and the centralized CLI logger."""
        self.logger = Logger()

    def install_commander(
        self,
        dest: Optional[str] = None,
        force: bool = False,
        timeout: int = 600,
    ) -> str:
        """
        Download and install Simplicity Commander (commander-cli) for this platform.

        Args:
            dest: Target directory for the package (default: ~/.sml/bin).
            force: Overwrite an existing installation if True.
            timeout: HTTP request timeout in seconds.

        Returns:
            The absolute path to the installed commander binary.
        """
        system = platform.system().lower()
        os_key = "windows" if system.startswith("win") else ("darwin" if system == "darwin" else "linux")
        zip_name = self._ZIP_BY_OS[os_key]
        url = f"{self._DOWNLOAD_BASE}/{zip_name}"

        dest_dir = Path(dest) if dest else self._INSTALL_DIR
        pkg_dir = dest_dir / "commander-cli"

        if pkg_dir.exists() and not force:
            raise FileExistsError(
                f"Simplicity Commander already installed at {pkg_dir}. Use force=True to overwrite."
            )

        dest_dir.mkdir(parents=True, exist_ok=True)

        self.logger.log_model_deployment(
            message=f"Downloading Simplicity Commander from {url}", level="Info"
        )

        with tempfile.TemporaryDirectory(prefix="sml_commander_") as tmp:
            tmp_path = Path(tmp)
            zip_path = tmp_path / zip_name
            self._download(url, zip_path, timeout)

            extract_root = tmp_path / "extracted"
            extract_root.mkdir()
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_root)

            # The outer zip nests per-platform archives (.zip on macOS, .tar.bz on
            # Linux); extract the best-matching commander-cli package into a stage.
            stage = tmp_path / "stage"
            stage.mkdir()
            base = stage
            if not self._extract_cli_package(extract_root, stage):
                # No nested archive yielded a binary; the outer zip may hold it directly.
                base = extract_root

            binary = self._locate_binary(base)
            if binary is None:
                raise RuntimeError(
                    "Could not locate the commander binary inside the downloaded archive."
                )

            # Copy the whole package directory so bundled libraries/resources are
            # preserved (the macOS Commander-cli.app bundle or the Linux folder).
            pkg_src = self._package_root(base, binary)
            if pkg_dir.exists():
                shutil.rmtree(pkg_dir)
            shutil.copytree(pkg_src, pkg_dir, symlinks=True)

            installed = pkg_dir / binary.relative_to(pkg_src)
            if os_key != "windows":
                self._make_executable(installed)

        self.logger.log_model_deployment(
            message=f"Installed Simplicity Commander to {installed}", level="Success"
        )
        return str(installed)

    def install_commander_remote(
        self,
        rpi_host: str,
        rpi_user: str,
        dest: str = "~/.sml/bin",
        force: bool = False,
        timeout: int = 600,
    ) -> str:
        """
        Download the Linux Simplicity Commander archive and push it to a Raspberry Pi
        via SCP, making the binary executable.

        The remote architecture is detected via ``uname -m`` over SSH so the
        correct per-arch tarball is selected from the outer zip.

        Args:
            rpi_host: Hostname or IP address of the Raspberry Pi.
            rpi_user: SSH username on the Pi.
            dest: Remote destination directory (default: ``~/.sml/bin``).
            force: Remove an existing installation before copying.
            timeout: HTTP download timeout in seconds.

        Returns:
            The remote absolute path to the installed commander-cli binary.
        """
        ssh_target = f"{rpi_user}@{rpi_host}"
        remote_pkg_dir = f"{dest}/commander-cli"

        # Expand ~ on the remote side once so we have a concrete path
        expand = subprocess.run(
            ["ssh", ssh_target, f"echo {remote_pkg_dir}"],
            capture_output=True, text=True, timeout=30,
        )
        if expand.returncode == 0 and expand.stdout.strip():
            remote_pkg_dir = expand.stdout.strip()

        if not force:
            check = subprocess.run(
                ["ssh", ssh_target, f"test -d {remote_pkg_dir} && echo exists || true"],
                capture_output=True, text=True, timeout=30,
            )
            if "exists" in check.stdout:
                raise FileExistsError(
                    f"Simplicity Commander already installed at {remote_pkg_dir} on {rpi_host}. "
                    "Use --force to overwrite."
                )

        # Detect the Pi's architecture to pick the matching nested archive
        arch_result = subprocess.run(
            ["ssh", ssh_target, "uname -m"],
            capture_output=True, text=True, timeout=30,
        )
        remote_machine = arch_result.stdout.strip().lower()
        arch_tokens = self._ARCH_TOKENS.get(remote_machine, [remote_machine])

        zip_name = self._ZIP_BY_OS["linux"]
        url = f"{self._DOWNLOAD_BASE}/{zip_name}"

        self.logger.log_model_deployment(
            message=(
                f"Downloading Linux Simplicity Commander from {url} "
                f"(remote arch: {remote_machine or 'unknown'})"
            ),
            level="Info",
        )

        with tempfile.TemporaryDirectory(prefix="sml_commander_") as tmp:
            tmp_path = Path(tmp)
            zip_path = tmp_path / zip_name
            self._download(url, zip_path, timeout)

            extract_root = tmp_path / "extracted"
            extract_root.mkdir()
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_root)

            stage = tmp_path / "stage"
            stage.mkdir()
            base = stage
            if not self._extract_cli_package(extract_root, stage, arch_tokens=arch_tokens):
                base = extract_root

            binary = self._locate_binary(base)
            if binary is None:
                raise RuntimeError(
                    "Could not locate the commander binary inside the Linux archive."
                )

            pkg_src = self._package_root(base, binary)
            rel_binary = binary.relative_to(pkg_src)

            # Remove stale installation if force, create destination directory
            if force:
                subprocess.run(
                    ["ssh", ssh_target, f"rm -rf {remote_pkg_dir}"],
                    timeout=30,
                )
            subprocess.run(
                ["ssh", ssh_target, f"mkdir -p $(dirname {remote_pkg_dir})"],
                check=True, timeout=30,
            )

            # Push the entire package directory (preserves bundled libraries)
            result = subprocess.run(
                ["scp", "-r", str(pkg_src), f"{ssh_target}:{remote_pkg_dir}"],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(f"SCP to {rpi_host} failed:\n{result.stderr}")

            remote_binary = f"{remote_pkg_dir}/{rel_binary}"
            subprocess.run(
                ["ssh", ssh_target, f"chmod +x {remote_binary}"],
                check=True, timeout=30,
            )

        self.logger.log_model_deployment(
            message=f"Installed Simplicity Commander to {ssh_target}:{remote_binary}",
            level="Success",
        )
        return remote_binary

    def _download(self, url: str, target: Path, timeout: int) -> None:
        """Stream the archive to ``target``, sending the SDK User-Agent header."""
        headers = {"User-Agent": USER_AGENT}
        with requests.get(url, stream=True, timeout=timeout, headers=headers) as r:
            r.raise_for_status()
            with open(target, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)

    def _arch_tokens(self) -> List[str]:
        """Return candidate architecture tokens for the current machine."""
        machine = platform.machine().lower()
        return self._ARCH_TOKENS.get(machine, [machine])

    def _extract_cli_package(
        self,
        search_root: Path,
        stage: Path,
        arch_tokens: Optional[List[str]] = None,
    ) -> bool:
        """
        Extract the best-matching commander-cli archive nested in the outer zip
        into ``stage``. Returns True once an archive yielding the binary is found.

        Candidates are scored to prefer the CLI variant and the target
        architecture; they are extracted one at a time until the binary appears.
        Pass ``arch_tokens`` to override the local platform's architecture tokens
        (useful when installing for a remote target, e.g. a Raspberry Pi).
        """
        archives = self._find_nested_archives(search_root)
        archives.sort(key=lambda a: self._score_archive(a, arch_tokens), reverse=True)
        for arc in archives:
            self._extract_archive(arc, stage)
            if self._locate_binary(stage) is not None:
                return True
            # This archive did not contain the binary; clear the stage and retry.
            for child in stage.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        return False

    def _find_nested_archives(self, root: Path) -> List[Path]:
        """Return nested archive files (.zip and .tar.bz/.tar.bz2) found under ``root``."""
        archives: List[Path] = []
        for pattern in ("*.zip", "*.tar.bz", "*.tar.bz2"):
            archives.extend(root.rglob(pattern))
        return archives

    def _score_archive(self, archive: Path, arch_tokens: Optional[List[str]] = None) -> int:
        """Score a nested archive; a higher score means a better commander-cli candidate.

        Args:
            arch_tokens: Architecture tokens to match against; defaults to the
                         local machine's tokens when not provided.
        """
        name = archive.name.lower()
        score = 0
        if "cli" in name:
            score += 10
        tokens = arch_tokens if arch_tokens is not None else self._arch_tokens()
        if any(token in name for token in tokens):
            score += 5
        return score

    def _extract_archive(self, archive: Path, dest: Path) -> None:
        """Extract a nested .zip or bzip2 tarball into ``dest`` (data filter on Python 3.12+)."""
        if archive.name.lower().endswith(".zip"):
            self._extract_zip(archive, dest)
            return
        with tarfile.open(archive, "r:bz2") as tf:
            try:
                tf.extractall(dest, filter="data")
            except TypeError:
                tf.extractall(dest)

    def _extract_zip(self, archive: Path, dest: Path) -> None:
        """
        Extract a zip while restoring symlinks and Unix permission bits, which
        ``ZipFile.extractall`` drops. Required for the macOS Commander-cli.app
        bundle, whose Frameworks rely on symlinks (otherwise dylibs fail to load).
        """
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                target = dest / info.filename
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    link_target = zf.read(info).decode()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.is_symlink() or target.exists():
                        target.unlink()
                    os.symlink(link_target, target)
                elif info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)
                    if mode:
                        os.chmod(target, mode & 0o777)

    def _package_root(self, base: Path, binary: Path) -> Path:
        """Return the top-level package directory under ``base`` containing the binary."""
        rel = binary.relative_to(base)
        if len(rel.parts) > 1:
            return base / rel.parts[0]
        return binary.parent

    def _make_executable(self, target: Path) -> None:
        """Set the executable bit on the binary and any sibling helper binaries."""
        for f in target.parent.iterdir():
            if f.is_file():
                mode = os.stat(f).st_mode
                os.chmod(f, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _locate_binary(self, root: Path) -> Optional[Path]:
        """Find the commander binary, preferring commander-cli over the GUI build."""
        for candidate in self._BIN_CANDIDATES:
            for p in root.rglob(candidate):
                if p.is_file():
                    return p
        return None
