"""
SiLabs MLOps Data Module

Simple API for ingesting IoT sensor data to Databricks Delta Lake via ZeroBus.

Usage:
    >>> from silabs_mlops import data
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
from typing import List, Dict, Any, Optional

from .ingest import IngestConfig, DataIngestor, ZerobusIngestClient

# Module-level configuration storage
_config: Optional[IngestConfig] = None

__all__ = [
    "config",
    "ingest",
    "ingest_from_file",
]


def config(
    server_endpoint: str,
    workspace_url: str,
    table_name: str,
    client_id: str,
    client_secret: str
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
        >>> from silabs_mlops import data
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
        client_secret=client_secret
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
        >>> from silabs_mlops import data
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
        >>> from silabs_mlops import data
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

