# ZeroBus Data Ingestion Library

Simple API for sending IoT data to Databricks via the ZeroBus Ingest connector.

## Installation

```bash
pip install silabs-mlops-cli
# or from source
pip install -e .
```

## Quick Start

**Two-step process: Configure once, ingest many times**

```python
from silabs_mlops import data

# Step 1: Configure your Databricks credentials (do once)
data.config(
    server_endpoint="1234567890123456.zerobus.us-west-2.cloud.databricks.com",
    workspace_url="https://dbc-a1b2c3d4-e5f6.cloud.databricks.com",
    table_name="main.default.sensor_data",
    client_id="your-client-id",
    client_secret="your-client-secret"
)

# Step 2: Ingest your sensor data (can do multiple times)
sensor_data = [
    {"device_id": "sensor-1", "temperature": 22.5, "humidity": 55},
    {"device_id": "sensor-2", "temperature": 23.1, "humidity": 60}
]

data.ingest(sensor_data)


### 3. Usage

#### Via CLI

```bash
# Ingest data from a JSON file
silabs-mlops ingest --file my_sensor_data.json
```

#### Programmatic API

```python
from silabs_mlops.data.ingest import IngestConfig, DataIngestor

# Configure ingestion
config = IngestConfig(
    server_endpoint="1234567890123456.zerobus.us-west-2.cloud.databricks.com",
    workspace_url="https://dbc-a1b2c3d4-e5f6.cloud.databricks.com",
    table_name="main.default.sensor_data",
    client_id="your-client-id",
    client_secret="your-client-secret"
)

# Option 1: Ingest from a file
ingestor = DataIngestor(config)
ingestor.ingest(buffer_path="sensor_data.json")

# Option 2: Ingest data directly
data = [
    {"device_id": "sensor-1", "temperature": 22.5, "humidity": 55},
    {"device_id": "sensor-2", "temperature": 23.1, "humidity": 60}
]
ingestor.ingest(data=data)
```

## Data Format

The library accepts JSON data in two formats:

**JSON Array:**
```json
[
  {"device_id": "sensor-1", "temperature": 22.5},
  {"device_id": "sensor-2", "temperature": 23.1}
]
```

**JSON Lines (newline-delimited):**
```
{"device_id": "sensor-1", "temperature": 22.5}
{"device_id": "sensor-2", "temperature": 23.1}
```

## Architecture

```
User Data → DataIngestor → ZeroBusClient → ZeroBus → Databricks Delta Lake (Bronze)
```

1. **User provides data** - You collect sensor data using your own methods
2. **DataIngestor** - Orchestrates the ingestion workflow
3. **ZeroBusClient** - Wraps the official Databricks ZeroBus SDK
4. **ZeroBus** - Databricks ingestion service
5. **Delta Lake** - Data lands in your specified table (Bronze layer)

## Configuration Reference

| Field | Description | Example |
|-------|-------------|---------|
| `server_endpoint` | ZeroBus server endpoint | `1234567890123456.zerobus.us-west-2.cloud.databricks.com` |
| `workspace_url` | Databricks workspace URL | `https://dbc-a1b2c3d4-e5f6.cloud.databricks.com` |
| `table_name` | Unity Catalog table | `main.default.sensor_data` |
| `client_id` | Service principal ID | UUID from Databricks |
| `client_secret` | Service principal secret | From Databricks |

See the [Databricks ZeroBus documentation](https://docs.databricks.com/aws/en/ingestion/zerobus-ingest) for setup instructions.
