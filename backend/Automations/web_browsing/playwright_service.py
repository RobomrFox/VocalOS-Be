# playwright_service.py
# This file is a background service. You DO NOT run this file.
# Run main.py instead.

import sys
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright, Page, BrowserContext
import atexit

app = Flask(__name__)
CORS(app)

# --- Global Playwright State ---
playwright_instance = None
pw_globals = {
    "browser": None,
    "context": None,
    "active_page_index": 0
}
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
    browser = playwright_instance.chromium.launch(
        channel="chrome", headless=False
    )
    pw_globals["browser"] = browser
    
    context = browser.new_context(storage_state=storage_state)
    pw_globals["context"] = context
    
    # Create the first page
    page = context.new_page()
    
    #
    # --- THIS IS THE FIX ---
    #
    page.goto("https://www.google.com")
    
    pw_globals["active_page_index"] = 0
    
    print(f"[playwright_service]: ✅ Service running. Page: {page.title()}")

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

def get_active_page() -> Page:
    """
    Gets the currently active page.
    Also validates and corrects the active_page_index.
    """
    context: BrowserContext = pw_globals["context"]
    pages = context.pages
    
    if not pages:
        print("[playwright_service]: No pages found. Creating new tab.")
        new_page = context.new_page()
        #
        # --- THIS IS THE OTHER FIX ---
        #
        new_page.goto("https://www.google.com")
        
        pw_globals["active_page_index"] = 0
        return new_page

    if pw_globals["active_page_index"] >= len(pages):
        pw_globals["active_page_index"] = len(pages) - 1
        
    page = pages[pw_globals["active_page_index"]]
    return page

@app.route("/execute", methods=["POST"])
def execute_command():
    """Receives and executes a browser command."""
    data = request.json
    action = data.get("action")
    
    try:
        context: BrowserContext = pw_globals["context"]
        page = get_active_page()
        
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
            
        elif action == "press":
            selector = data.get("selector")
            key = data.get("key")
            page.locator(selector).press(key)
            return jsonify({"status": "success", "reply": f"Pressed '{key}' on '{selector}'"})
        
        elif action == "scroll":
            direction = data.get("direction", "down")
            scroll_amount = "window.innerHeight * 0.8"
            if direction == "up":
                scroll_amount = f"-{scroll_amount}"
            page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            return jsonify({"status": "success", "reply": f"Scrolled {direction}"})

        elif action == "click_first_google_result":
            selector = "div[id='search'] h3 a"
            page.locator(selector).first.click()
            return jsonify({"status": "success", "reply": "Clicked the first Google result."})
            
        elif action == "click_first_youtube_video":
            selector = "a#video-title"
            page.locator(selector).first.click()
            return jsonify({"status": "success", "reply": "Clicked the first YouTube video."})

        elif action == "send_email":
            selector = "div[aria-label*='Send']"
            page.locator(selector).click()
            return jsonify({"status": "success", "reply": "Clicked the 'Send' button."})
        
        elif action == "get_tab_context":
             pages = context.pages
             titles = [p.title() for p in pages]
             active_index = pw_globals["active_page_index"]
             return jsonify({"status": "success", "reply": {"titles": titles, "active_index": active_index}})

        elif action == "open_tab":
            new_page = context.new_page()
            #
            # --- THIS IS THE THIRD FIX ---
            #
            new_page.goto("https://www.google.com")
            
            pw_globals["active_page_index"] = len(context.pages) - 1
            new_page.bring_to_front()
            return jsonify({"status": "success", "reply": f"Opened new tab and made it active."})

        elif action == "close_tab":
            if len(context.pages) > 1:
                page.close()
                pw_globals["active_page_index"] = max(0, pw_globals["active_page_index"] - 1)
                return jsonify({"status": "success", "reply": "Closed the tab."})
            else:
                #
                # --- THIS IS THE FOURTH FIX ---
                #
                page.goto("https://www.google.com")
                return jsonify({"status": "success", "reply": "This is the last tab, navigated to Google."})
        
        elif action == "switch_to_tab":
            target_index_1_based = data.get("index")
            target_index_0_based = target_index_1_based - 1
            
            if 0 <= target_index_0_based < len(context.pages):
                pw_globals["active_page_index"] = target_index_0_based
                new_page = get_active_page()
                new_page.bring_to_front()
                return jsonify({"status": "success", "reply": f"Switched to tab {target_index_1_based}."})
            else:
                return jsonify({"status": "error", "reply": f"Invalid tab index: {target_index_1_based}"}), 400

        elif action == "next_tab":
            current_index = pw_globals["active_page_index"]
            total_pages = len(context.pages)
            new_index = (current_index + 1) % total_pages
            pw_globals["active_page_index"] = new_index
            new_page = get_active_page()
            new_page.bring_to_front()
            return jsonify({"status": "success", "reply": "Switched to next tab."})
            
        elif action == "prev_tab":
            current_index = pw_globals["active_page_index"]
            total_pages = len(context.pages)
            new_index = (current_index - 1 + total_pages) % total_pages
            pw_globals["active_page_index"] = new_index
            new_page = get_active_page()
            new_page.bring_to_front()
            return jsonify({"status": "success", "reply": "Switched to previous tab."})

        else:
            return jsonify({"status": "error", "reply": f"Unknown action: {action}"}), 400
            
    except Exception as e:
        print(f"[playwright_service]: ❌ Error: {e}")
        if "Timeout" in str(e):
             return jsonify({"status": "error", "reply": f"Action failed: Could not find element. (Timeout)"}), 500
        return jsonify({"status": "error", "reply": str(e)}), 500

if __name__ == "__main__":
    startup_playwright()
    
    app.run(port=5001, debug=False, threaded=False)