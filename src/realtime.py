from faster_whisper import WhisperModel
import sounddevice as sd
import numpy as np
import queue
import threading
import time

# --- Settings ---
model_size = "base.en"      # Model size (e.g., "tiny.en", "base.en")
samplerate = 16000          # Whisper sample rate
channels = 1                # Mono audio

# --- VAD Settings ---
BLOCK_DURATION = 0.1        # How often to check for speech (in seconds).
SILENCE_DURATION = 2.0      # How long to wait in silence before transcribing (in seconds).
SILENCE_THRESHOLD = 0.01    # Energy threshold for silence. ** YOU MUST TUNE THIS **
FRAMES_PER_BLOCK = int(samplerate * BLOCK_DURATION)
SILENT_BLOCKS_TO_WAIT = int(SILENCE_DURATION / BLOCK_DURATION)

# --- Global State ---
audio_queue = queue.Queue() # This is the only global state we need

def audio_callback(indata, frames, time, status):
    """This is called by sounddevice for each new audio block."""
    if status:
        print(status)
    audio_queue.put(indata.copy())

def recorder():
    """Continuously records audio and puts it into the queue."""
    print("Recorder thread started.")
    with sd.InputStream(samplerate=samplerate, channels=channels,
                        callback=audio_callback, blocksize=FRAMES_PER_BLOCK):
        print("Listening... Press Ctrl+C to stop")
        while True:
            sd.sleep(100) # Keep the recorder thread alive

def transcriber():
    """
    Runs in the main thread.
    Pulls audio from the queue, performs VAD, and transcribes.
    """
    
    print("Transcriber waiting for model...")
    model = WhisperModel(model_size, device="cuda", compute_type="float16")
    print("Model loaded. Transcriber is active.")

    # --- Local state for VAD ---
    audio_buffer = []
    silence_counter = 0

    while True:
        try:
            # Get a block of audio
            block = audio_queue.get(timeout=BLOCK_DURATION)
            
            # Calculate the energy (RMS) of the block
            rms = np.sqrt(np.mean(block**2))
            # print(f"RMS: {rms:.4f}")
            
            if rms > SILENCE_THRESHOLD:
                # --- SPEECH DETECTED ---
                audio_buffer.append(block)
                silence_counter = 0 # Reset silence counter
            
            else:
                # --- SILENCE DETECTED ---
                if len(audio_buffer) > 0:
                    # We were speaking, but now we're silent
                    silence_counter += 1
                    
                    if silence_counter >= SILENT_BLOCKS_TO_WAIT:
                        # --- END OF SPEECH ---
                        print("\n[Transcribing...]", end="", flush=True)
                        
                        # Concatenate all blocks from the buffer
                        audio_data = np.concatenate(audio_buffer)
                        audio_buffer = [] # Clear the buffer
                        silence_counter = 0 # Reset the counter
                        
                        # Flatten and convert to the correct type
                        audio_data = audio_data.flatten().astype(np.float32)
                        
                        # Transcribe the audio
                        segments, _ = model.transcribe(
                            audio_data,
                            language="en",
                            beam_size=1
                        )
                        
                        # Join all segments into one string
                        text = "".join(segment.text for segment in segments).strip()
                        
                        if text:
                            # \r moves to the start of the line, \033[K clears the line
                            print(f"\r\033[KYOU SAID: {text}\n")
                        
                        print("[Listening...]", end="", flush=True)

                else:
                    # Just continuous silence, do nothing
                    pass
        
        except queue.Empty:
            # This is NOT an error. It means a block's worth of time passed
            # with NO new audio, which counts as silence.
            if len(audio_buffer) > 0:
                silence_counter += 1
                if silence_counter >= SILENT_BLOCKS_TO_WAIT:
                    # This is the same transcription logic as above.
                    # It handles the case where you stop talking and no
                    # "low RMS" blocks come in, only empty queue timeouts.
                    
                    print("\n[Transcribing (timeout)...]", end="", flush=True)
                    audio_data = np.concatenate(audio_buffer)
                    audio_buffer = []
                    silence_counter = 0
                    
                    audio_data = audio_data.flatten().astype(np.float32)
                    segments, _ = model.transcribe(audio_data, language="en", beam_size=1)
                    text = "".join(segment.text for segment in segments).strip()
                    
                    if text:
                        print(f"\r\033[KYOU SAID: {text}\n")
                    
                    print("[Listening...]", end="", flush=True)

# --- Start Threads ---
# Start the recorder in a background thread
threading.Thread(target=recorder, daemon=True).start()

# Run the transcriber in the main thread
try:
    transcriber()
except KeyboardInterrupt:
    print("\nStopping...")
except Exception as e:
    print(f"An error occurred: {e}")