"""Power actions: shut down, restart, sleep.

All of them wait for confirmation: a popup counts down POWER_COUNTDOWN seconds
with Execute / Cancel buttons (see App._request_confirm and Toast.confirm).
When the countdown ends or Execute is pressed, the action runs immediately.
"""
from __future__ import annotations

import ctypes
import os
import subprocess

from visualcommand.actions.base import register_action

POWER_COUNTDOWN = 10   # seconds the confirmation popup counts down


def _shutdown_exe() -> str:
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "shutdown.exe")


def _run_shutdown(args: list[str]) -> int:
    proc = subprocess.run([_shutdown_exe(), *args], capture_output=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    return proc.returncode


@register_action("shutdown", "Shut down", "Shuts the PC down after a 10 second countdown "
                 "you can cancel.", "Power", order=60, confirm_seconds=POWER_COUNTDOWN)
def shutdown(ctx, params):
    # /t 0: the countdown already happened in our popup. No /f: apps with unsaved
    # work can still ask before closing.
    code = _run_shutdown(["/s", "/t", "0"])
    if code != 0:
        raise RuntimeError(f"shutdown.exe returned {code}")
    return "Shutting down"


@register_action("restart", "Restart", "Restarts the PC after a 10 second countdown "
                 "you can cancel.", "Power", order=61, confirm_seconds=POWER_COUNTDOWN)
def restart(ctx, params):
    code = _run_shutdown(["/r", "/t", "0"])
    if code != 0:
        raise RuntimeError(f"shutdown.exe returned {code}")
    return "Restarting"


@register_action("sleep", "Sleep", "Puts the PC to sleep after a 10 second countdown "
                 "you can cancel.", "Power", order=62, confirm_seconds=POWER_COUNTDOWN)
def sleep(ctx, params):
    # SetSuspendState(hibernate=False, force=False, disable_wake_events=False).
    # Called directly (not via rundll32, which passes arguments wrongly and can
    # hibernate instead).
    if not ctypes.windll.powrprof.SetSuspendState(False, False, False):
        raise RuntimeError("Windows refused to sleep")
    return "Going to sleep"
