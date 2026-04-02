/***************************************************************************//**
 * @file
 * @brief Audio classifier runtime — voice keyword detection with BLE publish.
 ******************************************************************************/

#include "os.h"
#include "sl_power_manager.h"
#include "sl_status.h"
#include "app.h"
#include "audio_classifier.h"
#include "recognize_commands.h"
#include "config/audio_classifier_config.h"
#include "sl_tflite_micro_init.h"
#include "sl_ml_audio_feature_generation.h"
#include "sl_sleeptimer.h"
#include "sl_mvp.h"
#include "sl_led.h"
#include "sl_simple_led_instances.h"
#include "sl_mic.h"
#include <new>
#include <cstdio>
#include <cstring>

// 1 second of audio at 16kHz, 16-bit
#define AUDIO_BUFFER_SIZE_SAMPLES 16000 
static int16_t audio_ring_buffer[AUDIO_BUFFER_SIZE_SAMPLES];
static uint32_t ring_buffer_head = 0;
static bool audio_buffer_frozen = false;

static RecognizeCommands *command_recognizer = nullptr;
alignas(RecognizeCommands) static uint8_t command_recognizer_storage[sizeof(RecognizeCommands)];

static OS_TCB tcb;
static CPU_STK stack[TASK_STACK_SIZE];

int category_count = 0;
const char* category_labels[] = CATEGORY_LABELS;
static int category_label_count = sizeof(category_labels) / sizeof(category_labels[0]);

static void audio_classifier_task(void *arg);
static void handle_result(int32_t current_time, int result, uint8_t score, bool is_new_command);

static void update_audio_ring_buffer(int16_t* new_samples, uint32_t count) {
  if (audio_buffer_frozen) return;
  for (uint32_t i = 0; i < count; i++) {
    audio_ring_buffer[ring_buffer_head] = new_samples[i];
    ring_buffer_head = (ring_buffer_head + 1) % AUDIO_BUFFER_SIZE_SAMPLES;
  }
}

static void mic_on_buffer_ready(const int16_t *buffer, uint32_t n_frames) {
  update_audio_ring_buffer((int16_t*)buffer, n_frames);
  // Forward to ML feature generator
  sli_ml_audio_feature_generation_audio_buffer_write_chunk(buffer, n_frames);
}

extern "C" void app_get_triggered_audio_buffer(int16_t* out_buf, uint32_t* head_offset) {
  memcpy(out_buf, audio_ring_buffer, sizeof(audio_ring_buffer));
  *head_offset = ring_buffer_head;
  audio_buffer_frozen = false; // Unfreeze after copying
}

static sl_status_t run_inference(void)
{
  sl_status_t status = sl_ml_audio_feature_generation_fill_tensor(sl_tflite_micro_get_input_tensor());
  if (status != SL_STATUS_OK) {
    return SL_STATUS_FAIL;
  }
  TfLiteStatus invoke_status = sl_tflite_micro_get_interpreter()->Invoke();
  return (invoke_status == kTfLiteOk) ? SL_STATUS_OK : SL_STATUS_FAIL;
}

static sl_status_t process_output(void)
{
  uint8_t result = 0;
  uint8_t score = 0;
  bool is_new_command = false;
  uint32_t current_time_stamp = sl_sleeptimer_tick_to_ms(sl_sleeptimer_get_tick_count());

  TfLiteStatus process_status = command_recognizer->ProcessLatestResults(
    sl_tflite_micro_get_output_tensor(), current_time_stamp, &result, &score, &is_new_command);

  if (process_status == kTfLiteOk) {
    handle_result((int32_t)current_time_stamp, result, score, is_new_command);
    return SL_STATUS_OK;
  }
  return SL_STATUS_FAIL;
}

void audio_classifier_init(void)
{
  RTOS_ERR err;
  char task_name[] = "audio classifier task";
  OSTaskCreate(&tcb,
               task_name,
               audio_classifier_task,
               DEF_NULL,
               TASK_PRIORITY,
               &stack[0],
               (TASK_STACK_SIZE / 10u),
               TASK_STACK_SIZE,
               0u,
               0u,
               DEF_NULL,
               (OS_OPT_TASK_STK_CLR),
               &err);
  EFM_ASSERT((RTOS_ERR_CODE_GET(err) == RTOS_ERR_NONE));
}

static void audio_classifier_task(void *arg)
{
  RTOS_ERR err;
  (void)&arg;

  sl_simple_led_init_instances();
  sli_mvp_init();
  sl_tflite_micro_init();

  command_recognizer = new (command_recognizer_storage) RecognizeCommands(
    sl_tflite_micro_get_error_reporter(),
    SMOOTHING_WINDOW_DURATION_MS,
    DETECTION_THRESHOLD,
    SUPPRESSION_TIME_MS,
    MINIMUM_DETECTION_COUNT,
    IGNORE_UNDERSCORE_LABELS);

  const TfLiteTensor* input = sl_tflite_micro_get_input_tensor();
  const TfLiteTensor* output = sl_tflite_micro_get_output_tensor();

  if (output == nullptr || input == nullptr) {
    printf("[E] TFLM tensors NULL\r\n");
    while (1) { OSTimeDly(1000, OS_OPT_TIME_DLY, &err); }
  }

  if ((output->dims->size == 2) && (output->dims->data[0] == 1)) {
    category_count = output->dims->data[1];
  } else {
    printf("[E] Invalid output tensor shape\r\n");
    while (1) { OSTimeDly(1000, OS_OPT_TIME_DLY, &err); }
  }

  if ((input->type != kTfLiteInt8) || (output->type != kTfLiteInt8)) {
    printf("[E] Model I/O must be int8\r\n");
    while (1) { OSTimeDly(1000, OS_OPT_TIME_DLY, &err); }
  }

  sl_ml_audio_feature_generation_init();
  sl_mic_stop(); // Stop the SDK's initialization to re-register our hook

  // Re-register microphone callback to hook raw samples
  static int16_t double_mic_buffer[2 * 512]; // Ping-pong buffer
  sl_mic_start_streaming(double_mic_buffer, 512, (sl_mic_buffer_ready_callback_t)mic_on_buffer_ready);

  OSTimeDlyHMSM(0, 0, STARTUP_WARMUP_MS / 1000, STARTUP_WARMUP_MS % 1000,
                OS_OPT_TIME_DLY, &err);
  EFM_ASSERT((RTOS_ERR_CODE_GET(err) == RTOS_ERR_NONE));

  sl_power_manager_add_em_requirement(SL_POWER_MANAGER_EM1);

  printf("[I] Audio classifier ready (%d classes)\r\n", category_count);

  while (1) {
    OSTimeDlyHMSM(0, 0, 0, INFERENCE_INTERVAL_MS, OS_OPT_TIME_PERIODIC, &err);
    EFM_ASSERT((RTOS_ERR_CODE_GET(err) == RTOS_ERR_NONE));

    sl_ml_audio_feature_generation_update_features();
    
    // Raw audio is now captured in the background via the mic callback

    run_inference();
    process_output();
  }
}

static bool is_audio_silent(void)
{
  int64_t sum = 0;
  for (int i = 0; i < AUDIO_BUFFER_SIZE_SAMPLES; i++) {
    int16_t sample = audio_ring_buffer[i];
    sum += (sample < 0) ? -sample : sample;
  }
  // Sum of absolute values / total samples = average magnitude
  // A value of 50-100 is typically enough for a quiet room.
  return (sum / AUDIO_BUFFER_SIZE_SAMPLES) < 60;
}

static void handle_result(int32_t current_time, int result, uint8_t score, bool is_new_command)
{
  // Log any significant detections for debugging
  if (score > 100) {
    const char *label = get_category_label(result);
    printf("[D] Candidate: %s (score=%d), new=%d\r\n", label, score, is_new_command);
  }

  if (!is_new_command) {
    return;
  }

  // SILENCE FILTER for non-target words (anything index 2 or higher)
  if (result >= 2 && is_audio_silent()) {
    printf("[I] Skip trigger '%s' due to silence\r\n", get_category_label(result));
    return;
  }

  const char *label = get_category_label(result);
  ai_voice_result_publish((uint8_t)result, score, (uint32_t)current_time, 1u);
  printf("[I] %s (score=%d)\r\n", label, score);

  if (result == 0) {
    sl_led_turn_on(&DETECTION_LED);
    audio_buffer_frozen = true; // Snap the buffer
  } else if (result == 1) {
    sl_led_turn_off(&DETECTION_LED);
    audio_buffer_frozen = true; // Snap the buffer
  } else {
    // For "unknown" (result 2) or others, just snap the buffer
    audio_buffer_frozen = true; 
  }
}

const char * get_category_label(int index)
{
  if ((index >= 0) && (index < category_label_count)) {
    return category_labels[index];
  }
  return "?";
}
