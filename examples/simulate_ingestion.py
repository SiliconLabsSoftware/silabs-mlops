"""
Silicon Labs Edge Audio Simulator (Local Files → ZeroBus → Delta[BINARY])

What this does:
  • Continuously generates *spoken* GSC-style audio:
      - 1-second mono WAV @ 16 kHz (GSC-like shape)
      - Labels drawn from a GSC-style vocabulary (yes/no/up/down/...)
      - Random voice, speaking rate, speed (resample), light room reverb, background noise
  • Saves each .wav LOCALLY into SIM_LOCAL_DIR/<label>/ (no cloud/DBFS)
  • Sends a ZeroBus ingest record with:
        file_name, file_path (local), class_label, content_type, sample_rate,
        duration_ms, ingest_ts (microseconds), and audio_bytes (base64 string)
    NOTE: audio_bytes is BASE64 *string* (JSON-safe). When Databricks receives this Base64 string,
it will automatically decode it back into raw binary if your Delta Table column is configured as a BINARY type!

Run (example):
  export SIM_LOCAL_DIR=./out_wavs
  export ZEROBUS_SERVER_ENDPOINT=...
  export ZEROBUS_WORKSPACE_URL=...
  export ZEROBUS_TABLE_NAME=bronze_audio_events
  export ZEROBUS_CLIENT_ID=...
  export ZEROBUS_CLIENT_SECRET=...
  python simulate_ingest_gsc_local.py --interval-sec 0.5 --sample-rate 16000 --duration-ms 1000

Dependencies:
  pip install pyttsx3 numpy scipy soundfile python-dotenv
"""

import os
import io
import sys
import time
import uuid
import base64
import random
import string
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple

# Optional dotenv
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(): pass

# Numeric / audio
try:
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample, resample_poly, fftconvolve
except ImportError:
    print("Please install dependencies: pip install pyttsx3 numpy scipy soundfile python-dotenv", file=sys.stderr)
    sys.exit(2)

# Local TTS (fully offline on Windows via SAPI5)
try:
    import pyttsx3
except ImportError:
    print("pyttsx3 is required for local speech synthesis. pip install pyttsx3", file=sys.stderr)
    sys.exit(2)

# ZeroBus SDK
try:
    from silabs_mlops import data as zerobus_data
except Exception:
    zerobus_data = None
    print("[warn] 'silabs_mlops' SDK not found. WAVs will be saved locally but ingestion will be skipped.",
          file=sys.stderr)


# ---------------------------- Defaults & Args ----------------------------

DEFAULT_LABELS = [
    "yes","no","up","down","left","right","on","off","stop","go",
    "zero","one","two","three","four","five","six","seven","eight","nine"
]

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SiLabs Edge Audio Simulator (Local → ZeroBus → Delta[BINARY])")
    p = argparse.ArgumentParser(description="SiLabs Edge Audio Simulator (Local → ZeroBus → Delta[BINARY])")
    p.add_argument("--device-pool-size", type=int, default=5,
                   help="Number of unique device IDs to simulate")
    p.add_argument("--local-dir",    default=os.getenv("SIM_LOCAL_DIR", "./out_wavs"),
                   help="Local folder to save generated WAVs")
    p.add_argument("--interval-sec", type=float, default=float(os.getenv("SIM_INTERVAL_SEC", "0.5")))
    p.add_argument("--sample-rate",  type=int,   default=int(os.getenv("SIM_SAMPLE_RATE", "16000")))
    p.add_argument("--duration-ms",  type=int,   default=int(os.getenv("SIM_DURATION_MS", "1000")))
    p.add_argument("--labels",       default=os.getenv("SIM_LABELS", ",".join(DEFAULT_LABELS)),
                   help="Comma-separated label set (GSC-like). Ex: yes,no,up,down")
    p.add_argument("--seed",         type=int,   default=None)
    p.add_argument("--count",        type=int,   default=None, help="Generate N samples then exit")
    p.add_argument("--log-bytes",    action="store_true", help="Print byte size per payload")
    return p.parse_args()


# ---------------------------- Utility helpers ----------------------------

def now_us() -> int:
    return int(time.time() * 1_000_000)

def rand_suffix(n: int = 4) -> str:
    import string as _s
    return "".join(random.choices(_s.ascii_lowercase + _s.digits, k=n))

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


# ---------------------------- Audio helpers ------------------------------

def list_voice_ids() -> list[str]:
    eng = pyttsx3.init()
    voices = eng.getProperty("voices")
    return [v.id for v in voices] if voices else []

def tts_to_wav(tmp_wav: Path, text: str, voice_id: str, rate_wpm: int, volume: float = 1.0):
    """Synthesize text to WAV file using pyttsx3."""
    eng = pyttsx3.init()
    eng.setProperty("voice",  voice_id)
    eng.setProperty("rate",   rate_wpm)   # ~120–210 typical
    eng.setProperty("volume", volume)     # 0.0–1.0
    eng.save_to_file(text, str(tmp_wav))
    eng.runAndWait()

def load_wav(path: Path) -> tuple[np.ndarray, int]:
    y, sr = sf.read(str(path), always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    return y.astype(np.float32), int(sr)

def to_target_sr_1s(y: np.ndarray, sr_src: int, sr_tgt: int, dur_ms: int, norm_dbfs: float = -6.0):
    # resample to target
    if sr_src != sr_tgt:
        up, down = sr_tgt, sr_src
        g = np.gcd(up, down)
        y = resample_poly(y, up // g, down // g).astype(np.float32)
    # pad/crop to exactly N samples
    n_tgt = int(sr_tgt * dur_ms / 1000.0)
    if len(y) < n_tgt:
        y = np.pad(y, (0, n_tgt - len(y)))
    elif len(y) > n_tgt:
        start = (len(y) - n_tgt) // 2
        y = y[start:start + n_tgt]
    # peak normalize to target dBFS
    peak = float(np.max(np.abs(y)) + 1e-12)
    y = (y / peak) * (10.0 ** (norm_dbfs / 20.0))
    return np.clip(y, -1.0, 1.0).astype(np.float32)

def speed_perturb(y: np.ndarray, factor: float) -> np.ndarray:
    """Change speed by resampling (also shifts pitch)."""
    n_new = max(8, int(len(y) / factor))
    return resample(y, n_new).astype(np.float32)

def rand_noise(n: int, snr_db: float = 20.0) -> np.ndarray:
    """White noise scaled for SNR relative to ~ -6 dBFS speech."""
    noise = np.random.randn(n).astype(np.float32)
    noise = noise / (np.max(np.abs(noise)) + 1e-12)
    noise *= 10 ** ((-6 - snr_db) / 20.0)
    return noise

def schroeder_ir(sr: int, rt60: float = 0.3) -> np.ndarray:
    """Tiny synthetic room impulse response for light reverb."""
    n = max(64, int(sr * rt60))
    ir = np.zeros(n, dtype=np.float32)
    delays = np.random.randint(sr // 200, sr // 40, size=6)  # 5–25 ms
    gains  = np.random.uniform(0.2, 0.8, size=6)
    for d, g in zip(delays, gains):
        if d < n:
            ir[d] += g
    ir *= np.exp(-np.linspace(0, rt60, n) * 6.0).astype(np.float32)
    ir[0] += 1.0
    ir /= (np.max(np.abs(ir)) + 1e-12)
    return ir

def augment(y: np.ndarray, sr: int) -> np.ndarray:
    # speed +/- 10%
    if random.random() < 0.8:
        factor = random.uniform(0.9, 1.1)
        y = speed_perturb(y, factor)
    # light reverb
    if random.random() < 0.6:
        ir = schroeder_ir(sr, rt60=random.uniform(0.15, 0.5))
        y  = fftconvolve(y, ir, mode="full")[: len(y)].astype(np.float32)
    # background noise 10–30 dB SNR
    if random.random() < 0.8:
        snr = random.uniform(10, 30)
        y = np.clip(y + rand_noise(len(y), snr_db=snr), -1, 1)
    return y


# ---------------------------- Main loop ----------------------------

def main():
    load_dotenv()
    args = parse_args()

    # labels
    labels = [s.strip() for s in args.labels.split(",") if s.strip()]
    if not labels:
        labels = DEFAULT_LABELS

    # seed (optional)
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    # voice selection
    voice_ids = list_voice_ids()
    if not voice_ids:
        print("No local TTS voices found for pyttsx3; install a SAPI5/espeak voice and retry.", file=sys.stderr)
        sys.exit(2)

    # init ZeroBus config (if SDK is present)
    if zerobus_data:
        try:
            zerobus_data.config(
                server_endpoint=os.getenv("ZEROBUS_SERVER_ENDPOINT"),
                workspace_url=os.getenv("ZEROBUS_WORKSPACE_URL"),
                table_name=os.getenv("ZEROBUS_TABLE_NAME"),   # e.g., bronze_audio_events
                client_id=os.getenv("ZEROBUS_CLIENT_ID"),
                client_secret=os.getenv("ZEROBUS_CLIENT_SECRET"),
            )
        except Exception as e:
            print(f"[warn] ZeroBus config failed: {e}", file=sys.stderr)

    out_root = Path(args.local_dir)
    ensure_dir(out_root)

    #print("\n[sim] SiLabs Speech Simulator (GSC-like)")
    
    # Generate a pool of distinct devices
    pool_size = max(1, args.device_pool_size)
    device_pool = []
    for i in range(pool_size):
        did = f"SiLabs_{uuid.uuid4().hex[:6]}"
        dname = f"Audio Node {i+1} ({did[-4:]})"
        device_pool.append({"id": did, "name": dname})

    print("\nPress Ctrl+C to stop.\n")

    sent = 0
    try:
        while True:
            label   = random.choice(labels)
            voice   = random.choice(voice_ids)
            rate    = random.randint(120, 210)
            volume  = random.uniform(0.8, 1.0)

            # 1) TTS → temp WAV
            tmp_wav = Path(Path(os.getenv("TMP", ".")) / f"tts_{uuid.uuid4().hex[:8]}.wav")
            tts_to_wav(tmp_wav, label, voice, rate, volume=volume)

            # 2) Standardize to 16kHz, 1.0s, -6 dBFS
            y, sr0 = load_wav(tmp_wav)
            y      = to_target_sr_1s(y, sr0, args.sample_rate, args.duration_ms, norm_dbfs=-6.0)

            # 3) Augment (speed/reverb/noise), then refit to 1.0 s again in case length changed
            y = augment(y, args.sample_rate)
            y = to_target_sr_1s(y, args.sample_rate, args.sample_rate, args.duration_ms, norm_dbfs=-6.0)

            # 4) Save locally under <local-dir>/<label>/
            ts_iso  = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            fname   = f"{label}_{ts_iso}_{rand_suffix()}.wav"
            out_dir = out_root / label
            ensure_dir(out_dir)
            out_wav = out_dir / fname
            sf.write(out_wav, y, args.sample_rate, subtype="PCM_16")

            # 5) Read & base64-encode so JSON transport (ZeroBus) won't fail on bytes
            with open(out_wav, "rb") as f:
                wav_bytes = f.read()

            # Randomly pick which device generated this record
            device = random.choice(device_pool)

            event = {
                "device_id":   device["id"],
                "device_name": device["name"],
                "file_name":   fname,
                "file_path":   str(out_wav),
                "class_label": label,
                "content_type": "audio/wav",
                "sample_rate": int(args.sample_rate),
                "duration_ms": int(args.duration_ms),
                "ingest_ts":   now_us(),
                "audio_bytes": base64.b64encode(wav_bytes).decode("utf-8")
            }

            ok = False
            if zerobus_data:
                try:
                    ok = bool(zerobus_data.ingest([event]))
                except Exception as e:
                    print(f"[warn] ZeroBus ingest failed: {e}", file=sys.stderr)

            status = "ok" if ok else ("skipped" if zerobus_data is None else "FAILED")
            if args.log_bytes:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{device['id']}] {status:7s}  {label:>5s}  {fname}  bytes={len(y)*2}")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{device['id']}] {status:7s}  {label:>5s}  {fname}")

            # cleanup temp
            try: tmp_wav.unlink(missing_ok=True)
            except Exception: pass

            sent += 1
            if args.count is not None and sent >= args.count:
                break
            time.sleep(args.interval_sec)

    except KeyboardInterrupt:
        print("\n[sim] Stopped by user.")
    finally:
        pass

    print(f"[sim] Finished. Total records generated: {sent}")


if __name__ == "__main__":
    main()