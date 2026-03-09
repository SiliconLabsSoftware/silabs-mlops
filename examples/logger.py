"""
Silicon Labs MLOps - Logger Capabilities Showcase
Demonstrates viewing CLI history, syncing offline logs, and creating custom tracking events.
"""

from silabs_mlops.logs import Logger

# =========================================================
# 1. INITIALIZATION
# =========================================================
# The Logger automatically pulls the Workspace URL, Client ID, and Secret 
# directly from your CLI configuration (.env file or Databricks environment).
# You only need to optionally provide the destination Delta table.
logger = Logger(
    warehouse_name="Serverless Starter Warehouse", 
    table_name="mlops_dev.default.my_custom_logs" 
)


# =========================================================
# 2. VIEWING LOCAL HISTORY
# =========================================================
# View a beautifully formatted ASCII table of the last 50 actions on your PC.
print("--- Viewing Global Local History ---")
logger.view()

# You can also filter the table to see only specific types of actions:
# Valid built-in event types: "Profiling", "Deployment", "Data Ingestion"
print("\n--- Viewing Profiling Logs ---")
logger.view(event_type="Profiling")

print("\n--- Viewing Deployment Logs ---")
logger.view(event_type="Deployment")

print("\n--- Viewing Data Ingestion Logs ---")
logger.view(event_type="Data Ingestion")


# =========================================================
# 3. OFFLINE SYNCING (Fallback)
# =========================================================
# If you were working offline on an airplane or without Wi-Fi, the logger
# safely stored all your actions in `~/.silabs_mlops/logs.json`.
# You can run `sync_to_databricks` to bulk upload them all at once!
print("\n--- Syncing Offline Logs to Databricks ---")
# logger.sync_to_databricks() 
print("Uncomment `logger.sync_to_databricks()` to push offline logs.\n")


# =========================================================
# 4. LOGGING CUSTOM EVENTS (For Developers)
# =========================================================
# You can record any custom event from your scripts using `log_event()`.
# If `table_name` is set, this immediately streams to your Databricks Delta Table.
print("--- Logging Custom Events ---")
logger.log_event(
    type="System Calibration", 
    level="Info", 
    message="Initiating custom edge device calibration loop...", 
    source="User Script"
)
print("Logged custom calibration start event.\n")


# =========================================================
# 5. USING BUILT-IN HELPERS (For Developers)
# =========================================================
# If you are writing a script that wraps core CLI functionality, 
# you can use the built-in MLOps categories to keep your logs standardized.
logger.log_model_profiling("Completed mock loop of local profiling.")
logger.log_model_deployment("Successfully mocked flashing to board 123.", level="Success")
