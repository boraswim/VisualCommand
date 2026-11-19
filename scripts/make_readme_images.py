"""Developer tool: render the README images into docs/images/.

Everything is drawn from the app's own UI code with sample settings, on a plain
backdrop, so no real desktop, config or camera image ever ends up in a picture.

Usage: python scripts/make_readme_images.py
"""
from __future__ import annotations

import os
import tempfile
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageGrab

from visualcommand.config import Config
from visualcommand.icon import make_icon
from visualcommand.winutil import set_dpi_aware

OUT = Path(__file__).resolve().parent.parent / "docs" / "images"
BACKDROP = "#e9edf2"
FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def font(name: str, size: int):
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default()


# --- banner ---------------------------------------------------------------------------

def banner() -> None:
    w, h = 1280, 400
    img = Image.new("RGB", (w, h), "#0f1a14")
    d = ImageDraw.Draw(img)
    for y in range(h):                                    # soft green gradient
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(15 + 10 * t), int(26 + 40 * t), int(20 + 18 * t)))
    icon = make_icon("on", 200)
    img.paste(icon, (110, (h - 200) // 2), icon)
    d.text((360, 118), "VisualCommand", font=font("segoeuib.ttf", 84), fill="white")
    d.text((364, 222), "Hand-gesture shortcuts for Windows", font=font("segoeui.ttf", 38),
           fill="#c9f0d8")
    d.text((364, 276), "Fully local  ·  no images kept  ·  lives in your tray",
           font=font("segoeui.ttf", 28), fill="#8fbfa2")
    img.save(OUT / "banner.png", optimize=True)


# --- UI screenshots -------------------------------------------------------------------

class _Tracker:
    status, lighting, preview = "running", "good", False
    def wake(self): pass
    def request_camera_settings(self): pass
    def check_orientation(self, *a, **k): pass


class _App:
    def __init__(self, cfg):
        self.cfg, self.tracker = cfg, _Tracker()
        self.last_event = "👍 Thumbs up → Screenshot saved  (14:02:11)"
    def is_paused(self): return False
    def toggle_preview(self): pass
    def set_tracking(self, on): pass
    def test_action(self, a, p): pass
    def post(self, fn): fn()
    def notify(self, *a, **k): pass
    def open_trigger_logs(self): pass


SAMPLE_MAPPINGS = {
    "Thumb_Up": "screenshot", "Thumb_Down": "volume_down", "Closed_Fist": "mute_mic",
    "Victory": "lock_pc", "Point_Left": "media_prev", "Point_Right": "media_next",
    "Rock": "media_play_pause", "Three_Fingers": "shutdown",
}


def _backdrop(root, x, y, w, h):
    b = tk.Toplevel(root, bg=BACKDROP)
    b.overrideredirect(True)
    b.geometry(f"{w}x{h}+{x}+{y}")
    b.attributes("-topmost", True)
    return b


def _grab(x, y, w, h, path):
    ImageGrab.grab((x, y, x + w, y + h), all_screens=True).save(path, optimize=True)


def screenshots() -> None:
    from visualcommand.settings_ui import SettingsWindow
    from visualcommand.toast import Toast, _work_area

    cfg = Config(Path(tempfile.mkdtemp()) / "config.json")
    for gid, action in SAMPLE_MAPPINGS.items():
        cfg.set_mapping(gid, action)

    root = tk.Tk()
    ui = SettingsWindow(root, _App(cfg))
    root.withdraw()
    pad = 28
    bx, by = 60, 60
    win_w, win_h = 860, 700
    cap_w, cap_h = win_w + 2 * pad, win_h + 2 * pad + 40   # + title bar and frame
    root.geometry(f"{win_w}x{win_h}+{bx + pad}+{by + pad}")
    root.update()
    back = _backdrop(root, bx, by, cap_w, cap_h)
    ui.show()
    root.attributes("-topmost", True)
    nb = next(w for w in root.winfo_children() if w.winfo_class() == "TNotebook")
    tabs = [(0, "settings_gestures.png"), (1, "settings_general.png"), (2, "settings_sensitivity.png")]

    def shot(i=0):
        if i < len(tabs):
            nb.select(tabs[i][0])

            def grab_tab():
                # show() drops "always on top" after a moment; put the window back above
                # the backdrop right before grabbing.
                root.attributes("-topmost", True)
                root.lift()
                root.update()
                root.after(150, lambda: (_grab(bx, by, cap_w, cap_h, OUT / tabs[i][1]),
                                         shot(i + 1)))
            root.after(500, grab_tab)
        else:
            root.withdraw()
            back.destroy()
            toasts()

    def toasts():
        l, t, r, b = _work_area()
        w, h = 420, 250          # every grab below stays inside this backdrop
        x, y = r - w, b - h
        bd = _backdrop(root, x, y, w, h)
        toast = Toast(root)
        toast.show("👍 Thumbs up", "Screenshot saved: Screenshot_2026-11-19_14-02-11.png",
                   on_click=lambda: None, click_hint="Click to open the folder")
        root.after(700, lambda: (_grab(x, y, w, h, OUT / "popup_screenshot.png"),
                                 toast._close_now(), confirm(bd, x, y, w, h)))

    def confirm(bd, x, y, w, h):
        toast = Toast(root)
        toast.confirm("3️⃣ Three fingers", "Shut down", 10, on_execute=lambda: None,
                      on_cancel=lambda: None)
        root.after(2300, lambda: (_grab(x, y, w, h, OUT / "popup_power.png"),
                                  toast.cancel(), bd.destroy(), root.destroy()))

    root.after(800, shot)
    root.mainloop()


def main() -> None:
    set_dpi_aware()
    OUT.mkdir(parents=True, exist_ok=True)
    banner()
    screenshots()
    for p in sorted(OUT.glob("*.png")):
        print(f"{p.name}: {Image.open(p).size}")


if __name__ == "__main__":
    main()
