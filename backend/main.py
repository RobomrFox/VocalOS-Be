# main.py
# This is the ONLY file you need to run.

from flask import Flask, request, jsonify
from real_time_stt import AudioToTextRecorder
from stt import VoiceSignature
from dotenv import load_dotenv
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
import re  # ✅ Needed for regex parsing
import threading
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
import io
import soundfile as sf
import wave
import numpy as np

from stt import VoiceSignature

from real_time_stt import AudioToTextRecorder



load_dotenv()
from prompt import get_system_prompt  # <-- NEW IMPORT

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# --- Gemini API setup ---
script_dir = os.path.dirname(os.path.realpath(__file__))
dotenv_path = os.path.join(script_dir, ".env")

if os.path.exists(dotenv_path):
    print(f"🧠 [main.py]: Loading environment variables from {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print(f"🧠 [main.py]: ⚠️ WARNING: .env file not found at {dotenv_path}")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ [main.py]: CRITICAL ERROR: 'GEMINI_API_KEY' not found in .env file.")
    sys.exit()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")

recognizer = sr.Recognizer()

# --- Professor Database ---
PROFESSOR_DB = {
    "faiz": "faiz4@ualberta.ca"
    # You can add more here
}

# --- Email Draft Session ---
email_draft_session = {
    "to": "",
    "to_name": "",
    "subject": "",
    "body_content": ""
}

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
def open_browser(target):
    # ... (This function is unchanged) ...
    try:
        print(f"🌐 Opening NEW tab: {target}")
        webbrowser.open(target)
        return f"Opening {target} in a new tab."
    except Exception as e:
        return f"❌ Failed to open browser: {e}"
    

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


def open_local_app(app_name):
    # ... (This function is unchanged) ...
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
        
        elif system == "darwin":  # macOS
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
    """Focus the app window and type content reliably (Windows-safe)."""
    import pyautogui, pygetwindow as gw, subprocess, time, platform

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
    
def compose_email_and_refresh():
    # ... (This function is unchanged) ...
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
        
        gmail_url = (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={to_encoded}&su={subject_encoded}&body={body_encoded}"
        )
        
        print(f"📧 Refreshing Gmail compose for: {email_draft_session['to']}")
        
        reply = call_playwright_service({
            "action": "goto",
            "target": gmail_url
        })
        
        return f"📨 Refreshed Gmail draft. {reply}"

    except Exception as e:
        print(f"❌ Gmail compose failed: {e}")
        return f"❌ Failed to open Gmail compose — {e}"

def get_open_windows():
    system = platform.system().lower()
    if system == "windows":
        return [w.title for w in gw.getAllWindows() if w.title]
    else:
        # On macOS/Linux, cannot enumerate windows with pygetwindow
        return []
    

def numpy_to_wav_bytes(audio_np, sample_rate=16000):
    buf = io.BytesIO()
    sf.write(buf, audio_np, sample_rate, format='WAV')
    buf.seek(0)
    return buf

# === Ask Gemini for actions ===
def ask_gemini_for_action(user_text):
    """Ask Gemini to interpret the user's intent and return a safe structured action."""
    
    # Get tab context from the service
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
    
    # Build the full context string
    context = (
        f"Currently open windows: {open_windows[:5]}\n"
        f"Controlled Browser Context: {tab_context_str}"
    )

    # --- THIS IS THE CHANGE ---
    # Get the prompt from the new prompt.py file
    system_prompt = get_system_prompt(context)
    # --- END OF CHANGE ---

    print("🧠 [main.py]: Asking Gemini to interpret...")
    response = model.generate_content(f"{system_prompt}\n\nUser: {user_text}")
    text = (response.text or "").strip()
    print(f"🤖 Gemini raw output: {text}")

    # ✅ Strip Markdown fences if present
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
        print(f"⚠️ JSON parsing failed: {e}")
        # Try to extract first valid JSON-looking segment
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                # Re-run the parse and post-processing logic
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
                print(f"⚠️ Fallback parse failed: {e2}")
        # Final fallback
        return {"action": "none", "reply": text}


# --- Flask Routes (Unchanged) ---
@app.route("/listen-voice", methods=["POST"])
def listen_voice():
    try:
        verify_voice = False
        if request.is_json:
            verify_voice = request.get_json().get("verify_voice", False)
        else:
            verify_voice = request.form.get("verify_voice", "false").lower() == "true"

        global enrolled_embedding
        if verify_voice:
            if enrolled_embedding is None:
                return jsonify({"error": "No enrolled voice found. Please enroll first."}), 400
            print("🎧 Verifying voice signature...")
            verified = vs.verify(enrolled_embedding, duration=6)
            if not verified:
                return jsonify({"error": "Voice not recognized"}), 403
        else:
            print("Voice signature verification skipped (toggle off)")

        print("🧠 Recording and transcribing...")
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)

        user_text = recognizer.recognize_google(audio)
        print(f"🗣 You said: {user_text}")

        gemini_decision = ask_gemini_for_action(user_text)
        action = str(gemini_decision.get("action", "none")).lower()
        print(f"🧩 [main.py]: Parsed action: {action}")

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
            reply_text = f"I understood the action '{action}' but wasn't sure what to do."
        
        print(f"✅ [main.py]: Reply: {reply_text}")
        return jsonify({"text": user_text, "reply": reply_text})

    except Exception as e:
        print("❌ [main.py]: Full backend error:\n", traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# ==============================================================
# 💬 Text Command Route
# ==============================================================

@app.route("/listen", methods=["POST"])
def listen_text():
    # ... (This function is unchanged) ...
    global email_draft_session
    
    data = request.get_json()
    user_text = data.get("text", "").strip()

    if not user_text:
        return jsonify({"reply": "⚠️ I didn’t catch that. Could you repeat?"})

    print(f"💬 Text command: {user_text}")

    gemini_decision = ask_gemini_for_action(user_text)
    action = gemini_decision.get("action", "none")
    target = gemini_decision.get("target")
    reply = gemini_decision.get("reply", "")
    content = gemini_decision.get("content", "")
    
    # ✅ You added these lines, which is correct
    to = gemini_decision.get("to", "")
    subject = gemini_decision.get("subject", "")
    body = gemini_decision.get("body", "")

    if action == "open_browser" and target:
        reply_text = open_browser(target)
    elif action == "open_app" and target:
        reply_text = open_local_app(target)
    elif action == "write_text" and target and content:
        reply_text = write_to_app(target, content)
    # 🚨 ADD THIS BLOCK:
    elif action == "compose_email":
        reply_text = compose_email(to, subject, body)
    action = str(gemini_decision.get("action", "none")).lower()

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
        reply_text = reply or "I'm here and listening."

    return jsonify({"reply": reply_text})

# ==============================================================
# 💤 Wakeword Detection Route
# ==============================================================

@app.route("/wakeword", methods=["POST"])
def wakeword():
    try:
        with sr.Microphone() as source:
            print("🎤 Listening for possible wake phrase...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=4)

        text = recognizer.recognize_google(audio).lower()
        print(f"🗣️ Heard → {text}")

        # ✅ Use double braces {{ }} so they render literally
        prompt = """
        You are Audient, a voice assistant.
        Determine if the user is trying to wake up or greet you.
        If it sounds like 'hey computer', 'hello', 'hi computer', etc., return:
        { "wake": true, "reason": "greeting detected" }
        Otherwise return:
        { "wake": false, "reason": "not a wake phrase" }
        User said: "<text>"
        """.replace("<text>", text)


        result = model.generate_content(prompt)
        reply = result.text.strip()

        match = re.search(r"\{[\s\S]*\}", reply)
        data = json.loads(match.group(0)) if match else {"wake": False, "reason": "parse error"}

        print(f"🤖 Gemini decision → {data}")

        return jsonify({
            "wakeword_detected": data.get("wake", False),
            "text": text,
            "reason": data.get("reason", "")
        })

    except sr.UnknownValueError:
        return jsonify({"wakeword_detected": False, "error": "no speech detected"})
    except Exception as e:
        print("❌ Wakeword detection failed:", e)
        return jsonify({"wakeword_detected": False, "error": str(e)})


def wakeword_background_listener():
    """Continuously listens for wake words and triggers main listening flow."""
    while True:
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("👂 Passive listening for wake word...")
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=4)

            text = ""
            try:
                text = recognizer.recognize_google(audio).lower()
                print(f"🗣️ Passive heard: {text}")
            except sr.UnknownValueError:
                continue  # just ignore silence
            except Exception as e:
                print("⚠️ Wakeword recognition issue:", e)
                continue

            # If the user says "hey audient" or "ok audient"
            if re.search(r"\b(hey|hi|ok)\s+(audient|assistant|computer)\b", text):
                print("🎉 Wake word detected! Activating listening mode...")
                # Trigger real listening process
                try:
                    with app.test_request_context("/listen-voice", method="POST", json={"trigger": "wake"}):
                        listen_voice()
                except Exception as e:
                    print("⚠️ Wake listener trigger failed:", e)
        except Exception as e:
            print("⚠️ Wakeword listener loop error:", e)
            time.sleep(1)

# ==============================================================
# 🚀 Run Server
# ==============================================================

if __name__ == "__main__":
    print("🚀 Initializing VocalAI backend...")

    # ✅ Start the background thread FIRST before Flask starts
    wake_thread = threading.Thread(
        target=wakeword_background_listener,
        daemon=True  # stops automatically when Flask exits
    )
    wake_thread.start()
    print("🎧 Wakeword listener thread started successfully!")

    # ✅ Run Flask ONCE with reloader disabled to prevent double instances
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
    
