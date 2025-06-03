import asyncio
import pygetwindow as gw
import psutil
import win32process
import win32gui

class WindowMonitor:
    def __init__(self):
        self.previous_window_title = ""

    def get_process_name_from_hwnd(self, hwnd):
        """Get process name from window handle."""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    def get_active_window_info(self):
        """Get both title and process name of the currently active window."""
        active_window = gw.getActiveWindow()
        if not active_window:
            return None, None

        # Get window title
        title = active_window.title

        # Get process name
        hwnd = win32gui.GetForegroundWindow()
        process_name = self.get_process_name_from_hwnd(hwnd)
        
        return title, process_name

    def get_active_window_title(self):
        """Get the combined title and process name of the currently active window."""
        title, process_name = self.get_active_window_info()
        if not title:
            return None

        # If title doesn't contain process name, add it
        if process_name and process_name.lower() not in title.lower():
            return f"{title} - {process_name}"
        return title

    async def monitor_active_window(self, task):
        """Main window monitoring loop."""
        while True:
            current_window_title = self.get_active_window_title()

            if current_window_title and current_window_title != self.previous_window_title:
                print(f"Active window: {current_window_title}")
                self.previous_window_title = current_window_title

            await asyncio.sleep(1)
