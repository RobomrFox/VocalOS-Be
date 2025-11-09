from flask import Flask, request, jsonify, request
from flask_cors import CORS
import speech_recognition as sr
import numpy as np
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
import pickle
from dotenv import load_dotenv
import librosa 

from resemblyzer import VoiceEncoder, preprocess_wav

encoder = VoiceEncoder()

def get_embedding_from_audio_np(audio_np, sample_rate=16000):
    # Resemblyzer expects wav float32, typically sample rate 16k
    # Convert int16 numpy to float32 in range [-1, 1]
    wav = audio_np.astype(np.float32) / np.iinfo(np.int16).max
    return encoder.embed_utterance(wav)


load_dotenv()

recognizer = sr.Recognizer()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# === Gemini API setup ===
os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

recognizer = sr.Recognizer()

#speech recognition setup 


def generate_embedding_from_audio_file(file_path):
    audio_np, _ = librosa.load(file_path, sr=16000)
    return get_embedding_from_audio_np(audio_np)

enrollment_embedding_path = "enrolled_embedding.pkl"
enrolled_embedding = None

if os.path.exists(enrollment_embedding_path):
    # Load existing enrollment embedding from disk
    with open(enrollment_embedding_path, "rb") as f:
        enrolled_embedding = pickle.load(f)
else:
    # enrollment.wav might not exist if user didn't enroll yet, so check first
    if os.path.exists("enrollment.wav"):
        enrolled_embedding = generate_embedding_from_audio_file("enrollment.wav")
        with open(enrollment_embedding_path, "wb") as f:
            pickle.dump(enrolled_embedding, f)
    else:
        # No enrollment file and no saved embedding found
        enrolled_embedding = None



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

# @app.route("/voice-signature", methods=["POST"])
# def listen_voice():
#     try:
#         with sr.Microphone() as source:
#             recognizer.adjust_for_ambient_noise(source, duration=1)
#             audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)
#         user_text = recognizer.recognize_google(audio)
#         return jsonify({"text": user_text, "reply": f"Received: {user_text}"})
#     except sr.UnknownValueError:
#         return jsonify({"error": "Could not understand audio."}), 400
#     except sr.WaitTimeoutError:
#         return jsonify({"error": "Listening timed out."}), 408
#     except sr.RequestError as e:
#         return jsonify({"error": f"API request failed: {e}"}), 502
    

def is_speaker(audio_np, reference_embedding, threshold=0.65):
    test_embedding = get_embedding_from_audio_np(audio_np)
    similarity = np.dot(reference_embedding, test_embedding) / (
        np.linalg.norm(reference_embedding) * np.linalg.norm(test_embedding))
    return similarity > threshold


@app.route("/listen-voice", methods=["POST"])
def listen_voice():
    try:
        data = request.form or {}
        verify_voice = data.get("verify_voice", "true").lower() == "true"  # voice verification toggle

        # Require audio file upload from frontend for voice input
        audio_file = request.files.get("file")
        if not audio_file:
            return jsonify({"error": "No audio file uploaded"}), 400

        temp_path = "temp_audio.wav"
        audio_file.save(temp_path)

        # Load audio to numpy array at 16kHz for voice embedding comparison
        audio_np, _ = librosa.load(temp_path, sr=16000)

        # Verify voice embedding similarity if enabled
        if verify_voice:
            if enrolled_embedding is None:
                os.remove(temp_path)
                return jsonify({"error": "No enrolled voice found. Please enroll first."}), 400

            if not is_speaker(audio_np, enrolled_embedding):
                os.remove(temp_path)
                return jsonify({"error": "Voice not recognized"}), 403

        # Convert audio to text using SpeechRecognition with Google
        with sr.AudioFile(temp_path) as source:
            audio_data = recognizer.record(source)
            user_text = recognizer.recognize_google(audio_data)

        os.remove(temp_path)

        # Ask Gemini model for action based on recognized user_text
        gemini_decision = ask_gemini_for_action(user_text)
        if not isinstance(gemini_decision, dict):  # Safe parse fallback
            try:
                gemini_decision = json.loads(str(gemini_decision))
            except Exception:
                gemini_decision = {"action": "none", "reply": str(gemini_decision)}

        reply = gemini_decision.get("reply", "")

        # Implement any required action execution here if needed

        return jsonify({"text": user_text, "reply": reply})

    except sr.UnknownValueError:
        return jsonify({"error": "Could not understand audio."}), 400
    except sr.WaitTimeoutError:
        return jsonify({"error": "Listening timed out."}), 408
    except sr.RequestError as e:
        return jsonify({"error": f"API request failed: {e}"}), 502
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