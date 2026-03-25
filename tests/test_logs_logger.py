import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os

from sml.ops.logs import Logger

class TestLogger(unittest.TestCase):

    @patch('sml.ops.logs.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_logger_init(self, mock_file, mock_exists):
        mock_exists.return_value = False
        
        logger = Logger(
            databricks_host="fake",
            client_id="id",
            client_secret="secret"
        )
        
        self.assertEqual(logger.databricks_host, "fake")
        # Ensure it creates the initial array
        mock_file().write.assert_called_with('[]')

    @patch('sml.ops.logs.requests.post')
    def test_get_token_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "token123"}
        mock_post.return_value = mock_response
        
        logger = Logger("host", "id", "secret")
        token = logger._get_token()
        
        self.assertEqual(token, "token123")
        self.assertEqual(logger._access_token, "token123")
        mock_post.assert_called_once()
        
    @patch('sml.ops.logs.requests.get')
    def test_resolve_warehouse_id_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "warehouses": [{"name": "Serverless Starter Warehouse", "id": "w123"}]
        }
        mock_get.return_value = mock_response
        
        logger = Logger("host", "id", "secret")
        # Mock token retrieval since resolve uses it
        logger._get_token = MagicMock(return_value="token123")
        
        wid = logger._resolve_warehouse_id()
        self.assertEqual(wid, "w123")
        self.assertEqual(logger.warehouse_id, "w123")

    @patch('sml.ops.logs.json.load')
    @patch('sml.ops.logs.json.dump')
    @patch('builtins.open', new_callable=mock_open)
    @patch('sml.ops.logs.requests.post')
    def test_log_event(self, mock_post, mock_file, mock_dump, mock_load):
        # Local read returns empty
        mock_load.return_value = []
        
        logger = Logger("http://host", "id", "secret", "warehousename", "wid", "tab.le")
        logger._get_token = MagicMock(return_value="token")
        
        # Test basic event
        logger.log_event("Profiling", "Info", "Started")
        
        # We expect JSON dump to be called to save locally
        self.assertTrue(mock_dump.called)
        
        # We expect a POST request to Databricks SQL 
        mock_post.assert_called()
        self.assertEqual(mock_post.call_args[0][0], "http://host/api/2.0/sql/statements")

    @patch('builtins.print')
    @patch('sml.ops.logs.json.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_view_history(self, mock_file, mock_load, mock_print):
        # Fake logs
        mock_load.return_value = [
            {"timestamp": "t1", "type": "Profiling", "level": "Info", "source": "Sys", "message": "hello"},
            {"timestamp": "t2", "type": "Deployment", "level": "Error", "source": "Sys", "message": "failed"}
        ]
        
        logger = Logger()
        logger.view(event_type="Profiling")
        
        # We should print table headers and lines, but only 1 row matching "Profiling"
        mock_print.assert_any_call("t1                   | Profiling        | Info     | Sys             | hello")

    @patch('builtins.print')
    @patch('sml.ops.logs.json.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_view_history_empty_and_error(self, mock_file, mock_load, mock_print):
        # Test empty logs array
        mock_load.return_value = []
        logger = Logger()
        logger.view()
        mock_print.assert_any_call("\nNo local logs found.")
        
        # Test JSONDecodeError / FileNotFoundError
        mock_load.side_effect = json.JSONDecodeError("msg", "doc", 0)
        logger.view()
        mock_print.assert_any_call("\nNo local history file found. Run log_event() to start tracking.")

    @patch('sml.ops.logs.requests.post')
    def test_get_token_failure(self, mock_post):
        # Simulate network error or invalid creds
        mock_post.side_effect = Exception("Auth failed")
        logger = Logger("host", "id", "secret")
        
        with patch('builtins.print') as mock_print:
            token = logger._get_token()
            self.assertIsNone(token)
            mock_print.assert_any_call("Warning: Failed to fetch Databricks OAuth token: Auth failed")
            
        # Test missing client secret
        logger = Logger("host", "id", None)
        self.assertIsNone(logger._get_token())

    @patch('sml.ops.logs.requests.get')
    def test_resolve_warehouse_id_failure(self, mock_get):
        logger = Logger("host", "id", "secret", "MyWarehouse")
        logger._get_token = MagicMock(return_value="token123")
        
        # Simulate wrong warehouse name
        mock_response = MagicMock()
        mock_response.json.return_value = {"warehouses": [{"name": "Different", "id": "w123"}]}
        mock_get.return_value = mock_response
        
        with patch('builtins.print') as mock_print:
            wid = logger._resolve_warehouse_id()
            self.assertIsNone(wid)
            mock_print.assert_called_with("Warning: Could not find warehouse named 'MyWarehouse'")
            
        # Simulate API Exception
        mock_get.side_effect = Exception("API Down")
        with patch('builtins.print') as mock_print:
            wid = logger._resolve_warehouse_id()
            self.assertIsNone(wid)
            mock_print.assert_called_with("Warning: Failed to resolve warehouse ID: API Down")
            
        # Test resolving without a token
        logger._get_token = MagicMock(return_value=None)
        self.assertIsNone(logger._resolve_warehouse_id())

    @patch('sml.ops.logs.json.dump')    
    @patch('sml.ops.logs.json.load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('sml.ops.logs.requests.post')
    def test_log_event_api_failure(self, mock_post, mock_file, mock_load, mock_dump):
        mock_load.return_value = []
        logger = Logger("http://host", "id", "secret", "warehousename", "wid", "tab.le")
        logger._get_token = MagicMock(return_value="token")
        
        # Test that an API failure gracefully prints a warning 
        mock_post.side_effect = Exception("SQL API Error")
        
        with patch('builtins.print') as mock_print:
            logger.log_event("Profiling", "Info", "Started")
            mock_print.assert_called_with("Warning: Failed to stream log to Databricks: SQL API Error")

    @patch('sml.ops.logs.Logger.log_event')
    def test_log_wrappers(self, mock_log_event):
        logger = Logger()
        logger.log_model_deployment("depl message")
        mock_log_event.assert_called_with(type="Deployment", level="Info", message="depl message", source="Deployment Service")
        
    @patch('sml.ops.logs.requests.post')
    @patch('sml.ops.logs.json.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_sync_to_databricks(self, mock_file, mock_load, mock_post):
        logger = Logger("http://host", "id", "secret", "warehousename", "wid", "tab.le")
        logger._get_token = MagicMock(return_value="token123")
        
        # Mock local logs file
        mock_load.return_value = [
            {"timestamp": "t1", "type": "T", "level": "L", "message": "msg1", "source": "S1"},
            {"timestamp": "t2", "type": "T", "level": "L", "message": "msg2", "source": "S2"}
        ]
        
        # Fake successful insert for the first log, fake 400 error for the second
        mock_resp_success = MagicMock(status_code=200)
        mock_resp_success.json.return_value = {"status": {"state": "SUCCEEDED"}}
        mock_resp_fail = MagicMock(status_code=400, text="Bad Request")
        mock_post.side_effect = [mock_resp_success, mock_resp_fail]
        
        with patch('builtins.print') as mock_print:
            logger.sync_to_databricks()
            mock_print.assert_any_call("\n[ERROR] Failed to upload logs: HTTP 400 - Bad Request")
            mock_print.assert_any_call("\n✓ Successfully Bulk Synced 1 local logs into tab.le!")

    @patch('sml.ops.logs.json.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_sync_to_databricks_edge_cases(self, mock_file, mock_load):
        logger = Logger()
        
        # No table name
        with patch('builtins.print') as mock_print:
            logger.sync_to_databricks()
            mock_print.assert_called_with("Error: No table name provided for syncing!")
            
        logger.table_name = "t"
        
        # File not found
        mock_load.side_effect = FileNotFoundError()
        with patch('builtins.print') as mock_print:
            logger.sync_to_databricks()
            mock_print.assert_called_with("No local logs found to sync.")
            
        # Empty array
        mock_load.side_effect = None
        mock_load.return_value = []
        with patch('builtins.print') as mock_print:
            logger.sync_to_databricks()
            mock_print.assert_called_with("Local log file is empty. Nothing to sync!")

        # Auth failed
        mock_load.return_value = [{"timestamp": "123"}]
        logger._get_token = MagicMock(return_value=None)
        with patch('builtins.print') as mock_print:
            logger.sync_to_databricks()
            mock_print.assert_called_with("✗ Error: Could not authenticate or resolve warehouse ID. Check your credentials.")

    @patch('sml.ops.logs.Path.home')
    def test_logger_init_env_file_parsing(self, mock_home):
        # Create a fake `.sml.ops/.env` file
        mock_home_path = MagicMock()
        mock_home.return_value = mock_home_path
        mock_env_file = MagicMock()
        mock_env_file.exists.return_value = True
        mock_home_path.__truediv__.return_value = mock_env_file
        
        mock_open_func = mock_open(read_data='DATABRICKS_HOST="http://fake-from-env"\nBAD_LINE\n')
        with patch('builtins.open', mock_open_func):
            with patch.dict(os.environ, clear=True):
                # Import Config mock throwing an exception to hit the bare fallback branch
                with patch('sml.ops.config.Config', side_effect=Exception("No Config")):
                    logger = Logger(client_id="id", client_secret="sec")
                    
                    self.assertEqual(os.environ.get("DATABRICKS_HOST"), "http://fake-from-env")
                    self.assertEqual(logger.databricks_host, "http://fake-from-env")

if __name__ == '__main__':
    unittest.main()
