import customtkinter as ctk
import config_manager
from app_logic import WindowMonitor
import time
import threading
import platform

# How often the active window is polled, and how long an activity has to stay focused
# before it is judged (avoids closing windows the user only passed through).
POLL_INTERVAL_MS = 300
ACTIVITY_GRACE_SECONDS = 5

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
        self.current_active_window_title = ""
        self.activity_started_at = 0.0
        self.activity_checked = True
        self.monitoring_active = False
        self.current_task = ""
        # Remembers the verdict per activity so the AI is asked once per window title.
        self.verdicts = {}

        self.setup_home_tab()
        self.setup_settings_tab()
        self.apply_loaded_settings()

        # Start monitoring
        self.update_window_title()

        # Set up window close handler
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_window_title(self):
        """Poll the active window and judge it once it has been focused long enough."""
        title = self.window_monitor.get_active_window_title()

        if title != self.current_active_window_title:
            self.current_active_window_title = title
            self.active_window_display_label.configure(text=title or self.no_activity_text())
            self.activity_started_at = time.time()
            # A brand new activity always gets judged again, even if we saw it before.
            self.activity_checked = title is None

        backend_text = f"Watching windows via: {self.window_monitor.describe_backend()}"
        if self.backend_label.cget("text") != backend_text:
            self.backend_label.configure(text=backend_text)

        if (self.monitoring_active and title and not self.activity_checked
                and time.time() - self.activity_started_at >= ACTIVITY_GRACE_SECONDS):
            self.activity_checked = True
            self.evaluate_activity(title)

        self.after(POLL_INTERVAL_MS, self.update_window_title)

    def no_activity_text(self):
        """Message shown when the desktop does not tell us what is focused."""
        if self.window_monitor.linux_backend == 'wayland-unsupported':
            return ("Cannot read the active window on this Wayland compositor.\n"
                    "Install the GNOME 'Window Calls' extension, or use Hyprland, sway or Xorg.")
        return "No active window detected"

    def evaluate_activity(self, title):
        """Decide whether the focused activity is allowed, and close it if it is not."""
        from app_logic.task_checker import check_relevance

        if self.window_monitor.is_own_window():
            return

        settings = config_manager.load_settings()
        title_lower = title.lower()

        # Banned wins over allowed: the allowed list holds broad desktop-shell terms that
        # would otherwise whitelist a banned app whose title happens to contain one.
        if any(banned.lower() in title_lower for banned in settings.get('banned', [])):
            print(f"Relevance check: {title} - Not relevant (in banned list)")
            self.verdicts[title] = False
            self._close_activity(title)
            return

        if any(allowed.lower() in title_lower for allowed in settings.get('allowed', [])):
            print(f"Relevance check: {title} - Relevant (in allowed list)")
            return

        cached = self.verdicts.get(title)
        if cached is not None:
            # A cached "not relevant" is re-applied in case the previous close failed.
            print(f"Relevance check: {title} - {'Relevant' if cached else 'Not relevant'} (cached)")
            if not cached:
                self._close_activity(title)
            return

        # Run the AI call in a background thread to keep the UI responsive.
        def run_ai_check(task, activity):
            result = check_relevance(task, activity)

            def apply_result():
                if result is None:
                    return
                self.verdicts[activity] = result == 1
                print(f"Relevance check: {activity} - "
                      f"{'Relevant' if result == 1 else 'Not relevant'} (AI decision)")
                if result == 0 and self.current_active_window_title == activity:
                    self._close_activity(activity)
            self.after(0, apply_result)

        threading.Thread(target=run_ai_check, args=(self.current_task, title), daemon=True).start()

    def _close_activity(self, title):
        """Close current activity with platform-aware shortcuts."""
        title_lower = title.lower()
        settings = config_manager.load_settings()
        browsers = settings.get('browsers', [])
        is_browser = any(browser.lower() in title_lower for browser in browsers)
        what = 'browser tab' if is_browser else 'application'

        # Wayland compositors ignore synthetic key presses, so let the monitor try
        # its own IPC first and only fall back to pyautogui when it declines.
        if self.window_monitor.close_active_window(is_browser):
            print(f"Closed {what}: {title}")
            return

        if self.window_monitor.is_wayland:
            print(f"Could not close {what}: {title}")
            self._retry_activity_later()
            return

        # pyautogui needs a display server and is only imported on the fallback path,
        # so a headless/Wayland session cannot break compositor-driven closing.
        try:
            import pyautogui
        except Exception as error:
            print(f"Could not close {what}: {error}")
            self._retry_activity_later()
            return
        pyautogui.PAUSE = 0.5

        is_mac = platform.system() == 'Darwin'
        print(f"Closing {what}: {title}")
        if is_browser:
            if is_mac:
                pyautogui.hotkey('command', 'w')
                pyautogui.hotkey('command', 't')
            else:
                pyautogui.hotkey('ctrl', 'w')
                pyautogui.hotkey('ctrl', 't')
        elif is_mac:
            pyautogui.hotkey('command', 'w')
        else:
            pyautogui.hotkey('alt', 'f4')

    def _retry_activity_later(self):
        """Re-judge the current activity after the grace period if closing failed."""
        self.activity_checked = False
        self.activity_started_at = time.time()

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
        home_frame.grid_rowconfigure(4, weight=0)
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
        self.active_window_display_label.grid(row=3, column=0, pady=(50, 10))

        # Which desktop integration is in use; the main thing to know when nothing
        # is being detected.
        self.backend_label = ctk.CTkLabel(
            home_frame,
            text=f"Watching windows via: {self.window_monitor.describe_backend()}",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.backend_label.grid(row=4, column=0, pady=(0, 20))

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
            self.verdicts = {}
            self.activity_started_at = time.time()
            self.activity_checked = self.current_active_window_title is None
            self.start_button.configure(text="Stop")
        else:
            self.monitoring_active = False
            self.start_button.configure(text="Start")

if __name__ == "__main__":
    config_manager.ensure_config_directory_exists()
    app = App()
    app.mainloop()
