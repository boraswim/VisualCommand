"""Developer tool: build the app's notification sounds from the CC0 Kenney library.

Source: Kenney "Interface Sounds" (CC0, https://kenney.nl), in D:/Workshop/SFX.
Only the processed WAVs in assets/sounds/ go into the repo. Needs ffmpeg on PATH.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

LIB = Path("D:/Workshop/SFX/Kenney-Audio")
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"

SOUNDS = {
    # output name: (source file, gain in dB)
    "action.wav": ("confirmation_001.ogg", -8),
    "error.wav": ("error_004.ogg", -10),
    # power-action countdown popup: a "please respond" prompt, a bit louder
    "attention.wav": ("question_001.ogg", -5),
}


def find(name: str) -> Path:
    hits = list(LIB.rglob(name))
    if not hits:
        raise FileNotFoundError(f"{name} not found under {LIB}")
    return hits[0]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for out_name, (src_name, gain) in SOUNDS.items():
        src, dst = find(src_name), OUT / out_name
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
