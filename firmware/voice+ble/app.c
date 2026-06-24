/***************************************************************************//**
 * @file
 * @brief Core application logic.
 *******************************************************************************
 * # License
 * <b>Copyright 2026 Silicon Laboratories Inc. www.silabs.com</b>
 *******************************************************************************
 *
 * SPDX-License-Identifier: LicenseRef-MSLA
 *
 * The licensor of this software is Silicon Laboratories Inc. Your use of this
 * software is governed by the terms of Silicon Labs Master Software License
 * Agreement (MSLA) available at
 * www.silabs.com/about-us/legal/master-software-license-agreement. This
 * software is distributed to you in Source Code format and is governed by the
 * sections of the MSLA applicable to Source Code.
 *
 * By installing, copying or otherwise using this software, you agree to the
 * terms of the MSLA.
 ******************************************************************************/

#include <stdbool.h>
#include <stdint.h>
#include "sl_status.h"
#include "sl_simple_button_instances.h"
#include "app_timer.h"
#include "app_log.h"
#include "app_assert.h"
#include "sl_bt_api.h"
#include "gatt_db.h"
#include "sl_component_catalog.h"
#ifdef SL_CATALOG_CLI_PRESENT
#include "sl_cli.h"
#endif // SL_CATALOG_CLI_PRESENT
#include "sl_sensor_rht.h"
#include "sl_health_thermometer.h"
#include "sl_main_init.h"
#include "app.h"
#include "audio_classifier.h"

// Define APP_VOICE_CHAR_PRESENT based on existence of gattdb_voice_result
#ifdef gattdb_voice_result
#define APP_VOICE_CHAR_PRESENT 1
#else
#define APP_VOICE_CHAR_PRESENT 0
#endif

#define APP_ENABLE_AUDIO_CLASSIFIER 1u

// Connection handle.
static uint8_t app_connection = 0;

// The advertising set handle allocated from Bluetooth stack.
static uint8_t advertising_set_handle = 0xff;

// Button state.
static volatile bool app_btn0_pressed = false;

// Periodic timer handle.
static app_timer_t app_periodic_timer;
static app_timer_t app_voice_timer;
static app_timer_t app_audio_start_timer;

// Periodic timer callback.
static void app_periodic_timer_cb(app_timer_t *timer, void *data);
static void app_voice_timer_cb(app_timer_t *timer, void *data);
static void app_audio_start_timer_cb(app_timer_t *timer, void *data);
static void app_send_voice_result_payload(uint8_t class_id,
                                          uint8_t score,
                                          uint32_t timestamp_ms,
                                          uint8_t flags);

#define APP_VOICE_NOTIFY_INTERVAL_MS   1000u
#define APP_VOICE_DUMMY_DEFAULT_ENABLED 0u
#define APP_AUDIO_START_DELAY_MS       2500u

static bool app_voice_notify_enabled = false;
static bool app_voice_dummy_enabled = (APP_VOICE_DUMMY_DEFAULT_ENABLED != 0u);
static uint32_t app_voice_timestamp_ms = 0u;
static uint8_t app_voice_class_id = 0u;
static volatile bool app_voice_dummy_tick = false;
static bool app_voice_event_pending = false;
static uint8_t app_voice_event_class_id = 0u;
static uint8_t app_voice_event_score = 0u;
static uint8_t app_voice_event_flags = 0u;
static uint32_t app_voice_event_timestamp_ms = 0u;
static uint32_t app_voice_test_timestamp_ms = 0u;
#if APP_ENABLE_AUDIO_CLASSIFIER
static bool app_audio_classifier_started = false;
static volatile bool app_audio_start_pending = false;

// Burst state
#define AUDIO_BUF_SIZE_SAMPLES 16000
static int16_t app_audio_burst_buf[AUDIO_BUF_SIZE_SAMPLES];
static uint32_t app_audio_burst_head = 0;
static uint32_t app_audio_burst_bytes_sent = 0;
static uint32_t app_audio_burst_packets_sent = 0;
static bool app_audio_burst_pending = false;
static app_timer_t app_audio_burst_timer;
static void app_audio_burst_timer_cb(app_timer_t *timer, void *data);
#endif

#define BURST_SIGNAL_MASK 0x01

// Application Init.
void app_init(void)
{
  sl_status_t sc;
  // Init temperature sensor.
  sc = sl_sensor_rht_init();
  if (sc != SL_STATUS_OK) {
    app_log_warning("Relative Humidity and Temperature sensor initialization failed [0x%04lx]" APP_LOG_NL, sc);
  }
  app_log_info("Voice BLE controller APP initialized" APP_LOG_NL);
  if (!APP_VOICE_CHAR_PRESENT) {
    app_log_warning("Voice characteristic handle missing in gatt_db. Regenerate GATT sources." APP_LOG_NL);
  }
  app_log_info("Voice dummy mode default: %s" APP_LOG_NL,
               app_voice_dummy_enabled ? "enabled" : "disabled");
#if APP_ENABLE_AUDIO_CLASSIFIER
  voice_result_set_dummy_mode(false);
  app_log_info("Audio classifier start deferred until voice notify enable" APP_LOG_NL);
#endif

  /////////////////////////////////////////////////////////////////////////////
  // Put your additional application init code here!                         //
  // This is called once during start-up.                                    //
  /////////////////////////////////////////////////////////////////////////////
}

// Application Process Action.
void app_process_action(void)
{
  if (app_is_process_required()) {
#if APP_ENABLE_AUDIO_CLASSIFIER
    if (app_audio_start_pending) {
      app_audio_start_pending = false;
      if (!app_audio_classifier_started && app_voice_notify_enabled) {
        audio_classifier_init();
        app_audio_classifier_started = true;
        app_log_info("Audio classifier task started" APP_LOG_NL);
      }
    }
#endif

    if (app_voice_dummy_tick) {
      app_voice_dummy_tick = false;
      app_voice_timestamp_ms += APP_VOICE_NOTIFY_INTERVAL_MS;
      app_voice_class_id = (uint8_t)((app_voice_class_id + 1u) % 3u);
      voice_result_publish(app_voice_class_id,
                           (uint8_t)(70u + app_voice_class_id * 10u),
                           app_voice_timestamp_ms,
                           1u);
    }

    if (app_mutex_acquire()) {
      if (app_voice_event_pending) {
        uint8_t class_id = app_voice_event_class_id;
        uint8_t score = app_voice_event_score;
        uint8_t flags = app_voice_event_flags;
        uint32_t timestamp_ms = app_voice_event_timestamp_ms;
        app_voice_event_pending = false;
        app_mutex_release();
        app_send_voice_result_payload(class_id, score, timestamp_ms, flags);
        
        // Start the audio burst
        app_trigger_audio_burst();
      } else {
        app_mutex_release();
      }
    }

    // Audio Burst Processing (Moved to sl_bt_evt_system_soft_timer_id)
    /////////////////////////////////////////////////////////////////////////////
    /////////////////////////////////////////////////////////////////////////////
    // Put your additional application code here!                              //
    // This is will run each time app_proceed() is called.                     //
    // Do not call blocking functions from here!                               //
    /////////////////////////////////////////////////////////////////////////////
  }
}

/**************************************************************************//**
 * Bluetooth stack event handler.
 * This overrides the default weak implementation.
 *
 * @param[in] evt Event coming from the Bluetooth stack.
 *****************************************************************************/
void sl_bt_on_event(sl_bt_msg_t *evt)
{
  sl_status_t sc;
  bd_addr address;
  uint8_t address_type;

  // Handle stack events
  switch (SL_BT_MSG_ID(evt->header)) {
    // -------------------------------
    // This event indicates the device has started and the radio is ready.
    // Do not call any stack command before receiving this boot event!
    case sl_bt_evt_system_boot_id:
      // Print boot message.
      app_log_info("Bluetooth stack booted: v%d.%d.%d+%08lx" APP_LOG_NL,
                   evt->data.evt_system_boot.major,
                   evt->data.evt_system_boot.minor,
                   evt->data.evt_system_boot.patch,
                   evt->data.evt_system_boot.hash);

      // Extract unique ID from BT Address.
      sc = sl_bt_gap_get_identity_address(&address, &address_type);
      app_assert_status(sc);

      app_log_info("Bluetooth %s address: %02X:%02X:%02X:%02X:%02X:%02X" APP_LOG_NL,
                   address_type ? "static random" : "public device",
                   address.addr[5],
                   address.addr[4],
                   address.addr[3],
                   address.addr[2],
                   address.addr[1],
                   address.addr[0]);

      // Create an advertising set.
      sc = sl_bt_advertiser_create_set(&advertising_set_handle);
      app_assert_status(sc);

      // Generate data for advertising
      sc = sl_bt_legacy_advertiser_generate_data(advertising_set_handle,
                                                 sl_bt_advertiser_general_discoverable);
      app_assert_status(sc);

      // Set advertising interval to 100ms.
      sc = sl_bt_advertiser_set_timing(
        advertising_set_handle, // advertising set handle
        160, // min. adv. interval (milliseconds * 1.6)
        160, // max. adv. interval (milliseconds * 1.6)
        0,   // adv. duration
        0);  // max. num. adv. events
      app_assert_status(sc);

      // Start advertising and enable connections.
      sc = sl_bt_legacy_advertiser_start(advertising_set_handle,
                                         sl_bt_legacy_advertiser_connectable);
      app_assert_status(sc);

      app_log_info("Started advertising" APP_LOG_NL);
      break;

    // -------------------------------
    // This event indicates that a new connection was opened.
    case sl_bt_evt_connection_opened_id:
      app_connection = evt->data.evt_connection_opened.connection;
      app_log_info("Connection opened" APP_LOG_NL);

#ifdef SL_CATALOG_BLUETOOTH_FEATURE_POWER_CONTROL_PRESENT
      // Set remote connection power reporting - needed for Power Control
      sc = sl_bt_connection_set_remote_power_reporting(
        evt->data.evt_connection_opened.connection,
        sl_bt_connection_power_reporting_enable);
      app_assert_status(sc);
#endif // SL_CATALOG_BLUETOOTH_FEATURE_POWER_CONTROL_PRESENT

      break;

    // -------------------------------
    // This event indicates that a connection was closed.
    case sl_bt_evt_connection_closed_id:
      app_log_info("Connection closed: reason=0x%04lx" APP_LOG_NL,
                   (unsigned long)evt->data.evt_connection_closed.reason);
      app_voice_notify_enabled = false;
      app_voice_dummy_tick = false;
      app_voice_event_pending = false;
      (void)app_timer_stop(&app_voice_timer);
#if APP_ENABLE_AUDIO_CLASSIFIER
      app_audio_start_pending = false;
      (void)app_timer_stop(&app_audio_start_timer);
#endif

      // Restart advertising after client has disconnected.
      sc = sl_bt_legacy_advertiser_start(advertising_set_handle,
                                         sl_bt_legacy_advertiser_connectable);
      app_assert_status(sc);
      app_log_info("Started advertising" APP_LOG_NL);
      break;

    case sl_bt_evt_gatt_server_characteristic_status_id:
      if ((evt->data.evt_gatt_server_characteristic_status.characteristic == gattdb_voice_result)
          && (evt->data.evt_gatt_server_characteristic_status.status_flags == sl_bt_gatt_server_client_config)) {
        uint16_t cccd = evt->data.evt_gatt_server_characteristic_status.client_config_flags;
        if (cccd == sl_bt_gatt_disable) {
          if (app_voice_notify_enabled) {
            app_voice_notify_enabled = false;
            app_voice_dummy_tick = false;
            app_voice_event_pending = false;
            (void)app_timer_stop(&app_voice_timer);
#if APP_ENABLE_AUDIO_CLASSIFIER
            app_audio_start_pending = false;
            (void)app_timer_stop(&app_audio_start_timer);
#endif
            app_log_info("Voice result notify disabled" APP_LOG_NL);
          }
        } else if ((cccd & sl_bt_gatt_notification) != 0u) {
          if (!app_voice_notify_enabled) {
            app_voice_notify_enabled = true;
            app_voice_timestamp_ms = 0u;
            app_voice_class_id = 0u;
            app_voice_dummy_tick = false;
            app_voice_event_pending = false;
#if APP_ENABLE_AUDIO_CLASSIFIER
            if (!app_audio_classifier_started && !app_audio_start_pending) {
              sc = app_timer_start(&app_audio_start_timer,
                                   APP_AUDIO_START_DELAY_MS,
                                   app_audio_start_timer_cb,
                                   NULL,
                                   false);
              app_assert_status(sc);
              app_audio_start_pending = true;
              app_log_info("Audio classifier start scheduled in %lu ms" APP_LOG_NL,
                           (unsigned long)APP_AUDIO_START_DELAY_MS);
            }
#endif
            if (app_voice_dummy_enabled) {
              sc = app_timer_start(&app_voice_timer,
                                   APP_VOICE_NOTIFY_INTERVAL_MS,
                                   app_voice_timer_cb,
                                   NULL,
                                   true);
              app_assert_status(sc);
              app_voice_dummy_tick = true;
              app_proceed();
            }
            app_log_info("Voice result notify enabled" APP_LOG_NL);
          }
        } else {
          // Keep previous state for unsupported CCCD combinations (for example indication-only).
          app_log_warning("Voice result unsupported CCCD flags=0x%04x" APP_LOG_NL, (unsigned int)cccd);
        }
      }
      break;

#if APP_ENABLE_AUDIO_CLASSIFIER
    case sl_bt_evt_system_external_signal_id:
      if (evt->data.evt_system_external_signal.extsignals & BURST_SIGNAL_MASK) {
        if (app_audio_burst_pending && app_connection != 0) {
          uint32_t total_bytes = AUDIO_BUF_SIZE_SAMPLES * 2;
          uint16_t mtu = 0;
          sl_bt_gatt_server_get_mtu(app_connection, &mtu);
          uint16_t max_payload = (mtu > 3) ? (mtu - 3) : 20;
          if (max_payload > 240) max_payload = 240;

          uint8_t loop_packets = 0;
          while (app_audio_burst_bytes_sent < total_bytes && loop_packets < 5) {
            uint8_t chunk[250];
            uint16_t len = (total_bytes - app_audio_burst_bytes_sent > max_payload) ? max_payload : (total_bytes - app_audio_burst_bytes_sent);
            
            for (uint16_t i = 0; i < len; i++) {
              uint32_t sample_idx = ((app_audio_burst_head * 2 + app_audio_burst_bytes_sent + i) / 2) % AUDIO_BUF_SIZE_SAMPLES;
              uint8_t *byte_ptr = (uint8_t *)&app_audio_burst_buf[sample_idx];
              chunk[i] = byte_ptr[(app_audio_burst_bytes_sent + i) % 2];
            }

            sl_status_t sc = sl_bt_gatt_server_send_notification(app_connection, gattdb_audio_data, len, chunk);
            
            if (sc == SL_STATUS_OK) {
              app_audio_burst_bytes_sent += len;
              app_audio_burst_packets_sent++;
              loop_packets++;
              if (app_audio_burst_packets_sent % 50 == 0) {
                app_log_info("Burst: %lu/%lu bytes sent" APP_LOG_NL, 
                             (unsigned long)app_audio_burst_bytes_sent, 
                             (unsigned long)total_bytes);
              }
            } else if (sc == SL_STATUS_NO_MORE_RESOURCE) {
              break; 
            } else {
              app_log_error("Burst Error 0x%04x at %lu bytes" APP_LOG_NL, (int)sc, (unsigned long)app_audio_burst_bytes_sent);
              app_audio_burst_pending = false;
              (void)app_timer_stop(&app_audio_burst_timer);
              break;
            }
          }
          
          if (app_audio_burst_pending && app_audio_burst_bytes_sent >= total_bytes) {
            app_audio_burst_pending = false;
            (void)app_timer_stop(&app_audio_burst_timer);
            app_log_info("Audio burst complete (%lu pkts)" APP_LOG_NL, (unsigned long)app_audio_burst_packets_sent);
          }
        }
      }
      break;
#endif

    case sl_bt_evt_system_soft_timer_id:
      // Handle other timers if any
      break;

    ///////////////////////////////////////////////////////////////////////////
    // Add additional event handlers here as your application requires!      //
    ///////////////////////////////////////////////////////////////////////////

    // -------------------------------
    // Default event handler.
    default:
      break;
  }
}

/**************************************************************************//**
 * Callback function of connection close event.
 *
 * @param[in] reason Unused parameter required by the health_thermometer component
 * @param[in] connection Unused parameter required by the health_thermometer component
 *****************************************************************************/
void sl_bt_connection_closed_cb(uint16_t reason, uint8_t connection)
{
  (void)reason;
  (void)connection;
  sl_status_t sc;

  // Stop timer.
  sc = app_timer_stop(&app_periodic_timer);
  app_assert_status(sc);
  (void)app_timer_stop(&app_voice_timer);
}

/**************************************************************************//**
 * Health Thermometer - Temperature Measurement
 * Indication changed callback
 *
 * Called when indication of temperature measurement is enabled/disabled by
 * the client.
 *****************************************************************************/
void sl_bt_ht_temperature_measurement_indication_changed_cb(uint8_t connection,
                                                            sl_bt_gatt_client_config_flag_t client_config)
{
  sl_status_t sc;
  app_connection = connection;
  // Indication or notification enabled.
  if (sl_bt_gatt_disable != client_config) {
    // Start timer used for periodic indications.
    sc = app_timer_start(&app_periodic_timer,
                         SL_BT_HT_MEASUREMENT_INTERVAL_SEC * 1000,
                         app_periodic_timer_cb,
                         NULL,
                         true);
    app_assert_status(sc);
    // Send first indication.
    app_periodic_timer_cb(&app_periodic_timer, NULL);
  }
  // Indications disabled.
  else {
    // Stop timer used for periodic indications.
    (void)app_timer_stop(&app_periodic_timer);
  }
}

/**************************************************************************//**
 * Simple Button
 * Button state changed callback
 * @param[in] handle Button event handle
 *****************************************************************************/
void sl_button_on_change(const sl_button_t *handle)
{
  // Button pressed.
  if (sl_button_get_state(handle) == SL_SIMPLE_BUTTON_PRESSED) {
    if (&sl_button_btn0 == handle) {
      app_btn0_pressed = true;
    }
  }
  // Button released.
  else if (sl_button_get_state(handle) == SL_SIMPLE_BUTTON_RELEASED) {
    if (&sl_button_btn0 == handle) {
      app_btn0_pressed = false;
    }
  }
}

/**************************************************************************//**
 * Timer callback
 * Called periodically to time periodic temperature measurements and indications.
 *****************************************************************************/
static void app_periodic_timer_cb(app_timer_t *timer, void *data)
{
  (void)data;
  (void)timer;
  sl_status_t sc;
  int32_t temperature = 0;
  uint32_t humidity = 0;
  float tmp_c = 0.0;
  // float tmp_f = 0.0;

  // Measure temperature; units are % and milli-Celsius.
  sc = sl_sensor_rht_get(&humidity, &temperature);
  if (SL_STATUS_NOT_INITIALIZED == sc) {
    app_log_info("Relative Humidity and Temperature sensor is not initialized" APP_LOG_NL);
  } else if (sc != SL_STATUS_OK) {
    app_log_warning("Invalid RHT reading: %lu %ld" APP_LOG_NL, humidity, temperature);
  }

  // button 0 pressed: overwrite temperature with -20C.
  if (app_btn0_pressed) {
    temperature = -20 * 1000;
  }

  tmp_c = (float)temperature / 1000;
  app_log_info("Temperature: %5.2f C" APP_LOG_NL, (double)tmp_c);
  // Send temperature measurement indication to connected client.
  sc = sl_bt_ht_temperature_measurement_indicate(app_connection,
                                                 temperature,
                                                 false);
  // Conversion to Fahrenheit: F = C * 1.8 + 32
  // tmp_f = (float)(temperature*18+320000)/10000;
  // app_log_info("Temperature: %5.2f F" APP_LOG_NL, tmp_f);
  // Send temperature measurement indication to connected client.
  // sc = sl_bt_ht_temperature_measurement_indicate(app_connection,
  //                                                (temperature*18+320000)/10,
  //                                                true);
  if (sc) {
    app_log_warning("Failed to send temperature measurement indication [0x%04lx]" APP_LOG_NL, sc);
  }
}

static void app_voice_timer_cb(app_timer_t *timer, void *data)
{
  (void)timer;
  (void)data;
  if (!app_voice_notify_enabled) {
    return;
  }
  app_voice_dummy_tick = true;
  app_proceed();
}

static void app_audio_start_timer_cb(app_timer_t *timer, void *data)
{
  (void)timer;
  (void)data;
#if APP_ENABLE_AUDIO_CLASSIFIER
  app_audio_start_pending = true;
  app_proceed();
#endif
}

void voice_result_publish(uint8_t class_id,
                          uint8_t score,
                          uint32_t timestamp_ms,
                          uint8_t flags)
{
  if (!APP_VOICE_CHAR_PRESENT) {
    return;
  }

  if (app_mutex_acquire()) {
    app_voice_event_class_id = class_id;
    app_voice_event_score = score;
    app_voice_event_flags = flags;
    app_voice_event_timestamp_ms = timestamp_ms;
    app_voice_event_pending = true;
    app_mutex_release();
    app_proceed();
  }
}

void ai_voice_result_publish(uint8_t class_id,
                             uint8_t score,
                             uint32_t timestamp_ms,
                             uint8_t flags)
{
  voice_result_publish(class_id, score, timestamp_ms, flags);
}

void voice_result_set_dummy_mode(bool enabled)
{
  app_voice_dummy_enabled = enabled;
  app_voice_dummy_tick = false;

  if (!enabled) {
    (void)app_timer_stop(&app_voice_timer);
    app_log_info("Voice dummy mode disabled" APP_LOG_NL);
    return;
  }

  app_log_info("Voice dummy mode enabled" APP_LOG_NL);
  if (app_voice_notify_enabled) {
    sl_status_t sc = app_timer_start(&app_voice_timer,
                                     APP_VOICE_NOTIFY_INTERVAL_MS,
                                     app_voice_timer_cb,
                                     NULL,
                                     true);
    app_assert_status(sc);
  }
}

void voice_result_publish_test_event(void)
{
  app_voice_test_timestamp_ms += APP_VOICE_NOTIFY_INTERVAL_MS;
  ai_voice_result_publish(2u, 95u, app_voice_test_timestamp_ms, 0x03u);
}

static void app_send_voice_result_payload(uint8_t class_id,
                                          uint8_t score,
                                          uint32_t timestamp_ms,
                                          uint8_t flags)
{
  sl_status_t sc;
  uint8_t payload[8];

  if (!APP_VOICE_CHAR_PRESENT || !app_voice_notify_enabled) {
    return;
  }

  payload[0] = 1u;                         // version
  payload[1] = class_id;
  payload[2] = score;
  payload[3] = flags;
  payload[4] = (uint8_t)(timestamp_ms & 0xFFu);
  payload[5] = (uint8_t)((timestamp_ms >> 8) & 0xFFu);
  payload[6] = (uint8_t)((timestamp_ms >> 16) & 0xFFu);
  payload[7] = (uint8_t)((timestamp_ms >> 24) & 0xFFu);

  sc = sl_bt_gatt_server_send_notification(app_connection,
                                           gattdb_voice_result,
                                           sizeof(payload),
                                           payload);
  if (sc != SL_STATUS_OK) {
    app_log_warning("Voice result notify failed [0x%04lx]" APP_LOG_NL, (unsigned long)sc);
    app_voice_notify_enabled = false;
    app_voice_dummy_tick = false;
    app_voice_event_pending = false;
    (void)app_timer_stop(&app_voice_timer);
    return;
  }

  app_log_info("Voice event sent: ver=%u class=%u score=%u flags=0x%02X ts=%lu raw=%02X %02X %02X %02X %02X %02X %02X %02X" APP_LOG_NL,
               payload[0],
               payload[1],
               payload[2],
               payload[3],
               (unsigned long)timestamp_ms,
               payload[0],
               payload[1],
               payload[2],
               payload[3],
               payload[4],
               payload[5],
               payload[6],
               payload[7]);
}

#ifdef SL_CATALOG_CLI_PRESENT
void hello(sl_cli_command_arg_t *arguments)
{
  (void) arguments;
  bd_addr address;
  uint8_t address_type;
  sl_status_t sc = sl_bt_gap_get_identity_address(&address, &address_type);
  app_assert_status(sc);
  app_log_info("Bluetooth %s address: %02X:%02X:%02X:%02X:%02X:%02X" APP_LOG_NL,
               address_type ? "static random" : "public device",
               address.addr[5],
               address.addr[4],
               address.addr[3],
               address.addr[2],
               address.addr[1],
               address.addr[0]);
  voice_result_publish_test_event();
  app_log_info("Published one test external voice event" APP_LOG_NL);
}
#endif // SL_CATALOG_CLI_PRESENT
#include "app.h"

void app_trigger_audio_burst(void)
{
#if APP_ENABLE_AUDIO_CLASSIFIER
  if (!app_audio_burst_pending) {
    app_get_triggered_audio_buffer(app_audio_burst_buf, &app_audio_burst_head);
    app_audio_burst_bytes_sent = 0;
    app_audio_burst_packets_sent = 0;
    app_audio_burst_pending = true;
    sl_status_t status = app_timer_start(&app_audio_burst_timer, 10, app_audio_burst_timer_cb, NULL, true);
    if (status != SL_STATUS_OK) {
        app_log_error("Failed to start burst timer [0x%04x]" APP_LOG_NL, (int)status);
        app_audio_burst_pending = false;
    }
    app_log_info("Audio burst started (head %lu)" APP_LOG_NL, (unsigned long)app_audio_burst_head);
  }
#endif
}

#if APP_ENABLE_AUDIO_CLASSIFIER
static void app_audio_burst_timer_cb(app_timer_t *timer, void *data)
{
  (void)data;
  (void)timer;
  sl_bt_external_signal(BURST_SIGNAL_MASK);
}
#endif
