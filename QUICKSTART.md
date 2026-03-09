# Quick Start

This guide helps you get the Silicon Labs MLOps SDK running end-to-end with the minimum required steps, from data ingestion to edge model deployment via Raspberry Pi.

## Prerequisites
Before starting, ensure you have:

**Edge & Hardware**
- Silicon Labs device connected (e.g., EFR32, xG24) to a **Raspberry Pi** via USB
- Silicon Labs Simplicity Commander installed on the Raspberry Pi
- Python 3.9+ installed on your local workstation
- Passwordless SSH configured between your workstation and the Raspberry Pi (see [RPI_DEPLOYMENT_GUIDE.md](RPI_DEPLOYMENT_GUIDE.md))

**Cloud / Platform**
- Databricks workspace
- Access to Unity Catalog (Delta tables)
- Access to Databricks Volumes or MLflow Registry
- ZeroBus broker access for streaming ingestion

## Installation
Clone the SDK repository and install the CLI on your local workstation:

```bash
git clone <repo-url>
cd silabs-mlops-cli
pip install .
```

## Configuration
Secrets and environment settings should be injected via a `.env` file in your working directory. 

Example `.env` file:
```bash
# Databricks Auth (Use PAT OR Service Principal)
DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
# DATABRICKS_TOKEN=your_pat_token_here
DATABRICKS_CLIENT_ID=your_client_id
DATABRICKS_CLIENT_SECRET=your_client_secret

# ZeroBus Target
ZEROBUS_URL=https://<broker-endpoint>
```

Define model artifacts in `artifacts.yaml` to avoid typing full URLs:
```yaml
artifacts:
  iot_model:
    path: "/Volumes/mlops_dev/default/model_d/iot_model.tflite"
    type: "ml-model"
```

---

## Step 1: Ingest Data to Databricks

Send buffered sensor data to Databricks via ZeroBus.

```python
from silabs_mlops.data.ingest import DataIngestor, IngestConfig

config = IngestConfig(
    server_endpoint="https://broker.example.com",
    workspace_url="https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net",
    table_name="catalog.schema.sensor_data",
    client_id="client_id",
    client_secret="client_secret",
    buffer_path="sensor_data.json"
)

ingestor = DataIngestor(config)
ingestor.ingest()
```

**What happens:**
- Reads local JSON sensor buffers
- Connects to ZeroBus
- Data lands securely in Databricks Bronze Delta tables

## Step 2: Deploy to Edge Devices via Raspberry Pi

Upload the firmware/model to a remote Raspberry Pi and flash it to the physical device.

```python
from silabs_mlops.model.rpi_deployer import RPiDeployer

deployer = RPiDeployer(
    rpi_host="192.168.1.111",
    rpi_user="aimlraspberry",
    local_file_path="./my_model.s37",
    commander_path="/home/aimlraspberry/Desktop/SimplicityCommander-Linux/commander-cli/commander-cli"
)

deployer.deploy()
```

**What happens:**
- Connects to the Raspberry Pi over SSH
- SCPs the local firmware file to the Pi's `/tmp` directory
- Remote invokes Simplicity Commander on the Pi
- Auto-detects the J-Link serial and target chip
- Flashes the payload directly to the device memory
- Verifies the write and cleans up

---

## End-to-End (Single Command Flow via CLI)

The exact same workflow is available directly from the terminal without writing Python scripts:

```bash
# 1. Ingest edge data
silabs-mlops ingest --file sensor_data.json

# 2. Deploy firmware to device via Raspberry Pi
silabs-mlops model deploy --uri ./my_model.s37 --rpi-host 192.168.1.111 --rpi-user aimlraspberry
```
