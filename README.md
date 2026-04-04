# Silicon Labs MLOps SDK

The Silicon Labs MLOps SDK is a professional toolset designed to seamlessly bridge the gap between edge devices and cloud-based Machine Learning platforms. It provides a robust Command Line Interface (CLI) and Python API to manage the end-to-end MLOps lifecycle—focusing on high-throughput data ingestion to Databricks via ZeroBus and secure firmware/model deployment to Silicon Labs hardware via Raspberry Pi.

## Features

- **Data Ingestion**: High-throughput JSON and file ingestion to Databricks Unity Catalog via ZeroBus and Workspace API.
  - `data.ingest()`: Batch metadata ingestion to Delta Tables.
  - `data.file_ingest()`: Combined binary file upload to Volumes and metadata ingestion.
- **Remote Hardware Deployment**: Automated model/firmware flashing to Silicon Labs chips via SCP and SSH onto a Raspberry Pi.
- **NPU Profiling**:
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

## SDK Structure

```text
sml/
└── ops/
    ├── ble/                (Bluetooth connectivity)
    ├── data/
    │   └── ingest/         (ZeroBus integration)
    ├── model/
    │   ├── profiler.py     (NPU Profiler)
    │   └── deployer.py     (Edge Deployer)
    ├── common/             (Auth & Validators)
    ├── config.py           (Global configuration)
    ├── logs.py             (Universal Logger)
    └── cli.py              (Main CLI entry point)
```

## Requirements

- **Python** 3.9 or newer (`requires-python` in `pyproject.toml`).
- **Profiling** — [Silicon Labs MVP Profiler (`mvp_profiler`)](https://github.com/SiliconLabsSoftware/aiml-extension/tree/main/tool/profiler) must be installed and on your `PATH` when you use profiling features.
- **Databricks / ZeroBus** — Workspace credentials and ZeroBus configuration are required for ingest and cloud-backed profiling; see [Databricks Setup Guide](docs/databricks_setup_guide.md).

## Installation

To use the Silicon Labs MLOps SDK and Python libraries, you must first install the package.

### Using pip

- **End users** (runtime / deploy only):

  ```bash
  pip install silabs-mlops
  ```

  > NOTE:
  > If you are working in a Databricks Notebook or Jupyter, use the magic command:
  >
  > ```python
  > %pip install silabs-mlops
  > ```

- **Developers** (tests and tooling; quotes are required on Windows):

  ```bash
  pip install -e ".[test]"
  ```

### Using uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you do not already have it.

- **End users** (install from the repo root):

  ```bash
  uv pip install silabs-mlops
  ```

- **Developers** (editable install with test extras; quotes are required on Windows):

  ```bash
  uv pip install -e ".[test]"
  ```

- **Locked environment** (uses `uv.lock` — reproducible deps for local work):

  ```bash
  uv sync
  ```

  Installs the project into `.venv` with locked dependencies. For this repository, the `dev` dependency group (`pytest`, `pytest-cov`) is included by default. To sync without those tools, use `uv sync --no-group dev`.

If package installs or syncs misbehave because **uv** is picking up configuration from `pyproject.toml` or `uv.toml` (for example custom indexes), add **`--no-config`** so uv skips those files — e.g. `uv sync --no-config`, `uv pip install . --no-config`, or `uv build --no-config`. You can also set **`UV_NO_CONFIG=1`** in the environment.

### Verify Installation

After installation, you can verify it by running:

```bash
sml ops --help
```

### Building distributable artifacts with uv

From the repository root, build a wheel and source distribution into `dist/`:

```bash
uv build
```

Outputs are standard **`.whl`** and **`.tar.gz`** artifacts you can publish or install with `pip install dist/<artifact>`.

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

## CLI

After installation, the console script **`sml`** is available (`sml.ops.cli`). Remote deployment and environment setup are covered in [Raspberry Pi Deployment Guide](docs/deployment_guide.md).

## Build Executable Binaries

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

## Repository layout

| Path                             | Role                                          |
| -------------------------------- | --------------------------------------------- |
| `sml/ops/`                       | Python package: `data`, `model`, CLI, logging |
| `docs/`                          | User and operator guides (linked above)       |
| `examples/model_profiling.ipynb` | Databricks-oriented profiling workflow        |
| `tests/`                         | Test suite                                    |
