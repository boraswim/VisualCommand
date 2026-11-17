"""System actions: screenshot, lock, display, desktop, run a command, app control."""
from __future__ import annotations

import ctypes
import os
import subprocess
from datetime import datetime

from visualcommand.actions.base import Param, register_action
from visualcommand.actions.keys import press
from visualcommand.paths import screenshots_dir


@register_action("screenshot", "Take screenshot",
                 "Saves all monitors as a PNG in Pictures\\VisualCommand.", "System", order=10)
def screenshot(ctx, params):
    import mss
    import mss.tools

    if hasattr(ctx, "hide_popups"):
        ctx.hide_popups()          # don't capture our own previous popup
    path = screenshots_dir() / f"Screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}.png"
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])   # monitor 0 = the whole virtual desktop
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))
    return f"Screenshot saved: {path.name}"


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


SHUTDOWN_DELAY = 30


def _shutdown_exe() -> str:
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "shutdown.exe")


def _run_shutdown(args: list[str]) -> int:
    proc = subprocess.run([_shutdown_exe(), *args], capture_output=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    return proc.returncode


@register_action("shutdown_30s", f"Shut down PC in {SHUTDOWN_DELAY} seconds",
                 "Windows shuts down after a 30 second warning. Map 'Cancel shutdown' to "
                 "another gesture (or run shutdown /a) to stop it.", "System", order=17)
def shutdown_30s(ctx, params):
    code = _run_shutdown(["/s", "/t", str(SHUTDOWN_DELAY), "/c",
                          f"VisualCommand: shutting down in {SHUTDOWN_DELAY} seconds."])
    if code != 0:
        # 1190 = a shutdown is already scheduled
        return "A shutdown is already scheduled" if code == 1190 else f"Shutdown failed (code {code})"
    return f"PC shuts down in {SHUTDOWN_DELAY} seconds"


@register_action("cancel_shutdown", "Cancel shutdown",
                 "Stops a scheduled shutdown (from the action above or anywhere else).",
                 "System", order=18)
def cancel_shutdown(ctx, params):
    code = _run_shutdown(["/a"])
    return "Shutdown cancelled" if code == 0 else "No shutdown was scheduled"


@register_action("pause_tracking", "Pause tracking for 10 minutes",
                 "Releases the camera for 10 minutes.", "VisualCommand", order=90)
def pause_tracking(ctx, params):
    ctx.pause(minutes=10)
    return "Tracking paused for 10 minutes"
