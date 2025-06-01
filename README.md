# KeyMind UI

A productivity-focused application that helps users maintain focus by monitoring active windows and managing distractions. Built with Python and CustomTkinter.

## Features

- Active window monitoring
- Distraction detection and management
- Customizable settings
- Browser integration
- OpenAI GPT-4 powered relevance checking
- Optional Arduino integration for physical notifications

## Requirements

- Python 3.x
- CustomTkinter
- OpenAI API key
- PyWin32
- Other dependencies (see requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/keymind-ui.git
cd keymind-ui
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the project root with:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

Run the application:
```bash
python main.py
```

## Configuration

- Settings are stored in `user_config/settings.json`
- Customize browser monitoring in settings
- Configure Arduino settings if using hardware notifications

## Project Structure

```
keymind-ui/
├── app_logic/          # Core application logic
│   ├── monitor.py      # Window monitoring functionality
│   ├── ai_check.py     # AI relevance checking
│   └── hardware.py     # Arduino integration
├── user_config/        # User configuration files
├── main.py            # Application entry point
├── config_manager.py  # Configuration management
└── README.md         # Project documentation
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.