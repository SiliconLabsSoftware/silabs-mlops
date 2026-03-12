"""
ZeroBus data ingestion library for Databricks.

This module provides a clean abstraction for ingesting IoT sensor data
to Databricks Delta Lake via the ZeroBus Ingest connector.

Example:
    >>> from silabs_mlops.data.ingest import IngestConfig, DataIngestor
    >>> 
    >>> config = IngestConfig(
    ...     server_endpoint="1234567890123456.zerobus.us-west-2.cloud.databricks.com",
    ...     workspace_url="https://dbc-a1b2c3d4-e5f6.cloud.databricks.com",
    ...     table_name="main.default.sensor_data",
    ...     client_id="your-client-id",
    ...     client_secret="your-client-secret"
    ... )
    >>> 
    >>> ingestor = DataIngestor(config)
    >>> data = [{"device_id": "sensor-1", "temperature": 22.5, "humidity": 55}]
    >>> ingestor.ingest(data=data)
"""
from .config import IngestConfig
from .ingestor import DataIngestor
from .zerobus_client import ZerobusIngestClient

__all__ = ["IngestConfig", "DataIngestor", "ZerobusIngestClient"]