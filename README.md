# Silicon Labs MLOps CLI

The Silicon Labs MLOps CLI is a professional toolset designed to seamlessly bridge the gap between edge devices and cloud-based Machine Learning platforms. It provides a robust Command Line Interface (CLI) and Python API to manage the end-to-end MLOps lifecycle—focusing on high-throughput data ingestion to Databricks via ZeroBus and secure firmware/model deployment to Silicon Labs hardware via Raspberry Pi.

---

## Installation

To use the `silabs-mlops` command anywhere on your system, you need to install it in your Python environment.

```bash
# Standard installation for users
pip install .

# Installation for developers (editable mode)
pip install -e .
```

---

## Key Design Principles

- **Clear separation of concerns**: Data lifecycle ≠ Model lifecycle.
- **Hardware-aware ML**: Profiling is a first-class citizen for edge performance.
- **Governed deployments**: No unprofiled model reaches a physical device.
- **Cloud + Edge hybrid**: Edge execution with Cloud intelligence.
- **Databricks-native**: Uses Delta Lake, Jobs, and Model Registry as the system of record.

---

## High-Level Architecture Flow

### Data Lifecycle
- `ingest` → ZeroBus → Databricks Bronze (Delta Lake)

### Model Lifecycle
- `profile` → Simulator/Hardware-based performance validation
- `deploy`  → SCP + SSH based remote edge deployment via Raspberry Pi

---

## SDK Structure

```text
silabs_mlops/
├── data/
│   └── ingest/     (ZeroBus integration)
├── model/
│   ├── profile/    (NPU Profiler)
│   └── deploy/     (RPi Deployer)
├── common/         (Auth & Validators)
├── config/         (Global configuration)
└── cli.py          (Main CLI entry point)
```

---

## Documentation

For detailed instructions, architecture, and configuration, please refer to the following guides:

- [**Quickstart Guide**](quickstart.md): The fastest way to get your first model deployed and your first data ingested. **Start here!**
- [**User Guide**](user_guide.md): Comprehensive documentation covering CLI commands, authentication setups, and Python API usage.
- [**RPi Deployment Guide**](rpi_deployment_guide.md): Specialized guide for configuring Passwordless SSH and Simplicity Commander on a Raspberry Pi.
- [**Data Ingestion Guide**](data_ingest_guide.md): High-performance streaming guide for ZeroBus.
- [**Model Profiling Guide**](profiling_guide.md): Benchmarking models on Silicon Labs hardware and simulators.

---

## Features

- **Data Ingestion**: High-throughput JSON ingestion to Databricks Unity Catalog via ZeroBus.
- **Remote Hardware Deployment**: Automated model/firmware flashing to Silicon Labs chips via SCP and SSH onto a Raspberry Pi.
- **NPU Profiling**: Support for edge model performance profiling using Silicon Labs AI/ML tools.