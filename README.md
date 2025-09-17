# KeyMind.

KeyMind is an AI-powered focus management tool that helps you maintain productivity by monitoring and managing your active windows and applications. It uses Google's Gemini AI to determine task relevance and automatically manages distracting applications and browser tabs.

## Features

- **AI-Powered Task Relevance**: Uses Google Gemini AI to determine if your current activity is relevant to your task
- **Smart Window Management**: Automatically monitors active windows and browser tabs
- **Distraction Control**: Can close irrelevant applications and browser tabs
- **Customizable Settings**: Configure allowed and banned applications, browsers, and more
- **Modern UI**: Built with CustomTkinter for a clean, modern interface

## Requirements

- Google Gemini API key
- Windows or macOS (Linux support coming soon)

## Installation

1. Download the latest release from the [Releases page](https://github.com/yasiruhasantha/keymind/releases)

2. Extract the downloaded file to your desired location

3. Run the application - it will automatically create a settings file with default configurations

4. Bypass Gatekeeper (macOS only) – Watch this [video](https://youtu.be/biIvAM94b98) (There is no security risk because this is open source and will not try to steal your data or anything)


## Configuration

The application can be configured through the settings tab in the UI. Settings are stored in `user_config/settings.json`, which is automatically created with secure defaults when you first run the application.

You can customize your settings either through the UI or by directly editing `user_config/settings.json`:

```json
{
    "api_key": "YOUR_GEMINI_API_KEY",
    "browsers": ["firefox", "chrome"],
    "banned": ["games", "social media apps"],
    "allowed": [
        "new tab", "keymind", "explorer", "start", "shellhost",
        "shell", "taskbar", "task manager", "settings", "control panel",
        "system", "search", "notification", "security center",
        "windows defender", "windows security", "cmd", "powershell",
        "terminal"
    ]
}
```

> **Note**: The application comes with a pre-configured list of allowed system applications to ensure basic system functionality remains accessible.

### Configuration Options

- `api_key`: Your Google Gemini API key (required)
- `browsers`: List of browser names to monitor (e.g., "firefox", "chrome")
- `banned`: List of applications that will always be considered distracting
- `allowed`: List of applications that will always be considered relevant (includes system essentials)

## Usage

1. Start the application by running `KeyMind.exe` (Windows) or `python main.py` (macOS during development)

2. Enter your current task in the main window
   - Example: "Writing documentation for the project"

3. Click "Start" to begin focus monitoring
   - KeyMind will monitor your active windows and browser tabs
   - It will use AI to determine if each new window/tab is relevant to your task
   - Irrelevant applications/tabs will be automatically closed

4. Click "Stop" when you want to pause the monitoring

## Dependencies

- customtkinter>=5.2.0
- psutil>=5.9.0
- pyautogui>=0.9.54
- google-generativeai>=0.3.0
- pygetwindow>=0.0.9 (Windows)
- pywin32>=306 (Windows)
- pyobjc>=10.3 (macOS)

## Development

The project structure is organized as follows:

```
keymind/
├── main.py                 # Application entry point
├── config_manager.py       # Settings management
├── app_logic/
│   ├── monitor.py         # Window monitoring
│   ├── task_checker.py    # AI relevance checking
│   └── __init__.py
└── requirements.txt       # Project dependencies

Note: When you run the application, it will create a `user_config` directory
with your personal settings file.
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
