# BLE Module – User Guide

The Silicon Labs MLOps SDK's `ble` library provides a high-level API for connecting to Silicon Labs edge devices via Bluetooth Low Energy (BLE), receiving audio streams, and handling voice detection events.

> A ready-to-use example script is provided at `examples/Data_forwarder_and_ingestion/ble_receiver.py`. You can copy and edit this script directly for your project.

---

## 1. Global Configuration with `ble.config()`

The first step is always to call `ble.config()`. This stores your hardware settings globally so that the `BLEReceiver` can automatically use them without having to pass any arguments.

### Parameters Reference

| Parameter | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `device_name` | Yes | — | The Bluetooth name your board broadcasts (visible in BLE scanners). |
| `device_address` | Yes | — | The board's MAC address (e.g., `AA:BB:CC:DD:EE:FF`). Ensures faster, reliable connection. |
| `voice_result_uuid` | Yes | — | GATT UUID of the characteristic that sends 8-byte detection result packets (your metadata UUID). |
| `audio_data_uuid` | Yes | — | GATT UUID of the characteristic that streams raw audio bytes. |
| `output_dir` | Yes | — | Local folder where the script will save recorded `.wav` files. |
| `labels` | Yes | — | List of keyword strings mapped to firmware Class IDs in order. |
| `sample_rate` | Optional | `16000` | Sampling frequency of your firmware in Hz. |
| `channels` | Optional | `1` | Audio channels. `1` = Mono, `2` = Stereo. |
| `sample_width` | Optional | `2` | Bytes per audio sample. `2` = 16-bit audio. |
| `buffer_size` | Optional | `32000` | Total raw bytes to collect per recording before saving. |

> If you do not pass the optional parameters, the default values will be used automatically. These defaults match the most common SiLabs keyword spotting firmware configuration.

> **Where to find UUIDs?**: Open your Simplicity Studio project and look in `gatt_configuration.btconf`. Each characteristic will have a UUID listed there.

---

## 2. Ways to Provide Configuration

You have **two options** to provide your board's details to `ble.config()`:

### Option A – Use Environment Variables (Recommended)

Set your board's details as OS environment variables before running the script. This keeps credentials out of your code and is the most secure approach.

**On your Raspberry Pi terminal:**
```bash
export BLE_DEVICE_NAME="<YOUR_DEVICE_NAME>"
export BLE_DEVICE_ADDRESS="<YOUR_MAC_ADDRESS>"
export BLE_RESULT_UUID="<YOUR_VOICE_RESULT_UUID>"
export BLE_DATA_UUID="<YOUR_AUDIO_DATA_UUID>"
export AUDIO_SAMPLES_DIR="<YOUR_LOCAL_PATH>"
export BLE_SAMPLE_RATE=<YOUR_SAMPLE_RATE>
export BLE_CHANNELS=<YOUR_CHANNELS>
export BLE_SAMPLE_WIDTH=<YOUR_SAMPLE_WIDTH>
export BLE_LABELS="<keyword1>,<keyword2>,unknown"
```

**In your script, they are read automatically:**
```python
import os
from silabs_mlops import ble

ble.config(
    device_name=os.getenv("BLE_DEVICE_NAME"),
    device_address=os.getenv("BLE_DEVICE_ADDRESS"),
    voice_result_uuid=os.getenv("BLE_RESULT_UUID"),   #<- metadata UUID
    audio_data_uuid=os.getenv("BLE_DATA_UUID"),
    output_dir=os.getenv("AUDIO_SAMPLES_DIR"),
    sample_rate=os.getenv("BLE_SAMPLE_RATE", 16000),  # <- (optional) replace these values with your own values
    channels=os.getenv("BLE_CHANNELS", 1),              # <- (optional) replace these values with your own values
    sample_width=os.getenv("BLE_SAMPLE_WIDTH", 2),      # <- (optional) replace these values with your own values
    labels=os.getenv("BLE_LABELS", "on,off,unknown").split(","),
    buffer_size=os.getenv("BLE_BUFFER_SIZE", 32000)     # <- (optional) replace these values with your own values
)
```

### Option B – Provide Values Directly in the Script

The simplest approach for testing. You can type your values directly into the `ble.config()` call:

```python
from silabs_mlops import ble

ble.config(
    device_name="<YOUR_DEVICE_NAME>",
    device_address="<YOUR_MAC_ADDRESS>",
    voice_result_uuid="<YOUR_VOICE_RESULT_UUID>",
    audio_data_uuid="<YOUR_AUDIO_DATA_UUID>",
    output_dir="<YOUR_LOCAL_PATH>",
    sample_rate=16000,     # Optional: change to match your firmware
    channels=1,            # Optional: 1 = Mono (default)
    sample_width=2,        # Optional: 2 = 16-bit (default)
    labels=["on", "off", "unknown"]
)
```

### How the Example Script Combines Both Options
The example script at `examples/Data_forwarder_and_ingestion/ble_receiver.py` uses `os.getenv("VAR", "default")` which gives you both options at once:
```python
# If the environment variable is already set on your system, it uses that value.
# If not, it falls back to the value you type between the quotes.
DEVICE_NAME = os.getenv("BLE_DEVICE_NAME", "<YOUR_DEVICE_NAME>")
```

---

## 3. Class Labels

The `labels` list is the most critical configuration step. Every Silicon Labs keyword spotting firmware assigns an integer **Class ID** (0, 1, 2...) to each keyword it can detect. The `labels` list is your way of telling the SDK what each Class ID means in plain English.

> **How to find your keywords**: The firmware your board runs assigns an integer **Class ID** (0, 1, 2...) to each keyword it was trained to detect. Check your Simplicity Studio project's class or label definitions to see which Class ID corresponds to which keyword (check for files like eg., ` audio_classifier_config.h` or `app_voice.h` to see your keyword order). The order and names there is exactly what your `labels` list must mirror. If you add new keywords in the future by retraining the model, simply update this list to match. 

You can provide labels in **two ways**:

**Option A – Environment Variable** (comma-separated, no spaces):
```bash
export BLE_LABELS="on,off,unknown"
```

**Option B – Directly in the script**:
```python
# Class 0 = "on", Class 1 = "off", Class 2 = "unknown"
LABELS = ["on", "off", "unknown"]
```

If you retrain or change your model with new keywords, simply update your labels to match the new firmware. You do **not** need to change any other part of the pipeline.

---

## 4. Using BLEReceiver

Once `ble.config()` is called, the `BLEReceiver` class handles all Bluetooth communication automatically. The example script at `examples/Data_forwarder_and_ingestion/ble_receiver.py` shows the full recommended usage:

```python
import asyncio
from silabs_mlops import ble

async def main():
    ble.config(
        device_name="<YOUR_DEVICE_NAME>",
        device_address="<YOUR_MAC_ADDRESS>",
        voice_result_uuid="<YOUR_VOICE_RESULT_UUID>",
        audio_data_uuid="<YOUR_AUDIO_DATA_UUID>",
        output_dir="<YOUR_LOCAL_PATH>",
        sample_rate=16000,
        labels=["on", "off", "unknown"]
    )

    # BLEReceiver automatically uses the global config above
    receiver = ble.BLEReceiver()
    await receiver.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### What Happens Internally:
1. The receiver scans for your board by its `device_name`.
2. Once connected, it subscribes to both GATT characteristics (voice result and audio data).
3. When the board's on-device AI detects a keyword, it sends an 8-byte packet. The SDK decodes it and maps the Class ID to your `labels` list.
4. The raw audio bytes that follow are collected and saved as a `.wav` file in your `output_dir`.

### Saved File Format
Files are saved as:
```
{label}_{unix_timestamp}.wav
```
For example: `on_1711584000.wav`

The `.wav` header is automatically stamped with your configured `sample_rate`, `channels`, and `sample_width`, so any audio player will read it correctly.
