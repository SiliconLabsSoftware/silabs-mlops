import os
import asyncio
import wave
import struct
import time
import json
import difflib
import numpy as np
from bleak import BleakClient, BleakScanner
from vosk import Model, KaldiRecognizer

# --- Configuration ---
DEVICE_NAME = "<YOUR_DEVICE_NAME>" # e.g., "Voice_BLE_Controller_Demo"
DEVICE_ADDRESS = "<YOUR_DEVICE_ADDRESS>" # e.g., "1C:C0:89:2D:30:45"
VOSK_MODEL_PATH = r"<PATH_TO_VOSK_MODEL>" # e.g., "C:/models/vosk-model-small-en-us-0.15"

# Folder path to store audio samples
OUTPUT_DIR = r"<PATH_TO_OUTPUT_DIR>" # e.g., "C:/audio samples"

# UUIDs from gatt_configuration.btconf
VOICE_RESULT_UUID = "f7ee5e0c-1882-4c85-a6f1-8d6f81f10902"
AUDIO_DATA_UUID = "f7ee5e0c-1882-4c85-a6f1-8d6f81f10903"

# Audio parameters
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2 # 16-bit

# Global state
audio_buffer = bytearray()
current_label = "detection"
classifier = None

# --------------------------
# Audio Helpers (from classifier)
# --------------------------
ON_ALIASES = {"on", "one", "won", "awn", "hon", "on.", "on,", "on!"}
OFF_ALIASES = {"off", "of", "off.", "off,", "off!"}

def normalize_token(tok: str) -> str:
    t = (tok or "").strip().lower()
    if t in ON_ALIASES: return "on"
    if t in OFF_ALIASES: return "off"
    if difflib.SequenceMatcher(None, t, "on").ratio() >= 0.80: return "on"
    if difflib.SequenceMatcher(None, t, "off").ratio() >= 0.80: return "off"
    return t

def rms_dbfs(x: np.ndarray) -> float:
    if x.size == 0: return -120.0
    xf = x.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(xf * xf) + 1e-12))
    return 20.0 * np.log10(rms + 1e-12)

def apply_agc(int16_audio: np.ndarray, target_dbfs: float = -20.0) -> np.ndarray:
    if int16_audio.size == 0: return int16_audio
    cur = rms_dbfs(int16_audio)
    gain = 10.0 ** ((target_dbfs - cur) / 20.0)
    return (int16_audio.astype(np.float32) * gain).clip(-32768, 32767).astype(np.int16)

def simple_energy_vad(int16_audio: np.ndarray, sr: int, energy_thresh: float = 0.0004) -> np.ndarray:
    x = int16_audio.astype(np.float32) / 32768.0
    frame_len = int(sr * 0.02) # 20ms
    energies = [float(np.mean(x[i:i+frame_len]**2)) for i in range(0, len(x), frame_len)]
    if not energies: return int16_audio
    start_f = next((i for i, e in enumerate(energies) if e >= energy_thresh), 0)
    end_f = next((i for i, e in enumerate(reversed(energies)) if e >= energy_thresh), 0)
    start, end = start_f * frame_len, len(int16_audio) - (end_f * frame_len)
    return int16_audio[max(0, start-1600):min(len(int16_audio), end+1600)] # Pad 100ms

class OnOffVosk:
    def __init__(self, model_path: str):
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
        text = res.get("text", "").lower()
        
        # Check final result and individual word confidences
        best_label = "unknown"
        max_conf = 0.0
        if "result" in res:
            for w in res["result"]:
                label = normalize_token(w["word"])
                conf = w["conf"]
                if label in ("on", "off") and conf > max_conf:
                    max_conf = conf
                    best_label = label
        
        # Adaptive Thresholds
        if best_label == "on" and max_conf >= 0.48: return "on"
        if best_label == "off" and max_conf >= 0.55: return "off"
        return "unknown"

def save_wav(data, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(data)
    print(f"Saved: {filename} ({len(data)} bytes)")

async def notification_handler(sender, data):
    global audio_buffer, current_label
    
    if sender.uuid.lower() == AUDIO_DATA_UUID.lower():
        audio_buffer.extend(data)
        if len(audio_buffer) >= 32000:
            final_data = audio_buffer[:32000]
            label_to_save = current_label
            
            # If UNKNOWN, try integrated classifier
            if label_to_save == "unknown" and classifier:
                print("Running background classification...")
                # Run in thread to not block BLE events
                refined_label = await asyncio.to_thread(classifier.predict, bytes(final_data))
                if refined_label != "unknown":
                    print(f"Refined label: UNKNOWN -> {refined_label.upper()}")
                    label_to_save = refined_label

            # Filename format: label_address_name_timestamp.wav
            addr_str = DEVICE_ADDRESS.replace(":", "").replace("-", "")
            name_str = DEVICE_NAME.replace(" ", "-")
            filename = f"{label_to_save}_{addr_str}_{name_str}_{int(time.time())}.wav"
            save_wav(final_data, filename)
            audio_buffer = bytearray()
            print("--- Ready for next detection ---")

    elif sender.uuid.lower() == VOICE_RESULT_UUID.lower():
        ver, class_id, score, flags, ts = struct.unpack("<BBBB I", data)
        labels = ["on", "off", "unknown"]
        current_label = labels[class_id] if class_id < len(labels) else "unknown"
        print(f"\n[EVENT] Firmware Detected: {current_label.upper()} (Score: {score})")
        audio_buffer = bytearray() 

async def main():
    global classifier
    print("Initializing Audio Classifier...")
    try:
        classifier = OnOffVosk(VOSK_MODEL_PATH)
        print("Classifier Ready.")
    except Exception as e:
        print(f"Warning: Could not load classifier: {e}")

    print(f"Scanning for {DEVICE_NAME}...")
    device = await BleakScanner.find_device_by_address(DEVICE_ADDRESS, timeout=10.0)
    if not device:
        device = await BleakScanner.find_device_by_filter(lambda d, ad: d.name == DEVICE_NAME, timeout=10.0)
    if not device:
        print("Could not find device.")
        return

    async with BleakClient(device) as client:
        print(f"Connected to {device.name}")
        await client.start_notify(VOICE_RESULT_UUID, notification_handler)
        await client.start_notify(AUDIO_DATA_UUID, notification_handler)
        print("\n--- Subscribed to Voice Events ---")
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping...")
