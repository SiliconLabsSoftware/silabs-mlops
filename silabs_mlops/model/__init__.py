from typing import Optional
from .config import DeployConfig
from .deployer import ModelDeployer
from .registry import ArtifactRegistry, ArtifactNotFoundError
from .profiler import NPUProfiler, ProfileResult, LayerProfile

# Profiler instance
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
    use_simulator: bool = False
) -> ProfileResult:
    """
    Profile a model using the Silicon Labs NPU Toolkit (mvp_profiler).

    Args:
        model_path:     Path to the .tflite or compiled .zip model file.
        device_id:      Optional J-Link serial number or IP address.
        output_dir:     Directory to save profiling artifacts.
        profiler_path:  Explicit path to profiler binary.
        gui:            Launch the Profiler GUI (http://localhost:8080).
        timeout:        Subprocess timeout.
        accelerator:    Hardware accelerator target.
        platform:       Target hardware platform.
        weights_paging: Enable weights paging.
        use_simulator:  Run without hardware.

    Returns:
        ProfileResult containing parsed profiling metrics.
    """
    return _profiler.profile(
        model_path, device_id, output_dir, profiler_path, gui,
        timeout, accelerator, platform, weights_paging, use_simulator
    )


__all__ = [
    "DeployConfig",
    "ModelDeployer",
    "ArtifactRegistry",
    "ArtifactNotFoundError",
    "NPUProfiler",
    "ProfileResult",
    "LayerProfile",
    "profile",
]