"""Where things live on disk: bundled resources, settings, screenshots."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from visualcommand import APP_NAME


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_path(relative: str) -> Path:
    """Path to a file shipped with the app (inside the PyInstaller bundle when frozen)."""
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / relative


def model_path() -> Path:
    return resource_path("models/gesture_recognizer.task")


def app_data_dir() -> Path:
    """%APPDATA%\\VisualCommand: holds config.json and the text log, nothing else."""
    root = os.environ.get("APPDATA") or str(Path.home())
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _known_folder(guid: str) -> Path | None:
    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    try:
        g = GUID()
        ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid), ctypes.byref(g))
        out = ctypes.c_wchar_p()
        ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out))
        value = out.value
        ctypes.windll.ole32.CoTaskMemFree(out)
        return Path(value) if value else None
    except Exception:
        return None


def screenshots_dir() -> Path:
    """Pictures\\VisualCommand (follows OneDrive/known-folder redirection)."""
    pictures = _known_folder("{33E28130-4E1E-4676-835A-98395C3BC3BB}") or Path.home() / "Pictures"
    path = pictures / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
