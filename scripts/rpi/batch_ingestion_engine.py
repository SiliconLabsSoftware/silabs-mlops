import os
import time
import logging
import threading
import queue
import uuid
from pathlib import Path
import re
import subprocess
import wave  # Required to read metadata from audio files

# Path to Simplicity Commander
COMMANDER_PATH = os.getenv(
    "COMMANDER_PATH",
    str(Path.home() / "Desktop/SimplicityCommander-Linux/commander-cli/commander-cli"),
)  # <- replace this path with your own commander-cli path

# Global cache for hardware info to prevent redundant subprocess calls
_hw_cache = {"name": None, "id": None}
_hw_lock = threading.Lock()


def get_hw_info():
    """Runs commander-cli to find part number and unique ID from the connected board."""
    global _hw_cache

    with _hw_lock:
        if _hw_cache["name"] is not None:
            return _hw_cache["name"], _hw_cache["id"]

        if not Path(COMMANDER_PATH).exists():
            return None, None

        try:
            # 1. Get adapter list to find any connected device's serial number
            out = subprocess.check_output(
                [COMMANDER_PATH, "adapter", "list"], stderr=subprocess.STDOUT
            ).decode()
            sn_match = re.search(r"serialNumber=(\d+)", out)
            if not sn_match:
                return None, None
            sn = sn_match.group(1)

            # 2. Get device info for that serial number
            out = subprocess.check_output(
                [COMMANDER_PATH, "device", "info", "--serialno", sn],
                stderr=subprocess.STDOUT,
            ).decode()
            part_match = re.search(r"Part Number\s+:\s+(.+)", out)
            uid_match = re.search(r"Unique ID\s+:\s+(.+)", out)

            part = part_match.group(1).strip() if part_match else None
            uid = uid_match.group(1).strip() if uid_match else None

            _hw_cache["name"] = part
            _hw_cache["id"] = uid

            return part, uid
        except Exception:
            return None, None


# -----------------------------
# Configuration & Environment
# -----------------------------
WORKSPACE_URL = os.getenv("ZEROBUS_WORKSPACE_URL")
CLIENT_ID = os.getenv("ZEROBUS_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZEROBUS_CLIENT_SECRET")
SERVER_ENDPOINT = os.getenv("ZEROBUS_SERVER_ENDPOINT")
TABLE_NAME = os.getenv("ZEROBUS_TABLE_NAME")
VOLUME_PATH = os.getenv("DATABRICKS_VOLUME_PATH")

# Local directory to monitor (Must be set via BLE_OUTPUT_DIR environment variable)
MONITOR_DIR_PATH = os.getenv("BLE_OUTPUT_DIR")
if not MONITOR_DIR_PATH:
    raise EnvironmentError(
        "BLE_OUTPUT_DIR is not set. Run via 'python ingestion_service.py' to configure."
    )
MONITOR_DIR = Path(MONITOR_DIR_PATH)

# Number of worker threads for parallel upload (Optional)
# You can set this via environment variable 'NUM_WORKERS' or directly here.
# For Raspberry Pi, it's recommended to keep this below 7 to save resources.
NUM_WORKERS = int(os.getenv("NUM_WORKERS", "4"))

# SDK imports
try:
    from sml.ops import data as zerobus_data

    ZEROBUS_AVAILABLE = True
except Exception:
    ZEROBUS_AVAILABLE = False
# -----------------------------
# Logger Setup
# -----------------------------
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("MultiCloudIngestor")

# -----------------------------
# Worker Threads
# -----------------------------
file_queue = queue.Queue()


def directory_monitor_thread():
    """Thread 1: Actively listens for new WAV files in the directory."""
    logger.info(f"Monitor started on {MONITOR_DIR}")
    seen_files = set()

    while True:
        try:
            MONITOR_DIR.mkdir(parents=True, exist_ok=True)

            files = [f for f in os.listdir(MONITOR_DIR) if f.lower().endswith(".wav")]
            for f in files:
                fpath = MONITOR_DIR / f
                if str(fpath) not in seen_files:
                    logger.info(f"New file detected: {f}")
                    file_queue.put(str(fpath))
                    seen_files.add(str(fpath))

            # Clean up seen_files for files that were moved/deleted
            current_paths = {str(MONITOR_DIR / f) for f in files}
            seen_files &= current_paths

        except Exception as e:
            logger.error(f"Monitor error: {e}")

        time.sleep(1)


def uploader_thread(worker_id):
    """Worker Thread: Moves files to the cloud in parallel and deletes local copies."""
    logger.info(f"Worker-{worker_id} started")

    # Initialize ZeroBus once per thread (or shared if SDK allows)
    if ZEROBUS_AVAILABLE:
        try:
            zerobus_data.config(
                server_endpoint=SERVER_ENDPOINT,
                workspace_url=WORKSPACE_URL,
                table_name=TABLE_NAME,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
        except Exception as e:
            logger.error(f"Worker-{worker_id} ZeroBus config failed: {e}")

    while True:
        fpath = file_queue.get()
        try:
            fname = os.path.basename(fpath)
            # Parse Format: label_timestamp.wav
            parts = fname.replace(".wav", "").split("_")
            label = parts[0] if parts else "unknown"

            # --- Auto-Detection of Audio Params via WAV Header ---
            file_sample_rate = 16000  # Default
            try:
                with wave.open(fpath, "rb") as wf:
                    file_sample_rate = wf.getframerate()
            except Exception as e:
                logger.error(
                    f"Worker-{worker_id}: Could not read WAV header for {fname}: {e}"
                )

            # --- Hardware Detection via Commander CLI (Cached) ---
            hw_name, hw_id = get_hw_info()

            if hw_name and hw_id:
                device_id = hw_id
                device_name = hw_name
            else:
                device_id = f"Pi-{uuid.getnode():x}"
                device_name = "Raspberry Pi Voice Gateway"

            # 1 & 2. Comprehensive Ingestion (Upload + Metadata)
            dest_path = f"{VOLUME_PATH.rstrip('/')}/{fname}"

            metadata = {
                "device_id": device_id,
                "device_name": device_name,
                "file_name": fname,
                "class_label": label,
                "content_type": "audio/wav",
                "sample_rate": file_sample_rate,
                "duration_ms": 1000,
            }

            if ZEROBUS_AVAILABLE:
                logger.info(f"Worker-{worker_id} uploading {fname}...")
                success = zerobus_data.file_ingest(
                    file_path=fpath, volume_path=dest_path, metadata=metadata
                )

                if success:
                    logger.info(f"Worker-{worker_id} successfully processed {fname}")
                    # 3. Success -> Delete local file
                    if os.path.exists(fpath):
                        os.remove(fpath)
                else:
                    logger.error(
                        f"Worker-{worker_id} failed to process {fname}, keeping local copy"
                    )
            else:
                logger.error(
                    f"Worker-{worker_id}: ZeroBus SDK not available, cannot ingest."
                )

        except Exception as e:
            logger.error(f"Worker-{worker_id} error processing {fpath}: {e}")
        finally:
            file_queue.task_done()


# -----------------------------
# Entry Point
# -----------------------------
def main():
    if not WORKSPACE_URL:
        logger.error(
            "Missing mandatory environment variables. Please set ZEROBUS_WORKSPACE_URL, etc."
        )
    else:
        # Start directory monitor
        t_monitor = threading.Thread(target=directory_monitor_thread, daemon=True)
        t_monitor.start()

        # Start multiple worker threads
        logger.info(f"Starting {NUM_WORKERS} worker threads for ingestion...")
        for i in range(NUM_WORKERS):
            t_worker = threading.Thread(target=uploader_thread, args=(i,), daemon=True)
            t_worker.start()

        logger.info(
            "Multi-threaded Cloud Ingestor system running. Press Ctrl+C to stop."
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping...")


if __name__ == "__main__":
    main()
