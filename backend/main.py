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
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')






# === Flask App Setup ===
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# === Voice Setup (placeholders) ===
stt = AudioToTextRecorder()
vs = VoiceSignature()
username = "default_user"
enrolled_embedding = vs.load_embedding(username)

# ✅ Load .env file
load_dotenv()

# ✅ Retrieve the key from environment
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise EnvironmentError("❌ Missing GOOGLE_API_KEY in .env file!")

# ✅ Configure Gemini safely
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")

print("Gemini connected successfully!")

recognizer = sr.Recognizer()


# ==============================================================
# 🧰 Helper Functions
# ==============================================================

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
    """Focus the app window and type content reliably (Windows-safe)."""
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

        active = gw.getActiveWindow()
        if active and target in active.title.lower():
            print("✅ Window confirmed active.")

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
                return f"📨 Composing an email to {to or 'recipient'} via Edge."
            else:
                os.startfile(gmail_url)
                return f"📨 Composing an email to {to or 'recipient'} in default browser."
        else:
            webbrowser.open(gmail_url)
            return f"📨 Composing an email to {to or 'recipient'}."
    except Exception as e:
        print(f"❌ Gmail compose failed: {e}")
        return f"❌ Failed to open Gmail compose — {e}"


# ==============================================================
# 🤖 Gemini Logic
# ==============================================================

def ask_gemini_for_action(user_text):
    """Ask Gemini to interpret the user's intent and return a safe structured action."""
    open_windows = [w.title for w in gw.getAllWindows() if w.title]
    context = f"Currently open windows: {open_windows[:5]}"

    system_prompt = """
You are VocalAI, a desktop AI assistant that can perform user commands.
You can open websites, launch apps, write or append text in programs, or compose emails in Gmail.

Always reply **only in valid JSON** using one of the following structures:

- { "action": "open_browser", "target": "<url or website name>" }
- { "action": "open_app", "target": "<local application name>" }
- { "action": "write_text", "target": "<app name>", "content": "<text to write>" }
- { "action": "append_text", "target": "<app name>", "content": "<text to add>" }
- { "action": "compose_email", "to": "<recipient>", "subject": "<subject>", "body": "<email body>" }
- { "action": "none", "reply": "<normal chat response>" }
"""

    print("🧠 Asking Gemini to interpret + generate meaningful content...")

    try:
        response = model.generate_content(f"{system_prompt}\n\nUser: {user_text}")
        text = (response.text or "").strip()
        print(f"🤖 Gemini raw output: {text}")

        # Remove Markdown-style fences
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()

        # Try direct JSON parse
        try:
            parsed = json.loads(text)
            return parsed
        except Exception as e:
            print(f"⚠️ JSON parsing failed: {e}")
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    return parsed
                except Exception as e2:
                    print(f"⚠️ Fallback parse failed: {e2}")

        return {"action": "none", "reply": text}

    except Exception as e:
        print("❌ Gemini interpretation failed:", e)
        return {"action": "none", "reply": f"Sorry, something went wrong: {e}"}


# ==============================================================
# 🎙️ Voice Route
# ==============================================================

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

        print("🧠 Processing your voice...")

        try:
            user_text = recognizer.recognize_google(audio)
            print(f"🗣️ You said: {user_text}")
        except sr.UnknownValueError:
            print("❌ Could not understand audio (speech unintelligible).")
            return jsonify({
                "error": "Sorry, I couldn’t understand what you said. Please try again."
            }), 400
        except sr.RequestError as e:
            print(f"❌ Speech recognition service error: {e}")
            return jsonify({
                "error": "Speech recognition service unavailable. Check your internet connection."
            }), 503


        gemini_decision = ask_gemini_for_action(user_text)
        action = str(gemini_decision.get("action", "none")).lower()
        target = gemini_decision.get("target", "")
        reply = gemini_decision.get("reply", "")
        content = gemini_decision.get("content", "")
        to = gemini_decision.get("to", "")
        subject = gemini_decision.get("subject", "")
        body = gemini_decision.get("body", "")

        if action == "open_browser" and target:
            reply_text = open_browser(target)
        elif action == "open_app" and target:
            reply_text = open_local_app(target)
        elif action == "write_text" and target and content:
            reply_text = write_to_app(target, content)
        elif action == "compose_email":
            reply_text = compose_email(to, subject, body)
        elif action == "none" and reply:
            reply_text = reply
        else:
            reply_text = "I'm not sure what to do yet."

        print(f"✅ Reply: {reply_text}")
        return jsonify({"text": user_text, "reply": reply_text, "action": action})
    

    except Exception as e:
        print("❌ Full backend error:\n", traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# ==============================================================
# 💬 Text Command Route
# ==============================================================

@app.route("/listen", methods=["POST"])
def listen_text():
    try:
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
        to = gemini_decision.get("to", "")
        subject = gemini_decision.get("subject", "")
        body = gemini_decision.get("body", "")

        if action == "open_browser" and target:
            reply_text = open_browser(target)
        elif action == "open_app" and target:
            reply_text = open_local_app(target)
        elif action == "write_text" and target and content:
            reply_text = write_to_app(target, content)
        elif action == "compose_email":
            reply_text = compose_email(to, subject, body)
        elif action == "none" and reply:
            reply_text = reply
        else:
            reply_text = "I'm not sure what to do yet."

        print(f"✅ Reply: {reply_text}")
        return jsonify({"text": user_text, "reply": reply_text})

    except Exception as e:
        print("❌ Full backend error:\n", traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


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

        prompt = f"""
        You are Audient, a voice assistant.
        Determine if the user is trying to wake you up or greet you.
        If it sounds like 'hey audient', 'hello', 'hi audient', etc., return:
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



# ==============================================================
# 🚀 Run Server
# ==============================================================

if __name__ == "__main__":
    app.run(debug=True)
