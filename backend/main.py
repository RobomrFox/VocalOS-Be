# main.py
# This is the ONLY file you need to run.

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
from dotenv import load_dotenv
import io
import soundfile as sf
import wave
import numpy as np

from stt import VoiceSignature

from real_time_stt import AudioToTextRecorder



load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)


stt = AudioToTextRecorder()
vs = VoiceSignature()
username = "default_user"
enrolled_embedding = vs.load_embedding(username)

# === Gemini API setup ===
os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

recognizer = sr.Recognizer()

# --- Subprocess Management ---
PLAYWRIGHT_SERVICE_URL = "http://127.0.0.1:5001/execute"
playwright_process = None

def start_playwright_service():
    """
    Checks if the Playwright service is running. If not, starts it.
    """
    global playwright_process
    try:
        requests.post(PLAYWRIGHT_SERVICE_URL, json={"action": "get_title"}, timeout=0.5)
    except requests.exceptions.ConnectionError:
        print("🧠 [main.py]: Playwright service not found. Starting...")
        try:
            script_dir = os.path.dirname(os.path.realpath(__file__))
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
    """Ensures the service is running, then sends it a command."""
    start_playwright_service() # Smart-check
    
    try:
        response = requests.post(PLAYWRIGHT_SERVICE_URL, json=action_payload)
        
        if response.status_code == 200:
            return response.json().get("reply", "OK")
        else:
            return f"Error controlling browser: {response.json().get('reply', 'Unknown error')}"
    except requests.exceptions.ConnectionError:
        return "Failed to connect to browser service after restart."
    except Exception as e:
        return f"Error in Playwright service: {e}"

def shutdown_services():
    """Runs on exit to kill the background process."""
    global playwright_process
    if playwright_process:
        print(f"🧠 [main.py]: Shutting down background service (PID: {playwright_process.pid})...")
        playwright_process.terminate()
        playwright_process.wait()
        print("🧠 [main.py]: Background service shut down.")

atexit.register(shutdown_services)


# --- Original Helper Functions (Unchanged) ---
def open_browser(target):
    """Open URL in system default browser (NEW TAB)."""
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
    # ... (This function is unchanged) ...
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
    
def compose_email(to, subject, body):
    # ... (This function is unchanged) ...
    try:
        import urllib.parse
        to_encoded = urllib.parse.quote(to or "")
        subject_encoded = urllib.parse.quote(subject or "")
        body_encoded = urllib.parse.quote(body or "")
        gmail_url = (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={to_encoded}&su={subject_encoded}&body={body_encoded}"
        )
        print(f"📧 Redirecting to Gmail compose for: {to}")
        system = platform.system().lower()
        if system == "windows":
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path, gmail_url])
                return f"📨 Composing an email to {to or 'recipient'} via Chrome."
            elif os.path.exists(edge_path):
                subprocess.Popen([edge_path, gmail_url])
                return f"📨 ComTposing an email to {to or 'recipient'} via Edge."
            else:
                os.startfile(gmail_url)
                return f"📨 Composing an email to {to or 'recipient'} in default browser."
        else:
            webbrowser.open(gmail_url)
            return f"📨 Composing an email to {to or 'recipient'}."
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

# === Ask Gemini for actions (PROMPT IS UPGRADED) ===
def ask_gemini_for_action(user_text):
    """Ask Gemini to interpret the user's intent and return a safe structured action."""
    open_windows = get_open_windows()
    context = f"Currently open windows: {open_windows[:5]}"
    # ✅ Escape all curly braces with double braces
    system_prompt = """
You are VocalAI, a desktop AI assistant that translates user speech into JSON commands.
You can control a web browser and local applications.

Always reply **only in valid JSON** using one of the following structures:

--- Local Actions ---
- {{ "action": "open_app", "target": "<app_name>" }}
- {{ "action": "write_text", "target": "<app_name>", "content": "<text>" }}
- {{ "action": "compose_email", "to": "<recipient>", "subject": "<subject>", "body": "<body>" }}
- {{ "action": "open_browser", "target": "<url>" }} (Opens a NEW tab)

--- Controlled Browser Actions ---
- {{ "action": "playwright_goto", "target": "<url>" }} (Navigates the CURRENT tab)
- {{ "action": "playwright_fill", "selector": "<css_selector>", "content": "<text>" }}
- {{ "action": "playwright_press", "selector": "<css_selector>", "key": "<key>" }}
- {{ "action": "playwright_scroll", "direction": "<up|down>" }}
- {{ "action": "playwright_click_first_google_result" }}
- {{ "action": "playwright_click_first_youtube_video" }}

--- Fallback ---
- {{ "action": "none", "reply": "<textual reply>" }}

--- CONTEXTUAL RULES ---
You MUST use the "Active controlled browser page" context to decide the correct selector.

1. **APP VS. BROWSER (CRITICAL RULE):**
   - If the user says "open Google", "open Chrome", "open YouTube", "open Gmail", or any other website,
     you MUST use the `playwright_goto` action.
   - Example: User says "open Google Chrome" -> {{ "action": "playwright_goto", "target": "google.com" }}
   - You should ONLY use `open_app` for non-browser applications like "Notepad", "Calculator", "Word", etc.
   - Example: User says "open notepad" -> {{ "action": "open_app", "target": "notepad" }}

2. **FILLING/SEARCHING (playwright_fill):**
   - If the page title contains "Google", use selector: `[name='q']`
   - If the page title contains "YouTube", use selector: `input#search`
   - If the page title is unknown, you cannot fill.

3. **CLICKING (playwright_click_...):**
   - If the user says "click the first result" AND the page title contains "Google Search", use:
     `{{ "action": "playwright_click_first_google_result" }}`
   - If the user says "click the first video" OR "click the first result" AND the page title contains "YouTube", use:
     `{{ "action": "playwright_click_first_youtube_video" }}`

4. **SCROLLING (playwright_scroll):**
   - If the user says "scroll down", "go down", or "scroll", use:
     `{{ "action": "playwright_scroll", "direction": "down" }}`
   - If the user says "scroll up" or "go up", use:
     `{{ "action": "playwright_scroll", "direction": "up" }}`

--- EXAMPLES ---
Context:
Active controlled browser page: Google
User: "open Google Chrome"
→ {{ "action": "playwright_goto", "target": "google.com" }}

Context:
Active controlled browser page: YouTube
User: "open notepad"
→ {{ "action": "open_app", "target": "notepad" }}

Context:
Active controlled browser page: Google
User: "search for dantdm"
→ {{ "action": "playwright_fill", "selector": "[name='q']", "content": "dantdm" }}

Context:
Active controlled browser page: Google Search Results
User: "click the first link"
→ {{ "action": "playwright_click_first_google_result" }}

Context:
Active controlled browser page: YouTube - Home
User: "look up cats"
→ {{ "action": "playwright_fill", "selector": "input#search", "content": "cats" }}

Context:
{}
""".format(context)


    print("🧠 [main.py]: Asking Gemini to interpret...")
    response = model.generate_content(f"{system_prompt}\n\nUser: {user_text}")
    text = (response.text or "").strip()
    print(f"🤖 [main.py]: Gemini raw output: {text}")

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except Exception as e:
        print(f"⚠️ [main.py]: JSON parsing failed: {e}")
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception as e2:
                print(f"⚠️ [main.py]: Fallback parse failed: {e2}")
        return {"action": "none", "reply": text}
@app.route("/listen-voice", methods=["POST"])
def listen_voice():
    try:
        verify_voice = False
        if request.is_json:
            verify_voice = request.get_json().get("verify_voice", False)
        else:
            verify_voice = request.form.get("verify_voice", "false").lower() == "true"

        global enrolled_embedding

        # -------- Voice Signature Enrollment Workflow ----------
        if verify_voice:
            if enrolled_embedding is None:
                print("No enrolled voice found. Recording and enrolling now ...")
                # Record for enrollment, save, inform frontend
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=1)
                    print("Recording 8s for voice enrollment (speak normally)...")
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=8)
                try:
                    wav = audio.get_wav_data()
                    # Create embedding (implement: convert wav to np array for your vs.get_embedding)
                    audio_np = wav_to_numpy(wav)  # Define this utility!
                    enrolled_embedding = vs.get_embedding(audio_np)
                    vs.save_embedding("default_user", enrolled_embedding)
                    print("Enrollment completed.")
                    return jsonify({
                        "error": "No enrolled voice found. Enrolling now.",
                        "enroll_required": True
                    }), 200
                except Exception as e:
                    print("Enrollment failed:", e)
                    return jsonify({"error": "Voice enrollment failed.", "details": str(e)}), 500

            print("🎧 Verifying voice signature...")
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)
            wav = audio.get_wav_data()
            audio_np = wav_to_numpy(wav)  # Define or use your normal audio conversion pipeline
            verified = vs.verify(enrolled_embedding, audio_np)
            if not verified:
                return jsonify({"error": "Voice not recognized"}), 403
        else:
            print("Voice signature verification skipped (toggle off)")

        # ---------- Fast "batch" Transcription ----------
        print("Recording and transcribing...")
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)
        print("Processing your voice ...")
        try:
            user_text = recognizer.recognize_google(audio)
            print(f"You said: {user_text}")
        except sr.UnknownValueError:
            print("Could not understand audio (speech unintelligible).")
            return jsonify({
                "error": "Sorry, I couldn’t understand what you said. Please try again."
            }), 400
        except sr.RequestError as e:
            print(f"Speech recognition service error: {e}")
            return jsonify({
                "error": "Speech recognition service unavailable. Check your internet connection."
            }), 503

        # ----- Gemini/Action logic like before -----
        gemini_decision = ask_gemini_for_action(user_text)
        action = str(gemini_decision.get("action", "none")).lower()
        target = gemini_decision.get("target", "")
        reply = gemini_decision.get("reply", "")

        # Map action to reply if none
        if not reply or not reply.strip():
            if action and target:
                reply = f"Action: {action} - {target}"
            else:
                reply = "[No reply from AI]"

        print(f"Reply: {reply}")
        return jsonify({"text": user_text, "reply": reply, "action": action})

    except Exception as e:
        print("Full backend error:\n", traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# === Text-based route ===
@app.route("/listen", methods=["POST"])
def listen_text():
    """📝 Handle text messages directly"""
    data = request.get_json()
    user_text = data.get("text", "").strip()
    if not user_text:
        return jsonify({"reply": "⚠️ I didn’t catch that. Could you repeat?"})
    print(f"💬 [main.py]: Text command: {user_text}")

    gemini_decision = ask_gemini_for_action(user_text)
    action = gemini_decision.get("action", "none")

    # 1. Handle Local Actions
    if action == "open_browser":
        reply_text = open_browser(gemini_decision.get("target"))
    elif action == "open_app":
        reply_text = open_local_app(gemini_decision.get("target"))
    elif action == "write_text":
        reply_text = write_to_app(gemini_decision.get("target"), gemini_decision.get("content"))
    elif action == "compose_email":
        reply_text = compose_email(gemini_decision.get("to"), gemini_decision.get("subject"), gemini_decision.get("body"))
    
    # 2. Handle Playwright Actions
    elif action.startswith("playwright_"):
        payload = gemini_decision.copy()
        payload["action"] = action.replace("playwright_", "") # "playwright_goto" -> "goto"
        reply_text = call_playwright_service(payload)

    # 3. Handle Fallback
    elif action == "none":
        reply_text = gemini_decision.get("reply")
    else:
        reply_text = gemini_decision.get("reply") or "I'm here and listening."

    return jsonify({"reply": reply_text})

# === Run server ===
if __name__ == "__main__":
    
    print("🧠 [main.py]: Starting main server...")
    start_playwright_service()
    
    print("🧠 [main.py]: ✅ Main server running on [http://127.0.0.1:5000](http://127.0.0.1:5000)")
    app.run(port=5000, debug=True, use_reloader=False)