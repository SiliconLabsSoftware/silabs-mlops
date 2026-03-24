"""
SiLabs MLOps - Universal Logger

Handles local history storage and direct HTTP REST API streaming
to Azure Databricks Delta Tables via OAuth.
"""
import os
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

class Logger:
    """A Common Logger to track and persist System Logs matching."""
    
    def __init__(self, 
                 databricks_host: Optional[str] = None, 
                 client_id: Optional[str] = None, 
                 client_secret: Optional[str] = None,
                 warehouse_name: Optional[str] = None,
                 warehouse_id: Optional[str] = None, 
                 table_name: Optional[str] = None):
        """
        Optional parameters to configure direct REST API logging to Databricks SQL using OAuth.
        Reads from environment variables (e.g., DATABRICKS_HOST) if not provided.
        """
        # Load user's saved CLI credentials from hidden env file if they exist
        env_file = Path.home() / ".silabs_mlops" / ".env"
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k, v.strip('"\''))

        # Fallback to importing Config if they set it there
        try:
            from silabs_mlops.config import Config  # pyre-ignore[21]
            conf_host = Config.ZEROBUS_WORKSPACE_URL or Config.ZEROBUS_SERVER_ENDPOINT
            conf_client = Config.ZEROBUS_CLIENT_ID
            conf_secret = Config.ZEROBUS_CLIENT_SECRET
        except Exception:
            conf_host = conf_client = conf_secret = None

        # Fetch from args, env file, os env, or Config
        host = databricks_host or os.environ.get("DATABRICKS_HOST") or conf_host or ""
        self.databricks_host = host.rstrip('/') if host else None
        
        self.client_id = client_id or os.environ.get("DATABRICKS_CLIENT_ID") or conf_client
        self.client_secret = client_secret or os.environ.get("DATABRICKS_CLIENT_SECRET") or conf_secret
        self.warehouse_name = warehouse_name or os.environ.get("DATABRICKS_WAREHOUSE_NAME") or "Serverless Starter Warehouse"
        self.warehouse_id = warehouse_id or os.environ.get("DATABRICKS_WAREHOUSE_ID")
        self.table_name = table_name or os.environ.get("DATABRICKS_TABLE_NAME")
        self._access_token = None

        # Setup Local Log Storage for Offline Development, Testing & History
        self.local_log_dir = Path.home() / ".silabs_mlops"
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
            r = requests.post(token_url, data=data)
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
        headers = {"Authorization": f"Bearer {token}"}
        try:
            r = requests.get(url, headers=headers)
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

    def log_event(self, type: str, level: str, message: str, source: str = "System"):
        """
        Args:
            type (str): 'Profiling', 'Data Ingestion', 'Deployment', 'System'
            level (str): 'Success', 'Info', 'Warning', 'Error'
            message (str): Human-readable event description 
            source (str): Optional. e.g., 'Deployment Service', 'Profiler', etc.
        """
        # Use exact timestamp formatting matching: YYYY-MM-DD HH:MM:SS
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": type,
            "level": level,
            "message": message,
            "source": source
        }
        
        # 1. ALWAYS store locally for Testing / History Tracking
        try:
            with open(self.local_log_file, "r") as f:
                logs: List[Dict[str, Any]] = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logs: List[Dict[str, Any]] = []
            
        logs.append(log_entry)
        
        with open(self.local_log_file, "w") as f:
            json.dump(logs, f, indent=2)

        # 2. Automatically stream this individual log DIRECTLY to Databricks (if configured)!
        token = self._get_token()
        wid = self._resolve_warehouse_id()
        
        if self.databricks_host and token and wid and self.table_name and source != "ZeroBus":
            try:
                url = f"{self.databricks_host}/api/2.0/sql/statements"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                statement = f"INSERT INTO {self.table_name} (`timestamp`, `type`, `level`, `message`, `source`) VALUES (?, ?, ?, ?, ?)"
                payload = {
                    "warehouse_id": wid,
                    "statement": statement,
                    "parameters": [
                        {"value": log_entry["timestamp"], "type": "STRING"},
                        {"value": log_entry["type"], "type": "STRING"},
                        {"value": log_entry["level"], "type": "STRING"},
                        {"value": log_entry["message"], "type": "STRING"},
                        {"name": "source", "value": log_entry["source"], "type": "STRING"}
                    ]
                }
                
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()
            except Exception as e:
                print(f"Warning: Failed to stream log to Databricks via REST API. Please check your configuration: {e}")
        
    def log_data_ingestion(self, message: str, level: str = "Info", source: str = "Data Ingestor"):
        """Helper to specifically track Data Ingestion events."""
        self.log_event(type="Data Ingestion", level=level, message=message, source=source)
        
    def log_model_profiling(self, message: str, level: str = "Info", source: str = "Profiler"):
        """Helper to specifically track Model Profiling events."""
        self.log_event(type="Profiling", level=level, message=message, source=source)

    def log_model_deployment(self, message: str, level: str = "Info", source: str = "Deployment Service"):
        """Helper to specifically track Model Deployment events."""
        self.log_event(type="Deployment", level=level, message=message, source=source)
        
    def view(self, event_type: Optional[str] = None):
        """
        View the log history locally. 
        Args:
            event_type (str): Optional. E.g., 'Profiling','Deployment'
        """
        try:
            with open(self.local_log_file, "r") as f:
                logs: List[Dict[str, Any]] = json.load(f)
                
            if event_type:
                logs = [log for log in logs if str(log.get("type", "")).lower() == event_type.lower()]
                
            if not logs:
                print(f"\nNo local logs found" + (f" for type '{event_type}'." if event_type else "."))
                return
                
            print(f"\n--- Local Log History" + (f" ({event_type})" if event_type else "") + " ---")
            print(f"{'TIMESTAMP':<20} | {'TYPE':<16} | {'LEVEL':<8} | {'SOURCE':<15} | MESSAGE")
            print("-" * 100)
            
            # Show up to 50 most recent
            for log in logs[-50:]: # pyre-ignore[16]
                ts = log.get("timestamp", "")
                t = log.get("type", "")
                lvl = log.get("level", "")
                src = log.get("source", "")
                msg = log.get("message", "")
                print(f"{ts[:19]:<20} | {t[:16]:<16} | {lvl[:8]:<8} | {src[:15]:<15} | {msg}")
                
            print("-" * 100)
            
        except (json.JSONDecodeError, FileNotFoundError):
            print("\nNo local history file found. Run log_event() to start tracking.")

    def sync_to_databricks(self):
        """
        Reads all historically recorded local events and bulk-uploads them 
        to the user's Databricks Delta Table.
        """
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
            print("✗ Error: Could not authenticate or resolve warehouse ID. Check your credentials.")
            return

        url = f"{self.databricks_host}/api/2.0/sql/statements"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        print(f"--- Found {len(logs)} local logs. Syncing to {self.table_name} ---")
        success_count = 0
        
        for i, log_entry in enumerate(logs):
            # Escaping keywords like timestamp, type, and source which are often reserved
            statement = f"INSERT INTO {self.table_name} (`timestamp`, `type`, `level`, `message`, `source`) VALUES (?, ?, ?, ?, ?)"
            payload = {
                "warehouse_id": wid,
                "statement": statement,
                "parameters": [
                    {"value": log_entry["timestamp"], "type": "STRING"},
                    {"value": log_entry["type"], "type": "STRING"},
                    {"value": log_entry["level"], "type": "STRING"},
                    {"value": log_entry["message"], "type": "STRING"},
                    {"value": log_entry.get("source", "System"), "type": "STRING"}
                ]
            }
            try:
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code not in (200, 202):
                    print(f"\n[ERROR] Failed to upload log {i+1}: {response.status_code} - {response.text}")
                    continue
                
                success_count += 1
                import sys
                sys.stdout.write(f"\rUploading... {i+1}/{len(logs)} completed.")
                sys.stdout.flush()
            except Exception as e:
                print(f"\n[ERROR] Exception uploading log {i+1}: {e}")
                
        print(f"\n✓ Successfully Bulk Synced {success_count} local logs into {self.table_name}!")
