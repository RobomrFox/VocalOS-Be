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
from dotenv import load_dotenv

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

# === Helper functions ===

def open_browser(target):
    """Open URL in system default browser."""
    try:
        print(f"🌐 Opening browser: {target}")
        webbrowser.open(target)
        return f"Opening {target} in your browser."
    except Exception as e:
        return f"❌ Failed to open browser: {e}"

def open_local_app(app_name):
    """Cross-platform local app opener that handles Windows paths."""
    try:
        system = platform.system().lower()
        print(f"🖥️ Launching app: {app_name}")

        if system == "windows":
            # Common Windows app locations
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

        # 1️⃣ Ensure it's open
        wins = [w for w in gw.getAllWindows() if target in w.title.lower()]
        if not wins:
            print(f"⚠️ {app_name} not open, launching...")
            open_local_app(app_name)
            time.sleep(3)

        # 2️⃣ Wait until window appears
        for _ in range(12):
            wins = [w for w in gw.getAllWindows() if target in w.title.lower()]
            if wins:
                break
            time.sleep(0.5)

        if not wins:
            return f"❌ Could not find {app_name} window."

        win = wins[0]
        print(f"🪟 Found: {win.title}")

        # 3️⃣ Bring to foreground
        if system == "windows":
            subprocess.run(
                ["powershell", "-Command",
                 f"(New-Object -ComObject WScript.Shell).AppActivate('{win.title}')"],
                capture_output=True, text=True
            )
        else:
            win.activate()
        time.sleep(1.0)

        # 4️⃣ Confirm active window
        for _ in range(5):
            active = gw.getActiveWindow()
            if active and target in active.title.lower():
                print("✅ Window confirmed active.")
                break
            time.sleep(0.5)

        # 5️⃣ Type content
        print(f"⌨️ Typing:\n{content}")
        pyautogui.typewrite(content, interval=0.04)
        print("✅ Typing done.")
        return f"✅ Wrote your text into {app_name}."

    except Exception as e:
        print(f"❌ Failed to write: {e}")
        return f"Couldn’t write into {app_name}: {e}"
    
def compose_email(to, subject, body):
    """Force open Gmail compose window directly with pre-filled fields."""
    try:
        import urllib.parse

        # Encode user input
        to_encoded = urllib.parse.quote(to or "")
        subject_encoded = urllib.parse.quote(subject or "")
        body_encoded = urllib.parse.quote(body or "")

        # Gmail compose URL
        gmail_url = (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={to_encoded}&su={subject_encoded}&body={body_encoded}"
        )

        print(f"📧 Redirecting to Gmail compose for: {to}")

        # --- Try forcing Chrome or Edge explicitly (works better than webbrowser.open)
        system = platform.system().lower()
        if system == "windows":
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path, gmail_url])
                return f"📨 Composing an email to {to or 'recipient'} via Chrome."
            elif os.path.exists(edge_path):
                subprocess.Popen([edge_path, gmail_url])
                return f"📨 Composing an email to {to or 'recipient'} via Edge."
            else:
                # fallback to system default browser
                os.startfile(gmail_url)
                return f"📨 Composing an email to {to or 'recipient'} in default browser."

        else:
            # macOS / Linux fallback
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

# === Ask Gemini for actions ===
def ask_gemini_for_action(user_text):
    """Ask Gemini to interpret the user's intent and return a safe structured action."""
    open_windows = get_open_windows()
    context = f"Currently open windows: {open_windows[:5]}"
    # ✅ Escape all curly braces with double braces
    system_prompt = """
You are VocalAI, a desktop AI assistant that can perform user commands.
You can open websites, launch apps, write or append text in programs, or compose emails in Gmail.

Always reply **only in valid JSON** using one of the following structures:

- {{ "action": "open_browser", "target": "<url or website name>" }}
- {{ "action": "open_app", "target": "<local application name>" }}
- {{ "action": "write_text", "target": "<app name>", "content": "<the text to write>" }}
- {{ "action": "append_text", "target": "<app name>", "content": "<text to add>" }}
- {{ "action": "compose_email", "to": "<recipient email or name>", "subject": "<subject line>", "body": "<email body text>" }}
- {{ "action": "none", "reply": "<textual reply>" }}

Example:
User: "Send an email to my professor about my project progress."
→ {{ "action": "compose_email", "to": "professor", "subject": "Project Progress Update", "body": "Dear Professor, I wanted to update you on my current project progress..." }}

Be concise, structured, and strictly output JSON.
Context:
{}
""".format(context)

    print("🧠 Asking Gemini to interpret + generate meaningful content...")
    response = model.generate_content(f"{system_prompt}\n\nUser: {user_text}")
    text = (response.text or "").strip()
    print(f"🤖 Gemini raw output: {text}")

    # ✅ Strip Markdown fences if present
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    # ✅ Try parsing safely
    try:
        return json.loads(text)
    except Exception as e:
        print(f"⚠️ JSON parsing failed: {e}")
        # Try to extract first valid JSON-looking segment
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception as e2:
                print(f"⚠️ Fallback parse failed: {e2}")
        # Final fallback
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
        action = gemini_decision.get("action", "none").lower()
        target = gemini_decision.get("target", "")

        friendly_replies = {
            "open_app": f"Opening {target} now.",
            "open_browser": f"Opening browser to {target}.",
            "write_text": f"Typing your message in {target}.",
            "compose_email": "Composing email.",
            "none": gemini_decision.get("reply", ""),
        }

        reply = gemini_decision.get("reply", "")
        if not reply.strip():
            reply = friendly_replies.get(action, "[No reply from AI]")

        return jsonify({"text": user_text, "reply": reply})

    except sr.UnknownValueError:
        return jsonify({"error": "Could not understand audio."}), 400
    except sr.WaitTimeoutError:
        return jsonify({"error": "Listening timed out."}), 408
    except sr.RequestError as e:
        return jsonify({"error": f"API failed: {e}"}), 502
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error occurred."}), 500


# === Text-based route ===
@app.route("/listen", methods=["POST"])
def listen_text():
    """📝 Handle text messages directly"""
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
    else:
        reply_text = reply or "I'm here and listening."

    return jsonify({"reply": reply_text})

# === Run server ===
if __name__ == "__main__":
    app.run(debug=True)