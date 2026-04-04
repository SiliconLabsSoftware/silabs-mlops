# Data Ingestion User Guide

The Silicon Labs MLOps Data Ingestion library provides a high-performance, secure way to stream IoT sensor data from edge devices directly into Databricks Delta Tables (Bronze layer) using the **ZeroBus Ingest** connector.

The entire MLOps package (`data`, `model`, `logs`) uses a **single global configuration**, so you only call `data.config()` **once**, and all modules automatically authenticate and connect using the same credentials.

## Key Features
- **One-Time Global Configuration**: Configure your Databricks/ZeroBus credentials once — both data ingestion and model profiling reuse the configuration established by `data.config()`.
- **Zero-Configuration Ingestion**: Simple, programmatic API for sending single or batch records.
- **Automatic Logging**: Every ingestion attempt (start, success, or error) is automatically tracked in the central CLI logger.
- **Combined File & Metadata Ingestion**: Use `data.file_ingest()` to upload binary files (like audio/images) to Unity Catalog Volumes and their metadata to Delta Tables in a single call.
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

> [!TIP]
> **When to use `data.ingest()`**: Use this function when you only need to send text, sensor readings, or metadata from the edge side without uploading any physical files (like audio or images).

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

## Combined File & Metadata Ingestion
For use cases that involve uploading a physical file (like a `.wav` recording) and sending its associated metadata (like timestamp, device ID, and detected label) in a single operation, use `file_ingest()`.

### Usage
This function performs three tasks in order:
1. **Reads your local file** into memory.
2. **Uploads the file** to your Databricks Unity Catalog Volume (the location where all your audio files will be stored).
3. **Internally calls `data.ingest()`** to send the metadata to your Delta Table.

> [!IMPORTANT]
> **Mandatory Automatic Columns**: When you call `file_ingest()`, the SDK **automatically adds** the following fields to your metadata dictionary. You **must** include these exact column names in your Databricks table schema, and you do not need to provide them in your metadata dictionary:
> - **`file_path`**: The full destination path in your Databricks Volume where the audio files will be stored (STRING).
> - **`ingest_ts`**: The exact timestamp of when the ingestion occurred (TIMESTAMP).

```python
from sml.ops import data

# 1. Provide credentials
data.config(
    server_endpoint="your-zerobus-endpoint.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="catalog.schema.audio_events",
    client_id="your-service-principal-id",
    client_secret="your-service-principal-secret"
)

# 2. Prepare metadata
# Note: As the fields 'file_path' & 'ingest_ts' are automatically added to the metadata dictionary, 
# you must create the table with schema that includes these 2 fields also in Databricks.
metadata = {
    "device_id": "rpi-gateway-01",
    "timestamp": 1711567890.0,
    "label": "door_knock",
}

# 3. Perform combined ingestion
Combined ingestion allows you to upload a file to a Databricks Volume and send its metadata to a Delta Table in one step. 

success = data.file_ingest(
    file_path="local_sample.wav",                             # Add your local path where the files are stored
    volume_path="/Volumes/main/default/audio/sample_01.wav",  # provide the full volume path in Databricks where the audio file will be stored
    metadata=metadata                                          # Dictionary of metadata for the Delta Table
)

if success:
    print("✓ File uploaded and metadata ingested!")
```

> [!IMPORTANT]
> **Manual Table Creation Required**: Before using `file_ingest()` or `ingest()`, you **must** manually create your destination table in Databricks with a schema that matches your metadata keys. ZeroBus does not create the table for you.
>
> **Example SQL**:
```sql
CREATE TABLE main.default.iot_metadata (
  device_id STRING,
  timestamp DOUBLE,
  label STRING,
  -- These columns are automatically provided by the file_ingest() function 
  -- and must be added to your table schema:
  file_path STRING,    -- Stores the Volume path to the physical file
  ingest_ts TIMESTAMP  -- Stores the exact time of ingestion
) USING DELTA;
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
