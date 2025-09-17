import google.generativeai as genai
import json
import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('keymind_ai.log'),
        logging.StreamHandler()
    ]
)

def get_api_key():
    """Get Gemini API key from settings."""    
    try:
        # Get the directory where the executable/script is located
        if getattr(sys, 'frozen', False):
            # If running as executable
            base_path = os.path.dirname(sys.executable)
        else:
            # If running as script
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        settings_path = os.path.join(base_path, "user_config", "settings.json")
        logging.info(f"Looking for settings at: {os.path.abspath(settings_path)}")
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            api_key = settings.get("api_key", "")
            # Sanitize API key to avoid invalid header values
            if isinstance(api_key, str):
                api_key = api_key.strip()
            if api_key:
                logging.info("API key loaded successfully")
            else:
                logging.error("No API key found in settings.json")
            return api_key
    except Exception as e:
        logging.error(f"Error loading API key: {e}")
        return ""

def check_relevance(task, activity):
    """Check if current activity is relevant to the task using Gemini AI."""
    logging.info(f"Checking relevance - Task: {task}, Activity: {activity}")
    
    api_key = get_api_key()
    if not api_key:
        logging.error("No API key found")
        return None

    try:
        logging.info("Configuring Gemini AI")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""Your job is to figure out if the give task and the activity is relevent to each other. When figuring out their relevence you can catogorize them to different categories like study, programming, gaming, entertainment, work, etc. and then decide if they are relevent to each other or not.
        Output ONLY the number 1 if relevant, or 0 if not relevant.
        
        Task: {task}
        Activity: {activity}
        """
        
        logging.info("Sending request to Gemini AI")
        response = model.generate_content(prompt)
        result = response.text.strip()
        logging.info(f"Received response from Gemini AI: {result}")
        
        # Convert response to integer (1 or 0)
        try:
            result_int = int(result)
            logging.info(f"Parsed result: {result_int}")
            return result_int
        except ValueError:
            logging.error(f"Invalid AI response format: {result}")
            return None
            
    except Exception as e:
        print("Error checking relevance:", e)
        return None
