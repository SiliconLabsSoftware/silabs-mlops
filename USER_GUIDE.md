# Silicon Labs MLOps CLI User Guide

This guide explains how to install, configure, and use the SiLabs MLOps CLI to move data and models between Databricks and your Silicon Labs hardware.

## Installation

Clone the repository and install the tool in editable mode. This makes the `silabs-mlops` command available in your terminal.

```bash
cd silabs-mlops-cli
pip install -e .
```

## Setup and Authentication

The tool needs credentials to talk to Databricks. Open the `.env` file located inside the inner `silabs-mlops-cli/silabs-mlops-cli/` folder and provide your workspace URL. 

For authentication, you have two options. You only need to provide one.

Option 1: Personal Access Token
```bash
DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
DATABRICKS_TOKEN=your_pat_token_here
```

Option 2: Service Principal (Client ID and Secret)
```bash
DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
DATABRICKS_CLIENT_ID=your_client_id
DATABRICKS_CLIENT_SECRET=your_client_secret
```

If you leave `DATABRICKS_TOKEN` blank, the tool will automatically attempt to use your Client ID and Secret instead.

## Features

The tool is grouped into two main areas: `ingest` for sending data to Databricks, and `model` for compiling and deploying models back to devices.

### Data Ingestion

Use this command to send sensor data from a local JSON file to a Databricks Unity Catalog table. This uses ZeroBus under the hood.

```bash
silabs-mlops ingest --file sensor_data.json
```

It expects the `ZEROBUS_SERVER_ENDPOINT`, `ZEROBUS_WORKSPACE_URL`, and `ZEROBUS_TABLE_NAME` variables to be set in your `.env` file. You can also pass these directly in the command if you need to override them temporarily:

```bash
silabs-mlops ingest --file sensor_data.json --table my_catalog.my_schema.my_table
```

#### Data Format for Ingestion

The CLI accepts JSON data in two formats:

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

#### Data Architecture

```
User Data → DataIngestor → ZeroBusClient → ZeroBus → Databricks Delta Lake (Bronze)
```

1. **User provides data** - You collect sensor data using your own methods
2. **DataIngestor** - Orchestrates the ingestion workflow
3. **ZeroBusClient** - Wraps the official Databricks ZeroBus SDK
4. **ZeroBus** - Databricks ingestion service
5. **Delta Lake** - Data lands in your specified table (Bronze layer)

#### ZeroBus Configuration Reference

| Field | Description | Example |
|-------|-------------|---------|
| `server_endpoint` | ZeroBus server endpoint | `1234567890123456.zerobus.us-west-2.cloud.databricks.com` |
| `workspace_url` | Databricks workspace URL | `https://dbc-a1b2c3d4-e5f6.cloud.databricks.com` |
| `table_name` | Unity Catalog table | `main.default.sensor_data` |
| `client_id` | Service principal ID | UUID from Databricks |
| `client_secret` | Service principal secret | From Databricks |

See the [Databricks ZeroBus documentation](https://docs.databricks.com/aws/en/ingestion/zerobus-ingest) for setup instructions.

### Model Compilation

Before deploying a standard TensorFlow or Keras model to a device, it needs to be compiled and optimized. The compile command converts your `.h5` or `.keras` file into an optimized, quantized `.tflite` file.

```bash
silabs-mlops model compile --input my_model.h5 --output optimized_model.tflite
```

### Model Deployment

This command flashes a model file onto a connected Silicon Labs device using Simplicity Commander.

You need to tell the tool which model to deploy. You can point it directly to a Databricks Volume URL, an MLflow registry path, or a local file on your computer.

```bash
silabs-mlops model deploy --uri /path/to/local/model.tflite --ip 192.168.1.100
```

Typing out full Databricks Volume URLs can be tedious. To fix this, you can define "short names" for your models in the `artifacts.yaml` file located in the project root.

Example `artifacts.yaml` entry:
```yaml
artifacts:
  iot_model:
    path: "/Volumes/mlops_dev/default/model_d/iot_model.tflite"
    type: "ml-model"
```

Once defined, you can deploy using just the short name:

```bash
silabs-mlops model deploy --uri iot_model --ip 192.168.1.100
```

## Python Examples

If you prefer writing Python code instead of using the command line, the `examples/` folder contains scripts showing how to use the underlying Python classes directly.

`examples/model_deployment.py`
Shows how to configure the `ModelDeployer` class to automate the process of downloading a model from Databricks and flashing it to a device. 

`examples/data_ingestion.py`
Shows how to configure the `DataIngestor` class to send JSON records to Databricks.

