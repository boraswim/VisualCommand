"""Settings stored as JSON in %APPDATA%\\VisualCommand\\config.json."""
from __future__ import annotations

import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CONFIG_VERSION = 5

DEFAULTS: dict[str, Any] = {
    "version": CONFIG_VERSION,
    "tracking_enabled": True,
    # MediaPipe confidence needed to accept / keep a hand (0.3 lenient .. 0.9 strict).
    # Higher rejects shadows and clothing folds but may lose hands in poor light.
    "hand_strictness": 0.7,
    "notifications": True,
    "camera_index": 0,
    # MediaPipe expects a selfie-style (mirrored) image. Most webcams deliver an
    # unmirrored picture, so the app flips it; some already mirror it themselves and
    # must not be flipped again (otherwise left/right hands get swapped). Set by the
    # "Check camera orientation" button in the General tab.
    "mirror_image": True,
    # "auto": enhance only when the scene is dark / flat / backlit. "always" | "off".
    "lighting_mode": "auto",
    # Optional safety gesture: when set, other gestures only fire within arm_window
    # seconds after this one was held.
    "arm_gesture": "",
    "arm_window": 5.0,
    # Checks per second while no hand is visible: how quickly a new hand is noticed.
    "idle_fps": 6,
    "active_fps": 15,
    "sensitivity": {
        "hold_time": 0.4,       # seconds a pose must be held
        "cooldown": 2.0,        # seconds before the same gesture can fire again
        # MediaPipe's pose confidence needed (0..1). Its scores for a correctly
        # recognised pose are often only 0.6-0.75; the hold time (same pose for
        # hold_time seconds) is what guards against accidental triggers.
        "min_score": 0.55,
    },
    # gesture id -> {"action": action id, "params": {...}}
    "mappings": {
        "Thumb_Up": {"action": "screenshot"},
        "Closed_Fist": {"action": "mute_mic"},
        "Victory": {"action": "lock_pc"},
    },
}

# Motion gestures existed up to 0.1.2 and were removed in 0.1.3.
_REMOVED_GESTURES = {
    "Swipe_Left", "Swipe_Right", "Swipe_Up", "Swipe_Down", "Push", "Wave",
    "Circle_CW", "Circle_CCW", "Pinch_Drag_Up", "Pinch_Drag_Down",
}


def _merge(defaults: dict, loaded: dict) -> dict:
    out = copy.deepcopy(defaults)
    for key, value in loaded.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict) and key != "mappings":
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


class Config:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.first_run = not path.exists()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            with self._lock:
                self.data = _merge(DEFAULTS, loaded)
                migrated = self._migrate(int(loaded.get("version", 1)))
        except Exception:
            log.exception("Config unreadable, using defaults")
            return
        if migrated:
            try:
                self.save()
            except OSError:
                log.exception("Could not save migrated config")

    def _migrate(self, from_version: int) -> bool:
        """Bring an older config up to date. Returns True if anything changed."""
        changed = from_version < CONFIG_VERSION
        if from_version < 3:
            # Motion gestures (swipes etc.) were removed: drop their settings and mappings.
            self.data["sensitivity"].pop("swipe_distance", None)
            for gid in _REMOVED_GESTURES:
                self.data["mappings"].pop(gid, None)
        if from_version < 4:
            # 4 checks/s noticed a hand entering the frame too late; users who never
            # changed it move to the new default.
            if self.data.get("idle_fps") == 4:
                self.data["idle_fps"] = DEFAULTS["idle_fps"]
        if from_version < 5:
            # 0.7 rejected correctly recognised poses (e.g. open palm at 0.61).
            if self.data["sensitivity"].get("min_score") == 0.7:
                self.data["sensitivity"]["min_score"] = DEFAULTS["sensitivity"]["min_score"]
        self.data["version"] = CONFIG_VERSION
        return changed

    def save(self) -> None:
        with self._lock:
            text = json.dumps(self.data, indent=2)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self.path)

    # --- convenience accessors -------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.data.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        with self._lock:
            self.data[key] = value
        if save:
            self.save()

    def sensitivity(self) -> dict[str, float]:
        with self._lock:
            return dict(self.data["sensitivity"])

    def set_sensitivity(self, key: str, value: float) -> None:
        with self._lock:
            self.data["sensitivity"][key] = value
        self.save()

    def mappings(self) -> dict[str, dict]:
        with self._lock:
            return copy.deepcopy(self.data["mappings"])

    def set_mapping(self, gesture_id: str, action_id: str, params: dict | None = None) -> None:
        with self._lock:
            if not action_id or action_id == "none":
                self.data["mappings"].pop(gesture_id, None)
            else:
                self.data["mappings"][gesture_id] = {"action": action_id, "params": params or {}}
        self.save()
