# SPDX-License-Identifier: LicenseRef-MSLA
# @file __init__.py
# @brief BLE module with global config and BLEReceiver exports.
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

from typing import Optional, List
from .config import BLEConfig
from .receiver import BLEReceiver

# Module-level configuration storage
_config: Optional[BLEConfig] = None


def config(
    device_name: str,
    device_address: str,
    voice_result_uuid: str,
    audio_data_uuid: str,
    output_dir: str,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
    labels: Optional[List[str]] = None,
    buffer_size: int = 32000,
    scan_timeout: float = 10.0,
) -> BLEConfig:
    """
    Configure the BLE hardware settings globally.
    """
    global _config
    _config = BLEConfig(
        device_name=device_name,
        device_address=device_address,
        voice_result_uuid=voice_result_uuid,
        audio_data_uuid=audio_data_uuid,
        output_dir=output_dir,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        labels=labels,
        buffer_size=buffer_size,
        scan_timeout=scan_timeout,
    )
    return _config


__all__ = ["BLEConfig", "BLEReceiver", "config"]
