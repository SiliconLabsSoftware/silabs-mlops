"""
Simple Usage Examples - SiLabs MLOps Data Library
"""
from silabs_mlops import data

# =============================================================================
# Example 1: Basic Usage - Configure and Ingest
# =============================================================================

# Step 1: Configure your Databricks credentials (once at startup)
data.config(
    server_endpoint="your-workspace-id.zerobus.us-west-2.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="your_catalog.your_schema.your_table",
    client_id="your-client-id",
    client_secret="your-client-secret"
)

# Step 2: Ingest your sensor data (can do this many times)
sensor_data = [
    {"device_id": "sensor-1", "temperature": 22.5, "humidity": 55},
    {"device_id": "sensor-2", "temperature": 23.1, "humidity": 60},
    {"device_id": "sensor-3", "temperature": 21.8, "humidity": 58}
]

success = data.ingest(sensor_data)

if success:
    print("✓ Data sent to Databricks successfully!")
else:
    print("✗ Failed to send data")


# =============================================================================
# Example 2: Ingest from a JSON File
# =============================================================================

# Ingest from file (uses the same configuration from above)
success = data.ingest_from_file("test_sensor_data.json")

if success:
    print("✓ File data sent to Databricks successfully!")


# =============================================================================
# Example 3: Real IoT Workflow - Continuous Data Collection
# =============================================================================

import time

# Configure once at application startup
data.config(
    server_endpoint="your-workspace-id.zerobus.us-west-2.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="your_catalog.your_schema.iot_data",
    client_id="your-client-id",
    client_secret="your-client-secret"
)

def collect_sensor_readings():
    """User's own sensor collection logic"""
    return [
        {"device_id": "temp-sensor-1", "temperature": 22.5, "timestamp": time.time()},
        {"device_id": "humidity-sensor-1", "humidity": 55, "timestamp": time.time()}
    ]

# Continuous data collection loop
for i in range(3):
    print(f"\n--- Reading {i+1} ---")
    
    # Collect data from sensors
    readings = collect_sensor_readings()
    
    # Send to Databricks
    success = data.ingest(readings)
    
    if success:
        print(f"✓ Batch {i+1} sent to Databricks!")
    else:
        print(f"✗ Batch {i+1} failed")
    
    time.sleep(2)  # Wait before next reading
    

# =============================================================================
# Example 4: Combined File & Metadata Ingestion
# =============================================================================

# This uploads a local file to a Databricks Volume and sends its metadata 
# to a Delta Table in one step.

# 1. Configure Credentials 
data.config(
    server_endpoint="your-zerobus-endpoint.cloud.databricks.com",
    workspace_url="https://your-workspace.cloud.databricks.com",
    table_name="catalog.schema.audio_events",
    client_id="your-client-id",
    client_secret="your-client-secret"
)

# 2. Prepare Metadata
# IMPORTANT: You must manually create your Databricks Delta Table before 
# running this. The SDK automatically adds 'file_path' and 'ingest_ts' 
# to your metadata, so your table schema MUST include these columns.
#
# Example SQL:
# CREATE TABLE <catalog>.<schema>.<table_name> (
#   device_id STRING, class_label STRING, version STRING,
#   file_path STRING, ingest_ts TIMESTAMP
# ) USING DELTA;

metadata = {
    "device_id": "gateway-01",
    "class_label": "keyword_detected",
    "version": "1.0"
}

# The SDK automatically adds 'file_path' and 'ingest_ts' to the metadata.
success = data.file_ingest(
    file_path="local_sample.wav",                             # Local file path where the audio file is stored
    volume_path="/Volumes/<catalog>/<schema>/<volume>/sample.wav", # Destination Volume path where the audio file will be stored
    metadata=metadata                                          # Metadata dictionary
)

if success:
    print("✓ File and metadata ingested successfully!")
