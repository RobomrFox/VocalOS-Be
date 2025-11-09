import numpy as np
import sounddevice as sd
import os
import pickle
from resemblyzer import VoiceEncoder, preprocess_wav

class VoiceSignature:
    def __init__(self, profile_dir="voice_profiles", sample_rate=16000):
        self.encoder = VoiceEncoder()
        self.profile_dir = profile_dir
        self.sample_rate = sample_rate
        os.makedirs(self.profile_dir, exist_ok=True)

    def record_audio(self, duration):
        print(f"Recording {duration}s of audio. Speak clearly...")
        recording = sd.rec(int(duration * self.sample_rate), samplerate=self.sample_rate, channels=1)
        sd.wait()
        return np.squeeze(recording)

    def get_embedding(self, audio_np):
        wav = preprocess_wav(audio_np)
        return self.encoder.embed_utterance(wav)

    def save_embedding(self, username, embedding):
        path = os.path.join(self.profile_dir, f"{username}.pkl")
        with open(path, "wb") as f:
            pickle.dump(embedding, f)
        print(f"Saved embedding for user '{username}' at: {path}")

    def load_embedding(self, username):
        path = os.path.join(self.profile_dir, f"{username}.pkl")
        if os.path.exists(path):
            with open(path, "rb") as f:
                embedding = pickle.load(f)
                print(f"Loaded embedding for user '{username}'.")
                return embedding
        print(f"No embedding found for user '{username}'.")
        return None

    def enroll(self, username):
        print(f"Starting enrollment for user '{username}'...")
        audio = self.record_audio(10)  # 10 seconds enrollment
        embedding = self.get_embedding(audio)
        self.save_embedding(username, embedding)
        print(f"Enrollment completed for user '{username}'.")
        return embedding

    def verify(self, embedding, duration=3, threshold=0.65):
        print(f"Verifying speaker with {duration}s audio...")
        audio = self.record_audio(duration)
        test_embedding = self.get_embedding(audio)
        similarity = np.dot(embedding, test_embedding) / (np.linalg.norm(embedding) * np.linalg.norm(test_embedding))
        print(f"Speaker similarity: {similarity:.3f}")
        return similarity > threshold


if __name__ == "__main__":
    vs = VoiceSignature()

    # Try loading a single profile or enroll new
    username = "default_user"
    embedding = vs.load_embedding(username)
    if embedding is None:
        if input(f"No profile found for '{username}', enroll new profile? (y/n): ").lower() == 'y':
            embedding = vs.enroll(username)
        else:
            print("Exiting without enrollment.")
            exit(0)

    # Verify user voice before main operation
    verified = vs.verify(embedding)
    if not verified:
        print("Voice verification failed. Exiting.")
        exit(0)
    print("Voice verified! Ready for secure operations.")

    # Main loop for continuous verification + transcription placeholder
    while True:
        print("Listening for next voice chunk to verify...")
        if vs.verify(embedding):
            print("Speaker verified for chunk! You can transcribe/process this chunk here.")
            # Placeholder: implement your transcription logic here
        else:
            print("Speaker verification failed. Ignoring audio chunk.")
