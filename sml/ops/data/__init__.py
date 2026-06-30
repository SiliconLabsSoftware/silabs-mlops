# SPDX-License-Identifier: LicenseRef-MSLA
# @file __init__.py
# @brief Silicon Labs MLOps SDK - Data Module
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
Silicon Labs MLOps SDK - Data Module

Simple API for ingesting IoT sensor data to Databricks Delta Lake via ZeroBus.

Usage:
    >>> from sml.ops import data
    >>>
    >>> # Step 1: Configure your Databricks credentials
    >>> data.config(
    ...     server_endpoint="1234567890123456.zerobus.us-west-2.cloud.databricks.com",
    ...     workspace_url="https://dbc-a1b2c3d4-e5f6.cloud.databricks.com",
    ...     table_name="main.default.sensor_data",
    ...     client_id="your-client-id",
    ...     client_secret="your-client-secret"
    ... )
    >>>
    >>> # Step 2: Ingest your data
    >>> sensor_data = [{"device_id": "sensor-1", "temperature": 22.5}]
    >>> data.ingest(sensor_data)
"""

from typing import List, Dict, Any, Optional, Callable

from .ingest import IngestConfig, DataIngestor, IngestionService
from sml.ops.config import Config

_config: Optional[IngestConfig] = None

__all__ = [
    "config",
    "ingest",
    "ingest_from_file",
    "file_ingest",
    "serve",
    "IngestionService",
]


def config(
    server_endpoint: str,
    workspace_url: str,
    table_name: str,
    client_id: str,
    client_secret: str,
) -> None:
    """
    Configure your Databricks credentials for data ingestion.

    Call this once to set up your credentials. Then you can call ingest() multiple times
    without repeating the credentials.

    Args:
        server_endpoint: ZeroBus server endpoint (e.g., "1234567890123456.zerobus.us-west-2.cloud.databricks.com")
        workspace_url: Databricks workspace URL (e.g., "https://dbc-a1b2c3d4-e5f6.cloud.databricks.com")
        table_name: Unity Catalog table name (e.g., "main.default.sensor_data")
        client_id: Service principal application ID
        client_secret: Service principal secret

    Example:
        >>> from sml.ops import data
        >>>
        >>> # Configure once
        >>> data.config(
        ...     server_endpoint="1234567890123456.zerobus.us-west-2.cloud.databricks.com",
        ...     workspace_url="https://dbc-a1b2c3d4-e5f6.cloud.databricks.com",
        ...     table_name="main.default.sensor_data",
        ...     client_id="your-client-id",
        ...     client_secret="your-client-secret"
        ... )
    """
    global _config
    _config = IngestConfig(
        server_endpoint=server_endpoint,
        workspace_url=workspace_url,
        table_name=table_name,
        client_id=client_id,
        client_secret=client_secret,
    )

    Config.update(
        ZEROBUS_SERVER_ENDPOINT=server_endpoint,
        ZEROBUS_WORKSPACE_URL=workspace_url,
        ZEROBUS_TABLE_NAME=table_name,
        ZEROBUS_CLIENT_ID=client_id,
        ZEROBUS_CLIENT_SECRET=client_secret,
    )
    print("[OK] Configuration saved. You can now use data.ingest() to send data.")


def ingest(data: List[Dict[str, Any]]) -> bool:
    """
    Ingest data to Databricks Delta Lake via ZeroBus.

    You must call data.config() first to set up your credentials.

    Args:
        data: List of dictionaries representing records to ingest

    Returns:
        True if ingestion succeeded, False otherwise

    Example:
        >>> from sml.ops import data
        >>>
        >>> # Configure first (once)
        >>> data.config(
        ...     server_endpoint="...",
        ...     workspace_url="...",
        ...     table_name="...",
        ...     client_id="...",
        ...     client_secret="..."
        ... )
        >>>
        >>> # Ingest data (can be called multiple times)
        >>> sensor_data = [
        ...     {"device_id": "sensor-1", "temperature": 22.5, "humidity": 55},
        ...     {"device_id": "sensor-2", "temperature": 23.1, "humidity": 60}
        ... ]
        >>> data.ingest(sensor_data)
    """
    if _config is None:
        print("Error: Configuration not set. Call data.config() first.")
        return False

    ingestor = DataIngestor(_config)
    return ingestor.ingest(data=data)


def ingest_from_file(file_path: str) -> bool:
    """
    Ingest data from a JSON file to Databricks Delta Lake via ZeroBus.

    You must call data.config() first to set up your credentials.

    Args:
        file_path: Path to JSON file (supports JSON array or JSON lines format)

    Returns:
        True if ingestion succeeded, False otherwise

    Example:
        >>> from sml.ops import data
        >>>
        >>> # Configure first
        >>> data.config(server_endpoint="...", workspace_url="...", ...)
        >>>
        >>> # Ingest from file
        >>> data.ingest_from_file("sensor_data.json")
    """
    if _config is None:
        print("Error: Configuration not set. Call data.config() first.")
        return False

    ingestor = DataIngestor(_config)
    return ingestor.ingest(buffer_path=file_path)


def file_ingest(file_path: str, volume_path: str, metadata: Dict[str, Any]) -> bool:
    """
    Comprehensive file ingestion: Upload file to Volume and ingest metadata.

    You must call data.config() first to set up your credentials.

    Args:
        file_path: Local path to the file
        volume_path: Destination path in Databricks Unity Catalog Volume
        metadata: Dictionary of metadata to ingest via ZeroBus

    Returns:
        True if both upload and ingestion succeeded, False otherwise

    Example:
        >>> from sml.ops import data
        >>>
        >>> data.config(...)
        >>> metadata = {"device_id": "rpi-1", "file_name": "data.csv"}
        >>> data.file_ingest("data.csv", "/Volumes/main/default/data/data.csv", metadata)
    """
    if _config is None:
        print("Error: Configuration not set. Call data.config() first.")
        return False

    ingestor = DataIngestor(_config)
    return ingestor.file_ingest(file_path, volume_path, metadata)


def _ingest_config_from_env_or_stored() -> Optional[IngestConfig]:
    """Build IngestConfig from module state or Config env vars."""
    if _config is not None:
        return _config

    if not all(
        [
            Config.ZEROBUS_SERVER_ENDPOINT,
            Config.ZEROBUS_WORKSPACE_URL,
            Config.ZEROBUS_TABLE_NAME,
            Config.ZEROBUS_CLIENT_ID,
            Config.ZEROBUS_CLIENT_SECRET,
        ]
    ):
        return None

    return IngestConfig(
        server_endpoint=Config.ZEROBUS_SERVER_ENDPOINT,
        workspace_url=Config.ZEROBUS_WORKSPACE_URL,
        table_name=Config.ZEROBUS_TABLE_NAME,
        client_id=Config.ZEROBUS_CLIENT_ID,
        client_secret=Config.ZEROBUS_CLIENT_SECRET,
        volume_path=Config.DATABRICKS_VOLUME_PATH,
    )


def serve(
    monitor_dir: str,
    volume_path: str,
    *,
    pattern: str = "*.wav",
    workers: int = 4,
    commander_path: Optional[str] = None,
    metadata_builder: Optional[Callable] = None,
    block: bool = True,
    log: Optional[Callable[[str], None]] = None,
) -> Optional[IngestionService]:
    """
    Start the continuous file-watcher ingestion service.

    Uses credentials from data.config() or environment variables.

    Args:
        monitor_dir: Local directory to watch for new files
        volume_path: Databricks Unity Catalog volume base path
        pattern: Glob pattern for files to ingest (default: '*.wav')
        workers: Number of parallel uploader threads (default: 4)
        commander_path: Path to commander-cli for hardware detection
        metadata_builder: Optional callable(Path) -> dict for custom metadata
        block: If True, block until Ctrl+C (default: True)
        log: Optional logging callback

    Returns:
        IngestionService instance, or None if configuration is missing
    """
    config = _ingest_config_from_env_or_stored()
    if config is None:
        print("Error: Configuration not set. Call data.config() first or set .env.")
        return None

    service = IngestionService(
        config=config,
        monitor_dir=monitor_dir,
        volume_path=volume_path,
        pattern=pattern,
        workers=workers,
        commander_path=commander_path,
        metadata_builder=metadata_builder,
        log=log,
    )
    service.start()
    if block:
        service.wait()
    return service
