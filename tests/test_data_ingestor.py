import json
import unittest
from unittest.mock import patch, MagicMock, mock_open
from sml.ops.data.ingest.ingestor import DataIngestor
from sml.ops.data.ingest.config import IngestConfig
from sml.ops.config import USER_AGENT


class TestDataIngestor(unittest.TestCase):
    def setUp(self):
        #  Build a realistic mock config using real IngestConfig
        self.mock_config = MagicMock(spec=IngestConfig)
        self.mock_config.server_endpoint = "ep"
        self.mock_config.workspace_url = "https://wsp.url"
        self.mock_config.table_name = "tab"
        self.mock_config.client_id = "id"
        self.mock_config.client_secret = "secret"
        self.mock_config.buffer_path = "buf.json"

        #  Patch only inside the ingestor module
        with (
            patch("sml.ops.data.ingest.ingestor.ZerobusIngestClient"),
            patch("sml.ops.data.ingest.ingestor.Logger"),
        ):
            self.ingestor = DataIngestor(self.mock_config)

    # ---------------------------------------------------------------------
    #  _read_buffered_records Tests
    # ---------------------------------------------------------------------

    def test_read_buffer_none(self):
        """No buffer path → return empty list."""
        self.mock_config.buffer_path = None
        result = self.ingestor._read_buffered_records()
        self.assertEqual(result, [])

    @patch("sml.ops.data.ingest.ingestor.Path.exists")
    @patch("builtins.print")
    def test_read_buffer_missing_file(self, mock_print, mock_exists):
        mock_exists.return_value = False
        result = self.ingestor._read_buffered_records("missing.json")
        self.assertEqual(result, [])
        mock_print.assert_called_with("Warning: Buffer file not found at missing.json")

    @patch("sml.ops.data.ingest.ingestor.Path.exists")
    def test_read_buffer_json_array(self, mock_exists):
        mock_exists.return_value = True
        data = [{"a": 1}]
        with patch("builtins.open", mock_open(read_data=json.dumps(data))):
            result = self.ingestor._read_buffered_records()
            self.assertEqual(result, data)

    @patch("sml.ops.data.ingest.ingestor.Path.exists")
    def test_read_buffer_json_object(self, mock_exists):
        mock_exists.return_value = True
        data = {"a": 1}
        with patch("builtins.open", mock_open(read_data=json.dumps(data))):
            result = self.ingestor._read_buffered_records()
            self.assertEqual(result, [data])

    @patch("sml.ops.data.ingest.ingestor.Path.exists")
    @patch("builtins.print")
    def test_read_buffer_json_lines(self, mock_print, mock_exists):
        mock_exists.return_value = True
        content = '{"a":1}\n{"b":2}\ninvalid\n{"c":3}'
        with patch("builtins.open", mock_open(read_data=content)):
            result = self.ingestor._read_buffered_records()
            self.assertEqual(result, [{"a": 1}, {"b": 2}, {"c": 3}])
            mock_print.assert_called()

    # ---------------------------------------------------------------------
    #  ingest() Tests
    # ---------------------------------------------------------------------

    def test_ingest_no_records(self):
        with (
            patch.object(self.ingestor, "_read_buffered_records", return_value=[]),
            patch("builtins.print") as mock_print,
        ):
            result = self.ingestor.ingest()
            self.assertFalse(result)
            mock_print.assert_called_with("No records to ingest.")

    def test_ingest_success_buffer(self):
        records = [{"a": 1}]
        with patch.object(
            self.ingestor, "_read_buffered_records", return_value=records
        ):
            self.assertTrue(self.ingestor.ingest())
            self.ingestor.client.connect.assert_called_once()
            self.ingestor.client.ingest_batch.assert_called_with(records)
            self.ingestor.client.close.assert_called_once()

    def test_ingest_success_direct(self):
        records = [{"a": 1}]
        self.assertTrue(self.ingestor.ingest(data=records))
        self.ingestor.client.ingest_batch.assert_called_with(records)

    @patch("builtins.print")
    def test_ingest_auth_failure(self, mock_print):
        self.ingestor.client.connect.side_effect = Exception("401 Unauthorized")
        self.assertFalse(self.ingestor.ingest(data=[{"a": 1}]))
        mock_print.assert_any_call(
            "\n[AUTH FAILURE] 401 Unauthorized -- check your service principal permissions."
        )

    @patch("builtins.print")
    def test_ingest_schema_mismatch(self, mock_print):
        self.ingestor.client.connect.side_effect = Exception(
            "Error 4044: decoder failure"
        )
        self.assertFalse(self.ingestor.ingest(data=[{"a": 1}]))
        mock_print.assert_any_call(
            "\n[SCHEMA MISMATCH ERROR] The server rejected the record format (Code 4044)."
        )

    @patch("traceback.print_exc")
    @patch("builtins.print")
    def test_ingest_general_error(self, mock_print, mock_trace):
        self.ingestor.client.connect.side_effect = Exception("Unknown Error")
        self.assertFalse(self.ingestor.ingest(data=[{"a": 1}]))
        mock_print.assert_any_call("Error during ingestion: Exception: Unknown Error")

    @patch("builtins.print")
    def test_ingest_close_failure(self, mock_print):
        self.ingestor.client.close.side_effect = Exception("Close Error")
        self.assertTrue(self.ingestor.ingest(data=[{"a": 1}]))
        mock_print.assert_any_call(
            "[DEBUG] Could not cleanly close stream: Close Error"
        )

    # ---------------------------------------------------------------------
    #  OAuth Token Tests
    # ---------------------------------------------------------------------

    @patch("requests.post")
    def test_token_success(self, mock_post):
        mock_post.return_value.json.return_value = {"access_token": "tkn"}
        self.assertEqual(self.ingestor._get_oauth_token(), "tkn")

    def test_token_missing_creds(self):
        self.mock_config.client_id = None
        self.assertIsNone(self.ingestor._get_oauth_token())

    @patch("requests.post")
    def test_token_failure(self, mock_post):
        mock_post.side_effect = Exception("Network Error")
        self.assertIsNone(self.ingestor._get_oauth_token())

    @patch("requests.post")
    def test_token_sets_user_agent(self, mock_post):
        mock_post.return_value.json.return_value = {"access_token": "tkn"}
        self.ingestor._get_oauth_token()
        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["User-Agent"], USER_AGENT
        )

    # ---------------------------------------------------------------------
    #  Upload to Volume Tests
    # ---------------------------------------------------------------------

    @patch("requests.put")
    def test_upload_success(self, mock_put):
        mock_put.return_value.status_code = 200
        res = self.ingestor._upload_to_volume("t", b"x", "/Volumes/main/data/file.txt")
        self.assertTrue(res)

    @patch("requests.put")
    def test_upload_normalizes_dbfs(self, mock_put):
        mock_put.return_value.status_code = 200
        self.ingestor._upload_to_volume("t", b"x", "dbfs:/vol\\file.txt")
        args, _ = mock_put.call_args
        assert "/Volumes/vol/file.txt" in args[0]

    @patch("requests.put")
    def test_upload_failure(self, mock_put):
        mock_put.return_value.status_code = 500
        mock_put.return_value.text = "Err"
        res = self.ingestor._upload_to_volume("t", b"x", "/Volumes/x")
        self.assertFalse(res)

    @patch("requests.put")
    def test_upload_exception(self, mock_put):
        mock_put.side_effect = Exception("Crash")
        self.assertFalse(self.ingestor._upload_to_volume("t", b"x", "/Volumes/x"))

    @patch("requests.put")
    def test_upload_sets_user_agent(self, mock_put):
        mock_put.return_value.status_code = 200
        self.ingestor._upload_to_volume("t", b"x", "/Volumes/main/data/file.txt")
        self.assertEqual(mock_put.call_args.kwargs["headers"]["User-Agent"], USER_AGENT)

    # ---------------------------------------------------------------------
    #  file_ingest() Tests
    # ---------------------------------------------------------------------

    @patch("sml.ops.data.ingest.ingestor.time.time")
    def test_file_ingest_success(self, mock_time):
        mock_time.return_value = 12345.0

        with (
            patch("builtins.open", mock_open(read_data=b"content")),
            patch.object(self.ingestor, "_get_oauth_token", return_value="tok"),
            patch.object(self.ingestor, "_upload_to_volume", return_value=True),
            patch.object(self.ingestor, "ingest", return_value=True) as mock_ing,
        ):
            metadata = {"file_name": "data.csv"}
            result = self.ingestor.file_ingest("loc.csv", "/Volumes/x", metadata)

            self.assertTrue(result)
            self.assertEqual(metadata["file_path"], "/Volumes/x")
            self.assertEqual(metadata["ingest_ts"], 12_345_000_000)
            mock_ing.assert_called_once()

    @patch("builtins.open", side_effect=Exception("Read Error"))
    def test_file_ingest_read_failure(self, _):
        self.assertFalse(self.ingestor.file_ingest("missing.csv", "/v", {}))

    def test_file_ingest_token_failure(self):
        with (
            patch("builtins.open", mock_open(read_data=b"x")),
            patch.object(self.ingestor, "_get_oauth_token", return_value=None),
        ):
            self.assertFalse(self.ingestor.file_ingest("x", "/v", {}))

    def test_file_ingest_upload_failure(self):
        with (
            patch("builtins.open", mock_open(read_data=b"x")),
            patch.object(self.ingestor, "_get_oauth_token", return_value="tok"),
            patch.object(self.ingestor, "_upload_to_volume", return_value=False),
        ):
            self.assertFalse(self.ingestor.file_ingest("x", "/v", {}))


if __name__ == "__main__":
    unittest.main()
