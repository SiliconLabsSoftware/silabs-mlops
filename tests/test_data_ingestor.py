import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch


from sml.ops.data.ingest.config import IngestConfig
from sml.ops.data.ingest.ingestor import DataIngestor


@pytest.fixture
def config():
    """Default valid configuration."""
    return IngestConfig(
        server_endpoint="server.com",
        workspace_url="workspace.com",
        table_name="cat.db.tab",
        client_id="id",
        client_secret="secret"
    )


def test_ingestor_initialization(config):
    """Verify ingestor correctly creates the underlying client."""
    ing = DataIngestor(config)
    assert ing.config == config
    # Assumes the ingestor exposes the client and mirrors server_endpoint
    assert ing.client.server_endpoint == "server.com"


def test_read_buffered_json_array(tmp_path: Path, config):
    """Test reading a standard JSON array file."""
    buf = tmp_path / "buffer.json"
    buf.write_text(json.dumps([{"temp": 20}, {"temp": 25}]), encoding="utf-8")

    config.buffer_path = str(buf)
    ing = DataIngestor(config)

    records = ing._read_buffered_records()
    assert records == [{"temp": 20}, {"temp": 25}]


def test_read_buffered_json_lines(tmp_path: Path, config):
    """Test reading JSON lines (IoT style) format."""
    buf = tmp_path / "stream.jsonl"
    buf.write_text('{"sensor": "A", "val": 10}\n{"sensor": "B", "val": 20}\n', encoding="utf-8")

    config.buffer_path = str(buf)
    ing = DataIngestor(config)

    records = ing._read_buffered_records()
    assert records == [{"sensor": "A", "val": 10}, {"sensor": "B", "val": 20}]


def test_read_buffered_file_not_found(config):
    """Verify it returns empty list silently if file is missing."""
    config.buffer_path = "/tmp/does_not_exist.json"
    ing = DataIngestor(config)
    assert ing._read_buffered_records() == []


import sys

def test_ingest_no_records_outputs_and_aborts(config, capsys, monkeypatch):
    """If there's no data, it shouldn't connect and should print a message."""
    # Obtain the module directly from sys.modules to avoid shadowing by data.ingest()
    ingestor_mod = sys.modules["sml.ops.data.ingest.ingestor"]

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass
        def connect(self):
            raise AssertionError("should not connect")
        def close(self):
            pass

    # Replace the real client with a dummy
    monkeypatch.setattr(ingestor_mod, "ZerobusIngestClient", DummyClient)

    ing = DataIngestor(config)
    assert ing.ingest(data=[]) is False

    out = capsys.readouterr().out
    # Adapt this if you log instead of print
    assert "No records to ingest." in out


def test_ingest_happy_path_calls_once(config):
    """Test ingesting an explicitly passed python list."""
    ingestor_mod = sys.modules["sml.ops.data.ingest.ingestor"]
    
    with patch.object(ingestor_mod, "ZerobusIngestClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        ing = DataIngestor(config)
        records = [{"a": 1}]

        result = ing.ingest(data=records)

        assert result is True
        mock_client.connect.assert_called_once()
        mock_client.ingest_batch.assert_called_once_with(records)
        mock_client.close.assert_called_once()


def test_ingest_auth_failure_cleanup(config):
    """Test capturing a 401 Unauthorized exception and ensuring cleanup."""
    ingestor_mod = sys.modules["sml.ops.data.ingest.ingestor"]
    
    with patch.object(ingestor_mod, "ZerobusIngestClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.connect.side_effect = Exception("401 Unauthorized: Invalid secret")

        ing = DataIngestor(config)
        result = ing.ingest(data=[{"x": 1}])

        assert result is False
        mock_client.close.assert_called_once()  # Should always attempt to close


def test_ingest_schema_mismatch_failure(config):
    """Test capturing a schema/decoder error during batch ingest."""
    ingestor_mod = sys.modules["sml.ops.data.ingest.ingestor"]
    
    with patch.object(ingestor_mod, "ZerobusIngestClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.ingest_batch.side_effect = Exception("Code 4044: Decoder issue")

        ing = DataIngestor(config)
        result = ing.ingest(data=[{"x": 1}])

        assert result is False
        mock_client.connect.assert_called_once()
        mock_client.close.assert_called_once()


def test_ingest_from_buffer(tmp_path: Path, config):
    """Test ingesting from a buffer file when data is not explicitly provided."""
    buf = tmp_path / "data.json"
    buf.write_text(json.dumps([{"val": 100}]), encoding="utf-8")
    config.buffer_path = str(buf)

    ingestor_mod = sys.modules["sml.ops.data.ingest.ingestor"]
    with patch.object(ingestor_mod, "ZerobusIngestClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        ing = DataIngestor(config)

        result = ing.ingest()  # No data arg

        assert result is True
        mock_client.ingest_batch.assert_called_once_with([{"val": 100}])


def test_read_buffered_malformed_json(tmp_path: Path, config):
    """Test that malformed JSON lines are skipped with a warning."""
    buf = tmp_path / "malformed.jsonl"
    # One good line, one bad line
    buf.write_text('{"a": 1}\n{not_json}\n{"b": 2}', encoding="utf-8")
    config.buffer_path = str(buf)
    
    ing = DataIngestor(config)
    records = ing._read_buffered_records()
    
    assert records == [{"a": 1}, {"b": 2}]


def test_read_buffered_empty_file(tmp_path: Path, config):
    """Test reading an empty file."""
    buf = tmp_path / "empty.json"
    buf.write_text("", encoding="utf-8")
    config.buffer_path = str(buf)
    
    ing = DataIngestor(config)
    records = ing._read_buffered_records()
    
    assert records == []
