# Silicon Labs MLOps CLI User Guide

This guide explains how to install, configure, and use the SiLabs MLOps CLI to move data and models between Databricks and your Silicon Labs hardware.

---

## Installation

Clone the repository and install the tool in editable mode. This makes the `silabs-mlops` command available in your terminal.

```bash
cd silabs-mlops-cli
pip install -e .
```

---

## Setup and Authentication

The tool needs credentials to talk to Databricks. Open the `.env` file located inside the inner `silabs-mlops-cli/silabs-mlops-cli/` folder and provide your workspace URL. 

For authentication, you have two options. You only need to provide one.

- **Option 1: Personal Access Token**
  ```bash
  DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
  DATABRICKS_TOKEN=your_pat_token_here
  ```

- **Option 2: Service Principal (Client ID and Secret)**
  ```bash
  DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
  DATABRICKS_CLIENT_ID=your_client_id
  DATABRICKS_CLIENT_SECRET=your_client_secret
  ```

---

## Features

The tool is grouped into two main areas: `ingest` for sending data to Databricks, and `model` for deploying models back to devices via Raspberry Pi.

### 1. Data Ingestion

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

- **JSON Array:**
  ```json
  [
    {"device_id": "sensor-1", "temperature": 22.5},
    {"device_id": "sensor-2", "temperature": 23.1}
  ]
  ```

- **JSON Lines (newline-delimited):**
  ```
  {"device_id": "sensor-1", "temperature": 22.5}
  {"device_id": "sensor-2", "temperature": 23.1}
  ```

---

### 2. Raspberry Pi Model Deployment

This command flashes a firmware or model file onto a connected Silicon Labs device by communicating with a remote Raspberry Pi via **SCP** and **SSH**.

To deploy, you need to provide the target Raspberry Pi's IP address and SSH username.

```bash
silabs-mlops model deploy --uri ./my_model.s37 --rpi-host 192.168.1.111 --rpi-user aimlraspberry
```

#### How it Works:
- **SCP Phase**: The tool securely transfers your local firmware file to the Raspberry Pi's `/tmp` directory.
- **Auto-Detection**: It remotely invokes Simplicity Commander to detect the connected J-Link serial number and target Silicon Labs chip.
- **Flashing**: It executes the final flash command on the Raspberry Pi.

For detailed SSH key setup and Raspberry Pi environment configuration, see the [RPI_DEPLOYMENT_GUIDE.md](RPI_DEPLOYMENT_GUIDE.md).

---

## Python Examples

The `examples/` folder contains scripts for direct Python API usage.

- **`examples/rpi_deployment.py`**:
  Shows how to use the `RPiDeployer` class to programmatically automate remote Raspberry Pi flashing.

- **`examples/data_ingestion.py`**:
  Shows how to use the `DataIngestor` class to send JSON records to Databricks Unity Catalog tables.
