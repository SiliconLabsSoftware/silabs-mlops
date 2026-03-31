import os
import time
import struct
import logging
import threading
import queue
import requests
import uuid
import base64
from pathlib import Path
from datetime import datetime, timezone
import re
import subprocess
import wave

COMMANDER_PATH = os.getenv("COMMANDER_PATH", str(Path.home() / "Desktop/SimplicityCommander-Linux/commander-cli/commander-cli"))  # <- replace this path with your own commander-cli path

def get_hw_info():
    """Runs commander-cli to find part number and unique ID from the connected board."""
    if not Path(COMMANDER_PATH).exists():
        return None, None
    try:
        out = subprocess.check_output([COMMANDER_PATH, "adapter", "list"], stderr=subprocess.STDOUT).decode()
        sn_match = re.search(r"serialNumber=(\d+)", out)
        if not sn_match:
            return None, None
        sn = sn_match.group(1)

        out = subprocess.check_output([COMMANDER_PATH, "device", "info", "--serialno", sn], stderr=subprocess.STDOUT).decode()
        part_match = re.search(r"Part Number\s+:\s+(.+)", out)
        uid_match = re.search(r"Unique ID\s+:\s+(.+)", out)

        part = part_match.group(1).strip() if part_match else None
        uid = uid_match.group(1).strip() if uid_match else None
        return part, uid
    except Exception:
        return None, None

WORKSPACE_URL = os.getenv("ZEROBUS_WORKSPACE_URL")
CLIENT_ID = os.getenv("ZEROBUS_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZEROBUS_CLIENT_SECRET")
SERVER_ENDPOINT = os.getenv("ZEROBUS_SERVER_ENDPOINT")
TABLE_NAME = os.getenv("ZEROBUS_TABLE_NAME")
VOLUME_PATH = os.getenv("DATABRICKS_VOLUME_PATH")

MONITOR_DIR_PATH = os.getenv("AUDIO_SAMPLES_DIR")
if not MONITOR_DIR_PATH:
    raise EnvironmentError("AUDIO_SAMPLES_DIR is not set. Run via 'python start_ingestion.py' to configure.")
MONITOR_DIR = Path(MONITOR_DIR_PATH)

try:
    from sml.ops import data as zerobus_data    
    ZEROBUS_AVAILABLE = True
except Exception:
    ZEROBUS_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("CloudIngestor")

file_queue = queue.Queue()

def directory_monitor_thread():
    logger.info(f"Monitor started on {MONITOR_DIR}")
    seen_files = set()
    
    while True:
        try:
            MONITOR_DIR.mkdir(parents=True, exist_ok=True)
            
            files = [f for f in os.listdir(MONITOR_DIR) if f.lower().endswith('.wav')]
            for f in files:
                fpath = MONITOR_DIR / f
                if str(fpath) not in seen_files:
                    logger.info(f"New file detected: {f}")
                    file_queue.put(str(fpath))
                    seen_files.add(str(fpath))
            
            current_paths = {str(MONITOR_DIR / f) for f in files}
            seen_files &= current_paths
            
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            
        time.sleep(1)

def uploader_thread():
    logger.info("Uploader started")
    
    if ZEROBUS_AVAILABLE:
        try:
            zerobus_data.config(
                server_endpoint=SERVER_ENDPOINT,
                workspace_url=WORKSPACE_URL,
                table_name=TABLE_NAME,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            logger.info("ZeroBus SDK configured")
        except Exception as e:
            logger.error(f"ZeroBus config failed: {e}")

    while True:
        fpath = file_queue.get()
        try:
            fname = os.path.basename(fpath)
            parts = fname.replace('.wav', '').split('_')
            label = parts[0] if parts else "unknown"
            
            file_sample_rate = 16000
            try:
                with wave.open(fpath, "rb") as wf:
                    file_sample_rate = wf.getframerate()
                    logger.info(f"Detected {file_sample_rate}Hz from {fname} header")
            except Exception as e:
                logger.error(f"Could not read WAV header for {fname}: {e}")

            hw_name, hw_id = get_hw_info()
            
            if hw_name and hw_id:
                device_id = hw_id
                device_name = hw_name
            else:
                device_id = f"Pi-{uuid.getnode():x}"
                device_name = "Raspberry Pi Voice Gateway"

            dest_path = f"{VOLUME_PATH.rstrip('/')}/{fname}"
            
            metadata = {
                "device_id":   device_id,
                "device_name": device_name,
                "file_name":   fname,
                "class_label": label,
                "content_type": "audio/wav",
                "sample_rate": file_sample_rate,
                "duration_ms": 1000,
            }
            
            if ZEROBUS_AVAILABLE:
                success = zerobus_data.file_ingest(
                    file_path=fpath,
                    volume_path=dest_path,
                    metadata=metadata
                )
                
                if success:
                    logger.info(f"Successfully processed {fname}")
                    os.remove(fpath)
                    logger.info(f"Removed local file {fname}")
                else:
                    logger.error(f"Failed to process {fname}, keeping local copy")
            else:
                logger.error("ZeroBus SDK not available, cannot ingest.")

        except Exception as e:
            logger.error(f"Uploader error processing {fpath}: {e}")
        finally:
            file_queue.task_done()

def main():
    if not WORKSPACE_URL:
        logger.error("Missing mandatory environment variables. Please set ZEROBUS_WORKSPACE_URL, etc.")
    else:
        t1 = threading.Thread(target=directory_monitor_thread, daemon=True)
        t2 = threading.Thread(target=uploader_thread, daemon=True)
        
        t1.start()
        t2.start()
        
        logger.info("Cloud Ingestor system running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping...")