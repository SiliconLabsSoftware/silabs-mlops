import os
import sys
import unittest
import asyncio
import struct
import time
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sml.ops.ble.receiver import BLEReceiver
from sml.ops.ble.config import BLEConfig
import sml.ops.ble


class TestBLEReceiver(unittest.TestCase):
    def setUp(self):
        self.config = BLEConfig(
            device_name="TestDevice",
            device_address="00:11:22:33:44:55",
            voice_result_uuid="voice-uuid",
            audio_data_uuid="audio-uuid",
            output_dir="./test_output",
            labels=["on", "off", "unknown"],
            buffer_size=10,
        )
        self.receiver = BLEReceiver(config=self.config)
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def test_receiver_init_with_config(self):
        self.assertEqual(self.receiver.config, self.config)
        self.assertEqual(self.receiver.audio_buffer, bytearray())
        self.assertEqual(self.receiver.current_label, "detection")
        self.assertFalse(self.receiver._is_running)

    @patch("sml.ops.ble._config")
    def test_receiver_init_fallback(self, mock_global_config):
        # Setup the mock to return our config when accessed
        with patch("sml.ops.ble._config", self.config):
            rx = BLEReceiver()
            self.assertEqual(rx.config, self.config)

    @patch("sml.ops.ble._config", None)
    def test_receiver_init_no_config_error(self):
        with self.assertRaises(ValueError):
            BLEReceiver()

    @patch("wave.open")
    @patch("os.makedirs")
    def test_save_wav(self, mock_makedirs, mock_wave_open):
        mock_wf = MagicMock()
        mock_wave_open.return_value.__enter__.return_value = mock_wf

        self.receiver.save_wav(b"testdata", "test.wav")

        mock_makedirs.assert_called_once_with(self.config.output_dir, exist_ok=True)
        mock_wave_open.assert_called_once()
        mock_wf.writeframes.assert_called_with(b"testdata")

    def test_notification_handler_audio_data(self):
        sender = MagicMock()
        sender.uuid = self.config.audio_data_uuid
        data = b"012345"

        # Below buffer size
        self.loop.run_until_complete(self.receiver.notification_handler(sender, data))
        self.assertEqual(self.receiver.audio_buffer, data)

        # Reaching buffer size
        with patch.object(self.receiver, "save_wav") as mock_save_wav:
            self.loop.run_until_complete(
                self.receiver.notification_handler(sender, b"6789")
            )  # Total 10
            mock_save_wav.assert_called_once()
            self.assertEqual(self.receiver.audio_buffer, bytearray())

    def test_notification_handler_voice_result(self):
        sender = MagicMock()
        sender.uuid = self.config.voice_result_uuid
        data = struct.pack("<BBBB I", 1, 1, 80, 0, 1234)

        self.loop.run_until_complete(self.receiver.notification_handler(sender, data))
        self.assertEqual(self.receiver.current_label, "off")
        self.assertEqual(self.receiver.audio_buffer, bytearray())

    def test_notification_handler_voice_result_unknown(self):
        sender = MagicMock()
        sender.uuid = self.config.voice_result_uuid
        data = struct.pack("<BBBB I", 1, 10, 80, 0, 1234)

        self.loop.run_until_complete(self.receiver.notification_handler(sender, data))
        self.assertEqual(self.receiver.current_label, "unknown")

    def test_notification_handler_unmatched_uuid(self):
        sender = MagicMock()
        sender.uuid = "unrelated-uuid"

        self.loop.run_until_complete(
            self.receiver.notification_handler(sender, b"data")
        )
        self.assertEqual(self.receiver.audio_buffer, bytearray())

    @patch(
        "sml.ops.ble.receiver.BleakScanner.find_device_by_address",
        new_callable=AsyncMock,
    )
    @patch(
        "sml.ops.ble.receiver.BleakScanner.find_device_by_filter",
        new_callable=AsyncMock,
    )
    @patch("builtins.print")
    def test_start_device_not_found(self, mock_print, mock_filter, mock_address):
        mock_address.return_value = None
        mock_filter.return_value = None

        self.loop.run_until_complete(self.receiver.start())
        self.assertFalse(self.receiver._is_running)
        mock_print.assert_any_call("Could not find device.")

    @patch(
        "sml.ops.ble.receiver.BleakScanner.find_device_by_address",
        new_callable=AsyncMock,
    )
    @patch("sml.ops.ble.receiver.BleakClient")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    def test_start_success(self, mock_sleep, mock_client_class, mock_address):
        mock_device = MagicMock()
        mock_device.name = "TestDevice"
        mock_address.return_value = mock_device

        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock sleep to stop the loop after one iteration
        mock_sleep.side_effect = lambda x: self.receiver.stop()

        self.loop.run_until_complete(self.receiver.start())

        self.assertFalse(self.receiver._is_running)
        mock_client.start_notify.assert_called()

    def test_stop(self):
        self.receiver._is_running = True
        self.receiver.stop()
        self.assertFalse(self.receiver._is_running)


if __name__ == "__main__":
    unittest.main()
