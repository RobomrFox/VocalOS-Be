import numpy as np
import queue
import threading
import sounddevice as sd
from custom_engine import CustomEngine  # your Faster Whisper wrapper

class StreamingRecognizer:
    def __init__(self, sample_rate=16000, chunk_size=1024, vad_threshold=0.01, buffer_seconds=3):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.vad_threshold = vad_threshold
        self.buffer_seconds = buffer_seconds
        self.buffer_size = int(buffer_seconds * sample_rate)
        self.audio_queue = queue.Queue()
        self.engine = CustomEngine()
        self.running = False
        self.audio_buffer = []

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio input status: {status}")
        self.audio_queue.put(indata.copy())

    def is_speech(self, audio_chunk):
        energy = np.linalg.norm(audio_chunk) / len(audio_chunk)
        return energy > self.vad_threshold

    def recognition_loop(self):
        print("Recognition loop started")
        while self.running:
            if not self.audio_queue.empty():
                chunk = self.audio_queue.get()
                audio_np = np.squeeze(chunk)
                if self.is_speech(audio_np):
                    self.audio_buffer.append(audio_np)
                    if sum(len(a) for a in self.audio_buffer) >= self.buffer_size:
                        audio_for_recog = np.concatenate(self.audio_buffer)
                        text = self.engine.recognize(audio_for_recog, self.sample_rate)
                        print(f"Recognized: {text}")
                        self.audio_buffer = []
                else:
                    # Pause detected, process buffered audio if exists
                    if self.audio_buffer:
                        audio_for_recog = np.concatenate(self.audio_buffer)
                        text = self.engine.recognize(audio_for_recog, self.sample_rate)
                        print(f"Recognized (pause): {text}")
                        self.audio_buffer = []

    def start(self):
        self.running = True
        threading.Thread(target=self.recognition_loop, daemon=True).start()
        with sd.InputStream(channels=1, samplerate=self.sample_rate, blocksize=self.chunk_size, callback=self.audio_callback):
            print("Listening...")
            while self.running:
                pass

    def stop(self):
        self.running = False

if __name__ == "__main__":
    recognizer = StreamingRecognizer()
    try:
        recognizer.start()
    except KeyboardInterrupt:
        recognizer.stop()
        print("Stopped listening.")
