# Silicon Labs MLOps CLI

The Silicon Labs MLOps CLI is a professional toolset designed to seamlessly bridge the gap between edge devices and cloud-based Machine Learning platforms. It provides a robust Command Line Interface (CLI) and Python API to manage the end-to-end MLOps lifecycle—focusing on high-throughput data ingestion to Databricks via ZeroBus and secure firmware/model deployment directly to Silicon Labs hardware.

## Installation

To use the `silabs-mlops` CLI command anywhere on your system, you need to install it. 

```bash
# Standard installation for users
pip install .

# Installation for developers (editable mode)
pip install -e .
```

## Key Design Principles

- Clear separation of concerns
    - Data lifecycle ≠ Model lifecycle

- Hardware-aware ML
    - Compile and profile are first-class citizens

- Governed deployments
    - No unprofiled or unversioned model reaches devices

- Cloud + Edge hybrid
    - Edge execution, cloud intelligence

- Databricks-native
    - Delta Lake, Jobs, Model Registry as system of record

---

## High-Level Architecture Flow
```
Data Lifecycle
 └─ ingest    → ZeroBus → Databricks Bronze

Model Lifecycle
 ├─ profile   → Simulator-based performance validation
 └─ deploy    → ZeroBus-based edge deployment
```

## SDK Structure

```
silabs_mlops_sdk/
├── data/
│   └── ingest/
│
├── model/
│   ├── profile/
│   └── deploy/
│
├── common/
├── config/
└── cli/
```
---

## Module Responsibilities
`data.collect`

### Purpose:
Collect BLE sensor data on Raspberry Pi and buffer it locally.

### Responsibilities:

- BLE scanning
- Local buffering (file / ring buffer)
- Edge-safe fault handling
---
`data.ingest`
### Purpose:
Send buffered data to the cloud ingestion layer.

### Responsibilities:

- Publish data to ZeroBus
- Enforce Bronze schema compatibility
- Reliable delivery semantics

---

`model.profile`

### Purpose:
Validate compiled models using the Silicon Labs Simulator.

### Responsibilities:

- Measure:
    - Cycle count
    - Flash & RAM usage
    - Latency
    - Runtime errors
- Persist profiling history in Databricks
- Gate models before deployment

--- 
`model.deploy`

### Purpose:
Deploy approved models to edge devices.

### Responsibilities:

- Query Databricks for:
    - Correct model version
    - Artifact download URL
    - Target device(s)
- Send deployment instructions via ZeroBus
- Raspberry Pi downloads & installs model
- Update deployment history
- Support rollback

---

## Documentation

For detailed instructions, architecture, and configuration, please refer to the following guides:

- [**Quickstart Guide**](QUICKSTART.md): The fastest way to get your first model deployed and your first data ingested. Start here!
- [**User Guide**](USER_GUIDE.md): Comprehensive documentation covering all CLI commands, authentication setups, expected data formats, and Python API usage.