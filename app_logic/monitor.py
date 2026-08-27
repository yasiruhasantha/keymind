import ast
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import time
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
else:
    xlib_display = None
    if IS_LINUX:
        try:
            from Xlib import display as xlib_display
        except ImportError:
            xlib_display = None

_warned = set()


def _warn_once(message):
    """Print a diagnostic once so the log stays readable during the polling loop."""
    if message not in _warned:
        _warned.add(message)
        print(f"KeyMind: {message}", flush=True)


# PyInstaller points the dynamic loader at its own bundled libraries; system helpers
# such as hyprctl or gdbus then load the wrong libc/libstdc++ and fail to start.
_LOADER_VARS = ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'DYLD_LIBRARY_PATH',
                'DYLD_INSERT_LIBRARIES', 'DYLD_FRAMEWORK_PATH')


def _subprocess_env():
    """Environment for helper commands, with the PyInstaller loader overrides undone."""
    env = dict(os.environ)
    if getattr(sys, 'frozen', False):
        for var in _LOADER_VARS:
            original = env.pop(f'{var}_ORIG', None)
            if original:
                env[var] = original
            else:
                env.pop(var, None)
    return env


def is_wayland_session():
    return (os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland'
            or bool(os.environ.get('WAYLAND_DISPLAY')))


def hyprland_available():
    """Hyprland is usable when hyprctl can actually answer a query."""
    return shutil.which('hyprctl') is not None and _run(['hyprctl', '-j', 'activewindow']) is not None


def sway_available():
    return shutil.which('swaymsg') is not None and _run(['swaymsg', '-t', 'get_version']) is not None


def x11_available():
    if not os.environ.get('DISPLAY'):
        return False
    if xlib_display is not None:
        try:
            xlib_display.Display().close()
            return True
        except Exception:
            pass
    return shutil.which('xdotool') is not None


def detect_linux_backend():
    """
    Pick how to talk to the Linux desktop.
    Wayland has no generic protocol for reading other windows, so each supported
    compositor is driven through its own IPC; everything else falls back to X11.
    Detection probes the tools instead of trusting environment variables, which are
    often missing when the app is started from a launcher or a systemd unit.
    """
    if not IS_LINUX:
        return None
    if hyprland_available():
        return 'hyprland'
    if sway_available():
        return 'sway'
    if is_wayland_session():
        # GNOME exposes nothing by itself; the Window Calls extension adds a DBus API.
        # XWayland is usually reachable too, but it only ever sees X11 clients.
        if gnome_window_calls_available():
            return 'gnome-window-calls'
        return 'wayland-unsupported'
    return 'x11'


BACKEND_LABELS = {
    'hyprland': 'Hyprland (hyprctl)',
    'sway': 'sway (swaymsg)',
    'gnome-window-calls': 'GNOME Wayland (Window Calls extension)',
    'x11': 'X11',
    'wayland-unsupported': 'Wayland (unsupported compositor)',
}


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
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                                env=_subprocess_env())
    except (subprocess.SubprocessError, OSError) as error:
        _warn_once(f"could not run {command[0]}: {error}")
        return None
    if result.returncode != 0:
        _warn_once(f"{command[0]} failed ({result.returncode}): {result.stderr.strip()}")
        return None
    return result.stdout


def _hyprctl_dispatch(*arguments):
    """Run a hyprctl dispatcher; hyprctl still exits 0 when it rejects the command."""
    output = _run(['hyprctl', 'dispatch', *arguments])
    if output is None:
        return False
    if not output.strip().lower().startswith('ok'):
        _warn_once(f"hyprctl dispatch {' '.join(arguments)}: {output.strip()}")
        return False
    return True


# How long to keep a failing Linux backend before probing the desktop again.
BACKEND_RECHECK_SECONDS = 15


class WindowMonitor:
    def __init__(self):
        self.previous_window_title = ""
        self._x_display = None
        self._backend_detected_at = time.monotonic()
        self.own_pid = os.getpid()
        self.active_window_pid = None
        self.linux_backend = detect_linux_backend()
        self._report_backend()

    @property
    def is_wayland(self):
        """Wayland ignores synthetic key presses, so pyautogui is not a usable fallback."""
        return self.linux_backend in ('hyprland', 'sway', 'gnome-window-calls',
                                      'wayland-unsupported')

    def describe_backend(self):
        """Short human-readable description of how windows are being read."""
        if not IS_LINUX:
            return platform.system()
        return BACKEND_LABELS.get(self.linux_backend, self.linux_backend or 'unknown')

    def _report_backend(self):
        if not IS_LINUX:
            return
        _warn_once(f"window backend: {self.describe_backend()}")
        if self.linux_backend == 'wayland-unsupported':
            _warn_once("this Wayland compositor does not expose the active window to other "
                       "applications. Hyprland and sway work out of the box; on GNOME install "
                       "the 'Window Calls' extension "
                       "(https://extensions.gnome.org/extension/4724/window-calls/). "
                       "Otherwise log in to an X11/Xorg session.")
        elif self.linux_backend == 'x11' and xlib_display is None and not shutil.which('xdotool'):
            _warn_once("no way to read the active window. Install python-xlib "
                       "(pip install python-xlib) or xdotool.")

    def _redetect_backend(self):
        """Re-probe the desktop; compositor IPC is often not ready when the app starts."""
        self._backend_detected_at = time.monotonic()
        backend = detect_linux_backend()
        if backend != self.linux_backend:
            self.linux_backend = backend
            self._report_backend()
            return True
        return False

    def _resolve_pid(self, pid, fallback_name):
        """Remember the focused window's pid and prefer its real process name."""
        if not isinstance(pid, int) or pid <= 0:
            self.active_window_pid = None
            return fallback_name
        self.active_window_pid = pid
        try:
            return psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return fallback_name

    def is_own_window(self):
        """True when the focused window belongs to KeyMind itself."""
        return self.active_window_pid is not None and self.active_window_pid == self.own_pid

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
        fallback = window.get('class') or window.get('initialClass') or None
        process_name = self._resolve_pid(window.get('pid'), fallback)
        return title or process_name, process_name

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

        fallback = window.get('wm_class') or window.get('wm_class_instance') or None
        process_name = self._resolve_pid(window.get('pid'), fallback)
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
        window_props = node.get('window_properties') or {}
        fallback = node.get('app_id') or window_props.get('class') or None
        process_name = self._resolve_pid(node.get('pid'), fallback)
        return title or process_name, process_name

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

            wm_class = window.get_wm_class()
            fallback = wm_class[-1] if wm_class else None

            pid_atom = disp.intern_atom('_NET_WM_PID')
            pid_prop = window.get_full_property(pid_atom, 0)
            pid = int(pid_prop.value[0]) if pid_prop and pid_prop.value else None
            process_name = self._resolve_pid(pid, fallback)

            return title or process_name, process_name
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
                capture_output=True, text=True, timeout=2, check=True, env=_subprocess_env()
            ).stdout.strip()

            title = subprocess.run(
                ['xdotool', 'getwindowname', window_id],
                capture_output=True, text=True, timeout=2, check=True, env=_subprocess_env()
            ).stdout.strip() or None

            pid = None
            pid_result = subprocess.run(
                ['xdotool', 'getwindowpid', window_id],
                capture_output=True, text=True, timeout=2, env=_subprocess_env()
            )
            if pid_result.returncode == 0 and pid_result.stdout.strip():
                try:
                    pid = int(pid_result.stdout.strip())
                except ValueError:
                    pid = None
            process_name = self._resolve_pid(pid, None)

            return title or process_name, process_name
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
            try:
                _, self.active_window_pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                self.active_window_pid = None
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
            title, process_name = self._get_active_window_info_linux()
            if title:
                return title, process_name
            # Compositor IPC is often not ready yet when the app starts, and the session
            # can change under us, so re-probe instead of staying broken forever.
            if time.monotonic() - self._backend_detected_at >= BACKEND_RECHECK_SECONDS:
                if self._redetect_backend():
                    return self._get_active_window_info_linux()
            return None, None

        return None, None

    def _get_active_window_info_linux(self):
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

    def _active_window_id_x11(self):
        """Numeric X window id of the focused window, or None."""
        disp = self._get_x_display()
        if disp is not None:
            try:
                active = disp.screen().root.get_full_property(
                    disp.intern_atom('_NET_ACTIVE_WINDOW'), 0)
                if active and active.value:
                    return int(active.value[0])
            except Exception:
                pass
        output = _run(['xdotool', 'getactivewindow'])
        if output and output.strip().isdigit():
            return int(output.strip())
        return None

    def _close_active_window_x11(self, is_browser):
        """Close through xdotool so the packaged build does not depend on pyautogui."""
        if not shutil.which('xdotool'):
            return False
        if is_browser:
            # XTEST goes to whatever is focused; browsers ignore synthetic events that
            # are addressed to a specific window id.
            return (_run(['xdotool', 'key', '--clearmodifiers', 'ctrl+w']) is not None
                    and _run(['xdotool', 'key', '--clearmodifiers', 'ctrl+t']) is not None)
        window_id = self._active_window_id_x11()
        if window_id is None:
            return False
        return _run(['xdotool', 'windowclose', str(window_id)]) is not None

    def terminate_active_process(self):
        """
        Last resort when no window manager could close the window: ask the process
        behind it to quit.
        """
        pid = self.active_window_pid
        if not pid or pid <= 1 or pid == self.own_pid:
            return False
        try:
            psutil.Process(pid).terminate()
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as error:
            _warn_once(f"could not terminate pid {pid}: {error}")
            return False

    def close_active_window(self, is_browser):
        """
        Close the active window, or just its current tab when it is a browser.
        Returns True if the close was dispatched, False when the caller should fall back
        to synthetic key presses or to terminating the process.
        """
        if self.is_own_window():
            # Never let KeyMind close its own window.
            return False

        if self.linux_backend == 'x11':
            return self._close_active_window_x11(is_browser)

        if self.linux_backend == 'hyprland':
            address = self._get_active_window_hyprland().get('address')
            if not address:
                _warn_once("hyprctl did not report an address for the focused window")
                return False
            if is_browser:
                # Hyprland can inject the shortcut straight into the window; addressing it
                # explicitly also works on versions without the `activewindow` target.
                if (_hyprctl_dispatch('sendshortcut', f'CTRL,W,address:{address}')
                        and _hyprctl_dispatch('sendshortcut', f'CTRL,T,address:{address}')):
                    return True
                # sendshortcut is missing on older Hyprland versions; the window itself can
                # still be closed.
                _warn_once("closing the whole browser window: hyprctl could not send the "
                           "tab-close shortcut")
            return _hyprctl_dispatch('closewindow', f'address:{address}')

        if self.linux_backend == 'sway':
            if is_browser:
                if shutil.which('wtype'):
                    return (_run(['wtype', '-M', 'ctrl', '-k', 'w', '-m', 'ctrl']) is not None
                            and _run(['wtype', '-M', 'ctrl', '-k', 't', '-m', 'ctrl']) is not None)
                # Without a key injector a single tab cannot be singled out, so the whole
                # browser window goes rather than leaving the distraction open.
                _warn_once("closing the whole browser window: closing one tab on sway needs "
                           "wtype (https://github.com/atx/wtype)")
            return _run(['swaymsg', 'kill']) is not None

        if self.linux_backend == 'gnome-window-calls':
            if is_browser:
                # The extension cannot type; tab closing needs a uinput-based key injector.
                if shutil.which('ydotool'):
                    return (_run(['ydotool', 'key', 'ctrl+w']) is not None
                            and _run(['ydotool', 'key', 'ctrl+t']) is not None)
                _warn_once("closing the whole browser window: closing one tab on GNOME "
                           "Wayland needs ydotool (https://github.com/ReimuNotMoe/ydotool)")
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
