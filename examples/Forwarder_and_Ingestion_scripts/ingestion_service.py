import os
import sys

# ========================
# Databricks / ZeroBus Credentials
# Provide your own credentials below
# ========================
os.environ["ZEROBUS_WORKSPACE_URL"] = "https://<your-workspace-url>.azuredatabricks.net"
os.environ["ZEROBUS_CLIENT_ID"] = "<your-service-principal-client-id>"
os.environ["ZEROBUS_CLIENT_SECRET"] = "<your-service-principal-client-secret>"
os.environ["ZEROBUS_SERVER_ENDPOINT"] = "<your-workspace-id>.zerobus.<region>.azuredatabricks.net"
os.environ["ZEROBUS_TABLE_NAME"] = "<catalog>.<schema>.<table_name>"

# Databricks Volume Path
# Provide your UC Volume path. Example: "/Volumes/main/default/audio_data"
os.environ["DATABRICKS_VOLUME_PATH"] = "/Volumes/<catalog>/<schema>/<volume>"

# ========================
# Run the Ingestor
# ========================
import examples.Forwarder_and_Ingestion_scripts.ingestion_engine as ingestion_engine

# Force gTTS mode (real speech)
sys.argv.append("--synth-mode")
sys.argv.append("gTTS")

# Optional defaults (you can omit these if CLI already provides them)
sys.argv.append("--labels")
sys.argv.append("left,right,on,off,stop,go")

sys.argv.append("--device-pool-size")
sys.argv.append("5")

sys.argv.append("--interval-sec")
sys.argv.append("1")

# Start Ingestion
ingestion_engine.main()