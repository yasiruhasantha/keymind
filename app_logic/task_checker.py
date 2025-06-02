import google.generativeai as genai
import json
import os

def get_api_key():
    """Get Gemini API key from settings."""
    try:
        settings_path = os.path.join("user_config", "settings.json")
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            return settings.get("api_key", "")
    except Exception as e:
        print("Error loading API key:", e)
        return ""

def check_relevance(task, activity):
    """Check if current activity is relevant to the task using Gemini AI."""
    api_key = get_api_key()
    if not api_key:
        print("No API key found")
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""Given a task and a current activity, determine if they are relevant to each other.
        Output ONLY the number 1 if relevant, or 0 if not relevant.
        
        Task: {task}
        Current Activity: {activity}
        """
        
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        # Convert response to integer (1 or 0)
        try:
            return int(result)
        except ValueError:
            print("Invalid AI response format")
            return None
            
    except Exception as e:
        print("Error checking relevance:", e)
        return None
