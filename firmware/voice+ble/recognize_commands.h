/* Copyright 2017 The TensorFlow Authors. All Rights Reserved.
   Modified by Silicon Labs. */

#ifndef MODEL_RECOGNIZE_COMMANDS_H_
#define MODEL_RECOGNIZE_COMMANDS_H_

#include <cstdint>

#include "tensorflow/lite/c/common.h"
#include "tensorflow/lite/micro/tflite_bridge/micro_error_reporter.h"
#include "config/audio_classifier_config.h"
#include "audio_classifier.h"

class PreviousResultsQueue {
public:
  PreviousResultsQueue(tflite::ErrorReporter * error_reporter)
    : error_reporter_(error_reporter), front_index_(0), size_(0) {}

  struct Result {
    Result() : time_(0), scores() {}
    Result(int32_t time, uint8_t * input_scores) : time_(time) {
      for (int i = 0; i < category_count; ++i) {
        scores[i] = input_scores[i];
      }
    }
    int32_t time_;
    uint8_t scores[MAX_CATEGORY_COUNT];
  };

  int size() { return size_; }
  bool empty() { return size_ == 0; }
  Result& front() { return results_[front_index_]; }
  Result& back() {
    int back_index = front_index_ + (size_ - 1);
    if (back_index >= MAX_RESULT_COUNT) {
      back_index -= MAX_RESULT_COUNT;
    }
    return results_[back_index];
  }

  void push_back(const Result& entry);
  Result pop_front();
  Result& from_front(int offset);

private:
  tflite::ErrorReporter* error_reporter_;
  Result results_[MAX_RESULT_COUNT];
  int front_index_;
  int size_;
};

class RecognizeCommands {
public:
  explicit RecognizeCommands(tflite::ErrorReporter* error_reporter,
                             int32_t average_window_duration_ms = 1000,
                             uint8_t detection_threshold = 50,
                             int32_t suppression_ms = 1500,
                             int32_t minimum_count = 3,
                             bool ignore_underscore = true);

  TfLiteStatus ProcessLatestResults(const TfLiteTensor* latest_results,
                                    const int32_t current_time_ms,
                                    uint8_t* found_command_index,
                                    uint8_t* score,
                                    bool* is_new_command);

private:
  tflite::ErrorReporter* error_reporter_;
  int32_t average_window_duration_ms_;
  uint8_t detection_threshold_;
  int32_t suppression_ms_;
  int32_t minimum_count_;
  bool ignore_underscore_;
  PreviousResultsQueue previous_results_;
  uint8_t previous_top_label_index_;
  int32_t previous_top_label_time_;
};

#endif  // MODEL_RECOGNIZE_COMMANDS_H_

