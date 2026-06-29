# SPDX-License-Identifier: LicenseRef-MSLA
# @file logs.py
# @brief Silicon Labs MLOps SDK - Universal Logger
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
Silicon Labs MLOps SDK - Universal Logger

Handles local history storage and direct HTTP REST API streaming
to Azure Databricks Delta Tables via OAuth.
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from sml.ops.config import USER_AGENT


class Logger:
    """A Common Logger to track and persist System Logs matching."""

    def __init__(
        self,
        databricks_host: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        warehouse_name: Optional[str] = None,
        warehouse_id: Optional[str] = None,
        table_name: Optional[str] = None,
    ):
        # Load user's saved CLI credentials from hidden env file if they exist
        env_file = Path.home() / ".sml" / "ops" / ".env"
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k, v.strip("\"'"))

        # Fallback to importing Config if they set it there
        try:
            from sml.ops.config import Config  # pyre-ignore[21]

            conf_host = Config.ZEROBUS_WORKSPACE_URL or Config.ZEROBUS_SERVER_ENDPOINT
            conf_client = Config.ZEROBUS_CLIENT_ID
            conf_secret = Config.ZEROBUS_CLIENT_SECRET
        except Exception:
            conf_host = conf_client = conf_secret = None

        # Fetch from args, env file, os env, or Config
        host = databricks_host or os.environ.get("DATABRICKS_HOST") or conf_host or ""
        self.databricks_host = host.rstrip("/") if host else None

        self.client_id = (
            client_id or os.environ.get("DATABRICKS_CLIENT_ID") or conf_client
        )
        self.client_secret = (
            client_secret or os.environ.get("DATABRICKS_CLIENT_SECRET") or conf_secret
        )
        self.warehouse_name = (
            warehouse_name
            or os.environ.get("DATABRICKS_WAREHOUSE_NAME")
            or "Serverless Starter Warehouse"
        )
        self.warehouse_id = warehouse_id or os.environ.get("DATABRICKS_WAREHOUSE_ID")
        self.table_name = table_name or os.environ.get("DATABRICKS_TABLE_NAME")
        self._access_token = None

        # Setup Local Log Storage for Offline Development, Testing & History
        self.local_log_dir = Path.home() / ".sml" / "ops"
        self.local_log_file = self.local_log_dir / "logs.json"

        self.local_log_dir.mkdir(parents=True, exist_ok=True)
        if not self.local_log_file.exists():
            with open(self.local_log_file, "w") as f:
                json.dump([], f)

    def _get_token(self) -> Optional[str]:
        if self._access_token:
            return self._access_token
        if not (self.databricks_host and self.client_id and self.client_secret):
            return None

        token_url = f"{self.databricks_host}/oidc/v1/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "all-apis",
        }
        try:
            r = requests.post(
                token_url, data=data, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            r.raise_for_status()
            self._access_token = r.json().get("access_token")
            return self._access_token
        except Exception as e:
            print(f"Warning: Failed to fetch Databricks OAuth token: {e}")
            return None

    def _resolve_warehouse_id(self) -> Optional[str]:
        if self.warehouse_id:
            return self.warehouse_id

        token = self._get_token()
        if not token or not self.databricks_host or not self.warehouse_name:
            return None

        url = f"{self.databricks_host}/api/2.0/sql/warehouses"
        headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            warehouses = r.json().get("warehouses", [])
            for w in warehouses:
                if w.get("name") == self.warehouse_name:
                    self.warehouse_id = w.get("id")
                    return self.warehouse_id
            print(f"Warning: Could not find warehouse named '{self.warehouse_name}'")
            return None
        except Exception as e:
            print(f"Warning: Failed to resolve warehouse ID: {e}")
            return None

    def _build_named_insert(self, table_name: str, log_entry: dict):
        statement = (
            f"INSERT INTO {table_name} "
            f"(`timestamp`, `type`, `level`, `message`, `source`) "
            f"VALUES (:ts, :type, :level, :message, :source)"
        )
        params = [
            {"name": "ts", "value": log_entry["timestamp"], "type": "TIMESTAMP"},
            {"name": "type", "value": log_entry["type"], "type": "STRING"},
            {"name": "level", "value": log_entry["level"], "type": "STRING"},
            {"name": "message", "value": log_entry["message"], "type": "STRING"},
            {
                "name": "source",
                "value": log_entry.get("source", "System"),
                "type": "STRING",
            },
        ]
        return statement, params

    def _build_positional_insert(self, table_name: str, log_entry: dict):
        statement = (
            f"INSERT INTO {table_name} "
            f"(`timestamp`, `type`, `level`, `message`, `source`) "
            f"VALUES (?, ?, ?, ?, ?)"
        )
        params = [
            {"value": log_entry["timestamp"], "type": "TIMESTAMP"},
            {"value": log_entry["type"], "type": "STRING"},
            {"value": log_entry["level"], "type": "STRING"},
            {"value": log_entry["message"], "type": "STRING"},
            {"value": log_entry.get("source", "System"), "type": "STRING"},
        ]
        return statement, params

    def _post_with_fallback(
        self, url: str, headers: dict, table_name: str, log_entry: dict
    ):
        # Try named first
        statement, parameters = self._build_named_insert(table_name, log_entry)
        payload = {
            "warehouse_id": self.warehouse_id,
            "statement": statement,
            "parameters": parameters,
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code in (200, 202):
                res_data = response.json()
                state = res_data.get("status", {}).get("state")
                if state == "FAILED":
                    msg = res_data.get("status", {}).get("error", {}).get("message", "")
                    if "INVALID_PARAMETER_MARKER_VALUE" in msg or "MISSING_NAME" in msg:
                        raise ValueError(msg)
                    return False, msg or "Statement failed"
                return True, None
            text = response.text or ""
            if "INVALID_PARAMETER_MARKER_VALUE" in text or "MISSING_NAME" in text:
                raise ValueError(text)
            return False, f"HTTP {response.status_code} - {text}"
        except Exception as e:
            emsg = str(e)
            if "INVALID_PARAMETER_MARKER_VALUE" in emsg or "MISSING_NAME" in emsg:
                stmt2, params2 = self._build_positional_insert(table_name, log_entry)
                payload2 = {
                    "warehouse_id": self.warehouse_id,
                    "statement": stmt2,
                    "parameters": params2,
                }
                try:
                    r2 = requests.post(url, headers=headers, json=payload2, timeout=30)
                    if r2.status_code in (200, 202):
                        rj = r2.json()
                        state2 = rj.get("status", {}).get("state")
                        if state2 == "FAILED":
                            msg2 = (
                                rj.get("status", {})
                                .get("error", {})
                                .get("message", "Unknown error")
                            )
                            return False, msg2
                        return True, None
                    return False, f"HTTP {r2.status_code} - {r2.text}"
                except Exception as e2:
                    return False, str(e2)
            return False, emsg

    def log_event(self, type: str, level: str, message: str, source: str = "System"):
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": type,
            "level": level,
            "message": message,
            "source": source,
        }

        try:
            with open(self.local_log_file, "r") as f:
                logs: List[Dict[str, Any]] = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logs = []
        logs.append(log_entry)
        with open(self.local_log_file, "w") as f:
            json.dump(logs, f, indent=2)

        token = self._get_token()
        wid = self._resolve_warehouse_id()

        if (
            self.databricks_host
            and token
            and wid
            and self.table_name
            and source != "ZeroBus"
        ):
            try:
                url = f"{self.databricks_host}/api/2.0/sql/statements"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": USER_AGENT,
                }
                ok, err = self._post_with_fallback(
                    url, headers, self.table_name, log_entry
                )
                if not ok and err:
                    print(f"Warning: Failed to stream log to Databricks: {err}")
            except Exception as e:
                print(f"Warning: Failed to stream log to Databricks via REST API: {e}")

    def log_data_ingestion(
        self, message: str, level: str = "Info", source: str = "Data Ingestor"
    ):
        self.log_event(
            type="Data Ingestion", level=level, message=message, source=source
        )

    def log_model_profiling(
        self, message: str, level: str = "Info", source: str = "Profiler"
    ):
        self.log_event(type="Profiling", level=level, message=message, source=source)

    def log_model_deployment(
        self, message: str, level: str = "Info", source: str = "Deployment Service"
    ):
        self.log_event(type="Deployment", level=level, message=message, source=source)

    def view(self, event_type: Optional[str] = None):
        try:
            with open(self.local_log_file, "r") as f:
                logs: List[Dict[str, Any]] = json.load(f)

            if event_type:
                logs = [
                    log
                    for log in logs
                    if str(log.get("type", "")).lower() == event_type.lower()
                ]

            if not logs:
                print(
                    f"\nNo local logs found"
                    + (f" for type '{event_type}'." if event_type else ".")
                )
                return

            print(
                f"\n--- Local Log History"
                + (f" ({event_type})" if event_type else "")
                + " ---"
            )
            print(
                f"{'TIMESTAMP':<20} | {'TYPE':<16} | {'LEVEL':<8} | {'SOURCE':<15} | MESSAGE"
            )
            print("-" * 100)

            for log in logs[-50:]:
                ts = log.get("timestamp", "")
                t = log.get("type", "")
                lvl = log.get("level", "")
                src = log.get("source", "")
                msg = log.get("message", "")
                print(
                    f"{ts[:19]:<20} | {t[:16]:<16} | {lvl[:8]:<8} | {src[:15]:<15} | {msg}"
                )

            print("-" * 100)

        except (json.JSONDecodeError, FileNotFoundError):
            print("\nNo local history file found. Run log_event() to start tracking.")

    def sync_to_databricks(self):
        if not self.table_name:
            print("Error: No table name provided for syncing!")
            return

        try:
            with open(self.local_log_file, "r") as f:
                logs: List[Dict[str, Any]] = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print("No local logs found to sync.")
            return

        if not logs:
            print("Local log file is empty. Nothing to sync!")
            return

        token = self._get_token()
        wid = self._resolve_warehouse_id()
        if not token or not wid:
            print(
                "✗ Error: Could not authenticate or resolve warehouse ID. Check your credentials."
            )
            return

        url = f"{self.databricks_host}/api/2.0/sql/statements"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        print(f"--- Found {len(logs)} local logs. Syncing to {self.table_name} ---")
        success_count = 0
        last_error = None

        for i, log_entry in enumerate(logs):
            try:
                ok, err = self._post_with_fallback(
                    url, headers, self.table_name, log_entry
                )
                if not ok and err:
                    if err != last_error:
                        print(f"\n[ERROR] Failed to upload logs: {err}")
                        last_error = err
                    continue

                success_count += 1
                import sys

                sys.stdout.write(f"\rUploading... {i + 1}/{len(logs)} completed.")
                sys.stdout.flush()
            except Exception as e:
                err = str(e)
                if err != last_error:
                    print(f"\n[ERROR] Exception uploading logs: {err}")
                    last_error = err

        print(
            f"\n✓ Successfully Bulk Synced {success_count} local logs into {self.table_name}!"
        )
