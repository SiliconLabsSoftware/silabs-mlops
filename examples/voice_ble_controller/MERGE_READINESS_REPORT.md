# Merge Readiness Report — Voice over BLE

**Goal:** Transform the `bt_soc_thermometer_micriumos` BLE thermometer example into a voice-controlled BLE application that listens for "on"/"off" commands via microphone, controls an LED, and sends detection results to a connected phone over Bluetooth.

**Source projects:**
- **Base:** `bt_soc_thermometer_micriumos` (BLE thermometer with MicriumOS)
- **Ported from:** `aiml_soc_audio_classifier_efr32_micriumos` (AI audio keyword spotter)

**Target:** EFR32MG26B510F3200IM68 + BRD2608A, Simplicity SDK 2025.12.1, MicriumOS

---

## Table of Contents

- [1) Complete Changelog — Every Change Made](#1-complete-changelog--every-change-made)
- [2) Original vs Final Application](#2-original-vs-final-application)
- [3) Architecture Overview](#3-architecture-overview)
- [4) Debug Findings & Fixes](#4-debug-findings--fixes)
- [5) Phase-by-Phase Summary](#5-phase-by-phase-summary)
- [6) Current Runtime Configuration](#6-current-runtime-configuration)
- [7) Verified Behavior](#7-verified-behavior)
- [8) Known Limitations](#8-known-limitations)

---

## 1) Complete Changelog — Every Change Made

Below is every file that was created, modified, or copied — from the untouched BLE thermometer example to the final voice-over-BLE application.

### New Files Created (did not exist in the original project)

| File | Purpose |
|---|---|
| `audio_classifier.cc` | Voice detection engine. Runs as a MicriumOS background task. Initializes MVP, TFLM, microphone, and runs the inference loop. Controls the LED and publishes results via `ai_voice_result_publish()`. |
| `audio_classifier.h` | Public interface for the classifier — declares `audio_classifier_init()` and `get_category_label()`. |
| `recognize_commands.cc` | Smoothing algorithm that takes raw model scores and decides if a word was really spoken. Prevents false triggers by requiring sustained confidence over multiple inference cycles. Copied from AIML project. |
| `recognize_commands.h` | Header for the smoothing algorithm — declares `RecognizeCommands` class and `PreviousResultsQueue`. Copied from AIML project. |
| `config/audio_classifier_config.h` | Central configuration for the voice engine — detection threshold, inference interval, task priority, stack size, LED assignment, category labels. |
| `README.md` | Application documentation — flow, components, how to change settings, limitations, rename guide. |

### Config Files Copied from AIML Project

These files were copied from `aiml_soc_audio_classifier_efr32_micriumos/config/` into the BLE project's `config/` folder because the BLE project did not have them:

| File | What it configures |
|---|---|
| `config/sl_mic_i2s_config.h` | Microphone I2S pin assignments — USART0 on Port D (PD3=CLK, PD4=RX, PD5=CS) |
| `config/sl_tflite_micro_config.h` | TensorFlow Lite Micro settings — tensor arena size (100 KB), debug logging |
| `config/sl_nn_mvp_config.h` | MVP neural network optimizations — enables faster inference |
| `config/sl_driver_mvp_config.h` | MVP driver behavior — DMA channel, power mode. **Modified:** changed `SL_MVP_POWER_MODE` from `0` to `2` (yield RTOS thread) so MVP doesn't block BLE |
| `config/sl_simple_led_led0_config.h` | LED0 pin config — Port D, pin 7, active low |
| `config/sl_simple_led_led1_config.h` | LED1 pin config — Port A, pin 4, active low (used as detection LED) |

### Autogen Files Copied from AIML Project

| File | What it provides |
|---|---|
| `autogen/sl_simple_led_instances.c` | LED driver instances — creates `sl_led_led0` and `sl_led_led1` objects with init/on/off/toggle functions |
| `autogen/sl_simple_led_instances.h` | Header declaring the LED instances. **Modified:** added `extern "C"` guards so it can be included from C++ files without linker errors |

### Existing Files Modified

#### `app.c` — Main BLE Application

The original file only handled BLE advertising, connection, and temperature indications. The following was added:

| Change | Detail |
|---|---|
| Added `#include "audio_classifier.h"` | To call the classifier init function |
| Added `APP_ENABLE_AUDIO_CLASSIFIER` flag | Master switch to enable/disable the voice feature |
| Added voice result service handling | CCCD enable/disable logic for the `voice_result` characteristic in `sl_bt_on_event()` |
| Added deferred classifier start | When notifications are enabled, a 2.5-second timer starts. After the timer fires, `audio_classifier_init()` is called from task context (not from BLE callback). This prevents BLE instability. |
| Added `voice_result_publish()` | Queues a voice event using a mutex, wakes the app task via `app_proceed()` |
| Added `ai_voice_result_publish()` | Bridge function that the classifier calls — forwards to `voice_result_publish()` |
| Added `app_send_voice_result_payload()` | Builds the 8-byte notification payload and calls `sl_bt_gatt_server_send_notification()` |
| Added event queue in `app_process_action()` | Checks for pending voice events, acquires mutex, sends the notification from task context |
| Added `voice_result_set_dummy_mode()` | For testing — can generate fake periodic voice events without the mic |
| Added `voice_result_publish_test_event()` | Used by the CLI `hello` command to send a test event |
| Added disconnect cleanup | Stops timers, clears pending events, resets notification state on disconnect |

#### `app.h` — Application Interface

The original file only declared `app_init_bt()`. The following was added:

| Change | Detail |
|---|---|
| Added `extern "C"` guards | So the header works when included from C++ (audio_classifier.cc) |
| Added `app_proceed()` declaration | Wake the app task |
| Added `app_is_process_required()` declaration | Check if app task has work |
| Added `app_mutex_acquire()` / `app_mutex_release()` | Thread-safe access to shared voice event state |
| Added `voice_result_publish()` | Queue a voice event for BLE send |
| Added `ai_voice_result_publish()` | Bridge for the classifier |
| Added `voice_result_set_dummy_mode()` | Enable/disable test mode |
| Added `voice_result_publish_test_event()` | CLI test helper |

#### `config/btconf/gatt_configuration.btconf` — BLE GATT Database

| Change | Detail |
|---|---|
| Changed device name | From `"Thermometer Example"` to `"SDC_For_Silabs"` |
| Added Voice Result Service | Custom service with UUID `f7ee5e0c-1882-4c85-a6f1-8d6f81f10901` |
| Added Voice Result Characteristic | UUID `f7ee5e0c-1882-4c85-a6f1-8d6f81f10902`, 8 bytes, read + notify. Payload: version, class_id, score, flags, timestamp_ms |

#### `config/sl_board_control_config.h` — Board Peripherals

| Change | Detail |
|---|---|
| `SL_BOARD_ENABLE_SENSOR_MICROPHONE` | Changed from `0` to `1` — powers on the on-board MEMS microphone |

#### `cmake_gcc/CMakeLists.txt` — Build Configuration

This is where the bulk of the integration work happened. The original file only included the base BLE project cmake. Everything below was added:

| Category | What was added |
|---|---|
| **Path variables** | `AIML_APP_DIR` and `AIML_PKG_DIR` pointing to the AIML project and its SDK package |
| **Application sources** | `audio_classifier.cc`, `recognize_commands.cc` |
| **TFLM model** | `sl_tflite_micro_model.c` from AIML autogen |
| **Microfrontend sources** | 17 audio preprocessing files (filterbank, FFT, noise reduction, log scale, etc.) |
| **TFLM runtime** | `sl_tflite_micro_init.cc`, `sl_ml_audio_feature_generation.c`, `sl_ml_audio_feature_generation_init.c`, `debug_log.cc` |
| **MVP-accelerated TFLM kernels** | 7 files: `add.cc`, `conv.cc`, `depthwise_conv.cc`, `fully_connected.cc`, `mul.cc`, `pooling.cc`, `transpose_conv.cc` |
| **CMSIS-NN TFLM kernels** | 3 files: `softmax.cc`, `svdf.cc`, `unidirectional_sequence_lstm.cc` |
| **MVP driver** | 4 files: `sl_mvp.c`, `sl_mvp_hal_efr32.c`, `sl_mvp_program_area.c`, `sl_mvp_util.c` |
| **MVP math** | 22 files: vector/matrix operations (add, mult, scale, dot product, etc.) |
| **MVP neural network** | 9 files: `sl_mvp_ml_conv2d.c`, `sl_mvp_ml_fully_connected.c`, `sl_mvp_ml_pooling.c`, etc. |
| **Board drivers** | `sl_mic_i2s.c` (microphone), `sl_hal_usart.c`, `em_usart.c` (USART peripheral) |
| **LED driver** | `sl_led.c`, `sl_simple_led.c`, `sl_simple_led_instances.c` |
| **Include directories** | 14 paths added — AIML autogen/config, microfrontend, TFLM headers, flatbuffers, CMSIS-DSP/NN, MVP driver/math/nn/util, mic driver, USART/EMLIB, LED driver |
| **Compile definitions** | `TF_LITE_STATIC_MEMORY`, `TF_LITE_MCU_DEBUG_LOG`, `CMSIS_NN`, `SL_CATALOG_TFLITE_MICRO_PRESENT` |
| **Compile options** | `-mfp16-format=ieee` for C and C++ (required for MVP's half-precision float types) |
| **Link libraries** | `libtflm.a`, `libCMSISDSP.a`, `libcmsis-nn.a`, `stdc++`, `m` |

### Files NOT Changed (remained as-is from original)

| File | Note |
|---|---|
| `main.c` | Entry point — unchanged |
| `app_micriumos.c` | RTOS task creation, semaphore, mutex — unchanged |
| `sl_gatt_service_device_information_override.c` | Device info service — unchanged |
| All `autogen/` files (except LED instances) | Auto-generated by Simplicity Studio — not manually edited |
| All `simplicity_sdk_2025.12.1/` files | SDK — never modified |
| All other `config/` files | BLE, RTOS, power, clock configs — unchanged |

---

## 2) Original vs Final Application

| Aspect | Original (BLE Thermometer) | Final (Voice over BLE) |
|---|---|---|
| **Purpose** | Read temperature sensor, send readings to phone via BLE indication | Listen for "on"/"off" voice commands, control LED, send results to phone via BLE notification |
| **Peripherals used** | I2C temperature sensor, button | I2C temperature sensor, button, I2S microphone, 2 LEDs, MVP accelerator |
| **BLE services** | Generic Access, Device Info, Health Thermometer | Generic Access, Device Info, Health Thermometer, **Voice Result Service** (custom) |
| **RTOS tasks** | 1 (app task) | 2 (app task + audio classifier task) |
| **AI/ML** | None | TensorFlow Lite Micro with MVP hardware acceleration |
| **Binary size** | ~150 KB | ~403 KB |
| **RAM usage** | ~30 KB | ~130 KB (includes 100 KB tensor arena) |
| **Device name** | "Thermometer Example" | "SDC_For_Silabs" |

---

## 3) Architecture Overview

```
+---------------------+       +------------------------+
|                     |       |                        |
|  BLE App (app.c)    |<----->|  Audio Classifier      |
|                     |       |  (audio_classifier.cc) |
|  - Advertising      |       |                        |
|  - Connection mgmt  |       |  - Mic I2S input       |
|  - GATT notify      |       |  - Audio features      |
|  - Temp indications |       |  - TFLM + MVP inference|
|  - CLI commands      |       |  - LED control         |
|                     |       |                        |
+---------------------+       +------------------------+
        ^                              |
        |    ai_voice_result_publish() |
        +------------------------------+

Audio Pipeline:
  Mic -> I2S DMA -> Feature Gen -> TFLM Model -> RecognizeCommands -> handle_result
                                                                          |
                                                          +---------------+---------------+
                                                          |               |               |
                                                     LED on/off    BLE notify     UART log
```

### How the two tasks communicate:

1. The **audio classifier task** runs every 200 ms, processes audio, and calls `ai_voice_result_publish()` when a word is detected.
2. This function acquires a **mutex**, writes the event data to shared variables, and calls `app_proceed()` to wake the BLE app task.
3. The **BLE app task** wakes up, reads the event data (under mutex), builds the 8-byte payload, and sends it as a BLE notification.

This design ensures the classifier never directly touches BLE APIs, and the BLE task is never blocked by inference.

---

## 4) Debug Findings & Fixes

### Issues Encountered and Resolved

| # | Issue | Severity | Root Cause | Fix |
|---|---|---|---|---|
| 1 | BLE disconnect when classifier starts | Critical | `sl_tflite_micro_init()` was never called. The AIML app calls it in `sl_event_handler.c`, but the BLE app's event handler doesn't include it. TFLM APIs returned null pointers, causing a crash. | Added explicit `sl_tflite_micro_init()` call in the classifier task before any TFLM usage. |
| 2 | Microphone not working | Critical | `SL_BOARD_ENABLE_SENSOR_MICROPHONE` was `0` in the BLE app. Mic hardware never powered on. | Set to `1` in `sl_board_control_config.h`. |
| 3 | Missing mic pin config | High | `sl_mic_i2s_config.h` (USART0 pin assignments) was absent from BLE project. | Copied from AIML project. |
| 4 | Missing TFLM config | High | `sl_tflite_micro_config.h` (tensor arena size) was absent. | Copied from AIML project. |
| 5 | Linker errors (C++ runtime) | High | TFLM needs `__cxa_guard_*` (from libstdc++) and `expf`/`round` (from libm). BLE cmake didn't link these. | Added `stdc++` and `m` to `target_link_libraries`. |
| 6 | Task hangs at warmup delay | Medium | MicriumOS `OSTimeDlyHMSM` requires ms parameter 0–999. Passing 1000 causes `EFM_ASSERT` and halts the task silently. | Split into seconds + remaining ms: `OSTimeDlyHMSM(0, 0, ms/1000, ms%1000, ...)`. |
| 7 | Inference takes 15 seconds | High | MVP hardware accelerator was not included in the build. Inference fell back to pure software. | Added ~60 MVP source files, include paths, config files, and `sli_mvp_init()` call. Set `SL_MVP_POWER_MODE=2` for RTOS compatibility. |
| 8 | Compiler error: `__fp16` unknown | Medium | MVP math uses half-precision floats requiring a GCC flag. | Added `-mfp16-format=ieee` to compile options for C and CXX. |
| 9 | Linker error: LED init undefined | Medium | `sl_simple_led_instances.h` lacked `extern "C"` guards. When included from C++, the linker looked for C++-mangled symbol names. | Added `extern "C"` block to the header. |
| 10 | No LED control on detection | Low | Original `handle_result` only published events, didn't control any LED. | Added LED driver sources, config files, and on/off logic in `handle_result()`. |
| 11 | False voice detections | Low | Model occasionally triggers on background noise. Inherent limitation of small keyword models. | Can be mitigated by raising `DETECTION_THRESHOLD`, `MINIMUM_DETECTION_COUNT`, or `SMOOTHING_WINDOW_DURATION_MS` in config. |

### Debug Strategy Used

A graduated debug-level system (`APP_AUDIO_CLASSIFIER_LEVEL 0..3`) was created to isolate the crash:

| Level | What it tested | Result |
|---|---|---|
| 0 | Task only, no TFLM, no mic | Stable — proved the task itself is fine |
| 1 | TFLM init + model load (100 KB arena) | Stable — proved TFLM memory is fine |
| 2 | Level 1 + mic/audio pipeline init | Stable — proved no pin/DMA conflict |
| 3 | Full inference loop | Stable (after all fixes above) |

This system was removed during code cleanup after all issues were resolved.

---

## 5) Phase-by-Phase Summary

### Phase 0 — Baseline Verification ✅

- Verified `bt_soc_thermometer_micriumos` builds and runs correctly
- Confirmed BLE advertising, connection, temperature indications all work
- Captured baseline binary size (~150 KB) and RAM usage

### Phase 1 — BLE Transport Skeleton ✅

- Added custom Voice Result Service + Characteristic in `gatt_configuration.btconf`
- Changed device name to "SDC_For_Silabs"
- Added notification send path in `app.c` gated by CCCD enable + connection state
- Added dummy mode and CLI `hello` test command
- Tested from phone — notifications work before any AI code was added

### Phase 2 — AI Component Integration ✅

- Created `audio_classifier.cc/h` and copied `recognize_commands.cc/h` from AIML project
- Added `ai_voice_result_publish()` bridge connecting classifier output to BLE notifications
- Added event queue with mutex for thread-safe cross-task communication
- Added all AIML source files, include paths, compile definitions, and link libraries to CMakeLists.txt
- First successful build of merged firmware

### Phase 3 — Audio + Inference Runtime ✅

- Fixed all 9 issues listed in the debug findings above
- Achieved stable BLE + full inference at ~200 ms per cycle
- Confirmed voice detection on UART log

### Phase 4 — End-to-End Voice over BLE ✅

- Added LED driver support (sources, configs, instances)
- Implemented "on" → LED on, "off" → LED off behavior
- Cleaned up code — removed debug levels, diagnostic prints, unused variables
- Verified on hardware: say "on" → LED on + BLE notification; say "off" → LED off + BLE notification

### Phase 5 — Documentation ✅

- Created comprehensive `README.md` with flow, components, change guide, limitations, rename steps
- Updated `MERGE_READINESS_REPORT.md` with complete changelog

---

## 6) Current Runtime Configuration

| Parameter | Value | File |
|---|---|---|
| `INFERENCE_INTERVAL_MS` | 200 ms | `config/audio_classifier_config.h` |
| `STARTUP_WARMUP_MS` | 1000 ms | `config/audio_classifier_config.h` |
| `DETECTION_THRESHOLD` | 100 | `config/audio_classifier_config.h` |
| `SMOOTHING_WINDOW_DURATION_MS` | 600 ms | `config/audio_classifier_config.h` |
| `MINIMUM_DETECTION_COUNT` | 3 | `config/audio_classifier_config.h` |
| `SUPPRESSION_TIME_MS` | 1000 ms | `config/audio_classifier_config.h` |
| `TASK_PRIORITY` | 30 | `config/audio_classifier_config.h` |
| `TASK_STACK_SIZE` | 2048 | `config/audio_classifier_config.h` |
| `DETECTION_LED` | sl_led_led1 (Port A, pin 4) | `config/audio_classifier_config.h` |
| `SL_MVP_POWER_MODE` | 2 (yield RTOS) | `config/sl_driver_mvp_config.h` |
| Tensor arena | 100 KB | `config/sl_tflite_micro_config.h` |
| AI model | keyword_spotting_on_off_v2 | 3 classes: "on", "off", "_unknown_" |

---

## 7) Verified Behavior

- BLE advertising, connection, and GATT notifications stable with full inference running
- CLI `hello` command sends test voice events over BLE while inference runs concurrently
- Saying "on" turns LED on and sends BLE notification with class=0
- Saying "off" turns LED off and sends BLE notification with class=1
- LED stays in its last state until the opposite command is spoken
- Temperature indications still work independently alongside voice detection
- 5+ minute soak test passed with stable BLE connection
- Binary size: ~403 KB

---

## 8) Known Limitations

1. Only two voice commands supported ("on" and "off"). New commands require a different AI model.
2. Classifier starts only after BLE connect + notification enable (by design, to protect BLE stability).
3. Background noise can cause occasional false detections. Tunable via threshold/smoothing settings.
4. Single BLE connection at a time.
5. No persistent state — LED resets to off after power cycle.
6. Memory is tight (~130 KB RAM used). Larger models or more services need careful budgeting.
7. AI model is fixed at build time (on-device inference, no cloud).
