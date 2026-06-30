# SPDX-License-Identifier: LicenseRef-MSLA
# @file cli.py
# @brief Silicon Labs MLOps SDK CLI.
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
Silicon Labs MLOps SDK CLI.
"""

import os
import shutil
import asyncio
from pathlib import Path

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import click

from sml.ops.data.ingest import DataIngestor, IngestConfig
from sml.ops.config import Config
from sml.ops.logs import Logger
from sml.ops.model.deployer import RPiDeployer


_cli_logger = Logger()

_DEFAULT_VOICE_RESULT_UUID = "f7ee5e0c-1882-4c85-a6f1-8d6f81f10902"
_DEFAULT_AUDIO_DATA_UUID = "f7ee5e0c-1882-4c85-a6f1-8d6f81f10903"
_DEFAULT_OUTPUT_DIR = "./audio_samples"
_DEFAULT_LABELS = ["on", "off", "unknown"]
_DEFAULT_SAMPLE_RATE = 16000
_DEFAULT_CHANNELS = 1
_DEFAULT_SAMPLE_WIDTH = 2
_DEFAULT_BUFFER_SIZE = 32000
_DEFAULT_SCAN_TIMEOUT = 10.0


def _resolve_ble_value(cli_value, config_value, default):
    if cli_value is not None:
        return cli_value
    if config_value is not None:
        return config_value
    return default


def _resolve_ble_int(cli_value, config_value, default):
    resolved = _resolve_ble_value(cli_value, config_value, default)
    return int(resolved) if resolved is not None else default


def _resolve_ble_float(cli_value, config_value, default):
    resolved = _resolve_ble_value(cli_value, config_value, default)
    return float(resolved) if resolved is not None else default


@click.group()
def cli():
    """Silicon Labs MLOps SDK CLI."""
    pass


@cli.group()
def ops():
    """MLOps commands."""
    pass


@ops.command()
@click.option(
    "--file",
    required=True,
    type=click.Path(exists=True),
    help="Path to JSON data file to ingest.",
)
@click.option("--endpoint", help="ZeroBus server endpoint (overrides .env)")
@click.option("--workspace", help="Databricks workspace URL (overrides .env)")
@click.option("--table", help="Unity Catalog table name (overrides .env)")
@click.option("--client-id", help="Service principal client ID (overrides .env)")
@click.option(
    "--client-secret", help="Service principal client secret (overrides .env)"
)
def ingest(file, endpoint, workspace, table, client_id, client_secret):
    """Ingest JSON data to Databricks via ZeroBus."""
    config = IngestConfig(
        server_endpoint=endpoint or Config.ZEROBUS_SERVER_ENDPOINT,
        workspace_url=workspace or Config.ZEROBUS_WORKSPACE_URL,
        table_name=table or Config.ZEROBUS_TABLE_NAME,
        client_id=client_id or Config.ZEROBUS_CLIENT_ID,
        client_secret=client_secret or Config.ZEROBUS_CLIENT_SECRET,
        buffer_path=file,
    )

    missing = []
    if not config.server_endpoint:
        missing.append("ZEROBUS_SERVER_ENDPOINT")
    if not config.workspace_url:
        missing.append("ZEROBUS_WORKSPACE_URL")
    if not config.table_name:
        missing.append("ZEROBUS_TABLE_NAME")
    if not config.client_id:
        missing.append("ZEROBUS_CLIENT_ID")
    if not config.client_secret:
        missing.append("ZEROBUS_CLIENT_SECRET")

    if missing:
        click.echo(
            f"Error: Missing required configuration fields: {', '.join(missing)}"
        )
        click.echo("Set these in your .env file or provide via command-line options.")
        raise click.Abort()

    ingestor = DataIngestor(config)
    success = ingestor.ingest()
    click.echo(
        "✓ Ingestion completed successfully." if success else "✗ Ingestion failed."
    )


@ops.group(name="logs", invoke_without_command=True)
@click.option(
    "--type",
    "event_type",
    help='Filter logs by event type (for example: "Data Ingestion").',
)
@click.pass_context
def logs(ctx, event_type):
    """View and manage local log history."""
    if ctx.invoked_subcommand is None:
        logger = Logger()
        logger.view(event_type=event_type)


@logs.command(name="sync")
def sync_logs():
    """Sync local logs to Databricks."""
    logger = Logger()
    logger.sync_to_databricks()


@ops.group(name="profile", invoke_without_command=True)
@click.option(
    "--model-path",
    "--model",
    type=click.Path(exists=True),
    help="Path to .tflite or compiled .zip model.",
)
@click.option(
    "--device-id",
    "--device",
    help="Target device ID/Serial (auto-discovered if omitted).",
)
@click.option("--output", type=click.Path(), help="Directory for profiling results.")
@click.option(
    "--accelerator",
    default="mvpv1",
    show_default=True,
    help="Hardware accelerator target.",
)
@click.option("--platform", help="Target platform board (e.g., brd2605, brd2608a).")
@click.option("--gui", is_flag=True, help="Launch Profiler GUI.")
@click.option(
    "--volume-path",
    help="Directly upload results to a Databricks Volume and delete local artifacts.",
)
@click.pass_context
def profile(
    ctx, model_path, device_id, output, accelerator, platform, gui, volume_path
):
    """Profile a model using the MVP Profiler (mvp_profiler)."""
    if ctx.invoked_subcommand is not None:
        return

    from sml.ops.model import profile as run_profile

    if not model_path:
        raise click.UsageError("Missing required option '--model-path' / '--model'.")

    try:
        result = run_profile(
            model_path=model_path,
            device_id=device_id,
            output_dir=output,
            gui=gui,
            accelerator=accelerator,
            platform=platform,
            volume_path=volume_path,
        )
        if not gui:
            click.echo(f"[OK] Profiling completed. Results in: {result.output_dir}")
    except Exception as e:
        click.echo(f"[FAIL] Profiling failed: {e}", err=True)
        raise click.Abort()


def _install_profiler(dest, force) -> bool:
    """Install the MVP Profiler (mvp_profiler). Returns True on success or skip."""
    from sml.ops.model.profiler import NPUProfiler

    profiler = NPUProfiler()
    click.echo("Downloading mvp_profiler...")
    try:
        installed_path = profiler.install_profiler(dest=dest, force=force)
    except FileExistsError as e:
        click.echo(f"[SKIP] {e}")
        return True
    except Exception as e:
        click.echo(f"[FAIL] mvp_profiler installation failed: {e}", err=True)
        return False

    click.echo(f"[OK] mvp_profiler installed at: {installed_path}")

    if (
        shutil.which("mvp_profiler") is None
        and shutil.which("mvp_profiler.exe") is None
    ):
        install_dir = str(Path(installed_path).parent)
        click.echo(
            f"Note: add '{install_dir}' to your PATH to run 'mvp_profiler' directly."
        )
        click.echo("The SDK will also auto-detect it in ~/.sml/bin.")
    return True


def _install_commander(dest, force, rpi_host=None, rpi_user=None) -> bool:
    """Install Simplicity Commander (commander-cli). Returns True on success or skip."""
    from sml.ops.model.commander import CommanderInstaller

    installer = CommanderInstaller()
    click.echo("Downloading Simplicity Commander...")
    try:
        if rpi_host:
            installed_path = installer.install_commander_remote(
                rpi_host=rpi_host,
                rpi_user=rpi_user or "pi",
                dest=dest or "~/.sml/bin",
                force=force,
            )
            click.echo(
                f"[OK] Simplicity Commander installed on Pi at: {installed_path}"
            )
        else:
            installed_path = installer.install_commander(dest=dest, force=force)
            click.echo(f"[OK] Simplicity Commander installed at: {installed_path}")
            if (
                shutil.which("commander-cli") is None
                and shutil.which("commander") is None
            ):
                install_dir = str(Path(installed_path).parent)
                click.echo(
                    f"Note: add '{install_dir}' to your PATH to run 'commander-cli' directly."
                )
    except FileExistsError as e:
        click.echo(f"[SKIP] {e}")
        return True
    except Exception as e:
        click.echo(f"[FAIL] Simplicity Commander installation failed: {e}", err=True)
        return False
    return True


@cli.command(name="install")
@click.option(
    "--tool",
    type=click.Choice(["all", "commander", "profiler"]),
    help="Which external tool(s) to install (required): 'commander', 'profiler', or 'all'.",
)
@click.option(
    "--dest",
    type=click.Path(file_okay=False),
    help="Directory to install into (default: ~/.sml/bin).",
)
@click.option("--force", is_flag=True, help="Overwrite existing installation(s).")
@click.option(
    "--rpi-host",
    help="Raspberry Pi hostname/IP. When provided, commander is installed on the Pi via SCP/SSH.",
)
@click.option(
    "--rpi-user",
    default="pi",
    show_default=True,
    help="SSH username on the Raspberry Pi (used with --rpi-host).",
)
@click.pass_context
def install(ctx, tool, dest, force, rpi_host, rpi_user):
    """Download and install external tools."""
    if tool is None:
        click.echo(ctx.get_help())
        click.echo(
            "\nNo tool selected. Specify --tool with 'commander', 'profiler', or 'all'."
        )
        return

    failures = []
    if tool in ("all", "profiler") and not _install_profiler(dest, force):
        failures.append("mvp_profiler")
    if tool in ("all", "commander") and not _install_commander(
        dest, force, rpi_host=rpi_host, rpi_user=rpi_user
    ):
        failures.append("commander")

    if failures:
        click.echo(f"[FAIL] Failed to install: {', '.join(failures)}", err=True)
        raise click.Abort()


@ops.command(name="deploy")
@click.option(
    "--uri", required=True, help="Local file path to firmware/model (.s37/.bin/.hex)."
)
@click.option("--serial", help="Target J-Link serial number (optional).")
@click.option("--rpi-host", required=True, help="Target Pi IP/Hostname.")
@click.option(
    "--rpi-user", default="aimlraspberry", show_default=True, help="SSH user."
)
@click.option("--remote-path", help="Optional remote path on Pi.")
def deploy(uri, serial, rpi_host, rpi_user, remote_path):
    """
    Deploy firmware/model to a Silicon Labs device via Raspberry Pi (SCP + SSH).

    Uploads the file to the Pi, runs Commander for J-Link detection, then flashes.
    """
    click.echo(f"Initializing RPi deployment for: {uri}")
    click.echo(f"Target: {rpi_user}@{rpi_host}")

    try:
        deployer = RPiDeployer(
            rpi_host=rpi_host,
            rpi_user=rpi_user,
            local_file_path=uri,
            jlink_serial=serial,
        )

        if remote_path:
            ssh_target = f"{rpi_user}@{rpi_host}"
            _cli_logger.log_model_deployment(
                f"Targeting remote Raspberry Pi: {ssh_target}"
            )
            click.echo("Connected to Raspberry Pi")

            deployer._scp_firmware(uri, ssh_target, remote_path)
            click.echo("Firmware uploaded")

            serial_to_use = serial
            if not serial_to_use:
                serials = deployer._get_jlink_serials(ssh_target)
                if not serials:
                    raise RuntimeError("No J-Link devices connected.")
                if len(serials) == 1:
                    serial_to_use = serials[0]
                else:
                    click.echo("\nMultiple devices detected. Please select one:")
                    for i, s in enumerate(serials, 1):
                        click.echo(f"{i}) J-Link Serial: {s}")
                    choice = click.prompt(
                        f"\nSelect board [1-{len(serials)}]", type=int
                    )
                    serial_to_use = serials[choice - 1]

            device_name = deployer._get_device_name(ssh_target, serial_to_use)
            deployer._flash_firmware(
                ssh_target, remote_path, serial_to_use, device_name
            )
        else:
            deployer.deploy(jlink_serial=serial)

        click.echo("✓ Deployment finished successfully!")
        _cli_logger.log_model_deployment(
            f"Successfully deployed {uri} to {rpi_host}", level="Success"
        )
    except Exception as e:
        error_msg = f"Deployment failed: {e}"
        click.echo(f"✗ {error_msg}", err=True)
        _cli_logger.log_model_deployment(error_msg, level="Error")
        raise click.Abort()


@ops.group()
def ble():
    """BLE data collection commands."""
    pass


@ble.command(name="receive")
@click.option(
    "--device-name",
    default=None,
    help="BLE device name (env: BLE_DEVICE_NAME).",
)
@click.option(
    "--device-address",
    default=None,
    help="BLE MAC address (env: BLE_DEVICE_ADDRESS).",
)
@click.option(
    "--output-dir",
    default=None,
    help="Directory for saved .wav files (env: BLE_OUTPUT_DIR).",
)
@click.option(
    "--voice-result-uuid",
    default=None,
    help="GATT UUID for voice detection events (env: BLE_VOICE_RESULT_UUID).",
)
@click.option(
    "--audio-data-uuid",
    default=None,
    help="GATT UUID for audio stream (env: BLE_AUDIO_DATA_UUID).",
)
@click.option(
    "--labels",
    default=None,
    help="Comma-separated keyword labels (env: BLE_LABELS).",
)
@click.option(
    "--sample-rate",
    type=int,
    default=None,
    help="Audio sample rate in Hz (env: BLE_SAMPLE_RATE).",
)
@click.option(
    "--channels",
    type=int,
    default=None,
    help="Audio channels (env: BLE_CHANNELS).",
)
@click.option(
    "--sample-width",
    type=int,
    default=None,
    help="Bytes per sample (env: BLE_SAMPLE_WIDTH).",
)
@click.option(
    "--buffer-size",
    type=int,
    default=None,
    help="Audio buffer size in bytes (env: BLE_BUFFER_SIZE).",
)
@click.option(
    "--scan-timeout",
    type=float,
    default=None,
    help="BLE scan timeout in seconds (env: BLE_SCAN_TIMEOUT).",
)
def receive(
    device_name,
    device_address,
    output_dir,
    voice_result_uuid,
    audio_data_uuid,
    labels,
    sample_rate,
    channels,
    sample_width,
    buffer_size,
    scan_timeout,
):
    """Connect to a BLE device and save keyword-triggered audio samples."""
    from sml.ops.ble import config as ble_config, BLEReceiver

    resolved_labels = _resolve_ble_value(labels, Config.BLE_LABELS, None)
    if isinstance(resolved_labels, str):
        label_list = [label.strip() for label in resolved_labels.split(",") if label.strip()]
    elif resolved_labels is None:
        label_list = _DEFAULT_LABELS
    else:
        label_list = resolved_labels

    resolved_config = {
        "device_name": _resolve_ble_value(
            device_name, Config.BLE_DEVICE_NAME, ""
        ),
        "device_address": _resolve_ble_value(
            device_address, Config.BLE_DEVICE_ADDRESS, ""
        ),
        "voice_result_uuid": _resolve_ble_value(
            voice_result_uuid,
            Config.BLE_VOICE_RESULT_UUID,
            _DEFAULT_VOICE_RESULT_UUID,
        ),
        "audio_data_uuid": _resolve_ble_value(
            audio_data_uuid,
            Config.BLE_AUDIO_DATA_UUID,
            _DEFAULT_AUDIO_DATA_UUID,
        ),
        "output_dir": _resolve_ble_value(
            output_dir, Config.BLE_OUTPUT_DIR, _DEFAULT_OUTPUT_DIR
        ),
        "sample_rate": _resolve_ble_int(
            sample_rate, Config.BLE_SAMPLE_RATE, _DEFAULT_SAMPLE_RATE
        ),
        "channels": _resolve_ble_int(
            channels, Config.BLE_CHANNELS, _DEFAULT_CHANNELS
        ),
        "sample_width": _resolve_ble_int(
            sample_width, Config.BLE_SAMPLE_WIDTH, _DEFAULT_SAMPLE_WIDTH
        ),
        "buffer_size": _resolve_ble_int(
            buffer_size, Config.BLE_BUFFER_SIZE, _DEFAULT_BUFFER_SIZE
        ),
        "scan_timeout": _resolve_ble_float(
            scan_timeout, Config.BLE_SCAN_TIMEOUT, _DEFAULT_SCAN_TIMEOUT
        ),
        "labels": label_list,
    }

    ble_config(**resolved_config)

    def _emit(message: str):
        click.echo(message)
        _cli_logger.log_data_collection(message)

    receiver = BLEReceiver(log=_emit)

    try:
        asyncio.run(receiver.start())
    except KeyboardInterrupt:
        receiver.stop()
        click.echo("\nStopping...")
        _cli_logger.log_data_collection("BLE receive stopped by user.")
    except Exception as e:
        click.echo(f"[FAIL] BLE receive failed: {e}", err=True)
        _cli_logger.log_data_collection(
            f"BLE receive failed: {e}", level="Error"
        )
        raise click.Abort()


if __name__ == "__main__":
    cli()
