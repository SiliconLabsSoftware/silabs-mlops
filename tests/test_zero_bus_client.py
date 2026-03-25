from unittest.mock import MagicMock, patch
import pytest

from sml.ops.data.ingest.config import IngestConfig
from sml.ops.data.ingest.zerobus_client import ZerobusIngestClient, ZEROBUS_AVAILABLE


def test_config_whitespace_stripping():
    """Test that IngestConfig removes accidental whitespaces and trailing slashes."""
    config = IngestConfig(
        server_endpoint="  my.server.com  ",
        workspace_url="https://workspace.com/  ",
        table_name=" my.table ",
        client_id=" 1234 ",
        client_secret=" secret "
    )
    
    assert config.server_endpoint == "my.server.com"
    # Notice that workspace_url also strips trailing slash from rstrip("/")
    assert config.workspace_url == "https://workspace.com"
    assert config.table_name == "my.table"
    assert config.client_id == "1234"
    assert config.client_secret == "secret"

import sys

def test_zerobus_client_import_error():
    """Verify an ImportError is raised if the SDK is missing."""
    client_mod = sys.modules["sml.ops.data.ingest.zerobus_client"]
    with patch.object(client_mod, "ZEROBUS_AVAILABLE", False):
        with pytest.raises(ImportError) as exc:
            ZerobusIngestClient("server", "workspace", "table", "id", "secret")
        assert "databricks-zerobus-ingest-sdk is not installed" in str(exc.value)

def test_zerobus_client_connect_success():
    """Test successful stream creation."""
    client_mod = sys.modules["sml.ops.data.ingest.zerobus_client"]
    with patch.object(client_mod, "ZEROBUS_AVAILABLE", True), patch.object(client_mod, "ZerobusSdk") as mock_sdk_class:
        # Setup mocks
        mock_sdk_instance = MagicMock()
        mock_sdk_class.return_value = mock_sdk_instance
        mock_stream = MagicMock()
        mock_sdk_instance.create_stream.return_value = mock_stream

        client = ZerobusIngestClient("server", "workspace", "table", "id", "secret")
        client.connect()
        
        # Verify stream is created correctly
        mock_sdk_instance.create_stream.assert_called_once()
        assert client._stream == mock_stream

def test_zerobus_client_connect_failure():
    """Test handling of connection error."""
    client_mod = sys.modules["sml.ops.data.ingest.zerobus_client"]
    with patch.object(client_mod, "ZEROBUS_AVAILABLE", True), patch.object(client_mod, "ZerobusSdk") as mock_sdk_class:
        mock_sdk_instance = MagicMock()
        mock_sdk_class.return_value = mock_sdk_instance
        mock_sdk_instance.create_stream.side_effect = Exception("Auth failed")

        client = ZerobusIngestClient("server", "workspace", "table", "id", "secret")
        with pytest.raises(Exception) as exc:
            client.connect()
        assert "Auth failed" in str(exc.value)

def test_zerobus_ingest_record_without_connect():
    """Verify runtime error if trying to ingest without connecting first."""
    client_mod = sys.modules["sml.ops.data.ingest.zerobus_client"]
    with patch.object(client_mod, "ZEROBUS_AVAILABLE", True):
        client = ZerobusIngestClient("server", "workspace", "table", "id", "secret")
        with pytest.raises(RuntimeError) as exc:
            client.ingest_record({"temperature": 25})
        assert "not initialized" in str(exc.value)

def test_zerobus_ingest_batch():
    """Test successful ingestion of multiple records sequentially."""
    client_mod = sys.modules["sml.ops.data.ingest.zerobus_client"]
    with patch.object(client_mod, "ZEROBUS_AVAILABLE", True):
        client = ZerobusIngestClient("server", "workspace", "table", "id", "secret")
        mock_stream = MagicMock()
        client._stream = mock_stream  # simulate successful connect
        
        mock_ack = MagicMock()
        mock_stream.ingest_record.return_value = mock_ack
        
        records = [{"temp": 20}, {"temp": 25}]
        client.ingest_batch(records, wait_for_ack=True)
        
        # Stream method should be called twice
        assert mock_stream.ingest_record.call_count == 2
        # Ack wait method should be called twice
        assert mock_ack.wait_for_ack.call_count == 2

def test_zerobus_close_stream():
    """Test stream closure path."""
    client_mod = sys.modules["sml.ops.data.ingest.zerobus_client"]
    with patch.object(client_mod, "ZEROBUS_AVAILABLE", True):
        client = ZerobusIngestClient("server", "workspace", "table", "id", "secret")
        mock_stream = MagicMock()
        client._stream = mock_stream
        
        client.close()
        
        mock_stream.close.assert_called_once()
        assert client._stream is None
