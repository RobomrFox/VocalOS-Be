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

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

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


# === Ask Gemini for actions ===
def ask_gemini_for_action(user_text):
    """Ask Gemini to interpret the user's intent and return a safe structured action."""
    open_windows = [w.title for w in gw.getAllWindows() if w.title]
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
    """🎙️ Voice input → Gemini reasoning → perform action safely."""
    try:
        with sr.Microphone() as source:
            print("🎧 Listening... please speak clearly.")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)

        print("🧠 Processing your voice...")

        try:
            # 👉 This is the line that was crashing before
            user_text = recognizer.recognize_google(audio)
            print(f"🗣️ You said: {user_text}")
        except sr.UnknownValueError:
            # Could not understand the audio
            msg = "I couldn't understand what you said. Please try again and speak clearly."
            print("❌ STT UnknownValueError: ", msg)
            return jsonify({
                "error": msg,
                "code": "stt_unknown",
                "can_retry": True
            }), 400
        except sr.WaitTimeoutError:
            msg = "I didn't hear anything. Try speaking again."
            print("⏱️ STT WaitTimeoutError: ", msg)
            return jsonify({
                "error": msg,
                "code": "stt_timeout",
                "can_retry": True
            }), 408
        except sr.RequestError as e:
            # Network/API issue with Google STT
            msg = f"Speech recognition service failed: {e}"
            print("🌐 STT RequestError: ", msg)
            return jsonify({
                "error": msg,
                "code": "stt_api_error",
                "can_retry": False
            }), 502

        # 🧠 Ask Gemini what to do with the recognized text
        gemini_decision = ask_gemini_for_action(user_text)
        print(f"🔍 Raw Gemini decision type: {type(gemini_decision)}")

        # Ensure safe dict structure
        if not isinstance(gemini_decision, dict):
            try:
                gemini_decision = json.loads(str(gemini_decision))
            except Exception:
                gemini_decision = {"action": "none", "reply": str(gemini_decision)}

        # Extract safely
        action = str(gemini_decision.get("action", "none")).lower()
        target = gemini_decision.get("target") or ""
        reply = gemini_decision.get("reply") or ""
        content = gemini_decision.get("content") or ""
        to = gemini_decision.get("to") or ""
        subject = gemini_decision.get("subject") or ""
        body = gemini_decision.get("body") or ""

        print(f"🧩 Parsed action: {action}")

        # Execute action
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
        # 🔥 Log full traceback for debugging
        print("❌ Full backend error:\n", traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500



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