from src.stt import load_model, transcribe_audio

class CustomEngine:
    def __init__(self):
        self.model_loaded = False

    def load(self):
        if not self.model_loaded:
            print("Loading model...")
            load_model()
            self.model_loaded = True
            print("Model loaded.")

    def recognize(self, audio_data, sample_rate=16000):
        if not self.model_loaded:
            self.load()
        text = transcribe_audio(audio_data, sample_rate)
        return text

# Usage example for testing
if __name__ == "__main__":
    import numpy as np
    engine = CustomEngine()
    engine.load()  # preload model
    dummy_audio = np.zeros(16000 * 3)  # 3 seconds silence
    print("Recognized text:", engine.recognize(dummy_audio))
