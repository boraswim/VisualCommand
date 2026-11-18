"""System tray icon (the ^ area at the bottom right of the taskbar)."""
from __future__ import annotations

import os
import time

import pystray
from pystray import Menu, MenuItem as Item

from visualcommand import APP_NAME
from visualcommand import tracker as T
from visualcommand.icon import make_icon
from visualcommand.paths import screenshots_dir

_STATE_FOR_STATUS = {
    T.RUNNING: "on", T.OFF: "off", T.PAUSED: "paused", T.LOCKED: "paused",
    T.CAMERA_BUSY: "paused", T.STARTING: "paused", T.ERROR: "error",
}


class Tray:
    def __init__(self, app) -> None:
        self.app = app
        self._icons = {s: make_icon(s, 64) for s in ("on", "off", "paused", "error")}
        self._state = "off"
        menu = Menu(
            Item("Open VisualCommand", lambda: app.show_window(), default=True),
            Menu.SEPARATOR,
            Item("Tracking", lambda: app.set_tracking(not app.cfg.get("tracking_enabled", True)),
                 checked=lambda _: bool(app.cfg.get("tracking_enabled", True))),
            Item("Show camera preview", lambda: app.toggle_preview(),
                 checked=lambda _: app.tracker.preview),
            Item(lambda _: "Resume tracking" if app.is_paused() else "Pause for 10 minutes",
                 lambda: app.pause(0 if app.is_paused() else 10)),
            Item("Open screenshots folder", lambda: os.startfile(screenshots_dir())),
            Item("Open trigger logs", lambda: app.open_trigger_logs()),
            Menu.SEPARATOR,
            Item("Quit", lambda: app.quit()),
        )
        self.icon = pystray.Icon(APP_NAME, self._icons["off"], APP_NAME, menu)

    def start(self) -> None:
        self.icon.run_detached()

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:
            pass

    def tooltip(self) -> str:
        tr = self.app.tracker
        if self.app.is_paused():
            mins = max(1, int((self.app.paused_until - time.time()) / 60 + 0.5))
            return f"{APP_NAME}: paused ({mins} min left)"
        text = f"{APP_NAME}: {tr.status}"
        if tr.status == T.RUNNING:
            text += f" · lighting {tr.lighting}"
        return text[:127]

    def refresh(self) -> None:
        state = _STATE_FOR_STATUS.get(self.app.tracker.status, "paused")
        if state != self._state:
            self._state = state
            self.icon.icon = self._icons[state]
        self.icon.title = self.tooltip()
        self.icon.update_menu()

    def notify(self, message: str) -> None:
        try:
            self.icon.notify(message, APP_NAME)
        except Exception:
            pass
