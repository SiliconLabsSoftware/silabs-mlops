# SPDX-License-Identifier: LicenseRef-MSLA
# @file receiver.py
# @brief Async BLE client for scanning, streaming, and saving audio.
#
# # License
# Copyright 2026 Silicon Laboratories Inc. www.silabs.com
#
# The licensor of this software is Silicon Laboratories Inc. Your use of this
# software is governed by the terms of Silicon Labs Master Software License
# Agreement (MSLA) available at
# www.silabs.com/about-us/legal/master-software-license-agreement. This
# software is distributed to you in Source Code format and is governed by the
# sections of the MSLA applicable to Source Code.
#
# By installing, copying or otherwise using this software, you agree to the
# terms of the MSLA.

import os
import wave
import time
import struct
import asyncio
from typing import Optional
from bleak import BleakClient, BleakScanner
from .config import BLEConfig

class BLEReceiver:
    def __init__(self, config: Optional[BLEConfig] = None):
        if config is None:
            from sml.ops.ble import _config   
            if _config is None:
                raise ValueError("No BLE configuration provided. Call ble.config() first or pass a BLEConfig instance.")
            config = _config
            
        self.config = config
        self.audio_buffer = bytearray()
        self.current_label = "detection"
        self._is_running = False

    def save_wav(self, data, filename):
        os.makedirs(self.config.output_dir, exist_ok=True)
        filepath = os.path.join(self.config.output_dir, filename)
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(self.config.channels)
            wf.setsampwidth(self.config.sample_width)
            wf.setframerate(self.config.sample_rate)
            wf.writeframes(data)
        print(f"Saved: {filename} ({len(data)} bytes)")

    async def notification_handler(self, sender, data):
        if sender.uuid.lower() == self.config.audio_data_uuid.lower():
            self.audio_buffer.extend(data)
            if len(self.audio_buffer) >= self.config.buffer_size:
                final_data = self.audio_buffer[:self.config.buffer_size]
                label_to_save = self.current_label
                filename = f"{label_to_save}_{int(time.time())}.wav"
                self.save_wav(final_data, filename)
                self.audio_buffer = bytearray()
                print("--- Ready for next detection ---")

        elif sender.uuid.lower() == self.config.voice_result_uuid.lower():
            ver, class_id, score, flags, ts = struct.unpack("<BBBB I", data)
            self.current_label = self.config.labels[class_id] if class_id < len(self.config.labels) else "unknown"
            print(f"\n[EVENT] Firmware Detected: {self.current_label.upper()} (Score: {score})")
            self.audio_buffer = bytearray() 

    async def start(self):
        print(f"Scanning for {self.config.device_name}...")
        device = await BleakScanner.find_device_by_address(self.config.device_address, timeout=10.0)
        if not device:
            device = await BleakScanner.find_device_by_filter(lambda d, ad: d.name == self.config.device_name, timeout=10.0)
        
        if not device:
            print("Could not find device.")
            return

        async with BleakClient(device) as client:
            print(f"Connected to {device.name}")
            await client.start_notify(self.config.voice_result_uuid, self.notification_handler)
            await client.start_notify(self.config.audio_data_uuid, self.notification_handler)
            print("\n--- Subscribed to Voice Events ---")
            self._is_running = True
            while self._is_running:
                await asyncio.sleep(1)

    def stop(self):
        self._is_running = False
