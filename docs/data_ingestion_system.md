# Data Ingestion System – User Guide

This guide provides simple instructions for running the data ingestion system on the Raspberry Pi. We only need to run two scripts, and the system will automatically collect audio from the BLE board and upload it to the cloud.

---

## 1. Prerequisites

Before running the system, ensure the following:

### Raspberry Pi Setup
- Your Raspberry Pi must be fully configured for BLE communication and file handling.
- The BLE board should be connected to the Raspberry Pi for **power** and **Bluetooth-based communication**.
- Refer to [Raspberry pi setup](raspberry_pi_setup.md) for complete setup instructions.

### Configure Credentials & Paths (Add These Before Running)
Below settings **must be configured by the user** inside the configuration section of scripts.

#### 🔹 In data_ingestion.py file (User must set these)
- **MONITOR_DIR** – Directory where audio files will be saved and monitored.
- **COMMANDER_PATH** – Path to the commander tool.

#### 🔹 In ble_receiver.py file (User must set these)
- **DEVICE_NAME** – BLE device name.
- **DEVICE_ADDRESS** – BLE MAC address of the board.
- **MODEL_PATH** – Path to the speech recognition model (we used the Vosk model, but users can update this path based on the model they choose).
- **OUTPUT_DIR** – Output folder where processed files will be stored.

#### 🔹 In start_ingestion.py file (User must set these)

Open `start_ingestion.py` file and update the following placeholders with your own databricks credentials:

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
```

### Data Ingestion Setup
- The system manages the secure transfer of captured audio from the Raspberry Pi to your Databricks Delta Tables.
- **Mandatory Configuration**: Before running the system, you **must** edit the `start_ingestion.py` script to include your specific Databricks workspace and ZeroBus credentials. For obtaining these details, refer to the [Databricks Setup Guide](databricks_setup_guide.md).


Once the Raspberry Pi setup and ingestion configuration are complete, you can run the scripts as described below.

---

## 2. Overview

There are three Python scripts involved:
1. **start_ingestion.py**
2. **data_ingestion.py**
3. **ble_receiver.py**

You will manually start only **two** of them:
- `start_ingestion.py`
- `ble_receiver.py`

### `start_ingestion.py`
- Starts the entire upload system.
- This file serves as an interface between the edge device and Databricks for data ingestion. It contains the required Databricks credentials, and users must update these credentials with their own before running the system.
- Prepares the environment and launches the background process that monitors audio files.
- This script automatically starts the internal ingestion flow (`data_ingestion.py`).
- You do not need to run any other ingestion-related scripts manually.

### `ble_receiver.py`
- Connects to the BLE board via Bluetooth.
- Receives audio from the BLE device.
- Saves audio files into the local folder that the upload system monitors.

---

## 3. How to Run the System

### Step 1: Start the Upload System
```bash
python start_ingestion.py
```
This prepares the system for uploading audio files.

### Step 2: Start the BLE Receiver
Open another terminal and run:
```bash
python ble_receiver.py
```
This script listens to the BLE board and saves audio samples.

### Step 3: Let It Run
- Audio files will appear automatically.
- The system will upload them to the cloud.
- You can watch the logs for updates.

---

## 4. Changing Commands or Classification (New Model Usecase)
If you need to switch from ON/OFF keywords to different commands or a different classification task, follow these steps in **ble_receiver.py**:

1. **Update Aliases**: Change `ON_ALIASES` and `OFF_ALIASES` (lines 38-39) to match your new target keywords.
2. **Grammar Configuration**: Update `rec.SetGrammar()` in the `OnOffVosk` class (line 82) to include your new keywords.
3. **Normalization Logic**: Update the `normalize_token()` function to handle the mapping of speech-to-text results to your desired labels.
4. **Firmware Label Sync**: ensure the `labels` list in `notification_handler()` (line 142) matches the **Class IDs** defined in your firmware's configuration (`audio_classifier_config.h`).
5. **Adjust Thresholds**: Modify the confidence thresholds (lines 100-101) to suit the sensitivity of your new model.

---

## 5. Notes
- BLE board must remain powered ON and within Bluetooth range.
- Keep both terminals running.
- Do not manually delete files from the audio folder.
- The system automatically deletes processed audio files stored locally after upload onto the cloud to maintain storage efficiency.
- The speech‑recognition model classifies incoming audio locally.
- The provided audio_classifier folder serves only as an example configuration. Users are expected to  update this folder with their own audio classification model files to align with their deployment requirements
- Use **Ctrl + C** to stop the scripts.

