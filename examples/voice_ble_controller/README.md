# Voice-Controlled BLE Device

A merged application that listens for voice commands ("on" / "off") using an on-board microphone and AI model, controls an LED based on the command, and sends the result to a connected phone over Bluetooth.

Built for the **EFR32MG26** (BRD2608A dev board) using **Simplicity SDK 2025.12.1** and **MicriumOS**.

---

## Table of Contents

- [What Does This Application Do?](#what-does-this-application-do)
- [How It Works (Step by Step)](#how-it-works-step-by-step)
- [Project Structure — Key Files](#project-structure--key-files)
- [How the Components Connect](#how-the-components-connect)
- [BLE Notification Payload](#ble-notification-payload)
- [BLE Service Details](#ble-service-details)
- [Where to Make Changes](#where-to-make-changes)
- [Testing](#testing)
- [Hardware Requirements](#hardware-requirements)
- [Build Information](#build-information)
- [Limitations](#limitations)
- [How to Rename This Project](#how-to-rename-this-project)
- [Origin](#origin)

---

## What Does This Application Do?

1. The device powers on and starts **advertising over Bluetooth** so your phone can find it.
2. You connect to it from a BLE scanner app (e.g., nRF Connect).
3. You **enable notifications** on the "Voice Result" characteristic.
4. The device starts **listening through its microphone**.
5. When you say **"on"**, the **LED turns on** and a notification is sent to your phone.
6. When you say **"off"**, the **LED turns off** and a notification is sent to your phone.
7. The LED **stays in its last state** until you say the opposite command.

---

## How It Works (Step by Step)

```
       You speak "on" or "off"
               |
               v
    [ Microphone captures audio ]
               |
               v
    [ Audio features are extracted ]
               |
               v
    [ AI model runs on the chip ]
               |
               v
    [ "on" detected? Turn LED on  ]
    [ "off" detected? Turn LED off ]
               |
               v
    [ Result sent to phone via BLE notification ]
```

### The Startup Sequence

1. **Board boots up** — temperature sensor and BLE stack are initialized.
2. **BLE advertising begins** — the device shows up as "Voice_BLE_Controller_Demo" on your phone.
3. **Phone connects** — a BLE connection is established.
4. **Phone enables notifications** on the Voice Result characteristic.
5. **Audio classifier starts** (after a short 2.5-second delay to keep BLE stable):
   - LEDs are initialized
   - MVP hardware accelerator is initialized (speeds up the AI model)
   - AI model is loaded into memory
   - Microphone and audio pipeline are initialized
   - A 1-second warm-up period passes
   - The inference loop begins (runs every 200 ms)

### The Inference Loop

Every 200 milliseconds, the device:
1. Captures a fresh audio sample from the microphone.
2. Converts it into audio features (a compact representation of the sound).
3. Feeds these features into the AI model.
4. The model outputs a confidence score for each word: "on", "off", and "unknown".
5. A smoothing algorithm checks if a confident new command was detected.
6. If yes — the LED is toggled and a BLE notification is sent.

---

## Project Structure — Key Files

| File | What it does |
|---|---|
| `app.c` | Main BLE application. Handles advertising, connections, notifications, and bridges voice events to BLE. |
| `app.h` | Public functions shared between the BLE app and the classifier. |
| `audio_classifier.cc` | The voice detection engine. Runs as its own background task. Listens to the microphone, runs the AI model, controls the LED, and publishes results. |
| `audio_classifier.h` | Public interface for the classifier (init function, label lookup). |
| `recognize_commands.cc` | Smoothing logic that decides if a word was really spoken (avoids false triggers). |
| `recognize_commands.h` | Header for the smoothing logic. |
| `config/audio_classifier_config.h` | **Main configuration file.** Detection thresholds, timing, LED assignment, task settings. |
| `config/btconf/gatt_configuration.btconf` | BLE service and characteristic definitions. |
| `config/sl_board_control_config.h` | Board-level settings (microphone enable, sensors). |
| `config/sl_mic_i2s_config.h` | Microphone pin assignments (USART0 on Port D). |
| `config/sl_driver_mvp_config.h` | MVP accelerator settings (power mode for RTOS). |
| `config/sl_tflite_micro_config.h` | AI model memory (tensor arena size = 100 KB). |
| `config/sl_simple_led_led0_config.h` | LED0 pin config (Port D, pin 7). |
| `config/sl_simple_led_led1_config.h` | LED1 pin config (Port A, pin 4) — this is the detection LED. |
| `cmake_gcc/CMakeLists.txt` | Build configuration. Lists all source files, include paths, and libraries. |
| `autogen/sl_simple_led_instances.c` | LED driver instances (auto-generated from config). |
| `autogen/sl_tflite_micro_model.c` | The AI model binary (auto-generated, do not edit). |

---

## How the Components Connect

```
+---------------------+       +------------------------+
|                     |       |                        |
|  BLE App (app.c)    |<----->|  Audio Classifier      |
|                     |       |  (audio_classifier.cc) |
|  - Advertising      |       |                        |
|  - Connection mgmt  |       |  - Microphone input    |
|  - GATT notify      |       |  - AI inference        |
|  - CLI commands      |       |  - LED control         |
|                     |       |                        |
+---------------------+       +------------------------+
        ^                              |
        |                              |
        |    ai_voice_result_publish() |
        +------------------------------+
        (classifier sends detected
         commands to BLE for notify)
```

### How they talk to each other:

- **Audio classifier** detects a word and calls `ai_voice_result_publish()`.
- **BLE app** receives this call, queues the event safely (using a mutex), and wakes up the BLE task.
- **BLE task** packages the result into an 8-byte payload and sends it as a BLE notification.
- They run as **separate tasks** managed by MicriumOS, so neither blocks the other.

---

## BLE Notification Payload

When a word is detected, your phone receives an 8-byte notification:

| Byte | Field | Description |
|---|---|---|
| 0 | Version | Always `1` (payload format version) |
| 1 | Class ID | `0` = "on", `1` = "off" |
| 2 | Score | Confidence (0–255, higher = more certain) |
| 3 | Flags | `1` = new command detected |
| 4–7 | Timestamp | Time in milliseconds since boot (little-endian) |

**Example:** `01 00 D1 01 58 42 00 00` means "on" was detected with confidence 209 at ~17 seconds after boot.

---

## BLE Service Details

| Item | Value |
|---|---|
| Device Name | SDC_For_Silabs |
| Voice Result Service UUID | `f7ee5e0c-1882-4c85-a6f1-8d6f81f10901` |
| Voice Result Characteristic UUID | `f7ee5e0c-1882-4c85-a6f1-8d6f81f10902` |
| Supported Operations | Read, Notify |

To receive voice events, you must **enable notifications** on the Voice Result characteristic after connecting.

---

## Where to Make Changes

### Change the voice commands (e.g., add "yes"/"no")

You need a different AI model trained for those words. Replace the model file and update `CATEGORY_LABELS` in:

```
config/audio_classifier_config.h
```

Then update the `handle_result()` function in `audio_classifier.cc` to act on the new class IDs.

### Change which LED is used

Edit this line in `config/audio_classifier_config.h`:

```c
#define DETECTION_LED sl_led_led1
```

Change `sl_led_led1` to `sl_led_led0` (or both). The pin assignments for each LED are in:
- `config/sl_simple_led_led0_config.h` (Port D, pin 7)
- `config/sl_simple_led_led1_config.h` (Port A, pin 4)

### Change detection sensitivity

In `config/audio_classifier_config.h`:

| Setting | What it does | Default |
|---|---|---|
| `DETECTION_THRESHOLD` | Minimum confidence to count as a detection (0–255) | 100 |
| `SMOOTHING_WINDOW_DURATION_MS` | How long to average results before deciding (ms) | 600 |
| `MINIMUM_DETECTION_COUNT` | How many inference cycles must agree | 3 |
| `SUPPRESSION_TIME_MS` | Cool-down after a detection before another is allowed (ms) | 1000 |

- If you get **too many false detections**: increase `DETECTION_THRESHOLD` (try 150 or 200).
- If the device **misses commands**: decrease `DETECTION_THRESHOLD` (try 80).
- If it **detects the same word twice**: increase `SUPPRESSION_TIME_MS` (try 1500).

### Change how often the device listens

In `config/audio_classifier_config.h`:

```c
#define INFERENCE_INTERVAL_MS 200
```

Lower = more responsive but uses more CPU. Higher = saves power but slower reaction. The model was designed for 200 ms intervals.

### Change the BLE device name

Edit the device name in `config/btconf/gatt_configuration.btconf`:

```xml
<value length="19" type="utf-8" variable_length="false">SDC_For_Silabs</value>
```

After changing, regenerate the GATT database files.

### Change the BLE notification payload format

Edit the `app_send_voice_result_payload()` function in `app.c`. The payload is built as a byte array — you can add or rearrange fields as needed.

### Add more actions on detection (e.g., control a motor, send data)

Add your code inside `handle_result()` in `audio_classifier.cc`. The `result` variable tells you which word was detected:
- `0` = "on"
- `1` = "off"
- `2` = unknown sound (ignored by default)

---

## Testing

### Using a BLE scanner app (nRF Connect)

1. Flash the firmware to the board.
2. Open nRF Connect on your phone and scan for "SDC_For_Silabs".
3. Connect to the device.
4. Find the Voice Result characteristic (UUID ending in `0902`).
5. Enable notifications (tap the bell/notify icon).
6. Say "on" or "off" near the microphone.
7. You should see the LED change and a notification appear on your phone.

### Using the CLI (serial terminal)

Connect a serial terminal (115200 baud) to the board's VCOM port. Available commands:

- `hello` — sends a test voice event over BLE (useful to verify the notification path without speaking).

### What to expect on the serial log

```
[I] Health thermometer initialized
[I] Audio classifier start deferred until voice notify enable
[I] Bluetooth stack booted: v11.0.0+...
[I] Started advertising
[I] Connection opened
[I] Voice result notify enabled
[I] Audio classifier ready (3 classes)
[I] on (score=209)
[I] off (score=243)
```

---

## Hardware Requirements

| Component | Detail |
|---|---|
| Board | BRD2608A (EFR32MG26B510F3200IM68) |
| Microphone | On-board I2S MEMS mic (USART0, Port D pins 3/4/5) |
| LED0 | Port D, pin 7 (active low) |
| LED1 | Port A, pin 4 (active low) — used as detection LED |
| VCOM | EUSART0, Port A (serial log output) |

---

## Build Information

| Item | Value |
|---|---|
| SDK | Simplicity SDK 2025.12.1 |
| RTOS | MicriumOS |
| AI Framework | TensorFlow Lite for Microcontrollers |
| Hardware Accelerator | MVP (Matrix Vector Processor) |
| AI Model | keyword_spotting_on_off_v2 (3 classes: on, off, unknown) |
| Binary Size | ~403 KB |
| Build System | CMake + GCC ARM |

---

## Limitations

1. **Only two voice commands are supported** — "on" and "off". To add more commands, you need a different AI model trained for those words.

2. **The device must be connected via BLE before voice detection starts.** The classifier only begins listening after a phone connects and enables notifications. This is intentional to save power and avoid BLE stability issues during heavy audio processing.

3. **Background noise affects accuracy.** The microphone picks up all sounds. In a noisy environment, you may get false detections or missed commands. Speaking clearly within 30–50 cm of the board gives the best results.

4. **One BLE connection at a time.** The device supports a single connected client. If the phone disconnects, the device goes back to advertising but the classifier keeps running.

5. **No persistent state.** The LED state and voice results are not saved. After a power cycle, the device starts fresh with the LED off.

6. **Temperature readings are independent.** The health thermometer feature from the original app still works alongside voice detection. It uses a separate BLE characteristic and does not interfere with voice functionality.

7. **Memory is tight.** The AI model's tensor arena uses 100 KB of RAM. Adding significantly more features (e.g., a larger model, more BLE services) may require careful memory budgeting.

8. **The AI model runs on the device, not in the cloud.** This means it works without internet, but the model is fixed at build time. Changing the recognized words requires rebuilding the firmware with a new model.

---

## How to Rename This Project

If you want to change the project name from `bt_soc_thermometer_micriumos` to something else (e.g., `voice_ble_controller`), follow these steps carefully. Use find-and-replace where noted.

### Files that must be changed (build will break otherwise)

| Step | What to do |
|---|---|
| 1 | **Rename the project folder** itself (e.g., `bt_soc_thermometer_micriumos/` to `voice_ble_controller/`) |
| 2 | **Rename `bt_soc_thermometer_micriumos.slcp`** to the new name and update `project_name` and `label` on lines 2–3 inside the file |
| 3 | **Rename `cmake_gcc/bt_soc_thermometer_micriumos.cmake`** to the new name (e.g., `voice_ble_controller.cmake`) |
| 4 | **In `cmake_gcc/CMakeLists.txt`** — find-and-replace all occurrences of the old name with the new name (~15 places: project name, include, add_executable, target_* calls, custom commands) |
| 5 | **In the renamed `.cmake` file** (step 3) — update the linker map file name on line 480 |
| 6 | **In `cmake_gcc/CMakePresets.json`** — update the target name and display names (3 places) |

### Files that should be changed (won't break the build, but keeps things tidy)

| Step | What to do |
|---|---|
| 7 | **`.vscode/settings.json`** — update the `cmake.sourceDirectory` path |
| 8 | **`README.md`** — update any mentions of the old project name |
| 9 | **`MERGE_READINESS_REPORT.md`** — update references to the old project name |

### After renaming

1. **Delete the `cmake_gcc/build/` folder entirely.** It contains cached paths with the old name and must be regenerated.
2. Rebuild the project from scratch.

### Do NOT change

- Files inside `autogen/` — these are auto-generated and will be regenerated
- Files inside `simplicity_sdk_2025.12.1/` — these are SDK files
- Files inside `cmake_gcc/build/` — just delete this folder and rebuild

---

## Origin

This application was created by merging two Silicon Labs example projects:

- **bt_soc_thermometer_micriumos** — BLE thermometer with MicriumOS (the base project)
- **aiml_soc_audio_classifier_efr32_micriumos** — AI audio keyword spotter (the source of voice/ML components)

The merge brought the audio capture pipeline, AI inference engine, and MVP hardware acceleration into the BLE project, allowing voice-detected commands to be transmitted over Bluetooth.
