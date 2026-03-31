"""
Unit tests for ble/__init__.py 
"""

import sys
import types
import os
import pytest
from unittest.mock import MagicMock

# ──────────────────────────────────────────────────
# MOCK Submodules injected locally into sys.modules
# ──────────────────────────────────────────────────
config_mod = types.ModuleType("pkg.config")
config_mod.__package__ = "pkg"
class MockBLEConfig:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if getattr(self, "sample_rate", None) is None: self.sample_rate = 16000
        if getattr(self, "channels", None) is None: self.channels = 1
        if getattr(self, "sample_width", None) is None: self.sample_width = 2
        if getattr(self, "labels", None) is None: self.labels = ["on", "off", "unknown"]
        if getattr(self, "buffer_size", None) is None: self.buffer_size = 32000
config_mod.BLEConfig = MockBLEConfig
sys.modules["pkg.config"] = config_mod

receiver_mod = types.ModuleType("pkg.receiver")
receiver_mod.__package__ = "pkg"
receiver_mod.BLEReceiver = MagicMock()
sys.modules["pkg.receiver"] = receiver_mod

# ──────────────────────────────────────────────────
# IMPORT Module under test
# ──────────────────────────────────────────────────
import sml.ops.ble as pkg   

# ──────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────

class TestModuleLevelImports:
    def test_bleconfig_re_exported(self):
        assert pkg.BLEConfig is MockBLEConfig

    def test_blereceiver_re_exported(self):
        assert pkg.BLEReceiver is receiver_mod.BLEReceiver

class TestModuleLevelState:
    def test_initial_config_is_none(self):
        assert hasattr(pkg, "_config")

class TestConfigFunction:
    def test_config_returns_bleconfig(self):
        result = pkg.config(
            device_name="Dev", device_address="11:22",
            voice_result_uuid="v", audio_data_uuid="a", output_dir="/out",
        )
        assert isinstance(result, MockBLEConfig)

    def test_config_stores_global(self):
        result = pkg.config(
            device_name="Dev", device_address="11:22",
            voice_result_uuid="v", audio_data_uuid="a", output_dir="/out",
        )
        assert pkg._config is result

    def test_config_passes_defaults(self):
        cfg = pkg.config(
            device_name="D", device_address="AA:BB",
            voice_result_uuid="v", audio_data_uuid="a", output_dir="/tmp",
        )
        assert cfg.sample_rate == 16000
        assert cfg.channels == 1
        assert cfg.sample_width == 2
        assert cfg.labels == ["on", "off", "unknown"]
        assert cfg.buffer_size == 32000

    def test_config_custom_values(self):
        cfg = pkg.config(
            device_name="Custom", device_address="FF:EE",
            voice_result_uuid="v1", audio_data_uuid="a1", output_dir="/out",
            sample_rate=8000, channels=2, sample_width=4,
            labels=["yes", "no"], buffer_size=64000,
        )
        assert cfg.device_name == "Custom"
        assert cfg.device_address == "FF:EE"
        assert cfg.voice_result_uuid == "v1"
        assert cfg.audio_data_uuid == "a1"
        assert cfg.output_dir == "/out"
        assert cfg.sample_rate == 8000
        assert cfg.channels == 2
        assert cfg.sample_width == 4
        assert cfg.labels == ["yes", "no"]
        assert cfg.buffer_size == 64000

    def test_config_overwrites_previous(self):
        first = pkg.config(device_name="1", device_address="1", voice_result_uuid="1", audio_data_uuid="1", output_dir="/1")
        second = pkg.config(device_name="2", device_address="2", voice_result_uuid="2", audio_data_uuid="2", output_dir="/2")
        assert pkg._config is second
        assert pkg._config is not first

class TestDunderAll:
    def test_all_contains_expected_names(self):
        assert set(pkg.__all__) == {"BLEConfig", "BLEReceiver", "config"}

    def test_all_length(self):
        assert len(pkg.__all__) == 3