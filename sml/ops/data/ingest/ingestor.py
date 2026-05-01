# SPDX-License-Identifier: LicenseRef-MSLA
# @file ingestor.py
# @brief Data ingestion orchestrator for ZeroBus.
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
Data ingestion orchestrator for ZeroBus.
"""
import json
import logging
import traceback
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import IngestConfig
from .zerobus_client import ZerobusIngestClient
from sml.ops.logs import Logger   
# Suppress verbose INFO logs from ZeroBus SDK
logging.getLogger("databricks_zerobus_ingest_sdk").setLevel(logging.WARNING)


class DataIngestor:
    """Orchestrates data ingestion from local buffer/direct data to Databricks via ZeroBus."""

    def __init__(self, config: IngestConfig):
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
        """Read buffered JSON records from local storage (array or JSON-lines)."""
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

            # Try JSON array
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return [parsed]
            except json.JSONDecodeError:
                pass

            # Try JSON lines
            for line in content.split("\n"):
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"Warning: Could not parse line: {line[:50]}...")

        return records

    def ingest(self, data: Optional[List[Dict[str, Any]]] = None, buffer_path: Optional[str] = None) -> bool:
        """Main ingestion workflow."""
        records = data if data is not None else self._read_buffered_records(buffer_path)

        if not records:
            print("No records to ingest.")
            return False

        print(f"Preparing to ingest {len(records)} records to {self.config.table_name}...")
        self.cli_logger.log_data_ingestion(
            message=f"Starting batch ingestion of {len(records)} records to table '{self.config.table_name}'",
            level="Info",
        )

        try:
            self.client.connect()
            print(f"Connected to ZeroBus at {self.config.server_endpoint}")

            self.client.ingest_batch(records)
            print(f"Successfully ingested {len(records)} records to Databricks Delta Lake.")
            self.cli_logger.log_data_ingestion(
                message=f"Successfully ingested {len(records)} records to table '{self.config.table_name}'",
                level="Success",
            )
            return True

        except Exception as e:
            err = str(e)

            if "401" in err or "Unauthorized" in err:
                print(f"Error during ingestion: {e}")
                print("\n[AUTH FAILURE] 401 Unauthorized -- check your service principal permissions.")
                self.cli_logger.log_data_ingestion(
                    message=f"Ingestion failed (401 Unauthorized) for '{self.config.table_name}'",
                    level="Error",
                )

            elif "4044" in err or "decoder" in err.lower() or "encoder" in err.lower():
                print("\n[SCHEMA MISMATCH ERROR] The server rejected the record format (Code 4044).")
                print(f"  Details: {err}")
                print("  Ensure your keys match the Databricks table schema exactly.")
                self.cli_logger.log_data_ingestion(
                    message=f"Ingestion failed (Schema Mismatch) for '{self.config.table_name}': {err}",
                    level="Error",
                )

            else:
                print(f"Error during ingestion: {type(e).__name__}: {e}")
                traceback.print_exc()
                self.cli_logger.log_data_ingestion(
                    message=f"Ingestion failed for '{self.config.table_name}': {err}",
                    level="Error",
                )
            return False

        finally:
            try:
                self.client.close()
            except Exception as close_err:
                print(f"[DEBUG] Could not cleanly close stream: {close_err}")


    def _get_oauth_token(self) -> Optional[str]:
        """Fetch Databricks OAuth token using client credentials."""
        if not (self.config.workspace_url and self.config.client_id and self.config.client_secret):
            print("Error: Incomplete credentials for OAuth token fetch.")
            return None

        token_url = f"{self.config.workspace_url.rstrip('/')}/oidc/v1/token"

        try:
            r = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": "all-apis",
                },
                timeout=10,
            )
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as e:
            print(f"Error: OAuth token fetch failed: {e}")
            return None

    def _upload_to_volume(self, token: str, file_bytes: bytes, volume_path: str) -> bool:
        """Upload a file to Databricks Unity Catalog volume."""
        p = str(volume_path).replace("\\", "/")

        if p.startswith("dbfs:/"):
            p = p.replace("dbfs:/", "/")

        parts = [seg for seg in p.split("/") if seg]
        p = "/" + "/".join(parts)

        if not p.startswith("/Volumes/"):
            p = f"/Volumes/{p.lstrip('/')}"

        url = f"{self.config.workspace_url.rstrip('/')}/api/2.0/fs/files{p}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
        }

        try:
            r = requests.put(
                url,
                headers=headers,
                data=file_bytes,
                params={"overwrite": "true"},
                timeout=30,
            )
            if r.status_code not in (200, 204):
                print(f"Error: Files API returned {r.status_code}: {r.text}")
                return False

            return True

        except Exception as e:
            print(f"Error: Volume upload failed: {e}")
            return False

    def file_ingest(self, file_path: str, volume_path: str, metadata: Dict[str, Any]) -> bool:
        """Upload a file to a UC volume and ingest metadata using ZeroBus."""
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            print(f"Error: Could not read file {file_path}: {e}")
            return False

        token = self._get_oauth_token()
        if not token:
            print("Error: Could not obtain OAuth token for volume upload.")
            return False

        print(f"Uploading {file_path} to {volume_path}...")
        if not self._upload_to_volume(token, file_bytes, volume_path):
            print(f"Error: Failed to upload {file_path} to Volume.")
            return False

        metadata["file_path"] = volume_path
        if "ingest_ts" not in metadata:
            metadata["ingest_ts"] = int(time.time() * 1_000_000)

        print(f"Ingesting metadata for {metadata.get('file_name', file_path)}...")
        return self.ingest(data=[metadata])