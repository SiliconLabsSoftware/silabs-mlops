import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from click.testing import CliRunner

from sml.ops.cli import cli


class TestBleReceiveCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("sml.ops.cli.asyncio.run")
    @patch("sml.ops.ble.config")
    @patch("sml.ops.ble.BLEReceiver")
    def test_receive_uses_cli_options(self, mock_receiver_cls, mock_ble_config, mock_run):
        mock_receiver = MagicMock()
        mock_receiver_cls.return_value = mock_receiver

        result = self.runner.invoke(
            cli,
            [
                "ops",
                "ble",
                "receive",
                "--device-name",
                "TestBoard",
                "--device-address",
                "AA:BB:CC:DD:EE:FF",
                "--output-dir",
                "/tmp/audio",
                "--labels",
                "dog,cat,unknown",
                "--scan-timeout",
                "5",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        mock_ble_config.assert_called_once()
        kwargs = mock_ble_config.call_args.kwargs
        self.assertEqual(kwargs["device_name"], "TestBoard")
        self.assertEqual(kwargs["device_address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(kwargs["output_dir"], "/tmp/audio")
        self.assertEqual(kwargs["labels"], ["dog", "cat", "unknown"])
        self.assertEqual(kwargs["scan_timeout"], 5.0)
        mock_receiver_cls.assert_called_once()
        mock_run.assert_called_once()

    @patch("sml.ops.cli.asyncio.run")
    @patch("sml.ops.ble.config")
    @patch("sml.ops.ble.BLEReceiver")
    @patch("sml.ops.cli.Config")
    def test_receive_falls_back_to_env_config(
        self, mock_config, mock_receiver_cls, mock_ble_config, mock_run
    ):
        mock_config.BLE_DEVICE_NAME = "EnvBoard"
        mock_config.BLE_DEVICE_ADDRESS = "11:22:33:44:55:66"
        mock_config.BLE_OUTPUT_DIR = "/env/audio"
        mock_config.BLE_VOICE_RESULT_UUID = None
        mock_config.BLE_AUDIO_DATA_UUID = None
        mock_config.BLE_LABELS = "on,off"
        mock_config.BLE_SAMPLE_RATE = "8000"
        mock_config.BLE_CHANNELS = "2"
        mock_config.BLE_SAMPLE_WIDTH = "2"
        mock_config.BLE_BUFFER_SIZE = "16000"
        mock_config.BLE_SCAN_TIMEOUT = "15"

        result = self.runner.invoke(cli, ["ops", "ble", "receive"])

        self.assertEqual(result.exit_code, 0, result.output)
        kwargs = mock_ble_config.call_args.kwargs
        self.assertEqual(kwargs["device_name"], "EnvBoard")
        self.assertEqual(kwargs["device_address"], "11:22:33:44:55:66")
        self.assertEqual(kwargs["output_dir"], "/env/audio")
        self.assertEqual(kwargs["labels"], ["on", "off"])
        self.assertEqual(kwargs["sample_rate"], 8000)
        self.assertEqual(kwargs["channels"], 2)
        self.assertEqual(kwargs["buffer_size"], 16000)
        self.assertEqual(kwargs["scan_timeout"], 15.0)

    @patch("sml.ops.cli.asyncio.run", side_effect=KeyboardInterrupt)
    @patch("sml.ops.ble.config")
    @patch("sml.ops.ble.BLEReceiver")
    def test_receive_handles_keyboard_interrupt(
        self, mock_receiver_cls, mock_ble_config, mock_run
    ):
        mock_receiver = MagicMock()
        mock_receiver_cls.return_value = mock_receiver

        result = self.runner.invoke(cli, ["ops", "ble", "receive"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Stopping...", result.output)
        mock_receiver.stop.assert_called_once()

    @patch("sml.ops.cli.asyncio.run", side_effect=RuntimeError("BLE failed"))
    @patch("sml.ops.ble.config")
    @patch("sml.ops.ble.BLEReceiver")
    def test_receive_aborts_on_runtime_error(
        self, mock_receiver_cls, mock_ble_config, mock_run
    ):
        result = self.runner.invoke(cli, ["ops", "ble", "receive"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("BLE receive failed", result.output)


if __name__ == "__main__":
    unittest.main()
