import os
import sys
import unittest
import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sml.ops.ble
from sml.ops.ble import config, BLEConfig, BLEReceiver

class TestBLEConfig(unittest.TestCase):
    def test_ble_config_init_minimal(self):
        """Test BLEConfig defaults."""
        cfg = BLEConfig(
            device_name="Dev", device_address="Add",
            voice_result_uuid="v-uuid", audio_data_uuid="a-uuid",
            output_dir="./out"
        )
        self.assertEqual(cfg.sample_rate, 16000)
        self.assertEqual(cfg.labels, ["on", "off", "unknown"])

    def test_ble_config_init_full(self):
        """Test BLEConfig with all params."""
        cfg = BLEConfig(
            "D", "A", "V", "Au", "O",
            sample_rate=44100, channels=2, sample_width=4,
            labels=["a", "b"], buffer_size=10
        )
        self.assertEqual(cfg.sample_rate, 44100)
        self.assertEqual(cfg.labels, ["a", "b"])

    def test_ble_config_type_conversion(self):
        """Test numeric string conversion."""
        cfg = BLEConfig("D", "A", "V", "Au", "O", sample_rate="22050")
        self.assertEqual(cfg.sample_rate, 22050)

    def test_ble_config_labels_none(self):
        """Test None for labels handled gracefully."""
        cfg = BLEConfig("D", "A", "V", "Au", "O", labels=None)
        self.assertIsNotNone(cfg.labels)

class TestBLEInit(unittest.TestCase):
    def setUp(self):
        sml.ops.ble._config = None

    def test_config_function_updates_global(self):
        """Test global config() helper."""
        cfg = config("D", "A", "V", "Au", "O")
        self.assertIsInstance(cfg, BLEConfig)
        self.assertIs(sml.ops.ble._config, cfg)

    def test_dunder_all(self):
        """Test package exports."""
        self.assertIn("BLEConfig", sml.ops.ble.__all__)
        self.assertIn("BLEReceiver", sml.ops.ble.__all__)

    def test_imports(self):
        """Test package imports."""
        self.assertIs(sml.ops.ble.BLEConfig, BLEConfig)

class TestBLEReceiver(unittest.TestCase):
    def setUp(self):
        self.config = BLEConfig("D", "A", "V", "Au", "./out", buffer_size=10)
        self.receiver = BLEReceiver(config=self.config)
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def test_receiver_init_success(self):
        """Test init with config."""
        self.assertEqual(self.receiver.config, self.config)

    @patch("sml.ops.ble._config")
    def test_receiver_init_fallback(self, mock_global_config):
        """Test fallback to global config."""
        with patch("sml.ops.ble._config", self.config):
            rx = BLEReceiver()
            self.assertEqual(rx.config, self.config)

    @patch("sml.ops.ble._config", None)
    def test_receiver_init_no_config_error(self):
        """Test initialization error when no config is provided."""
        with self.assertRaises(ValueError):
            BLEReceiver()

    @patch("wave.open")
    @patch("os.makedirs")
    def test_save_wav(self, mock_makedirs, mock_wave_open):
        """Test WAV file saving."""
        mock_wf = MagicMock()
        mock_wave_open.return_value.__enter__.return_value = mock_wf
        self.receiver.save_wav(b"data", "test.wav")
        mock_wave_open.assert_called_once()

    def test_notification_handler_audio(self):
        """Test audio data notification handling."""
        sender = MagicMock(uuid=self.config.audio_data_uuid)
        self.loop.run_until_complete(self.receiver.notification_handler(sender, b"123"))
        self.assertEqual(self.receiver.audio_buffer, b"123")
        
        with patch.object(self.receiver, "save_wav") as mock_save:
            self.loop.run_until_complete(self.receiver.notification_handler(sender, b"4567890")) # total 3 + 7 = 10
            mock_save.assert_called_once()
            self.assertEqual(self.receiver.audio_buffer, bytearray())

    def test_notification_handler_voice_result(self):
        """Test voice result notification handling."""
        sender = MagicMock(uuid=self.config.voice_result_uuid)
        data = struct.pack("<BBBB I", 1, 1, 80, 0, 1234) # index 1 is 'off'
        self.loop.run_until_complete(self.receiver.notification_handler(sender, data))
        self.assertEqual(self.receiver.current_label, "off")

    def test_notification_handler_unknown_label(self):
        """Test unknown label index in voice result."""
        sender = MagicMock(uuid=self.config.voice_result_uuid)
        data = struct.pack("<BBBB I", 1, 10, 80, 0, 1234)
        self.loop.run_until_complete(self.receiver.notification_handler(sender, data))
        self.assertEqual(self.receiver.current_label, "unknown")

    def test_notification_handler_unmatched(self):
        """Test notification for unmatched UUID."""
        sender = MagicMock(uuid="other")
        self.loop.run_until_complete(self.receiver.notification_handler(sender, b"data"))
        self.assertEqual(self.receiver.audio_buffer, bytearray())

    @patch("sml.ops.ble.receiver.BleakScanner.find_device_by_address", new_callable=AsyncMock)
    @patch("sml.ops.ble.receiver.BleakScanner.find_device_by_filter", new_callable=AsyncMock)
    @patch("builtins.print")
    def test_start_not_found(self, mock_print, mock_filter, mock_address):
        """Test scanner failing to find device."""
        mock_address.return_value = None
        mock_filter.return_value = None
        self.loop.run_until_complete(self.receiver.start())
        mock_print.assert_any_call("Could not find device.")

    @patch("sml.ops.ble.receiver.BleakScanner.find_device_by_address", new_callable=AsyncMock)
    @patch("sml.ops.ble.receiver.BleakClient")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    def test_start_success(self, mock_sleep, mock_client_class, mock_address):
        """Test successful connection and notification setup."""
        mock_device = MagicMock()
        mock_address.return_value = mock_device
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_sleep.side_effect = lambda x: self.receiver.stop()
        
        self.loop.run_until_complete(self.receiver.start())
        mock_client.start_notify.assert_called()

    def test_stop(self):
        """Test stopping the receiver."""
        self.receiver._is_running = True
        self.receiver.stop()
        self.assertFalse(self.receiver._is_running)

if __name__ == "__main__":
    unittest.main()
