# Silicon Labs MLOps SDK

> **_NOTE:_**
> This software package is experimental, provided “as is”, and considered “BETA SOFTWARE” under the Silicon Labs MSLA (Master Software License Agreement). SILICON LABS DOES NOT OFFER ANY SUPPORT FOR THIS EXPERIMENTAL SOFTWARE AND DISCLAIMS ALL WARRANTIES EXPRESS OR IMPLIED CONCERNING THIS EXPERIMENTAL SOFTWARE.

The Silicon Labs MLOps SDK is a professional toolset designed to seamlessly bridge the gap between edge devices and cloud-based Machine Learning platforms. It provides a robust Command Line Interface (CLI) and Python API to manage the end-to-end MLOps lifecycle—focusing on high-throughput data ingestion to Databricks via ZeroBus and secure firmware/model deployment to Silicon Labs hardware via Raspberry Pi.

## Features

- **Data Ingestion**: High-throughput JSON and file ingestion to Databricks Unity Catalog via ZeroBus and Workspace API.
  - `data.ingest()`: Batch metadata ingestion to Delta Tables.
  - `data.file_ingest()`: Combined binary file upload to Volumes and metadata ingestion.
- **Remote Hardware Deployment**: Automated model/firmware flashing to Silicon Labs chips via SCP and SSH onto a Raspberry Pi.
- **Model profiling** — Support for edge model performance profiling using Silicon Labs AI/ML tools like ML Model Profiler on device, simulator, or in Databricks notebooks.
- **BLE Connectivity**: Collect real-time audio and sensor data from Silicon Labs boards via Bluetooth.
  - `ble.config()`: Global configuration for UUIDs, sample rates, and labels.
  - `ble.BLEReceiver()`: Main class for managing device connection and data capture.
- **Single global configuration** — Call `data.config()` once; data ingestion, profiling, and logging share the same Databricks and ZeroBus credentials.
- **CLI** — The `sml` entry point supports workflows such as remote deployment (see the deployment guide).
- **Cloud integration** — Unity Catalog volumes, MLflow, and related Databricks patterns as described in the guides below.

## Key Design Principles

- **Clear separation of concerns**: Data lifecycle ≠ Model lifecycle.
- **Hardware-aware ML**: Profiling is a first-class citizen for edge performance.
- **Governed deployments**: No unprofiled model reaches a physical device.
- **Cloud + Edge hybrid**: Edge execution with Cloud intelligence.
- **Bluetooth-native collection**: Real-time audio and sensor data capture via low-latency BLE.
- **Databricks-native**: Uses Delta Lake, Unity Catalog Volumes, and Model Registry as the system of record.

## High-Level Architecture Flow

### Data Lifecycle

- **Metadata**: `data.ingest` → ZeroBus → Databricks Delta Tables (Bronze)
- **Files (Audio/Images)**: `data.file_ingest` → Workspace API → Databricks Unity Catalog Volumes

### Model Lifecycle

- `profile` → Simulator-driven NPU benchmarking, latency + memory profiling
- `deploy` → SCP + SSH based remote edge deployment via Raspberry Pi

## Repository layout

```text
.
├── docs/                       (Documentation)
├── firmware/
│   └── aiml_ble_soc_kws_efr32_micriumos/   (Reference BLE KWS Simplicity Studio project)
├── scripts/
│   ├── examples/               (data ingestion, profiling, RPi deployment samples)
│   ├── rpi/                    (ingestion engines, BLE receiver, ingestion service)
│   └── training/               (notebooks and training utilities)
├── sml/                        (installable Python package)
│   └── ops/
│       ├── ble/                (Bluetooth connectivity)
│       ├── data/
│       │   └── ingest/         (ZeroBus client, ingestor, ingest config)
│       ├── model/
│       │   ├── profiler.py     (ML Model Profiler)
│       │   ├── deployer.py     (Edge Deployer)
│       │   └── config.py       (Model/profiling configuration)
│       ├── config.py           (Global SDK configuration)
│       ├── logs.py             (Universal logger)
│       └── cli.py              (Main CLI entry point: sml)
├── tests/                      (pytest suite)
├── pyproject.toml
├── README.md
└── uv.lock
```

## Requirements

- **Python** 3.9 or newer (`requires-python` in `pyproject.toml`).
- **Profiling** — [Silicon Labs MVP Profiler (`mvp_profiler`)](https://github.com/SiliconLabsSoftware/aiml-extension/tree/main/tool/profiler) must be installed and on your `PATH` when you use profiling features.
- **Databricks / ZeroBus** — Workspace credentials and ZeroBus configuration are required for ingest and cloud-backed profiling; see [Databricks Setup Guide](docs/databricks_setup_guide.md).
- **Environment Variables**:

  ```sh

  # ZeroBus Ingestion Configuration
  DATABRICKS_VOLUME_PATH="/Volumes/<catalog>/<schema>/<volume>"
  ZEROBUS_SERVER_ENDPOINT="<workspace-id>.zerobus.<region>.azuredatabricks.net"
  ZEROBUS_WORKSPACE_URL="https://adb-<workspace-id>.<shard>.azuredatabricks.net"
  ZEROBUS_TABLE_NAME="<catalog>.<schema>.<table_name>"
  ZEROBUS_CLIENT_ID="<service-principal-client-id>"
  ZEROBUS_CLIENT_SECRET="<service-principal-client-secret>"

  # BLE app configuration
  BLE_DEVICE_NAME="<BLE App Name>"
  BLE_DEVICE_ADDRESS="xx:xx:xx:xx:xx:xx"
  BLE_RESULT_UUID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  BLE_DATA_UUID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  BLE_LABELS="<keyword1>,<keyword2>,unknown"
  AUDIO_SAMPLES_DIR="/path/to/your/audio_samples"
  ```

## Installation

To use the Silicon Labs MLOps SDK and Python libraries, you must first install the package.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you do not already have it.

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

- **End users**

  ```bash
  uv venv
  uv pip install silabs-mlops
  ```

  > NOTE:
  > If you are working in a Databricks Notebook or Jupyter, use the magic command:
  >
  > ```python
  > %pip install silabs-mlops
  > # or
  > !uv pip install silabs-mlops
  > ```

- **Developers**:

  ```bash
  uv venv
  uv pip install -e ".[test]"
  ```

### Verify Installation

After installation, you can verify it by running:

```bash
sml ops --help
```

For more information about remote deployment and environment, see [Raspberry Pi Deployment Guide](docs/deployment_guide.md).

## Building

### Build Python Packages (Wheels)

From the repository root, build a wheel and source distribution into `dist/`:

```bash
uv build
```

Outputs are standard **`.whl`** and **`.tar.gz`** artifacts you can publish or install with `pip install dist/<artifact>`.

### Build Executable Binaries

Build from the repository root. Commands below assume dependencies are installed in `.venv`.

### PyInstaller

```bash
uv pip install pyinstaller
pyinstaller --onefile --name sml "sml/ops/cli.py"
./dist/sml --help
```

### Nuitka

```bash
uv pip install nuitka zstandard
uv run python -m nuitka --onefile --assume-yes-for-downloads --output-dir=dist --output-filename=sml "sml/ops/cli.py"
./dist/sml --help
```

## Quick start

1. Complete Databricks and ZeroBus setup: [Databricks Setup Guide](docs/databricks_setup_guide.md).
2. Configure the SDK once with `data.config(...)` — see [Data Ingestion User Guide](docs/data_ingest_guide.md) for examples and options.

## Documentation

For detailed instructions, architecture, and configuration, please refer to the following guides:

- [**Quickstart Guide**](docs/quickstart.md): The fastest way to get your first model deployed and your first data ingested. **Start here!**
- [**User Guide**](docs/user_guide.md): Comprehensive documentation covering CLI commands, authentication setups, and Python API usage.
- [**Databricks Setup Guide**](docs/databricks_setup_guide.md): Step-by-step instructions for creating Catalogs, Schemas, and Service Principals in Databricks.
- [**RPi Deployment Guide**](docs/deployment_guide.md): Specialized guide for configuring Passwordless SSH and Simplicity Commander on a Raspberry Pi.
- [**Raspberry Pi Setup**](docs/raspberry_pi_setup.md): Guide for preparing and flashing the Raspberry Pi OS.
- [**Data Ingestion Guide**](docs/data_ingest_guide.md): High-performance streaming guide for ZeroBus and Workspace API.
- [**BLE Module Guide**](docs/ble_module_guide.md): Technical reference for the Bluetooth connectivity library.
- [**Model Profiling Guide**](docs/profiling_guide.md): NPU-accelerated benchmarking for edge models, including latency analysis, memory footprint profiling, and simulator-driven performance validation.
