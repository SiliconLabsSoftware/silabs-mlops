"""
Silicon Labs MLOps SDK CLI.
"""
import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import click

from sml.ops import model
from sml.ops.data.ingest import DataIngestor, IngestConfig
from sml.ops.config import Config
from sml.ops.logs import Logger


@click.group()
def cli():
    """Silicon Labs MLOps SDK CLI."""
    pass


@cli.group()
def ops():
    """MLOps commands."""
    pass


@ops.command()
@click.option("--file", required=True, type=click.Path(exists=True), help="Path to JSON data file to ingest.")
@click.option("--endpoint", help="ZeroBus server endpoint (overrides .env)")
@click.option("--workspace", help="Databricks workspace URL (overrides .env)")
@click.option("--table", help="Unity Catalog table name (overrides .env)")
@click.option("--client-id", help="Service principal client ID (overrides .env)")
@click.option("--client-secret", help="Service principal client secret (overrides .env)")
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
        click.echo(f"Error: Missing required configuration fields: {', '.join(missing)}")
        click.echo("Set these in your .env file or provide via command-line options.")
        raise click.Abort()

    ingestor = DataIngestor(config)
    success = ingestor.ingest()
    click.echo("✓ Ingestion completed successfully." if success else "✗ Ingestion failed.")


@ops.group(name="logs", invoke_without_command=True)
@click.option("--type", "event_type", help='Filter logs by event type (for example: "Data Ingestion").')
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


@ops.command()
@click.option(
    "--model-path",
    "--model",
    required=True,
    type=click.Path(exists=True),
    help="Path to .tflite or compiled .zip model.",
)
@click.option("--device-id", "--device", help="Target device ID/Serial (auto-discovered if omitted).")
@click.option("--output", type=click.Path(), help="Directory for profiling results.")
@click.option("--accelerator", default="mvpv1", show_default=True, help="Hardware accelerator target.")
@click.option("--platform", help="Target platform board (e.g., brd2605, brd2608a).")
@click.option("--gui", is_flag=True, help="Launch Profiler GUI.")
@click.option(
    "--volume-path",
    help="Directly upload results to a Databricks Volume and delete local artifacts.",
)
def profile(model_path, device_id, output, accelerator, platform, gui, volume_path):
    """Profile a model using the MVP Profiler (mvp_profiler)."""
    try:
        result = model.profile(
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


if __name__ == "__main__":
    cli()

