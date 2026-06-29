import unittest
import requests
from unittest.mock import patch, MagicMock, mock_open


from sml.ops.data.ingest.config import IngestConfig
from sml.ops.data.ingest import ingestor as ingestor_mod
from sml.ops.data.ingest.ingestor import DataIngestor
from sml.ops.data.ingest import zerobus_client as zerobus_mod
from sml.ops.data.ingest.zerobus_client import ZerobusIngestClient
import sml.ops.data


# ======================================================================
#  Test IngestConfig
# ======================================================================

class TestIngestConfig(unittest.TestCase):
    def test_strip_whitespace(self):
        cfg = IngestConfig(
            server_endpoint="  ep  ",
            workspace_url="  https://ws.url/  ",
            table_name="  t  ",
            client_id="  id  ",
            client_secret="  sec  "
        )
        self.assertEqual(cfg.server_endpoint, "ep")
        self.assertEqual(cfg.workspace_url, "https://ws.url")
        self.assertEqual(cfg.table_name, "t")
        self.assertEqual(cfg.client_id, "id")
        self.assertEqual(cfg.client_secret, "sec")

    def test_none_fields(self):
        cfg = IngestConfig("e", "w", "t", "i", "s")
        cfg.server_endpoint = None
        cfg.workspace_url = None
        cfg.__post_init__()
        self.assertIsNone(cfg.workspace_url)


# ======================================================================
#  Test Zerobus Client
# ======================================================================

class TestZerobusIngestClient(unittest.TestCase):
    def setUp(self):
        zerobus_mod.ZEROBUS_AVAILABLE = True
        with patch.object(zerobus_mod, "Logger"):
            self.client = ZerobusIngestClient("e", "u", "t", "i", "s")

    def test_import_error_when_unavailable(self):
        orig = zerobus_mod.ZEROBUS_AVAILABLE
        try:
            zerobus_mod.ZEROBUS_AVAILABLE = False
            with self.assertRaises(ImportError):
                ZerobusIngestClient("e", "u", "t", "i", "s")
        finally:
            zerobus_mod.ZEROBUS_AVAILABLE = orig

    @patch.object(zerobus_mod, "ZerobusSdk", create=True)
    @patch.object(zerobus_mod, "TableProperties", create=True)
    @patch.object(zerobus_mod, "StreamConfigurationOptions", create=True)
    @patch.object(zerobus_mod, "RecordType", create=True)
    def test_connect_success(self, *_):
        inst = MagicMock()
        zerobus_mod.ZerobusSdk.return_value = inst
        self.client.connect()
        inst.create_stream.assert_called_once()

    @patch.object(zerobus_mod, "ZerobusSdk", create=True)
    @patch.object(zerobus_mod, "TableProperties", create=True)
    @patch.object(zerobus_mod, "StreamConfigurationOptions", create=True)
    @patch.object(zerobus_mod, "RecordType", create=True)
    def test_connect_failure(self, *_):
        inst = MagicMock()
        zerobus_mod.ZerobusSdk.return_value = inst
        inst.create_stream.side_effect = Exception("Connect Err")
        with self.assertRaises(Exception):
            self.client.connect()


# ======================================================================
#  Test data module wrapper init
# ======================================================================

class TestDataInit(unittest.TestCase):
    def setUp(self):
        sml.ops.data._config = None

    @patch("sml.ops.data.IngestConfig")
    @patch("sml.ops.data.Config.update")
    @patch("builtins.print")
    def test_config_init(self, *_):
        sml.ops.data.config("e", "w", "t", "i", "s")
        self.assertIsNotNone(sml.ops.data._config)

    @patch("sml.ops.data.DataIngestor")
    def test_ingest_wrappers(self, mock_ing_cls):
        sml.ops.data._config = MagicMock()
        inst = MagicMock()
        mock_ing_cls.return_value = inst

        sml.ops.data.ingest([{"a": 1}])
        inst.ingest.assert_called_with(data=[{"a": 1}])

        sml.ops.data.ingest_from_file("p.json")
        inst.ingest.assert_called_with(buffer_path="p.json")

        sml.ops.data.file_ingest("l.csv", "r.csv", {})
        inst.file_ingest.assert_called_with("l.csv", "r.csv", {})


# ======================================================================
# ✅ Test DataIngestor
# ======================================================================

class TestDataIngestor(unittest.TestCase):
    def setUp(self):
        self.config = IngestConfig("e", "https://ws.url", "t", "i", "s", "buf.json")
        with patch.object(ingestor_mod, "ZerobusIngestClient"), \
             patch.object(ingestor_mod, "Logger"):
            self.ing = DataIngestor(self.config)

    @patch.object(ingestor_mod, "Path")
    def test_read_buffer(self, mock_path):
        self.config.buffer_path = None
        self.assertEqual(self.ing._read_buffered_records(), [])

        self.config.buffer_path = "missing.json"
        mock_path.return_value.exists.return_value = False
        self.assertEqual(self.ing._read_buffered_records(), [])

        mock_path.return_value.exists.return_value = True
        with patch("builtins.open", mock_open(read_data='[{"a":1}]')):
            self.assertEqual(self.ing._read_buffered_records(), [{"a": 1}])

    def test_ingest_no_records(self):
        with patch.object(self.ing, "_read_buffered_records", return_value=[]), \
             patch("builtins.print") as p:
            self.assertFalse(self.ing.ingest())
            p.assert_called_with("No records to ingest.")

    def test_ingest_success(self):
        self.ing.client.connect = MagicMock()
        self.ing.client.ingest_batch = MagicMock()
        self.assertTrue(self.ing.ingest(data=[{"a": 1}]))

    @patch("builtins.print")
    def test_close_failure(self, p):
        self.ing.client.close.side_effect = Exception("Close Err")
        self.assertTrue(self.ing.ingest(data=[{"a": 1}]))
        p.assert_any_call("[DEBUG] Could not cleanly close stream: Close Err")

    @patch("requests.post")
    def test_get_token(self, post):
        post.return_value.json.return_value = {"access_token": "x"}
        self.assertEqual(self.ing._get_oauth_token(), "x")

        post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("err")
        self.assertIsNone(self.ing._get_oauth_token())


if __name__ == "__main__":
    unittest.main()