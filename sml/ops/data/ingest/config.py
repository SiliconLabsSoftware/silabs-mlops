# SPDX-License-Identifier: LicenseRef-MSLA
# @file config.py
# @brief Configuration for ZeroBus ingestion.
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
Configuration for ZeroBus ingestion.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class IngestConfig:
    """
    Configuration for ingesting data to Databricks via ZeroBus.

    Attributes:
        server_endpoint: ZeroBus server endpoint (e.g., "1234567890123456.zerobus.us-west-2.cloud.databricks.com")
        workspace_url: Databricks workspace URL (e.g., "https://dbc-a1b2c3d4-e5f6.cloud.databricks.com")
        table_name: Unity Catalog table name (e.g., "main.default.sensor_data")
        client_id: Service principal application ID
        client_secret: Service principal secret
        buffer_path: Optional path to buffered data file (JSON lines format)
    """

    server_endpoint: str
    workspace_url: str
    table_name: str
    client_id: str
    client_secret: str
    buffer_path: Optional[str] = None

    def __post_init__(self):
        """Strip whitespace from all string fields to prevent silent auth failures
        caused by accidental spaces/newlines in .env values."""
        self.server_endpoint = (
            self.server_endpoint.strip()
            if self.server_endpoint
            else self.server_endpoint
        )
        self.workspace_url = (
            self.workspace_url.strip() if self.workspace_url else self.workspace_url
        )
        self.table_name = (
            self.table_name.strip() if self.table_name else self.table_name
        )
        self.client_id = self.client_id.strip() if self.client_id else self.client_id
        self.client_secret = (
            self.client_secret.strip() if self.client_secret else self.client_secret
        )
        # Also strip trailing slashes on workspace_url (common copy-paste issue)
        if self.workspace_url:
            self.workspace_url = self.workspace_url.rstrip("/")
