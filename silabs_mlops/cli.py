"""
SiLabs MLOps CLI
================
User-facing commands for:
  • Data ingestion to Databricks (via ZeroBus)
  • Model registry listing
  • Raspberry Pi deployment (SCP + SSH + Commander on the Pi)
  • NPU profiling (headless or GUI)

Note:
  - Local/host deployment via Commander has been removed as requested.
  - Raspberry Pi deployment requires Commander to be installed on the Pi
    and accessible by the provided path (or via a wrapper).
"""

import click
import os

# Internal package imports
from silabs_mlops.data.ingest import DataIngestor, IngestConfig
from silabs_mlops.config import Config
from silabs_mlops import model
from silabs_mlops.model.registry import ArtifactRegistry
from silabs_mlops.model.rpi_deployer import RPiDeployer


@click.group()
def main():
    """SiLabs MLOps CLI"""
    pass


# -----------------------------------------------------------------------------
# Ingestion
# -----------------------------------------------------------------------------
@main.command()
@click.option('--file', required=True, type=click.Path(exists=True), help='Path to JSON data file to ingest.')
@click.option('--endpoint', help='ZeroBus server endpoint (overrides .env)')
@click.option('--workspace', help='Databricks workspace URL (overrides .env)')
@click.option('--table', help='Unity Catalog table name (overrides .env)')
@click.option('--client-id', help='Service principal client ID (overrides .env)')
@click.option('--client-secret', help='Service principal client secret (overrides .env)')
def ingest(file, endpoint, workspace, table, client_id, client_secret):
    """
    Ingest JSON data to Databricks via ZeroBus.

    Configuration can be provided via .env or CLI options.

    Example:
        silabs-mlops ingest --file sensor_data.json
    """
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
        click.echo(f"Error: Missing required configuration fields: {', '.join(missing)}")
        click.echo("Set these in your .env file or provide via command-line options.")
        raise click.Abort()

    ingestor = DataIngestor(config)
    success = ingestor.ingest()
    click.echo("✓ Ingestion completed successfully." if success else "✗ Ingestion failed.")


# -----------------------------------------------------------------------------
# Model management group (list, deploy via Raspberry Pi only)
# -----------------------------------------------------------------------------
@main.group()
def model_cmd():
    """Manage and deploy models for edge devices."""
    pass


@model_cmd.command(name="list")
def list_artifacts():
    """
    List all registered artifacts from artifacts.yaml.

    Example:
        silabs-mlops model list
    """
    registry = ArtifactRegistry()
    artifacts = registry.list_artifacts()

    if not artifacts:
        click.echo("No artifacts registered. Add entries to artifacts.yaml.")
        return

    click.echo("\nRegistered Artifacts (from artifacts.yaml):\n")
    click.echo(f"  {'NAME':<20} {'VERSION':<10} {'TYPE':<12} DESCRIPTION")
    click.echo(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*30}")
    for name, meta in artifacts.items():
        click.echo(
            f"  {name:<20} {meta.get('version', 'N/A'):<10} "
            f"{meta.get('type', 'N/A'):<12} {meta.get('description', '')}"
        )
    click.echo("")


@model_cmd.command(name="deploy")
@click.option('--uri', required=True, help=(
    'Local file path to firmware/model (.s37/.bin/.hex). '
    'Note: Registry/MLflow/Volumes are not resolved here; pass a concrete file path.'
))
@click.option('--commander', help='Path to Simplicity Commander executable on the Raspberry Pi '
                                  '(e.g., /usr/local/bin/commander-wrapper or "commander" if in PATH).')
@click.option('--rpi-host', required=True, help='Target Raspberry Pi IP/Hostname for remote flashing via SSH.')
@click.option('--rpi-user', default='pi', show_default=True, help='Target Raspberry Pi SSH user.')
@click.option('--remote-path', help='Optional absolute path on Pi where the file should be uploaded '
                                    '(defaults to /tmp/<filename>).')
def deploy(uri, commander, rpi_host, rpi_user, remote_path):
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
        )

        if remote_path:
            # Override default /tmp/<basename> with the provided remote path
            # by calling the internal steps directly.
            import logging
            logger = logging.getLogger(__name__)
            ssh_target = f"{rpi_user}@{rpi_host}"
            logger.info(f"Targeting remote Raspberry Pi: {ssh_target}")
            print("Connected to Raspberry Pi")

            deployer._scp_firmware(uri, ssh_target, remote_path)
            print("Firmware uploaded")

            jlink_serial = deployer._get_jlink_serial(ssh_target)
            device_name = deployer._get_device_name(ssh_target, jlink_serial)
            deployer._flash_firmware(ssh_target, remote_path, jlink_serial, device_name)
        else:
            # Standard deploy uses /tmp/<filename>
            deployer.deploy()

        click.echo("✓ Deployment finished successfully!")
    except Exception as e:
        click.echo(f"✗ Deployment failed: {e}", err=True)
        raise click.Abort()


# -----------------------------------------------------------------------------
# Profiling
# -----------------------------------------------------------------------------
@main.command()
@click.option('--model-path', '--model', required=True, type=click.Path(exists=True),
              help='Path to .tflite or compiled .zip model.')
@click.option('--device-id', '--device', help='Target device ID/Serial (auto-discovered if omitted).')
@click.option('--output', type=click.Path(), help='Directory for profiling results.')
@click.option('--accelerator', default='mvpv1', show_default=True, help='Hardware accelerator target.')
@click.option('--platform', help='Target platform board (e.g., brd2605, brd2608a).')
@click.option('--gui', is_flag=True, help='Launch Profiler GUI.')
@click.option('--volume-path', help='Directly upload results to a Databricks Volume and delete local artifacts.')
def profile(model_path, device_id, output, accelerator, platform, gui, volume_path):
    """
    Profile a model using the NPU Toolkit (mvp_profiler).
    """
    try:
        result = model.profile(
            model_path=model_path,
            device_id=device_id,
            output_dir=output,
            gui=gui,
            accelerator=accelerator,
            platform=platform,
            volume_path=volume_path,  # pass-through; implement in NPUProfiler.profile if needed
        )
        if not gui:
            click.echo(f"[OK] Profiling completed. Results in: {result.output_dir}")
    except Exception as e:
        click.echo(f"[FAIL] Profiling failed: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()