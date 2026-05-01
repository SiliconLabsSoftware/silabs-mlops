# SPDX-License-Identifier: LicenseRef-MSLA
# @file __init__.py
# @brief Package version and lazy ops submodules.
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

__version__ = "0.1.0"

# Submodules `data` and `model` are imported lazily via `from sml.ops import data` /
# `from sml.ops import model` so the CLI (`python -m sml.ops.cli`) does not pull
# TensorFlow / ZeroBus / profiler until those subsystems are used.

__all__ = ["__version__"]

