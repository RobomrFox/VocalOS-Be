import sounddevice as sd
import numpy as np
from src.stt import load_model, transcribe_audio
from command_listener import CommandListener

def record_audio(duration=5, sample_rate=16000):
    print(f"Recording for {duration} seconds...")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    print("Recording complete.")
    return audio.flatten()

def main():
    model = load_model()
    commands = CommandListener()

    while True:
        input("Press Enter and start speaking...")
        audio_data = record_audio()
        text = transcribe_audio(audio_data, sample_rate=16000)
        print(f"You said: {text}")
        commands.handle_command(text)

if __name__ == "__main__":
    main()
