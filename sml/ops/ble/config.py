# SPDX-License-Identifier: LicenseRef-MSLA
# @file config.py
# @brief BLEConfig dataclass for device and audio capture settings.
#
# # License
# Copyright 2026 Silicon Laboratories Inc. www.silabs.com
#
# The licensor of this software is Silicon Laboratories Inc. Your use of this
# software is governed by the terms of Silicon Labs Master Software License
# Agreement (MSLA) available at
# www.silabs.com/about-us/legal/master-software-license-agreement. This
# software is distributed to you in Source Code format and is governed by the
# sections of the MSLA applicable to Source Code.
#
# By installing, copying or otherwise using this software, you agree to the
# terms of the MSLA.

from typing import List, Optional

class BLEConfig:
    def __init__(
        self,
        device_name: str,
        device_address: str,
        voice_result_uuid: str,
        audio_data_uuid: str,
        output_dir: str,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
        labels: Optional[List[str]] = None,
        buffer_size: int = 32000
    ):
        self.device_name = device_name
        self.device_address = device_address
        self.voice_result_uuid = voice_result_uuid
        self.audio_data_uuid = audio_data_uuid
        self.output_dir = output_dir
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.sample_width = int(sample_width)
        self.labels = labels or ["on", "off", "unknown"]
        self.buffer_size = int(buffer_size)
