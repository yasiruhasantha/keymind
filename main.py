import customtkinter as ctk
import config_manager
from app_logic import WindowMonitor
import time

# --- Appearance Settings ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("KeyMind - Focus Assistant")
        self.geometry("600x550")

        self.grid_rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(self, width=580, height=530)
        self.tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.tab_view.add("home")
        self.tab_view.add("settings")

        # Initialize window monitor
        self.window_monitor = WindowMonitor()
        self.current_active_window_title = "Initializing..."

        self.setup_home_tab()
        self.setup_settings_tab()
        self.apply_loaded_settings()

        # Start monitoring
        self.update_window_title()

        # Set up window close handler
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_window_title(self):
        """Update the displayed window title and check task relevance."""
        from app_logic.task_checker import check_relevance
        
        title = self.window_monitor.get_active_window_title()
        current_time = time.time()
        if title and title != self.current_active_window_title:
            self.current_active_window_title = title
            self.active_window_display_label.configure(text=title)
            
            # Check relevance if monitoring is active and we have a task
            if hasattr(self, 'monitoring_active') and self.monitoring_active:
                if hasattr(self, 'last_activity') and title != self.last_activity:
                    # Wait 5 seconds before checking new activity                    if current_time - getattr(self, 'last_check_time', 0) >= 5:
                        # Load current settings
                        settings = config_manager.load_settings()
                        allowed = settings.get('allowed', [])
                        banned = settings.get('banned', [])
                        browsers = settings.get('browsers', [])

                        # Check if activity is in allowed list
                        if any(allowed_app.lower() in title.lower() for allowed_app in allowed):
                            print(f"Relevance check: {title} - Relevant (in allowed list)")
                            relevance = 1
                        # Check if activity is in banned list
                        elif any(banned_app.lower() in title.lower() for banned_app in banned):
                            print(f"Relevance check: {title} - Not relevant (in banned list)")
                            relevance = 0
                        # If not in either list, use AI to check relevance
                        else:
                            relevance = check_relevance(self.current_task, title)
                            if relevance is not None:
                                print(f"Relevance check: {title} - {'Relevant' if relevance == 1 else 'Not relevant'} (AI decision)")
                        
                        # If activity is not relevant, close it
                        if relevance == 0:
                            import pyautogui
                            pyautogui.PAUSE = 0.5  # Add a small delay between actions
                            
                            # Check if it's a browser by looking at the process name or window title
                            title_lower = title.lower()
                            is_browser = any(browser.lower() in title_lower for browser in browsers)
                            
                            if is_browser:
                                # For browsers, close tab with Ctrl+W and open new tab with Ctrl+T
                                print(f"Closing browser tab: {title}")
                                pyautogui.hotkey('ctrl', 'w')
                                pyautogui.hotkey('ctrl', 't')
                            else:
                                # For other applications, use Alt+F4
                                print(f"Closing application: {title}")
                                pyautogui.hotkey('alt', 'f4')
                        
                        self.last_check_time = current_time
                        self.last_activity = title

        self.after(200, self.update_window_title)

    def apply_loaded_settings(self):
        """Loads settings using config_manager and applies them to the UI."""
        print("Loading settings into UI...")
        loaded_config = config_manager.load_settings()

        # Apply API key
        self.api_key_entry.delete(0, "end")
        self.api_key_entry.insert(0, loaded_config.get("api_key", ""))

        # Apply browsers
        self.browsers_entry.delete(0, "end")
        browsers = loaded_config.get("browsers", [])
        if isinstance(browsers, list):
            self.browsers_entry.insert(0, ", ".join(browsers))

        # Apply banned apps
        self.banned_entry.delete(0, "end")
        banned = loaded_config.get("banned", [])
        if isinstance(banned, list):
            self.banned_entry.insert(0, ", ".join(banned))

        # Apply allowed apps
        self.allowed_entry.delete(0, "end")
        allowed = loaded_config.get("allowed", [])
        if isinstance(allowed, list):
            self.allowed_entry.insert(0, ", ".join(allowed))

        print("Settings applied to UI.")

    def on_closing(self):
        """Handles application close events."""
        print("Closing application...")
        self.destroy()

    def setup_home_tab(self):
        home_frame = self.tab_view.tab("home")
        home_frame.grid_rowconfigure(0, weight=1)
        home_frame.grid_rowconfigure(1, weight=1)
        home_frame.grid_rowconfigure(2, weight=1)
        home_frame.grid_rowconfigure(3, weight=1)
        home_frame.grid_columnconfigure(0, weight=1)

        # Task label at the top
        task_label = ctk.CTkLabel(
            home_frame,
            text="Enter your task:",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        task_label.grid(row=0, column=0, padx=20, pady=(100, 0))

        # Task input below label
        self.task_entry = ctk.CTkEntry(
            home_frame,
            width=400,
            height=35
        )
        self.task_entry.grid(row=1, column=0, padx=20, pady=(20, 0))

        # Start button below input
        self.start_button = ctk.CTkButton(
            home_frame,
            text="Start",
            width=150,
            height=40,
            font=ctk.CTkFont(size=15),
            command=self.on_start_button_press
        )
        self.start_button.grid(row=2, column=0, pady=(20, 0))

        # Current activity at bottom
        self.active_window_display_label = ctk.CTkLabel(
            home_frame, 
            text="current activity",
            font=ctk.CTkFont(size=20),
            wraplength=500
        )
        self.active_window_display_label.grid(row=3, column=0, pady=(50, 20))

    def setup_settings_tab(self):
        settings_frame = self.tab_view.tab("settings")
        settings_frame.grid_columnconfigure(0, weight=0)
        settings_frame.grid_columnconfigure(1, weight=1)

        # API Key Section
        api_key_label = ctk.CTkLabel(settings_frame, text="Gemini API Key", anchor="w")
        api_key_label.grid(row=0, column=0, padx=(20,10), pady=20, sticky="w")

        self.api_key_entry = ctk.CTkEntry(settings_frame, placeholder_text="Enter your API key", width=350)
        self.api_key_entry.grid(row=0, column=1, padx=(0,20), pady=20, sticky="ew")

        # Browsers Section
        browsers_label = ctk.CTkLabel(settings_frame, text="Browsers", anchor="w")
        browsers_label.grid(row=1, column=0, padx=(20,10), pady=20, sticky="w")

        self.browsers_entry = ctk.CTkEntry(settings_frame, placeholder_text="Enter comma-separated browser names", width=350)
        self.browsers_entry.grid(row=1, column=1, padx=(0,20), pady=20, sticky="ew")

        # Banned Section
        banned_label = ctk.CTkLabel(settings_frame, text="Banned", anchor="w")
        banned_label.grid(row=2, column=0, padx=(20,10), pady=20, sticky="w")

        self.banned_entry = ctk.CTkEntry(settings_frame, placeholder_text="Enter comma-separated app names", width=350)
        self.banned_entry.grid(row=2, column=1, padx=(0,20), pady=20, sticky="ew")

        # Allowed Section
        allowed_label = ctk.CTkLabel(settings_frame, text="Allowed", anchor="w")
        allowed_label.grid(row=3, column=0, padx=(20,10), pady=20, sticky="w")

        self.allowed_entry = ctk.CTkEntry(settings_frame, placeholder_text="Enter comma-separated app names", width=350)
        self.allowed_entry.grid(row=3, column=1, padx=(0,20), pady=20, sticky="ew")

        # Help text
        help_label = ctk.CTkLabel(
            settings_frame,
            text="Note: Enter app and browser names as comma-separated values.\nExample: chrome, firefox, microsoft edge",
            text_color="gray",
            justify="left"
        )
        help_label.grid(row=4, column=0, columnspan=2, padx=20, pady=(0,20), sticky="w")

        # Spacer
        spacer_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        spacer_frame.grid(row=5, column=0, columnspan=2, sticky="nsew")
        settings_frame.grid_rowconfigure(5, weight=1)

        # Buttons
        buttons_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        buttons_frame.grid(row=6, column=0, columnspan=2, padx=20, pady=(10,20), sticky="sw")

        save_button = ctk.CTkButton(
            buttons_frame,
            text="Save",
            width=100,
            command=self.on_save_button_press
        )
        save_button.pack(side="left", padx=(0,10))

        cancel_button = ctk.CTkButton(
            buttons_frame,
            text="Cancel",
            width=100,
            fg_color="gray",
            hover_color="darkgray",
            command=self.on_cancel_button_press
        )
        cancel_button.pack(side="left")

    def on_save_button_press(self):
        """Gathers data from UI and saves it using config_manager."""
        # Get settings from UI
        api_key = self.api_key_entry.get()
        browsers = [b.strip() for b in self.browsers_entry.get().split(",") if b.strip()]
        banned = [a.strip() for a in self.banned_entry.get().split(",") if a.strip()]
        allowed = [a.strip() for a in self.allowed_entry.get().split(",") if a.strip()]

        print("Saving settings...")
        config_manager.save_settings(api_key, browsers, banned, allowed)
        print("Settings have been saved.")

    def on_cancel_button_press(self):
        """Handle cancel button press in settings."""
        print("Cancel button pressed!")
        self.apply_loaded_settings()
        print("UI changes reverted to last saved state.")

    def on_start_button_press(self):
        """Handle start button press."""
        if self.start_button.cget("text") == "Start":
            self.current_task = self.task_entry.get()
            if not self.current_task:
                print("Please enter a task first")
                return
                
            print("Task started:", self.current_task)
            self.monitoring_active = True
            self.last_check_time = 0
            self.last_activity = ""
            self.start_button.configure(text="Stop")
        else:
            self.monitoring_active = False
            self.start_button.configure(text="Start")

if __name__ == "__main__":
    config_manager.ensure_config_directory_exists()
    app = App()
    app.mainloop()
