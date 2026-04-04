# User Guide: SiLabs MLOps Logging

The Silicon Labs MLOps SDK includes a universal logging system that tracks system events, profiling results, and data ingestion activities. These logs are stored locally for history tracking and can be automatically streamed or synced to a Databricks Delta Table.

## Features
- **Local History**: Logs are always saved locally to `~/.silabs_mlops/logs.json`.
- **Direct Streaming**: Automatically send custom event and user built-in helper logs to Databricks via REST API as they happen.
- **Bulk Sync**: Sync historical local logs to your cloud tables at any time.

## Databricks Table Schema Requirements

> [!IMPORTANT]
> If you choose to store logs in a Databricks table, you **must** use the following fixed schema. The CLI uses a specific `INSERT` statement that aligns with these exact metadata fields. Using a different schema will cause logging to fail.

### Required Column Structure
Your target table in Databricks must have the following columns:

| Column Name | Datatype | Description | Example Value |
|-------------|----------|-------------|---------------|
| `timestamp` | `TIMESTAMP` | Event time | `2024-03-14 15:30:00` |
| `type`      | `STRING` | Category of the event | `Profiling`, `Data Ingestion`, `Deployment` |
| `level`     | `STRING` | Severity level | `Success`, `Info`, `Warning`, `Error` |
| `message`   | `STRING` | Detailed description | `Started profiling model: custom_v1.tflite` |
| `source`    | `STRING` | The component that triggered the log | `Profiler`, `Data Ingestor`, `System` |

### SQL for Table Creation
You can run this SQL command in your Databricks Workspace to create a compatible table. For more details on setting up tables and catalogs, see the [Databricks Setup Guide](databricks_setup_guide.md).

```sql
-- "main.default.system_logs" In here main is catalog, default is schema, system_logs is table name replace them with your own
CREATE TABLE IF NOT EXISTS main.default.system_logs (
  timestamp TIMESTAMP,
  type STRING,
  level STRING,
  message STRING,
  source STRING
) USING DELTA;
```

## Authentication Logic

The `Logger` is designed to work seamlessly with your existing CLI configuration. It automatically pulls authentication details (`workspace_url`, `client_id`, and `client_secret`) from the **Global Configuration** set by `data.config()`. See the [Databricks Setup Guide](databricks_setup_guide.md) for how to retrieve these credentials.

**The user must specify:**
1. **`table_name`**: The specific Databricks table for log storage.
2. **`warehouse_name`**: The SQL Warehouse to execute the inserts (defaults to "Serverless Starter Warehouse").

## Usage Example

## Quick Start 

First, call the global config **once**. If you have already called it for data ingestion that's enough no need to call it again and initialize the logger with your specific table and warehouse name. If you don't have a table, you can create one using the SQL command above.

#### **Option 1: Using Environment Variables**
```python 
import os
from sml.ops import data
# Call this ONLY if you haven't configured the global credentials before.
# If you already called data.config() earlier (e.g., during data ingestion), you DO NOT need to call it again before logging.

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
    table_name="catalog.schema.some_temp_table",   # Required globally (ignored by Logger class)
    client_id="your-service-principal-id",
    client_secret="your-service-principal-secret"
)
```
### 1. Initialization
Use this if you want to store all your logs of CLI events in databricks delta table.
The Logger automatically pulls the Workspace URL, Client ID, and Secret directly from your CLI configuration (global configuration set by data.config()). You only need to optionally provide the destination Delta table and sync to store all logs of the CLI events performed.

```python
from sml.ops.logs import Logger

# Initialize Logger with your specific table and warehouse
logger = Logger(
    table_name="main.default.system_logs",
    warehouse_name="Serverless Starter Warehouse"
)

logger.sync_to_databricks()
```
### 2. Viewing Local Logs History

```python
# View all local actions on your PC
from sml.ops.logs import Logger
logger = Logger()
logger.view()

# View specific event types only
# Valid types: "Profiling", "Data Ingestion", "Deployment"
logger.view(event_type="Profiling")
```

### 3. Logging Custom Events

You can record custom events from your own automated scripts. If `table_name` is set, this immediately streams to your Databricks Delta Table no need to sync. Otherwise they will be stored locally and can be synced later using logger.sync_to_databricks().

```python
# Initialize Logger with your specific table and warehouse
logger = Logger(
    table_name="main.default.system_logs",
    warehouse_name="Serverless Starter Warehouse"
)

# Log a generic system event
logger.log_event(
    type="Calibration",
    level="Info",
    message="System calibration sequence started",
    source="Setup Script"
)
```

### 4. Using Built-in Helpers

If you are writing a script that wraps core CLI functionality, you can use the built-in MLOps categories to keep your logs standardized. If `table_name` is set, this immediately streams to your Databricks Delta Table no need to sync.

```python

from sml.ops.logs import Logger
logger = Logger(
    table_name="main.default.system_logs",
    warehouse_name="Serverless Starter Warehouse"
)
# Use component-specific helpers
logger.log_model_profiling("Completed local simulation for model_v2.tflite")
logger.log_data_ingestion("Successfully sent batch to Delta Lake")

```

### 5. Syncing Logs (Offline Support)

If you were working offline on an airplane or without Wi-Fi, the logger safely stored all your actions in `~/.silabs_mlops/logs.json`. You can run `sync_to_databricks` to bulk upload them all at once!. Note: Make sure you have the table_name and warehouse_name set if you want to sync the logs to Databricks. 

```python
# Bulk sync any local logs that were recorded offline
logger.sync_to_databricks()

```

## Local Log Storage
Logs are persisted on your machine at:
- **Windows**: `C:\Users\<User>\.silabs_mlops\logs.json`
- **Linux/Mac**: `~/.silabs_mlops/logs.json`

> [!CAUTION]
> On Databricks clusters, the local filesystem is ephemeral. Always sync your logs to a Delta Table or Volume if you want to keep them long-term.
