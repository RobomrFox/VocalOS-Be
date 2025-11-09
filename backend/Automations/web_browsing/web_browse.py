import sys
import time
from playwright.sync_api import sync_playwright
import os

AUTH_FILE_PATH = "auth.json"

def get_script_dir():
    # Gets the directory where this script is located
    return os.path.dirname(os.path.realpath(__file__))

def run_playwright_shell():
    auth_file = os.path.join(get_script_dir(), AUTH_FILE_PATH)
    
    if not os.path.exists(auth_file):
        print(f"Error: Auth file not found: {auth_file}")
        print("Please run 'python auth_setup.py' first to log in.")
        return

    print("--- Playwright Shell Initialized ---")
    print(f"Loading authentication state from {auth_file}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(storage_state=auth_file)
        page = context.new_page()
        
        page.goto("https://www.google.com")
        
        print("\n--- Commands ---")
        print("  goto [url]              - Navigates to a URL")
        print("  fill [selector] [text]  - Fills a field")
        print("  click [selector]        - Clicks an element")
        print("  press [selector] [key]  - Simulates a key press (e.g., 'Enter')") # <-- ADDED
        print("  exit                    - Quits the shell")
        print("---------------------------------")
        print(f"Successfully loaded: {page.title()}")

        while True:
            try:
                command = input(f"playwright> ")
                if not command:
                    continue
                
                parts = command.split(" ", 2)
                action = parts[0].lower()

                if action == "exit":
                    print("Exiting...")
                    break
                
                elif action == "goto":
                    url = parts[1]
                    if not url.startswith("http"):
                        url = "https://" + url
                    print(f"Navigating to {url}...")
                    page.goto(url)
                
                elif action == "fill":
                    if len(parts) < 3:
                        print("Usage: fill [selector] [text]")
                        continue
                    selector = parts[1]
                    text = parts[2]
                    print(f"Filling '{selector}' with '{text}'")
                    page.locator(selector).fill(text)

                elif action == "click":
                    if len(parts) < 2:
                        print("Usage: click [selector]")
                        continue
                    selector = parts[1]
                    print(f"Clicking: {selector}")
                    page.locator(selector).click()
                
                # --- NEW COMMAND ---
                elif action == "press":
                    if len(parts) < 3:
                        print("Usage: press [selector] [key]")
                        continue
                    selector = parts[1]
                    key = parts[2]
                    print(f"Pressing '{key}' on '{selector}'")
                    page.locator(selector).press(key)

                else:
                    print(f"Unknown command: {action}")

                page.wait_for_load_state("load", timeout=5000)
                print(f"Current Page: {page.title()}")

            except Exception as e:
                print(f"--- ERROR: {e} ---")
            
        browser.close()

if __name__ == "__main__":
    run_playwright_shell()