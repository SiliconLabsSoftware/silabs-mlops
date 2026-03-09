"""
SiLabs Volume + ZeroBus Audio Simulator (spoken GSC-style words, multi-device)

Split ingestion:
  • Raw WAV -> Databricks Unity Catalog Volume (Files API)
  • Metadata -> Delta via ZeroBus (silabs_mlops.data)
  MAKE SURE you have your credentials in .env file
"""

import os
import sys
import io
import time
import uuid
import base64
import random
import argparse
import requests
import numpy as np
import soundfile as sf
from datetime import datetime, timezone
from pathlib import Path
from scipy.signal import resample, resample_poly, fftconvolve

# -------------------------
# Optional .env loader
# -------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# -------------------------
# ZeroBus SDK (optional)
# -------------------------
try:
    from silabs_mlops import data as zerobus_data
    ZEROBUS_AVAILABLE = True
except Exception:
    ZEROBUS_AVAILABLE = False
    print("[warn] ZeroBus SDK not found; metadata ingestion disabled.", file=sys.stderr)

# -------------------------
# TTS (pyttsx3)
# -------------------------
try:
    import pyttsx3
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False

# -------------------------
# Defaults
# -------------------------
SAMPLE_RATE = int(os.getenv("SIM_SAMPLE_RATE", "16000"))
DURATION_MS = int(os.getenv("SIM_DURATION_MS", "1000"))

# Expanded GSC-like label set
DEFAULT_LABELS = [
    "yes","no","up","down","left","right","on","off","stop","go",
    "zero","one","two","three","four","five","six","seven","eight","nine",
    "forward","backward","follow","learn","tree","wow","bed","cat","dog","house"
]

# ============================================================================
# Volumes path normalization (Windows-safe)
# ============================================================================
def to_volume_posix(p: str) -> str:
    """
    Normalize any incoming path to a POSIX UC Volume path:
      - Convert backslashes to forward slashes
      - Strip 'dbfs:/' scheme (Files API expects /Volumes/...)
      - Collapse duplicate slashes
      - Ensure the path begins with '/Volumes/...'
    """
    if p is None:
        raise ValueError("Volume path is None")

    p = str(p).replace("\\", "/")
    if p.startswith("dbfs:/"):
        p = p.replace("dbfs:/", "/")

    parts = [seg for seg in p.split("/") if seg]
    p = "/" + "/".join(parts)

    if not p.startswith("/Volumes/"):
        raise ValueError(f"Volume path must start with /Volumes/. Got: {p}")

    return p

# ============================================================================
# Databricks Authentication
# ============================================================================
def get_oauth_token(host: str, client_id: str, client_secret: str) -> str:
    token_url = f"{host.rstrip('/')}/oidc/v1/token"
    r = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "all-apis",
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]

# ============================================================================
# Databricks Files API (directories & files)
#   - Accept 200 or 204 as success
# ============================================================================
def dbx_mkdirs(host: str, token: str, dir_path: str) -> None:
    dir_path = to_volume_posix(dir_path)
    url = f"{host.rstrip('/')}/api/2.0/fs/directories{dir_path}"
    r = requests.put(url, headers={"Authorization": f"Bearer {token}"})
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"[ERROR] mkdirs failed {r.status_code}: {r.text}")

def dbx_put_file(host: str, token: str, file_bytes: bytes, volume_path: str) -> bool:
    volume_path = to_volume_posix(volume_path)
    url = f"{host.rstrip('/')}/api/2.0/fs/files{volume_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    r = requests.put(url, headers=headers, data=file_bytes, params={"overwrite": "true"})
    if r.status_code not in (200, 204):
        print(f"[ERROR] Files API returned {r.status_code}: {r.text}")
        return False
    return True

def dbx_head_file(host: str, token: str, file_path: str) -> int:
    file_path = to_volume_posix(file_path)
    url = f"{host.rstrip('/')}/api/2.0/fs/files{file_path}"
    r = requests.head(url, headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 200:
        try:
            return int(r.headers.get("Content-Length", "-1"))
        except Exception:
            return -1
    return -1

# ============================================================================
# Audio helpers  (1s/16k/-6 dBFS + gentler augmentation)
# ============================================================================
def to_target_sr_1s(y: np.ndarray, sr_src: int, sr_tgt: int, dur_ms: int) -> np.ndarray:
    if sr_src != sr_tgt:
        g = np.gcd(sr_src, sr_tgt)
        y = resample_poly(y, sr_tgt // g, sr_src // g).astype(np.float32)

    n_tgt = int(sr_tgt * dur_ms / 1000.0)
    if len(y) < n_tgt:
        y = np.pad(y, (0, n_tgt - len(y)))
    elif len(y) > n_tgt:
        start = (len(y) - n_tgt) // 2
        y = y[start:start + n_tgt]

    peak = float(np.max(np.abs(y)) + 1e-12)
    y = (y / peak) * (10 ** (-6 / 20.0))
    return np.clip(y, -1.0, 1.0).astype(np.float32)

def wav_bytes_from_float32(y: np.ndarray, sr: int) -> bytes:
    bio = io.BytesIO()
    sf.write(bio, y, sr, format="WAV", subtype="PCM_16")
    return bio.getvalue()

# Gentler augmentation: closer to GSC public dataset
def speed_perturb(y: np.ndarray, factor: float) -> np.ndarray:
    n_new = max(8, int(len(y) / factor))
    return resample(y, n_new).astype(np.float32)

def schroeder_ir(sr: int, rt60: float = 0.18) -> np.ndarray:
    n = max(64, int(sr * rt60))
    ir = np.zeros(n, dtype=np.float32)
    delays = np.random.randint(sr // 250, sr // 60, size=4)  # smaller, fewer reflections
    gains  = np.random.uniform(0.15, 0.45, size=4)
    for d, g in zip(delays, gains):
        if d < n:
            ir[d] += g
    decay = np.exp(-np.linspace(0, rt60, n) * 6.0).astype(np.float32)
    ir *= decay
    ir[0] += 1.0
    ir /= (np.max(np.abs(ir)) + 1e-12)
    return ir

def add_noise(y: np.ndarray, snr_db: float) -> np.ndarray:
    n = np.random.randn(len(y)).astype(np.float32)
    n = n / (np.max(np.abs(n)) + 1e-12)
    n *= 10 ** ((-6 - snr_db) / 20.0)  # gentler noise (higher SNR)
    return np.clip(y + n, -1, 1).astype(np.float32)

def augment_gentle(y: np.ndarray, sr: int) -> np.ndarray:
    # 50% chance slight speed (0.95–1.05)
    if random.random() < 0.5:
        y = speed_perturb(y, random.uniform(0.95, 1.05))
    # 30% chance light reverb (rt60 ~ 0.12–0.3s)
    if random.random() < 0.3:
        ir = schroeder_ir(sr, rt60=random.uniform(0.12, 0.30))
        y  = fftconvolve(y, ir, mode="full")[:len(y)].astype(np.float32)
    # 40% chance background noise (SNR 22–35 dB) — quieter than before
    if random.random() < 0.4:
        y = add_noise(y, snr_db=random.uniform(22, 35))
    return y

# ============================================================================
# SYNTHESIS MODES
#   tts  : spoken word using pyttsx3 (Windows: SAPI5)
#   tone : synthetic fallback
# ============================================================================
def list_voice_ids() -> list[str]:
    if not TTS_AVAILABLE:
        return []
    eng = pyttsx3.init()
    voices = eng.getProperty("voices")
    ids = []
    for v in voices:
        lang = ""
        try:
            lang = ",".join([str(x) for x in getattr(v, "languages", [])]).lower()
        except Exception:
            pass
        if ("en" in lang) or (not lang):
            ids.append(v.id)
    if not ids and voices:
        ids = [v.id for v in voices]
    return ids

def tts_word_to_array(word: str, sr_tgt: int, dur_ms: int, voice_id: str, rate_wpm: int = 165) -> np.ndarray:
    tmp_wav = Path(os.getenv("TMP", "/tmp")) / f"tts_{uuid.uuid4().hex[:8]}.wav"
    eng = pyttsx3.init()
    eng.setProperty("voice", voice_id)
    eng.setProperty("rate", rate_wpm)
    eng.save_to_file(word, str(tmp_wav))
    eng.runAndWait()

    y, sr0 = sf.read(str(tmp_wav))
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y.astype(np.float32)
    try: tmp_wav.unlink(missing_ok=True)
    except Exception: pass

    # standardize -> gentle augment -> standardize
    y = to_target_sr_1s(y, int(sr0), sr_tgt, dur_ms)
    y = augment_gentle(y, sr_tgt)
    y = to_target_sr_1s(y, sr_tgt, sr_tgt, dur_ms)
    return y

def tone_gsc_like(word: str, sr: int, dur_ms: int) -> np.ndarray:
    # backup when TTS unavailable — still gentler processing
    dur_s = dur_ms / 1000.0
    t = np.linspace(0, dur_s, int(sr * dur_s), endpoint=False)
    base = 0.30 * np.sin(2 * np.pi * 220 * t)
    form = 0.18 * np.sin(2 * np.pi * (900 + 80*np.sin(2*np.pi*2.5*t)) * t + 0.3)
    y = base + form
    y = augment_gentle(y.astype(np.float32), sr)
    y = to_target_sr_1s(y, sr, sr, dur_ms)
    return y

def synth_audio(word: str, mode: str, sr: int, dur_ms: int, voice_pool: list[str]) -> np.ndarray:
    if mode == "tts" and TTS_AVAILABLE and voice_pool:
        voice = random.choice(voice_pool)
        rate  = random.randint(150, 180)  # narrower speaking rate
        try:
            return tts_word_to_array(word, sr, dur_ms, voice, rate_wpm=rate)
        except Exception as e:
            print(f"[warn] TTS failed ({e}); using tone fallback.")
    return tone_gsc_like(word, sr, dur_ms)

# ============================================================================
# Device identity & pool (no "Vol")
# ============================================================================
DEVICE_MODELS = ["EFR32MG24", "EFR32BG24", "EFR32MG21", "EFR32BG22"]

def make_device_identity() -> tuple[str, str]:
    model = random.choice(DEVICE_MODELS)
    tail  = uuid.uuid4().hex[:4].upper()
    device_id = f"SiLabs-{model}-{tail}"
    device_name = f"SiLabs {model} DevKit ({tail})"
    return device_id, device_name

def make_device_pool(n: int) -> list[dict]:
    pool = []
    for _ in range(max(1, n)):
        did, dname = make_device_identity()
        pool.append({"device_id": did, "device_name": dname})
    return pool

# ============================================================================
# ZeroBus event (schema-aligned)
# ============================================================================
def make_event(device_id: str, device_name: str, fname: str, file_path: str, label: str) -> dict:
    return {
        "device_id":   device_id,
        "device_name": device_name,
        "file_name":   fname,
        "file_path":   file_path,
        "class_label": label,
        "content_type": "audio/wav",
        "sample_rate": SAMPLE_RATE,
        "duration_ms": DURATION_MS,
        "ingest_ts":   int(time.time() * 1_000_000),  # microseconds
    }

# ============================================================================
# CLI
# ============================================================================
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SiLabs Volume + Delta Metadata Simulator (spoken GSC words, multi-device)")
    p.add_argument("--device-pool-size", type=int, default=5, help="Number of devices to simulate")
    p.add_argument("--interval-sec", type=float, default=1.0)
    p.add_argument("--volume-path", default=os.getenv("DATABRICKS_VOLUME_PATH"),
                   help="UC Volume base path, e.g., /Volumes/<catalog>/<schema>/<volume>")
    p.add_argument("--count", type=int, default=None, help="Generate N total samples then exit")
    p.add_argument("--store-bytes", action="store_true", help="Attach audio_bytes to Delta row")
    p.add_argument("--synth-mode", choices=["auto", "tts", "tone"], default="auto",
                   help="Speech synthesis mode (default auto: prefer TTS if available)")
    p.add_argument("--labels", default=",".join(DEFAULT_LABELS),
                   help="Comma-separated label set")
    return p.parse_args()

# ============================================================================
# MAIN
# ============================================================================
def main():
    args = parse_args()

    # Validate & normalize volume base
    if not args.volume_path:
        raise SystemExit(
            "ERROR: No --volume-path and DATABRICKS_VOLUME_PATH not set.\n"
            "Example:\n"
            "  DATABRICKS_VOLUME_PATH=/Volumes/mlops_dev/default/audio_raw\n"
            "  python simulate_volume_ingestion.py --count 1"
        )
    volume_base = to_volume_posix(args.volume_path)

    # Databricks Files API token
    workspace_url = os.getenv("ZEROBUS_WORKSPACE_URL")  # e.g., https://adb-...azuredatabricks.net
    client_id     = os.getenv("ZEROBUS_CLIENT_ID")
    client_secret = os.getenv("ZEROBUS_CLIENT_SECRET")
    if not (workspace_url and client_id and client_secret):
        raise SystemExit("ERROR: Missing ZEROBUS_WORKSPACE_URL / ZEROBUS_CLIENT_ID / ZEROBUS_CLIENT_SECRET.")

    try:
        token = get_oauth_token(workspace_url, client_id, client_secret)
        print("[OK] Authenticated with Databricks Files API.")
    except Exception as e:
        raise SystemExit(f"ERROR: OAuth token fetch failed: {e}")

    # ZeroBus configure (optional)
    if ZEROBUS_AVAILABLE:
        try:
            zerobus_data.config(
                server_endpoint=os.getenv("ZEROBUS_SERVER_ENDPOINT"),
                workspace_url=workspace_url,
                table_name=os.getenv("ZEROBUS_TABLE_NAME", "mlops_dev.default.stream_audio_events"),
                client_id=client_id,
                client_secret=client_secret,
            )
            print("[OK] ZeroBus configured.")
        except Exception as e:
            print(f"[warn] ZeroBus config failed: {e}")

    # Label list & voices
    labels = [s.strip() for s in args.labels.split(",") if s.strip()]
    voice_pool = list_voice_ids() if TTS_AVAILABLE else []
    mode = args.synth_mode
    if mode == "auto":
        mode = "tts" if (TTS_AVAILABLE and voice_pool) else "tone"
    if mode == "tts" and not (TTS_AVAILABLE and voice_pool):
        print("[warn] TTS requested but no voices available; using 'tone' fallback.")
        mode = "tone"

    # Device pool
    devices = make_device_pool(args.device_pool_size)

    print(f"\n[sim] Devices     : {len(devices)}")
    print(f"[sim] Volume Path: {volume_base}")
    print(f"[sim] Synth mode : {mode.upper()} (voices={len(voice_pool)})\n")

    sent = 0
    both_ok = 0

    try:
        while True:
            label = random.choice(labels)
            dev   = random.choice(devices)   # pick a device for this sample

            # 1) Generate audio (spoken if TTS)
            y = synth_audio(label, mode, sr=SAMPLE_RATE, dur_ms=DURATION_MS, voice_pool=voice_pool)

            # 2) Encode to WAV bytes
            wav_bytes = wav_bytes_from_float32(y, SAMPLE_RATE)

            # 3) Build destination and ensure directory exists
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            fname = f"{label}_{ts}.wav"                           # no device in filename
            volume_dest = to_volume_posix(f"{volume_base.rstrip('/')}/{fname}")
            parent_dir  = to_volume_posix(str(Path(volume_dest).parent))

            dbx_mkdirs(workspace_url, token, parent_dir)
            upload_ok = dbx_put_file(workspace_url, token, wav_bytes, volume_dest)

            # 4) Ingest metadata (schema aligned) for the chosen device
            event = make_event(dev["device_id"], dev["device_name"], fname, volume_dest, label)
            if args.store_bytes:
                event["audio_bytes"] = base64.b64encode(wav_bytes).decode("utf-8")

            meta_ok = False
            if ZEROBUS_AVAILABLE:
                try:
                    meta_ok = bool(zerobus_data.ingest([event]))
                except Exception as e:
                    print(f"[ERROR] Metadata ingest failed: {e}")

            if upload_ok and meta_ok:
                both_ok += 1

            # per-record log (keep concise)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {'ok' if (upload_ok and meta_ok) else 'partial/failed'} | "
                  f"{dev['device_id']} | {label:7s} | {fname}")

            sent += 1
            if args.count and sent >= args.count:
                break

            time.sleep(args.interval_sec)

    except KeyboardInterrupt:
        print("\n[sim] Stopped by user.")

    # Final single-line result as requested
    print(f"Total records sent: {both_ok}")

if __name__ == "__main__":
    main()