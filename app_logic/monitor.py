import asyncio
import os
import platform
import shutil
import subprocess
import psutil

# Optional/conditional imports per OS
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    import pygetwindow as gw
    import win32process
    import win32gui
elif IS_MAC:
    # pygetwindow on mac can be unreliable for frontmost process. Use Quartz/AppKit.
    from AppKit import NSWorkspace
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
elif IS_LINUX:
    try:
        from Xlib import display as xlib_display
    except ImportError:
        xlib_display = None

class WindowMonitor:
    def __init__(self):
        self.previous_window_title = ""
        self._x_display = None

        if IS_LINUX:
            if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland':
                print("Warning: Wayland sessions do not expose the active window to other "
                      "applications. Log in to an X11/Xorg session for KeyMind to work.")
            elif xlib_display is None and not shutil.which('xdotool'):
                print("Warning: no way to read the active window. Install python-xlib "
                      "(pip install python-xlib) or xdotool.")

    def _get_x_display(self):
        """Open (and cache) a connection to the X server."""
        if not IS_LINUX or xlib_display is None:
            return None
        if self._x_display is None:
            try:
                self._x_display = xlib_display.Display()
            except Exception:
                return None
        return self._x_display

    def _get_active_window_info_x11(self):
        """Read the active window title/process from X11 EWMH properties."""
        disp = self._get_x_display()
        if disp is None:
            return None, None

        try:
            root = disp.screen().root
            active_atom = disp.intern_atom('_NET_ACTIVE_WINDOW')
            active = root.get_full_property(active_atom, 0)
            if not active or not active.value:
                return None, None

            window = disp.create_resource_object('window', active.value[0])

            title = None
            name_atom = disp.intern_atom('_NET_WM_NAME')
            utf8_atom = disp.intern_atom('UTF8_STRING')
            name = window.get_full_property(name_atom, utf8_atom)
            if name and name.value:
                title = name.value.decode('utf-8', 'replace') if isinstance(name.value, bytes) else str(name.value)
            else:
                legacy = window.get_wm_name()
                if legacy:
                    title = legacy.decode('utf-8', 'replace') if isinstance(legacy, bytes) else str(legacy)

            process_name = None
            pid_atom = disp.intern_atom('_NET_WM_PID')
            pid_prop = window.get_full_property(pid_atom, 0)
            if pid_prop and pid_prop.value:
                try:
                    process_name = psutil.Process(int(pid_prop.value[0])).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    process_name = None
            if not process_name:
                wm_class = window.get_wm_class()
                if wm_class:
                    process_name = wm_class[-1]

            return title, process_name
        except Exception:
            # The window may disappear between the two calls, or the connection may drop.
            self._x_display = None
            return None, None

    def _get_active_window_info_xdotool(self):
        """Fallback for Linux systems without python-xlib but with xdotool installed."""
        if not shutil.which('xdotool'):
            return None, None
        try:
            window_id = subprocess.run(
                ['xdotool', 'getactivewindow'],
                capture_output=True, text=True, timeout=2, check=True
            ).stdout.strip()

            title = subprocess.run(
                ['xdotool', 'getwindowname', window_id],
                capture_output=True, text=True, timeout=2, check=True
            ).stdout.strip() or None

            process_name = None
            pid_result = subprocess.run(
                ['xdotool', 'getwindowpid', window_id],
                capture_output=True, text=True, timeout=2
            )
            if pid_result.returncode == 0 and pid_result.stdout.strip():
                try:
                    process_name = psutil.Process(int(pid_result.stdout.strip())).name()
                except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    process_name = None

            return title, process_name
        except (subprocess.SubprocessError, OSError):
            return None, None

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

        if IS_LINUX:
            title, process_name = self._get_active_window_info_x11()
            if not title:
                title, process_name = self._get_active_window_info_xdotool()
            return title, process_name

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
