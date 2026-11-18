"""Trigger log: one small JSON file per fired gesture, kept for 24 hours.

Each record holds only numbers from hand tracking, never an image:
the hand's 21 landmarks (x, y, depth) for the ~1.5 s before the trigger,
MediaPipe's label/confidence, left/right, lighting, the rule measures, the
settings in use, which action it ran and what happened (ran / failed /
executed / cancelled). Used to find and tune false triggers.

Files live in %APPDATA%\\VisualCommand\\trigger_logs and are never sent anywhere;
the user can zip the folder and share it on purpose.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from visualcommand import __version__

log = logging.getLogger(__name__)

RETENTION_SECONDS = 24 * 3600
SCHEMA = 1

# FrameFeatures fields copied into each frame (all numbers; the rule measures)
MEASURES = (
    "palm_size", "pinch", "index_reach", "straightness", "straightness_index_middle", "spread",
    "palm_width", "tilt", "palm_facing", "thumb_index_angle", "thumb_lift", "thumb_angle",
    "fist_tightness", "v_gap", "v_angle", "ring_pinky_curl",
)

README = """VisualCommand trigger log
=========================

One file per time a gesture triggered an action. Each file is deleted
automatically 24 hours after it was written.

What is inside (numbers only - no pictures are ever saved):
- when it happened, the app version, the gesture and the action it ran
  (action settings such as typed commands are NOT saved)
- for the ~1.5 seconds before the trigger: the 21 hand points (x, y, depth)
  of the hand that made the gesture, MediaPipe's pose label and confidence,
  left/right hand, lighting, and the measurements the gesture rules use
- the detection settings in use
- the outcome: ran, failed, or for power actions executed / cancelled
  (a cancelled power action is a good sign of a false trigger)

Nothing here is sent anywhere by the app. If you want to help improve
gesture recognition, you can zip this folder and share it yourself.
You can turn the log off in VisualCommand > General > Trigger log.
"""


def _round(v, nd=4):
    return round(float(v), nd)


def frame_record(f, t_trigger: float) -> dict:
    """One FrameFeatures as plain numbers."""
    rec = {"t": _round(f.t - t_trigger, 3), "hand": bool(f.hand)}
    if not f.hand or f.landmarks is None:
        return rec
    z = f.extra.get("z")
    pts = []
    for i, (x, y) in enumerate(f.landmarks):
        p = [_round(x), _round(y)]
        if z is not None:
            p.append(_round(z[i]))
        pts.append(p)
    rec.update({
        "landmarks": pts,                        # user view: x grows to the user's right
        "mp_label": f.mp_label, "mp_score": _round(f.mp_score, 3),
        "handedness": f.handedness,
        "handedness_score": _round(f.extra.get("handedness_score", 0.0), 3),
        "extended": [bool(e) for e in f.extended],
        "lighting": f.lighting,
        "measures": {k: _round(getattr(f, k), 4) for k in MEASURES},
    })
    return rec


class TriggerLog:
    def __init__(self, folder: Path, retention_seconds: float = RETENTION_SECONDS) -> None:
        self.folder = Path(folder)
        self.retention = retention_seconds
        self._lock = threading.Lock()

    def ensure_folder(self) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        readme = self.folder / "README.txt"
        if not readme.exists():
            readme.write_text(README, encoding="utf-8")
        return self.folder

    def record(self, gesture_id: str, action_id: str, frames: list, settings: dict) -> Path | None:
        """Write one trigger. Returns its file (used to add the outcome later)."""
        try:
            self.ensure_folder()
            now = datetime.now()
            t_trigger = frames[-1].t if frames else time.monotonic()
            data = {
                "schema": SCHEMA,
                "app_version": __version__,
                "time": now.isoformat(timespec="milliseconds"),
                "gesture": gesture_id,
                "action": action_id,
                "outcome": "pending",
                "settings": settings,
                "frames": [frame_record(f, t_trigger) for f in frames],
            }
            stem = f"trigger_{now:%Y%m%d_%H%M%S_%f}"[:-3] + f"_{gesture_id}"
            with self._lock:
                path, n = self.folder / f"{stem}.json", 1
                while path.exists():                  # same millisecond: never overwrite
                    n += 1
                    path = self.folder / f"{stem}_{n}.json"
                path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
            self.purge()
            return path
        except Exception:
            log.exception("Could not write trigger log")
            return None

    def set_outcome(self, path: Path | None, outcome: str, detail: str = "") -> None:
        """Add what happened after the trigger (ran / failed / executed / cancelled)."""
        if path is None:
            return
        try:
            with self._lock:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                data["outcome"] = outcome
                if detail:
                    data["outcome_detail"] = detail[:200]
                Path(path).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        except FileNotFoundError:
            pass                                   # already purged or deleted by the user
        except Exception:
            log.exception("Could not update trigger log %s", path)

    def purge(self, now: float | None = None) -> int:
        """Delete records older than the retention period. Returns how many."""
        if not self.folder.exists():
            return 0
        cutoff = (now if now is not None else time.time()) - self.retention
        removed = 0
        for p in self.folder.glob("trigger_*.json"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except OSError:
                pass
        return removed
