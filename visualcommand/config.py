"""Settings stored as JSON in %APPDATA%\\VisualCommand\\config.json."""
from __future__ import annotations

import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CONFIG_VERSION = 2

DEFAULTS: dict[str, Any] = {
    "version": CONFIG_VERSION,
    "tracking_enabled": True,
    # MediaPipe confidence needed to accept / keep a hand (0.3 lenient .. 0.9 strict).
    # Higher rejects shadows and clothing folds but may lose hands in poor light.
    "hand_strictness": 0.7,
    "notifications": True,
    "camera_index": 0,
    # "auto": enhance only when the scene is dark / flat / backlit. "always" | "off".
    "lighting_mode": "auto",
    # Optional safety gesture: when set, other gestures only fire within arm_window
    # seconds after this one was held.
    "arm_gesture": "",
    "arm_window": 5.0,
    "idle_fps": 4,
    "active_fps": 15,
    "sensitivity": {
        "hold_time": 0.4,       # seconds a pose must be held
        "cooldown": 2.0,        # seconds before the same gesture can fire again
        "min_score": 0.7,       # pose confidence needed (0..1)
        "swipe_distance": 0.25, # fraction of the frame a swipe must travel
    },
    # gesture id -> {"action": action id, "params": {...}}
    "mappings": {
        "Thumb_Up": {"action": "screenshot"},
        "Closed_Fist": {"action": "mute_mic"},
        "Victory": {"action": "lock_pc"},
        "Swipe_Left": {"action": "media_prev"},
        "Swipe_Right": {"action": "media_next"},
    },
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
                self._migrate(int(loaded.get("version", 1)))
        except Exception:
            log.exception("Config unreadable, using defaults")

    def _migrate(self, from_version: int) -> None:
        if from_version < 2:
            # 0.1.0 shipped a swipe distance that was too demanding; move users who
            # never changed it to the new default.
            if self.data["sensitivity"].get("swipe_distance") == 0.3:
                self.data["sensitivity"]["swipe_distance"] = DEFAULTS["sensitivity"]["swipe_distance"]
        self.data["version"] = CONFIG_VERSION

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
