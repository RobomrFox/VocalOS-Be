# main.py
# This is the ONLY file you need to run.
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
import speech_recognition as sr
import time
import google.generativeai as genai
import os
import subprocess
import platform
import webbrowser
import json
import pyautogui
import pygetwindow as gw
import traceback
import requests
import atexit
import sys
import re
from dotenv import load_dotenv
from prompt import get_system_prompt
from real_time_stt import AudioToTextRecorder
from stt import VoiceSignature
import numpy as np
import wave
import threading

from flask_socketio import SocketIO, emit

import pvporcupine
from pvporcupine import PorcupineError
import sounddevice as sd
import queue

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# We no longer need threading

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

socketio = SocketIO(app, cors_allowed_origins="*")

# --- Gemini API setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_PROFILE_DIR = os.path.join(SCRIPT_DIR, "voice_profiles")

script_dir = os.path.dirname(os.path.realpath(__file__))

stt = AudioToTextRecorder()
vs = VoiceSignature(profile_dir=VOICE_PROFILE_DIR)  # ✅ Pass the absolute path
username = "default_user"
enrolled_embedding = vs.load_embedding(username)

if os.path.exists(SCRIPT_DIR):
    print(f"🧠 [main.py]: Loading environment variables from ")
    load_dotenv()
else:
    print(f"🧠 [main.py]: ⚠️ WARNING: .env file not found at")

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ [main.py]: CRITICAL ERROR: 'GOOGLE_API_KEY' not found in .env file.")
    sys.exit()

PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY")
if not PICOVOICE_ACCESS_KEY:
    print("❌ [main.py]: CRITICAL ERROR: 'PICOVOICE_ACCESS_KEY' not found in .env file.")
    print("Please get a free key from https://console.picovoice.ai/")
    sys.exit()

pause_listener = threading.Event()
pause_listener.set()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash-lite")
recognizer = sr.Recognizer()

def calibrate_ambient_noise():
    """Listens for 1s to set the initial energy threshold."""
    print("🎤 Calibrating ambient noise... Please be quiet for 1 second.")
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
        print("✅ Ambient noise calibrated.")
    except Exception as e:
        print(f"⚠️ Could not calibrate ambient noise: {e}. Using defaults.")

# --- Professor Database ---
PROFESSOR_DB = {
    "jack": "faiz4@ualberta.ca"
}

# --- Email Draft Session ---
email_draft_session = {
    "to": "",
    "to_name": "",
    "subject": "",
    "body_content": ""
}

def wav_to_numpy(wav_bytes):
    with io.BytesIO(wav_bytes) as wav_io:
        with wave.open(wav_io) as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            sample_width = wav_file.getsampwidth()
            # Convert frames to numpy array based on sample width
            if sample_width == 2:
                dtype = np.int16
            elif sample_width == 4:
                dtype = np.int32
            else:
                dtype = np.uint8  # fallback
            audio_np = np.frombuffer(frames, dtype=dtype)
    return audio_np.astype(np.float32) / np.iinfo(dtype).max  # normalize to flo

# --- Subprocess Management ---
PLAYWRIGHT_SERVICE_URL = "http://127.0.0.1:5001/execute"
playwright_process = None

def start_playwright_service():
    # ... (This function is unchanged) ...
    global playwright_process
    try:
        requests.post(PLAYWRIGHT_SERVICE_URL, json={"action": "get_tab_context"}, timeout=0.5)
    except requests.exceptions.ConnectionError:
        print("🧠 [main.py]: Playwright service not found. Starting...")
        try:
            service_path = os.path.join(script_dir, "Automations", "web_browsing", "playwright_service.py")
            if not os.path.exists(service_path):
                print(f"❌ [main.py]: CRITICAL ERROR: Cannot find '{service_path}'")
                return
            playwright_process = subprocess.Popen([sys.executable, service_path])
            print(f"🧠 [main.py]: Started service with PID: {playwright_process.pid}")
            time.sleep(4) 
        except Exception as e:
            print(f"🧠 [main.py]: ❌ FAILED to start playwright_service.py: {e}")
    except requests.exceptions.Timeout:
        pass

def call_playwright_service(action_payload):
    # ... (This function is unchanged) ...
    start_playwright_service()
    try:
        response = requests.post(PLAYWRIGHT_SERVICE_URL, json=action_payload)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get("status") == "success":
            return response_data.get("reply", "OK")
        else:
            return f"Error controlling browser: {response_data.get('reply', 'Unknown error')}"
    except requests.exceptions.ConnectionError:
        return "Failed to connect to browser service after restart."
    except Exception as e:
        return f"Error in Playwright service: {e}"

def shutdown_services():
    # ... (This function is unchanged) ...
    global playwright_process
    if playwright_process:
        print(f"🧠 [main.py]: Shutting down background service (PID: {playwright_process.pid})...")
        playwright_process.terminate()
        playwright_process.wait()
        print("🧠 [main.py]: Background service shut down.")

atexit.register(shutdown_services)

# --- Helper Functions ---
# ... (open_browser, open_local_app, write_to_app are unchanged) ...
def open_browser(target):
    """
    Open a URL in the controlled Playwright browser instance.
    If no Playwright session exists, it will auto-start.
    """
    try:
        if not target.startswith("http"):
            target = "https://" + target
        print(f"🌐 [Playwright] Opening tab: {target}")
        result = call_playwright_service({
            "action": "goto",     # instruct Playwright to open in existing browser
            "target": target
        })
        return f"📂 Browser controlled by Playwright — opened {target}. {result}"
    except Exception as e:
        print(f"❌ [main.py]: Failed to open browser tab via Playwright: {e}")
        return f"❌ Failed to open tab in controlled browser: {e}"

def open_local_app(app_name):
    try:
        system = platform.system().lower()
        print(f"🖥️ Launching app: {app_name}")
        if system == "windows":
            app_paths = {
                "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "notepad": "notepad.exe",
                "vscode": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                "visual studio code": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                "cmd": "cmd.exe",
                "calculator": "calc.exe",
                "explorer": "explorer.exe",
                "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
            }
            exe_path = app_paths.get(app_name.lower())
            if exe_path:
                exe_path = os.path.expandvars(exe_path)
                subprocess.Popen(exe_path)
                return f"Launching {app_name.title()}."
            else:
                subprocess.Popen(f'start {app_name}', shell=True)
                return f"Trying to launch {app_name}..."
        elif system == "darwin":
            subprocess.Popen(["open", "-a", app_name])
            return f"Opening {app_name} on macOS."
        elif system == "linux":
            subprocess.Popen([app_name])
            return f"Launching {app_name} on Linux."
        else:
            raise Exception("Unsupported OS")
    except Exception as e:
        print(f"❌ Failed to open {app_name}: {e}")
        return f"Sorry, I couldn’t open {app_name}."


def write_to_app(app_name, content):
    try:
        system = platform.system().lower()
        target = app_name.lower()
        print(f"✍️ Preparing to write into {target}...")
        wins = [w for w in gw.getAllWindows() if target in w.title.lower()]
        if not wins:
            print(f"⚠️ {app_name} not open, launching...")
            open_local_app(app_name)
            time.sleep(3)
        for _ in range(12):
            wins = [w for w in gw.getAllWindows() if target in w.title.lower()]
            if wins:
                break
            time.sleep(0.5)
        if not wins:
            return f"❌ Could not find {app_name} window."
        win = wins[0]
        print(f"🪟 Found: {win.title}")
        if system == "windows":
            subprocess.run(
                ["powershell", "-Command",
                 f"(New-Object -ComObject WScript.Shell).AppActivate('{win.title}')"],
                capture_output=True, text=True
            )
        else:
            win.activate()
        time.sleep(1.0)
        for _ in range(5):
            active = gw.getActiveWindow()
            if active and target in active.title.lower():
                print("✅ Window confirmed active.")
                break
            time.sleep(0.5)
        print(f"⌨️ Typing:\n{content}")
        pyautogui.typewrite(content, interval=0.04)
        print("✅ Typing done.")
        return f"✅ Wrote your text into {app_name}."
    except Exception as e:
        print(f"❌ Failed to write: {e}")
        return f"Couldn’t write into {app_name}: {e}"
    
#
# --- THIS FUNCTION IS UNCHANGED ---
#
def compose_email_and_refresh():
    global email_draft_session
    try:
        import urllib.parse
        
        dear_line = f"Dear {email_draft_session['to_name']},"
        content = email_draft_session['body_content']
        closing = "Best regards,\nMorro"
        final_body = f"{dear_line}\n\n{content}\n\n{closing}"

        to_encoded = urllib.parse.quote(email_draft_session['to'] or "")
        subject_encoded = urllib.parse.quote(email_draft_session['subject'] or "")
        body_encoded = urllib.parse.quote(final_body or "")
        
        # --- THIS IS THE FIX ---
        gmail_url = (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={to_encoded}&su={subject_encoded}&body={body_encoded}"
        )
        # --- END OF FIX ---
        
        print(f"📧 Refreshing Gmail compose for: {email_draft_session['to']}")
        
        reply = call_playwright_service({
            "action": "goto",
            "target": gmail_url
        })
        
        return f"📨 Refreshed Gmail draft. {reply}"

    except Exception as e:
        print(f"❌ Gmail compose failed: {e}")
        return f"❌ Failed to open Gmail compose — {e}"


def ask_gemini_for_action(user_text):
    # ... (This function is unchanged) ...
    tab_context_raw = call_playwright_service({"action": "get_tab_context"})
    tab_context_str = "Tab context unavailable."
    
    if isinstance(tab_context_raw, dict):
        titles = tab_context_raw.get("titles", [])
        active_index = tab_context_raw.get("active_index", 0)
        
        tab_list = []
        for i, title in enumerate(titles):
            title_short = (title[:30] + '..') if len(title) > 30 else title
            if i == active_index:
                tab_list.append(f"*(Tab {i+1}: {title_short})*")
            else:
                tab_list.append(f"(Tab {i+1}: {title_short})")
        tab_context_str = "Tabs: " + ", ".join(tab_list)
    
    open_windows = [w.title for w in gw.getAllWindows() if w.title]
    
    context = (
        f"Currently open windows: {open_windows[:5]}\n"
        f"Controlled Browser Context: {tab_context_str}"
    )

    system_prompt = get_system_prompt(context)

    print("🧠 [main.py]: Asking Gemini to interpret...")
    response = model.generate_content(f"{system_prompt}\n\nUser: {user_text}")
    text = (response.text or "").strip()
    print(f"🤖 [main.py]: Gemini raw output: {text}")

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        def parse_text_to_int(text_num):
            num_map = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
            }
            return num_map.get(str(text_num).lower(), None)

        json_data = json.loads(text)
        
        if json_data.get("action") == "playwright_switch_to_tab":
            index_str = str(json_data.get("index", ""))
            index_num = parse_text_to_int(index_str)
            if index_num:
                json_data["index"] = index_num
            else:
                return {"action": "none", "reply": f"I didn't understand which tab number '{index_str}' is."}
        
        return json_data
        
    except Exception as e:
        print(f"⚠️ [main.py]: JSON parsing failed: {e}")
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                json_data = json.loads(match.group(0))
                if json_data.get("action") == "playwright_switch_to_tab":
                    index_str = str(json_data.get("index", ""))
                    index_num = parse_text_to_int(index_str)
                    if index_num:
                        json_data["index"] = index_num
                    else:
                        return {"action": "none", "reply": f"I didn't understand which tab number '{index_str}' is."}
                return json_data
            except Exception as e2:
                print(f"⚠️ [main.py]: Fallback parse failed: {e2}")
        return {"action": "none", "reply": text}

#
# --- THIS IS THE NEW, FASTER /listen-voice FUNCTION ---
## Make sure you have this import if it's not already present at the top of your file

# (And assuming numpy as np, speech_recognition as sr, etc. are already imported)
# (And assuming ask_gemini_for_action and other helper functions are defined)

#
# --- THIS IS THE NEW, CORRECTED /listen-voice FUNCTION ---
#
@app.route("/listen-voice", methods=["POST"])
def listen_voice():
    """
    This route does Speech-to-Text with OPTIONAL voice verification.
    1. Optionally verifies speaker identity
    2. Converts speech to text
    3. Passes text to Gemini to get an action/reply
    4. EXECUTES the action
    5. Returns the final text, reply, and action
    """
    # --- ADD THIS BLOCK ---
    pause_listener.clear() # Tell the listener thread to pause
    print("🚦 [main.py]: Paused wake word listener.")
    # Give the thread a moment to release the mic
    # You might not need this, but it's safer
    time.sleep(0.1) 
    # --- END BLOCK ---

    global email_draft_session  # <-- ✅ ADDED THIS
    try:
        # Check if voice verification is requested
        verify_voice = False
        if request.is_json:
            verify_voice = request.get_json().get("verify_voice", False)
        else:
            verify_voice = request.form.get("verify_voice", "false").lower() == "true"

        global enrolled_embedding

        # --- (Voice Enrollment & Verification logic is unchanged) ---
        if verify_voice:
            if enrolled_embedding is None:
                recognizer.adjust_for_ambient_noise(source, duration=.75)
                print("No enrolled voice found. Recording and enrolling now...")
                with sr.Microphone() as source:
                    print("Recording 10s for voice enrollment - SPEAK CONTINUOUSLY...")
                    audio = recognizer.listen(source, timeout=15, phrase_time_limit=10)
                
                try:
                    wav = audio.get_wav_data()
                    audio_np = wav_to_numpy(wav)
                    enrolled_embedding = vs.get_embedding(audio_np)
                    
                    if len(enrolled_embedding) == 0 or np.all(enrolled_embedding == 0):
                        print("❌ ERROR: Invalid embedding created!")
                        return jsonify({
                            "error": "Enrollment failed - please speak clearly",
                            "code": "enrollment_invalid"
                        }), 500
                    
                    vs.save_embedding("default_user", enrolled_embedding)
                    print(f"✅ Enrollment completed! Embedding norm: {np.linalg.norm(enrolled_embedding):.3f}")
                except Exception as e:
                    print("Enrollment failed:", e)
                    return jsonify({
                        "error": "Voice enrollment failed.",
                        "details": str(e),
                        "code": "enrollment_error"
                    }), 500

            # Record and verify
            print("🎧 Recording for verification and transcription...")
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=.5)
                recognizer.pause_threshold = 0.7
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)

            # Verify the audio
            wav = audio.get_wav_data()
            audio_np = wav_to_numpy(wav)
            verified = vs.verify(enrolled_embedding, audio_np, threshold=0.80)
            
            if not verified:
                return jsonify({
                    "error": "Voice not recognized",
                    "code": "voice_rejected"
                }), 403
            print("✅ Voice verified!")
        
        else:
            # Standard recording without verification
            print("Listening... please speak clearly.")
            with sr.Microphone() as source:
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)

        # --- (Transcription logic is unchanged) ---
        print("[main.py] Processing your voice...")
        try:
            user_text = recognizer.recognize_google(audio)
            print(f"You said: {user_text}")

            # ----- START: ✅ FULL Gemini Action & Execution Logic -----
            
            # 1. Ask AI
            gemini_decision = ask_gemini_for_action(user_text)
            action = str(gemini_decision.get("action", "none")).lower()
            print(f"🧩 [main.py]: Parsed action: {action}")

            # 2. Perform Action
            if action == "open_browser":
                browser_result = open_browser(gemini_decision.get("target"))
                reply_text = browser_result["reply"]
                action = browser_result[action]
            elif action == "open_app":
                reply_text = open_local_app(gemini_decision.get("target"))
            elif action == "write_text":
                reply_text = write_to_app(gemini_decision.get("target"), gemini_decision.get("content"))
            
            elif action == "email_start_professor":
                name = gemini_decision.get("name").lower()
                email = PROFESSOR_DB.get(name)
                if email:
                    email_draft_session = {"to": email, "to_name": name.title(), "subject": "", "body_content": ""}
                    reply_text = compose_email_and_refresh()
                else:
                    reply_text = f"I don't have a professor named '{name}' in my database."
            
            elif action == "email_start_generic":
                email = gemini_decision.get("to")
                email_draft_session = {"to": email, "to_name": email.split('@')[0], "subject": "", "body_content": ""}
                reply_text = compose_email_and_refresh()

            elif action == "email_set_title":
                email_draft_session["subject"] = gemini_decision.get("title")
                reply_text = compose_email_and_refresh()
            
            elif action == "email_set_content":
                email_draft_session["body_content"] = gemini_decision.get("content")
                reply_text = compose_email_and_refresh()

            elif action == "email_clear_title":
                email_draft_session["subject"] = ""
                reply_text = compose_email_and_refresh()
            
            elif action == "email_clear_content":
                email_draft_session["body_content"] = ""
                reply_text = compose_email_and_refresh()
            
            elif action.startswith("playwright_"):
                payload = gemini_decision.copy()
                payload["action"] = action.replace("playwright_", "")
                reply_text = call_playwright_service(payload)

            elif action == "none":
                reply_text = gemini_decision.get("reply")
            else:
                reply_text = gemini_decision.get("reply") or "I'm here and listening."

            # 3. Return Final Reply
            print(f"✅ [main.py]: Reply: {reply_text}")
            return jsonify({"text": user_text, "reply": reply_text, "action": action})
            # ----- END: ✅ FULL Gemini Action & Execution Logic -----

        except sr.UnknownValueError:
            msg = "I couldn't understand what you said. Please try again."
            return jsonify({"error": msg, "code": "stt_unknown", "can_retry": True}), 400
        except sr.WaitTimeoutError:
            msg = "I didn't hear anything. Try speaking again."
            return jsonify({"error": msg, "code": "stt_timeout", "can_retry": True}), 408
        except sr.RequestError as e:
            msg = f"Speech recognition service failed: {e}"
            return jsonify({"error": msg, "code": "stt_api_error", "can_retry": False}), 502

    except Exception as e:
        print("[main.py] Full backend error:\n", traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    
    finally:
        # --- ADD THIS BLOCK ---
        # ALWAYS resume the wake word listener when this function is done
        pause_listener.set() 
        print("🟢 [main.py]: Resumed wake word listener.")
        # --- END BLOCK ---
#
# --- /listen (text) route is UNCHANGED and now handles all actions ---
#
@app.route("/listen", methods=["POST"])
def listen_text():
    """
    Receives text, interprets it, and performs an action.
    """
    global email_draft_session
    
    data = request.get_json()
    user_text = data.get("text", "").strip()
    if not user_text:
        return jsonify({"reply": "⚠️ I didn’t catch that. Could you repeat?"})
    print(f"💬 [main.py]: Text command: {user_text}")

    # 1. Ask AI
    gemini_decision = ask_gemini_for_action(user_text)
    action = str(gemini_decision.get("action", "none")).lower()
    print(f"🧩 [main.py]: Parsed action: {action}")

    # 2. Perform Action
    if action == "open_browser":
        reply_text = open_browser(gemini_decision.get("target"))
    elif action == "open_app":
        reply_text = open_local_app(gemini_decision.get("target"))
    elif action == "write_text":
        reply_text = write_to_app(gemini_decision.get("target"), gemini_decision.get("content"))
    
    elif action == "email_start_professor":
        name = gemini_decision.get("name").lower()
        email = PROFESSOR_DB.get(name)
        if email:
            email_draft_session = {"to": email, "to_name": name.title(), "subject": "", "body_content": ""}
            reply_text = compose_email_and_refresh()
        else:
            reply_text = f"I don't have a professor named '{name}' in my database."
    
    elif action == "email_start_generic":
        email = gemini_decision.get("to")
        email_draft_session = {"to": email, "to_name": email.split('@')[0], "subject": "", "body_content": ""}
        reply_text = compose_email_and_refresh()

    elif action == "email_set_title":
        email_draft_session["subject"] = gemini_decision.get("title")
        reply_text = compose_email_and_refresh()
    
    elif action == "email_set_content":
        email_draft_session["body_content"] = gemini_decision.get("content")
        reply_text = compose_email_and_refresh()

    elif action == "email_clear_title":
        email_draft_session["subject"] = ""
        reply_text = compose_email_and_refresh()
    
    elif action == "email_clear_content":
        email_draft_session["body_content"] = ""
        reply_text = compose_email_and_refresh()
    
    elif action.startswith("playwright_"):
        payload = gemini_decision.copy()
        payload["action"] = action.replace("playwright_", "")
        reply_text = call_playwright_service(payload)

    elif action == "none":
        reply_text = gemini_decision.get("reply")
    else:
        reply_text = gemini_decision.get("reply") or "I'm here and listening."

    # 3. Return Final Reply
    print(f"✅ [main.py]: Reply: {reply_text}")
    return jsonify({"reply": reply_text})

# ==============================================================
# 💤 Wakeword Detection + Passive Listener
# ==============================================================

# @app.route("/wakeword", methods=["POST"])
# def wakeword():
#     try:
#         with sr.Microphone() as source:
#             print("🎤 Listening for possible wake phrase...")
#             audio = recognizer.listen(source, timeout=3, phrase_time_limit=4)

#         text = recognizer.recognize_google(audio).lower()
#         print(f"🗣️ Heard → {text}")

#         prompt = f"""
#         You are Audient, a voice assistant.
#         Determine if the user is trying to wake you up.
#         If it sounds like 'hey computer', 'hello', 'hi computer', etc., return:
#         {{ "wake": true, "reason": "greeting detected" }}
#         Otherwise return:
#         {{ "wake": false, "reason": "not a wake phrase" }}
#         User said: "{text}"
#         """
#         result = model.generate_content(prompt)
#         reply = result.text.strip()
#         match = re.search(r"\{[\s\S]*\}", reply)
#         data = json.loads(match.group(0)) if match else {"wake": False, "reason": "parse error"}

#         print(f"🤖 Gemini decision → {data}")
#         return jsonify({
#             "wakeword_detected": data.get("wake", False),
#             "text": text,
#             "reason": data.get("reason", "")
#         })
#     except sr.UnknownValueError:
#         return jsonify({"wakeword_detected": False, "error": "no speech detected"})
#     except Exception as e:
#         print("❌ Wakeword detection failed:", e)
#         return jsonify({"wakeword_detected": False, "error": str(e)})

# def wakeword_background_listener():
#     print("🎧 [WakeListener]: Starting passive wake listener (Siri-style)...")
#     recognizer = sr.Recognizer()
#     sample_rate = 16000
#     block_duration = 2  # seconds
#     q = queue.Queue()

#     # Callback collects audio chunks
#     def callback(indata, frames, time_info, status):
#         if status:
#             print(f"🎙️ Audio input status: {status}")
#         q.put(indata.copy())

#     # Continuous input stream
#     with sd.InputStream(samplerate=sample_rate, channels=1, callback=callback):
#         buffer = np.zeros(int(sample_rate * block_duration))
#         last_detection_time = 0

#         while True:
#             try:
#                 data = q.get()
#                 buffer = np.concatenate((buffer[len(data):], data.flatten()))
#                 audio = sr.AudioData(buffer.tobytes(), sample_rate, 2)

#                 # Attempt recognition only every few seconds
#                 if time.time() - last_detection_time > 2:
#                     try:
#                         text = recognizer.recognize_google(audio).lower().strip()
#                         if text:
#                             print(f"🗣️ Heard → {text}")
#                             if re.search(r"\b(hey|hi|ok)\s+(audient|assistant|computer)\b", text):
#                                 print("🎉 Wake word detected! Activating...")
#                                 threading.Thread(target=activate_listening_session, daemon=True).start()
#                                 last_detection_time = time.time()
#                     except sr.UnknownValueError:
#                         pass
#                     except Exception as e:
#                         print(f"⚠️ Wakeword recognition issue: {e}")

#             except KeyboardInterrupt:
#                 print("🧠 [WakeListener]: Stopping passive listener.")
#                 break
#             except Exception as e:
#                 print(f"⚠️ Loop error: {e}")
#                 time.sleep(1)
                
def wakeword_background_listener():
    """
    Runs Porcupine v3.0.5 in a background thread.
    This uses the access_key and the correct keyword logic.
    """
    porcupine = None
    try:
        # 1. Define the paths to the built-in keyword files
        keyword_paths = [
            pvporcupine.KEYWORD_PATHS['computer'],
            pvporcupine.KEYWORD_PATHS['ok google'],
            pvporcupine.KEYWORD_PATHS['hey siri']
        ]

        # ✅ 1. Store the names yourself. This fixes the 'keyword_names' bug.
        keywords = ['computer', 'ok google', 'hey siri']

        # 2. Initialize using the create() factory method
        porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keyword_paths=keyword_paths,
            sensitivities=[0.5] * len(keyword_paths) # Add sensitivities
        )
        
        # ✅ 2. Use your local 'keywords' list here
        print(f"🎧 [WakeListener]: Porcupine (v3.0.5) loaded with keywords: {keywords}")

        # Open an audio stream from the microphone
        with sd.InputStream(
            samplerate=porcupine.sample_rate,
            channels=1,
            dtype='int16',
            blocksize=porcupine.frame_length
        ) as stream:
            
            while True:
                pause_listener.wait() 
                
                pcm, overflowed = stream.read(porcupine.frame_length)
                if overflowed:
                    print("⚠️ [WakeListener]: Audio buffer overflow", file=sys.stderr)
                    
                pcm = pcm.flatten()
                
                keyword_index = porcupine.process(pcm)
                
                if keyword_index >= 0:
                    # ✅ 3. Use your local 'keywords' list here
                    keyword = keywords[keyword_index] 
                    print(f"🎉 Wake word detected: '{keyword}'")
                    
                    socketio.emit('wakeword_detected', {'text': keyword})
                    
                    time.sleep(2) 

    except PorcupineError as e:  # <-- This will now work
        print(f"❌ [WakeListener]: Porcupine error: {e}")
        print("Please ensure your PICOVOICE_ACCESS_KEY is correct.")
    except Exception as e:
        print(f"❌ [WakeListener]: Unexpected error: {e}", file=sys.stderr)
        traceback.print_exc()
    finally:
        if porcupine:
            porcupine.delete()
            print("🛑 [WakeListener]: Porcupine resources released.")

# def activate_listening_session():
#     """Start the main voice listening process without blocking the wake listener."""
#     print("🎤 [Audient]: Wakeword detected → switching to active listening mode!")

#     # Optional: play an activation chime
#     try:
#         import simpleaudio as sa
#         wave_obj = sa.WaveObject.from_wave_file("assets/ding.wav")
#         wave_obj.play()
#     except Exception:
#         pass

#     try:
#         with app.test_request_context("/listen-voice", method="POST", json={"trigger": "wake"}):
#             listen_voice()
#     except Exception as e:
#         print(f"⚠️ [Audient]: Active listening failed: {e}")


# ==============================================================
# 🚀 Run Server
# ==============================================================

if __name__ == "__main__":
    print("🧠 [main.py]: Starting main server...")
    start_playwright_service()

    calibrate_ambient_noise()

    # wake_thread = threading.Thread(target=wakeword_background_listener, daemon=True)
    # wake_thread.start()
    # print("🎧 Passive wakeword listener thread started successfully!")

    # app.run(port=5000, debug=True, use_reloader=False)

    wake_thread = threading.Thread(target=wakeword_background_listener, daemon=True)
    wake_thread.start()
    print("🎧 Passive wakeword listener thread started successfully!")

    # ✅ 5. USE SOCKETIO.RUN (requires eventlet)
    socketio.run(app, port=5000, debug=True, use_reloader=False)


# # === Run server ===
# if __name__ == "__main__":
    
#     print("🧠 [main.py]: Starting main server...")
#     start_playwright_service()
    
#     print("🧠 [main.py]: ✅ Main server running on ([http://127.0.0.1:5000](http://127.0.0.1:5000))")
    
#     # Back to the original, simple config. No threading.
#     app.run(port=5000, debug=True, use_reloader=False)