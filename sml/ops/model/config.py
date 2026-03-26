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
        commander_path: Optional path to the Simplicity Commander executable.
        device_ip: Optional target device IP address.
        interface: Connection interface (e.g., "swd", "jtag"). Default "swd".
        verify: Whether to verify the flash after writing.
        halt: Whether to halt the core after flashing.
        noverify: Whether to skip verification (useful for IP flashing).
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
