"""Developer tool: replay trigger-log records through the current gesture rules.

For each record (a trigger that happened), rebuild the hand frames and run them
through the engine with the record's gesture mapped. Shows whether the current
rules would still fire, and if not, why (the deliberate-gesture checks).

Usage: python scripts/replay_trigger_logs.py [FOLDER or FILE ...]
       (default: %APPDATA%/VisualCommand/trigger_logs)
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from visualcommand.features import (
    FrameFeatures, drop_phantom_hands, features_from_landmarks, palm_facing, plausible_hand,
)
from visualcommand.gestures import load_all
from visualcommand.hands import HandSlots

ASPECT = 480 / 360


def frames_from_record(data: dict) -> list[FrameFeatures]:
    out = []
    for fr in data["frames"]:
        if not fr.get("hand"):
            out.append(FrameFeatures(t=fr["t"]))
            continue
        lm = np.array(fr["landmarks"], dtype=np.float32)
        f = features_from_landmarks(fr["t"], lm[:, :2].copy(), ASPECT, fr.get("lighting", "good"),
                                    fr["mp_label"], fr["mp_score"], fr["handedness"])
        f.extra["handedness_score"] = fr.get("handedness_score", 0.99)
        if lm.shape[1] == 3:
            raw = lm.copy()
            raw[:, 0] = 1.0 - raw[:, 0]           # back to the camera's natural view
            f.palm_facing = palm_facing(raw, ASPECT, fr["handedness"])
            f.extra["z"] = lm[:, 2]
        out.append(f)
    return out


def replay(data: dict) -> tuple[bool, Counter]:
    """(would it still fire?, reasons the hand didn't count)"""
    settings = data.get("settings", {})
    sens = dict(settings.get("sensitivity") or {"hold_time": 0.4, "cooldown": 2.0, "min_score": 0.55})
    slots = HandSlots(2)
    fired, reasons = False, Counter()
    for f in frames_from_record(data):
        hands = drop_phantom_hands([f] if plausible_hand(f) else [])
        if slots.process(f.t, hands, f.lighting, {data["gesture"]}, sens):
            fired = True
        for s in slots.slots:
            if s.engine.last_problem and s.current is not None and s.current.hand:
                reasons[s.engine.last_problem] += 1
    return fired, reasons


def main() -> None:
    load_all()
    args = sys.argv[1:] or [os.path.join(os.environ.get("APPDATA", ""), "VisualCommand", "trigger_logs")]
    files = []
    for a in args:
        p = Path(a)
        files += sorted(p.glob("trigger_*.json")) if p.is_dir() else [p]
    still = 0
    for p in files:
        data = json.loads(p.read_text(encoding="utf-8"))
        fired, reasons = replay(data)
        still += fired
        why = "; ".join(f"{r} ({n} frames)" for r, n in reasons.most_common(3)) or "-"
        print(f"{'FIRES  ' if fired else 'blocked'}  {p.name}  [{data['outcome']}]  {why}")
    print(f"\n{still}/{len(files)} records would still fire with the current rules")


if __name__ == "__main__":
    main()
