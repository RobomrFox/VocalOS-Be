import torch
import numpy as np
import sounddevice as sd

model = None
utils = None

def load_vad_model():
    global model, utils
    print("Loading Silero VAD model...")
    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
    print("VAD model loaded!")

def record_with_vad(sample_rate=16000, device=None, silence_duration=None, min_duration=1.0):
    from config import load_config
    
    if silence_duration is None:
        config = load_config()
        silence_duration = config.get('command_pause', 0.7)
        
    if model is None:
        load_vad_model()
    
    get_speech_timestamps, _, read_audio, _, _ = utils
    
    print("Listening... (speak to start recording)")
    
    chunks = []
    silence_chunks = 0
    max_silence_chunks = int(silence_duration * sample_rate / 512)
    min_chunks = int(min_duration * sample_rate / 512)
    recording = False
    
    def audio_callback(indata, frames, time, status):
        nonlocal silence_chunks, recording
        
        audio_chunk = indata.copy().flatten()
        audio_tensor = torch.from_numpy(audio_chunk)
        
        speech_prob = model(audio_tensor, sample_rate).item()
        
        if speech_prob > 0.5:
            if not recording:
                print("Recording...")
                recording = True
            chunks.append(audio_chunk)
            silence_chunks = 0
        elif recording:
            chunks.append(audio_chunk)
            silence_chunks += 1
    
    with sd.InputStream(callback=audio_callback, channels=1, samplerate=sample_rate, blocksize=512, device=device):
        while True:
            sd.sleep(100)
            
            if recording and silence_chunks > max_silence_chunks and len(chunks) > min_chunks:
                print("Silence detected. Stopping...")
                break
    
    if len(chunks) == 0:
        return None, sample_rate
    
    audio_data = np.concatenate(chunks)
    return audio_data, sample_rate

if __name__ == "__main__":
    from capture import get_microphones
    from stt import transcribe_audio, load_model as load_stt_model
    
    print("Available microphones:")
    mics = get_microphones()
    for mic in mics:
        default_marker = " (default)" if mic['is_default'] else ""
        print(f"  {mic['id']}: {mic['name']}{default_marker}")
    
    mic_choice = input("\nEnter mic ID (or press Enter for default): ").strip()
    device = int(mic_choice) if mic_choice else None
    
    load_vad_model()
    load_stt_model()
    
    audio, sr = record_with_vad(device=device)
    
    if audio is not None:
        print("\nTranscribing...")
        text = transcribe_audio(audio, sr)
        print(f"You said: {text}")
    else:
        print("No speech detected.")
