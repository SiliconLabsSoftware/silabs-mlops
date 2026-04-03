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

### 🔹 `ble_receiver.py` 

This script uses the `silabs_mlops.ble` SDK library to handle all Bluetooth communication. It calls `ble.config()` to pass your BLE connection parameters to the library, then starts a `BLEReceiver` loop that connects, listens for keyword detections, and saves audio files automatically.

You have **two options** to provide your BLE connection parameters:

**Option A – Set as Environment Variables** (Recommended for security):
```bash
export BLE_DEVICE_NAME="<YOUR_DEVICE_NAME>"
export BLE_DEVICE_ADDRESS="<YOUR_MAC_ADDRESS>"
export BLE_RESULT_UUID="<YOUR_VOICE_RESULT_UUID>"
export BLE_DATA_UUID="<YOUR_AUDIO_DATA_UUID>"
export AUDIO_SAMPLES_DIR="<YOUR_LOCAL_PATH>"
export BLE_SAMPLE_RATE=<YOUR_SAMPLE_RATE>
export BLE_CHANNELS=<YOUR_CHANNELS>
export BLE_SAMPLE_WIDTH=<YOUR_SAMPLE_WIDTH>
export BLE_LABELS="<keyword1>,<keyword2>,unknown"
```

**Option B – Edit directly in the script**:
Open `ble_receiver.py` and replace the placeholders:
```python
DEVICE_NAME = os.getenv("BLE_DEVICE_NAME", "<YOUR_DEVICE_NAME>")          
DEVICE_ADDRESS = os.getenv("BLE_DEVICE_ADDRESS", "<YOUR_MAC_ADDRESS>")        
VOICE_RESULT_UUID = os.getenv("BLE_RESULT_UUID", "<YOUR_VOICE_RESULT_UUID>")  #<- your metadata UUID
AUDIO_DATA_UUID = os.getenv("BLE_DATA_UUID", "<YOUR_AUDIO_DATA_UUID>")        
OUTPUT_DIR = os.getenv("AUDIO_SAMPLES_DIR", "<YOUR_LOCAL_PATH>")              
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

# The local folder on your Pi where files are temporarily saved. This **must match** the `OUTPUT_DIR` in ble_receiver.py
os.environ["AUDIO_SAMPLES_DIR"] = "/path/to/your/audio_samples"
```

> For details on obtaining these databricks credentials, refer to the [Databricks Setup Guide](databricks_setup_guide.md).

### 🔹 Choose Your Ingestion Engine

Once your configurations are set in `ingestion_service.py` and `ble_receiver.py`, you must configure your data ingestion script. Based on your specific use case, Use **one** of the two scripts as your data ingestion engine:

#### 1. `sequential_ingestion_engine.py` (Standard / Low-Volume)
**Recommended Use-Case**: This is the default option. This script continuously checks your local folder and uploads single audio files one at a time to Databricks. If you only have a few data samples or a single device, this is the perfect, lightweight script for your workload (no multi-threading).

This script uses **Simplicity Commander** to automatically read your connected SiLabs board's hardware ID and name. You must point it to where you installed Simplicity Commander on your Raspberry Pi.

You have **two options**:

**Option A – Set as an Environment Variable:**
```bash
export COMMANDER_PATH="/path/to/your/commander-cli"
```
**Option B – Edit directly in the script (sequential_ingestion_engine.py):**
```python
COMMANDER_PATH = os.getenv("COMMANDER_PATH", "/path/to/your/commander-cli") # <- replace this path with your own commander-cli path
```

#### 2. `batch_ingestion_engine.py` (High-Volume Simultaneous)
**Recommended Use-Case**: If you have multiple devices or a high volume of audio files streaming in rapidly, then use this script to handle simultaneous parallel uploads via worker threads. By processing a batch of files concurrently (instead of one-by-one), it drastically reduces overall upload time and prevents a backlog on your Raspberry Pi.

If you choose to use the **`batch_ingestion_engine.py`** script, the base configuration in `ingestion_service.py` (your Databricks credentials) and `ble_receiver.py` mentioned above remains exactly the same. You simply need to apply a few settings regarding your commander path and worker threads (either via environment variables or directly inside the script) and modify `ingestion_service.py` to launch it:

**2.1 Update Simplicity Commander Path**

Just like above, configure the path to your Simplicity Commander. You have the same two options:

**Option A – Set as an Environment Variable:**
```bash
export COMMANDER_PATH="/path/to/your/commander-cli"
```
**Option B – Edit directly in the script (`batch_ingestion_engine.py`):**
```python
COMMANDER_PATH = os.getenv("COMMANDER_PATH", "/path/to/your/commander-cli") # <- replace this path with your own commander-cli path
```

**2.2 Handle High-Volume Ingestion (Optional)**

The script handles multiple simultaneous uploads using **worker threads**. If you have many audio files coming in at once, you can increase this number:

- **Variable**: `NUM_WORKERS` (Default: `4`)
- **Recommendation**: Keep this **below 7** on a Raspberry Pi to avoid system slowdown.
- **Option A (Environment Variable)**: `export NUM_WORKERS=6`
- **Option B (Direct Edit)**: Edit `NUM_WORKERS = int(os.getenv("NUM_WORKERS", "4"))` in `batch_ingestion_engine.py`.

**2.3 Update `ingestion_service.py`**

Finally, open your `ingestion_service.py` and tell it to launch the parallel ingestion script instead:

* **Comment out:** `import sequential_ingestion_engine`
* **Uncomment:** `import batch_ingestion_engine as sequential_ingestion_engine`

> **Note**: If Simplicity Commander is not installed or the path is wrong in whichever script you choose, the script will skip hardware ID detection and use a generic Raspberry Pi identifier instead.

---

## 3. Overview

There are four Python scripts provided in the examples folder, but you will only run **three** of them as your core gateway system:

1. **`ble_receiver.py`** (Required)
2. **`ingestion_service.py`** (Required)
3. **`sequential_ingestion_engine.py`** *(Use for Standard Uploads)*
4. **`batch_ingestion_engine.py`** *(Use for High-Volume Concurrent Uploads)* 

You will manually execute only **two** scripts in your terminal:
- `ble_receiver.py`
- `ingestion_service.py`

### `ble_receiver.py`
- Connects to the BLE board via Bluetooth.
- Receives raw audio and metadata from the BLE device.
- Saves the detected audio as `.wav` files into the local folder that the upload system monitors.

### `ingestion_service.py`
- Starts the entire upload system to Databricks.
- This file serves as an interface between the edge device and Databricks for data ingestion. It contains the required Databricks credentials, and users must update these credentials with their own before running the system.
- Once launched, it automatically triggers your chosen underlying ingestion script (`sequential_ingestion_engine.py` or `batch_ingestion_engine.py`) in the background.
- You do not need to run the underlying ingestion scripts manually.

---

## 4. Databricks Table Schema
The data ingestion system requires a destination table in Databricks Unity Catalog. **ZeroBus does not automatically create this table or manage its schema.**

### Important: Mandatory Fields
When the `data.file_ingest()` function is called in the ingestion script (`sequential_ingestion_engine.py` or `batch_ingestion_engine.py`), it **automatically adds** two more fields to your metadata. You do not need to provide these in your metadata dictionary; however, you **must** include these column names in your Databricks table schema:

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
> If you want a different schema or different metadata for the audio files you are ingesting, you can modify the `metadata` dictionary in the ingestion script you have chosen (**`sequential_ingestion_engine.py`** or **`batch_ingestion_engine.py`**) to match your new schema. However, you must always include the **`file_path`** and **`ingest_ts`** fields as they are automatically provided by the SDK and are mandatory for the table creation on the Databricks side.

---

## 5. How to Run the System

### Step 1: Start the BLE Receiver
Open a terminal and run:
```bash
python ble_receiver.py
```
This script connects to your Silicon Labs Edge device via Bluetooth. As soon as the Edge device detects a keyword locally, it transmits an audio sample to be saved in your local folder.

### Step 2: Start the Upload System
Open a **second terminal** and run:
```bash
python ingestion_service.py
```
This script acts as a service manager. It automatically launches your chosen data ingestion engine (`sequential_ingestion_engine.py` or `batch_ingestion_engine.py`) in the background. The underlying engine is what strictly monitors the local folder for new `.wav` files and uploads them to Databricks. You do not need to run or do anything else.

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



