"""
Configuration for Model Deployment.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeployConfig:
    """
    Configuration for deploying models to embedded devices using Simplicity Commander.
    
    Attributes:
        model_uri: The MLflow Model Registry URI or Artifact Path (e.g., "models:/my_model/Production", "runs:/<run_id>/model.s37").
        commander_path: Optional path to the Simplicity Commander executable. If not provided, it will be auto-discovered.
        device_ip: Optional target device IP address.
        interface: Connection interface (e.g., "swd", "jtag"). Default "swd".
        verify: Whether to verify the flash after writing. Default True.
        halt: Whether to halt the core after flashing. Default False.
        noverify: Whether to skip verification (useful for IP flashing). Default False.
    """
    model_uri: str
    commander_path: Optional[str] = "commander"
    device_ip: Optional[str] = None
    interface: str = "swd"
    verify: bool = True
    halt: bool = False
    noverify: bool = False
    rpi_host: Optional[str] = None
    rpi_user: Optional[str] = "pi"
