"""
SiLabs MLOps - Universal Logger

This module provides a centralized Logger class that records system events 
(Data Ingestion, Model Profiling, Deployment) and automatically streams the 
results directly to a Databricks SQL Warehouse using the Databricks REST API.
"""
import json
import requests  # pyre-ignore[21]
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

class Logger:
    """A Common Logger to track and persist System Logs matching."""
    
    def __init__(self, databricks_host: Optional[str] = None, databricks_token: Optional[str] = None, warehouse_id: Optional[str] = None, table_name: Optional[str] = None):
        """
        Optional parameters to configure direct REST API logging to Databricks SQL.
        """
        self.databricks_host = databricks_host
        self.databricks_token = databricks_token
        self.warehouse_id = warehouse_id
        self.table_name = table_name


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
        


        # Automatically stream this individual log DIRECTLY to Databricks!
        if self.databricks_host and self.databricks_token and self.warehouse_id and self.table_name and source != "ZeroBus":
            try:
                url = f"https://{self.databricks_host}/api/2.0/sql/statements"
                headers = {
                    "Authorization": f"Bearer {self.databricks_token}",
                    "Content-Type": "application/json"
                }
                
                statement = f"INSERT INTO {self.table_name} (timestamp, type, level, message, source) VALUES (?, ?, ?, ?, ?)"
                payload = {
                    "warehouse_id": self.warehouse_id,
                    "statement": statement,
                    "parameters": [
                        {"name": "timestamp", "value": log_entry["timestamp"], "type": "STRING"},
                        {"name": "type", "value": log_entry["type"], "type": "STRING"},
                        {"name": "level", "value": log_entry["level"], "type": "STRING"},
                        {"name": "message", "value": log_entry["message"], "type": "STRING"},
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


