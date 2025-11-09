# playwright_service.py
# This file is a background service. You DO NOT run this file.
# Run main.py instead.

import sys
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright, Page
import atexit

app = Flask(__name__)
CORS(app)

# --- Global Playwright State ---
playwright_instance = None
pw_globals = {"browser": None, "context": None, "page": None}
AUTH_FILE_PATH = "auth.json"

def get_script_dir():
    return os.path.dirname(os.path.realpath(__file__))

def startup_playwright():
    """Initializes Playwright and launches a persistent browser."""
    global playwright_instance, pw_globals
    auth_file = os.path.join(get_script_dir(), AUTH_FILE_PATH)
    storage_state = auth_file if os.path.exists(auth_file) else None
    
    if storage_state:
        print(f"[playwright_service]: Loading auth state from {auth_file}")
    else:
        print(f"[playwright_service]: ⚠️ Warning: auth.json not found.")
        
    print(f"[playwright_service]: 🚀 Launching Playwright browser...")
    playwright_instance = sync_playwright().start()
    pw_globals["browser"] = playwright_instance.chromium.launch(
        channel="chrome", headless=False
    )
    pw_globals["context"] = pw_globals["browser"].new_context(
        storage_state=storage_state
    )
    pw_globals["page"] = pw_globals["context"].new_page()
    pw_globals["page"].goto("https://www.google.com")
    print(f"[playwright_service]: ✅ Service running. Page: {pw_globals['page'].title()}")

def shutdown_playwright():
    """Closes the browser on exit."""
    print(f"[playwright_service]:  shutting down...")
    if pw_globals["browser"]:
        pw_globals["browser"].close()
    if playwright_instance:
        playwright_instance.stop()
    print(f"[playwright_service]: ✅ Shutdown complete.")

atexit.register(shutdown_playwright)

# --- API Endpoints for Controlling the Browser ---

def get_page():
    """Helper to safely get the page object."""
    page: Page = pw_globals.get("page")
    if not page or page.is_closed():
        raise Exception("Playwright page is not available or has been closed.")
    return page

@app.route("/execute", methods=["POST"])
def execute_command():
    """Receives and executes a browser command."""
    data = request.json
    action = data.get("action")
    
    try:
        page = get_page()
        
        if action == "goto":
            url = data.get("target")
            if not url.startswith("http"):
                url = "https://" + url
            page.goto(url)
            page.wait_for_load_state("load", timeout=5000)
            return jsonify({"status": "success", "reply": f"Navigated to {page.title()}"})

        elif action == "fill":
            selector = data.get("selector")
            text = data.get("content")
            page.locator(selector).fill(text)
            return jsonify({"status": "success", "reply": f"Filled '{selector}'"})
            
        elif action == "click":
            selector = data.get("selector")
            page.locator(selector).click()
            return jsonify({"status": "success", "reply": f"Clicked '{selector}'"})

        elif action == "press":
            selector = data.get("selector")
            key = data.get("key")
            page.locator(selector).press(key)
            return jsonify({"status": "success", "reply": f"Pressed '{key}' on '{selector}'"})
        
        # --- NEW ACTION: SCROLL ---
        elif action == "scroll":
            direction = data.get("direction", "down")
            scroll_amount = "window.innerHeight * 0.8"
            if direction == "up":
                scroll_amount = f"-{scroll_amount}"
            
            page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            return jsonify({"status": "success", "reply": f"Scrolled {direction}"})

        # --- NEW ACTION: CLICK GOOGLE RESULT ---
        elif action == "click_first_google_result":
            # This is the selector for the clickable 'h3' link in a Google search
            selector = "div[id='search'] h3 a"
            print(f"[playwright_service]: Clicking first Google result using: {selector}")
            # Use .first to grab only the first one
            page.locator(selector).first.click()
            return jsonify({"status": "success", "reply": "Clicked the first Google result."})
            
        # --- NEW ACTION: CLICK YOUTUBE VIDEO ---
        elif action == "click_first_youtube_video":
            # This is the selector for a video title link on YouTube
            selector = "a#video-title"
            print(f"[playwright_service]: Clicking first YouTube video using: {selector}")
            page.locator(selector).first.click()
            return jsonify({"status": "success", "reply": "Clicked the first YouTube video."})

        elif action == "get_title":
             return jsonify({"status": "success", "reply": page.title()})

        else:
            return jsonify({"status": "error", "reply": f"Unknown action: {action}"}), 400
            
    except Exception as e:
        print(f"[playwright_service]: ❌ Error: {e}")
        # Provide a more specific error for timeouts
        if "Timeout" in str(e):
             return jsonify({"status": "error", "reply": f"Action failed: Could not find element. (Timeout)"}), 500
        return jsonify({"status": "error", "reply": str(e)}), 500

if __name__ == "__main__":
    startup_playwright()
    # This service runs on port 5001
    app.run(port=5001, debug=False)