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
import audioop
import queue
from flask_socketio import SocketIO, emit

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# === Flask setup ===
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*")

# === Gemini setup ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_PROFILE_DIR = os.path.join(SCRIPT_DIR, "voice_profiles")

stt = AudioToTextRecorder()
vs = VoiceSignature(profile_dir=VOICE_PROFILE_DIR)
username = "default_user"
enrolled_embedding = vs.load_embedding(username)

if os.path.exists(SCRIPT_DIR):
    print("🧠 [main.py]: Loading environment variables...")
    load_dotenv()
else:
    print("⚠️ [main.py]: .env file not found.")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ Missing GEMINI_API_KEY in .env file.")
    sys.exit()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash-lite")
recognizer = sr.Recognizer()

pause_listener = threading.Event()
pause_listener.set()

# === NEW: wake_lock flag ===
wake_lock = threading.Lock()
wake_active = False  # tracks whether currently in a wake session


# === Utility ===
def calibrate_ambient_noise():
    print("🎤 Calibrating ambient noise...")
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
        print("✅ Ambient noise calibrated.")
    except Exception as e:
        print(f"⚠️ Could not calibrate ambient noise: {e}")


def adaptive_listen(recognizer, source, silence_duration=2.0, min_energy=300, max_time=30):
    print("🎧 Adaptive listening started...")
    frames = []
    start_time = time.time()
    last_spoken = time.time()
    while True:
        data = source.stream.read(1024)
        frames.append(data)
        rms = audioop.rms(data, 2)
        if rms > min_energy:
            last_spoken = time.time()
        if time.time() - last_spoken > silence_duration:
            print("🤫 Silence detected, stopping.")
            break
        if time.time() - start_time > max_time:
            print("⏱️ Max recording time reached.")
            break
    wav_data = b"".join(frames)
    return sr.AudioData(wav_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)


# === Email setup ===
PROFESSOR_DB = {"jack": "faiz4@ualberta.ca"}
email_draft_session = {"to": "", "to_name": "", "subject": "", "body_content": ""}


def wav_to_numpy(wav_bytes):
    with io.BytesIO(wav_bytes) as wav_io:
        with wave.open(wav_io) as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            sample_width = wav_file.getsampwidth()
            dtype = np.int16 if sample_width == 2 else np.int32
            audio_np = np.frombuffer(frames, dtype=dtype)
    return audio_np.astype(np.float32) / np.iinfo(dtype).max


# === Playwright Management ===
PLAYWRIGHT_SERVICE_URL = "http://127.0.0.1:5001/execute"
playwright_process = None


def start_playwright_service():
    global playwright_process
    try:
        requests.post(PLAYWRIGHT_SERVICE_URL, json={"action": "get_tab_context"}, timeout=0.5)
    except requests.exceptions.ConnectionError:
        print("🧠 Starting Playwright service...")
        try:
            service_path = os.path.join(SCRIPT_DIR, "Automations", "web_browsing", "playwright_service.py")
            playwright_process = subprocess.Popen([sys.executable, service_path])
            print(f"🧠 Playwright started (PID: {playwright_process.pid})")
            time.sleep(4)
        except Exception as e:
            print(f"❌ Could not start playwright_service.py: {e}")


def call_playwright_service(action_payload):
    start_playwright_service()
    try:
        response = requests.post(PLAYWRIGHT_SERVICE_URL, json=action_payload)
        response_data = response.json()
        if response.status_code == 200 and response_data.get("status") == "success":
            return response_data.get("reply", "OK")
        else:
            return f"Error controlling browser: {response_data.get('reply', 'Unknown error')}"
    except Exception as e:
        return f"Error in Playwright service: {e}"


def shutdown_services():
    global playwright_process
    if playwright_process:
        print(f"🧠 Shutting down Playwright (PID: {playwright_process.pid})...")
        playwright_process.terminate()
        playwright_process.wait()
        print("✅ Playwright shut down.")


atexit.register(shutdown_services)


# === System helpers ===
def open_browser(target):
    try:
        if not target.startswith("http"):
            target = "https://" + target
        print(f"🌐 Opening tab: {target}")
        result = call_playwright_service({"action": "goto", "target": target})
        return f"📂 Browser controlled by Playwright — opened {target}. {result}"
    except Exception as e:
        return f"❌ Failed to open browser: {e}"


def open_local_app(app_name):
    try:
        system = platform.system().lower()
        print(f"🖥️ Launching app: {app_name}")
        if system == "windows":
            app_paths = {
                "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "notepad": "notepad.exe",
                "vscode": r"%USERPROFILE%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                "visual studio code": r"%USERPROFILE%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                "cmd": "cmd.exe",
                "calculator": "calc.exe",
                "explorer": "explorer.exe",
                "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
            }
            exe_path = os.path.expandvars(app_paths.get(app_name.lower(), ""))
            if exe_path and os.path.exists(exe_path):
                subprocess.Popen(exe_path)
                return f"Launching {app_name.title()}."
            else:
                subprocess.Popen(f"start {app_name}", shell=True)
                return f"Trying to launch {app_name}..."
        elif system == "darwin":
            subprocess.Popen(["open", "-a", app_name])
            return f"Opening {app_name} on macOS."
        elif system == "linux":
            subprocess.Popen([app_name])
            return f"Launching {app_name} on Linux."
    except Exception as e:
        return f"❌ Failed to open {app_name}: {e}"


def close_local_app(app_name):
    try:
        system = platform.system().lower()
        app_map = {
            "chrome": "chrome",
            "google chrome": "chrome",
            "vscode": "Code",
            "visual studio code": "Code",
            "notepad": "notepad",
            "word": "WINWORD",
            "calculator": "Calculator",
            "explorer": "explorer",
        }
        process_name = app_map.get(app_name.lower(), app_name)
        if system == "windows":
            subprocess.run(["taskkill", "/F", "/IM", f"{process_name}.exe"], capture_output=True, text=True)
        elif system == "darwin":
            subprocess.run(["pkill", "-f", process_name], capture_output=True, text=True)
        elif system == "linux":
            subprocess.run(["pkill", process_name], capture_output=True, text=True)
        return f"✅ Closed {app_name.title()} successfully."
    except Exception as e:
        return f"❌ Failed to close {app_name}: {e}"


def write_to_app(app_name, content):
    try:
        target = app_name.lower()
        wins = [w for w in gw.getAllWindows() if target in w.title.lower()]
        if not wins:
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
        if platform.system().lower() == "windows":
            subprocess.run(["powershell", "-Command", f"(New-Object -ComObject WScript.Shell).AppActivate('{win.title}')"])
        else:
            win.activate()
        time.sleep(1)
        pyautogui.typewrite(content, interval=0.04)
        return f"✅ Wrote your text into {app_name}."
    except Exception as e:
        return f"Couldn’t write into {app_name}: {e}"


# === Email helpers ===
def compose_email_and_refresh():
    global email_draft_session
    try:
        import urllib.parse
        dear_line = f"Dear {email_draft_session['to_name']},"
        content = email_draft_session["body_content"]
        closing = "Best regards,\nAudient"
        final_body = f"{dear_line}\n\n{content}\n\n{closing}"
        to_encoded = urllib.parse.quote(email_draft_session["to"] or "")
        subject_encoded = urllib.parse.quote(email_draft_session["subject"] or "")
        body_encoded = urllib.parse.quote(final_body or "")
        gmail_url = (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={to_encoded}&su={subject_encoded}&body={body_encoded}"
        )
        call_playwright_service({"action": "goto", "target": gmail_url})
        return f"📨 Refreshed Gmail draft."
    except Exception as e:
        return f"❌ Failed to open Gmail compose — {e}"


def handle_email_action(data):
    global email_draft_session
    act = data.get("action")
    if act == "email_start_professor":
        name = data.get("name", "").lower()
        email = PROFESSOR_DB.get(name)
        if not email:
            return f"I don’t have a professor named {name}."
        email_draft_session = {"to": email, "to_name": name.title(), "subject": "", "body_content": ""}
        return compose_email_and_refresh()
    elif act == "email_start_generic":
        email = data.get("to")
        email_draft_session = {"to": email, "to_name": email.split('@')[0], "subject": "", "body_content": ""}
        return compose_email_and_refresh()
    elif act == "email_set_title":
        email_draft_session["subject"] = data.get("title")
        return compose_email_and_refresh()
    elif act == "email_set_content":
        email_draft_session["body_content"] = data.get("content")
        return compose_email_and_refresh()
    else:
        return "Unknown email action."


# === Gemini Action Handler ===
def ask_gemini_for_action(user_text):
    try:
        tab_context_raw = call_playwright_service({"action": "get_tab_context"})
        tab_context_str = "Tab context unavailable."
        if isinstance(tab_context_raw, dict):
            titles = tab_context_raw.get("titles", [])
            active_index = tab_context_raw.get("active_index", 0)
            tab_context_str = "Tabs: " + ", ".join(
                [f"{'(Active)' if i == active_index else ''}{t[:25]}" for i, t in enumerate(titles)]
            )
        open_windows = [w.title for w in gw.getAllWindows() if w.title]
        context = f"Currently open windows: {open_windows[:5]}\nControlled Browser Context: {tab_context_str}"
        system_prompt = get_system_prompt(context)
        response = model.generate_content(f"{system_prompt}\n\nUser: {user_text}")
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                return json.loads(match.group(0))
            return {"action": "none", "reply": text}
    except Exception as e:
        print(f"❌ Error in ask_gemini_for_action: {e}")
        return {"action": "none", "reply": f"Error: {e}"}


# === Core voice route ===
@app.route("/listen-voice", methods=["POST"])
def listen_voice():
    global wake_active, enrolled_embedding
    try:
        with wake_lock:
            wake_active = True
        print("🚦 Paused wakeword detection during active listening.")
        socketio.emit("wake_status", {"status": "🚦 Paused wakeword detection during active listening."})

        verify_voice = request.get_json().get("verify_voice", False) if request.is_json else False

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("🎤 Listening for your command...")
            socketio.emit("wake_status", {"status": "🎤 Listening for your command..."})
            # Standard, reliable speech capture
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)

        wav = audio.get_wav_data()
        user_audio_np = wav_to_numpy(wav)

        # === 🔒 Voice Signature Verification ===
        if verify_voice:
            if enrolled_embedding is None:
                print("🧠 No enrolled voice profile found — enrolling new voice.")
                enrolled_embedding = vs.get_embedding(user_audio_np)
                vs.save_embedding("default_user", enrolled_embedding)
                return jsonify({
                    "text": "Voice profile enrolled successfully.",
                    "reply": "🔐 Your voice signature has been recorded for future verification.",
                    "action": "voice_enrolled"
                })

            print("🔍 Verifying your voice signature...")
            verified = vs.verify(enrolled_embedding, user_audio_np, threshold=0.65)
            if not verified:
                print("🚫 Voice signature mismatch!")
                socketio.emit("wake_status", {"status": "🚫 Voice signature mismatch!"})
                return jsonify({
                    "error": "Voice did not match the enrolled profile.",
                    "code": "voice_mismatch"
                }), 403
            print("✅ Voice verified successfully.")
            socketio.emit("wake_status", {"status": "✅ Voice verified successfully."})

        # === 🎧 Speech Recognition ===
        print("🧠 Transcribing user speech...")
        socketio.emit("wake_status", {"status": "🧠 Transcribing user speech..."})
        user_text = recognizer.recognize_google(audio)
        print(f"🗣️ You said: {user_text}")
        socketio.emit("wake_status", {"status": f"🗣️ You said: {user_text}"})

        # === 🧩 Gemini Decision ===
        gemini_decision = ask_gemini_for_action(user_text)
        act = gemini_decision.get("action", "")
        reply = ""

        if act == "open_browser":
            reply = open_browser(gemini_decision.get("target"))
        elif act == "open_app":
            reply = open_local_app(gemini_decision.get("target"))
        elif act == "close_app":
            reply = close_local_app(gemini_decision.get("target"))
        elif act.startswith("email_"):
            reply = handle_email_action(gemini_decision)
        elif act.startswith("playwright_"):
            payload = gemini_decision.copy()
            payload["action"] = act.replace("playwright_", "")
            reply = call_playwright_service(payload)
        else:
            reply = gemini_decision.get("reply", "I'm here.")

        socketio.emit("wake_status", {"status": f"✅ {reply}"})
        return jsonify({
            "text": user_text,
            "reply": reply,
            "action": act
        })

    except sr.UnknownValueError:
        socketio.emit("wake_status", {"status": "⚠️ Couldn’t understand speech."})
        return jsonify({"error": "Couldn’t understand speech."}), 400
    except sr.WaitTimeoutError:
        socketio.emit("wake_status", {"status": "⏱️ No speech detected."})
        return jsonify({"error": "No speech detected."}), 408
    except Exception as e:
        print(traceback.format_exc())
        socketio.emit("wake_status", {"status": f"❌ Error: {e}"})
        return jsonify({"error": str(e)}), 500
    finally:
        with wake_lock:
            wake_active = False
        print("🟢 Wakeword detection re-enabled.")
        socketio.emit("wake_status", {"status": "🟢 Wakeword detection re-enabled."})

# === Wakeword Detection with Lock ===
@app.route("/wakeword", methods=["POST"])
def wakeword():
    global wake_active
    with wake_lock:
        if wake_active:
            print("⏸️ Wakeword check skipped — active listening session.")
            socketio.emit("wake_status", {"status": "Wakeword check skipped — active listening session."})
            return jsonify({"wakeword_detected": False, "reason": "wake session active"})

    try:
        with sr.Microphone() as source:
            print("🎤 Listening for possible wake phrase...")
            socketio.emit("wake_status", {"status": "🎤 Listening for possible wake phrase..."})
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=4)

        text = recognizer.recognize_google(audio).lower()
        print(f"🗣️ Heard → {text}")
        socketio.emit("wake_status", {"status": f"🗣️ Heard → {text}"})

        prompt = f"""
        You are Audient, a voice assistant.
        Determine if the user is trying to wake you up.
        If it sounds like 'hey computer', 'hello', 'hi computer', etc., return:
        {{ "wake": true, "reason": "greeting detected" }}
        Otherwise return:
        {{ "wake": false, "reason": "not a wake phrase" }}
        User said: "{text}"
        """

        result = model.generate_content(prompt)
        reply = result.text.strip()
        match = re.search(r"\{[\s\S]*\}", reply)
        data = json.loads(match.group(0)) if match else {"wake": False, "reason": "parse error"}
        print(f"🤖 Gemini decision → {data}")
        socketio.emit("wake_status", {"status": f"🤖 Gemini decision → {data}"})

        if data.get("wake", False):
            with wake_lock:
                wake_active = True
            threading.Timer(10, lambda: _unlock_wake()).start()

        return jsonify({
            "wakeword_detected": data.get("wake", False),
            "text": text,
            "reason": data.get("reason", "")
        })

    except sr.UnknownValueError:
        socketio.emit("wake_status", {"status": "⚠️ No speech detected"})
        return jsonify({"wakeword_detected": False, "error": "no speech detected"})
    except Exception as e:
        print("❌ Wakeword detection failed:", e)
        socketio.emit("wake_status", {"status": f"❌ Wakeword detection failed: {e}"})
        return jsonify({"wakeword_detected": False, "error": str(e)})


def _unlock_wake():
    global wake_active
    with wake_lock:
        wake_active = False
    print("🔓 Wakeword unlocked automatically after 10s.")


# === Run server ===
if __name__ == "__main__":
    print("🧠 [main.py]: Starting main server...")
    start_playwright_service()
    calibrate_ambient_noise()
    socketio.run(app, port=5000, debug=True, use_reloader=False)
