import os
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sml.ops.data.ingest.config import IngestConfig
from sml.ops.data.ingest.service import (
    IngestionService,
    build_wav_metadata,
    default_metadata_builder,
)


class TestMetadataBuilders(unittest.TestCase):
    def test_build_wav_metadata_parses_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "on_test.wav"
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00" * 320)

            with patch(
                "sml.ops.data.ingest.service.get_hw_info", return_value=(None, None)
            ):
                meta = build_wav_metadata(wav_path)

            self.assertEqual(meta["class_label"], "on")
            self.assertEqual(meta["file_name"], "on_test.wav")
            self.assertEqual(meta["content_type"], "audio/wav")
            self.assertEqual(meta["sample_rate"], 16000)

    def test_default_metadata_builder_generic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            path.write_text("a,b\n", encoding="utf-8")

            with patch(
                "sml.ops.data.ingest.service.get_hw_info", return_value=(None, None)
            ):
                meta = default_metadata_builder(path)

            self.assertEqual(meta["file_name"], "data.csv")
            self.assertEqual(meta["content_type"], "text/csv")
            self.assertIn("ingest_ts", meta)


class TestIngestionService(unittest.TestCase):
    def setUp(self):
        self.config = IngestConfig("e", "https://ws.url", "t", "i", "s")
        self.tmp = tempfile.TemporaryDirectory()
        self.monitor_dir = self.tmp.name
        self.volume_path = "/Volumes/main/default/data"

    def tearDown(self):
        self.tmp.cleanup()

    def _make_service(self, **kwargs):
        defaults = {
            "config": self.config,
            "monitor_dir": self.monitor_dir,
            "volume_path": self.volume_path,
            "pattern": "*.wav",
            "workers": 1,
            "poll_interval": 0.05,
        }
        defaults.update(kwargs)
        return IngestionService(**defaults)

    @patch("sml.ops.data.ingest.service.DataIngestor")
    def test_uploader_deletes_on_success(self, mock_ingestor_cls):
        mock_ingestor = MagicMock()
        mock_ingestor.file_ingest.return_value = True
        mock_ingestor_cls.return_value = mock_ingestor

        wav_path = Path(self.monitor_dir) / "on_sample.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 320)

        service = self._make_service()
        service._file_queue.put(str(wav_path))

        thread = threading.Thread(target=service._uploader, args=(0,), daemon=True)
        thread.start()
        thread.join(timeout=2)
        service._stop_event.set()
        thread.join(timeout=1)

        self.assertFalse(wav_path.exists())
        mock_ingestor.file_ingest.assert_called_once()

    @patch("sml.ops.data.ingest.service.DataIngestor")
    def test_uploader_keeps_file_on_failure(self, mock_ingestor_cls):
        mock_ingestor = MagicMock()
        mock_ingestor.file_ingest.return_value = False
        mock_ingestor_cls.return_value = mock_ingestor

        wav_path = Path(self.monitor_dir) / "off_sample.wav"
        wav_path.write_bytes(b"not-a-real-wav")

        service = self._make_service()
        service._file_queue.put(str(wav_path))

        thread = threading.Thread(target=service._uploader, args=(0,), daemon=True)
        thread.start()
        thread.join(timeout=2)
        service._stop_event.set()
        thread.join(timeout=1)

        self.assertTrue(wav_path.exists())

    @patch("sml.ops.data.ingest.service.DataIngestor")
    def test_monitor_enqueues_new_files(self, mock_ingestor_cls):
        mock_ingestor_cls.return_value = MagicMock()

        wav_path = Path(self.monitor_dir) / "hello.wav"
        wav_path.write_bytes(b"x")

        service = self._make_service()
        service._stop_event.clear()

        def stop_after_enqueue():
            time.sleep(0.2)
            service._stop_event.set()

        threading.Thread(target=stop_after_enqueue, daemon=True).start()
        service._directory_monitor()

        queued = []
        while not service._file_queue.empty():
            queued.append(service._file_queue.get_nowait())

        self.assertIn(str(wav_path), queued)

    def test_start_stop_lifecycle(self):
        service = self._make_service()
        with patch.object(service, "_directory_monitor"), patch.object(
            service, "_uploader"
        ):
            service.start()
            self.assertTrue(service._started)
            service.stop()
            self.assertFalse(service._started)


if __name__ == "__main__":
    unittest.main()
