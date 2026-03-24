# Databricks Notebook Profiling Guide

This guide explains how to use the `model_profiling.ipynb` notebook to profile your Silicon Labs AI/ML models directly within a Databricks environment.

***

## Overview

The `model_profiling.ipynb` notebook provides a complete workflow for:

1.  **Model Profiling** – Running the Silicon Labs NPU simulator to analyze performance metrics.
2.  **Cloud Storage** – Uploading profiling results to Databricks Unity Catalog Volumes.
3.  **Experiment Tracking** – Logging metrics and artifacts to MLflow.
4.  **Model Registration** – Registering validated models to the Unity Catalog Model Registry.
5.  **Log Management** – Syncing SDK logs to Delta tables.

***

## Prerequisites & Setup

### 1. Upload the Notebook to Databricks

1.  Log into your Databricks Workspace.
2.  Navigate to: `Workspace → Users → <your-email>`.
3.  Right‑click the folder → **Import**.
4.  Upload `examples/model_profiling.ipynb`.

***

### 2. Setup the NPU Toolkit Model Profiler (`mvp_profiler`)

The SDK requires the `mvp_profiler` toolkit to generate profiling metrics. It must be available either in your cluster PATH or provided manually through the notebook.

#### Download the Linux version of `mvp_profiler`

Since Databricks clusters run on Linux:

**Direct download link (Linux binary):**  
<https://github.com/SiliconLabsSoftware/aiml-extension/raw/refs/heads/main/tool/profiler/mvp_profiler>

***

You can set up the profiler using one of the following methods:

***

## Option A — Add to System PATH (Recommended for Admins)

### Method 1: Cluster Init Script (Persistent)

1.  Upload the Linux binary to a Unity Catalog Volume:  
    `/Volumes/<catalog>/<schema>/<volume>/mvp_profiler`

2.  Create an init script (e.g. `setup_profiler.sh`):

```bash
#!/bin/bash
cp /Volumes/<catalog>/<schema>/<volume>/mvp_profiler /usr/local/bin/mvp_profiler
chmod +x /usr/local/bin/mvp_profiler
```

3.  Configure the script:  
    **Compute → Cluster → Edit → Advanced Options → Init Scripts**

4.  Restart the cluster.

***

### Method 2: Add via Environment Variables (Simpler)

1.  Upload `mvp_profiler` to your workspace, e.g.:  
    `/Workspace/Users/<email>/mvp_profiler`

2.  Make executable:

```bash
%sh
chmod +x /Workspace/Users/<email>/mvp_profiler
```

3.  Add to PATH:  
    **Compute → Edit → Advanced Options → Spark → Environment Variables**

<!---->

    PATH=$PATH:/Workspace/Users/<email>/

4.  Restart the cluster.
5.  Verify:

```bash
%sh
which mvp_profiler
```

***

## Option B — Manual Workspace Upload (Standard Users)

1.  Download the Linux `mvp_profiler` binary.
2.  Upload it to your workspace, e.g.:  
    `/Workspace/Users/<your-email>/mvp_profiler`
3.  Provide its full path in the notebook:

```python
profiler_path = "/Workspace/Users/<your-email>/mvp_profiler"
```

***

### 3. Upload Your Model

Upload your compiled `.tflite` model to your workspace:

`/Workspace/Users/<your-email>/model.tflite`

***

## Notebook Configuration

Update the following placeholders in the notebook before running.

***

### Global Configuration Cell

*   `<your-zerobus-endpoint>`
*   `<your-workspace-url>`
*   `<catalog>.<schema>.<table_name>`
*   `<your-client-id>`
*   `<your-client-secret>`

> This table name is required by the unified configuration but is not used by `model.profile()`.

***

### Profiling Cell

*   `model_path`: Path to your `.tflite` model
*   `volume_path`: Unity Catalog Volume for output
*   `profiler_path`: Only required if using Option B

***

### MLflow Cell

*   `experiment_name`: Path for MLflow experiment
    *   Automatically created if not present
*   `volume_path`: Same as profiling step

***

### Model Registration Cells

#### Teacher Model

```python
teacher_v = register_single_file(
    "<path>/model.teacher.h5",
    "<catalog>.<schema>.model_teacher",
    "teacher_register"
)
```

#### Student Model

```python
student_v = register_single_file(
    "<path>/model.tflite",
    "<catalog>.<schema>.model_student",
    "student_register"
)
```

***

### Upload Logs Cell

*   `<your-sql-warehouse-name>`
*   `<catalog>.<schema>.<table_name>`

***

## Running the Notebook

1.  **Initialization** – Run the first two cells to restart the Python engine and install the `silabs-mlops` library:
    ```python
    %pip install silabs-mlops
    ```
2.  **Configuration** – Run `data.config()`
3.  **Profiling** – Executes NPU simulator and uploads results
4.  **MLflow Tracking** – Logs artifacts and metrics
5.  **Registration** – Registers teacher and student models
6.  **Log Upload** – Syncs SDK logs to Delta tables

***

## Detailed Model Registry Notes

*   Unity Catalog model names must follow:  
    `catalog.schema.model_name`
*   Re-registering updates model version automatically.
*   Using a new name creates a new model entity.

***

## Troubleshooting

*   Ensure all Workspace paths begin with `/Workspace/` or `/Users/`.
*   Ensure the Linux profiler binary is used.
*   Validate Service Principal permissions:
    *   `USE CATALOG`, `USE SCHEMA`, `WRITE VOLUME`
*   Verify PATH configuration if using Option A.
*   Confirm your ZeroBus credentials are correct.

***
