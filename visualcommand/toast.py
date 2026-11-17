"""The app's own notification popup (replaces Windows' toasts).

One popup at a time, bottom-right above the taskbar. A new message replaces the
current popup immediately. It never takes keyboard focus, doesn't appear in the
taskbar, fades out by itself, and disappears when clicked.
Must be used from the Tk thread (App.notify posts to it).
"""
from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes

from PIL import ImageTk

from visualcommand.icon import make_icon

BG = "#ffffff"
BORDER = "#d4d4d8"
TITLE_FG = "#1f1f23"
TEXT_FG = "#55555c"
ACCENT = {"info": "#22a05a", "error": "#c83c3c", "paused": "#d68c1e"}

WIDTH = 340
MARGIN = 16
SHOW_MS = 2600
FADE_STEPS = 8
FADE_MS = 20

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008


def _work_area() -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right, rect.bottom


class Toast:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._win: tk.Toplevel | None = None
        self._jobs: list[str] = []
        self._icons = {kind: ImageTk.PhotoImage(make_icon(state, 32), master=root)
                       for kind, state in (("info", "on"), ("error", "error"), ("paused", "paused"))}

    # --- public -------------------------------------------------------------------
    def show(self, title: str, message: str = "", kind: str = "info") -> None:
        self._close_now()        # replace whatever is showing
        win = tk.Toplevel(self.root, bg=BORDER)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        self._win = win

        card = tk.Frame(win, bg=BG)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(card, bg=ACCENT.get(kind, ACCENT["info"]), width=5).pack(side="left", fill="y")
        tk.Label(card, image=self._icons.get(kind, self._icons["info"]), bg=BG).pack(side="left", padx=(12, 8), pady=12, anchor="n")
        text = tk.Frame(card, bg=BG)
        text.pack(side="left", fill="both", expand=True, pady=10, padx=(0, 14))
        tk.Label(text, text=title, bg=BG, fg=TITLE_FG, font=("Segoe UI Semibold", 10),
                 anchor="w", justify="left", wraplength=WIDTH - 80).pack(fill="x")
        if message:
            tk.Label(text, text=message, bg=BG, fg=TEXT_FG, font=("Segoe UI", 9),
                     anchor="w", justify="left", wraplength=WIDTH - 80).pack(fill="x", pady=(2, 0))

        for w in (win, card, text, *card.winfo_children(), *text.winfo_children()):
            w.bind("<Button-1>", lambda _e: self._close_now())

        win.update_idletasks()
        h = win.winfo_reqheight()
        left, top, right, bottom = _work_area()
        win.geometry(f"{WIDTH}x{h}+{right - WIDTH - MARGIN}+{bottom - h - MARGIN}")
        self._style_native(win)
        win.deiconify()
        self._fade(win, 0, +1)
        self._jobs.append(self.root.after(SHOW_MS, lambda: self._fade(win, FADE_STEPS, -1)))

    # --- internals ----------------------------------------------------------------
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
