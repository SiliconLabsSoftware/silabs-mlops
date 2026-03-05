"""
Command-line interface for the silabs-mlops toolkit.

This module defines user-facing commands for data ingestion, model management,
TensorFlow Lite compilation, profiling, and deployment to Silicon Labs embedded
devices. The CLI wraps internal MLOps utilities and provides a unified entry
point for interacting with Databricks, ZeroBus, and Simplicity Commander.
"""
import click
import json
import os
from silabs_mlops.data import DataIngestor, IngestConfig
from silabs_mlops.config import Config
from silabs_mlops.model import ModelDeployer, DeployConfig
from silabs_mlops.model.registry import ArtifactRegistry

@click.group()
def main():
    """SiLabs MLOps CLI"""
    pass

@main.command()
@click.option('--file', required=True, type=click.Path(exists=True), help='Path to JSON data file to ingest.')
@click.option('--endpoint', help='ZeroBus server endpoint (overrides .env)')
@click.option('--workspace', help='Databricks workspace URL (overrides .env)')
@click.option('--table', help='Unity Catalog table name (overrides .env)')
@click.option('--client-id', help='Service principal client ID (overrides .env)')
@click.option('--client-secret', help='Service principal client secret (overrides .env)')
def ingest(file, endpoint, workspace, table, client_id, client_secret):
    """
    Ingest data to Databricks via ZeroBus.
    
    Reads JSON data from FILE and ingests it to the specified Databricks table.
    Configuration can be provided via .env file or command-line options.
    
    Example:
        silabs-mlops ingest --file sensor_data.json
    """
    # Load configuration from .env or CLI options
    config = IngestConfig(
        server_endpoint=endpoint or Config.ZEROBUS_SERVER_ENDPOINT,
        workspace_url=workspace or Config.ZEROBUS_WORKSPACE_URL,
        table_name=table or Config.ZEROBUS_TABLE_NAME,
        client_id=client_id or Config.ZEROBUS_CLIENT_ID,
        client_secret=client_secret or Config.ZEROBUS_CLIENT_SECRET,
        buffer_path=file
    )
    
    # Validate configuration
    missing_fields = []
    if not config.server_endpoint:
        missing_fields.append("ZEROBUS_SERVER_ENDPOINT")
    if not config.workspace_url:
        missing_fields.append("ZEROBUS_WORKSPACE_URL")
    if not config.table_name:
        missing_fields.append("ZEROBUS_TABLE_NAME")
    if not config.client_id:
        missing_fields.append("ZEROBUS_CLIENT_ID")
    if not config.client_secret:
        missing_fields.append("ZEROBUS_CLIENT_SECRET")
    
    if missing_fields:
        click.echo(f"Error: Missing required configuration fields: {', '.join(missing_fields)}")
        click.echo("Set these in your .env file or provide via command-line options.")
        return
    
    # Create ingestor and ingest data
    ingestor = DataIngestor(config)
    success = ingestor.ingest()
    
    if success:
        click.echo("Ingestion completed successfully.")
    else:
        click.echo("Ingestion failed.")

@main.group()
def model():
    """Manage, compile, and deploy ML models for edge devices."""
    pass

@model.command(name="list")
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

@model.command()
@click.option('--input', 'model_input', required=True, help='Path to Keras model (.h5, .keras) or SavedModel directory.')
@click.option('--output', required=True, help='Path/filename for the compiled .tflite model.')
@click.option('--size-opt/--no-size-opt', default=True, help='Optimize for model size (default: True).')
def compile(model_input, output, size_opt):
    """
    Compile a TensorFlow/Keras model to optimized INT8 TFLite.
    
    Converts a standard model into a Silicon Labs optimized .tflite file 
    with automated INT8 quantization and synthetic calibration.
    """
    click.echo(f"Compiling model: {model_input}")
    try:
        from silabs_mlops.model import compile as compile_model
        tflite_path = compile_model(
            model=model_input,
            output_path=output,
            optimize_for_size=size_opt
        )
        click.echo(f"Compilation successful: {tflite_path}")
    except Exception as e:
        click.echo(f"Compilation failed: {e}", err=True)

@model.command()
@click.option('--uri', required=True, help=(
    'Artifact name from artifacts.yaml (e.g. iot_model), '
    'an MLflow URI (models:/...), '
    'a Databricks Volume URL (https://...), '
    'or a local file path.'
))
@click.option('--commander', help='Path to Simplicity Commander executable (auto-discovered if omitted).')
@click.option('--ip', help='Target device IP address.')
@click.option('--interface', default='swd', help='Connection interface (swd, jtag). Default: swd.')
@click.option('--verify/--no-verify', default=True, help='Verify flash after writing. Default: True.')
@click.option('--halt/--no-halt', default=False, help='Halt core after flashing. Default: False.')
def deploy(uri, commander, ip, interface, verify, halt):
    """
    Deploy a model to a Silicon Labs embedded device.
    
    Downloads the model (from MLflow or local) and flashes it 
    to the target device using Simplicity Commander.
    """
    click.echo(f"Initializing deployment for: {uri}")
    
    config = DeployConfig(
        model_uri=uri,
        commander_path=commander,
        device_ip=ip,
        interface=interface,
        verify=verify,
        halt=halt,
        noverify=not verify
    )
    
    try:
        deployer = ModelDeployer(config)
        deployer.deploy()
        click.echo("Deployment finished successfully!")
    except Exception as e:
        click.echo(f"Deployment failed: {e}", err=True)

@main.command()
@click.option('--model-path', '--model', required=True, type=click.Path(exists=True), help='Path to .tflite or .zip model.')
@click.option('--device-id', '--device', help='Target device ID/Serial (auto-discovered if omitted).')
@click.option('--output', type=click.Path(), help='Directory for profiling results.')
@click.option('--accelerator', default='mvpv1', help='Hardware accelerator target (default: mvpv1).')
@click.option('--platform', help='Target platform board (e.g., brd2605).')
@click.option('--gui', is_flag=True, help='Launch Profiler GUI.')
def profile(model_path, device_id, output, accelerator, platform, gui):
    """
    Profile a model using the NPU Toolkit (mvp_profiler).
    """
    try:
        from silabs_mlops import model
        result = model.profile(
            model_path=model_path,
            device_id=device_id,
            output_dir=output,
            gui=gui,
            accelerator=accelerator,
            platform=platform
        )
        if not gui:
            click.echo(f"[OK] Profiling completed. Results in: {result.output_dir}")
    except Exception as e:
        click.echo(f"[FAIL] Profiling failed: {e}")
        raise click.Abort()

if __name__ == "__main__":
    main()
