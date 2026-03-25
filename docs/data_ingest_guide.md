# Data Ingestion User Guide

The Silicon Labs MLOps Data Ingestion library provides a high-performance, secure way to stream IoT sensor data from edge devices directly into Databricks Delta Tables (Bronze layer) using the **ZeroBus Ingest** connector.

The entire MLOps package (`data`, `model`, `logs`) uses a **single global configuration**, so you only call `data.config()` **once**, and all modules automatically authenticate and connect using the same credentials.

## Key Features
- **One-Time Global Configuration**: Configure your Databricks/ZeroBus credentials once — both data ingestion and model profiling reuse the configuration established by `data.config()`.
- **Zero-Configuration Ingestion**: Simple, programmatic API for sending single or batch records.
- **Automatic Logging**: Every ingestion attempt (start, success, or error) is automatically tracked in the central CLI logger.
- **Local Buffering**: Supports reading records from local JSON files (JSON Array or JSON Lines).
- **Secure Authentication**: Integrates with Databricks OAuth Service Principals.

---

# Quick Start

## 1. Configure Global Credentials
This initializes the global configuration shared across the entire library. Refer to the [Databricks Setup Guide](databricks_setup_guide.md) for obtaining your ZeroBus and Databricks credentials. You can initialize this configuration either by fetching your system's environment variables (using `os.getenv()`) inside `data.config()` or by providing the strings directly.

#### **Option 1: Using Environment Variables**
```python
import os
from sml.ops import data

data.config(
    server_endpoint=os.getenv("ZEROBUS_SERVER_ENDPOINT"),
    workspace_url=os.getenv("ZEROBUS_WORKSPACE_URL"),
    table_name=os.getenv("ZEROBUS_TABLE_NAME"),
    client_id=os.getenv("ZEROBUS_CLIENT_ID"),
    client_secret=os.getenv("ZEROBUS_CLIENT_SECRET")
)
```

#### **Option 2: Direct Configuration**
```python
from sml.ops import data

data.config(
    server_endpoint="your-zerobus-endpoint.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="catalog.schema.sensor_table",
    client_id="your-service-principal-id",
    client_secret="your-service-principal-secret"
)
```

### 2. Ingest Data Directly
You can send a list of dictionaries (records) directly to your Databricks table.

> [!IMPORTANT]
> **Schema Matching**: The keys in your Python dictionaries must match the column names and data types of your Databricks Delta table exactly. If there is a mismatch, the ingestion will fail with a **Schema Mismatch** error.
> 
> **Table Schema Example**:
> Before ingesting, ensure your table is created with matching column names in the databricks:
>
> ```sql
> CREATE TABLE IF NOT EXISTS catalog.schema.sensor_table (
>   device_id STRING,
>   temp DOUBLE,
>   unit STRING
> ) USING DELTA;
> ```
> 
> For more details on how to create a table, refer to the [Databricks Setup Guide](databricks_setup_guide.md).

You can use this script to send a list of dictionaries (records) directly to your Databricks table.

```python
from sml.ops import data

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
from sml.ops import data

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
The library can automatically read and upload data from local "buffer" files. This can be used when you want the locally stored sensor data to be sent and stored on databricks delta tables.

> [!NOTE]
> The schema of the records in your local JSON file must match the column names of your target Databricks Delta table exactly to avoid schema mismatch errors.


### Supported Formats
1. **JSON Array**: `[{"key": "val"}, ...]`
2. **JSON Lines**: `{"key": "val"}\n{"key2": "val2"}`

### Usage
To sync a local file to Databricks, use the `ingest_from_file` function. This is the most robust way to handle local buffers.

```python
from sml.ops import data

# Ingest from file (uses the same configuration from above)
success = data.ingest_from_file("path/to/sensor_data.json") # -> provide the path to your local buffer file 
if success:
    print("✓ File data sent to Databricks successfully!")
```

---

## Advanced: Programmatic Ingestor
For more control, you can instantiate the `DataIngestor` class directly.

```python
from sml.ops.data.ingest import DataIngestor, IngestConfig

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
sml ops logs --type "Data Ingestion"
sml ops logs sync
```

**Via Python Script:**
```python
from sml.ops.logs import Logger

logger = Logger()
# Filter only for ingestion events
logger.view(event_type="Data Ingestion")
```

---

## ⚠️ Troubleshooting
- **401 Unauthorized**: Check your system environment variables or `data.config()` credentials.
- **Schema Mismatch (4044)**: Ensure the keys in your Python dictionaries match the columns in your Databricks Delta table exactly.
- **Closed Stream**: If a network error occurs, the ingestor will safely attempt to close the connection and log the diagnostic error.
