***

# **Data Ingestion System – User Guide**

This guide provides simple instructions for running the data‑ingestion system on a **Raspberry Pi**, which automatically collects audio from the BLE board and uploads it to the cloud.

***

# **1. Prerequisites**

##  **Dependencies to Install**

Install the following on your Raspberry Pi:

*   **Silicon Labs MLOps SDK**
    ```bash
    pip install silabs-mlops
    ```
    *Note: `ingestion_engine.py` uses internal SDK functions to securely forward edge data to Databricks via ZeroBus.*

*   **bleak** – For Bluetooth (BLE) communication

*   **pyaudio** – For real‑time audio handling

***

##  **Raspberry Pi Setup**

Before running the system, ensure:

*   Raspberry Pi is fully configured for BLE and file handling
*   BLE board is connected to Raspberry Pi via power + Bluetooth
*   Raspberry Pi is configured as per:  
    **raspberry\_pi\_setup.md**

***

##  **Required User Configuration**

Several fields must be **manually updated** by the user inside the scripts.

***

###  **In `ingestion_engine.py`**

You *must* set:

*   `MONITOR_DIR` – Directory where audio files are saved
*   `COMMANDER_PATH` – Path to the commander tool

***

###  **In `ble_receiver.py`**

Set the following:

*   `DEVICE_NAME` – BLE device name
*   `DEVICE_ADDRESS` – BLE MAC address
*   `OUTPUT_DIR` – Output folder for processed audio

***

###  **In `ingestion_service.py`**

You *must* insert your Databricks and ZeroBus credentials:

```python
# Databricks & ZeroBus Credentials
os.environ["ZEROBUS_WORKSPACE_URL"] = "https://<your-workspace-url>.azuredatabricks.net"
os.environ["ZEROBUS_CLIENT_ID"] = "<your-service-principal-client-id>"
os.environ["ZEROBUS_CLIENT_SECRET"] = "<your-service-principal-client-secret>"

# ZeroBus Endpoint and Table
os.environ["ZEROBUS_SERVER_ENDPOINT"] = "<workspace-id>.zerobus.<region>.azuredatabricks.net"
os.environ["ZEROBUS_TABLE_NAME"] = "<catalog>.<schema>.<table_name>"

# Databricks Volume Path
os.environ["DATABRICKS_VOLUME_PATH"] = "/Volumes/<catalog>/<schema>/<volume>"
```

For guidance on obtaining these values, see:  
**databricks\_setup\_guide.md**

***

# **2. System Overview**

The ingestion system is composed of three scripts:

1.  **ingestion\_service.py**
2.  **ingestion\_engine.py**
3.  **ble\_receiver.py**

You will manually run only:

 `ingestion_service.py`  
 `ble_receiver.py`

***

##  **What Each Script Does**

### **`ingestion_service.py`**

*   Entry point for the ingestion system
*   Contains environment variables and credentials
*   Prepares the ingestion environment
*   Starts `ingestion_engine.py` automatically (background process)
*   No need to manually run `ingestion_engine.py`

***

### **`ble_receiver.py`**

*   Connects to the BLE board
*   Receives audio packets
*   Saves audio to a directory monitored by the ingestion system

***

# **3. How to Run the System**

##  **Step 1: Start the Upload System**

```bash
python ingestion_service.py
```

This initializes the ingestion pipeline.

***

##  **Step 2: Start the BLE Receiver**

Open a **new terminal** and run:

```bash
python ble_receiver.py
```

This script listens to the BLE board and writes audio files locally.

***

##  **Step 3: Let the System Run**

*   Audio files will appear automatically
*   The ingestion system uploads them to Databricks
*   After upload, processed files are automatically deleted
*   Logs will show upload and classification updates

***

# **4. Notes & Best Practices**

*   Keep BLE board powered ON and within Bluetooth range
*   Do not delete files manually from the monitored directory
*   Two terminals must remain running
*   The speech‑recognition model runs locally on the Pi
*   The **audio\_classifier/** folder is provided only as an example — users should replace it with their own model files
*   Stop scripts with:  
    **Ctrl + C**

***
