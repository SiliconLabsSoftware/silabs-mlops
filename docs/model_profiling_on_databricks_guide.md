# Databricks Notebook Profiling Guide

This guide explains how to use the `model_profiling.ipynb` notebook to profile your Silicon Labs AI/ML models directly within a Databricks environment.

## Overview

The `model_profiling.ipynb` notebook provides a complete workflow for:
1. **Model Profiling**: Running the Silicon Labs NPU simulator to analyze model performance (Arena size, Cycle count, etc.).
2. **Cloud Storage**: Automatically uploading profiling results to Databricks Unity Catalog Volumes.
3. **Experiment Tracking**: Logging metrics and artifacts to MLflow for version control and comparison.
4. **Model Registration**: Registering validated models to the Unity Catalog Model Registry.
5. **Log Management**: Syncing SDK action logs to Delta tables for auditing.

---

## Prerequisites & Setup

### 1. Upload the Notebook to Databricks
1. Log in to your Databricks Workspace.
2. Navigate to your user folder: `Workspace` -> `Users` -> `<your-email>`.
3. Right-click on the folder and select **Import**.
4. Drag and drop the `examples/model_profiling.ipynb` file or click **browse** to select it.

### 2. Setup the NPU Toolkit model profiler (`mvp_profiler`)
The SDK requires the `mvp_profiler` toolkit to profile models. It is a mandatory dependency for the profiling and without it, the profiling will fail. You have two options for configuring it in Databricks:

#### Option A: Add to System Path (Recommended for Admins)
If you have permissions, you can upload the **Linux version** of `mvp_profiler` to your Databricks environment (e.g., DBFS, Workspace files, or an init script location), and add the profiler binary to the cluster’s $PATH. When the binary is included in the PATH, the MLOps SDK will automatically locate and use it during profiling without requiring the profiler_path argument.

#### **Steps to add the profiler to the Cluster PATH:**

#### **Method 1: Cluster Init Script (Recommended for Permanent Setup)**
1.  **Upload the Binary**: Upload the Linux `mvp_profiler` to a Unity Catalog Volume (e.g., `/Volumes/<catalog>/<schema>/<volume>/mvp_profiler`).
2.  **Create Init Script**: Create a `.sh` file in your Workspace (e.g., `setup_profiler.sh`) with these contents:

    ```bash
    #!/bin/bash
    cp /Volumes/<catalog>/<schema>/<volume>/mvp_profiler /usr/local/bin/mvp_profiler
    chmod +x /usr/local/bin/mvp_profiler
    ```
3. **Configure Cluster**: In the Databricks UI, 
    * **Databricks** → **Compute** → **your cluster** → **Edit** → **Advanced Options** → **Init Scripts**. 
    * Add the path of your `.sh` file in the cluster’s Init Scripts section.
4. **Restart**: Restart the cluster. The SDK will now find `mvp_profiler` automatically.

#### **Method 2: Cluster Environment Variables (Simpler Setup)**
1.  **Upload the Binary**: Upload `mvp_profiler` somewhere in your `/Workspace/Users/<email>/` folder.
2. **Make the Binary Executable (one‑time)**
    ```shell
    %sh
    chmod +x /Workspace/Users/<email>/mvp_profiler
    ```
3.  **Add to PATH**: In the Databricks UI, 
    * Go to **Compute** → **Cluster** → **Edit**
    * Expand **Advanced Options** → **Spark** → **Environment Variables**
    * Add: 
    ```bash
    PATH=$PATH:/Workspace/Users/<email>/
    ```
4.  **Restart**: Restart the cluster. 
5.  **Verify**: Run the following command in a notebook cell to confirm it is in the PATH.
    ```shell
    %sh
    which mvp_profiler
    ```

#### Option B: Manual Workspace Upload (Standard Users)
If you cannot modify the system path:
1. Obtain the **Linux version** of the `mvp_profiler` binary.
2. Upload it to your Databricks Workspace (e.g., in the same folder as your model).
3. Copy the **File Path** (e.g., `/Workspace/Users/<your-email>/mvp_profiler`).
4. You will provide this path manually in the notebook's profiling cell.

> Note: If you haven't installed the NPU Toolkit model profiler (mvp_profiler), you can download it from the official Silicon Labs [GitHub repository](https://github.com/SiliconLabsSoftware/aiml-extension/tree/main/tool/profiler).

### 3. Upload your Model
Ensure your compiled `.tflite` model is uploaded to your Databricks Workspace.
- Example Path: `/Workspace/Users/<your-email>/model.tflite`

---

## Notebook Configuration (Placeholders)

You must update the following placeholders in the notebook before running:

### Cell: Global Credentials Configuration
Update these with your specific Databricks and ZeroBus details:
- `<your-zerobus-endpoint>`: The URL of your ZeroBus server.
- `<your-workspace-url>`: Your Databricks Workspace URL (e.g., `https://adb-123.4.azuredatabricks.net`).
- `<catalog>.<schema>.<table_name>`: The target Delta table for your sensor data.
  > [!NOTE]
  > This table is primarily used for **data ingestion**. Since the SDK uses a unified configuration, this parameter is required, but it is **ignored** by the `model.profile()` function. If you haven't set up an ingestion table yet, you can pass `None` or use a placeholder name.
- `<your-client-id>`: Your Service Principal Client ID.
- `<your-client-secret>`: Your Service Principal Secret.

> For more details on how to get these credentials, see the [Databricks Setup Guide](databricks_setup_guide.md).

### Cell: Model Profiling
- `model_path`: The full path to your `.tflite` file in the Workspace.
- `volume_path`: The Unity Catalog Volume where results will be stored (e.g., `/Volumes/<catalog>/<schema>/<volume_name>`).
- `profiler_path`: The path to the `mvp_profiler` binary if using **Option B** above (e.g., `/Workspace/Users/<email>/mvp_profiler`).

### Cell: MLflow Integration
- `experiment_name`: The workspace **path** where you want your history stored (e.g., `/Users/<email>/my_profiling_exp`). 
  > [!TIP]
  > You are providing a **path**. If an experiment doesn't exist at this path, the notebook will **automatically create it** for you.
- `volume_path`: Must match the Volume path used in the profiling cell.

### Cell: Model Registration
you have to provide these in the cell(11-12) for registering your models in the UC Model registry
1. **Model File Path**: The exact location of the model you want to register (e.g., the `.h5` teacher model or `.tflite` student model).
2. **Unity Catalog Model Name**: The destination in Unity Catalog in the format `<catalog>.<schema>.<model_name>`.
3. **Registration Run Name**: A unique name for this registration activity in MLflow (e.g., "teacher_v1_registration").

For the model registry there are two models: teacher and student model. So, for both you have to provide the model file path and unity catalog model name and registration run name.

#### Register the teacher model artifact to UC

```python
teacher_v = register_single_file(
    "<path to>/model.teacher.h5", # path to the teacher model in Databricks workspace
    "<catalog>.<schema>.model_teacher", # name of the teacher model to register in UC
    "teacher_register" # name of the registration run
)
```
 
#### Register the student model artifact to UC

```python
student_v = register_single_file(
    "<path to>/model.tflite", # path to the student model in Databricks workspace
    "<catalog>.<schema>.model_student", # name of the student model to register in UC
    "student_register" # name of the registration run
)
```

### Cell: Upload Logs
- `<your-sql-warehouse-name>`: The name of your SQL Warehouse (found in the "SQL Warehouses" tab of Databricks).
- `<catalog>.<schema>.<table_name>`: The target table for your SDK action logs. For more information on log syncing, see the [Logs Guide](logs_guide.md).

---

## Running the Notebook

1. **Initialization**: Run the first two cells to restart the Python engine and install the `silabs-mlops` library.
2. **Configuration**: Execute the `data.config()` cell to authenticate.
3. **Execution**: Run the profiling cell. 
   - If successful, it will print hardware metrics (Arena size, MACs) and confirm the upload to your Volume.
4. **Tracking**: Run the MLflow cell to log these results. Click the **View Run** link to see beautiful charts and side-by-side comparisons in the MLflow UI.
5. **Registration**: If the model performance is acceptable, use the Registration cells to promote the model to the Unity Catalog Model Registry.
6. **Upload Logs**: Run the Upload Logs cell to sync the SDK action logs to Delta tables for auditing.   

---

## Detailed Model Registry Instructions

When registering a model, pay close attention to the **Unity Catalog Model Name**. This is the single most important detail:
- It must follow the three-level namespace: `catalog.schema.model_name`. 
- If you register a model with a name that already exists, Unity Catalog will automatically increment the **version number** (e.g., Version 1 -> Version 2). If you provided a new name it will create and register a new model with that name.

---

> Note: The `<user-email>` placeholder represents your Databricks workspace user email. Replace it with your actual email address when specifying Workspace paths such as `/Workspace/Users/<user-email>/model.tflite` or `/Workspace/Users/<user-email>/mvp_profiler`.
You can find your Databricks user email by clicking your profile icon in the top‑right corner of the Databricks workspace.

## Troubleshooting

- **File Not Found**: Ensure your `.tflite` model and `mvp_profiler` binary are uploaded to the correct paths in your Workspace.
- **Permission Denied**: Verify that your Service Principal has `USE CATALOG`, `USE SCHEMA`, and `WRITE VOLUME` permissions.
- **ZeroBus Errors**: Double-check your `server_endpoint` and `client_secret`.
- **Path Errors**: Ensure all Workspace paths start with `/Workspace/` or `/Users/` as appropriate.
- **Profiler Issues**: Remember to use the **Linux version** of the `mvp_profiler` binary, as Databricks clusters run on Linux.