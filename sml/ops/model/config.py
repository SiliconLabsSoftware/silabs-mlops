# SPDX-License-Identifier: LicenseRef-MSLA
# @file config.py
# @brief Configuration for model deployment.
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

"""
Configuration for model deployment.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeployConfig:
    """
    Configuration for deploying models to embedded devices using Simplicity Commander.

    Attributes:
        model_uri: The MLflow Model Registry URI or Artifact Path.
        device_ip: Optional target device IP address.
        interface: Connection interface (e.g., "swd", "jtag"). Default "swd".
        verify: Whether to verify the flash after writing.
        halt: Whether to halt the core after flashing.
        noverify: Whether to skip verification (useful for IP flashing).
    """

    model_uri: str
    device_ip: Optional[str] = None
    interface: str = "swd"
    verify: bool = True
    halt: bool = False
    noverify: bool = False
    rpi_host: Optional[str] = None
    rpi_user: Optional[str] = "pi"
