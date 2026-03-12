# Model Profiling User Guide

The Silicon Labs MLOps Model Profiling library provides a Python wrapper around the Silicon Labs NPU Toolkit (`mvp_profiler`). It allows users to profile compiled `.tflite` or `.zip` models on actual Silicon Labs hardware or in a local simulator.


With the unified configuration design:

> **Call `data.config()` once. The model module automatically uses the same credentials for cloud uploads and logging.**

This makes the profiling workflow simple, secure, and fully integrated with Databricks.

---

## Key Features
- **Hardware Integration**: Profile models directly on connected Silicon Labs boards.
- **Local Simulation**: Run profiling without physical hardware using the built-in simulator.
- **Result Collections**: Captures arena size, total MACs, layer-by-layer metrics, and Perfetto traces.
- **Cloud Integration**: Automatically uploads profiling artifacts and history logs to Databricks Unity Catalog Volumes.
- **Automatic Logging**: Every profiling session is automatically tracked in the central CLI logger.
- **Global Configuration Shared Across Modules**: No repeated credential entry — both `data` and `model` modules reuse the same config.

---

## Quick Start

Before profiling, call the global config **once**. If you have already called it for data ingestion that's enough no need to call it again:

```python 
# Call this ONLY if you have NOT already configured the global credentials.
# If you already called data.config() earlier (e.g., during data ingestion),
# you DO NOT need to call it again before profiling.
from silabs_mlops import data

data.config(
    server_endpoint="your-zerobus-endpoint.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="catalog.schema.some_temp_table",   # Required globally (ignored by profiler)
    client_id="your-service-principal-id",
    client_secret="your-service-principal-secret"
)
```

### 1. Basic Profiling (Hardware)
To profile a model on a connected Silicon Labs board:

```python
from silabs_mlops import model

# This automatically discovers the first connected board and profiles the model
result = model.profile("models/my_model.tflite")

print(f"Arena Size: {result.arena_size_kb} KB")
print(f"Total MACs: {result.total_macs}")
```

### 2. Local Simulation (No Hardware Required)
To profile the model quickly on your local CPU without a connected board:

```python
from silabs_mlops import model

result = model.profile("models/my_model.tflite", use_simulator=True)
```

---

## Output Artifacts
Every profiling session generates a unique output directory (locally or in the cloud) containing:
- **`profiling_summary.txt`**: A human-readable text summary of memory and cycles.
- **`profiling_results.yaml`**: Structured YAML data of metrics and per-layer performance.
- **`profiling_history.log`**: A complete capture of the profiler's console output (very useful for debugging errors).

---

## Databricks Volume Upload
You can automatically upload all profiling results to a Databricks Volume by providing a `volume_path`.

```python
from silabs_mlops import model

result = model.profile(
    model_path="models/my_model.tflite",
    volume_path="/Volumes/main/default/profiling_results",
    use_simulator=True
)

# result.output_dir is a dynamic path that always points to where your results are stored
# result.output_dir will now point to the remote Databricks URL path (e.g., /Volumes/main/default/...). 
print(f"Remote Results: {result.output_dir}")
```

---

## Advanced: Manual Configuration
For complex setups, you can specify custom paths and hardware targets.

```python
from silabs_mlops import model

result = model.profile(
    model_path="my_model.tflite",
    device_id="123456789",          # Specific J-Link serial
    accelerator="mvpv1",            # Hardware target
    platform="brd2605",             # Specific platform board
    weights_paging=True,            # Enable paging
    timeout=1200                    # Wait up to 20 minutes
)
```

---

## Monitoring & Logging
Every profiling session is automatically logged. Even if the profiling fails, the `profiling_history.log` is captured and uploaded to the cloud if a `volume_path` is specified.

**Via CLI:**
```bash
silabs-mlops logs --type "Profiling"
```

**Via Python Script:**
```python
from silabs_mlops.logs import Logger

logger = Logger()
# Filter only for profiling events
logger.view(event_type="Profiling")
```
