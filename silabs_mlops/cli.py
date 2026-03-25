"""
Silicon Labs MLOps SDK
================
User-facing commands for:
  • Data ingestion to Databricks (via ZeroBus)

Note:
  - Configuration can be provided via .env or CLI options.
"""

import os

# Suppress TensorFlow / oneDNN logging and warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import click

# Internal package imports
from silabs_mlops.data.ingest import DataIngestor, IngestConfig
from silabs_mlops.config import Config
from silabs_mlops.logs import Logger


@click.group()
def cli():
    """Silicon Labs MLOps SDK CLI."""
    pass


@cli.group()
def ops():
    """MLOps commands."""
    pass


# -----------------------------------------------------------------------------
# Ingestion
# -----------------------------------------------------------------------------
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
    """
    Ingest JSON data to Databricks via ZeroBus.

    Configuration can be provided via .env or CLI options.

    Example:
        sml ops ingest --file sensor_data.json
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


if __name__ == "__main__":
    cli()

