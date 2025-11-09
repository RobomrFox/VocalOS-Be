import sounddevice as sd
import numpy as np
# Add at the very top of your recognizer file
import sys
import os

# Make sure Python can find Talon based on your repo layout
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lang")))

from talon import speech_system

def inject_to_talon(recognized_text):
    speech_system.engine_mimic(recognized_text)

# Wherever you process final STT result:
inject_to_talon(recognized_text)


# List available microphones
def get_microphones():
    devices = sd.query_devices()
    mics = []
    
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            mics.append({
                'id': idx,
                'name': device['name'],
                'is_default': idx == sd.default.device[0]
            })
    
    return mics

# List all audio devices
def list_devices():
    print("Available audio devices:")
    print(sd.query_devices())

def test_microphone(duration=5, device=None):
    print(f"Recording {duration} seconds...")
    sample_rate = 16000
    audio = sd.rec(
        int(duration * sample_rate), 
        samplerate=sample_rate, 
        channels=1, 
        dtype='float32',
        device=device
    )
    sd.wait()
    print("Recording complete!")
    return audio, sample_rate

if __name__ == "__main__":
    print("Available microphones:")
    for mic in get_microphones():
        default_marker = " (default)" if mic['is_default'] else ""
        print(f"  {mic['id']}: {mic['name']}{default_marker}")
    
    print("\nTesting default microphone...")
    audio_data, sr = test_microphone(duration=3)
    print(f"Captured {len(audio_data)} samples at {sr}Hz")
