# File: config_manager.py
import os
import json

# Define the directory and file for storing configuration
CONFIG_DIR_NAME = "user_config"
SETTINGS_FILE_NAME = "settings.json"

# Get the absolute path to the directory where this script is located
# This ensures that CONFIG_DIR_NAME is created relative to the script's location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR_PATH = os.path.join(BASE_DIR, CONFIG_DIR_NAME)
SETTINGS_FILE_PATH = os.path.join(CONFIG_DIR_PATH, SETTINGS_FILE_NAME)

def ensure_config_directory_exists():
    """
    Checks if the configuration directory exists, and creates it if not.
    """
    if not os.path.exists(CONFIG_DIR_PATH):
        try:
            os.makedirs(CONFIG_DIR_PATH)
            print(f"Configuration directory created: {CONFIG_DIR_PATH}")
        except OSError as e:
            print(f"Error creating configuration directory {CONFIG_DIR_PATH}: {e}")
            # Depending on the error, you might want to raise it or handle it differently
            raise # Re-raise the exception if directory creation fails critically

def save_settings(api_key, chrome_selected, opera_selected, firefox_selected):
    """
    Saves the provided settings to the settings file in JSON format.
    """
    ensure_config_directory_exists() # Ensure directory is there before trying to save

    settings_data = {
        "api_key": api_key,
        "web_browsers": {
            "chrome": chrome_selected,
            "opera": opera_selected,
            "firefox": firefox_selected,
        }
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
    ensure_config_directory_exists() # Good practice, though mainly for initial setup

    default_settings = {
        "api_key": "",
        "web_browsers": {
            "chrome": True,  # Default to True as in the original UI
            "opera": True,
            "firefox": True,
        }
    }

    if not os.path.exists(SETTINGS_FILE_PATH):
        print(f"Settings file not found at {SETTINGS_FILE_PATH}. Using default settings.")
        return default_settings

    try:
        with open(SETTINGS_FILE_PATH, "r") as f:
            settings_data = json.load(f)
            # You might want to add more validation here to ensure the loaded data has the expected structure
            if not isinstance(settings_data.get("api_key"), str): # Basic validation
                settings_data["api_key"] = default_settings["api_key"]
            if not isinstance(settings_data.get("web_browsers"), dict): # Basic validation
                settings_data["web_browsers"] = default_settings["web_browsers"]
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
