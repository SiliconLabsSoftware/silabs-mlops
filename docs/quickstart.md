# Quick start

This guide helps you get the Silicon Labs MLOps SDK running end-to-end with the minimum required steps, from Bluetooth-based data collection and high-throughput ingestion to edge model deployment via Raspberry Pi.

## Prerequisites
Before starting, ensure you have:

**Edge & Hardware**
- Silicon Labs device connected (e.g., EFR32, xG24) to a **Raspberry Pi** via USB
- Silicon Labs Simplicity Commander installed on the Raspberry Pi
- Python 3.9+ installed on your local workstation
- Passwordless SSH configured between your workstation and the Raspberry Pi (see [rpi_deployment_guide.md](rpi_deployment_guide.md))

**Cloud / Platform**
- Databricks workspace
- Access to Unity Catalog (Delta tables)
- Access to Databricks Volumes or MLflow Registry
- ZeroBus broker access for streaming ingestion

For a detailed walkthrough on setting up your Databricks workspace, catalogs, and service principals, see the [Databricks Setup Guide](databricks_setup_guide.md).

## Installation
You can install the Silicon Labs MLOps SDK via terminal or directly within a notebook.

### Option 1: Terminal
```bash
pip install silabs-mlops
```

### Option 2: Notebook (Databricks / Jupyter)
```python
%pip install silabs-mlops
```

**Verify the setup**:
```bash
silabs-mlops --help
```

### Configuration
There are two ways to provide credentials to the tool. Refer to the [Databricks Setup Guide](databricks_setup_guide.md) for instructions on how to obtain these credentials.

1.  **For the CLI**: Set **Environment Variables** on your machine. The CLI will automatically fetch these whenever you run CLI commands.
2.  **For Python Scripts**: Use the **`data.config()`** function. You can either pull from Environment Variables into it (using `os.getenv()`) or provide credentials directly.

### 1. Environment Variables Setup (For CLI Automatic Auth)

#### **Windows (PowerShell)**
```powershell
setx ZEROBUS_SERVER_ENDPOINT "your-endpoint"
setx ZEROBUS_WORKSPACE_URL "https://your-workspace"
setx ZEROBUS_TABLE_NAME "your.table"
setx ZEROBUS_CLIENT_ID "your-id"
setx ZEROBUS_CLIENT_SECRET "your-secret"
```

#### **Linux / macOS (Bash/Zsh)**
```bash
export ZEROBUS_SERVER_ENDPOINT="your-endpoint"
export ZEROBUS_WORKSPACE_URL="https://your-workspace"
export ZEROBUS_TABLE_NAME="your.table"
export ZEROBUS_CLIENT_ID="your-id"
export ZEROBUS_CLIENT_SECRET="your-secret"
```

### 2. Programmatic Configuration
If you are writing a Python script, you can provide credentials once at the start. You can either pull them from your system's Environment Variables using `os.getenv()` or provide them directly.

#### **Option 1: Using Environment Variables**
```python
import os
from silabs_mlops import data

data.config(
    server_endpoint=os.getenv("ZEROBUS_SERVER_ENDPOINT"),
    workspace_url=os.getenv("ZEROBUS_WORKSPACE_URL"),
    table_name=os.getenv("ZEROBUS_TABLE_NAME"),
    client_id=os.getenv("ZEROBUS_CLIENT_ID"),
    client_secret=os.getenv("ZEROBUS_CLIENT_SECRET")
)
```

#### **Option 2: Direct Hardcoding**
```python
from silabs_mlops import data

data.config(
    server_endpoint="your-zerobus-endpoint.databricks.com",
    workspace_url="https://your-workspace.databricks.com",
    table_name="catalog.schema.sensor_table",
    client_id="your-id",
    client_secret="your-secret"
)
```

Define model artifacts in `artifacts.yaml` to avoid typing full URLs:
```yaml
artifacts:
  iot_model:
    path: "/Volumes/mlops_dev/default/model_d/iot_model.tflite"
    type: "ml-model"
```

---

## Bluetooth Connectivity (ble)
The `silabs_mlops.ble` module allows you to discover and connect to your Silicon Labs hardware via Bluetooth to collect real-time sensor and audio data.

```python
from silabs_mlops import ble

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

## Step 1: Ingest data to Databricks

Stream IoT sensor data from edge devices directly into Databricks Delta Tables (Bronze layer) and send buffered sensor data to Databricks via ZeroBus. For detailed information, see the [data_ingest_guide.md](data_ingest_guide.md).

### Configure the Credentials

Configure your Databricks credentials (once at startup either by fetching your system's environment variables (using `os.getenv()`) inside `data.config()` or by providing the strings directly)

```python
from silabs_mlops import data
# Provided credentials directly 
data.config(
    server_endpoint="your-zerobus-endpoint.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="catalog.schema.sensor_table",
    client_id="your-service-principal-id",
    client_secret="your-service-principal-secret"
)
```

### Ingest Data Directly
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
### Real IoT Workflow: Continuous Data Collection
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

**What happens:**
- Reads local JSON sensor buffers
- Connects to ZeroBus
    - Data lands securely in Databricks Bronze Delta tables

### Ingesting Files (Audio, Images, etc.)
To ingest files like audio or binary files via BLE, images, and other binary data into Databricks Unity Catalog Volumes along with their metadata, use the `file_ingest()` function. This combines both the file upload and the metadata record ingestion into a single, reliable command.

```python
from silabs_mlops import data

# 1. Configure credentials
data.config(
    server_endpoint="your-zerobus-endpoint.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="catalog.schema.audio_events",
    client_id="your-service-principal-id",
    client_secret="your-service-principal-secret"
)

# 2. Provide metadata for the file
metadata = {
    "device_id":   "silabs-xg24-01",
    "class_label": "keyword_detected",
    "sample_rate": 16000
}

# 2. Upload file + ingest metadata
# Note: file_path and ingest_ts are added automatically by the SDK to the metadata dictionary, so you must create the table with schema that includes these 2 fields also in Databricks.
success = data.file_ingest(
    file_path="local_sample.wav",                             # Path to your local file
    volume_path="/Volumes/main/default/audio/sample_01.wav",  # Provide the full path in Databricks Volume to store the file
    metadata=metadata                                          # Dictionary of attributes
)

if success:
    print("✓ Audio file and metadata ingested successfully!")
```
For more details on ingestion, see the [data_ingest_guide.md](data_ingest_guide.md).

## Step 2: Profile the model 

Analyze your model's performance on the NPU before deployment. For detailed information, see the [profiling_guide.md](profiling_guide.md).

**Note**: Before starting, ensure you have installed the **NPU Toolkit model profiler (mvp_profiler)** and added it to your system's PATH. For detailed setup steps, see the [profiler_guide.md](profiling_guide.md).

### Local Simulation with Databricks Volume Upload
You can automatically upload all profiling results to a Databricks Volume by providing a `volume_path`.

```python
from silabs_mlops import model

result = model.profile(
    model_path="models/my_model.tflite", #-> add your model path here
    volume_path="/Volumes/main/default/profiling_results", #-> add your volume path here
    use_simulator=True
)
# result.output_dir is a dynamic path that always points to where your results are stored
# result.output_dir will now point to the remote Databricks URL path (e.g., /Volumes/main/default/...). 
print(f"Remote Results: {result.output_dir}")
```


## Step 3: Deploy to edge devices via Raspberry Pi

Upload the firmware/model to a remote Raspberry Pi and flash it to the physical device.

```python
from silabs_mlops.model.deployer import RPiDeployer

deployer = RPiDeployer(
    rpi_host="host_ip",
    rpi_user="user_name",
    local_file_path="./my_model.s37",
    commander_path="/home/aimlraspberry/Desktop/SimplicityCommander-Linux/commander-cli/commander-cli"#(example)
)

deployer.deploy()
```

**What happens:**
- Connects to the Raspberry Pi over SSH
- SCPs the local firmware file to the Pi's `/tmp` directory
- Remote invokes Simplicity Commander on the Pi
- Auto-detects the J-Link serial and target chip
- Flashes the payload directly to the device memory

## Step 4: Monitoring via Logs

The CLI keeps a local history of every operation. This is your first stop for troubleshooting.

### Viewing Logs in Python
The `Logger` class allows you to programmatically inspect the history:
```python
from silabs_mlops.logs import Logger

logger = Logger()
# Filter and view profiling events
logger.view(event_type="Profiling")
```

### Viewing Logs via CLI

```bash
# View recent activity
silabs-mlops logs

# Filter for specific operations
silabs-mlops logs --type Ingestion
silabs-mlops logs --type Profiling
```

For more details, see the [logs_guide.md](logs_guide.md).

---

## End-to-end (Single Command Flow via CLI)

The exact same workflow is available directly from the terminal without writing Python scripts:

```bash
# 1. Ingest edge data
silabs-mlops ingest --file sensor_data.json

# 2. Profile model performance (Optional)
silabs-mlops profile --model ./my_model.tflite --accelerator mvpv1

# 3. Deploy firmware to device via Raspberry Pi
silabs-mlops model deploy --uri ./my_model.s37 --rpi-host <RPI_IP_ADDRESS> --rpi-user <RPI_USERNAME>
```
