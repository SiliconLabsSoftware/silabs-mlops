# sml-ops

Silicon Labs MLOps SDK for edge devices and Databricks: ingest IoT data into Delta tables, profile AI/ML models on hardware or simulator, track runs in Databricks, and deploy to edge targets via a CLI.

## Features

- **Single global configuration** — Call `data.config()` once; data ingestion, profiling, and logging share the same Databricks and ZeroBus credentials.
- **Data ingestion** — Stream sensor data into Databricks Delta (Bronze) through the ZeroBus Ingest connector.
- **Model profiling** — Wraps Silicon Labs `mvp_profiler` for `.tflite` / `.zip` models on device, simulator, or in Databricks notebooks.
- **CLI** — The `sml` entry point supports workflows such as remote deployment (see the deployment guide).
- **Cloud integration** — Unity Catalog volumes, MLflow, and related Databricks patterns as described in the guides below.

## Requirements

- **Python** 3.9 or newer (`requires-python` in `pyproject.toml`).
- **Profiling** — [Silicon Labs MVP Profiler (`mvp_profiler`)](https://github.com/SiliconLabsSoftware/aiml-extension/tree/main/tool/profiler) must be installed and on your `PATH` when you use profiling features.
- **Databricks / ZeroBus** — Workspace credentials and ZeroBus configuration are required for ingest and cloud-backed profiling; see [Databricks Setup Guide](docs/databricks_setup_guide.md).

## Installation

### Using pip

- **End users** (runtime / deploy only):

  ```bash
  pip install .
  ```

- **Developers** (tests and tooling; quotes are required on Windows):

  ```bash
  pip install -e ".[test]"
  ```

### Using uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you do not already have it.

- **End users** (install from the repo root):

  ```bash
  uv pip install .
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

Read in this order if you are setting up end-to-end:

| Order | Guide | Description |
| :---: | --- | --- |
| 1 | [Databricks Setup Guide](docs/databricks_setup_guide.md) | Service principal, Unity Catalog, volumes, and how configuration reaches the SDK. |
| 2 | [Data Ingestion User Guide](docs/data_ingest_guide.md) | Ingesting IoT data into Delta via ZeroBus and `data.config()`. |
| 3 | [Model Profiling User Guide](docs/profiling_guide.md) | Profiling on local machine or Silicon Labs hardware with `mvp_profiler`. |
| 4 | [Databricks Notebook Profiling Guide](docs/model_profiling_on_databricks_guide.md) | Using `examples/model_profiling.ipynb` for profiling, MLflow, and model registry on Databricks. |
| 5 | [Raspberry Pi Deployment Guide](docs/deployment_guide.md) | Environment setup, SSH, and model deployment via the CLI. |

## CLI

After installation, the console script **`sml`** is available (`sml.ops.cli`). Remote deployment and environment setup are covered in [Raspberry Pi Deployment Guide](docs/deployment_guide.md).

## Repository layout

| Path | Role |
| --- | --- |
| `sml/ops/` | Python package: `data`, `model`, CLI, logging |
| `docs/` | User and operator guides (linked above) |
| `examples/model_profiling.ipynb` | Databricks-oriented profiling workflow |
| `tests/` | Test suite |
