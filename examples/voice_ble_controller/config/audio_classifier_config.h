/***************************************************************************//**
 * @file
 * @brief Audio classifier application config
 ******************************************************************************/

#ifndef AUDIO_CLASSIFIER_CONFIG_H
#define AUDIO_CLASSIFIER_CONFIG_H

#if __has_include("sl_tflite_micro_model_parameters.h")
  #include "sl_tflite_micro_model_parameters.h"
#endif

#if defined(SL_TFLITE_MODEL_AVERAGE_WINDOW_DURATION_MS)
  #define SMOOTHING_WINDOW_DURATION_MS SL_TFLITE_MODEL_AVERAGE_WINDOW_DURATION_MS
#else
  #define SMOOTHING_WINDOW_DURATION_MS 1500 // Increased for better smoothing
#endif


#if defined(SL_TFLITE_MODEL_MINIMUM_COUNT)
  #define MINIMUM_DETECTION_COUNT SL_TFLITE_MODEL_MINIMUM_COUNT
#else
  #define MINIMUM_DETECTION_COUNT 2 // Reduced to trigger more easily
#endif


#if defined(SL_TFLITE_MODEL_DETECTION_THRESHOLD)
  #define DETECTION_THRESHOLD SL_TFLITE_MODEL_DETECTION_THRESHOLD
#else
  #define DETECTION_THRESHOLD 120 // Lowered to be more sensitive
#endif


#if defined(SL_TFLITE_MODEL_SUPPRESSION_MS)
  #define SUPPRESSION_TIME_MS SL_TFLITE_MODEL_SUPPRESSION_MS
#else
  #define SUPPRESSION_TIME_MS 1000
#endif

#define IGNORE_UNDERSCORE_LABELS 1

#define DETECTION_LED         sl_led_led1
#define INFERENCE_INTERVAL_MS 200
#define STARTUP_WARMUP_MS     1000
#define MAX_CATEGORY_COUNT    16
#define MAX_RESULT_COUNT      50
#define TASK_STACK_SIZE       2048
#define TASK_PRIORITY         30

#undef CATEGORY_LABELS
#define CATEGORY_LABELS { "on", "off", "unknown" }

#endif // AUDIO_CLASSIFIER_CONFIG_H
