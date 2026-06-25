/* Copyright 2017 The TensorFlow Authors. All Rights Reserved.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
==============================================================================
Modified by Silicon Labs.
==============================================================================*/

#include "recognize_commands.h"
#include <cstdio>

void PreviousResultsQueue::push_back(const Result& entry)
{
  if (size() >= MAX_RESULT_COUNT) {
    TF_LITE_REPORT_ERROR(error_reporter_, "Couldn't push_back latest result, too many already!");
    return;
  }
  size_ += 1;
  back() = entry;
}

PreviousResultsQueue::Result PreviousResultsQueue::pop_front()
{
  if (size() <= 0) {
    TF_LITE_REPORT_ERROR(error_reporter_, "Couldn't pop_front result, none present!");
    return Result();
  }
  Result result = front();
  front_index_ += 1;
  if (front_index_ >= MAX_RESULT_COUNT) {
    front_index_ = 0;
  }
  size_ -= 1;
  return result;
}

PreviousResultsQueue::Result& PreviousResultsQueue::from_front(int offset)
{
  if ((offset < 0) || (offset >= size_)) {
    TF_LITE_REPORT_ERROR(error_reporter_, "Attempt to read beyond the end of the queue!");
    offset = size_ - 1;
  }
  int index = front_index_ + offset;
  if (index >= MAX_RESULT_COUNT) {
    index -= MAX_RESULT_COUNT;
  }
  return results_[index];
}

RecognizeCommands::RecognizeCommands(tflite::ErrorReporter* error_reporter,
                                     int32_t average_window_duration_ms,
                                     uint8_t detection_threshold,
                                     int32_t suppression_ms,
                                     int32_t minimum_count,
                                     bool ignore_underscore)
  : error_reporter_(error_reporter),
    average_window_duration_ms_(average_window_duration_ms),
    detection_threshold_(detection_threshold),
    suppression_ms_(suppression_ms),
    minimum_count_(minimum_count),
    ignore_underscore_(ignore_underscore),
    previous_results_(error_reporter)
{
  previous_top_label_index_ = 0;
  previous_top_label_time_ = 0;
}

TfLiteStatus RecognizeCommands::ProcessLatestResults(
  const TfLiteTensor* latest_results, const int32_t current_time_ms,
  uint8_t* found_command_index, uint8_t* score, bool* is_new_command)
{
  int8_t current_top_index = 0;
  uint32_t current_top_score = 0;
  uint8_t converted_scores[category_count];

  if ((latest_results->dims->size != 2)
      || (latest_results->dims->data[0] != 1)
      || (latest_results->dims->data[1] != category_count)) {
    TF_LITE_REPORT_ERROR(error_reporter_,
                         "Recognition expects %d elements but got %d",
                         category_count, latest_results->dims->data[1]);
    return kTfLiteError;
  }

  if ((!previous_results_.empty()) && (current_time_ms < previous_results_.front().time_)) {
    TF_LITE_REPORT_ERROR(error_reporter_,
                         "Results must be fed in increasing time order");
    return kTfLiteError;
  }

  if (latest_results->type == kTfLiteFloat32) {
    for (int i = 0; i < category_count; ++i) {
      converted_scores[i] = (uint8_t)(latest_results->data.f[i] * 255);
    }
  } else if (latest_results->type == kTfLiteInt8) {
    for (int i = 0; i < category_count; ++i) {
      converted_scores[i] = (uint8_t)(latest_results->data.int8[i] + 128);
    }
  } else {
    TF_LITE_REPORT_ERROR(error_reporter_, "Unsupported output tensor data type");
    return kTfLiteError;
  }

  if (minimum_count_ == 0) {
    for (int i = 0; i < category_count; i++) {
      if (converted_scores[i] > current_top_score) {
        current_top_score = converted_scores[i];
        current_top_index = i;
      }
    }
  } else {
    previous_results_.push_back({ current_time_ms, converted_scores });
    const int64_t time_limit = current_time_ms - average_window_duration_ms_;
    while ((!previous_results_.empty()) && previous_results_.front().time_ < time_limit) {
      previous_results_.pop_front();
    }

    const int32_t how_many_results = previous_results_.size();
    if (how_many_results < minimum_count_) {
      *found_command_index = previous_top_label_index_;
      *score = 0;
      *is_new_command = false;
      return kTfLiteOk;
    }

    uint32_t average_scores[category_count];
    for (int offset = 0; offset < previous_results_.size(); ++offset) {
      PreviousResultsQueue::Result previous_result = previous_results_.from_front(offset);
      const uint8_t* scores = previous_result.scores;
      for (int i = 0; i < category_count; ++i) {
        if (offset == 0) {
          average_scores[i] = scores[i];
        } else {
          average_scores[i] += scores[i];
        }
      }
    }
    for (int i = 0; i < category_count; ++i) {
      average_scores[i] /= how_many_results;
    }
    for (int i = 0; i < category_count; ++i) {
      if (average_scores[i] > current_top_score) {
        current_top_score = average_scores[i];
        current_top_index = i;
      }
    }
  }

  const char *current_top_label = get_category_label(current_top_index);
  int64_t time_since_last_top = current_time_ms - previous_top_label_time_;

  if ((current_top_score > detection_threshold_)
      && (ignore_underscore_ && current_top_label[0] != '_')
      && (time_since_last_top > suppression_ms_)) {
    previous_top_label_index_ = current_top_index;
    previous_top_label_time_ = current_time_ms;
    *is_new_command = true;
  } else {
    *is_new_command = false;
  }

  *found_command_index = current_top_index;
  *score = current_top_score;
  return kTfLiteOk;
}

