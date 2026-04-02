import os
import sys
import unittest

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sml.ops.ble.config import BLEConfig

class TestBLEConfig(unittest.TestCase):
    def test_ble_config_init_minimal(self):
        """Test BLEConfig with minimum required arguments to verify defaults."""
        cfg = BLEConfig(
            device_name="TestDevice",
            device_address="00:11:22:33:44:55",
            voice_result_uuid="voice-uuid",
            audio_data_uuid="audio-uuid",
            output_dir="./output"
        )
        
        self.assertEqual(cfg.device_name, "TestDevice")
        self.assertEqual(cfg.device_address, "00:11:22:33:44:55")
        self.assertEqual(cfg.voice_result_uuid, "voice-uuid")
        self.assertEqual(cfg.audio_data_uuid, "audio-uuid")
        self.assertEqual(cfg.output_dir, "./output")
        self.assertEqual(cfg.sample_rate, 16000)
        self.assertEqual(cfg.channels, 1)
        self.assertEqual(cfg.sample_width, 2)
        self.assertEqual(cfg.labels, ["on", "off", "unknown"])
        self.assertEqual(cfg.buffer_size, 32000)

    def test_ble_config_init_full(self):
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
        
        self.assertEqual(cfg.sample_rate, 44100)
        self.assertEqual(cfg.channels, 2)
        self.assertEqual(cfg.sample_width, 4)
        self.assertEqual(cfg.labels, custom_labels)
        self.assertEqual(cfg.buffer_size, 64000)

    def test_ble_config_type_conversion(self):
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
        
        self.assertEqual(cfg.sample_rate, 22050)
        self.assertIsInstance(cfg.sample_rate, int)
        self.assertEqual(cfg.channels, 1)
        self.assertEqual(cfg.sample_width, 2)
        self.assertEqual(cfg.buffer_size, 16000)

    def test_ble_config_labels_explicit_none(self):
        """Test that passing None for labels triggers the default fallback."""
        cfg = BLEConfig(
            device_name="D",
            device_address="A",
            voice_result_uuid="V",
            audio_data_uuid="Au",
            output_dir="O",
            labels=None
        )
        self.assertEqual(cfg.labels, ["on", "off", "unknown"])

if __name__ == "__main__":
    unittest.main()
