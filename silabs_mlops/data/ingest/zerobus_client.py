"""
ZeroBus client wrapper for Databricks ingestion.
"""
from typing import Dict, Any, List, Optional, Callable
try:
    from zerobus.sdk.sync import ZerobusSdk
    from zerobus.sdk.shared import RecordType, StreamConfigurationOptions, TableProperties
    ZEROBUS_AVAILABLE = True
except ImportError:
    ZEROBUS_AVAILABLE = False


class ZerobusIngestClient:
    """
    Wrapper around the Databricks ZeroBus SDK for ingesting data to Delta tables.
    
    Provides a clean interface for:
    - Establishing secure streaming connections
    - Ingesting JSON records (single or batch)
    - Handling acknowledgements
    - Managing connection lifecycle
    """

    def __init__(
        self,
        server_endpoint: str,
        workspace_url: str,
        table_name: str,
        client_id: str,
        client_secret: str,
        ack_callback: Optional[Callable[[Any], None]] = None,
    ):
        """
        Initialize ZeroBus client.
        
        Args:
            server_endpoint: ZeroBus server endpoint
            workspace_url: Databricks workspace URL
            table_name: Unity Catalog table name
            client_id: Service principal application ID
            client_secret: Service principal secret
            ack_callback: Optional callback for acknowledgement tracking
        """
        if not ZEROBUS_AVAILABLE:
            raise ImportError(
                "databricks-zerobus-ingest-sdk is not installed. "
                "Install it with: pip install databricks-zerobus-ingest-sdk"
            )
        
        self.server_endpoint = server_endpoint
        self.workspace_url = workspace_url
        self.table_name = table_name
        self.client_id = client_id
        self.client_secret = client_secret
        self.ack_callback = ack_callback

        self._sdk = None
        self._stream = None

    def connect(self) -> None:
        """Initialize ZeroBus stream connection."""
        self._sdk = ZerobusSdk(self.server_endpoint, self.workspace_url)

        table_properties = TableProperties(self.table_name)
        
        # Use JSON record type for simplicity (recommended for IoT sensor data)
        options = StreamConfigurationOptions(
            record_type=RecordType.JSON,
            ack_callback=self.ack_callback if self.ack_callback else None
        )

        self._stream = self._sdk.create_stream(
            self.client_id,
            self.client_secret,
            table_properties,
            options,
        )

    def ingest_record(self, record: Dict[str, Any], wait_for_ack: bool = True) -> None:
        """
        Ingest a single JSON record into ZeroBus.
        
        Args:
            record: Dictionary representing the record to ingest
            wait_for_ack: Whether to block until acknowledgement is received
        
        Raises:
            RuntimeError: If stream is not initialized
        """
        if not self._stream:
            raise RuntimeError("ZeroBus stream not initialized. Call connect() first.")

        ack = self._stream.ingest_record(record)

        if wait_for_ack:
            ack.wait_for_ack()

    def ingest_batch(self, records: List[Dict[str, Any]], wait_for_ack: bool = True) -> None:
        """
        Ingest multiple records sequentially.
        
        Args:
            records: List of dictionaries to ingest
            wait_for_ack: Whether to wait for acknowledgement on each record
        """
        for record in records:
            self.ingest_record(record, wait_for_ack=wait_for_ack)

    def close(self) -> None:
        """Close ZeroBus stream safely."""
        if self._stream:
            self._stream.close()
            self._stream = None
