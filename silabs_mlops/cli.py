"""
SiLabs MLOps CLI
================
User-facing commands for:
  • NPU profiling (headless or GUI)
"""

import os
import sys

# Suppress TensorFlow / oneDNN logging and warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import click

# Internal package imports
from silabs_mlops import model
from silabs_mlops.logs import Logger


@click.group()
def main():
    """SiLabs MLOps CLI"""
    pass


# -----------------------------------------------------------------------------
# Logs
# -----------------------------------------------------------------------------
@main.group()
def logs():
    """Manage local and remote logs."""
    pass


@logs.command(name="view")
@click.option('--type', 'event_type', help='Filter by event type (e.g., Profiling).')
def logs_view(event_type):
    """View local log history."""
    logger = Logger()
    logger.view(event_type=event_type)


@logs.command(name="sync")
def logs_sync():
    """Sync local logs to Databricks Delta Table."""
    logger = Logger()
    logger.sync_to_databricks()


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
            volume_path=volume_path,
        )
        if not gui:
            click.echo(f"[OK] Profiling completed. Results in: {result.output_dir}")
    except Exception as e:
        click.echo(f"[FAIL] Profiling failed: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()