import struct
import time
import numpy as np
from bleak import BleakClient, BleakScanner

# --- Configuration ---
DEVICE_NAME = "<YOUR_DEVICE_NAME>" # e.g., "Voice_BLE_Controller_Demo"
DEVICE_ADDRESS = "<YOUR_DEVICE_ADDRESS>" # e.g., "1C:C0:89:2D:30:45"

# Folder path to store audio samples
OUTPUT_DIR = r"<PATH_TO_OUTPUT_DIR>" # e.g., "C:/audio samples"

# UUIDs from gatt_configuration.btconf
VOICE_RESULT_UUID = "f7ee5e0c-1882-4c85-a6f1-8d6f81f10902"
AUDIO_DATA_UUID = "f7ee5e0c-1882-4c85-a6f1-8d6f81f10903"

# Audio parameters
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2 # 16-bit

# --- Global state ---
audio_buffer = bytearray()
current_label = "detection"

def save_wav(data, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(data)
    print(f"Saved: {filename} ({len(data)} bytes)")

async def notification_handler(sender, data):
    global audio_buffer, current_label
    
    if sender.uuid.lower() == AUDIO_DATA_UUID.lower():
        audio_buffer.extend(data)
        if len(audio_buffer) >= 32000:
            final_data = audio_buffer[:32000]
            label_to_save = current_label

            # Filename format: label_address_name_timestamp.wav
            addr_str = DEVICE_ADDRESS.replace(":", "").replace("-", "")
            name_str = DEVICE_NAME.replace(" ", "-")
            filename = f"{label_to_save}_{addr_str}_{name_str}_{int(time.time())}.wav"
            save_wav(final_data, filename)
            audio_buffer = bytearray()
            print("--- Ready for next detection ---")

    elif sender.uuid.lower() == VOICE_RESULT_UUID.lower():
        ver, class_id, score, flags, ts = struct.unpack("<BBBB I", data)
        # CHANGE HERE: Ensure this list matches the firmware's class IDs in audio_classifier_config.h
        labels = ["on", "off", "unknown"]
        current_label = labels[class_id] if class_id < len(labels) else "unknown"
        print(f"\n[EVENT] Firmware Detected: {current_label.upper()} (Score: {score})")
        audio_buffer = bytearray() 

async def main():
    print(f"Scanning for {DEVICE_NAME}...")
    device = await BleakScanner.find_device_by_address(DEVICE_ADDRESS, timeout=10.0)
    if not device:
        device = await BleakScanner.find_device_by_filter(lambda d, ad: d.name == DEVICE_NAME, timeout=10.0)
    if not device:
        print("Could not find device.")
        return

    async with BleakClient(device) as client:
        print(f"Connected to {device.name}")
        await client.start_notify(VOICE_RESULT_UUID, notification_handler)
        await client.start_notify(AUDIO_DATA_UUID, notification_handler)
        print("\n--- Subscribed to Voice Events ---")
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping...")
