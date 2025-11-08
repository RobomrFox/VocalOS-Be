from faster_whisper import WhisperModel
import numpy as np

model = None

def load_model(model_size="base"):
    global model
    model = WhisperModel(model_size, device="cpu")

def transcribe_audio(audio_data, sample_rate=16000):
    if model is None:
        load_model()
    audio_data = audio_data.flatten()
    segments, _ = model.transcribe(audio_data)
    text = "".join([segment.text for segment in segments])
    return text.strip()

if __name__ == "__main__":
    from capture import get_microphones, test_microphone
    
    print("Available microphones:")
    mics = get_microphones()
    for mic in mics:
        default_marker = " (default)" if mic['is_default'] else ""
        print(f"  {mic['id']}: {mic['name']}{default_marker}")
    
    mic_choice = input("\nEnter mic ID (or press Enter for default): ").strip()
    device_id = int(mic_choice) if mic_choice else None
    
    print("\nLoading model...")
    load_model()
    
    print("\nSpeak now!")
    audio, sr = test_microphone(duration=15, device=device_id)
    
    print("\nTranscribing...")
    text = transcribe_audio(audio, sr)
    print(f"You said: {text}")
