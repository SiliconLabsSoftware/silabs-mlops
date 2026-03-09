# Model Module — User Guide

> **Package:** `silabs_mlops.model`
>
> This module provides the core MLOps capabilities for working with AI/ML models on Silicon Labs embedded devices: compiling TensorFlow/Keras models to TFLite, deploying firmware to hardware targets, and profiling inference performance on the NPU.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Quick-Start Examples](#2-quick-start-examples)
3. [TFLite Compiler](#3-tflite-compiler)
4. [Model Deployer](#4-model-deployer)
5. [NPU Profiler](#5-npu-profiler)
6. [Top-Level Convenience Function: `profile()`](#6-top-level-convenience-function-profile)
7. [Data Classes Reference](#7-data-classes-reference)
8. [DeployConfig Reference](#8-deployconfig-reference)
9. [Error Handling](#9-error-handling)
10. [Prerequisites & Environment Variables](#10-prerequisites--environment-variables)

---

## 1. Overview

The `model` module exposes three main components:

| Component | Class / Function | Purpose |
|---|---|---|
| **Compiler** | `TFLiteCompiler` | Convert Keras / SavedModel → `.tflite` with INT8 quantization |
| **Deployer** | `ModelDeployer` | Flash a firmware/model artifact to a Silicon Labs device |
| **Profiler** | `NPUProfiler` | Run the Silicon Labs `mvp_profiler` tool and parse results |
| **Convenience** | `profile()` | Module-level shortcut to `NPUProfiler.profile()` |

Public exports (available directly from `silabs_mlops.model`):

```python
from silabs_mlops.model import (
    DeployConfig,       # Deployment configuration dataclass
    ModelDeployer,      # Flashes model artifacts to embedded targets
    NPUProfiler,        # Wraps the Silicon Labs mvp_profiler CLI tool
    ProfileResult,      # Structured result from a profiling session
    LayerProfile,       # Per-layer profiling data
    profile,            # Module-level convenience wrapper for NPUProfiler.profile()
)
```

---

## 2. Quick-Start Examples

### 2.1 Compile a Keras model to TFLite

```python
from silabs_mlops.model.compiler import TFLiteCompiler

compiler = TFLiteCompiler()
output_path = compiler.compile(
    model="path/to/my_model.h5",
    output_path="output/my_model.tflite"
)
print(f"Compiled model saved to: {output_path}")
```

### 2.2 Deploy a model to a connected device

```python
from silabs_mlops.model import DeployConfig, ModelDeployer

config = DeployConfig(
    model_uri="models:/my_registered_model/Production",
    device_ip="192.168.1.42"
)
deployer = ModelDeployer(config)
deployer.deploy()
```

### 2.3 Profile a model on hardware

```python
from silabs_mlops.model import profile

result = profile(
    model_path="output/my_model.tflite",
    device_id="440339411",
    output_dir="profiling_results/",
    accelerator="mvpv1"
)
print(f"Arena size: {result.arena_size_kb:.1f} KB")
print(f"Total MACs: {result.total_macs:,}")
```

### 2.4 Profile using the simulator (no hardware)

```python
from silabs_mlops.model import profile

result = profile(
    model_path="output/my_model.tflite",
    use_simulator=True,
    output_dir="profiling_results/"
)
```

---

## 3. TFLite Compiler

**Class:** `silabs_mlops.model.compiler.TFLiteCompiler`

Converts TensorFlow/Keras models to `.tflite` format optimized for Silicon Labs MCUs. Applies INT8 full-integer quantization by default, with automatic fallback to dynamic-range quantization if INT8 conversion fails.

### `compile()`

```python
TFLiteCompiler.compile(
    model: Union[tf.keras.Model, str],
    output_path: str,
    optimize_for_size: bool = True,
    representative_dataset: Optional[Callable] = None
) -> str
```

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | `tf.keras.Model` \| `str` | ✅ | A Keras model object, or a path to a `.h5`, `.keras`, or SavedModel directory |
| `output_path` | `str` | ✅ | Output file path (`.tflite`) or directory. If a directory is given, saves as `model_optimized.tflite` |
| `optimize_for_size` | `bool` | ❌ | Apply `tf.lite.Optimize.DEFAULT` (default: `True`) |
| `representative_dataset` | `Callable` | ❌ | A generator function yielding calibration samples for INT8 quantization. Falls back to synthetic data if not provided |

**Returns:** Absolute path (`str`) to the compiled `.tflite` file.

**Raises:**
- `FileNotFoundError` — model path does not exist
- `ValueError` — unsupported file format or invalid SavedModel directory
- `RuntimeError` — TFLite Converter or quantization failed

### Supported Input Formats

| Input | Detected By |
|---|---|
| In-memory `tf.keras.Model` | direct object |
| Keras `.h5` or `.keras` file | file extension |
| TensorFlow SavedModel directory | presence of `saved_model.pb` |

### Quantization Strategy

The compiler follows this priority:

1. **INT8 full-integer quantization** (preferred for MCU targets) — uses the provided or synthetic representative dataset.
2. **Dynamic-range fallback** — if INT8 conversion fails, automatically falls back to float32 I/O with dynamic-range ops.

The output filename is suffixed to indicate the type: `_int8.tflite` or `_dynamic.tflite`.

> **Tip:** For best accuracy on-device, always provide a real representative dataset (100–500 samples from your actual training distribution).

```python
import numpy as np

def my_representative_data():
    for _ in range(200):
        yield [np.random.uniform(-1, 1, (1, 128)).astype(np.float32)]

compiler.compile(
    model=my_keras_model,
    output_path="output/model.tflite",
    representative_dataset=my_representative_data
)
```

---

## 4. Model Deployer

**Class:** `silabs_mlops.model.deployer.ModelDeployer`

Orchestrates the end-to-end deployment of a model artifact (firmware binary or `.tflite`) to a Silicon Labs embedded device using **Simplicity Commander**.

### Workflow

```
1. Validate all inputs (URI format, IP address, Commander binary)
2. Download the model artifact from the appropriate source
3. Flash the artifact to the target device via Simplicity Commander
4. Clean up temporary files (always, even on failure)
```

### Constructor

```python
ModelDeployer(config: DeployConfig)
```

Validates the `DeployConfig` at construction time. Raises `ValueError` or `FileNotFoundError` immediately if any setting is invalid.

### `deploy()`

```python
ModelDeployer.deploy() -> None
```

Runs the full deployment pipeline. Downloads the model and flashes it to the hardware target.

**Raises:**
- `FileNotFoundError` — model artifact not found locally or on server
- `PermissionError` — Databricks authentication failed (HTTP 401/403)
- `RuntimeError` — Simplicity Commander returned a non-zero exit code

### Supported Model URI Formats

The deployer resolves `model_uri` in this order:

| URI Format | Example | Behavior |
|---|---|---|
| Local path | `/path/to/firmware.s37` | Used as-is, never deleted |
| HTTP/HTTPS URL | `https://databricks.../file.tflite` | Downloaded via authenticated HTTP |
| MLflow Model Registry | `models:/my_model/Production` | Downloaded via MLflow |
| MLflow Run Artifact | `runs:/<run_id>/model.s37` | Downloaded via MLflow |
| Short artifact name | `iot_model` | Resolved via `ArtifactRegistry` (`artifacts.yaml`) |

### Supported Firmware File Extensions

Files with these extensions are recognized as flashable artifacts:

- `.s37` — Motorola S-record (most common for Silicon Labs)
- `.bin` — Raw binary
- `.hex` — Intel HEX format
- `.tflite` — TensorFlow Lite flat buffer

### Usage Example

```python
from silabs_mlops.model import DeployConfig, ModelDeployer

# Deploy from MLflow Model Registry via SWD
config = DeployConfig(
    model_uri="models:/gesture_classifier/Staging",
    device_ip=None,        # USB/SWD — no IP needed
    interface="swd",
    verify=True,
)
deployer = ModelDeployer(config)
deployer.deploy()

# Deploy from a Databricks Volume URL over IP
config = DeployConfig(
    model_uri="https://my-workspace.azuredatabricks.net/.../model.s37",
    device_ip="192.168.1.100",
    noverify=True           # Skip post-flash verification (required for IP mode)
)
ModelDeployer(config).deploy()
```

---

## 5. NPU Profiler

**Class:** `silabs_mlops.model.profiler.NPUProfiler`

A Python wrapper around the Silicon Labs **`mvp_profiler`** command-line tool (part of the NPU Toolkit). Runs the profiler binary, streams its output to the terminal, and parses the result files into structured Python objects.

### Binary Resolution Order

The profiler binary is resolved in this priority:

1. Explicit path provided via `profiler_path` parameter
2. `mvp_profiler` / `mvp_profiler.exe` on the system `PATH`
3. `python -m npu_toolkit.profiler` (if the Python package is installed)
4. `sml` / `sml.exe` on the system `PATH` (fallback)

### `discover_devices()`

```python
NPUProfiler.discover_devices(
    profiler_path: Optional[str] = None
) -> List[DeviceInfo]
```

Discovers connected Silicon Labs development boards using `sdm adapter list`.

**Returns:** A list of `DeviceInfo` objects. Returns an empty list if no boards are found or `sdm` is unavailable.

```python
profiler = NPUProfiler()
devices = profiler.discover_devices()
for d in devices:
    print(f"Device ID: {d.device_id}, Board: {d.board}, Connection: {d.connection_type}")
```

### `profile()`

```python
NPUProfiler.profile(
    model_path: str,
    device_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    profiler_path: Optional[str] = None,
    gui: bool = False,
    timeout: int = 600,
    accelerator: str = "mvpv1",
    platform: Optional[str] = None,
    weights_paging: bool = False,
    use_simulator: bool = False
) -> ProfileResult
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `model_path` | `str` | — | Path to `.tflite` or compiled `.zip` model file |
| `device_id` | `str` | `None` | J-Link serial number or IP address of the target device |
| `output_dir` | `str` | `None` | Directory for saving profiling artifacts. Auto-generated with timestamp if not set |
| `profiler_path` | `str` | `None` | Explicit path to `mvp_profiler` binary |
| `gui` | `bool` | `False` | If `True`, launches the Profiler GUI at `http://localhost:8080` |
| `timeout` | `int` | `600` | Maximum seconds to wait for the profiler subprocess |
| `accelerator` | `str` | `"mvpv1"` | Target hardware accelerator (e.g., `"mvpv1"`, `"mvpv2"`) |
| `platform` | `str` | `None` | Target platform string (e.g., `"brd2605"`) |
| `weights_paging` | `bool` | `False` | Enable weights paging for large models |
| `use_simulator` | `bool` | `False` | Run profiling in local simulation mode (no hardware required) |

**Returns:** `ProfileResult` containing all structured profiling metrics and output file paths.

**Raises:**
- `FileNotFoundError` — model file not found (unless `gui=True`)
- `EnvironmentError` — `mvp_profiler` / `sml` binary not found on PATH
- `RuntimeError` — profiler subprocess failed or timed out

### Profiling Modes

| Mode | How to Enable | Use Case |
|---|---|---|
| **Real hardware** (auto-discover) | `device_id=None`, `use_simulator=False` | Production profiling with auto device pick |
| **Real hardware** (specific device) | `device_id="440339411"` | When multiple devices are connected |
| **Simulator** | `use_simulator=True` | No hardware; quick cycle-accurate estimates |
| **GUI** | `gui=True` | Interactive exploration at `http://localhost:8080` |

---

## 6. Top-Level Convenience Function: `profile()`

A module-level function that wraps `NPUProfiler().profile()` for ergonomic one-liner use.

```python
from silabs_mlops.model import profile

result = profile(
    model_path: str,
    device_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    profiler_path: Optional[str] = None,
    gui: bool = False,
    timeout: int = 600,
    accelerator: str = "mvpv1",
    platform: Optional[str] = None,
    weights_paging: bool = False,
    use_simulator: bool = False
) -> ProfileResult
```

Accepts the same parameters as `NPUProfiler.profile()`. The profiler instance is shared at the module level (`silabs_mlops.model._profiler`).

---

## 7. Data Classes Reference

### `ProfileResult`

Returned by `NPUProfiler.profile()` and `profile()`. Contains all parsed profiling metrics and artifact paths.

| Field | Type | Description |
|---|---|---|
| `model_name` | `str` | Stem of the model filename |
| `model_path` | `str` | Absolute path to the profiled model |
| `device_id` | `str` | Device ID used (or `"auto"`) |
| `output_dir` | `str` | Directory where artifacts were saved |
| `arena_size_kb` | `float \| None` | Runtime tensor arena size in KB |
| `total_macs` | `int \| None` | Total multiply-accumulate operations |
| `board` | `str \| None` | Target board identifier (e.g., `"BRD2608A"`) |
| `layers` | `List[LayerProfile]` | Per-layer breakdown |
| `summary_txt_path` | `str \| None` | Path to the plain-text profiling summary |
| `report_json_path` | `str \| None` | Path to the JSON/YAML report |
| `pftrace_path` | `str \| None` | Path to the Perfetto trace file (`.pftrace`) |
| `captured_packets_path` | `str \| None` | Path to captured packets JSON |
| `raw_report` | `dict \| None` | Raw parsed contents of the report file |

**Example usage:**

```python
result = profile("model.tflite", use_simulator=True)

print(f"Arena size : {result.arena_size_kb:.1f} KB")
print(f"Total MACs : {result.total_macs:,}")
print(f"Layers     : {len(result.layers)}")
print(f"Report     : {result.report_json_path}")
```

---

### `LayerProfile`

Per-layer profiling data within `ProfileResult.layers`.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Layer name |
| `input_shape` | `str` | Input tensor shape (as string) |
| `output_shape` | `str` | Output tensor shape (as string) |
| `mcu_cycles` | `int` | CPU cycles consumed by this layer |
| `mcu_stalls` | `int` | CPU stall cycles |
| `acc_cycles` | `int` | Accelerator (MVP) cycles |
| `acc_stalls` | `int` | Accelerator stall cycles |
| `time_ms` | `float` | Estimated execution time in milliseconds |

**Example: iterate over layers**

```python
for layer in result.layers:
    print(f"{layer.name:30s}  {layer.time_ms:.3f} ms  acc_cycles={layer.acc_cycles:,}")
```

---

### `DeviceInfo`

Returned by `NPUProfiler.discover_devices()`.

| Field | Type | Description |
|---|---|---|
| `device_id` | `str` | J-Link serial number (7–12 digits) |
| `board` | `str \| None` | Board part number (e.g., `"BRD2608A"`) |
| `connection_type` | `str \| None` | Connection type (e.g., `"usb"`) |
| `raw` | `str` | Raw text of the line from `sdm adapter list` |

---

## 8. DeployConfig Reference

**Class:** `silabs_mlops.model.config.DeployConfig` (a Python `dataclass`)

```python
@dataclass
class DeployConfig:
    model_uri: str
    commander_path: Optional[str] = "commander"
    device_ip: Optional[str] = None
    interface: str = "swd"
    verify: bool = True
    halt: bool = False
    noverify: bool = False
```

| Field | Type | Default | Description |
|---|---|---|---|
| `model_uri` | `str` | *(required)* | MLflow URI, HTTP URL, local path, or short artifact name |
| `commander_path` | `str \| None` | `"commander"` | Path to Simplicity Commander binary; auto-discovered if not set |
| `device_ip` | `str \| None` | `None` | IP address of the target device (for network-connected boards) |
| `interface` | `str` | `"swd"` | Debug interface: `"swd"` or `"jtag"` |
| `verify` | `bool` | `True` | Verify flash contents after writing (`--verify` flag) |
| `halt` | `bool` | `False` | Halt CPU core after flashing (`--halt` flag) |
| `noverify` | `bool` | `False` | Skip verification — required when flashing via IP (`--noverify` flag). Takes precedence over `verify`. |

---

## 9. Error Handling

### Compiler Errors

| Exception | Cause |
|---|---|
| `FileNotFoundError` | The model path string does not point to an existing file |
| `ValueError` | Unsupported file extension or directory missing `saved_model.pb` |
| `RuntimeError` | TFLite converter failed; check TF version in the error message |

### Deployer Errors

| Exception | Cause |
|---|---|
| `ValueError` | Invalid `model_uri` format or `device_ip` |
| `FileNotFoundError` | `commander` binary not found; no firmware file in artifact dir |
| `PermissionError` | HTTP 401/403 — Databricks token missing or insufficient permissions |
| `RuntimeError` | Simplicity Commander returned non-zero exit code |

**Authentication for Databricks downloads:**

```bash
# Set before running any deployment
set DATABRICKS_HOST=https://my-workspace.azuredatabricks.net
set DATABRICKS_TOKEN=dapi...
```

### Profiler Errors

| Exception | Cause |
|---|---|
| `FileNotFoundError` | Model `.tflite` file not found |
| `EnvironmentError` | `mvp_profiler` / `sml` binary not found on `PATH` |
| `RuntimeError` | Profiler subprocess failed or timed out |

**Install the NPU toolkit:**

```bash
# Via Silicon Labs Toolchain Manager
slt install sml

# Or search for 'Silabs Machine Learning' in Simplicity Studio
```

---

## 10. Prerequisites & Environment Variables

### Required Tools

| Tool | Required For | Install |
|---|---|---|
| `tensorflow` | `TFLiteCompiler` | `pip install tensorflow` |
| `mlflow` | `ModelDeployer` (MLflow URIs) | `pip install mlflow` |
| `requests` | `ModelDeployer` (HTTP URLs) | `pip install requests` |
| `simplicity_commander` | `ModelDeployer` (flashing) | Simplicity Studio |
| `mvp_profiler` / `sml` | `NPUProfiler` | Simplicity Studio / `slt install sml` |

### Environment Variables

| Variable | Used By | Description |
|---|---|---|
| `DATABRICKS_HOST` | `ModelDeployer` | Databricks workspace URL (e.g., `https://...azuredatabricks.net`) |
| `DATABRICKS_TOKEN` | `ModelDeployer` | Personal Access Token for Databricks API auth |
| `MLFLOW_TRACKING_URI` | `ModelDeployer` | MLflow tracking server URI (set automatically by Databricks) |

### `.env` File Support

The library automatically loads a `.env` file from the project root (using `python-dotenv`). You can define environment variables there:

```dotenv
DATABRICKS_HOST=https://my-workspace.azuredatabricks.net
DATABRICKS_TOKEN=dapi...
MLFLOW_TRACKING_URI=databricks
```

---

*Generated for `silabs-mlops-cli` — Silicon Labs MLOps SDK.*
