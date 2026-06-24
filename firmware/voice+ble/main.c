/***************************************************************************//**
 * @file main.c
 * @brief main() function.
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

#include "sl_main_init.h"
#include "sl_main_kernel.h"

int main(void)
{
  // Initialize Silicon Labs device, system, service(s) and protocol stack(s).
  sl_main_second_stage_init();

  // app_init_bt() is invoked from internal_init_early via app_os_helper (voice_ble_controller pattern).
  app_init();

  while (sl_main_start_task_should_continue()) {
    app_process_action();
  }
}
