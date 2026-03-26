# Model Profiling User Guide

The Silicon Labs MLOps Model Profiling library provides a Python wrapper around the Silicon Labs MVP Profiler (`mvp_profiler`). It allows users to profile compiled `.tflite` or `.zip` models on actual Silicon Labs hardware or in a local simulator.

With the unified configuration design:

> **Call `data.config()` once. The model module automatically uses the same credentials for cloud uploads and logging.**

This makes the profiling workflow simple, secure, and fully integrated with Databricks. For workspace and credential setup details, see the [Databricks Setup Guide](databricks_setup_guide.md).

---

## Key Features

- **Hardware Integration**: Profile models directly on connected Silicon Labs boards.
- **Local Simulation**: Run profiling without physical hardware using the built-in simulator.
- **Result Collections**: Captures arena size, total MACs, layer-by-layer metrics, and Perfetto traces.
- **Cloud Integration**: Automatically uploads profiling artifacts and history logs to Databricks Unity Catalog Volumes.
- **Automatic Logging**: Every profiling session is automatically tracked in the central CLI logger.
- **Global Configuration Shared Across Modules**: No repeated credential entry — both `data` and `model` modules reuse the same config.

---

> [!IMPORTANT]
> **Mandatory Tooling**: To perform profiling, the Silicon Labs **MVP Profiler model profiler (mvp_profiler)** MUST be installed and added to your system's PATH. Without this tool, the profiling session will fail.

## Installation & Path Setup

The profiling library requires the Silicon Labs **MVP Profiler model profiler (mvp_profiler)** to be installed on your workstation.

### 1. Setup the ML Profiler

Ensure that you have downloaded and installed the mvp_profiler binary for your operating system (Windows or Linux).
You can download both versions from the official Silicon Labs [GitHub repository](https://github.com/SiliconLabsSoftware/aiml-extension/tree/main/tool/profiler).
After installing, use the following steps to make sure the profiler is added to your system’s PATH so the CLI and Python library can access it globally.

#### **Windows**

1. Open **Settings** → Search for **"Edit the system environment variables"**.
2. Click **Environment Variables**.
3. Under **System Variables**, find and select **Path**, then click **Edit**.
4. Click **New** and add the full path to the folder containing `mvp_profiler.exe` (e.g., `C:\SiliconLabs\MLProfiler\bin`).
5. Restart your terminal.

#### **Linux / macOS**

Add the following line to your `~/.bashrc`, `~/.zshrc`, or `~/.bash_profile`:

```bash
export PATH=$PATH:/path/to/npu_toolkit/bin
```

Then, reload your shell:

```bash
source ~/.bashrc  # or ~/.zshrc
```

### 2. Manual Profiler Path (Alternative)

If you prefer not to add it to your PATH, you can provide the explicit path directly in your Python script:

```python
from sml.ops import model

result = model.profile(
    model_path="my_model.tflite",
    profiler_path="C:/path/to/mvp_profiler.exe" # Manual path to the tool on Windows
    # profiler_path="/path/to/mvp_profiler" # Manual path to the tool on Linux
)
```

---

## Quick Start

Before profiling, ensure your **Global Configuration** is set. If you have already set it earlier in your script for the data ingestion, you can skip this no need to call it again.

#### **Option 1: Using Environment Variables**

```python
import os
from sml.ops import data
# Call this ONLY if you have NOT already configured the global credentials.
# If you already called data.config() earlier (e.g., during data ingestion), you DO NOT need to call it again before profiling.
data.config(
    server_endpoint=os.getenv("ZEROBUS_SERVER_ENDPOINT"),
    workspace_url=os.getenv("ZEROBUS_WORKSPACE_URL"),
    table_name=os.getenv("ZEROBUS_TABLE_NAME"),
    client_id=os.getenv("ZEROBUS_CLIENT_ID"),
    client_secret=os.getenv("ZEROBUS_CLIENT_SECRET")
)
```

#### **Option 2: Direct Configuration**

```python
from sml.ops import data

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
from sml.ops import model

# This automatically discovers the first connected board and profiles the model
result = model.profile("models/my_model.tflite")

print(f"Arena Size: {result.arena_size_kb} KB")
print(f"Total MACs: {result.total_macs}")
```

### 2. Local Simulation (No Hardware Required)

To profile the model quickly on your local CPU without a connected board:

```python
from sml.ops import model

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

You can automatically upload all profiling results to a Databricks Volume by providing a `volume_path`. For volume permissions and creation steps, see the [Databricks Setup Guide](databricks_setup_guide.md).

```python
from sml.ops import model
try:
    result = model.profile(
        model_path=model_path,
        use_simulator=True,     # runs locally on PC
        volume_path="/Volumes/my_catalog/my_schema/profiling_results" #-> add your volume path here
    )
    # The result object contains all the extracted data:
    print(f"  ✓ Model:         {result.model_name}")
    print(f"  ✓ Arena Size:    {result.arena_size_kb:.1f} KB")
    print(f"  ✓ Total MACs:    {result.total_macs:,}")
    # result.output_dir is a dynamic path that always points to where your results are stored
    # result.output_dir will now point to the remote Databricks URL path (e.g., /Volumes/main/default/...).
    print(f"Remote Results: {result.output_dir}")
    print(f"  ✓ History Log:   {result.history_log_path}")
except Exception as e:
    # If there is a failure, the script will crash here
    # but the history.log will STILL upload to the volume path.
    print(f"  [!] Profiling failed -> {e}")
```

---

## Advanced: Manual Configuration

For complex setups, you can specify custom paths and hardware targets.

```python
from sml.ops import model

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
sml ops logs --type "Profiling"
```

**Via Python Script:**

```python
from sml.ops.logs import Logger

logger = Logger()
# Filter only for profiling events
logger.view(event_type="Profiling")
```
