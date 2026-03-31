import sys
import types
import struct
import os
from unittest.mock import AsyncMock, MagicMock, patch

# ──────────────────────────────────────────────────
# STEP 1: Stub ALL non-stdlib modules
# ──────────────────────────────────────────────────

# --- numpy ---
numpy_mod = types.ModuleType("numpy")
numpy_mod.np = numpy_mod
sys.modules["numpy"] = numpy_mod

# --- bleak ---
mock_BleakClient = MagicMock(name="BleakClient")
mock_BleakScanner = MagicMock(name="BleakScanner")

bleak_mod = types.ModuleType("bleak")
bleak_mod.BleakClient = mock_BleakClient
bleak_mod.BleakScanner = mock_BleakScanner
sys.modules["bleak"] = bleak_mod

# --- sml.ops.ble (fallback path used by BLEReceiver) ---
sml_mod = types.ModuleType("sml")
sml_ops_mod = types.ModuleType("sml.ops")
sml_ble_mod = types.ModuleType("sml.ops.ble")
sml_ble_mod._config = None

sys.modules["sml"] = sml_mod
sys.modules["sml.ops"] = sml_ops_mod
sys.modules["sml.ops.ble"] = sml_ble_mod

# ──────────────────────────────────────────────────
# STEP 2: Fake package for .config and .receiver
# ──────────────────────────────────────────────────

_dir = os.path.dirname(os.path.abspath(__file__))

ble_pkg = types.ModuleType("ble_pkg")
ble_pkg.__path__ = [_dir]
ble_pkg.__package__ = "ble_pkg"
sys.modules["ble_pkg"] = ble_pkg

import importlib.util

# config.py
_config_spec = importlib.util.spec_from_file_location(
    "ble_pkg.config",
    os.path.join(_dir, "config.py"),
    submodule_search_locations=[],
)
config_mod = importlib.util.module_from_spec(_config_spec)
config_mod.__package__ = "ble_pkg"
sys.modules["ble_pkg.config"] = config_mod
_config_spec.loader.exec_module(config_mod)

BLEConfig = config_mod.BLEConfig

# receiver.py
_recv_spec = importlib.util.spec_from_file_location(
    "ble_pkg.receiver",
    os.path.join(_dir, "receiver.py"),
    submodule_search_locations=[],
)
receiver_mod = importlib.util.module_from_spec(_recv_spec)
receiver_mod.__package__ = "ble_pkg"
sys.modules["ble_pkg.receiver"] = receiver_mod
_recv_spec.loader.exec_module(receiver_mod)

BLEReceiver = receiver_mod.BLEReceiver

# ──────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────

import pytest

@pytest.fixture
def cfg():
    return BLEConfig(
        device_name="TestDevice",
        device_address="AA:BB:CC:DD:EE:FF",
        voice_result_uuid="voice-uuid",
        audio_data_uuid="audio-uuid",
        output_dir="/mock/output",
        labels=["on", "off"],
        buffer_size=10,
    )

@pytest.fixture
def rx(cfg):
    return BLEReceiver(config=cfg)

# ──────────────────────────────────────────────────
# __init__
# ──────────────────────────────────────────────────

class TestInit:

    def test_with_explicit_config(self, cfg):
        rec = BLEReceiver(config=cfg)
        assert rec.config is cfg
        assert rec.audio_buffer == bytearray()
        assert rec.current_label == "detection"
        assert rec._is_running is False

    def test_fallback_to_global_config(self, cfg):
        sml_ble_mod._config = cfg
        try:
            rec = BLEReceiver()
            assert rec.config is cfg
        finally:
            sml_ble_mod._config = None

    def test_raises_when_no_config(self):
        sml_ble_mod._config = None
        with pytest.raises(ValueError, match="No BLE configuration provided"):
            BLEReceiver()

# ──────────────────────────────────────────────────
# save_wav
# ──────────────────────────────────────────────────

class TestSaveWav:

    def test_creates_dir_opens_wav_writes_frames(self, rx):
        mock_wf = MagicMock()

        with patch.object(receiver_mod.os, "makedirs") as m_mkdirs, \
             patch.object(receiver_mod.os.path, "join",
                          return_value="/mock/output/f.wav"), \
             patch.object(receiver_mod.wave, "open") as m_wave, \
             patch("builtins.print") as m_print:

            m_wave.return_value.__enter__ = lambda self: mock_wf
            m_wave.return_value.__exit__ = MagicMock(return_value=False)

            rx.save_wav(b"abcde", "f.wav")

            m_mkdirs.assert_called_once_with("/mock/output", exist_ok=True)
            m_wave.assert_called_once_with("/mock/output/f.wav", "wb")
            mock_wf.setnchannels.assert_called_once_with(1)
            mock_wf.setsampwidth.assert_called_once_with(2)
            mock_wf.setframerate.assert_called_once_with(16000)
            mock_wf.writeframes.assert_called_once_with(b"abcde")
            m_print.assert_called_once_with("Saved: f.wav (5 bytes)")

# ──────────────────────────────────────────────────
# notification_handler
# ──────────────────────────────────────────────────

class TestNotificationHandler:

    @pytest.mark.asyncio
    async def test_audio_uuid_buffer_below_threshold(self, rx):
        sender = MagicMock(uuid="audio-uuid")
        await rx.notification_handler(sender, b"abc")
        assert rx.audio_buffer == bytearray(b"abc")

    @pytest.mark.asyncio
    async def test_audio_uuid_buffer_reaches_threshold(self, rx):
        sender = MagicMock(uuid="AUDIO-UUID")
        data = b"0123456789X"

        with patch.object(rx, "save_wav") as m_save, \
             patch.object(receiver_mod.time, "time", return_value=5000.0), \
             patch("builtins.print") as m_print:

            await rx.notification_handler(sender, data)

            m_save.assert_called_once_with(
                bytearray(b"0123456789"), "detection_5000.wav"
            )
            assert rx.audio_buffer == bytearray()
            m_print.assert_called_once_with("--- Ready for next detection ---")

    @pytest.mark.asyncio
    async def test_voice_uuid_known_class_id(self, rx):
        sender = MagicMock(uuid="VOICE-UUID")
        payload = struct.pack("<BBBB I", 1, 1, 80, 0, 999)

        with patch("builtins.print") as m_print:
            await rx.notification_handler(sender, payload)

        assert rx.current_label == "off"
        assert rx.audio_buffer == bytearray()
        m_print.assert_called_once_with(
            "\n[EVENT] Firmware Detected: OFF (Score: 80)"
        )

    @pytest.mark.asyncio
    async def test_voice_uuid_unknown_class_id(self, rx):
        sender = MagicMock(uuid="voice-uuid")
        payload = struct.pack("<BBBB I", 1, 99, 50, 0, 0)

        with patch("builtins.print"):
            await rx.notification_handler(sender, payload)

        assert rx.current_label == "unknown"

    @pytest.mark.asyncio
    async def test_unrelated_uuid_ignored(self, rx):
        sender = MagicMock(uuid="other-uuid")
        await rx.notification_handler(sender, b"data")
        assert rx.audio_buffer == bytearray()

# ──────────────────────────────────────────────────
# start()
# ──────────────────────────────────────────────────

def _client_ctx(mock_client):
    class _Ctx:
        async def __aenter__(self):
            return mock_client
        async def __aexit__(self, *_):
            pass
    return _Ctx()

class TestStart:

    @pytest.mark.asyncio
    async def test_device_not_found(self, rx):
        mock_scanner = MagicMock()
        mock_scanner.find_device_by_address = AsyncMock(return_value=None)
        mock_scanner.find_device_by_filter = AsyncMock(return_value=None)

        with patch.object(receiver_mod, "BleakScanner", mock_scanner), \
             patch("builtins.print") as m_print:

            await rx.start()
            m_print.assert_any_call("Could not find device.")

    @pytest.mark.asyncio
    async def test_found_by_address(self, rx):
        dev = MagicMock()
        dev.name = "TestDevice"
        client = AsyncMock()

        mock_scanner = MagicMock()
        mock_scanner.find_device_by_address = AsyncMock(return_value=dev)

        async def _stop_on_sleep(_):
            rx.stop()

        with patch.object(receiver_mod, "BleakScanner", mock_scanner), \
             patch.object(receiver_mod, "BleakClient",
                          return_value=_client_ctx(client)), \
             patch.object(receiver_mod.asyncio, "sleep",
                          side_effect=_stop_on_sleep), \
             patch("builtins.print") as m_print:

            await rx.start()

            client.start_notify.assert_any_call(
                rx.config.voice_result_uuid, rx.notification_handler)
            client.start_notify.assert_any_call(
                rx.config.audio_data_uuid, rx.notification_handler)
            m_print.assert_any_call(f"Connected to {dev.name}")
            m_print.assert_any_call("\n--- Subscribed to Voice Events ---")

    @pytest.mark.asyncio
    async def test_found_by_filter_fallback(self, rx):
        dev = MagicMock()
        dev.name = "TestDevice"
        client = AsyncMock()

        mock_scanner = MagicMock()
        mock_scanner.find_device_by_address = AsyncMock(return_value=None)
        mock_scanner.find_device_by_filter = AsyncMock(return_value=dev)

        async def _stop_on_sleep(_):
            rx.stop()

        with patch.object(receiver_mod, "BleakScanner", mock_scanner), \
             patch.object(receiver_mod, "BleakClient",
                          return_value=_client_ctx(client)), \
             patch.object(receiver_mod.asyncio, "sleep",
                          side_effect=_stop_on_sleep), \
             patch("builtins.print"):

            await rx.start()

            client.start_notify.assert_any_call(
                rx.config.voice_result_uuid, rx.notification_handler)

# ──────────────────────────────────────────────────
# stop()
# ──────────────────────────────────────────────────

class TestStop:

    def test_stop_sets_flag_false(self, rx):
        rx._is_running = True
        rx.stop()
        assert rx._is_running is False
