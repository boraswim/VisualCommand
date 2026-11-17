"""Developer tool: download MediaPipe's gesture recognizer model into models/.

Runs only at build time. The app itself never touches the network: it loads
this file from disk (bundled into the exe by PyInstaller).
"""
from pathlib import Path
import urllib.request

URL = ("https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
       "gesture_recognizer/float16/latest/gesture_recognizer.task")
DEST = Path(__file__).resolve().parent.parent / "models" / "gesture_recognizer.task"


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and DEST.stat().st_size > 1_000_000:
        print(f"Model already present: {DEST}")
        return
    print(f"Downloading {URL}")
    tmp = DEST.with_suffix(".part")
    urllib.request.urlretrieve(URL, tmp)
    tmp.replace(DEST)
    print(f"Saved {DEST} ({DEST.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
