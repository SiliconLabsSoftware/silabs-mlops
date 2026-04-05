/***************************************************************************//**
 * @file
 * @brief Audio classifier integration interface.
 ******************************************************************************/

#ifndef AUDIO_CLASSIFIER_H
#define AUDIO_CLASSIFIER_H

#ifdef __cplusplus
extern "C" {
#endif

extern int category_count;

void audio_classifier_init(void);
const char *get_category_label(int index);

#ifdef __cplusplus
}
#endif

#endif // AUDIO_CLASSIFIER_H

