"""Tiny keyboard helper: send virtual-key presses with keybd_event (no extra deps)."""
from __future__ import annotations

import ctypes
import time

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

VK = {
    "win": 0x5B, "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "tab": 0x09,
    "d": 0x44, "volume_mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
    "media_next": 0xB0, "media_prev": 0xB1, "media_stop": 0xB2, "media_play_pause": 0xB3,
}
_EXTENDED = {0x5B, 0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2, 0xB3}


def _event(vk: int, up: bool) -> None:
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED else 0)
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)


def press(*names: str) -> None:
    """Press a key combo, e.g. press("win", "d")."""
    codes = [VK[n] for n in names]
    for c in codes:
        _event(c, up=False)
    time.sleep(0.02)
    for c in reversed(codes):
        _event(c, up=True)
