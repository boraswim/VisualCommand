"""App / tray icon, drawn in code so state colours need no image files."""
from __future__ import annotations

from PIL import Image, ImageDraw

COLORS = {
    "on": (34, 160, 90),        # tracking
    "off": (110, 110, 118),     # tracking disabled
    "paused": (214, 140, 30),   # paused / locked / camera busy
    "error": (200, 60, 60),
}


def make_icon(state: str = "on", size: int = 64) -> Image.Image:
    s = 4  # draw at 4x and downsample for smooth edges
    W = size * s
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, W - 1), radius=int(W * 0.22), fill=COLORS.get(state, COLORS["on"]))

    white = (255, 255, 255, 255)
    u = W / 64.0
    # palm
    d.rounded_rectangle((18 * u, 30 * u, 46 * u, 54 * u), radius=int(9 * u), fill=white)
    # fingers (index..pinky), slightly different lengths
    for x, top in ((18.5, 13), (25.5, 9), (32.5, 10), (39.5, 15)):
        d.rounded_rectangle((x * u, top * u, (x + 6) * u, 36 * u), radius=int(3 * u), fill=white)
    # thumb, angled outwards
    d.polygon([(18 * u, 40 * u), (9 * u, 29 * u), (13 * u, 25.5 * u), (22 * u, 34 * u)], fill=white)
    d.ellipse((8 * u, 24.5 * u, 14 * u, 30.5 * u), fill=white)
    return img.resize((size, size), Image.LANCZOS)


def save_ico(path) -> None:
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    make_icon("on", 256).save(path, format="ICO", sizes=[(n, n) for n in sizes])
