from pathlib import Path
import types
from unittest.mock import patch
import pytest

# Testing the public API (exercises __init__.py and config.py)
from sml.ops.model import RPiDeployer

@pytest.fixture
def deployer(tmp_path: Path):
    """Fixture to create a deployer with a temporary dummy firmware file."""
    fw = tmp_path / "firmware.s37"
    fw.write_text("dummy_binary_content")
    return RPiDeployer(
        rpi_host="192.168.1.111",
        rpi_user="aimlraspberry",
        local_file_path=str(fw),
    )

def test_rpi_deployer_init_validation(tmp_path: Path):
    """Ensure it raises Error if local file is missing."""
    with pytest.raises(FileNotFoundError):
        RPiDeployer("h", "u", str(tmp_path / "missing.s37"))

def test_find_remote_commander_logic(monkeypatch, deployer):
    """Verify smart discovery and error when commander is not found."""
    # Scenario A: Auto-discovery finds it
    def run_found(cmd, **k):
        return types.SimpleNamespace(returncode=0, stdout="/usr/bin/commander-cli\n", stderr="")

    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", run_found)
    assert deployer._find_remote_commander("u@h") == "/usr/bin/commander-cli"

    # Scenario B: Discovery fails, raises RuntimeError
    def run_fail(cmd, **k):
        return types.SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", run_fail)
    with pytest.raises(RuntimeError, match="Could not locate Simplicity Commander"):
        deployer._find_remote_commander("u@h")

def test_jlink_serial_detection_parsing(monkeypatch, deployer):
    """Verify that multiple serial numbers are correctly extracted."""
    adapter_out = "serialNumber = 123456\nserialNumber=987654"
    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", 
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=adapter_out, stderr=""))
    
    serials = deployer._get_jlink_serials("u@h")
    assert serials == ["123456", "987654"]

def test_device_name_parsing(monkeypatch, deployer):
    """Verify part number extraction from commander device info."""
    info_out = "Part Number : EFR32MG26B510F3200IM68\nFlash Size : 3200 kB"
    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", 
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=info_out, stderr=""))
    
    name = deployer._get_device_name("u@h", "123")
    assert name == "EFR32MG26B510F3200IM68"

def test_full_deployment_flow_orchestration(monkeypatch, deployer):
    """Test the complete deploy() sequence with all mocks."""
    def fake_run(cmd, **k):
        j = " ".join(cmd)
        if "which commander" in j: return types.SimpleNamespace(returncode=0, stdout="/bin/cmd", stderr="")
        if "adapter list" in j: return types.SimpleNamespace(returncode=0, stdout="serialNumber=123", stderr="")
        if "device info" in j: return types.SimpleNamespace(returncode=0, stdout="Part Number : EFR32", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="OK", stderr="")

    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", fake_run)
    
    # This should run through discovery, scp, detection, and flash without errors
    deployer.deploy()

def test_interactive_selection_logic(monkeypatch, deployer):
    """Test that it correctly prompts and uses user input for board selection."""
    def fake_run(cmd, **k):
        if "adapter list" in " ".join(cmd):
            return types.SimpleNamespace(returncode=0, stdout="serialNumber=111\nserialNumber=222", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="Part Number : EFR32", stderr="")

    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", fake_run)
    
    # Mock user typing "2" to select the second serial number
    with patch("builtins.input", return_value="2"):
        deployer.deploy()
        # The test passes if no RuntimeError is raised

def test_flash_failure_handling(monkeypatch, deployer):
    """Verify that a non-zero exit code during flash raises RuntimeError."""
    def run_fail(cmd, **k):
        if " flash " in " ".join(cmd):
            return types.SimpleNamespace(returncode=1, stdout="", stderr="Verification failed")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", run_fail)
    with pytest.raises(RuntimeError) as exc:
        deployer._flash_firmware("pi@h", "/tmp/t.s37", "123", "EFR32")
    assert "Flash failed" in str(exc.value)

def test_error_scp_failure(monkeypatch, deployer):
    """Test SCP failure branch."""
    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", 
                        lambda *a, **k: types.SimpleNamespace(returncode=1, stdout="", stderr="SCP fail"))
    with pytest.raises(RuntimeError) as exc:
        deployer._scp_firmware("local", "pi@h", "remote")
    assert "SCP failed" in str(exc.value)

def test_error_adapter_list_failure(monkeypatch, deployer):
    """Test Adapter List Failure branch."""
    def run_fail(cmd, **k):
        if "adapter list" in " ".join(cmd):
            return types.SimpleNamespace(returncode=1, stdout="", stderr="Adapter list failed")
        return types.SimpleNamespace(returncode=0, stdout="OK", stderr="")
    
    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", run_fail)
    with pytest.raises(RuntimeError) as exc:
        deployer._get_jlink_serials("pi@h")
    assert "Adapter list failed" in str(exc.value)

def test_error_no_devices_connected(monkeypatch, deployer):
    """Test No J-Link devices connected branch."""
    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", 
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="Empty output", stderr=""))
    with pytest.raises(RuntimeError) as exc:
        deployer.deploy()
    assert "No J-Link devices connected" in str(exc.value)

def test_device_info_failures(monkeypatch, deployer):
    """Hits lines in deployer.py"""
    # 1. Command itself fails (Line 163)
    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", 
                        lambda *a, **k: types.SimpleNamespace(returncode=1, stdout="", stderr="Crash"))
    with pytest.raises(RuntimeError) as exc:
        deployer._get_device_name("u@h", "123")
    assert "Device info failed" in str(exc.value)

    # 2. Command succeeds but output is missing Part Number (Line 168)
    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", 
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="No parts found here!", stderr=""))
    with pytest.raises(RuntimeError) as exc:
        deployer._get_device_name("u@h", "123")
    assert "Could not extract device name" in str(exc.value)

def test_multiple_devices_invalid_input(monkeypatch, deployer):
    """Hits interactive selection lines in deployer.py"""
    def fake_run(cmd, **k):
        if "adapter list" in " ".join(cmd):
            return types.SimpleNamespace(returncode=0, stdout="serialNumber=111\nserialNumber=222", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="Part Number : EFR32", stderr="")

    monkeypatch.setattr("sml.ops.model.deployer.subprocess.run", fake_run)
    
    # Simulate user typing a number out of range (Scenario for lines 69-71)
    with patch("builtins.input", return_value="99"), pytest.raises(RuntimeError) as exc:
        deployer.deploy()
    assert "Invalid selection" in str(exc.value)
