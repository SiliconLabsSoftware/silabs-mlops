"""
Firmware Deployment Example - SiLabs MLOps
------------------------------------------
This script demonstrates how to use `RPiDeployer` to flash firmware either:
1. Locally via Simplicity Commander (USB/J-Link on this machine), or
2. Remotely via a Raspberry Pi (SCP + SSH).
"""

import logging
import os

from dotenv import load_dotenv

from sml.ops.model.deployer import RPiDeployer

# Suppress TensorFlow oneDNN floating-point warnings
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Load .env credentials if necessary
load_dotenv()


def run_example():
    print("\n--- SiLabs MLOps Deployment ---")

    # Path to your local firmware file (e.g., an .s37 or .bin file)
    local_file = "examples/bt_soc_thermometer_freertos.s37"

    # Omit rpi_host (None) to flash a board attached to this machine.
    # Set rpi_host to deploy via a Raspberry Pi over SSH.
    rpi_host = None  # e.g. "192.168.1.111"
    rpi_user = "aimlraspberry"

    print(f"  Local File : {local_file}")
    if rpi_host:
        print(f"  RPi Host   : {rpi_host} (User: {rpi_user})\n")
    else:
        print("  Target     : local Simplicity Commander\n")

    # Install Commander first if needed:
    #   sml install --tool commander
    #   sml install --tool commander --rpi-host <RPI_IP> --rpi-user <USER>
    try:
        deployer = RPiDeployer(
            rpi_host=rpi_host,
            rpi_user=rpi_user,
            local_file_path=local_file,
        )

        # Check if the file exists locally before running
        if not os.path.exists(local_file):
            print(f"Warning: Local file '{local_file}' not found.")
            print(
                "Please create or specify a valid file path to run the actual deployment."
            )
            print("Skipping actual deployment step.")
            return

        target = f"{rpi_user}@{rpi_host}" if rpi_host else "local machine"
        print(f"Starting deployment to {target}...")
        deployer.deploy()
        print(f"\nDeployment to {target} completed successfully.")

    except Exception as e:  # noqa: BLE001
        print(f"\nDeployment failed: {e}")


if __name__ == "__main__":
    run_example()
