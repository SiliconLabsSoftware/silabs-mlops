import os
import wave
import json
import difflib
import numpy as np
from vosk import Model, KaldiRecognizer

# --- Audio Helpers ---

ON_ALIASES = {"on", "one", "won", "awn", "hon", "on.", "on,", "on!"}
OFF_ALIASES = {"off", "of", "off.", "off,", "off!"}


def normalize_token(tok: str) -> str:
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
    if x.size == 0:
        return -120.0
    xf = x.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(xf * xf) + 1e-12))
    return 20.0 * np.log10(rms + 1e-12)


def apply_agc(int16_audio: np.ndarray, target_dbfs: float = -20.0) -> np.ndarray:
    if int16_audio.size == 0:
        return int16_audio
    cur = rms_dbfs(int16_audio)
    gain = 10.0 ** ((target_dbfs - cur) / 20.0)
    return (int16_audio.astype(np.float32) * gain).clip(-32768, 32767).astype(np.int16)


def simple_energy_vad(
    int16_audio: np.ndarray, sr: int, energy_thresh: float = 0.0004
) -> np.ndarray:
    x = int16_audio.astype(np.float32) / 32768.0
    frame_len = int(sr * 0.02)  # 20ms
    energies = [
        float(np.mean(x[i : i + frame_len] ** 2)) for i in range(0, len(x), frame_len)
    ]
    if not energies:
        return int16_audio
    start_f = next((i for i, e in enumerate(energies) if e >= energy_thresh), 0)
    end_f = next((i for i, e in enumerate(reversed(energies)) if e >= energy_thresh), 0)
    start, end = start_f * frame_len, len(int16_audio) - (end_f * frame_len)
    return int16_audio[
        max(0, start - 1600) : min(len(int16_audio), end + 1600)
    ]  # Pad 100ms


class OnOffVosk:
    def __init__(self, model_path: str):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vosk model not found at: {model_path}")
        self.model = Model(model_path)

    def predict(self, pcm_data: bytes) -> str:
        int16_audio = np.frombuffer(pcm_data, dtype=np.int16)
        # Apply AGC and VAD to improve detection
        processed = apply_agc(int16_audio)
        processed = simple_energy_vad(processed, 16000)

        rec = KaldiRecognizer(self.model, 16000)
        rec.SetWords(True)
        rec.SetGrammar('["on","off","one","won","awn","hon","of","[unk]"]')
        rec.AcceptWaveform(processed.tobytes())

        res = json.loads(rec.FinalResult())
        best_label = "unknown"
        max_conf = 0.0

        if "result" in res:
            for w in res["result"]:
                label = normalize_token(w["word"])
                conf = w["conf"]
                if label in ("on", "off"):
                    if conf > max_conf:
                        max_conf = conf
                        best_label = label

        # Adaptive Thresholds (Slightly relaxed for better initial success)
        if best_label == "on" and max_conf >= 0.40:
            return "on"
        if best_label == "off" and max_conf >= 0.45:
            return "off"

        if max_conf > 0:
            return f"unknown (best guess: {best_label} @ {max_conf:.2f})"
        return "unknown"


def run_refinement(audio_dir, model_dir, auto_rename=False):
    """
    Main entry point for Databricks or local batch processing.
    Scans for 'unknown' files and re-labels them based on Vosk results.
    """
    if not os.path.exists(model_dir):
        print(f"Error: Model directory not found at {model_dir}")
        return []

    if not os.path.exists(audio_dir):
        print(f"Error: Audio directory not found at {audio_dir}")
        return []

    print(f"Initializing Vosk Classifier from {model_dir}...")
    classifier = OnOffVosk(model_dir)
    files = [f for f in os.listdir(audio_dir) if f.lower().endswith(".wav")]

    results = []
    print(f"Scanning {len(files)} files in {audio_dir}...")

    unknown_files = [f for f in files if f.lower().startswith("unknown")]
    print(f"Found {len(unknown_files)} files starting with 'unknown'.")

    for f in unknown_files:
        path = os.path.join(audio_dir, f)
        try:
            with wave.open(path, "rb") as wf:
                pcm_data = wf.readframes(wf.getnframes())

            refined = classifier.predict(pcm_data)
            if refined in ("on", "off"):
                new_name = refined + f[7:]
                full_old_path = os.path.join(audio_dir, f)
                full_new_path = os.path.join(audio_dir, new_name)

                results.append(
                    {
                        "original_name": f,
                        "new_name": new_name,
                        "original_path": full_old_path,
                        "new_path": full_new_path,
                        "refined_label": refined,
                    }
                )

                if auto_rename:
                    try:
                        os.rename(full_old_path, full_new_path)
                        print(f" [OK] Renamed: {f} -> {new_name}")
                    except Exception as re:
                        print(f" [WARN] Match found but rename failed: {re}")
                else:
                    print(f" [MATCH] {f} -> {new_name} (auto_rename=False)")
            else:
                print(f" [LOW CONF] {f}: {refined}")
        except Exception as e:
            print(f" [FAIL] Could not process {f}: {e}")

    print(f"Done. Refined {len(results)} files.")
    return results


if __name__ == "__main__":
    # Local Example
    run_refinement("C:/audio samples", "C:/models/vosk-model-small-en-us")
