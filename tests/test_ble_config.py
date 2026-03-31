import pytest
from sml.ops.ble import BLEConfig  

def test_ble_config_init_minimal():
    """Test BLEConfig with minimum required arguments to verify defaults."""
    cfg = BLEConfig(
        device_name="TestDevice",
        device_address="00:11:22:33:44:55",
        voice_result_uuid="voice-uuid",
        audio_data_uuid="audio-uuid",
        output_dir="./output"
    )
    
    assert cfg.device_name == "TestDevice"
    assert cfg.device_address == "00:11:22:33:44:55"
    assert cfg.voice_result_uuid == "voice-uuid"
    assert cfg.audio_data_uuid == "audio-uuid"
    assert cfg.output_dir == "./output"
    
    assert cfg.sample_rate == 16000
    assert cfg.channels == 1
    assert cfg.sample_width == 2
    assert cfg.labels == ["on", "off", "unknown"]
    assert cfg.buffer_size == 32000

def test_ble_config_init_full():
    """Test BLEConfig with all parameters provided to verify custom overrides."""
    custom_labels = ["start", "stop", "action"]
    cfg = BLEConfig(
        device_name="FullDevice",
        device_address="AA:BB:CC:DD:EE:FF",
        voice_result_uuid="v-uuid-2",
        audio_data_uuid="a-uuid-2",
        output_dir="./custom_out",
        sample_rate=44100,
        channels=2,
        sample_width=4,
        labels=custom_labels,
        buffer_size=64000
    )
    
    assert cfg.sample_rate == 44100
    assert cfg.channels == 2
    assert cfg.sample_width == 4
    assert cfg.labels == custom_labels
    assert cfg.buffer_size == 64000

def test_ble_config_type_conversion():
    """Test that numeric string inputs are correctly converted to integers."""
    cfg = BLEConfig(
        device_name="D",
        device_address="A",
        voice_result_uuid="V",
        audio_data_uuid="Au",
        output_dir="O",
        sample_rate="22050",
        channels="1",
        sample_width="2",
        buffer_size="16000"
    )
    
    assert cfg.sample_rate == 22050
    assert isinstance(cfg.sample_rate, int)
    assert cfg.channels == 1
    assert cfg.sample_width == 2
    assert cfg.buffer_size == 16000

def test_ble_config_labels_explicit_none():
    """Test that passing None for labels triggers the default fallback."""
    cfg = BLEConfig(
        device_name="D",
        device_address="A",
        voice_result_uuid="V",
        audio_data_uuid="Au",
        output_dir="O",
        labels=None
    )
    assert cfg.labels == ["on", "off", "unknown"]
