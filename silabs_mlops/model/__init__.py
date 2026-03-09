"""
silabs_mlops.model
Unified public API for deployment and profiling (no compilation).
"""

from typing import Optional

from .config import DeployConfig
from .deployer import ModelDeployer
from .registry import ArtifactRegistry, ArtifactNotFoundError
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
) -> ProfileResult:
    """
    Profile a model using the Silicon Labs NPU Toolkit (mvp_profiler).

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
        model_path=model_path,
        device_id=device_id,
        output_dir=output_dir,
        profiler_path=profiler_path,
        gui=gui,
        timeout=timeout,
        accelerator=accelerator,
        platform=platform,
        weights_paging=weights_paging,
        use_simulator=use_simulator,
    )


__all__ = [
    # Deployment
    "DeployConfig",
    "ModelDeployer",
    # Registry
    "ArtifactRegistry",
    "ArtifactNotFoundError",
    # Profiler
    "NPUProfiler",
    "ProfileResult",
    "LayerProfile",
    "profile",
]