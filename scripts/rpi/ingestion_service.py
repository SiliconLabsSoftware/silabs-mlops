import os

# ========================
# Databricks / ZeroBus Credentials
# ========================
# Update these with your own Databricks/ZeroBus credentials
os.environ["ZEROBUS_WORKSPACE_URL"] = "https://<your-workspace-url>.azuredatabricks.net"
os.environ["ZEROBUS_CLIENT_ID"] = "<your-service-principal-client-id>"
os.environ["ZEROBUS_CLIENT_SECRET"] = "<your-service-principal-client-secret>"

# ZeroBus Endpoint and Table
os.environ["ZEROBUS_SERVER_ENDPOINT"] = "<your-workspace-id>.zerobus.<region>.azuredatabricks.net"
os.environ["ZEROBUS_TABLE_NAME"] = "<catalog>.<schema>.<table_name>"

# Databricks Volume Path (Example: "/Volumes/main/default/audio_data")
os.environ["DATABRICKS_VOLUME_PATH"] = "/Volumes/<catalog>/<schema>/<volume>"

# Local directory to monitor (Must match ble_receiver.py)
os.environ["AUDIO_SAMPLES_DIR"] = "/path/to/your/audio_samples"

# ========================
# Run the Ingestor
# ========================
# Option 1: Standard Ingestion (Processes & uploads one file at a time)
import sequential_ingestion_engine

# Option 2: High-Volume Simultaneous Ingestion (Processes & uploads multiple files at once)
# (Uncomment the line below and comment Option 1 to enable parallel uploading)
# import batch_ingestion_engine as sequential_ingestion_engine

if __name__ == "__main__":
    sequential_ingestion_engine.main()
