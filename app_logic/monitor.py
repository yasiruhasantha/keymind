import asyncio
import pygetwindow as gw

class WindowMonitor:
    def __init__(self):
        self.previous_window_title = ""

    def get_active_window_title(self):
        """Get the title of the currently active window."""
        active_window = gw.getActiveWindow()
        return active_window.title if active_window else None

    async def monitor_active_window(self, task):
        """Main window monitoring loop."""
        while True:
            current_window_title = self.get_active_window_title()

            if current_window_title and current_window_title != self.previous_window_title:
                print(f"Active window: {current_window_title}")
                self.previous_window_title = current_window_title

            await asyncio.sleep(1)
