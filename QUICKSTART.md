# Quick Start

This guide helps you get the Silicon Labs MLOps SDK running end-to-end with the minimum required steps, from data ingestion to edge model deployment.

## Prerequisites
Before starting, ensure you have:

**Edge & Hardware**
- Silicon Labs device connected (e.g., EFR32, xG24) over J-Link or Ethernet
- Silicon Labs Simplicity Commander installed
- Python 3.9+

**Cloud / Platform**
- Databricks workspace
- Access to Unity Catalog (Delta tables)
- Access to Databricks Volumes or MLflow Registry
- ZeroBus broker access for streaming ingestion

## Installation
Clone the SDK repository and install the CLI:

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
from silabs_mlops.data import DataIngestor, IngestConfig

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

## Step 2: Compile the Model

Once data is trained into a model in Databricks, developers export it. Locally, compile the model for Silicon Labs hardware.

```python
from silabs_mlops import model

model.compile(
    model="raw_model.h5",
    output_path="optimized_model.tflite",
    optimize_for_size=True
)
```

**What happens:**
- Converts TensorFlow/Keras format into a `.tflite` file
- Applies automated INT8 quantization
- Model is now ready for edge execution

*(Note: In a standard workflow, this optimized model is then uploaded to a Databricks Volume or MLflow Registry).*

## Step 3: Deploy to Edge Devices

Download the optimized model from the Databricks cloud and flash it to the physical device.

```python
from silabs_mlops.model import ModelDeployer, DeployConfig

config = DeployConfig(
    model_uri="iot_model",
    device_ip="192.168.1.100", # Optional if using direct USB debugging
    verify=True,
    commander_path=r"C:\Path\To\commander-cli.exe" # Optional if available in PATH
)

deployer = ModelDeployer(config)
deployer.deploy()
```

**What happens:**
- SDK resolves "iot_model" to the Databricks Volume URL using `artifacts.yaml`
- Securely negotiates an OAuth Bearer token
- Downloads the model artifact
- Invokes Simplicity Commander to flash the `.tflite` payload directly to the device memory
- Confirms checksum and cleans up temporary downloads

---

## End-to-End (Single Command Flow via CLI)

The exact same workflow is available directly from the terminal without writing Python scripts:

```bash
# 1. Ingest edge data
silabs-mlops ingest --file sensor_data.json

# 2. Compile model for SiLabs hardware
silabs-mlops model compile --input raw_model.h5 --output optimized_model.tflite

# 3. Pull model from cloud and flash to hardware
silabs-mlops model deploy --uri iot_model --ip 192.168.1.100
```
