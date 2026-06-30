# RPI to Cloud Data Ingestion– User Guide

This guide provides simple instructions for running the data ingestion system on the Raspberry Pi. We use a three-script architecture to automatically collect audio from the BLE board and upload it to your Databricks Delta Tables.

---

## 1. Prerequisites

### Dependencies to be Installed:

- **The Silicon Labs MLOps SDK**: `pip install silabs-mlops`
  - *Install this SDK to access the `silabs_mlops.ble` and `silabs_mlops.data` libraries used by the gateway scripts. It automatically installs all required dependencies including `bleak`, `numpy`, and `requests`.*
- **Commander-cli_linux_aarch64**:
  - *Install this commander-cli (Linux version-ARM64) from Silicon labs or [click here](https://www.silabs.com/software-and-tools/simplicity-studio/simplicity-commander?tab=getting-started) to download it and export the commander-cli path*  

Before running the system, ensure the following:

### Raspberry Pi Setup
- Your Raspberry Pi must be fully configured for BLE communication and file handling.
- The Edge device (Silicon Labs device) should be visible to raspberry Pi's bluetooth (check `bluetoothctl` for the siliconlab device name and mac address [example:- 1C:C0:89:2D:30:45 voice_ble_controller]).
- Refer to [Raspberry Pi Setup](raspberry_pi_setup.md) for complete setup instructions.

---

## 2. Configuration (User Action Required)

Before running the system, you must update the following scripts with your specific details:

### 🔹 BLE audio collection (`sml ops ble receive` or `ble_receiver.py`) 

The recommended way to collect BLE audio is the CLI command:

```bash
sml ops ble receive \
  --device-name "<YOUR_DEVICE_NAME>" \
  --device-address "<YOUR_MAC_ADDRESS>" \
  --output-dir "/path/to/your/audio_samples" \
  --labels "on,off,unknown"
```

Alternatively, [ble_receiver.py](../scripts/rpi/ble_receiver.py) uses the `silabs_mlops.ble` SDK library to handle all Bluetooth communication. It calls `ble.config()` to pass your BLE connection parameters to the library, then starts a `BLEReceiver` loop that connects, listens for keyword detections, and saves audio files automatically.

You have **two options** to provide your BLE connection parameters:

**Option A – Set as Environment Variables** (Recommended for security):
```bash
export BLE_DEVICE_NAME="<YOUR_DEVICE_NAME>"
export BLE_DEVICE_ADDRESS="<YOUR_MAC_ADDRESS>"
export BLE_VOICE_RESULT_UUID="<YOUR_VOICE_RESULT_UUID>"
export BLE_AUDIO_DATA_UUID="<YOUR_AUDIO_DATA_UUID>"
export BLE_OUTPUT_DIR="<YOUR_LOCAL_PATH>"
export BLE_SAMPLE_RATE=<YOUR_SAMPLE_RATE>
export BLE_CHANNELS=<YOUR_CHANNELS>
export BLE_SAMPLE_WIDTH=<YOUR_SAMPLE_WIDTH>
export BLE_BUFFER_SIZE=<YOUR_BUFFER_SIZE>
export BLE_SCAN_TIMEOUT=<YOUR_SCAN_TIMEOUT>
export BLE_LABELS="<keyword1>,<keyword2>,unknown"
```

**Option B – Edit directly in the script**:
Open `ble_receiver.py` and replace the placeholders:
```python
DEVICE_NAME = os.getenv("BLE_DEVICE_NAME", "<YOUR_DEVICE_NAME>")          
DEVICE_ADDRESS = os.getenv("BLE_DEVICE_ADDRESS", "<YOUR_MAC_ADDRESS>")        
VOICE_RESULT_UUID = os.getenv("BLE_VOICE_RESULT_UUID", "<YOUR_VOICE_RESULT_UUID>")
AUDIO_DATA_UUID = os.getenv("BLE_AUDIO_DATA_UUID", "<YOUR_AUDIO_DATA_UUID>")        
OUTPUT_DIR = os.getenv("BLE_OUTPUT_DIR", "<YOUR_LOCAL_PATH>")              
SAMPLE_RATE = os.getenv("BLE_SAMPLE_RATE", 16000)    # <- (optional) replace these values with your own values 
CHANNELS = os.getenv("BLE_CHANNELS", 1)              # <- (optional) replace these values with your own values
SAMPLE_WIDTH = os.getenv("BLE_SAMPLE_WIDTH", 2)      # <- (optional) replace these values with your own values

# Labels: comma-separated, must match your firmware's class order
_labels_env = os.getenv("BLE_LABELS")
LABELS = _labels_env.split(",") if _labels_env else ["<keyword1>", "<keyword2>", "unknown"]
```

> **LABELS – Most Important!** The firmware your board runs assigns an integer **Class ID** (0, 1, 2...) to each keyword it detects. Your `labels` list must match this exact order. Check your Simplicity Studio project (e.g., `audio_classifier_config.h` or `app_voice.h`) to find your keyword order. If you retrain with new keywords, just update this list!
> ```python
> # Example: if your firmware defines Class 0 = "on", Class 1 = "off", Class 2 = "unknown"
> LABELS = ["on", "off", "unknown"]
> ```

> **Note**: For more details on how to configure the BLE module, refer to the [BLE Module Guide](ble_module_guide.md).

### 🔹 `ingestion_service.py` (Cloud Settings)
Open `ingestion_service.py` and update the placeholders with your Databricks/ZeroBus credentials:

```python
# Provide your own credentials below
os.environ["ZEROBUS_WORKSPACE_URL"] = "https://<your-workspace-url>.azuredatabricks.net"
os.environ["ZEROBUS_CLIENT_ID"] = "<your-service-principal-client-id>"
os.environ["ZEROBUS_CLIENT_SECRET"] = "<your-service-principal-client-secret>"

# ZeroBus Endpoint and Table
os.environ["ZEROBUS_SERVER_ENDPOINT"] = "<your-workspace-id>.zerobus.<region>.azuredatabricks.net"
os.environ["ZEROBUS_TABLE_NAME"] = "<catalog>.<schema>.<table_name>"

# Databricks Volume Path (Example: "/Volumes/main/default/audio_data")
os.environ["DATABRICKS_VOLUME_PATH"] = "/Volumes/<catalog>/<schema>/<volume>"

# The local folder on your Pi where files are temporarily saved. This **must match** `BLE_OUTPUT_DIR` / `--output-dir`
os.environ["BLE_OUTPUT_DIR"] = "/path/to/your/audio_samples"
```

> For details on obtaining these databricks credentials, refer to the [Databricks Setup Guide](databricks_setup_guide.md).

### 🔹 Ingestion Service Options

Once your configurations are set in `ingestion_service.py` and `ble_receiver.py`, tune optional environment variables:

**Simplicity Commander** (hardware ID detection):
```bash
export COMMANDER_PATH="/path/to/your/commander-cli"
```

**Parallel uploads** (`NUM_WORKERS`, default `4`):
- Use `NUM_WORKERS=1` for sequential (one file at a time).
- Increase for high-volume parallel uploads (keep below 7 on a Raspberry Pi).
```bash
export NUM_WORKERS=4
```

**File pattern** (optional, default `*.wav`):
```bash
export INGEST_PATTERN="*.wav"
```

> **Note**: If Simplicity Commander is not installed or the path is wrong, the service skips hardware ID detection and uses a generic Raspberry Pi identifier instead.

---

## 3. Overview

There are two Python scripts you run as your core gateway system:

1. **`ble_receiver.py`** (Required)
2. **`ingestion_service.py`** (Required)

Both delegate to the `sml` SDK (`sml ops ble receive` and `sml ops ingest serve` are equivalent CLI commands).

### `ble_receiver.py`
- Connects to the BLE board via Bluetooth.
- Receives raw audio and metadata from the BLE device.
- Saves the detected audio as `.wav` files into the local folder that the upload system monitors.

### `ingestion_service.py`
- Thin shim that calls `sml.ops.data.serve()` with settings from your `.env`.
- Watches the local folder for new files and uploads them to Databricks.
- Configure credentials and paths via environment variables (see section 2).

---

## 4. Databricks Table Schema
The data ingestion system requires a destination table in Databricks Unity Catalog. **ZeroBus does not automatically create this table or manage its schema.**

### Important: Mandatory Fields
When the `data.file_ingest()` function is called by the ingestion service, it **automatically adds** two more fields to your metadata. You do not need to provide these in your metadata dictionary; however, you **must** include these column names in your Databricks table schema:

1. **`file_path`**: The audio file path in the Databricks Volume (STRING).
2. **`ingest_ts`**: The exact timestamp of the audio file ingestion (TIMESTAMP).

### Correct SQL Example
To ensure ingestion succeeds, create your table in Databricks using this exact schema (matching the metadata in your ingestion script):

```sql
CREATE TABLE main.default.ble_audio_metadata (
  -- User-defined metadata in ingestion script
  device_id STRING,
  device_name STRING,
  file_name STRING,
  class_label STRING,
  content_type STRING,
  sample_rate INT,
  duration_ms INT,
  -- Columns automatically provided by file_ingest()
  file_path STRING,    
  ingest_ts TIMESTAMP  
) USING DELTA;
```

> [!NOTE]
> If you want a different schema or different metadata for the audio files you are ingesting, pass a custom `metadata_builder` to `IngestionService` or `data.serve()` in Python. However, you must always include the **`file_path`** and **`ingest_ts`** fields as they are automatically provided by the SDK and are mandatory for the table creation on the Databricks side.

---

## 5. How to Run the System

### Step 1: Start the BLE Receiver
Open a terminal and run either:
```bash
sml ops ble receive
```
or the standalone script:
```bash
python ble_receiver.py
```
This connects to your Silicon Labs Edge device via Bluetooth. As soon as the Edge device detects a keyword locally, it transmits an audio sample to be saved in your local folder.

### Step 2: Start the Upload System
Open a **second terminal** and run either:

**Recommended (SDK CLI):**
```bash
sml ops ingest serve
```

**Python API:**
```python
from sml.ops import data

data.config(
    server_endpoint="...",
    workspace_url="...",
    table_name="...",
    client_id="...",
    client_secret="...",
)
data.serve(
    monitor_dir="/path/to/audio_samples",  # or BLE_OUTPUT_DIR from .env
    volume_path="/Volumes/catalog/schema/volume",
    pattern="*.wav",
    workers=4,
)
```

**Legacy script (still supported):**
```bash
python ingestion_service.py
```

The service monitors your local folder for new files matching `--pattern` (default `*.wav`) and uploads them to Databricks. Use `--workers 1` for sequential uploads or increase for parallel uploads (default: 4, env: `NUM_WORKERS`).

Required environment variables (can also be passed as CLI flags):
- `BLE_OUTPUT_DIR` — local watch directory (`--monitor-dir`)
- `DATABRICKS_VOLUME_PATH` — Unity Catalog volume base path (`--volume-path`)
- `ZEROBUS_*` — ZeroBus/Databricks credentials
- `COMMANDER_PATH` — optional path to commander-cli for hardware detection

---

## 6. Changing Commands or Classification (New Model Usecase)

If you train a new model for your board (e.g., switching from "ON/OFF" to "DOG/CAT"), you only need to change one line in **`ble_receiver.py`**:

```python
# Match this to your new firmware's classes!
LABELS = ["dog", "cat", "unknown"]
```

The system will automatically pick up the new labels and update your Databricks table accordingly. You do **not** need to change any cloud code.

## 7. Important Notes
- **Automatic Metadata**: The system automatically reads the **Sample Rate** from the audio file header. If you change your board's sample rate, simply update it in `ble_receiver.py` and the cloud will follow.
- **Storage Efficiency**: The Raspberry Pi automatically **deletes** local `.wav` files after they are successfully uploaded to Databricks to save space.
- **Error Recovery**: If you lose internet connection, the data ingestion engine will keep retrying until the files are safely uploaded.
- **Metadata Matching**: Every key in your `metadata` dictionary (including the automatic `file_path` and `ingest_ts` fields) must have a corresponding column name and data type in your Databricks table.
- **Failures**: If there is any mismatch between your metadata and the Databricks table schema, the system will return a **Schema Mismatch (4044)** error and the local file will not be deleted.
- **BLE Board**: Keep the BLE board powered ON and within Bluetooth range.
- **Keep Both Terminals Running**: Do not close either terminal while the system is operating.
- Use **Ctrl + C** to stop the scripts.



