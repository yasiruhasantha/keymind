# File: app_logic/settings_actions.py

def save_settings_action(api_key, chrome, opera, firefox):
    """
    Saves the provided settings.
    For now, it just prints them. In a real application,
    this function would write to a configuration file, database, etc.
    """
    print("Save action from app_logic/settings_actions.py!")
    print(f"Saving API Key: '{api_key}'") # Added quotes for clarity if API key is empty
    print(f"Chrome selected: {chrome}")
    print(f"Opera selected: {opera}")
    print(f"Firefox selected: {firefox}")

    # --- Placeholder for actual saving logic ---
    # Example: Saving to a simple text file (config.txt)
    try:
        with open("config.txt", "w") as f:
            f.write(f"API_KEY={api_key}\n")
            f.write(f"BROWSER_CHROME={chrome}\n")
            f.write(f"BROWSER_OPERA={opera}\n")
            f.write(f"BROWSER_FIREFOX={firefox}\n")
        print("Settings saved to config.txt")
    except IOError as e:
        print(f"Error saving settings to file: {e}")
    # --- End of placeholder ---

def load_settings_action():
    """
    Loads settings.
    For now, it tries to read from 'config.txt'.
    In a real application, this would read from the same source as save_settings_action.
    """
    print("Load action from app_logic/settings_actions.py!")
    settings = {
        "api_key": "",
        "chrome": False,
        "opera": False,
        "firefox": False
    }
    try:
        with open("config.txt", "r") as f:
            for line in f:
                line = line.strip()
                if not line or '=' not in line:
                    continue
                key, value = line.split("=", 1)
                if key == "API_KEY":
                    settings["api_key"] = value
                elif key == "BROWSER_CHROME":
                    settings["chrome"] = value.lower() == 'true'
                elif key == "BROWSER_OPERA":
                    settings["opera"] = value.lower() == 'true'
                elif key == "BROWSER_FIREFOX":
                    settings["firefox"] = value.lower() == 'true'
        print("Settings loaded from config.txt")
        return settings
    except FileNotFoundError:
        print("config.txt not found. Using default settings.")
        return settings # Return default if file not found
    except IOError as e:
        print(f"Error loading settings from file: {e}")
        return settings # Return default on other errors
