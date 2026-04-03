# Silicon Labs MLOps SDK User Guide

This guide explains how to install, configure, and use the Silicon Labs MLOps SDK to manage Bluetooth connectivity, data ingestion, model profiling, and remote hardware deployment via Raspberry Pi.

---

## Installation
To use the Silicon Labs MLOps SDK and Python libraries, you must first install the package.

### Option 1: Direct Installation (CLI / Terminal)
```bash
pip install silabs-mlops
```

### Option 2: Notebook Installation (Databricks / Jupyter)
If you are working in a Databricks Notebook or Jupyter, use the magic command:
```python
%pip install silabs-mlops
```

### Verify Installation
After installation, you can verify it by running:
```bash
silabs-mlops --help
```

---

## Setup and Authentication

The tool requires credentials for Databricks and ZeroBus. There are two ways to provide these:

1.  **For the CLI**: Set **Environment Variables** on your system. The CLI will automatically fetch these whenever you run CLI commands like `silabs-mlops ingest`. 
2.  **For Python Scripts**: Use the **`data.config()`** function. You can either fetch your Environment Variables into it using `os.getenv()` or provide credentials directly as strings.

Refer to the [Databricks Setup Guide](databricks_setup_guide.md) for instructions on where to find these credentials in your workspace.

### Environment Variables Setup

#### **Windows (PowerShell)**
Run these commands once to save credentials permanently to your user profile:
```powershell
setx ZEROBUS_SERVER_ENDPOINT "your-endpoint"
setx ZEROBUS_WORKSPACE_URL "https://your-workspace"
setx ZEROBUS_TABLE_NAME "your.table"
setx ZEROBUS_CLIENT_ID "your-id"
setx ZEROBUS_CLIENT_SECRET "your-secret"
```
*Note: Restart your terminal after running these.*

#### **Linux / macOS (Bash/Zsh)**
Add these lines to your `~/.bashrc` or `~/.zshrc`:
```bash
export ZEROBUS_SERVER_ENDPOINT="your-endpoint"
export ZEROBUS_WORKSPACE_URL="https://your-workspace"
export ZEROBUS_TABLE_NAME="your.table"
export ZEROBUS_CLIENT_ID="your-id"
export ZEROBUS_CLIENT_SECRET="your-secret"
```

### Programmatic Configuration
If you are writing a Python script, you can provide credentials once at the start. You can either hardcode them or pull them from your system's **Environment Variables** using `os.getenv()`.

#### **Option 1: Fetching from Environment Variables (Recommended)**
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
    server_endpoint="your-zerobus-endpoint.databricks.com",
    workspace_url="https://your-workspace.databricks.com",
    table_name="catalog.schema.sensor_table",
    client_id="your-id",
    client_secret="your-secret"
)
```

---

## Databricks & Unity Catalog Setup

### Prerequisites
Before using the ingestion or profiling features, your Databricks workspace and Service Principal (SP) must be correctly configured. For detailed steps, see the [Databricks Setup Guide](databricks_setup_guide.md).

- **ZeroBus Enablement**: The target workspace must be ZeroBus enabled.
- **Security Groups**: The user security group must have full privileges on the target Catalog.
- **Service Principal**: An M2M Service Principal must be created for authentication.

### Required Permissions (GRANTs)
To enable the SDK to interact with your data, provide the following explicit **GRANTs** on the target Catalog to your Service Principal:

#### Catalog & Schema Access
- `GRANT USE CATALOG ON CATALOG <catalog_name>`
- `GRANT USE SCHEMA, CREATE TABLE ON CATALOG <catalog_name>`
- `GRANT USE SCHEMA, SELECT, MODIFY ON SCHEMA <schema_name>`

#### Volume Access (For Profiling Results)
If you storage profiling results or logs in Databricks Volumes:
- `GRANT WRITE VOLUME, READ VOLUME ON VOLUME <volume_name>`

> [!IMPORTANT]
> **Workspace Consistency**: You must create your Volumes in the **same workspace** where you provide the workspace credentials via `data.config()` or Environment Variables. All metadata (URL, Client ID, Secret) used to store results and logs is automatically fetched from this configuration.


---

## Bluetooth Connectivity (ble module)

The `sml.ops.ble` module handles Bluetooth Low Energy (BLE) connections to Silicon Labs hardware for real-time sensor and audio data collection.

```python
from sml.ops import ble

# Configure the BLE connection with all your required parameters
ble.config(
    device_name="MySilabsBoard",
    device_address="AA:BB:CC:DD:EE:FF",
    voice_result_uuid="00002A37-0000-1000-8000-00805F9B34FB", # Example UUID
    audio_data_uuid="00002A38-0000-1000-8000-00805F9B34FB",  # Example UUID
    output_dir="./captured_audio",
    sample_rate=16000,
    channels=1,
    sample_width=2,
    labels=["on", "off", "unknown"],
    buffer_size=32000
)
```
For more information, refer to the [ble_module_guide.md](ble_module_guide.md).

---

## Data Ingestion

Stream IoT sensor data from edge devices directly into Databricks Delta Tables (Bronze layer) using the ZeroBus connector. You can also use the `data.file_ingest()` function to send audio files and other binary data to Databricks Unity Catalog Volumes via the Workspace API.
For detailed information, see the [data_ingest_guide.md](data_ingest_guide.md).

### Key Features
- **Zero-Configuration Ingestion**: Simple API for sending single or batch records.
- **Automatic Logging**: Every attempt is tracked in the central CLI logger.
- **Local Buffering**: Supports reading from local JSON files (Array or Lines).

### Quick Start (Python API)

```python
# 1. Configure once (either by fetching your system's environment variables (using `os.getenv()`) inside `data.config()` or by providing the strings directly.)
import os
from sml.ops import data
# Fetching system's environment variables (using `os.getenv()`) inside `data.config()`  
data.config(
    server_endpoint=os.getenv("ZEROBUS_SERVER_ENDPOINT"),
    workspace_url=os.getenv("ZEROBUS_WORKSPACE_URL"),
    table_name=os.getenv("ZEROBUS_TABLE_NAME"),
    client_id=os.getenv("ZEROBUS_CLIENT_ID"),
    client_secret=os.getenv("ZEROBUS_CLIENT_SECRET")
)

# 2. Ingest batch of records
records = [{"device_id": "sensor-01", "temp": 24.5}, {"device_id": "sensor-02", "temp": 22.1}]
data.ingest(records)
```

### Ingesting Files with Metadata (`file_ingest`)
Use `file_ingest()` to upload binary files (audio, images, etc.) to a Databricks Volume and record their metadata in a Delta Table simultaneously. Note: `file_path` and `ingest_ts` are added automatically by the SDK; no need to provide them in your Python metadata dictionary but you must create the table with schema that includes these 2 fields also in Databricks to avoid **Schema Mismatch** errors.

```python
from sml.ops import data

# Configure credentials
data.config(
    server_endpoint="your-zerobus-endpoint.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="catalog.schema.audio_events",
    client_id="your-service-principal-id",
    client_secret="your-service-principal-secret"
)

# Requires the full destination path in Databricks (including filename)
success = data.file_ingest(
    file_path="local_sample.wav",
    volume_path="/Volumes/main/default/audio/sample_01.wav",
    metadata={"device_id": "gateway-01", "class_label": "keyword"}
)
```

### Ingesting from Local Files
The library can automatically read and upload data from local "buffer" files.

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

## Model Profiling

The model profiling library provides a Python wrapper around the Silicon Labs NPU Toolkit (`mvp_profiler`) for analyzing models on hardware or in a simulator.

**Note**: Before profiling, you must install the **NPU Toolkit model profiler (mvp_profiler)** and add it to your system's PATH. For detailed instructions, see the [profiling_guide.md](profiling_guide.md).

### Key Features
- **Hardware & Simulation**: Profile on physical boards or via a local CPU simulator.
- **Result Collections**: Captures arena size, MACs, layer-by-layer metrics, and Perfetto traces.
- **Cloud Integration**: Automatically uploads artifacts to Databricks Unity Catalog Volumes.

### Quick Start
```python
from sml.ops import model

# Profile on discovered hardware
result = model.profile("my_model.tflite")

# Profile using local simulator (No hardware required)
result = model.profile("my_model.tflite", use_simulator=True)

print(f"Arena Size: {result.arena_size_kb} KB | Total MACs: {result.total_macs}")
```
### Local Simulation with Databricks Volume Upload
You can automatically upload all profiling results to a Databricks Volume by providing a `volume_path`.

```python
from sml.ops import model

result = model.profile(
    model_path="models/my_model.tflite", #-> add your model path here
    volume_path="/Volumes/main/default/profiling_results", #-> add your volume path here
    use_simulator=True
)
# result.output_dir is a dynamic path that always points to where your results are stored
# result.output_dir will now point to the remote Databricks URL path (e.g., /Volumes/main/default/...). 
print(f"Remote Results: {result.output_dir}")
```

### Output Artifacts
Every session generates a folder (local or cloud) with:
- `profiling_summary.txt`: Human-readable performance summary.
- `profiling_results.yaml`: Structured layer-by-layer metrics.

---

## Raspberry Pi Model Deployment

Deploy and flash firmware/models to Silicon Labs hardware connected to a remote Raspberry Pi via **SCP** and **SSH**.

### Deployment via CLI
```bash
silabs-mlops model deploy --uri ./my_model.s37 --rpi-host <RPI_IP> --rpi-user <USER_NAME>
```

### How it Works
1. **Transfer**: The tool SCPs the local firmware to the Pi's `/tmp` directory.
2. **Detection**: Remotely invokes Commander to find the J-Link serial and target chip.
3. **Flash**: Executes the final flash command and verifies the write.

For detailed SSH and udev setup, see the [rpi_deployment_guide.md](rpi_deployment_guide.md).

---

---

## Monitoring & Logging

Every activity—whether it's data ingestion, model profiling, or deployment—is automatically logged by the SDK. This is essential for debugging and verifying that your edge-to-cloud pipeline is working.

### Viewing Logs in Python
The `Logger` class allows you to programmatically inspect the history:
```python
from sml.ops.logs import Logger

logger = Logger()
# Filter and view profiling events
logger.view(event_type="Profiling")
```

### Viewing Logs via CLI
You can filter logs by type directly in the terminal:
```bash
# View all recent logs
silabs-mlops logs

# View only Ingestion logs
silabs-mlops logs --type Ingestion

# View only Profiling logs
silabs-mlops logs --type Profiling
```

For more advanced logging details and Databricks synchronization, see the [logs_guide.md](logs_guide.md).

---

## Troubleshooting

- **401/403 Error**: Check your environment variable credentials or databricks credentials provided through data.config() or Volume permissions in Databricks. 
- **Schema Mismatch**: Ensure dictionary keys match the Delta Table columns exactly.
- **SSH Timeout**: Verify the Raspberry Pi IP and check for network packet loss.
