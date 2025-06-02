import customtkinter as ctk
import config_manager
from app_logic import WindowMonitor

# --- Appearance Settings ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("KeyMind UI - Focus Assistant")
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
        """Update the displayed window title."""
        title = self.window_monitor.get_active_window_title()
        if title and title != self.current_active_window_title:
            self.current_active_window_title = title
            self.active_window_display_label.configure(text=title)
        self.after(200, self.update_window_title)

    def apply_loaded_settings(self):
        """Loads settings using config_manager and applies them to the UI."""
        print("Loading settings into UI...")
        loaded_config = config_manager.load_settings()

        self.api_key_entry.delete(0, "end")
        self.api_key_entry.insert(0, loaded_config.get("api_key", ""))

        browsers_config = loaded_config.get("web_browsers", {})
        for browser, checkbox in [
            ("chrome", self.chrome_checkbox),
            ("opera", self.opera_checkbox),
            ("firefox", self.firefox_checkbox)
        ]:
            if browsers_config.get(browser, True):
                checkbox.select()
            else:
                checkbox.deselect()
        print("Settings applied to UI.")

    def on_closing(self):
        """Handles application close events."""
        print("Closing application...")
        self.destroy()

    def setup_home_tab(self):
        home_frame = self.tab_view.tab("home")
        home_frame.grid_rowconfigure(0, weight=1)
        home_frame.grid_rowconfigure(1, weight=0)
        home_frame.grid_rowconfigure(2, weight=1)
        home_frame.grid_columnconfigure(0, weight=1)

        self.active_window_display_label = ctk.CTkLabel(
            home_frame, 
            text=self.current_active_window_title, 
            font=ctk.CTkFont(size=20, weight="bold"),
            wraplength=500
        )
        self.active_window_display_label.grid(row=0, column=0, pady=(150, 20), padx=20, sticky="s")

    def setup_settings_tab(self):
        settings_frame = self.tab_view.tab("settings")
        settings_frame.grid_columnconfigure(0, weight=0)
        settings_frame.grid_columnconfigure(1, weight=1)

        # API Key Section
        api_key_label = ctk.CTkLabel(settings_frame, text="Gemini API Key", anchor="w")
        api_key_label.grid(row=0, column=0, padx=(20,10), pady=20, sticky="w")

        self.api_key_entry = ctk.CTkEntry(settings_frame, placeholder_text="Enter your API key", width=350)
        self.api_key_entry.grid(row=0, column=1, padx=(0,20), pady=20, sticky="ew")

        # Web Browsers Section
        web_browser_label = ctk.CTkLabel(
            settings_frame,
            text="Web Browsers",
            anchor="w",
            font=ctk.CTkFont(weight="bold")
        )
        web_browser_label.grid(row=1, column=0, columnspan=2, padx=20, pady=(10,5), sticky="w")

        self.chrome_checkbox = ctk.CTkCheckBox(settings_frame, text="Chrome")
        self.chrome_checkbox.grid(row=2, column=0, columnspan=2, padx=30, pady=5, sticky="w")

        self.opera_checkbox = ctk.CTkCheckBox(settings_frame, text="Opera")
        self.opera_checkbox.grid(row=3, column=0, columnspan=2, padx=30, pady=5, sticky="w")

        self.firefox_checkbox = ctk.CTkCheckBox(settings_frame, text="Firefox")
        self.firefox_checkbox.grid(row=4, column=0, columnspan=2, padx=30, pady=5, sticky="w")

        # Spacer and Buttons
        spacer_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        spacer_frame.grid(row=5, column=0, columnspan=2, sticky="nsew")
        settings_frame.grid_rowconfigure(5, weight=1)

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
        api_key = self.api_key_entry.get()
        chrome_selected = bool(self.chrome_checkbox.get())
        opera_selected = bool(self.opera_checkbox.get())
        firefox_selected = bool(self.firefox_checkbox.get())

        print("Saving settings...")
        config_manager.save_settings(api_key, chrome_selected, opera_selected, firefox_selected)
        print("Settings have been saved.")

    def on_cancel_button_press(self):
        """Handle cancel button press in settings."""
        print("Cancel button pressed!")
        self.apply_loaded_settings()
        print("UI changes reverted to last saved state.")

if __name__ == "__main__":
    config_manager.ensure_config_directory_exists()
    app = App()
    app.mainloop()
