# SPDX-License-Identifier: LicenseRef-MSLA
# @file __init__.py
# @brief Public API for model profiling and firmware deployment.
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
sml.ops.model
Public API for profiling (NPU) and deployment (local or RPi / Commander).
"""

from typing import Any

from .config import DeployConfig
from .deployer import RPiDeployer

__all__ = [
    "CommanderInstaller",
    "DeployConfig",
    "LayerProfile",
    "NPUProfiler",
    "ProfileResult",
    "RPiDeployer",
    "profile",
]

_npu_profiler = None


def _get_npu_profiler():
    global _npu_profiler
    if _npu_profiler is None:
        from .profiler import NPUProfiler

        _npu_profiler = NPUProfiler()
    return _npu_profiler


def profile(
    model_path: str,
    device_id: str | None = None,
    output_dir: str | None = None,
    profiler_path: str | None = None,
    gui: bool = False,
    timeout: int = 600,
    accelerator: str = "mvpv1",
    platform: str | None = None,
    weights_paging: bool = False,
    use_simulator: bool = False,
    volume_path: str | None = None,
) -> Any:
    """Profile a model using the Silicon Labs MVP Profiler (mvp_profiler)."""
    return _get_npu_profiler().profile(
        model_path,
        device_id,
        output_dir,
        profiler_path,
        gui,
        timeout,
        accelerator,
        platform,
        weights_paging,
        use_simulator,
        volume_path,
    )


def __getattr__(name: str) -> Any:
    if name == "NPUProfiler":
        from .profiler import NPUProfiler

        return NPUProfiler
    if name == "ProfileResult":
        from .profiler import ProfileResult

        return ProfileResult
    if name == "LayerProfile":
        from .profiler import LayerProfile

        return LayerProfile
    if name == "CommanderInstaller":
        from .commander import CommanderInstaller

        return CommanderInstaller
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
