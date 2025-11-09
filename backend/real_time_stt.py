import sounddevice as sd
import queue
import numpy as np

class AudioToTextRecorder:
    def __init__(self, sample_rate=16000, chunk_duration=3):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.q = queue.Queue()

    def _callback(self, indata, frames, time, status):
        if status:
            print(f"Audio input status: {status}")
        self.q.put(indata.copy())

    def record_audio_chunk(self):
        print(f"Recording audio chunk for {self.chunk_duration} seconds...")
        frames = int(self.sample_rate * self.chunk_duration)
        audio_frames = []
        with sd.InputStream(samplerate=self.sample_rate, channels=1, callback=self._callback):
            while sum(len(f) for f in audio_frames) < frames:
                audio_frames.append(self.q.get())

        audio_np = np.concatenate(audio_frames, axis=0).flatten()
        print(f"Recorded {len(audio_np)/self.sample_rate:.2f} seconds of audio")
        return audio_np

    def transcribe_chunk(self, audio_np):
        # Call your transcription model/API with np audio (replace with your actual call)
        recognized_text = "Simulated transcription text"
        print("Transcribing chunk (simulate):", recognized_text)
        return recognized_text

if __name__ == "__main__":
    recorder = AudioToTextRecorder()
    audio = recorder.record_audio_chunk()
    text = recorder.transcribe_chunk(audio)
    print("Transcribed text:", text)
