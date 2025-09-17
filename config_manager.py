# File: config_manager.py
import os
import sys
import json

# Define the directory and file for storing configuration
CONFIG_DIR_NAME = "user_config"
SETTINGS_FILE_NAME = "settings.json"

# Get the directory where the executable/script is located
if getattr(sys, 'frozen', False):
    # If running as executable
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # If running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_DIR_PATH = os.path.join(BASE_DIR, CONFIG_DIR_NAME)
SETTINGS_FILE_PATH = os.path.join(CONFIG_DIR_PATH, SETTINGS_FILE_NAME)

def get_default_settings():
    """
    Returns the default settings that should be used when creating a new settings file.
    """
    return {
        "api_key": "",
        "browsers": [],
        "banned": [],
        "allowed": [
            # Cross-platform/common
            "new tab", "keymind", "terminal",
            # Windows
            "explorer", "start", "shellhost", "shell", "lockapp", "taskbar", "task manager",
            "settings", "control panel", "system", "search", "notification", "security center",
            "windows defender", "windows security", "cmd", "powershell",
            # macOS (Finder, System Settings, Spotlight, etc.)
            "Finder", "System Settings", "Activity Monitor", "Spotlight", "Launchpad",
            "Safari", "Terminal", "Console"
        ]
    }

def ensure_config_directory_exists():
    """
    Checks if the configuration directory exists, and creates it if not.
    Also creates a default settings.json if it doesn't exist.
    """
    if not os.path.exists(CONFIG_DIR_PATH):
        try:
            os.makedirs(CONFIG_DIR_PATH)
            print(f"Configuration directory created: {CONFIG_DIR_PATH}")
        except OSError as e:
            print(f"Error creating configuration directory {CONFIG_DIR_PATH}: {e}")
            raise  # Re-raise the exception if directory creation fails critically
    
    # Create default settings file if it doesn't exist
    if not os.path.exists(SETTINGS_FILE_PATH):
        try:
            with open(SETTINGS_FILE_PATH, 'w') as f:
                json.dump(get_default_settings(), f, indent=4)
            print(f"Default settings file created at: {SETTINGS_FILE_PATH}")
        except IOError as e:
            print(f"Error creating default settings file: {e}")
            raise

def save_settings(api_key, browsers, banned, allowed):
    """
    Saves the provided settings to the settings file in JSON format.
    """
    ensure_config_directory_exists()

    settings_data = {
        "api_key": api_key,
        "browsers": browsers,
        "banned": banned,
        "allowed": allowed
    }

    try:
        with open(SETTINGS_FILE_PATH, "w") as f:
            json.dump(settings_data, f, indent=4)
        print(f"Settings saved to: {SETTINGS_FILE_PATH}")
    except IOError as e:
        print(f"Error saving settings to {SETTINGS_FILE_PATH}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving settings: {e}")

def load_settings():
    """
    Loads settings from the settings file.
    Returns a dictionary with settings or default values if the file doesn't exist or is invalid.
    """
    ensure_config_directory_exists()  # This will create default settings if they don't exist
    default_settings = get_default_settings()

    if not os.path.exists(SETTINGS_FILE_PATH):
        print(f"Settings file not found at {SETTINGS_FILE_PATH}. Using default settings.")
        return default_settings

    try:
        with open(SETTINGS_FILE_PATH, "r") as f:
            settings_data = json.load(f)
            
            # Validate and convert settings to new format if needed
            if not isinstance(settings_data.get("api_key"), str):
                settings_data["api_key"] = default_settings["api_key"]

            # Convert old web_browsers format if it exists
            if "web_browsers" in settings_data:
                old_browsers = settings_data.pop("web_browsers")
                if isinstance(old_browsers, dict):
                    settings_data["browsers"] = [
                        browser for browser, enabled in old_browsers.items() 
                        if enabled
                    ]

            # Ensure lists exist and are valid
            for key in ["browsers", "banned", "allowed"]:
                if not isinstance(settings_data.get(key), list):
                    settings_data[key] = default_settings[key]

            return settings_data
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {SETTINGS_FILE_PATH}. Using default settings.")
        return default_settings
    except IOError as e:
        print(f"Error loading settings from {SETTINGS_FILE_PATH}: {e}. Using default settings.")
        return default_settings
    except Exception as e:
        print(f"An unexpected error occurred while loading settings: {e}. Using default settings.")
        return default_settings

if __name__ == '__main__':
    # Example usage (for testing this module directly)
    print(f"Base directory: {BASE_DIR}")
    print(f"Config directory path: {CONFIG_DIR_PATH}")
    print(f"Settings file path: {SETTINGS_FILE_PATH}")

    ensure_config_directory_exists()
    save_settings("test_api_key_123", True, False, True)
    loaded = load_settings()
    print("\nLoaded settings:")
    print(json.dumps(loaded, indent=4))

    # Test loading when file doesn't exist (by temporarily renaming it)
    if os.path.exists(SETTINGS_FILE_PATH):
        temp_name = SETTINGS_FILE_PATH + ".bak"
        os.rename(SETTINGS_FILE_PATH, temp_name)
        print(f"\nTesting load with no file (renamed to {temp_name})...")
        loaded_no_file = load_settings()
        print(json.dumps(loaded_no_file, indent=4))
        os.rename(temp_name, SETTINGS_FILE_PATH) # Rename back
