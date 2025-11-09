import numpy as np
import sounddevice as sd
import os
import pickle
from resemblyzer import VoiceEncoder, preprocess_wav
from RealtimeSTT import AudioToTextRecorder

# Configuration
VOICE_PROFILE_DIR = "voice_profiles"
ENROLLMENT_DURATION = 10       # seconds for initial voice registration
CHECK_DURATION = 3             # seconds per diarization check audio chunk

encoder = VoiceEncoder()
os.makedirs(VOICE_PROFILE_DIR, exist_ok=True)

def record_audio(duration, fs=16000):
    print(f"Recording for {duration} seconds. Speak clearly...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    return np.squeeze(recording)

def get_embedding(audio):
    wav = preprocess_wav(audio)
    return encoder.embed_utterance(wav)

def register_voice_profile():
    username = input("Enter name for new voice profile: ").strip()
    if not username:
        print("Profile name cannot be empty.")
        return None, None
    audio = record_audio(ENROLLMENT_DURATION)
    embedding = get_embedding(audio)
    profile_path = os.path.join(VOICE_PROFILE_DIR, f"{username}.pkl")
    with open(profile_path, "wb") as f:
        pickle.dump(embedding, f)
    print(f"Voice profile saved at {profile_path}")
    return username, embedding

def load_single_profile():
    profiles = [f for f in os.listdir(VOICE_PROFILE_DIR) if f.endswith(".pkl")]
    if len(profiles) == 1:
        path = os.path.join(VOICE_PROFILE_DIR, profiles[0])
        with open(path, "rb") as f:
            print(f"Loaded voice profile: {profiles[0][:-4]}")
            return profiles[0][:-4], pickle.load(f)
    return None, None

def is_speaker(audio, embedding, threshold=0.65):
    test_emb = get_embedding(audio)
    similarity = np.dot(embedding, test_emb) / (np.linalg.norm(embedding) * np.linalg.norm(test_emb))
    print(f"Speaker similarity: {similarity:.3f}")
    return similarity > threshold

def process_transcription(text):
    print(f"Transcribed: {text}")

def main():
    recorder = AudioToTextRecorder()

    username, embedding = load_single_profile()
    if embedding is None:
        print("No single voice profile found.")
        if input("Register a new voice profile? (y/n): ").lower() == "y":
            username, embedding = register_voice_profile()
            if embedding is None:
                print("Registration failed. Exiting.")
                return
        else:
            print("No voice profile available. Exiting.")
            return

    # Initial verification before starting loop
    print(f"Verify voice for profile '{username}'. Please speak.")
    audio = record_audio(ENROLLMENT_DURATION)
    if not is_speaker(audio, embedding):
        print("Verification failed. Exiting.")
        return
    print("Voice verified! Starting secure transcription loop.")

    while True:
        audio_chunk = record_audio(CHECK_DURATION)
        if is_speaker(audio_chunk, embedding):
            print("Speaker verified, transcribing chunk...")
            # Pass chunk audio data to transcription method
            # This may vary depending on your transcription API. Here, assuming recorder.text reads audio
            recorder.text(process_transcription)
        else:
            print("Unknown speaker, skipping transcription.")

if __name__ == "__main__":
    main()
