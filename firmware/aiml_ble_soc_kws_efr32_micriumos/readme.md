# Audio Classifier with Voice over BLE

This example extends [aiml_soc_audio_classifier_efr32_micriumos](../aiml_soc_audio_classifier_efr32_micriumos) with Bluetooth Low Energy: keyword classification results (and optional audio samples) are exposed over a custom GATT service. A Health Thermometer–style service is used for the on-board RHT sensor, following the same Micrium OS + BLE pattern as the Bluetooth SDK voice examples.

Open `aiml_soc_voice_ble_efr32_micriumos.slcp` in Simplicity Studio (AI/ML extension, **no Conan/package-manager workflow**—same as the other `examples/aiml-extension/examples` projects). Create a solution for your board, run **Generate**, then build and flash.

## Behavior

Audio classification matches the base audio classifier: LEDs and VCOM show activity and detections. In addition, BLE advertising allows a phone or central to connect; GATT notifications carry classification updates and optional PCM data per `config/btconf/gatt_configuration.btconf`.

## Model

Same keyword-spotting `.tflite` assets as the audio classifier (`tflite_models/tflite/`). Replace models as in the [base readme](../aiml_soc_audio_classifier_efr32_micriumos/readme.md#model).

## References

- [Machine Learning (AI/ML) documentation](https://docs.silabs.com/machine-learning/latest/aiml-developing-with)
- [MLTK](https://siliconlabs.github.io/mltk)
- [TensorFlow Lite Micro](https://www.tensorflow.org/lite/microcontrollers)
