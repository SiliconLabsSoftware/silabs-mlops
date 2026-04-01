import os
import asyncio

# ========================
# BLE Configuration
# ========================
# Set these to match your board's configuration
DEVICE_NAME = os.getenv("BLE_DEVICE_NAME", "<YOUR_DEVICE_NAME>")
DEVICE_ADDRESS = os.getenv("BLE_DEVICE_ADDRESS", "<YOUR_DEVICE_MAC_ADDRESS>")

# UUIDs from gatt_configuration.btconf
VOICE_RESULT_UUID = os.getenv("BLE_RESULT_UUID", "<YOUR_VOICE_RESULT_UUID>")
AUDIO_DATA_UUID = os.getenv("BLE_DATA_UUID", "<YOUR_AUDIO_DATA_UUID>")

# Folder path where audio samples will be saved (Local Storage Path)
OUTPUT_DIR = os.getenv("AUDIO_SAMPLES_DIR", "/path/to/your/audio_samples")

# Audio parameters (Matches firmware settings)
SAMPLE_RATE = os.getenv("BLE_SAMPLE_RATE", 16000)
CHANNELS = os.getenv("BLE_CHANNELS", 1)
SAMPLE_WIDTH = os.getenv("BLE_SAMPLE_WIDTH", 2)

# Class Labels (Keywords)
_labels_env = os.getenv("BLE_LABELS")
LABELS = _labels_env.split(",") if _labels_env else ["<keyword1>", "<keyword2>", "unknown"]

# ========================
# BLE Receiver Loop
# ========================
from sml.ops import ble   

async def main():
    ble.config(
        device_name=DEVICE_NAME,
        device_address=DEVICE_ADDRESS,
        voice_result_uuid=VOICE_RESULT_UUID,
        audio_data_uuid=AUDIO_DATA_UUID,
        output_dir=OUTPUT_DIR,
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        sample_width=SAMPLE_WIDTH,
        labels=LABELS
    )

    receiver = ble.BLEReceiver()
    
    try:
        await receiver.start()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping...")