"""Entry point: tray icon + camera worker + settings window."""
from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from logging.handlers import RotatingFileHandler

from visualcommand import APP_NAME, __version__
from visualcommand import actions, gestures, sound
from visualcommand.config import Config
from visualcommand.paths import app_data_dir
from visualcommand.tracker import Tracker
from visualcommand.tray import Tray
from visualcommand.winutil import SingleInstance, repair_autostart, set_dpi_aware

log = logging.getLogger(APP_NAME)


def _setup_logging(verbose: bool) -> None:
    handler = RotatingFileHandler(app_data_dir() / "visualcommand.log", maxBytes=256_000,
                                  backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("PIL", "comtypes"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _com_init() -> None:
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass


class App:
    def __init__(self, args) -> None:
        self.args = args
        self.cfg = Config(app_data_dir() / "config.json")
        if self.cfg.first_run:
            self.cfg.save()
        self.paused_until = 0.0
        self.last_event = ""
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._executor = ThreadPoolExecutor(1, "action", initializer=_com_init)
        self._quitting = False

        gestures.load_all()
        actions.load_all()

        self.root = tk.Tk()
        self.root.withdraw()
        self.ui = None
        self.toast = None
        self.tracker = Tracker(self)
        self.tray = Tray(self)

    # --- thread-safe bridge to the Tk thread -----------------------------------------
    def post(self, fn) -> None:
        self._queue.put(fn)

    def _pump(self) -> None:
        try:
            while True:
                self._queue.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            log.exception("UI callback failed")
        if not self._quitting:
            self.root.after(150, self._pump)

    def _ui(self):
        if self.ui is None:
            from visualcommand.settings_ui import SettingsWindow
            self.ui = SettingsWindow(self.root, self)
        return self.ui

    def _refresh_ui(self) -> None:
        if self.ui is not None:
            self.ui.refresh_status()

    # --- called from anywhere ----------------------------------------------------------
    def show_window(self) -> None:
        self.post(lambda: self._ui().show())

    def notify(self, message: str, title: str = APP_NAME, error: bool = False) -> None:
        """Show the app's own popup (replaces any popup already showing).

        Errors are always shown; action confirmations only if enabled in settings.
        """
        if not error and not self.cfg.get("notifications", True):
            return

        def show():
            if self.toast is None:
                from visualcommand.toast import Toast
                self.toast = Toast(self.root)
            self.toast.show(title, message, "error" if error else "info")
        self.post(show)

    def hide_popups(self, timeout: float = 0.5) -> None:
        """Remove our popup before something captures the screen (call from any non-Tk thread)."""
        if self.toast is None:
            return
        done = threading.Event()

        def close():
            self.toast._close_now()
            self.root.update_idletasks()
            done.set()
        self.post(close)
        done.wait(timeout)
        time.sleep(0.05)   # let the compositor drop the window

    def on_tracker_status(self) -> None:
        self.tray.refresh()
        self.post(self._refresh_ui)

    def on_gesture(self, gesture_id: str) -> None:
        mapping = self.cfg.mappings().get(gesture_id)
        if not mapping:
            return
        log.info("Gesture %s -> %s", gesture_id, mapping.get("action"))
        self._executor.submit(self._run_action, gesture_id, mapping.get("action"), mapping.get("params"))

    def test_action(self, action_id: str, params: dict | None) -> None:
        self._executor.submit(self._run_action, "", action_id, params)

    @staticmethod
    def feedback_for(from_gesture: bool, action_id: str, msg: str | None, failed: bool,
                     popups_on: bool, sounds_on: bool) -> tuple[bool, str | None]:
        """What to show/play after an action: (show popup?, sound name or None).

        Test-button runs get neither: the result shows in the window's status line.
        """
        if not from_gesture:
            return False, None
        sound = ("error" if failed else "action") if sounds_on else None
        popup = bool(msg) and action_id != "lock_pc" and (popups_on or failed)
        return popup, sound

    def _run_action(self, gesture_id: str, action_id: str, params: dict | None) -> None:
        g = gestures.registry().get(gesture_id)
        label = f"{g.icon} {g.name}" if g else "Test"
        failed = False
        try:
            msg = actions.run_action(action_id, params, self)
        except Exception as exc:
            log.exception("Action %s failed", action_id)
            msg, failed = f"Couldn't run {action_id}: {exc}", True
        self.last_event = f"{label} → {msg or action_id}  ({datetime.now():%H:%M:%S})"
        popup, sound_name = self.feedback_for(
            bool(gesture_id), action_id, msg, failed,
            popups_on=self.cfg.get("notifications", True), sounds_on=self.cfg.get("sounds", True))
        if sound_name:
            sound.play(sound_name)
        if popup:
            self.notify(msg, title=label, error=failed)
        self.post(self._refresh_ui)

    def set_tracking(self, on: bool) -> None:
        self.cfg.set("tracking_enabled", bool(on))
        if on:
            self.paused_until = 0.0
        self.tracker.wake()
        self.tray.refresh()
        self.post(self._refresh_ui)

    def toggle_preview(self) -> None:
        if not self.tracker.preview and not self.cfg.get("tracking_enabled", True):
            self.set_tracking(True)
        if self.is_paused():
            self.pause(0)
        self.tracker.set_preview(not self.tracker.preview)
        self.tray.refresh()
        self.post(self._refresh_ui)

    def is_paused(self) -> bool:
        return self.paused_until > time.time()

    def pause(self, minutes: float) -> None:
        self.paused_until = time.time() + minutes * 60 if minutes else 0.0
        self.tracker.wake()
        self.tray.refresh()
        self.post(self._refresh_ui)

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self.tracker.stop()
        self.tray.stop()
        self.root.after(0, self.root.quit)

    # --- lifecycle ---------------------------------------------------------------------
    def _listen_for_show(self, instance: SingleInstance) -> None:
        while not self._quitting:
            if instance.wait_show(1000):
                self.show_window()

    def _bench(self) -> None:
        import psutil
        proc = psutil.Process()
        proc.cpu_percent(None)
        last_frames = 0
        while not self._quitting:
            time.sleep(10)
            st = self.tracker.stats
            frames = st["frames"] - last_frames
            last_frames = st["frames"]
            ms = sum(st["proc_ms"]) / len(st["proc_ms"]) if st["proc_ms"] else 0.0
            conns = [c for c in proc.net_connections(kind="inet")]
            log.info("BENCH status=%s fps=%.1f proc=%.1fms cpu=%.1f%% rss=%.0fMB net_connections=%d",
                     self.tracker.status, frames / 10, ms,
                     proc.cpu_percent(None) / psutil.cpu_count(), proc.memory_info().rss / 1e6, len(conns))

    def run(self, instance: SingleInstance) -> None:
        repair_autostart()
        self.tracker.start()
        self.tray.start()
        self.tray.refresh()
        threading.Thread(target=self._listen_for_show, args=(instance,), daemon=True).start()
        if self.args.bench:
            threading.Thread(target=self._bench, daemon=True).start()
        if not self.args.tray:
            self.show_window()
        self.root.after(150, self._pump)
        self.root.mainloop()
        self.tracker.join(timeout=3)
        self._executor.shutdown(wait=False)
        log.info("Exited")


def main() -> None:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--tray", action="store_true", help="start hidden in the tray")
    parser.add_argument("--bench", action="store_true", help="log CPU / fps every 10 s")
    parser.add_argument("--verbose", action="store_true")
    args, _ = parser.parse_known_args()

    instance = SingleInstance()
    if not instance.primary:
        instance.signal_primary()   # bring the running copy's window up instead
        return

    set_dpi_aware()
    _setup_logging(args.verbose)
    log.info("%s %s starting (python %s)", APP_NAME, __version__, sys.version.split()[0])
    try:
        App(args).run(instance)
    except Exception:
        log.exception("Fatal error")
        raise


if __name__ == "__main__":
    main()
