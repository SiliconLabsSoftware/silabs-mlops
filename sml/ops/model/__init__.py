"""
sml.ops.model
Unified public API for profiling.
"""

from typing import Optional

from .profiler import NPUProfiler, ProfileResult, LayerProfile

# Singleton profiler instance used by the package-level `profile()` helper.
_profiler = NPUProfiler()


def profile(
    model_path: str,
    device_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    profiler_path: Optional[str] = None,
    gui: bool = False,
    timeout: int = 600,
    accelerator: str = "mvpv1",
    platform: Optional[str] = None,
    weights_paging: bool = False,
    use_simulator: bool = False,
    volume_path: Optional[str] = None,
) -> ProfileResult:
    """
    Profile a model using the Silicon Labs MVP Profiler (mvp_profiler).

    Args:
        model_path:     Path to the .tflite or compiled .zip model file.
        device_id:      Optional J-Link serial number or IP address for on-target profiling.
        output_dir:     Directory to save profiling artifacts.
        profiler_path:  Explicit path to profiler binary (if not in PATH).
        gui:            Launch the Profiler GUI (http://localhost:8080).
        timeout:        Subprocess timeout in seconds.
        accelerator:    Hardware accelerator target, e.g., "mvpv1".
        platform:       Target hardware platform/part/family (optional).
        weights_paging: Enable weights paging in profiler (if supported).
        use_simulator:  Run on simulator instead of hardware (if supported).

    Returns:
        ProfileResult with parsed profiling metrics.
    """
    return _profiler.profile(
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


__all__ = [
    "NPUProfiler",
    "ProfileResult",
    "LayerProfile",
    "profile",
]
