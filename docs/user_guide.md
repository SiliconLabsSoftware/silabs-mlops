# Silicon Labs MLOps CLI User Guide

This guide explains how to install, configure, and use the SiLabs MLOps toolset to manage data ingestion, model profiling, and remote hardware deployment via Raspberry Pi.

---

## Installation

To use the `silabs-mlops` CLI and Python libraries, you must first install the package.

### Standard Installation (For Users)
Use this if you just want to run the CLI and use the library:
```bash
pip install .
```

### Developer Installation (Editable Mode)
Use this if you plan to modify the code or are testing new features:
```bash
pip install -e .
```

---

## Setup and Authentication

The tool requires credentials for Databricks and ZeroBus. Store these in a `.env` file in the project root.

### Databricks Credentials
You can use either a Personal Access Token or a Service Principal:

- **Option 1: Service Principal (Recommended)**
  ```bash
  DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
  DATABRICKS_CLIENT_ID=your-client-id
  DATABRICKS_CLIENT_SECRET=your-client-secret
  ```

- **Option 2: Personal Access Token**
  ```bash
  DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
  DATABRICKS_TOKEN=dapi...
  ```

---

## Databricks & Unity Catalog Setup

Before using the ingestion or profiling features, your Databricks workspace and Service Principal (SP) must be correctly configured.

### Prerequisites
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
> **Workspace Consistency**: You must create your Volumes in the **same workspace** where you provide the workspace credentials via `data.config()`. All metadata (URL, Client ID, Secret) used to store results and logs is automatically fetched from this configuration.

---

## Data Ingestion

Stream IoT sensor data from edge devices directly into Databricks Delta Tables (Bronze layer) using the ZeroBus connector.
For detailed information, see the [data_ingest_guide.md](data_ingest_guide.md).

### Key Features
- **Zero-Configuration Ingestion**: Simple API for sending single or batch records.
- **Automatic Logging**: Every attempt is tracked in the central CLI logger.
- **Local Buffering**: Supports reading from local JSON files (Array or Lines).

### Quick Start (Python API)
```python
from silabs_mlops import data

# 1. Configure once
data.config(
    server_endpoint="your-zerobus-endpoint.databricks.com",
    workspace_url="https://your-workspace.databricks.com",
    table_name="catalog.schema.sensor_table",
    client_id="your-id",
    client_secret="your-secret"
)

# 2. Ingest batch of records
records = [{"device_id": "sensor-01", "temp": 24.5}, {"device_id": "sensor-02", "temp": 22.1}]
data.ingest(records)
```

### Ingest from Local Files (CLI)
```bash
silabs-mlops ingest --file sensor_readings.json
```

---

## Model Profiling

The model profiling library provides a Python wrapper around the Silicon Labs NPU Toolkit (`mvp_profiler`) for analyzing models on hardware or in a simulator.
For detailed information, see the [profiling_guide.md](profiling_guide.md).

### Key Features
- **Hardware & Simulation**: Profile on physical boards or via a local CPU simulator.
- **Result Collections**: Captures arena size, MACs, layer-by-layer metrics, and Perfetto traces.
- **Cloud Integration**: Automatically uploads artifacts to Databricks Unity Catalog Volumes.

### Quick Start
```python
from silabs_mlops import model

# Profile on discovered hardware
result = model.profile("my_model.tflite")

# Profile using local simulator (No hardware required)
result = model.profile("my_model.tflite", use_simulator=True)

print(f"Arena Size: {result.arena_size_kb} KB | Total MACs: {result.total_macs}")
```

### Output Artifacts
Every session generates a folder (local or cloud) with:
- `profiling_summary.txt`: Human-readable performance summary.
- `profiling_results.yaml`: Structured layer-by-layer metrics.
- `report.pftrace`: Trace file for Perfetto bottleneck analysis.

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

## Troubleshooting

- **401/403 Error**: Check your `.env` credentials or Volume permissions in Databricks.
- **Schema Mismatch**: Ensure dictionary keys match the Delta Table columns exactly.
- **SSH Timeout**: Verify the Raspberry Pi IP and check for network packet loss.
