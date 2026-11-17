"""System actions: screenshot, lock, display, desktop, run a command, app control."""
from __future__ import annotations

import ctypes
import os
import subprocess
from datetime import datetime
from pathlib import Path

from visualcommand.actions.base import ActionResult, Param, register_action
from visualcommand.actions.keys import press
from visualcommand.paths import screenshots_dir


def primary_monitor(monitors: list[dict]) -> dict:
    """The main display from mss's monitor list.

    monitors[0] is the whole virtual desktop (all screens); the rest are single
    displays. Prefer the one mss marks as primary; otherwise the one at (0, 0),
    which is where Windows always puts the primary display.
    """
    screens = monitors[1:] or monitors
    for m in screens:
        if m.get("is_primary"):
            return m
    for m in screens:
        if m.get("left") == 0 and m.get("top") == 0:
            return m
    return screens[0]


@register_action("screenshot", "Take screenshot",
                 "Saves your main display as a PNG in Pictures\\VisualCommand.", "System",
                 order=10)
def screenshot(ctx, params):
    import mss
    import mss.tools

    if hasattr(ctx, "hide_popups"):
        ctx.hide_popups()          # don't capture our own previous popup
    path = screenshots_dir() / f"Screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}.png"
    open_mss = getattr(mss, "MSS", None) or mss.mss   # mss.mss is deprecated in newer mss
    with open_mss() as sct:
        shot = sct.grab(primary_monitor(sct.monitors))
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))
    # Clicking the popup opens the folder with this screenshot selected.
    return ActionResult(f"Screenshot saved: {path.name}", reveal=path)


def reveal_in_explorer(path) -> None:
    """Open the folder containing `path` with the file selected (folder only if the
    file is gone)."""
    path = Path(path)
    if path.exists():
        subprocess.Popen(["explorer", f"/select,{path}"])
    elif path.parent.exists():
        os.startfile(path.parent)


@register_action("lock_pc", "Lock PC", "Locks Windows (same as Win+L).", "System", order=11)
def lock_pc(ctx, params):
    ctypes.windll.user32.LockWorkStation()
    return None


@register_action("display_off", "Turn display off", "Puts the monitors to sleep.", "System", order=12)
def display_off(ctx, params):
    HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER = 0xFFFF, 0x0112, 0xF170
    ctypes.windll.user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)
    return None


@register_action("show_desktop", "Show desktop", "Minimise / restore all windows (Win+D).",
                 "System", order=13)
def show_desktop(ctx, params):
    press("win", "d")
    return None


@register_action("task_view", "Task view", "Open Task View (Win+Tab).", "System", order=14)
def task_view(ctx, params):
    press("win", "tab")
    return None


@register_action("open_screenshots", "Open screenshots folder", "", "System", order=15)
def open_screenshots(ctx, params):
    os.startfile(screenshots_dir())
    return None


@register_action("run_command", "Open app / file / command…",
                 "Runs whatever you type: a program path, a file, a URL or a shell command.",
                 "System", params=(Param("command", "Command", r"notepad.exe"),), order=16)
def run_command(ctx, params):
    cmd = (params.get("command") or "").strip()
    if not cmd:
        return "No command set for this gesture"
    try:
        os.startfile(cmd)
    except OSError:
        subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return f"Ran: {cmd}"


@register_action("pause_tracking", "Pause tracking for 10 minutes",
                 "Releases the camera for 10 minutes.", "VisualCommand", order=90)
def pause_tracking(ctx, params):
    ctx.pause(minutes=10)
    return "Tracking paused for 10 minutes"
