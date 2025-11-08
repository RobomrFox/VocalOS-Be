# custom_engine.py
from src.stt import load_model, transcribe_audio

class CustomEngine:
    def __init__(self):
        self.model_loaded = False

    def load(self):
        if not self.model_loaded:
            load_model()
            self.model_loaded = True

    def recognize(self, audio_data, sample_rate=16000):
        self.load()
        text = transcribe_audio(audio_data, sample_rate)
        return text

# Usage example
if __name__ == "__main__":
    # Simple test (replace with actual microphone capture logic)
    import numpy as np
    dummy_audio = np.zeros(16000 * 5)  # 5 seconds of silence
    engine = CustomEngine()
    print("Recognized text:", engine.recognize(dummy_audio))
