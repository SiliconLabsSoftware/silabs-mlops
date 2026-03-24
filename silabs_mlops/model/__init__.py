"""
silabs_mlops.model
Unified public API for deployment.
"""

from .config import DeployConfig
from .deployer import RPiDeployer

__all__ = [
    # Deployment
    "DeployConfig",
    "RPiDeployer",
]