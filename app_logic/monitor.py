import asyncio
import platform
import psutil

# Optional/conditional imports per OS
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

if IS_WINDOWS:
    import pygetwindow as gw
    import win32process
    import win32gui
elif IS_MAC:
    # pygetwindow on mac can be unreliable for frontmost process. Use Quartz/AppKit.
    from AppKit import NSWorkspace
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

class WindowMonitor:
    def __init__(self):
        self.previous_window_title = ""

    def get_process_name_from_hwnd(self, hwnd):
        """Get process name from window handle (Windows only)."""
        if not IS_WINDOWS:
            return None
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    def get_active_window_info(self):
        """Get both title and process name of the currently active window."""
        if IS_WINDOWS:
            active_window = gw.getActiveWindow()
            if not active_window:
                return None, None

            title = active_window.title
            hwnd = win32gui.GetForegroundWindow()
            process_name = self.get_process_name_from_hwnd(hwnd)
            return title, process_name

        if IS_MAC:
            try:
                # Frontmost application
                front_app = NSWorkspace.sharedWorkspace().frontmostApplication()
                app_name = str(front_app.localizedName()) if front_app else None

                # Inspect on-screen windows and find the one owned by the front app
                windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID) or []
                window_title = None
                process_name = app_name

                for win in windows:
                    owner = win.get('kCGWindowOwnerName')
                    name = win.get('kCGWindowName')
                    if owner and app_name and owner == app_name:
                        if name:
                            window_title = name
                            break

                # Fallbacks
                if window_title and process_name:
                    return window_title, process_name
                if window_title:
                    return window_title, None
                if process_name:
                    return process_name, process_name
                return None, None
            except Exception:
                return None, None

        # Unsupported platforms (e.g., Linux not yet implemented)
        return None, None

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
