from flask import Flask, request, jsonify
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
import sys
from datetime import datetime  # ✅ for date/time answers

sys.stdout.reconfigure(encoding='utf-8')

# ✅ Load environment variables from .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print(f"🔍 GOOGLE_API_KEY loaded? {'✅ Yes' if api_key else '❌ No'}")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# === Gemini API setup ===
if not api_key:
    raise EnvironmentError("❌ Missing GOOGLE_API_KEY in .env file.")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")
print("✅ Gemini connected successfully!")

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

# === Built-in quick answers (date/time etc.) ===
def handle_builtin_question(user_text: str):
    """Handle very simple questions locally without Gemini (date/time/day)."""
    text = (user_text or "").strip().lower()
    if not text:
        return None

    now = datetime.now()

    # Time questions
    if any(phrase in text for phrase in ["what time is it", "current time", "time now", "tell me the time"]):
        return f"It’s {now.strftime('%I:%M %p')}."

    # Date questions
    if "date" in text or "today" in text:
        # e.g. "what is the date today", "what's today's date"
        return f"Today is {now.strftime('%A, %B %d, %Y')}."

    # Day-of-week questions
    if "what day is it" in text or ("day" in text and "today" in text):
        return f"Today is {now.strftime('%A')}."

    return None

# === Fallback free-chat with Gemini ===
def fallback_chat(user_text: str) -> str:
    """If structured action flow can't help, just talk like a normal AI."""
    try:
        prompt = """
You are VocalAI, a friendly conversational assistant.
The user already tried a command mode and it wasn't helpful enough.
Now just answer naturally and helpfully, with NO JSON, only plain text.
"""
        resp = model.generate_content(f"{prompt}\nUser: {user_text}")
        reply = (resp.text or "").strip()
        return reply or "Sorry, I’m still thinking about how to answer that."
    except Exception as e:
        print("❌ Fallback chat error:", e)
        return "Sorry, something went wrong while trying to answer that."

# === Ask Gemini for actions ===
def ask_gemini_for_action(user_text):
    """Ask Gemini to interpret user intent, handle memory-like context, auto-correct speech, and continuously self-correct while generating."""
    import re
    open_windows = [w.title for w in gw.getAllWindows() if w.title]
    context = f"Currently open windows: {open_windows[:5]}"

    # 🧠 Persistent pseudo-memory (same as before)
    memory_context = {
        "known_contacts": ["professor", "John", "Ava", "Mom", "Dad"],
        "known_hobbies": ["coding", "music", "travel", "photography"],
        "recent_topics": ["hackathon", "Gemini integration", "VocalAI design"]
    }

    # 🪄 STEP 1: Pre-correct the speech text before reasoning (lightweight + fast)
    try:
        correction_prompt = f"""
        You are a precise language model helping correct speech-to-text output.
        The user's phrase came from microphone transcription: "{user_text}".
        Fix any misspellings, missing letters, spacing issues, or duplicated words
        while keeping the same meaning and tone.
        Return ONLY the corrected sentence (no explanation, no quotes).
        """
        correction = model.generate_content(correction_prompt)
        corrected_text = (correction.text or "").strip()
        if corrected_text:
            print(f"🪄 Auto-corrected speech → {corrected_text}")
            user_text = corrected_text
    except Exception as e:
        print(f"⚠️ Spell correction skipped: {e}")

    # === STEP 2: Enhanced reasoning prompt with continuous correction awareness ===
    system_prompt = f"""
You are VocalAI — a friendly, proactive AI desktop assistant that listens to speech and acts or replies naturally.

The user's message was transcribed from spoken audio: "{user_text}"
(which may still include minor misheard or mispronounced words).

Your reasoning and output generation rules:
1️⃣ As you generate your reasoning and final response, continuously self-correct any remaining
    speech or transcription errors in real time — do NOT mention corrections.
2️⃣ Always interpret what the user *meant*, even if the transcript contains partial or broken words.
3️⃣ Keep your tone natural, concise, and humanlike.
4️⃣ Return output strictly as JSON — never add Markdown, explanations, or comments outside JSON.

Supported actions (choose ONE main intent per response):

### 🧩 Functional Actions
- {{ "action": "open_browser", "target": "<url or website name>" }}
- {{ "action": "open_app", "target": "<local application name>" }}
- {{ "action": "write_text", "target": "<app name>", "content": "<text to write>" }}
- {{ "action": "append_text", "target": "<app name>", "content": "<text to add>" }}
- {{ "action": "compose_email", "to": "<recipient email or name>", "subject": "<subject line>", "body": "<email body text>" }}
- {{ "action": "search", "query": "<topic or item to search>" }}
- {{ "action": "show_reminder", "time": "<datetime or relative time>", "content": "<reminder text>" }}

### 💬 Conversational Replies
- {{ "action": "none", "reply": "<response as VocalAI in a natural tone>" }}

### 🧠 Memory / Personalization
If the user says something like “Remember my hobby is painting” or “My brother’s name is Sam”, store it:
- {{ "action": "remember", "type": "hobby" | "contact" | "fact", "content": "<the info to remember>", "reply": "<short acknowledgment>" }}

If the user asks something about remembered info:
- {{ "action": "recall", "type": "<hobby/contact/fact>", "reply": "<what you remember>" }}

Example interactions:

User: "Remember my friend Jake likes photography."
→ {{ "action": "remember", "type": "contact", "content": "Jake likes photography", "reply": "Got it! I'll remember Jake is into photography." }}

User: "What do you know about my hobbies?"
→ {{ "action": "recall", "type": "hobby", "reply": "You mentioned enjoying coding, music, and photography." }}

User: "Send an email to my professor about my project update."
→ {{ "action": "compose_email", "to": "professor", "subject": "Project Update", "body": "Hi Professor, here’s my latest progress on the project..." }}

User: "Play some music."
→ {{ "action": "open_app", "target": "Spotify" }}

Current context:
{context}

Known memory:
{memory_context}
"""

    print("🧠 Asking Gemini to interpret + generate meaningful content...")

    try:
        response = model.generate_content(f"{system_prompt}\n\nUser: {user_text}")
        text = (response.text or "").strip()
        print(f"🤖 Gemini raw output: {text}")

        # ✅ Clean Markdown formatting if present
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()

        # ✅ Try parsing JSON directly
        try:
            parsed = json.loads(text)
            return parsed
        except Exception as e:
            print(f"⚠️ JSON parsing failed: {e}")
            # Attempt to extract JSON-like substring
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    return parsed
                except Exception as e2:
                    print(f"⚠️ Fallback parse failed: {e2}")

        # 🧩 Fallback — treat the entire string as natural chat
        return {"action": "none", "reply": text}

    except Exception as e:
        print("❌ ask_gemini_for_action error:", e)
        return {"action": "none", "reply": "Sorry, something went wrong while thinking about that."}



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
            user_text = recognizer.recognize_google(audio)
            print(f"🗣️ You said: {user_text}")
        except sr.UnknownValueError:
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
            msg = f"Speech recognition service failed: {e}"
            print("🌐 STT RequestError: ", msg)
            return jsonify({
                "error": msg,
                "code": "stt_api_error",
                "can_retry": False
            }), 502

        # 🧩 First, check if we can answer locally (date/time/etc.)
        builtin = handle_builtin_question(user_text)
        if builtin:
            print("⚡ Answered via builtin handler.")
            return jsonify({"text": user_text, "reply": builtin})

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
            # 🔁 Fallback: normal chat answer instead of "I'm not sure"
            reply_text = fallback_chat(user_text)

        print(f"✅ Reply: {reply_text}")
        return jsonify({"text": user_text, "reply": reply_text})

    except Exception as e:
        # 🔥 Log full traceback for debugging
        print("❌ Full backend error:\n", traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route("/listen-voice-ai", methods=["POST"])
def listen_voice_ai():
    """🎙️ Voice input → Gemini reasoning → perform action safely."""
    try:
        with sr.Microphone() as source:
            print("🎧 Listening... please speak clearly.")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)

        print("🧠 Processing your voice...")

        try:
            user_text = recognizer.recognize_google(audio)
            print(f"🗣️ You said: {user_text}")
        except sr.UnknownValueError:
            msg = "I couldn't understand what you said. Please try again and speak clearly."
            print("❌ STT UnknownValueError: ", msg)
            return jsonify({"error": msg, "code": "stt_unknown", "can_retry": True}), 400
        except sr.WaitTimeoutError:
            msg = "I didn't hear anything. Try speaking again."
            print("⏱️ STT WaitTimeoutError: ", msg)
            return jsonify({"error": msg, "code": "stt_timeout", "can_retry": True}), 408
        except sr.RequestError as e:
            msg = f"Speech recognition service failed: {e}"
            print("🌐 STT RequestError: ", msg)
            return jsonify({"error": msg, "code": "stt_api_error", "can_retry": False}), 502

        # 🧩 Try builtin first
        builtin = handle_builtin_question(user_text)
        if builtin:
            print("⚡ Answered via builtin handler (AI route).")
            return jsonify({"text": user_text, "reply": builtin})

        # 🧠 Ask Gemini for what to do
        gemini_decision = ask_gemini_for_action(user_text)
        if not isinstance(gemini_decision, dict):
            try:
                gemini_decision = json.loads(str(gemini_decision))
            except Exception:
                gemini_decision = {"action": "none", "reply": str(gemini_decision)}

        action = str(gemini_decision.get("action", "none")).lower()
        target = gemini_decision.get("target") or ""
        reply = gemini_decision.get("reply") or ""
        content = gemini_decision.get("content") or ""
        to = gemini_decision.get("to") or ""
        subject = gemini_decision.get("subject") or ""
        body = gemini_decision.get("body") or ""

        print(f"🧩 Parsed action: {action}")

        # Perform the action
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
            reply_text = fallback_chat(user_text)

        print(f"✅ Reply: {reply_text}")
        return jsonify({"text": user_text, "reply": reply_text})

    except Exception as e:
        print("❌ Full backend error:\n", traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route("/wakeword", methods=["POST"])
def wakeword():
    """🎧 Gemini interprets if spoken phrase is a wake-up call."""
    try:
        with sr.Microphone() as source:
            print("🎤 Listening for possible wake phrase...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=4)

        # Convert to text
        text = recognizer.recognize_google(audio).lower()
        print(f"🗣️ Heard → {text}")

        # Ask Gemini if this is a wake-up phrase
        prompt = f"""
        You are Audient, a voice assistant.
        Determine if the user is trying to wake you up or greet you.
        If the phrase sounds like 'hey audient', 'hello', 'hi audient', or any greeting
        meant to activate you, return:
        {{ "wake": true, "reason": "greeting detected" }}
        Otherwise return:
        {{ "wake": false, "reason": "not a wake phrase" }}

        User said: "{text}"
        """
        result = model.generate_content(prompt)
        reply = result.text.strip()

        # clean JSON
        import re, json
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

# === Run server ===
if __name__ == "__main__":
    app.run(debug=True)
