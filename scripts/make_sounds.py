"""Developer tool: build the app's notification sounds from Kenney's CC0 audio.

Source: Kenney "Interface Sounds" (CC0, https://kenney.nl/assets/interface-sounds).
Download and unzip it, then point this script at the folder:

    python scripts/make_sounds.py path/to/kenney_interface-sounds

(or set VISUALCOMMAND_SFX_LIBRARY). Only the processed WAVs in assets/sounds/ go
into the repo; they are already there, so you only need this to change a sound.
Needs ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"

SOUNDS = {
    # output name: (source file, gain in dB)
    "action.wav": ("confirmation_001.ogg", -8),
    "error.wav": ("error_004.ogg", -10),
    # power-action countdown popup: a "please respond" prompt, a bit louder
    "attention.wav": ("question_001.ogg", -5),
}


def find(library: Path, name: str) -> Path:
    hits = list(library.rglob(name))
    if not hits:
        raise FileNotFoundError(f"{name} not found under {library}")
    return hits[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("library", nargs="?", default=os.environ.get("VISUALCOMMAND_SFX_LIBRARY"),
                    help="folder containing Kenney's Interface Sounds (.ogg files)")
    args = ap.parse_args()
    if not args.library:
        ap.error("give the Kenney Interface Sounds folder (or set VISUALCOMMAND_SFX_LIBRARY)")
    library = Path(args.library)
    OUT.mkdir(parents=True, exist_ok=True)
    for out_name, (src_name, gain) in SOUNDS.items():
        src, dst = find(library, src_name), OUT / out_name
        # mono, 44.1 kHz, 16-bit; quieter than the raw pack; 30 ms fade-out to avoid clicks
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
               "-ac", "1", "-ar", "44100", "-sample_fmt", "s16",
               "-af", f"volume={gain}dB,areverse,afade=t=in:d=0.03,areverse",
               str(dst)]
        subprocess.run(cmd, check=True)
        print(f"{dst.name}: {dst.stat().st_size} bytes  <- {src.name}")
    (OUT / "CREDITS.txt").write_text(
        "action.wav, error.wav, attention.wav: processed from Kenney 'Interface Sounds' "
        "(confirmation_001, error_004, question_001), CC0 1.0, https://kenney.nl\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
