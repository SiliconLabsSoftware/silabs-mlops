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

# Path to Simplicity Commander
COMMANDER_PATH = r"<PATH_TO_COMMANDER_CLI>" # e.g., "C:/SimplicityCommander/commander.exe"

def get_hw_info():
    """Runs commander-cli to find part number and unique ID from the connected board."""
    if not os.path.exists(COMMANDER_PATH):
        return None, None
    try:
        # 1. Get adapter list to find any connected device's serial number
        out = subprocess.check_output([COMMANDER_PATH, "adapter", "list"], stderr=subprocess.STDOUT).decode()
        sn_match = re.search(r"serialNumber=(\d+)", out)
        if not sn_match:
            return None, None
        sn = sn_match.group(1)

        # 2. Get device info for that serial number
        out = subprocess.check_output([COMMANDER_PATH, "device", "info", "--serialno", sn], stderr=subprocess.STDOUT).decode()
        part_match = re.search(r"Part Number\s+:\s+(.+)", out)
        uid_match = re.search(r"Unique ID\s+:\s+(.+)", out)

        part = part_match.group(1).strip() if part_match else None
        uid = uid_match.group(1).strip() if uid_match else None
        return part, uid
    except Exception:
        return None, None

# -----------------------------
# Configuration & Environment
# -----------------------------
# These should be set in your OS environment or a .env file
WORKSPACE_URL = os.getenv("ZEROBUS_WORKSPACE_URL")
CLIENT_ID = os.getenv("ZEROBUS_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZEROBUS_CLIENT_SECRET")
SERVER_ENDPOINT = os.getenv("ZEROBUS_SERVER_ENDPOINT")
TABLE_NAME = os.getenv("ZEROBUS_TABLE_NAME")
VOLUME_PATH_BASE = os.getenv("DATABRICKS_VOLUME_PATH")

# Local directory to monitor
MONITOR_DIR = r"<PATH_TO_MONITOR_DIR>" # Should match Ble_receiver's OUTPUT_DIR

# SDK imports
try:
    from sml.ops import data as zerobus_data

    ZEROBUS_AVAILABLE = True
except Exception:
    ZEROBUS_AVAILABLE = False

# -----------------------------
# Logger Setup
# -----------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("CloudIngestor")

# -----------------------------
# Databricks Helpers
# -----------------------------
def get_oauth_token():
    if not (WORKSPACE_URL and CLIENT_ID and CLIENT_SECRET):
        return None
    token_url = f"{WORKSPACE_URL.rstrip('/')}/oidc/v1/token"
    try:
        r = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "all-apis",
            },
            timeout=10
        )
        r.raise_for_status()
        return r.json()["access_token"]
    except Exception as e:
        logger.error(f"OAuth token fetch failed: {e}")
        return None

def to_volume_posix(p: str) -> str:
    p = str(p).replace("\\", "/")
    if p.startswith("dbfs:/"):
        p = p.replace("dbfs:/", "/")
    parts = [seg for seg in p.split("/") if seg]
    p = "/" + "/".join(parts)
    if not p.startswith("/Volumes/"):
        return f"/Volumes/{p.lstrip('/')}" # Try to force Volumes prefix
    return p

def dbx_put_file(token, file_bytes, volume_path):
    volume_path = to_volume_posix(volume_path)
    url = f"{WORKSPACE_URL.rstrip('/')}/api/2.0/fs/files{volume_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    try:
        r = requests.put(url, headers=headers, data=file_bytes, params={"overwrite": "true"}, timeout=30)
        if r.status_code not in (200, 204):
            logger.error(f"Files API error {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return False

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
            if not os.path.exists(MONITOR_DIR):
                os.makedirs(MONITOR_DIR, exist_ok=True)
            
            files = [f for f in os.listdir(MONITOR_DIR) if f.lower().endswith('.wav')]
            for f in files:
                fpath = os.path.join(MONITOR_DIR, f)
                if fpath not in seen_files:
                    logger.info(f"New file detected: {f}")
                    file_queue.put(fpath)
                    seen_files.add(fpath)
            
            # Clean up seen_files for files that were moved/deleted
            current_paths = {os.path.join(MONITOR_DIR, f) for f in files}
            seen_files &= current_paths
            
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            
        time.sleep(1)

def uploader_thread():
    """Thread 2: Moves files to the cloud and deletes local copies."""
    logger.info("Uploader started")
    
    # Initialize ZeroBus once
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

    token = None
    token_expiry = 0

    while True:
        fpath = file_queue.get()
        try:
            # Refresh token if needed
            if time.time() > token_expiry - 60:
                token = get_oauth_token()
                if token:
                    token_expiry = time.time() + 3500 # Assume ~1hr life
            
            if not token:
                logger.error("No valid token, skipping upload")
                file_queue.put(fpath) # Retry later
                time.sleep(5)
                continue

            # Load file
            with open(fpath, 'rb') as f:
                wav_bytes = f.read()
            
            fname = os.path.basename(fpath)
            # Parse Format: label_address_name_timestamp.wav
            parts = fname.replace('.wav', '').split('_')
            
            # --- Hardware Detection via Commander CLI ---
            hw_name, hw_id = get_hw_info()
            
            if hw_name and hw_id:
                label = parts[0]
                device_id = hw_id
                device_name = hw_name
            elif len(parts) >= 3:
                label = parts[0]
                device_id = parts[1]
                device_name = parts[2].replace('-', ' ') # Restore spaces
            else:
                label = parts[0] if parts else "unknown"
                device_id = f"Pi-{uuid.getnode():x}"
                device_name = "Raspberry Pi Voice Gateway"

            
            # 1. Upload to Databricks Volume
            dest_path = f"{VOLUME_PATH_BASE.rstrip('/')}/{fname}"
            if dbx_put_file(token, wav_bytes, dest_path):
                logger.info(f"Uploaded {fname} to UC Volume")
                
                # 2. Ingest Metadata to ZeroBus
                if ZEROBUS_AVAILABLE:
                    event = {
                        "device_id":   device_id,
                        "device_name": device_name,
                        "file_name":   fname,
                        "file_path":   to_volume_posix(dest_path),
                        "class_label": label,
                        "content_type": "audio/wav",
                        "sample_rate": 16000,
                        "duration_ms": 1000,
                        "ingest_ts":   int(time.time() * 1_000_000),
                    }
                    try:
                        zerobus_data.ingest([event])
                        logger.info(f"Ingested metadata for {fname}")
                    except Exception as e:
                        logger.error(f"ZeroBus ingest failed for {fname}: {e}")
                
                # 3. Success -> Delete local file
                os.remove(fpath)
                logger.info(f"Removed local file {fname}")
            else:
                logger.error(f"Failed to upload {fname}, keeping local copy")
                # Add back to queue? No, maybe just log it.

        except Exception as e:
            logger.error(f"Uploader error processing {fpath}: {e}")
        finally:
            file_queue.task_done()

# -----------------------------
# Entry Point
# -----------------------------
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
