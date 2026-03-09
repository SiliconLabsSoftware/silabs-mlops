"""
Raspberry Pi Firmware Deployer.
Uploads a firmware file to a Raspberry Pi and flashes it to a Silabs board.
"""

import subprocess
import logging
import re
import os

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
logger = logging.getLogger(__name__)


class RPiDeployer:
    """
    Deploy and flash firmware to a Silabs device connected to a Raspberry Pi.
    - Uploads firmware using SCP
    - Runs Commander on the Raspberry Pi using SSH
    - Auto-detects J-Link serial and MCU part number (via "Part Number : ...")
    """

    def __init__(self, rpi_host: str, rpi_user: str, local_file_path: str, commander_path: str):
        self.rpi_host = rpi_host
        self.rpi_user = rpi_user
        self.local_file_path = local_file_path
        self.commander_path = commander_path  # e.g. "/usr/local/bin/commander-wrapper"

        if not os.path.exists(self.local_file_path):
            raise FileNotFoundError(f"Local firmware file not found: {self.local_file_path}")

    
    def deploy(self):
        remote_path = f"/tmp/{os.path.basename(self.local_file_path)}"
        ssh_target = f"{self.rpi_user}@{self.rpi_host}"

        logger.info(f"Targeting remote Raspberry Pi: {ssh_target}")
        print("Connected to Raspberry Pi")

        # 1. Upload firmware
        self._scp_firmware(self.local_file_path, ssh_target, remote_path)
        print("Firmware uploaded")

        # 2. Detect J-Link serial from adapter list
        jlink_serial = self._get_jlink_serial(ssh_target)

        # 3. Detect device part number from device info
        device_name = self._get_device_name(ssh_target, jlink_serial)

        # 4. Flash firmware
        self._flash_firmware(ssh_target, remote_path, jlink_serial, device_name)

    
    def _scp_firmware(self, local: str, ssh_target: str, remote: str):
        cmd = ["scp", local, f"{ssh_target}:{remote}"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"SCP failed:\n{result.stderr}")

    
    def _get_jlink_serial(self, ssh_target: str) -> str:
        """
        Run `commander adapter list` and extract:
        serialNumber=440335321
        """
        cmd = [
            "ssh", ssh_target,
            f"{self.commander_path} adapter list"
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        print("Adapter list:")
        print(result.stdout)

        if result.returncode != 0:
            raise RuntimeError(f"Adapter list failed:\n{result.stderr}")

        m = re.search(r"serialNumber\s*=\s*(\d+)", result.stdout)
        if not m:
            raise RuntimeError("Could not find J-Link serial number in adapter list.")

        serial = m.group(1)
        print("Detected J-Link Serial:", serial)
        return serial

   
    def _get_device_name(self, ssh_target: str, jlink_serial: str) -> str:
        """
        Run:
            commander device info --serialno <SN>

        Extract device name from:
            Part Number : EFR32MG26B510F3200IM68
        """
        cmd = [
            "ssh", ssh_target,
            f"{self.commander_path} device info --serialno {jlink_serial}"
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        print("Device info:")
        print(result.stdout)

        if result.returncode != 0:
            raise RuntimeError(f"Device info failed:\n{result.stderr}")

        # Extract chip from: Part Number : EFR32MG26B510F3200IM68
        m = re.search(r"Part Number\s*:\s*([A-Za-z0-9_]+)", result.stdout)
        if not m:
            raise RuntimeError("Could not extract device name from Commander output.")

        device_name = m.group(1).strip()
        print("Detected Device Name:", device_name)
        return device_name

   
    def _flash_firmware(self, ssh_target: str, remote_path: str, jlink_serial: str, device_name: str):
        """
        Correct flash syntax:
            commander flash <file> --serialno <SN> --device <PART> -v
        """
        cmd = [
            "ssh", ssh_target,
            f"{self.commander_path} flash {remote_path} "
            f"--serialno {jlink_serial} "
            f"--device {device_name} -v"
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        print("Flash Output:")
        print(result.stdout)

        if result.returncode != 0:
            print("Flash Errors:\n", result.stderr)
            raise RuntimeError("Flash failed.")