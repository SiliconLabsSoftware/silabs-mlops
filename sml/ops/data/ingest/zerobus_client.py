# SPDX-License-Identifier: LicenseRef-MSLA
# @file zerobus_client.py
# @brief ZeroBus client wrapper for Databricks ingestion.
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
ZeroBus client wrapper for Databricks ingestion.
"""

from typing import Dict, Any, List, Optional, Callable

try:
    from zerobus.sdk.sync import ZerobusSdk
    from zerobus.sdk.shared import (
        RecordType,
        StreamConfigurationOptions,
        TableProperties,
    )

    ZEROBUS_AVAILABLE = True
except ImportError:
    ZEROBUS_AVAILABLE = False

from sml.ops.logs import Logger


class ZerobusIngestClient:
    """Wrapper around the Databricks ZeroBus SDK for ingesting data to Delta tables."""

    def __init__(
        self,
        server_endpoint: str,
        workspace_url: str,
        table_name: str,
        client_id: str,
        client_secret: str,
        ack_callback: Optional[Callable[[Any], None]] = None,
    ):
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
        self.logger = Logger()

    def connect(self) -> None:
        """Initialize ZeroBus stream connection."""
        self._sdk = ZerobusSdk(self.server_endpoint, self.workspace_url)

        table_properties = TableProperties(self.table_name)
        options = StreamConfigurationOptions(
            record_type=RecordType.JSON,
            ack_callback=self.ack_callback if self.ack_callback else None,
        )

        try:
            self._stream = self._sdk.create_stream(
                self.client_id,
                self.client_secret,
                table_properties,
                options,
            )
            self.logger.log_data_ingestion(
                f"Successfully connected to ZeroBus stream for table: {self.table_name}",
                level="Success",
            )
        except Exception as e:
            self.logger.log_data_ingestion(
                f"Failed to connect to ZeroBus stream for table {self.table_name}. Error: {e}",
                level="Error",
            )
            raise e

    def ingest_record(self, record: Dict[str, Any], wait_for_ack: bool = True) -> None:
        """Ingest a single JSON record into ZeroBus."""
        if not self._stream:
            raise RuntimeError("ZeroBus stream not initialized. Call connect() first.")

        ack = self._stream.ingest_record(record)
        if wait_for_ack:
            ack.wait_for_ack()

    def ingest_batch(
        self, records: List[Dict[str, Any]], wait_for_ack: bool = True
    ) -> None:
        """Ingest multiple records sequentially."""
        for record in records:
            self.ingest_record(record, wait_for_ack=wait_for_ack)

    def close(self) -> None:
        """Close ZeroBus stream safely."""
        if self._stream:
            try:
                self._stream.close()
                self.logger.log_data_ingestion(
                    f"Closed ZeroBus stream for table: {self.table_name}", level="Info"
                )
            except Exception as e:
                self.logger.log_data_ingestion(
                    f"Error closing ZeroBus stream for table {self.table_name}: {e}",
                    level="Warning",
                )
            finally:
                self._stream = None
