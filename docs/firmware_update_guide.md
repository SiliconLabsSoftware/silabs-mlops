# Firmware Update Guide – Voice-BLE Controller
This guide provides simple instructions for updating the AI model and flashing the firmware on your Silicon Labs edge device (EFR32MG26). Follow these steps to replace your "ON/OFF" model with a new one or to update your keyword labels.

## 1. Prerequisites  
Before you begin, ensure you have the following tools installed and added to your system PATH:

*   **Simplicity SDK (v2025.12.1 or later):** The core SDK for building the project.
*   **ARM GCC Toolchain:** Used to compile the C/C++ code.
*   **CMake (v3.25+):** The build system generator.
*   **Ninja:** The recommended build tool for fast compilation.
*   **Simplicity Commander:** Used to flash the final binary to the board.  
    *   *Download:* [Simplicity Commander](https://www.silabs.com/software-and-tools/simplicity-studio/simplicity-commander?tab=getting-started)
    *   *Note:* Ensure `commander.exe` (Windows) or `commander-cli` (Linux) is in your PATH.

---

## 2. Configuration (User Action Required)
When you have a new model or want to change your keywords, you must update two specific parts of the project:

### 🔹 Step 1: Replace the TFLite Model
Download your new `.tflite` model and move it to the following directory:
`voice_ble_controller/config/tflite/`

*   **Important:** The current system is configured to look for a specific file. If you rename your new model to `keyword_spotting_on_off_v2.tflite`, the build system will pick it up automatically.
*   **Using a different filename?** If you use a different name, you must update the reference in the project configuration (usually via the Simplicity Configurator).

### 🔹 Step 2: Update Keyword Labels
Open `voice_ble_controller/config/audio_classifier_config.h` and update the `CATEGORY_LABELS` to match your new model's output classes.

**Example: Switching from "ON/OFF" to "DOG/CAT"**
```c
// Match this to your new model's output order!
#undef CATEGORY_LABELS
#define CATEGORY_LABELS { "dog", "cat", "unknown" }
```

> [!IMPORTANT]
> The order of labels in this list **MUST MATCH** the output order of your AI model. If "dog" is index 0 in your model, it must be the first item in the list.

---

## 3. Rebuild the Project
After replacing the model and updating the labels, you must rebuild the firmware. This process converts the `.tflite` file into a C-array (`autogen/sl_tflite_micro_model.c`) and compiles the binary.

Choose **one** of the following methods to build your project:

### Option A: Command Line (CMake)
1.  Open a terminal inside the project directory.
2.  Navigate to the build folder:
    ```powershell
    cd voice_ble_controller/cmake_gcc
    ```
3.  **Configure the project** (only required the first time or if you added files):
    ```powershell
    cmake --preset project
    ```
4.  **Build the firmware:**
    ```powershell
    cmake --build --preset default_config
    ```

### Option B: Simplicity Studio (IDE)
1.  **Open Simplicity Studio** and ensure your board is connected.
2.  **Import the project:** Go to `File > Import` and select the folder containing the `voice_ble_controller.slcp` file.
3.  **Generate project files:** If you changed the `.slcp` or added files, click the **"Generate"** button in the project overview.
4.  **Build:** Click the **Hammer icon** (Build) in the top toolbar.
5.  **Location:** The output `.s37` file will be in the project folder (e.g., `GNU ARM vXX.X.X - Default`).

### Option C: VS Code (Silicon Labs Extension)
1.  **Open VS Code** and ensure the **Silicon Labs Support** extension is installed.
2.  **Open the Project:** Open the folder containing the `voice_ble_controller.slcp` file.
3.  **Select Configuration:** In the **Silicon Labs View** (sidebar icon), ensure the correct SDK and Toolchain are selected.
4.  **Build:** Click the **Build icon** (Hammer) next to your project name in the Silicon Labs view.
5.  **Flash:** Click the **Flash icon** (Lightning bolt) to upload the binary directly to your board.

---

## 4. How to Flash the Firmware
Depending on how you built your project (Options A, B, or C), use one of the following methods to flash:

*   **Options A & B (CMake/Studio):** Use the manual `commander` command below.
*   **Option C (VS Code Extension):** You can use the **Flash icon (Lightning bolt)** in the Silicon Labs sidebar to flash automatically. Skip the steps below if using Option C.

### Step 1: Identify your Device Serial Number (Mandatory)
Before flashing, you must obtain your board's unique 9-digit serial number. Ensure your board is connected via USB and run:
```powershell
commander device info
```
Look for the `Serial Number` line in the output (e.g., `440312345`).


### Step 2: Run the Flash Command
Run the following command, replacing `<YOUR_SERIAL_NUMBER>` with the number from Step 1:

```powershell
# Mandatory: --serialno must be provided for the flash to succeed
commander flash voice_ble_controller/cmake_gcc/build/voice_ble_controller.s37 --serialno <YOUR_SERIAL_NUMBER>
```

> [!IMPORTANT]
> The `--serialno` argument is mandatory to ensure the correct board is targetted, even if only one board is connected.

---

## 5. Verifying the Update
After flashing, the board will reboot automatically. You can verify the new keywords are working using the **Serial Log**:

1.  Open a serial terminal (e.g., PuTTY, Tera Term, minicom, or VS Code Serial Monitor).
2.  Set the baud rate to **115200**.
3.  Press the **Reset** button on the board.
4.  You should see the following log confirming the number of classes:
    `[I] Audio classifier ready (3 classes)`
5.  Say your new keywords near the microphone. If a keyword is detected, it will appear in the log:
    `[I] dog (score=245)`

---

## 6. Project Checklist
- [ ] New `.tflite` model copied to `config/tflite/`
- [ ] `CATEGORY_LABELS` updated in `audio_classifier_config.h`
- [ ] `cmake --build` ran successfully with no errors
- [ ] Firmware flashed via Simplicity Commander
- [ ] Verified detections in the Serial Log at 115200 baud

---

> [!NOTE]
> The source code for this project folder is also uploaded in the [examples folder](https://capgemini-my.sharepoint.com/personal/paavan_joshi_capgemini_com/Documents/Documents/Silicon-Labs/MLops_SDK_lib_dev/silabs-mlops-cli/examples) for easy reference.
