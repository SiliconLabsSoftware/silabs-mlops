# SPDX-License-Identifier: LicenseRef-MSLA
# @file deployer.py
# @brief Firmware deployer (local or via Raspberry Pi).
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
Firmware deployer for Silicon Labs devices.
Flashes a local firmware file either directly (USB/J-Link on this machine) or
via a remote Raspberry Pi (SCP + SSH).
"""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
logger = logging.getLogger(__name__)


class RPiDeployer:
    """
    Deploy and flash firmware to a Silicon Labs device.

    When `rpi_host` is set, uploads firmware via SCP and runs Commander on the
    Pi over SSH. When omitted, runs Commander locally against a USB-attached
    J-Link. Auto-detects J-Link serial and MCU part number (via `Part Number : ...`).
    """

    def __init__(
        self,
        rpi_host: str | None = None,
        rpi_user: str | None = None,
        local_file_path: str | None = None,
        jlink_serial: str | None = None,
    ):
        if local_file_path is None:
            raise TypeError("local_file_path is required")

        self.rpi_host = rpi_host
        self.rpi_user = rpi_user or "aimlraspberry"
        self.local_file_path = local_file_path
        self.resolved_commander = None
        self.jlink_serial = jlink_serial

        if not os.path.exists(self.local_file_path):
            raise FileNotFoundError(
                f"Local firmware file not found: {self.local_file_path}"
            )

    @property
    def is_remote(self) -> bool:
        """True when deploying via a Raspberry Pi SSH target."""
        return bool(self.rpi_host)

    def deploy(self, jlink_serial: str | None = None):
        if self.is_remote:
            self._deploy_remote(jlink_serial=jlink_serial)
        else:
            self._deploy_local(jlink_serial=jlink_serial)

    def _deploy_local(self, jlink_serial: str | None = None):
        logger.info("Targeting local Simplicity Commander")
        print("Deploying via local Simplicity Commander")

        self.resolved_commander = self._find_local_commander()
        firmware_path = os.path.abspath(self.local_file_path)

        serial_to_use = self._resolve_serial(jlink_serial, ssh_target=None)
        device_name = self._get_device_name(serial_to_use, ssh_target=None)
        self._flash_firmware(firmware_path, serial_to_use, device_name, ssh_target=None)

    def _deploy_remote(self, jlink_serial: str | None = None):
        remote_path = f"/tmp/{os.path.basename(self.local_file_path)}"
        ssh_target = f"{self.rpi_user}@{self.rpi_host}"

        logger.info(f"Targeting remote Raspberry Pi: {ssh_target}")
        print("Connected to Raspberry Pi")

        self.resolved_commander = self._find_remote_commander(ssh_target)

        self._scp_firmware(self.local_file_path, ssh_target, remote_path)
        print("Firmware uploaded")

        serial_to_use = self._resolve_serial(jlink_serial, ssh_target=ssh_target)
        device_name = self._get_device_name(serial_to_use, ssh_target=ssh_target)
        self._flash_firmware(
            remote_path, serial_to_use, device_name, ssh_target=ssh_target
        )

    def _resolve_serial(self, jlink_serial: str | None, ssh_target: str | None) -> str:
        serial_to_use = jlink_serial or self.jlink_serial
        if serial_to_use:
            return serial_to_use

        serials = self._get_jlink_serials(ssh_target=ssh_target)
        if not serials:
            location = "the Raspberry Pi" if ssh_target else "this machine"
            raise RuntimeError(f"No J-Link devices connected to {location}.")

        if len(serials) == 1:
            print(f"Auto-selected only connected device: {serials[0]}")
            return serials[0]

        print("\nMultiple devices detected. Please select one:")
        for i, s in enumerate(serials, 1):
            print(f"{i}) J-Link Serial: {s}")

        choice = input(f"\nSelect board [1-{len(serials)}]: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(serials):
                return serials[idx]
            raise ValueError()
        except ValueError:
            raise RuntimeError("Invalid selection. Aborting.")

    def _find_local_commander(self) -> str:
        for name in ("commander-cli", "commander"):
            found = shutil.which(name)
            if found:
                logger.info(f"Auto-detected commander on PATH: {found}")
                return found

        home = Path.home()
        search_roots = [
            home / ".sml" / "bin",
            home / "Desktop",
            home,
        ]
        for root in search_roots:
            if not root.exists():
                continue
            max_depth = 3 if root != home else 4
            for candidate in ("commander-cli", "commander"):
                for path in root.rglob(candidate):
                    try:
                        rel_depth = len(path.relative_to(root).parts)
                    except ValueError:
                        continue
                    if rel_depth > max_depth:
                        continue
                    if path.is_file() and os.access(path, os.X_OK):
                        logger.info(f"Auto-detected commander at: {path}")
                        return str(path)

        raise RuntimeError(
            "Could not locate Simplicity Commander on this machine. "
            "Install it with `sml install --tool commander` or add it to the PATH."
        )

    def _find_remote_commander(self, ssh_target: str) -> str:
        # Each candidate is followed by "| grep ." so that an empty find/which
        # output exits 1, allowing the || chain to continue to the next option.
        search_snippet = (
            "which commander-cli 2>/dev/null | grep . || "
            "which commander 2>/dev/null | grep . || "
            "find $HOME/.sml/bin -maxdepth 3 -name commander-cli -executable -type f 2>/dev/null | head -n 1 | grep . || "
            "find $HOME/Desktop -maxdepth 3 -name commander-cli -executable -type f 2>/dev/null | head -n 1 | grep . || "
            "find $HOME/Desktop -maxdepth 3 -name commander -executable -type f 2>/dev/null | head -n 1 | grep . || "
            "find $HOME -maxdepth 4 -name commander-cli -executable -type f 2>/dev/null | head -n 1"
        )

        cmd = ["ssh", ssh_target, search_snippet]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        resolved = result.stdout.strip()
        if resolved:
            logger.info(f"Auto-detected commander at: {resolved}")
            return resolved

        raise RuntimeError(
            "Could not locate Simplicity Commander on the Raspberry Pi. "
            "Install it there or add it to the PATH."
        )

    def _scp_firmware(self, local: str, ssh_target: str, remote: str):
        cmd = [
            "scp",
            "-o",
            "ConnectTimeout=30",
            "-o",
            "ConnectionAttempts=5",
            local,
            f"{ssh_target}:{remote}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            raise RuntimeError(f"SCP failed (check network/IP):\n{result.stderr}")

    def _run_commander(
        self, args: list[str], ssh_target: str | None = None
    ) -> subprocess.CompletedProcess:
        if not self.resolved_commander:
            raise RuntimeError("Commander path not resolved.")

        if ssh_target:
            remote_cmd = f"{self.resolved_commander} {' '.join(args)}"
            cmd = [
                "ssh",
                "-o",
                "ConnectTimeout=30",
                "-o",
                "ConnectionAttempts=5",
                ssh_target,
                remote_cmd,
            ]
        else:
            cmd = [self.resolved_commander, *args]

        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def _get_jlink_serials(self, ssh_target: str | None = None) -> list:
        result = self._run_commander(["adapter", "list"], ssh_target=ssh_target)

        if result.returncode != 0:
            raise RuntimeError(f"Adapter list failed:\n{result.stderr}")

        serials = re.findall(r"serialNumber\s*=\s*(\d+)", result.stdout)
        return serials

    def _get_device_name(self, jlink_serial: str, ssh_target: str | None = None) -> str:
        result = self._run_commander(
            ["device", "info", "--serialno", jlink_serial],
            ssh_target=ssh_target,
        )

        print("Device info:")
        print(result.stdout)

        if result.returncode != 0:
            raise RuntimeError(f"Device info failed:\n{result.stderr}")

        m = re.search(r"Part Number\s*:\s*([A-Za-z0-9_]+)", result.stdout)
        if not m:
            raise RuntimeError("Could not extract device name from Commander output.")

        device_name = m.group(1).strip()
        print("Detected Device Name:", device_name)
        return device_name

    def _flash_firmware(
        self,
        firmware_path: str,
        jlink_serial: str,
        device_name: str,
        ssh_target: str | None = None,
    ):
        if ssh_target:
            # Remote path may contain spaces; quote it for the SSH shell.
            flash_args = [
                "flash",
                f'"{firmware_path}"',
                "--serialno",
                jlink_serial,
                "--device",
                device_name,
                "-v",
            ]
        else:
            flash_args = [
                "flash",
                firmware_path,
                "--serialno",
                jlink_serial,
                "--device",
                device_name,
                "-v",
            ]

        result = self._run_commander(flash_args, ssh_target=ssh_target)

        print("Flash Output:")
        print(result.stdout)

        if result.returncode != 0:
            print("Flash Errors:\n", result.stderr)
            raise RuntimeError("Flash failed.")
