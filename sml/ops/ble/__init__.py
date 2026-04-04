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
    buffer_size: int = 32000
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
        buffer_size=buffer_size
    )
    return _config

__all__ = ["BLEConfig", "BLEReceiver", "config"]
