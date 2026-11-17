"""The app's own popups (replace Windows' toasts).

One popup at a time, bottom-right above the taskbar. It never takes keyboard
focus and doesn't appear in the taskbar.

- show(): a short message that fades out by itself; a new one replaces it.
  Clicking it closes it.
- confirm(): for actions that need confirmation (power actions). Counts down with
  Execute / Cancel buttons; runs the action when the countdown ends. While it is
  open, ordinary messages don't replace it.

Must be used from the Tk thread (App posts to it).
"""
from __future__ import annotations

import ctypes
import time
import tkinter as tk
from ctypes import wintypes
from typing import Callable

from PIL import ImageTk

from visualcommand.icon import make_icon

BG = "#ffffff"
BORDER = "#d4d4d8"
TITLE_FG = "#1f1f23"
TEXT_FG = "#55555c"
ACCENT = {"info": "#22a05a", "error": "#c83c3c", "paused": "#d68c1e", "confirm": "#d68c1e"}
EXECUTE_BG, EXECUTE_ACTIVE = "#c83c3c", "#a82f2f"
CANCEL_BG, CANCEL_ACTIVE = "#ececf0", "#dcdce2"
BAR_BG = "#ececf0"

WIDTH = 340
MARGIN = 16
SHOW_MS = 2600
FADE_STEPS = 8
FADE_MS = 20
TICK_MS = 100

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008


def _work_area() -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right, rect.bottom


def countdown_text(action: str, remaining: float) -> str:
    return f"{action} in {max(0, int(remaining + 0.999))} s"


class Toast:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._win: tk.Toplevel | None = None
        self._jobs: list[str] = []
        self._confirm: dict | None = None          # state of an open confirmation
        self._icons = {kind: ImageTk.PhotoImage(make_icon(state, 32), master=root)
                       for kind, state in (("info", "on"), ("error", "error"),
                                           ("paused", "paused"), ("confirm", "paused"))}

    @property
    def confirming(self) -> bool:
        return self._confirm is not None

    # --- public -------------------------------------------------------------------
    def show(self, title: str, message: str = "", kind: str = "info") -> bool:
        """Short message. Returns False (not shown) while a confirmation is open."""
        if self.confirming:
            return False
        win, card, text = self._frame(title, kind)
        if message:
            tk.Label(text, text=message, bg=BG, fg=TEXT_FG, font=("Segoe UI", 9),
                     anchor="w", justify="left", wraplength=WIDTH - 80).pack(fill="x", pady=(2, 0))
        for w in (win, card, text, *card.winfo_children(), *text.winfo_children()):
            w.bind("<Button-1>", lambda _e: self._close_now())
        self._present(win)
        self._jobs.append(self.root.after(SHOW_MS, lambda: self._fade(win, FADE_STEPS, -1)))
        return True

    def confirm(self, title: str, action: str, seconds: float,
                on_execute: Callable[[], None], on_cancel: Callable[[], None]) -> None:
        """Count down `seconds`, then call on_execute (also on the Execute button).
        Cancel (or a newer confirmation) calls on_cancel instead."""
        if self.confirming:
            self._finish(execute=False)              # a newer request replaces it
        win, card, text = self._frame(title, "confirm")
        countdown = tk.Label(text, text=countdown_text(action, seconds), bg=BG, fg=TITLE_FG,
                             font=("Segoe UI", 12), anchor="w")
        countdown.pack(fill="x", pady=(2, 6))
        bar = tk.Canvas(text, height=4, bg=BAR_BG, highlightthickness=0, bd=0)
        bar.pack(fill="x", pady=(0, 10))
        fill = bar.create_rectangle(0, 0, WIDTH, 4, fill=ACCENT["confirm"], width=0)
        buttons = tk.Frame(text, bg=BG)
        buttons.pack(fill="x")

        def button(label, bg, active, fg, cmd):
            b = tk.Button(buttons, text=label, command=cmd, bg=bg, fg=fg, activebackground=active,
                          activeforeground=fg, relief="flat", bd=0, padx=16, pady=5,
                          font=("Segoe UI Semibold", 9), cursor="hand2", takefocus=0)
            b.pack(side="left", padx=(0, 8))
            return b

        execute = button("Execute", EXECUTE_BG, EXECUTE_ACTIVE, "white",
                         lambda: self._finish(execute=True))
        cancel = button("Cancel", CANCEL_BG, CANCEL_ACTIVE, TITLE_FG,
                        lambda: self._finish(execute=False))
        self._confirm = {"on_execute": on_execute, "on_cancel": on_cancel, "action": action,
                         "deadline": time.monotonic() + seconds, "seconds": seconds,
                         "label": countdown, "bar": bar, "fill": fill, "win": win,
                         "buttons": (execute, cancel)}
        self._present(win)
        self._jobs.append(self.root.after(TICK_MS, self._tick))

    def execute_now(self) -> None:
        """Same as pressing Execute (for tests / keyboard shortcuts)."""
        if self.confirming:
            self._finish(execute=True)

    def cancel(self) -> None:
        """Same as pressing Cancel."""
        if self.confirming:
            self._finish(execute=False)

    def hide_message(self) -> None:
        """Close a plain message (e.g. before a screenshot); a confirmation stays."""
        if not self.confirming:
            self._close_now()

    # --- internals ----------------------------------------------------------------
    def _frame(self, title: str, kind: str):
        self._close_now()
        win = tk.Toplevel(self.root, bg=BORDER)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        self._win = win
        card = tk.Frame(win, bg=BG)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(card, bg=ACCENT.get(kind, ACCENT["info"]), width=5).pack(side="left", fill="y")
        tk.Label(card, image=self._icons.get(kind, self._icons["info"]), bg=BG).pack(
            side="left", padx=(12, 8), pady=12, anchor="n")
        text = tk.Frame(card, bg=BG)
        text.pack(side="left", fill="both", expand=True, pady=10, padx=(0, 14))
        tk.Label(text, text=title, bg=BG, fg=TITLE_FG, font=("Segoe UI Semibold", 10),
                 anchor="w", justify="left", wraplength=WIDTH - 80).pack(fill="x")
        return win, card, text

    def _present(self, win: tk.Toplevel) -> None:
        win.update_idletasks()
        h = win.winfo_reqheight()
        left, top, right, bottom = _work_area()
        win.geometry(f"{WIDTH}x{h}+{right - WIDTH - MARGIN}+{bottom - h - MARGIN}")
        self._style_native(win)
        win.deiconify()
        self._fade(win, 0, +1)

    def _tick(self) -> None:
        c = self._confirm
        if c is None:
            return
        remaining = c["deadline"] - time.monotonic()
        if remaining <= 0:
            self._finish(execute=True)
            return
        try:
            c["label"].configure(text=countdown_text(c["action"], remaining))
            width = c["bar"].winfo_width() or WIDTH
            c["bar"].coords(c["fill"], 0, 0, width * remaining / c["seconds"], 4)
        except tk.TclError:
            return
        self._jobs.append(self.root.after(TICK_MS, self._tick))

    def _finish(self, execute: bool) -> None:
        c, self._confirm = self._confirm, None
        self._close_now()
        if c is not None:
            (c["on_execute"] if execute else c["on_cancel"])()

    def _style_native(self, win: tk.Toplevel) -> None:
        """No focus stealing, no taskbar button, rounded corners on Windows 11."""
        try:
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass

    def _fade(self, win: tk.Toplevel, step: int, direction: int) -> None:
        if win is not self._win:
            return                      # replaced meanwhile
        try:
            win.attributes("-alpha", max(0.0, min(1.0, step / FADE_STEPS)) * 0.97)
        except tk.TclError:
            return
        nxt = step + direction
        if 0 <= nxt <= FADE_STEPS:
            self._jobs.append(self.root.after(FADE_MS, lambda: self._fade(win, nxt, direction)))
        elif direction < 0:
            self._close_now()

    def _close_now(self) -> None:
        for job in self._jobs:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()
        if self._win is not None:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None
