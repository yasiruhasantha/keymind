import ast
import asyncio
import json
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

def detect_linux_backend():
    """
    Pick how to talk to the Linux desktop.
    Wayland has no generic protocol for reading other windows, so each supported
    compositor is driven through its own IPC; everything else falls back to X11.
    """
    if not IS_LINUX:
        return None
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') and shutil.which('hyprctl'):
        return 'hyprland'
    if os.environ.get('SWAYSOCK') and shutil.which('swaymsg'):
        return 'sway'
    if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland':
        # GNOME exposes nothing by itself; the Window Calls extension adds a DBus API.
        if gnome_window_calls_available():
            return 'gnome-window-calls'
        return 'wayland-unsupported'
    return 'x11'


GNOME_WINDOWS_DBUS = [
    '--session', '--dest', 'org.gnome.Shell',
    '--object-path', '/org/gnome/Shell/Extensions/Windows',
]


def _gdbus_call(method, *args):
    """Call a method on the Window Calls extension and return its unwrapped value."""
    if not shutil.which('gdbus'):
        return None
    command = ['gdbus', 'call'] + GNOME_WINDOWS_DBUS + [
        '--method', f'org.gnome.Shell.Extensions.Windows.{method}'
    ] + [str(arg) for arg in args]
    output = _run(command)
    if output is None:
        return None
    # gdbus prints a GVariant tuple, e.g. ("[{...}]",)
    try:
        value = ast.literal_eval(output.strip())
    except (ValueError, SyntaxError):
        return None
    if isinstance(value, tuple):
        # Methods such as Close return an empty tuple; report the call as successful.
        return value[0] if value else True
    return value


def gnome_window_calls_available():
    return _gdbus_call('List') is not None


def _run(command, timeout=2):
    """Run a helper command, returning stdout or None if it is unavailable/fails."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


class WindowMonitor:
    def __init__(self):
        self.previous_window_title = ""
        self._x_display = None
        self.linux_backend = detect_linux_backend()
        # Wayland ignores synthetic key presses, so pyautogui is not a usable fallback there.
        self.is_wayland = self.linux_backend in ('hyprland', 'sway', 'gnome-window-calls',
                                                 'wayland-unsupported')

        if self.linux_backend == 'wayland-unsupported':
            print("Warning: this Wayland compositor does not expose the active window to "
                  "other applications. Hyprland and sway work out of the box; on GNOME "
                  "install the 'Window Calls' extension "
                  "(https://extensions.gnome.org/extension/4724/window-calls/). "
                  "Otherwise log in to an X11/Xorg session.")
        elif self.linux_backend == 'x11' and xlib_display is None and not shutil.which('xdotool'):
            print("Warning: no way to read the active window. Install python-xlib "
                  "(pip install python-xlib) or xdotool.")

    def _get_active_window_hyprland(self):
        """Read the focused window from Hyprland's IPC (`hyprctl`)."""
        output = _run(['hyprctl', '-j', 'activewindow'])
        if not output:
            return {}
        try:
            window = json.loads(output)
        except json.JSONDecodeError:
            return {}
        return window if isinstance(window, dict) else {}

    def _get_active_window_info_hyprland(self):
        window = self._get_active_window_hyprland()
        if not window:
            return None, None

        title = window.get('title') or None
        process_name = window.get('class') or window.get('initialClass') or None
        pid = window.get('pid')
        if isinstance(pid, int) and pid > 0:
            try:
                process_name = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return title, process_name

    def _get_focused_window_gnome(self):
        """Return the focused window entry from the GNOME 'Window Calls' extension."""
        listing = _gdbus_call('List')
        if not isinstance(listing, str):
            return {}
        try:
            windows = json.loads(listing)
        except json.JSONDecodeError:
            return {}
        for window in windows if isinstance(windows, list) else []:
            if isinstance(window, dict) and window.get('focus'):
                return window
        return {}

    def _get_active_window_info_gnome(self):
        window = self._get_focused_window_gnome()
        if not window:
            return None, None

        title = None
        window_id = window.get('id')
        if window_id is not None:
            title = _gdbus_call('GetTitle', window_id) or None

        process_name = window.get('wm_class') or window.get('wm_class_instance') or None
        pid = window.get('pid')
        if isinstance(pid, int) and pid > 0:
            try:
                process_name = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        return title or process_name, process_name

    def _get_focused_node_sway(self):
        """Walk sway's tree and return the focused container."""
        output = _run(['swaymsg', '-t', 'get_tree'])
        if not output:
            return {}
        try:
            tree = json.loads(output)
        except json.JSONDecodeError:
            return {}

        stack = [tree]
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            if node.get('focused'):
                return node
            stack.extend(node.get('nodes', []) + node.get('floating_nodes', []))
        return {}

    def _get_active_window_info_sway(self):
        node = self._get_focused_node_sway()
        if not node:
            return None, None

        title = node.get('name') or None
        app_id = node.get('app_id')
        window_props = node.get('window_properties') or {}
        process_name = app_id or window_props.get('class') or None
        pid = node.get('pid')
        if isinstance(pid, int) and pid > 0:
            try:
                process_name = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return title, process_name

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
            try:
                disp.close()
            except Exception:
                pass
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
            if self.linux_backend == 'hyprland':
                return self._get_active_window_info_hyprland()
            if self.linux_backend == 'sway':
                return self._get_active_window_info_sway()
            if self.linux_backend == 'gnome-window-calls':
                return self._get_active_window_info_gnome()
            if self.linux_backend == 'x11':
                title, process_name = self._get_active_window_info_x11()
                if not title:
                    title, process_name = self._get_active_window_info_xdotool()
                return title, process_name
            return None, None

        return None, None

    def close_active_window(self, is_browser):
        """
        Close the active window, or just its current tab when it is a browser.
        Returns True if the close was dispatched through a compositor, False when the
        caller should fall back to synthetic key presses (pyautogui).
        """
        if self.linux_backend == 'hyprland':
            if is_browser:
                # Hyprland can inject the shortcut straight into the focused window.
                return (_run(['hyprctl', 'dispatch', 'sendshortcut', 'CTRL,W,activewindow']) is not None
                        and _run(['hyprctl', 'dispatch', 'sendshortcut', 'CTRL,T,activewindow']) is not None)
            address = self._get_active_window_hyprland().get('address')
            if not address:
                return False
            return _run(['hyprctl', 'dispatch', 'closewindow', f'address:{address}']) is not None

        if self.linux_backend == 'sway':
            if is_browser:
                if shutil.which('wtype'):
                    return (_run(['wtype', '-M', 'ctrl', '-k', 'w', '-m', 'ctrl']) is not None
                            and _run(['wtype', '-M', 'ctrl', '-k', 't', '-m', 'ctrl']) is not None)
                print("Cannot close browser tabs on sway without wtype installed.")
                return False
            return _run(['swaymsg', 'kill']) is not None

        if self.linux_backend == 'gnome-window-calls':
            if is_browser:
                # The extension cannot type; tab closing needs a uinput-based key injector.
                if shutil.which('ydotool'):
                    return (_run(['ydotool', 'key', 'ctrl+w']) is not None
                            and _run(['ydotool', 'key', 'ctrl+t']) is not None)
                print("Cannot close browser tabs on GNOME Wayland without ydotool installed; "
                      "leaving the browser open.")
                return False
            window_id = self._get_focused_window_gnome().get('id')
            if window_id is None:
                return False
            return _gdbus_call('Close', window_id) is not None

        return False

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
