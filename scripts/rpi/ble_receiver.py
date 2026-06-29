import os
import time
import asyncio
import struct
import wave

from sml.ops import ble

# ========================
# BLE Configuration
# ========================
# Set these to match your board's configuration
DEVICE_NAME = os.getenv("BLE_DEVICE_NAME", "<YOUR_DEVICE_NAME>")
DEVICE_ADDRESS = os.getenv("BLE_DEVICE_ADDRESS", "<YOUR_DEVICE_MAC_ADDRESS>")

# UUIDs from gatt_configuration.btconf
VOICE_RESULT_UUID = "f7ee5e0c-1882-4c85-a6f1-8d6f81f10902"
AUDIO_DATA_UUID = "f7ee5e0c-1882-4c85-a6f1-8d6f81f10903"

# Folder path where audio samples will be saved (Local Storage Path)
OUTPUT_DIR = os.getenv("AUDIO_SAMPLES_DIR", "/path/to/your/audio_samples")

# Audio parameters
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit

# Class Labels (Keywords)
_labels_env = os.getenv("BLE_LABELS")
LABELS = (
    _labels_env.split(",") if _labels_env else ["<keyword1>", "<keyword2>", "unknown"]
)

# --- Global state ---
audio_buffer = bytearray()
current_label = "detection"


def save_wav(data, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with wave.open(filepath, "wb") as wf:
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
    ble.config(
        device_name=DEVICE_NAME,
        device_address=DEVICE_ADDRESS,
        voice_result_uuid=VOICE_RESULT_UUID,
        audio_data_uuid=AUDIO_DATA_UUID,
        output_dir=OUTPUT_DIR,
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        sample_width=SAMPLE_WIDTH,
        labels=LABELS,
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
