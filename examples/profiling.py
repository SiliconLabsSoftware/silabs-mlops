"""
Silicon Labs NPU Model Profiling
------------------------------------------------
This shows you how to use the 'model' module to profile
TFLite models for Silicon Labs hardware.

IMPORTANT:
Before running ANY profiling commands, you MUST configure
your Databricks/ZeroBus credentials ONCE using data.config().

Example:

    from silabs_mlops import data
    data.config(
        server_endpoint="your-endpoint.cloud.databricks.com",
        workspace_url="https://your-workspace.cloud.databricks.com",
        table_name="catalog.schema.table_name",     # Not used by profiler
        client_id="your-client-id",
        client_secret="your-client-secret"
    )

If you ALREADY called data.config() earlier (e.g., during ingestion),
you do NOT need to call it again.

The model.profile() function will automatically use those credentials
for:
    ✓ Uploading profiling results to Databricks Volumes
    ✓ Uploading history.log files
    ✓ Logging profiling sessions to the global logger


"""

from silabs_mlops import model

# 1. Basic Path Setup
# Change this to your actual .tflite model path
model_path = "workspace/outputs/my_model.tflite" 

# =========================================================
# USE CASE A: Local Simulation & Cloud Upload
# =========================================================
'''
Use this when you want to run model profiling on your PC 
and upload all metrics, logic, and error history directly 
to Databricks Volumes instead of saving them locally.

MAKE SURE you have the mvp_profiler.exe in your PATH if you are running on Windows.
& mvp_profiler(linux version) in databricks notebook PATH if you are running on databricks notebook.
'''
print("\n--- [A] Local Simulation & Cloud Upload ---")
try:
    result = model.profile(
        model_path=model_path,
        use_simulator=True,          # RUN LOCALLY ON PC
        volume_path="/Volumes/my_catalog/my_schema/profiling_results" #-> add your volume path here
    )
    # The result object contains all the extracted data:
    print(f"  ✓ Model:         {result.model_name}")
    print(f"  ✓ Arena Size:    {result.arena_size_kb:.1f} KB")
    print(f"  ✓ Total MACs:    {result.total_macs:,}")
    print(f"  ✓ Remote Folder: {result.output_dir}")
    print(f"  ✓ History Log:   {result.history_log_path}")
except Exception as e:
    # If there is a failure, the script will crash here
    # but the history.log will STILL upload to the volume path.
    print(f"  [!] Profiling failed -> {e}")

