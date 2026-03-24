"""
Silicon-Labs-MLOps-CLI
=======================
User-facing commands for:
  • Raspberry Pi deployment (SCP + SSH + Commander on the Pi)

Note:
  - Raspberry Pi deployment requires Commander to be installed on the Pi
    and accessible by the provided path (or via a wrapper).
"""

import os
import sys
import click

# Internal package imports
from silabs_mlops.model.deployer import RPiDeployer
from silabs_mlops.logs import Logger

# Initialize Universal Logger
logger = Logger()


@click.group()
def main():
    """SiLabs Deployment Toolkit CLI"""
    pass


# -----------------------------------------------------------------------------
# Deployment (Raspberry Pi SSH)
# -----------------------------------------------------------------------------
@main.command(name="deploy")
@click.option('--uri', required=True, help='Local file path to firmware/model (.s37/.bin/.hex).')
@click.option('--serial', help='Target J-Link serial number (optional).')
@click.option('--commander', help='Path to Simplicity Commander on Raspberry Pi.')
@click.option('--rpi-host', required=True, help='Target Pi IP/Hostname.')
@click.option('--rpi-user', default='aimlraspberry', show_default=True, help='SSH user.')
@click.option('--remote-path', help='Optional remote path on Pi.')
def deploy(uri, serial, commander, rpi_host, rpi_user, remote_path):
    """
    Deploy a firmware/model to a Silicon Labs device via Raspberry Pi (SCP + SSH).

    Steps:
      1) Uploads the local file to the Raspberry Pi.
      2) Runs Commander on the Pi to auto-detect J-Link and device part.
      3) Flashes the image on the connected board.

    Requirements on the Raspberry Pi:
      - Commander installed and accessible (use a wrapper if needed).
      - Correct USB permissions (udev rules), so flashing works without sudo.
    """
    click.echo(f"Initializing RPi deployment for: {uri}")
    click.echo(f"Target: {rpi_user}@{rpi_host} (commander: {commander or 'commander'})")

    try:
        deployer = RPiDeployer(
            rpi_host=rpi_host,
            rpi_user=rpi_user,
            local_file_path=uri,
            commander_path=commander or "commander",
            jlink_serial=serial,
        )

        if remote_path:
            # Override default /tmp/<basename> with the provided remote path
            # by calling the internal steps directly.
            ssh_target = f"{rpi_user}@{rpi_host}"
            logger.log_model_deployment(f"Targeting remote Raspberry Pi: {ssh_target}")
            print("Connected to Raspberry Pi")

            deployer._scp_firmware(uri, ssh_target, remote_path)
            print("Firmware uploaded")

            # Resolve serial (interactive if not provided)
            serial_to_use = serial
            if not serial_to_use:
                serials = deployer._get_jlink_serials(ssh_target)
                if not serials:
                    raise RuntimeError("No J-Link devices connected.")
                if len(serials) == 1:
                    serial_to_use = serials[0]
                else:
                    print("\nMultiple devices detected. Please select one:")
                    for i, s in enumerate(serials, 1):
                        print(f"{i}) J-Link Serial: {s}")
                    choice = click.prompt(f"\nSelect board [1-{len(serials)}]", type=int)
                    serial_to_use = serials[choice - 1]

            device_name = deployer._get_device_name(ssh_target, serial_to_use)
            deployer._flash_firmware(ssh_target, remote_path, serial_to_use, device_name)
        else:
            # Standard deploy uses /tmp/<filename> (now with interactive selection)
            deployer.deploy(jlink_serial=serial)

        click.echo("✓ Deployment finished successfully!")
        logger.log_model_deployment(f"Successfully deployed {uri} to {rpi_host}", level="Success")
    except Exception as e:
        error_msg = f"Deployment failed: {e}"
        click.echo(f"✗ {error_msg}", err=True)
        logger.log_model_deployment(error_msg, level="Error")
        raise click.Abort()


if __name__ == "__main__":
    main()