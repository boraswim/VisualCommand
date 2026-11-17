"""Developer tool: write assets/icon.ico from the same drawing the tray uses."""
from pathlib import Path

from visualcommand.icon import save_ico

DEST = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"

if __name__ == "__main__":
    DEST.parent.mkdir(exist_ok=True)
    save_ico(DEST)
    print(f"Wrote {DEST}")
