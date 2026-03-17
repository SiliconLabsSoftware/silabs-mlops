"""
Data ingestion orchestrator for ZeroBus.
"""
import json
import logging
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import IngestConfig
from .zerobus_client import ZerobusIngestClient
from silabs_mlops.logs import Logger

# Suppress verbose INFO logs from the underlying ZeroBus SDK
logging.getLogger("databricks_zerobus_ingest_sdk").setLevel(logging.WARNING)


class DataIngestor:
    """
    Orchestrates data ingestion from local buffer or direct data to Databricks via ZeroBus.
    
    Workflow:
    1. Initialize with configuration
    2. Optional: Read buffered records from file
    3. Connect to ZeroBus
    4. Ingest records to Databricks Delta Lake (Bronze layer)
    5. Clean shutdown
    """

    def __init__(self, config: IngestConfig):
        """
        Initialize data ingestor.
        
        Args:
            config: Ingestion configuration
        """
        self.config = config
        self.client = ZerobusIngestClient(
            server_endpoint=config.server_endpoint,
            workspace_url=config.workspace_url,
            table_name=config.table_name,
            client_id=config.client_id,
            client_secret=config.client_secret,
        )
        self.cli_logger = Logger()

    def _read_buffered_records(self, buffer_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Read buffered JSON records from local storage.
        
        Supports two formats:
        - JSON array: [{"key": "value"}, ...]
        - JSON lines: {"key": "value"}\n{"key2": "value2"}
        
        Args:
            buffer_path: Path to buffer file (overrides config.buffer_path)
        
        Returns:
            List of record dictionaries
        """
        path = buffer_path or self.config.buffer_path
        if not path:
            return []

        buffer_file = Path(path)
        if not buffer_file.exists():
            print(f"Warning: Buffer file not found at {path}")
            return []

        records = []
        with open(buffer_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            
            # Try JSON array format first
            try:
                records = json.loads(content)
                if isinstance(records, list):
                    return records
                elif isinstance(records, dict):
                    return [records]
            except json.JSONDecodeError:
                # Fall back to JSON lines format
                pass
            
            # Try JSON lines format
            for line in content.split('\n'):
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"Warning: Could not parse line: {line[:50]}...")

        return records

    def ingest(self, data: Optional[List[Dict[str, Any]]] = None, buffer_path: Optional[str] = None) -> bool:
        """
        Main ingestion workflow.
        
        Args:
            data: Optional data to ingest directly (if None, reads from buffer_path)
            buffer_path: Optional path to buffer file (overrides config.buffer_path)
        
        Returns:
            True if ingestion succeeded, False otherwise
        """
        # Get records from either direct data or buffer file
        if data is not None:
            records = data
        else:
            records = self._read_buffered_records(buffer_path)

        if not records:
            print("No records to ingest.")
            return False

        print(f"Preparing to ingest {len(records)} records to {self.config.table_name}...")
        self.cli_logger.log_data_ingestion(
            message=f"Starting batch ingestion of {len(records)} records to table '{self.config.table_name}'",
            level="Info"
        )

        try:
            self.client.connect()
            print(f"Connected to ZeroBus at {self.config.server_endpoint}")

            self.client.ingest_batch(records)
            print(f"Successfully ingested {len(records)} records to Databricks Delta Lake.")
            self.cli_logger.log_data_ingestion(
                message=f"Successfully ingested {len(records)} records to table '{self.config.table_name}'",
                level="Success"
            )
            return True
        except Exception as e:
            err = str(e)
            if "401" in err or "Unauthorized" in err:
                print(f"Error during ingestion: {e}")
                print("\n[AUTH FAILURE] 401 Unauthorized -- check your service principal permissions.")
                self.cli_logger.log_data_ingestion(message=f"Ingestion failed (401 Unauthorized) for '{self.config.table_name}'", level="Error")
            elif "4044" in err or "decoder" in err.lower() or "encoder" in err.lower():
                print(f"\n[SCHEMA MISMATCH ERROR] The server rejected the record format (Code 4044).")
                print(f"  Details: {err}")
                print(f"  Ensure your keys match the Databricks table schema exactly.")
                self.cli_logger.log_data_ingestion(message=f"Ingestion failed (Schema Mismatch) for '{self.config.table_name}': {err}", level="Error")
            else:
                print(f"Error during ingestion: {type(e).__name__}: {e}")
                traceback.print_exc()
                self.cli_logger.log_data_ingestion(message=f"Ingestion failed for '{self.config.table_name}': {err}", level="Error")
            return False
        finally:
            try:
                self.client.close()
            except Exception as close_err:
                # If ingestion failed, close() often fails too.
                # We log it but don't let it raise and hide the original error.
                print(f"[DEBUG] Could not cleanly close stream: {close_err}")


