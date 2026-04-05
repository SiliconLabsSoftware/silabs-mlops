import os

# ========================
# Databricks / ZeroBus Credentials
# ========================
# Update these with your own Databricks/ZeroBus credentials

# ZeroBus Ingestion Configuration
DATABRICKS_VOLUME_PATH = "/Volumes/mlops_dev/default/audio_raw"
ZEROBUS_SERVER_ENDPOINT = "7405615984054316.zerobus.southcentralus.azuredatabricks.net"
ZEROBUS_WORKSPACE_URL = "https://adb-7405615984054316.16.azuredatabricks.net"
ZEROBUS_TABLE_NAME = "mlops_dev.default.stream_audio_metadata"
ZEROBUS_CLIENT_ID = "2cf06ebd-b4ad-40f8-91be-74e576e147f5"
ZEROBUS_CLIENT_SECRET = "dose3ecfb65d12bdc5a1a8d228e140e34883"


os.environ["DATABRICKS_VOLUME_PATH"] = DATABRICKS_VOLUME_PATH
os.environ["ZEROBUS_SERVER_ENDPOINT"] = ZEROBUS_SERVER_ENDPOINT
os.environ["ZEROBUS_WORKSPACE_URL"] = ZEROBUS_WORKSPACE_URL
os.environ["ZEROBUS_TABLE_NAME"] = ZEROBUS_TABLE_NAME
os.environ["ZEROBUS_CLIENT_ID"] = ZEROBUS_CLIENT_ID
os.environ["ZEROBUS_CLIENT_SECRET"] = ZEROBUS_CLIENT_SECRET

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

