# Data Ingestion User Guide

The Silicon Labs MLOps Data Ingestion library provides a high-performance, secure way to stream IoT sensor data from edge devices directly into Databricks Delta Tables (Bronze layer) using the **ZeroBus Ingest** connector.

## Key Features
- **Zero-Configuration Ingestion**: Simple, programmatic API for sending single or batch records.
- **Automatic Logging**: Every ingestion attempt (start, success, or error) is automatically tracked in the central CLI logger.
- **Local Buffering**: Supports reading records from local JSON files (JSON Array or JSON Lines).
- **Secure Authentication**: Integrates with Databricks OAuth Service Principals.

---

## Quick Start

### 1. Configure Credentials
Provide your ZeroBus and Databricks credentials once. These are typically saved in your `.env` file or passed through the `config` module.

```python
from silabs_mlops.data import config

config(
    server_endpoint="your-zerobus-endpoint.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="catalog.schema.sensor_table",
    client_id="your-service-principal-id",
    client_secret="your-service-principal-secret"
)
```

### 2. Ingest Data Directly
You can send a list of dictionaries (records) directly to your Databricks table.

```python
from silabs_mlops import data

records = [
    {"device_id": "sensor-01", "temp": 24.5, "unit": "C"},
    {"device_id": "sensor-02", "temp": 22.1, "unit": "C"}
]

# This automatically connects, ingests, and logs the results
data.ingest(records)
```

---

## Real IoT Workflow: Continuous Data Collection
In many IoT scenarios, you want to collect and send data continuously in a loop. You can achieve this by calling `data.ingest()` inside a standard Python loop.

```python
import time
from silabs_mlops import data

# Configure once at application startup
data.config(
    server_endpoint="your-workspace-id.zerobus.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="your_catalog.your_schema.iot_data",
    client_id="your-client-id",
    client_secret="your-client-secret"
)

def collect_sensor_readings():
    """Placeholder for your own sensor collection logic"""
    return [
        {"device_id": "temp-sensor-1", "temperature": 22.5, "timestamp": time.time()},
        {"device_id": "humidity-sensor-1", "humidity": 55, "timestamp": time.time()}
    ]

# Continuous collection loop
while True:
    print("\n--- Collecting New Readings ---")
    
    # 1. Collect data from sensors
    readings = collect_sensor_readings()
    
    # 2. Send to Databricks (Connects, Sends, and Disconnects automatically)
    success = data.ingest(readings)
    
    if success:
        print("✓ Batch sent to Databricks!")
    else:
        print("✗ Batch failed")
    
    # 3. Wait before the next collection interval
    time.sleep(2) 
```

---

## Ingesting from Local Files
The library can automatically read and upload data from local "buffer" files.

### Supported Formats
1. **JSON Array**: `[{"key": "val"}, ...]`
2. **JSON Lines**: `{"key": "val"}\n{"key2": "val2"}`

### Usage
```python
from silabs_mlops import data

# Reads from the path defined in your config or a specific file
data.ingest(buffer_path="data/sensor_readings.json")
```

---

## Advanced: Programmatic Ingestor
For more control, you can instantiate the `DataIngestor` class directly.

```python
from silabs_mlops.data.ingest import DataIngestor, IngestConfig

config = IngestConfig(
    server_endpoint="...",
    workspace_url="...",
    table_name="...",
    client_id="...",
    client_secret="..."
)

ingestor = DataIngestor(config)

# Perform ingestion
if ingestor.ingest(records):
    print("Ingestion successful!")
```

---

## Monitoring & Logging
Every ingestion session is automatically logged. You can view the history of your ingestions using the CLI or the `Logger` class.

**Via CLI:**
```bash
silabs-mlops logs --type "Data Ingestion"
```

**Via Python Script:**
```python
from silabs_mlops.logs import Logger

logger = Logger()
# Filter only for ingestion events
logger.view(event_type="Data Ingestion")
```

---

## ⚠️ Troubleshooting
- **401 Unauthorized**: Check your Service Principal credentials in `.env`.
- **Schema Mismatch (4044)**: Ensure the keys in your Python dictionaries match the columns in your Databricks Delta table exactly.
- **Closed Stream**: If a network error occurs, the ingestor will safely attempt to close the connection and log the diagnostic error.
