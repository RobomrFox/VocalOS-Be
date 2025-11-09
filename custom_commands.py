# custom_commands.py
from core.custom_engine import CustomEngine
from core.app_control import AppControl
import sounddevice as sd
import numpy as np

def record_audio(duration=5, sample_rate=16000):
    print("Recording audio for", duration, "seconds...")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    return np.squeeze(audio)

def main():
    engine = CustomEngine()
    app_ctrl = AppControl()
    
    while True:
        audio = record_audio()
        text = engine.recognize(audio)
        print(f"Recognized: {text}")
        
        # Example commands
        if "open safari" in text.lower():
            app_ctrl.open_app("Safari")
        elif "switch to finder" in text.lower():
            app_ctrl.switch_to_app("Finder")
        elif "quit" in text.lower():
            print("Exiting...")
            break

if __name__ == "__main__":
    main()

