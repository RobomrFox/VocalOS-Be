import json
import os

CONFIG_FILE = 'config.json'

def setup_assistant():
    print("\n" + "=" * 50)
    print("VocalOS Setup")
    print("=" * 50)
    name = input("\nWhat do you want to call your assistant? (e.g., Jarvis, Friday): ").strip()
    
    if not name:
        name = "Jarvis"
        print(f"Using default name: {name}")
    
    config = {
        'wake_word': name.lower(),
        'wake_pause': 0.7,       # Wake word detection (in seconds)
        'command_pause': 0.7,    # Command execution pause
        'dictation_pause': 1.2   # Dictation mode pause
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Setup complete! Your assistant is named '{name}'")
    print(f"Say 'Hey {name}' to activate.\n")
    
    return config

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return setup_assistant()
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)
