import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from click.testing import CliRunner

from sml.ops.cli import cli


class TestIngestCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("sml.ops.cli.DataIngestor")
    @patch("sml.ops.cli.Config")
    def test_one_shot_ingest_with_file(self, mock_config, mock_ingestor_cls):
        mock_config.ZEROBUS_SERVER_ENDPOINT = "ep"
        mock_config.ZEROBUS_WORKSPACE_URL = "https://ws"
        mock_config.ZEROBUS_TABLE_NAME = "t"
        mock_config.ZEROBUS_CLIENT_ID = "id"
        mock_config.ZEROBUS_CLIENT_SECRET = "sec"

        mock_ingestor = MagicMock()
        mock_ingestor.ingest.return_value = True
        mock_ingestor_cls.return_value = mock_ingestor

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('[{"a": 1}]')
            path = f.name

        try:
            result = self.runner.invoke(cli, ["ops", "ingest", "--file", path])
            self.assertEqual(result.exit_code, 0, result.output)
            mock_ingestor.ingest.assert_called_once()
        finally:
            os.unlink(path)

    def test_ingest_without_file_shows_usage_error(self):
        result = self.runner.invoke(cli, ["ops", "ingest"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Missing required option '--file'", result.output)

    @patch("sml.ops.data.ingest.service.IngestionService")
    @patch("sml.ops.cli.Config")
    def test_ingest_serve_resolves_options(self, mock_config, mock_service_cls):
        mock_config.ZEROBUS_SERVER_ENDPOINT = "ep"
        mock_config.ZEROBUS_WORKSPACE_URL = "https://ws"
        mock_config.ZEROBUS_TABLE_NAME = "t"
        mock_config.ZEROBUS_CLIENT_ID = "id"
        mock_config.ZEROBUS_CLIENT_SECRET = "sec"
        mock_config.BLE_OUTPUT_DIR = "/tmp/audio"
        mock_config.DATABRICKS_VOLUME_PATH = "/Volumes/main/default/data"
        mock_config.COMMANDER_PATH = None
        mock_config.NUM_WORKERS = "2"

        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.wait.side_effect = KeyboardInterrupt

        result = self.runner.invoke(
            cli,
            [
                "ops",
                "ingest",
                "serve",
                "--pattern",
                "*.wav",
                "--workers",
                "3",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        kwargs = mock_service_cls.call_args.kwargs
        self.assertEqual(kwargs["monitor_dir"], "/tmp/audio")
        self.assertEqual(kwargs["volume_path"], "/Volumes/main/default/data")
        self.assertEqual(kwargs["pattern"], "*.wav")
        self.assertEqual(kwargs["workers"], 3)
        mock_service.start.assert_called_once()


class TestBleReceiveCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("sml.ops.cli.asyncio.run")
    @patch("sml.ops.ble.config")
    @patch("sml.ops.ble.BLEReceiver")
    def test_receive_uses_cli_options(
        self, mock_receiver_cls, mock_ble_config, mock_run
    ):
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
        mock_config.BLE_VOICE_SERVICE_UUID = None
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
        self.assertEqual(
            kwargs["voice_service_uuid"], "f7ee5e0c-1882-4c85-a6f1-8d6f81f10901"
        )

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


class TestDeployCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("sml.ops.cli.RPiDeployer")
    def test_deploy_local_without_rpi_host(self, mock_deployer_cls):
        mock_deployer = MagicMock()
        mock_deployer_cls.return_value = mock_deployer

        with tempfile.NamedTemporaryFile(suffix=".s37", delete=False) as f:
            f.write(b"fw")
            path = f.name

        try:
            result = self.runner.invoke(cli, ["ops", "deploy", "--uri", path])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("local deployment", result.output)
            kwargs = mock_deployer_cls.call_args.kwargs
            self.assertIsNone(kwargs["rpi_host"])
            self.assertEqual(kwargs["local_file_path"], path)
            mock_deployer.deploy.assert_called_once()
        finally:
            os.unlink(path)

    @patch("sml.ops.cli.RPiDeployer")
    def test_deploy_remote_with_rpi_host(self, mock_deployer_cls):
        mock_deployer = MagicMock()
        mock_deployer_cls.return_value = mock_deployer

        with tempfile.NamedTemporaryFile(suffix=".s37", delete=False) as f:
            f.write(b"fw")
            path = f.name

        try:
            result = self.runner.invoke(
                cli,
                [
                    "ops",
                    "deploy",
                    "--uri",
                    path,
                    "--rpi-host",
                    "192.168.1.10",
                    "--rpi-user",
                    "pi",
                ],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("RPi deployment", result.output)
            kwargs = mock_deployer_cls.call_args.kwargs
            self.assertEqual(kwargs["rpi_host"], "192.168.1.10")
            self.assertEqual(kwargs["rpi_user"], "pi")
            mock_deployer.deploy.assert_called_once()
        finally:
            os.unlink(path)

    def test_deploy_remote_path_requires_rpi_host(self):
        with tempfile.NamedTemporaryFile(suffix=".s37", delete=False) as f:
            f.write(b"fw")
            path = f.name

        try:
            result = self.runner.invoke(
                cli,
                ["ops", "deploy", "--uri", path, "--remote-path", "/tmp/fw.s37"],
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("--remote-path requires --rpi-host", result.output)
        finally:
            os.unlink(path)


class TestProfileCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("sml.ops.model.profile")
    def test_profile_simulate_passes_use_simulator(self, mock_profile):
        mock_result = MagicMock()
        mock_result.output_dir = "/tmp/profiling"
        mock_profile.return_value = mock_result

        with tempfile.NamedTemporaryFile(suffix=".tflite", delete=False) as f:
            f.write(b"model")
            path = f.name

        try:
            result = self.runner.invoke(
                cli, ["ops", "profile", "--model", path, "--simulate"]
            )
            self.assertEqual(result.exit_code, 0, result.output)
            kwargs = mock_profile.call_args.kwargs
            self.assertTrue(kwargs["use_simulator"])
            self.assertIsNone(kwargs["device_id"])
        finally:
            os.unlink(path)

    @patch("sml.ops.model.profile")
    def test_profile_defaults_to_hardware(self, mock_profile):
        mock_result = MagicMock()
        mock_result.output_dir = "/tmp/profiling"
        mock_profile.return_value = mock_result

        with tempfile.NamedTemporaryFile(suffix=".tflite", delete=False) as f:
            f.write(b"model")
            path = f.name

        try:
            result = self.runner.invoke(cli, ["ops", "profile", "--model", path])
            self.assertEqual(result.exit_code, 0, result.output)
            kwargs = mock_profile.call_args.kwargs
            self.assertFalse(kwargs["use_simulator"])
        finally:
            os.unlink(path)

    def test_profile_simulate_rejects_device(self):
        with tempfile.NamedTemporaryFile(suffix=".tflite", delete=False) as f:
            f.write(b"model")
            path = f.name

        try:
            result = self.runner.invoke(
                cli,
                [
                    "ops",
                    "profile",
                    "--model",
                    path,
                    "--simulate",
                    "--device",
                    "123456789",
                ],
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("--simulate cannot be used with", result.output)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
