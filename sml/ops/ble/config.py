from typing import List, Optional

class BLEConfig:
    def __init__(
        self,
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
    ):
        self.device_name = device_name
        self.device_address = device_address
        self.voice_result_uuid = voice_result_uuid
        self.audio_data_uuid = audio_data_uuid
        self.output_dir = output_dir
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.sample_width = int(sample_width)
        self.labels = labels or ["on", "off", "unknown"]
        self.buffer_size = int(buffer_size)
