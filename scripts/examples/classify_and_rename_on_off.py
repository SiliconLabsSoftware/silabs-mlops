import os
import re
import json
import argparse
import shutil
from typing import Optional, Tuple

import soundfile as sf
from vosk import Model, KaldiRecognizer
import numpy as np
import difflib

# --------------------------
# Config
# --------------------------
KEYWORDS = ["on", "off"]
DEFAULT_CONF_THRESHOLD = 0.60  # Good default for 0.5–2 s clips
MIN_DURATION_SEC = 0.10  # Accept short clips after VAD
CHUNK_BYTES = 4000
VERBOSE = True

# Sliding-window settings (robust to gaps/unclear speech)
WIN_MS = 500  # window size ~0.5s
HOP_MS = 80  # stride ~80ms (overlap improves recall)

# Aliases (common ASR confusions)
ON_ALIASES = {"on", "one", "won", "awn", "hon", "on.", "on,", "on!"}
OFF_ALIASES = {"off", "of", "off.", "off,", "off!"}


# --------------------------
# Normalization & helpers
# --------------------------
def normalize_token(tok: str) -> str:
    """Map common mis-hearings to canonical labels 'on' or 'off'."""
    t = (tok or "").strip().lower()
    if t in ON_ALIASES:
        return "on"
    if t in OFF_ALIASES:
        return "off"
    if difflib.SequenceMatcher(None, t, "on").ratio() >= 0.80:
        return "on"
    if difflib.SequenceMatcher(None, t, "off").ratio() >= 0.80:
        return "off"
    return t


def rms_dbfs(x: np.ndarray) -> float:
    """Return RMS in dBFS for int16 signal normalized to [-1,1]."""
    if x.size == 0:
        return -120.0
    xf = x.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(xf * xf) + 1e-12))
    return 20.0 * np.log10(rms + 1e-12)


def apply_agc(int16_audio: np.ndarray, target_dbfs: float = -20.0) -> np.ndarray:
    """Simple loudness normalization to target RMS (dBFS)."""
    if int16_audio.size == 0:
        return int16_audio
    cur = rms_dbfs(int16_audio)
    gain_db = target_dbfs - cur
    gain = 10.0 ** (gain_db / 20.0)
    xf = (int16_audio.astype(np.float32) * gain).clip(-32768, 32767)
    return xf.astype(np.int16)


def simple_energy_vad(
    int16_audio: np.ndarray,
    sr: int,
    frame_ms: float = 20.0,
    energy_thresh: float = 0.0005,
    pad_ms: float = 100.0,
) -> np.ndarray:
    """
    Trims leading/trailing silence using a simple energy threshold on ~20 ms frames.
    Returns a trimmed int16 mono array.
    """
    if int16_audio.ndim != 1:
        int16_audio = int16_audio.reshape(-1)

    # normalize to [-1, 1] float for energy calc
    x = int16_audio.astype(np.float32) / 32768.0
    frame_len = int(sr * frame_ms / 1000.0)
    frame_len = max(frame_len, 1)
    energies = []
    for i in range(0, len(x), frame_len):
        frame = x[i : i + frame_len]
        if len(frame) == 0:
            break
        energies.append(float(np.mean(frame * frame)))
    if not energies:
        return int16_audio

    # find first/last frames above threshold
    start_f = 0
    while start_f < len(energies) and energies[start_f] < energy_thresh:
        start_f += 1
    end_f = len(energies) - 1
    while end_f >= 0 and energies[end_f] < energy_thresh:
        end_f -= 1

    if start_f >= end_f:
        return int16_audio  # mostly silence or very low energy

    pad = int(sr * pad_ms / 1000.0)
    start = max(0, start_f * frame_len - pad)
    end = min(len(int16_audio), (end_f + 1) * frame_len + pad)
    return int16_audio[start:end]


# --------------------------
# Filename helpers
# --------------------------
def extract_id_from_filename(fname: str) -> str:
    base = os.path.basename(fname)
    m = re.match(r"unknown_(\d+)\.wav$", base, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    digits = re.sub(r"\D+", "", os.path.splitext(base)[0])
    return digits if digits else "0"


def make_target_path(src_path: str, label: str, out_dir: Optional[str] = None) -> str:
    file_id = extract_id_from_filename(src_path)
    target_dir = out_dir if out_dir else os.path.dirname(src_path)
    return os.path.join(target_dir, f"{label}_{file_id}.wav")


def copy_labeled(
    src_path: str, label: str, out_dir: Optional[str] = None, dry_run: bool = False
):
    """
    Create a renamed COPY in the output folder (keep original in inbox).
    """
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(src_path), "classified")
    os.makedirs(out_dir, exist_ok=True)

    base_dst = make_target_path(src_path, label, out_dir)
    dst_path = base_dst
    if os.path.exists(dst_path):
        stem, ext = os.path.splitext(dst_path)
        n = 1
        while True:
            candidate = f"{stem}_{n}{ext}"
            if not os.path.exists(candidate):
                dst_path = candidate
                break
            n += 1

    if dry_run:
        print(f"[DRY-RUN] Would COPY: {src_path} -> {dst_path}")
        return

    shutil.copy2(src_path, dst_path)
    print(f"[COPIED] {os.path.basename(src_path)} -> {dst_path}")


# --------------------------
# Audio I/O (int16 mono, 16 kHz)
# --------------------------
def load_audio_int16(
    file_path: str, target_sr: int = 16000
) -> Tuple[Optional[np.ndarray], Optional[int], Optional[float]]:
    try:
        audio, sr = sf.read(file_path, dtype="int16", always_2d=True)
    except Exception as e:
        print(f"[ERROR] Cannot read {file_path}: {e}")
        return None, None, None

    mono = audio.mean(axis=1).astype("int16") if audio.shape[1] > 1 else audio[:, 0]

    # Resample (simple linear interpolation; good enough for 16k speech)
    if sr != target_sr and sr > 0:
        x_old = np.linspace(0, 1, num=len(mono), endpoint=False)
        x_new = np.linspace(0, 1, num=int(len(mono) * target_sr / sr), endpoint=False)
        mono = np.interp(x_new, x_old, mono).astype("int16")
        sr = target_sr

    # AGC normalization (helps unclear/quiet speech)
    mono = apply_agc(mono, target_dbfs=-20.0)

    duration = len(mono) / sr if sr and sr > 0 else 0.0
    return mono, sr, duration


# --------------------------
# Vosk classifier with multi-path decoding
# --------------------------
class OnOffVosk:
    def __init__(self, model_dir: str, conf_threshold: float = DEFAULT_CONF_THRESHOLD):
        if not os.path.isdir(model_dir):
            raise RuntimeError(f"Vosk model folder not found: {model_dir}")
        self.model = Model(model_dir)
        self.conf_threshold = conf_threshold
        # Slightly easier acceptance for "on" (common under-detection)
        self.off_min_conf = conf_threshold
        self.on_min_conf = min(0.50, conf_threshold - 0.10)  # e.g., 0.60 -> 0.50

    def _accumulate_words(self, rec: KaldiRecognizer, pcm_bytes: bytes):
        """Stream bytes into recognizer, collect partial keyword hints + final words."""
        partial_words = []
        for i in range(0, len(pcm_bytes), CHUNK_BYTES):
            rec.AcceptWaveform(pcm_bytes[i : i + CHUNK_BYTES])
            try:
                pdata = json.loads(rec.PartialResult() or "{}")
                part = (pdata.get("partial") or "").strip().lower()
                if part:
                    for tok in part.split():
                        nt = normalize_token(tok)
                        if nt in ("on", "off"):
                            # partial evidence, bias 'on' slightly
                            base_conf = 0.53 if nt == "on" else 0.50
                            partial_words.append({"word": nt, "conf": base_conf})
            except Exception:
                pass

        fdata = json.loads(rec.FinalResult() or "{}")
        text_hint = fdata.get("text") or ""
        final_words = []
        if "result" in fdata:
            for w in fdata["result"]:
                final_words.append(
                    {
                        "word": normalize_token((w.get("word") or "")),
                        "conf": float(w.get("conf") or 0.0),
                    }
                )
        return final_words + partial_words, text_hint

    def _pick_best(self, words, text_hint: str, on_min: float, off_min: float):
        # Aggregate max confidence per canonical label
        best = {"on": 0.0, "off": 0.0}
        for w in words:
            ww = normalize_token(w.get("word") or "")
            cc = float(w.get("conf") or 0.0)
            if ww in best:
                best[ww] = max(best[ww], cc)

        # final transcript contains 'on' → give a small boost
        if " on " in f" {text_hint.lower()} ":
            best["on"] = max(best["on"], 0.55)

        # Decide with asymmetric thresholds
        label, conf = None, 0.0
        if best["off"] >= off_min and best["off"] >= best["on"]:
            label, conf = "off", best["off"]
        if best["on"] >= on_min and best["on"] > conf:
            label, conf = "on", best["on"]
        return label, conf, best

    def _decode_clip(self, pcm_int16: np.ndarray, sr: int):
        """Decode entire clip with constrained grammar."""
        if pcm_int16.size == 0:
            return None, 0.0, {"on": 0.0, "off": 0.0}
        rec = KaldiRecognizer(self.model, sr)
        rec.SetWords(True)
        rec.SetGrammar('["on","off","one","won","awn","hon","of","[unk]"]')
        pcm_bytes = pcm_int16.tobytes()
        words, text_hint = self._accumulate_words(rec, pcm_bytes)
        label, conf, best = self._pick_best(
            words, text_hint, self.on_min_conf, self.off_min_conf
        )
        return label, conf, best

    def _decode_windows(self, pcm_int16: np.ndarray, sr: int):
        """Sliding-window decoding to catch very short 'on' with gaps."""
        if pcm_int16.size == 0:
            return None, 0.0, {"on": 0.0, "off": 0.0}
        N = len(pcm_int16)
        win = int(sr * WIN_MS / 1000.0)
        hop = int(sr * HOP_MS / 1000.0)
        best_overall = {"on": 0.0, "off": 0.0}
        label_best, conf_best = None, 0.0

        for start in range(0, max(1, N - win + 1), hop):
            end = min(N, start + win)
            chunk = pcm_int16[start:end]
            rec = KaldiRecognizer(self.model, sr)
            rec.SetWords(True)
            rec.SetGrammar('["on","off","one","won","awn","hon","of","[unk]"]')
            words, text_hint = self._accumulate_words(rec, chunk.tobytes())
            label, conf, best = self._pick_best(
                words, text_hint, self.on_min_conf, self.off_min_conf
            )

            # Track maxima
            best_overall["on"] = max(best_overall["on"], best["on"])
            best_overall["off"] = max(best_overall["off"], best["off"])
            if label and conf > conf_best:
                label_best, conf_best = label, conf

        return label_best, conf_best, best_overall

    def predict(self, wav_path: str):
        # Load & normalize
        mono, sr, _ = load_audio_int16(wav_path)
        if mono is None:
            return None, 0.0

        # Path A: full clip (raw, AGC only)
        label_full, conf_full, best_full = self._decode_clip(mono, sr)

        # Path B: VAD-trimmed (keeps more relevant speech; robust to leading gaps)
        mono_vad = simple_energy_vad(
            mono, sr, frame_ms=20.0, energy_thresh=0.0004, pad_ms=120.0
        )
        label_vad, conf_vad, best_vad = self._decode_clip(mono_vad, sr)

        # Path C: Sliding windows (catches super-short 'on' fragments)
        label_win, conf_win, best_win = self._decode_windows(mono, sr)

        # Combine evidence: take the highest-confidence valid label across paths
        candidates = [
            ("full", label_full, conf_full),
            ("vad", label_vad, conf_vad),
            ("win", label_win, conf_win),
        ]
        # If nothing crosses the threshold, consider adaptive relaxation for 'on'
        chosen_label, chosen_conf = None, 0.0
        for src, lab, conf in sorted(candidates, key=lambda t: t[2], reverse=True):
            if lab == "off" and conf >= self.off_min_conf:
                chosen_label, chosen_conf = lab, conf
                break
            if lab == "on" and conf >= self.on_min_conf:
                chosen_label, chosen_conf = lab, conf
                break

        # Adaptive fallback: if still nothing, pick the overall max if it's close enough
        if not chosen_label:
            # Compute overall maxima
            on_max = max(best_full["on"], best_vad["on"], best_win["on"])
            off_max = max(best_full["off"], best_vad["off"], best_win["off"])
            # Soft floor for 'on' (0.48) and 'off' (0.55)
            if off_max >= 0.55 and off_max >= on_max:
                chosen_label, chosen_conf = "off", off_max
            elif on_max >= 0.48:
                chosen_label, chosen_conf = "on", on_max

        # Debug (optional)
        # if VERBOSE:
        #     print(f"[DEBUG] full={best_full} vad={best_vad} win={best_win} -> {chosen_label}:{chosen_conf:.2f}")

        return chosen_label, chosen_conf


# --------------------------
# Core processing
# --------------------------
def process_one_file(
    wav_path: str, classifier: OnOffVosk, out_dir: Optional[str], dry_run: bool
):
    base = os.path.basename(wav_path)
    if not re.match(r"unknown_.*\.wav$", base, flags=re.IGNORECASE):
        if VERBOSE:
            print(f"[SKIP] Not an unknown_* file: {base}")
        return
    label, conf = classifier.predict(wav_path)
    if label in ("on", "off"):
        print(f"[DETECTED] {label.upper()} (conf={conf:.2f}) in {base}")
        copy_labeled(
            wav_path, label, out_dir, dry_run=dry_run
        )  # COPY (keep original in inbox)
    else:
        print(f"[NO-DECISION] {base} — could not confidently detect 'on'/'off'")


def process_batch(
    inbox: str, classifier: OnOffVosk, out_dir: Optional[str], dry_run: bool
):
    files = [
        os.path.join(inbox, f)
        for f in os.listdir(inbox)
        if re.match(r"unknown_.*\.wav$", f, flags=re.IGNORECASE)
    ]
    if not files:
        print("[INFO] No files matching unknown_*.wav")
        return
    for f in sorted(files):
        try:
            process_one_file(f, classifier, out_dir, dry_run)
        except Exception as e:
            print(f"[ERROR] {os.path.basename(f)}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Detect 'on'/'off' in unknown_*.wav and copy labeled files to output."
    )
    parser.add_argument(
        "--inbox", required=True, help="Directory containing unknown_*.wav files."
    )
    parser.add_argument(
        "--model", required=True, help="Path to Vosk model (unzipped folder)."
    )
    parser.add_argument(
        "--out", default=None, help="Output folder (default: <inbox>/classified)."
    )
    parser.add_argument(
        "--dry", action="store_true", help="Dry-run: don't actually copy files."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_CONF_THRESHOLD,
        help=f"Base confidence threshold (default {DEFAULT_CONF_THRESHOLD}).",
    )
    args = parser.parse_args()

    inbox = args.inbox
    out_dir = args.out
    dry_run = args.dry
    threshold = args.threshold

    if not os.path.isdir(inbox):
        raise SystemExit(f"Inbox not found: {inbox}")
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    classifier = OnOffVosk(args.model, conf_threshold=threshold)
    process_batch(inbox, classifier, out_dir, dry_run)


if __name__ == "__main__":
    main()
