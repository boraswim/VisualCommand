"""Windows plumbing: single instance, "show window" signal, lock detection, autostart."""
from __future__ import annotations

import ctypes
import sys
import winreg
from ctypes import wintypes
from pathlib import Path

from visualcommand import APP_NAME
from visualcommand.paths import is_frozen

MUTEX_NAME = "VisualCommandSingleInstanceMutex"   # also used by the installer (AppMutex)
SHOW_EVENT_NAME = "VisualCommandShowWindowEvent"

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32 = ctypes.WinDLL("user32", use_last_error=True)

_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
_k32.CreateEventW.restype = wintypes.HANDLE
_k32.CreateEventW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
_k32.OpenEventW.restype = wintypes.HANDLE
_k32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
_k32.SetEvent.argtypes = (wintypes.HANDLE,)
_k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
_k32.WaitForSingleObject.restype = wintypes.DWORD
_k32.CloseHandle.argtypes = (wintypes.HANDLE,)
_u32.OpenInputDesktop.restype = wintypes.HANDLE
_u32.OpenInputDesktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_u32.SwitchDesktop.argtypes = (wintypes.HANDLE,)
_u32.CloseDesktop.argtypes = (wintypes.HANDLE,)

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0


class SingleInstance:
    """Holds the app mutex. `primary` is False when another copy is already running."""

    def __init__(self) -> None:
        self._mutex = _k32.CreateMutexW(None, False, MUTEX_NAME)
        self.primary = ctypes.get_last_error() != ERROR_ALREADY_EXISTS
        self._event = _k32.CreateEventW(None, False, False, SHOW_EVENT_NAME) if self.primary else None

    def signal_primary(self) -> None:
        """Ask the running copy to show its window."""
        h = _k32.OpenEventW(EVENT_MODIFY_STATE, False, SHOW_EVENT_NAME)
        if h:
            _k32.SetEvent(h)
            _k32.CloseHandle(h)

    def wait_show(self, timeout_ms: int) -> bool:
        return bool(self._event) and _k32.WaitForSingleObject(self._event, timeout_ms) == WAIT_OBJECT_0


def session_locked() -> bool:
    """True while the workstation is locked (the input desktop isn't ours)."""
    DESKTOP_SWITCHDESKTOP = 0x0100
    h = _u32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not h:
        return True
    ok = _u32.SwitchDesktop(h)
    _u32.CloseDesktop(h)
    return not ok


def set_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# --- Start with Windows (HKCU Run key is the single source of truth) -------------

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command() -> str:
    if is_frozen():
        return f'"{sys.executable}" --tray'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{exe}" -m visualcommand --tray'


def autostart_value() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, APP_NAME)[0]
    except OSError:
        return None


def autostart_enabled() -> bool:
    return autostart_value() is not None


def set_autostart(enabled: bool) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def repair_autostart() -> None:
    """If autostart is on but points somewhere else (app moved / upgraded), fix the path."""
    value = autostart_value()
    if value is not None and value != autostart_command():
        set_autostart(True)
