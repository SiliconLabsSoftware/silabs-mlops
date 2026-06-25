# SPDX-License-Identifier: LicenseRef-MSLA
# @file deployer.py
# @brief Raspberry Pi firmware deployer.
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
Raspberry Pi firmware deployer.
Uploads a firmware file to a Raspberry Pi and flashes it to a Silicon Labs board.
"""

import logging
import os
import re
import subprocess

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
logger = logging.getLogger(__name__)


class RPiDeployer:
    """
    Deploy and flash firmware to a Silicon Labs device connected to a Raspberry Pi.
    - Uploads firmware using SCP
    - Runs Commander on the Raspberry Pi using SSH
    - Auto-detects J-Link serial and MCU part number (via "Part Number : ...")
    """

    def __init__(
        self,
        rpi_host: str,
        rpi_user: str,
        local_file_path: str,
        jlink_serial: str = None,
    ):
        self.rpi_host = rpi_host
        self.rpi_user = rpi_user
        self.local_file_path = local_file_path
        self.resolved_commander = None
        self.jlink_serial = jlink_serial

        if not os.path.exists(self.local_file_path):
            raise FileNotFoundError(f"Local firmware file not found: {self.local_file_path}")

    def deploy(self, jlink_serial: str = None):
        remote_path = f"/tmp/{os.path.basename(self.local_file_path)}"
        ssh_target = f"{self.rpi_user}@{self.rpi_host}"

        logger.info(f"Targeting remote Raspberry Pi: {ssh_target}")
        print("Connected to Raspberry Pi")

        self.resolved_commander = self._find_remote_commander(ssh_target)

        self._scp_firmware(self.local_file_path, ssh_target, remote_path)
        print("Firmware uploaded")

        serial_to_use = jlink_serial or self.jlink_serial
        if not serial_to_use:
            serials = self._get_jlink_serials(ssh_target)
            if not serials:
                raise RuntimeError("No J-Link devices connected to the Raspberry Pi.")

            if len(serials) == 1:
                serial_to_use = serials[0]
                print(f"Auto-selected only connected device: {serial_to_use}")
            else:
                print("\nMultiple devices detected. Please select one:")
                for i, s in enumerate(serials, 1):
                    print(f"{i}) J-Link Serial: {s}")

                choice = input(f"\nSelect board [1-{len(serials)}]: ").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(serials):
                        serial_to_use = serials[idx]
                    else:
                        raise ValueError()
                except ValueError:
                    raise RuntimeError("Invalid selection. Aborting.")

        device_name = self._get_device_name(ssh_target, serial_to_use)

        self._flash_firmware(ssh_target, remote_path, serial_to_use, device_name)

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
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"SCP failed (check network/IP):\n{result.stderr}")

    def _get_jlink_serials(self, ssh_target: str) -> list:
        cmd = [
            "ssh",
            "-o",
            "ConnectTimeout=30",
            "-o",
            "ConnectionAttempts=5",
            ssh_target,
            f"{self.resolved_commander} adapter list",
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Adapter list failed:\n{result.stderr}")

        serials = re.findall(r"serialNumber\s*=\s*(\d+)", result.stdout)
        return serials

    def _get_device_name(self, ssh_target: str, jlink_serial: str) -> str:
        cmd = [
            "ssh",
            "-o",
            "ConnectTimeout=30",
            "-o",
            "ConnectionAttempts=5",
            ssh_target,
            f"{self.resolved_commander} device info --serialno {jlink_serial}",
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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

    def _flash_firmware(self, ssh_target: str, remote_path: str, jlink_serial: str, device_name: str):
        cmd = [
            "ssh",
            "-o",
            "ConnectTimeout=30",
            "-o",
            "ConnectionAttempts=5",
            ssh_target,
            f'{self.resolved_commander} flash "{remote_path}" '
            f"--serialno {jlink_serial} "
            f"--device {device_name} -v",
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        print("Flash Output:")
        print(result.stdout)

        if result.returncode != 0:
            print("Flash Errors:\n", result.stderr)
            raise RuntimeError("Flash failed.")
