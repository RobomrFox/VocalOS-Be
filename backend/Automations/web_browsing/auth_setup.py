# auth_setup.py
import sys
from playwright.sync_api import sync_playwright

AUTH_FILE_PATH = "auth.json"

def run_auth_setup():
    with sync_playwright() as p:
        # Launch a visible browser
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Go to the login page
        page.goto("https://gmail.com")
        
        print("\n-------------------------------------------------------------")
        print("Please log in to your Google Account in the browser window.")
        print("After you are fully logged in, press 'Enter' in this terminal.")
        print("-------------------------------------------------------------")
        
        # Wait for user to press Enter
        input()

        try:
            # Save the storage state to the file
            context.storage_state(path=AUTH_FILE_PATH)
            print(f"Successfully saved authentication state to {AUTH_FILE_PATH}")
        except Exception as e:
            print(f"Failed to save auth state: {e}")
        
        browser.close()

if __name__ == "__main__":
    run_auth_setup()