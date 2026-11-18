"""Trigger log: numbers-only records of fired gestures, deleted after 24 hours."""
import json
import os
import time
from types import SimpleNamespace as NS

import numpy as np

from visualcommand.features import FrameFeatures, build_hands
from visualcommand.hands import HISTORY_SECONDS, HandSlots
from visualcommand.main import App
from visualcommand.triggerlog import MEASURES, TriggerLog

SENS = {"hold_time": 0.4, "cooldown": 2.0, "min_score": 0.55}


def _hand(t, label="Victory", score=0.9):
    lm = [NS(x=0.4 + 0.01 * i, y=0.5 - 0.01 * i, z=-0.001 * i) for i in range(21)]
    res = NS(hand_landmarks=[lm], gestures=[[NS(category_name=label, score=score)]],
             handedness=[[NS(category_name="Right", score=0.98)]])
    f = build_hands(t, res, 4 / 3, "good", to_user_view=True)[0]
    return f


def test_record_holds_numbers_only_and_what_it_was_paired_with(tmp_path):
    log = TriggerLog(tmp_path)
    frames = [_hand(10.0 + i / 15) for i in range(10)]
    path = log.record("Victory", "lock_pc", frames, {"hand_strictness": 0.7})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["gesture"] == "Victory" and data["action"] == "lock_pc"
    assert data["outcome"] == "pending" and data["settings"]["hand_strictness"] == 0.7
    assert len(data["frames"]) == 10 and data["frames"][-1]["t"] == 0.0
    fr = data["frames"][0]
    assert len(fr["landmarks"]) == 21 and len(fr["landmarks"][0]) == 3     # x, y, depth
    assert fr["mp_label"] == "Victory" and fr["handedness"] == "Right"
    assert set(fr["measures"]) == set(MEASURES)
    assert "params" not in data                     # typed commands are never stored
    assert (tmp_path / "README.txt").exists()


def test_record_contains_no_image_data(tmp_path):
    path = TriggerLog(tmp_path).record("Thumb_Up", "screenshot", [_hand(1.0)], {})
    text = path.read_text(encoding="utf-8")
    assert path.stat().st_size < 20_000                # a few KB of numbers, not pixels
    for word in ("image", "pixel", "jpeg", "png", "base64"):
        assert word not in text.lower()


def test_outcome_is_added_later(tmp_path):
    log = TriggerLog(tmp_path)
    p = log.record("Call_Me", "shutdown", [_hand(1.0)], {})
    log.set_outcome(p, "cancelled")
    assert json.loads(p.read_text(encoding="utf-8"))["outcome"] == "cancelled"
    log.set_outcome(tmp_path / "gone.json", "ran")      # missing file: no error


def test_records_older_than_24_hours_are_deleted(tmp_path):
    log = TriggerLog(tmp_path)
    old = log.record("Rock", "screenshot", [_hand(1.0)], {})
    new = log.record("Rock", "screenshot", [_hand(2.0)], {})
    day_ago = time.time() - 24 * 3600 - 60
    os.utime(old, (day_ago, day_ago))
    assert log.purge() == 1
    assert not old.exists() and new.exists() and (tmp_path / "README.txt").exists()


def test_hand_slots_report_the_hand_that_fired_with_its_history():
    slots = HandSlots(2)
    fired = []
    for i in range(40):                                  # ~2.6 s holding a peace sign
        t = i / 15
        f = FrameFeatures(t=t, hand=True, mp_label="Victory", mp_score=0.9,
                          palm_center=(0.5, 0.5), palm_size=0.2)
        slots.process(t, [f], "good", {"Victory"}, SENS)
        fired += slots.last_triggers
    assert len(fired) == 1
    gid, frames = fired[0]
    assert gid == "Victory" and frames
    assert frames[-1].t - frames[0].t <= HISTORY_SECONDS


class _GestureApp:
    def __init__(self, tmp_path, enabled=True):
        self.dispatched = []
        self.trigger_log = TriggerLog(tmp_path)
        maps = {"Victory": {"action": "lock_pc"}}
        values = {"trigger_log": enabled, "hand_strictness": 0.7}

        class cfg:
            mappings = staticmethod(lambda: maps)
            get = staticmethod(lambda k, d=None: values.get(k, d))
            sensitivity = staticmethod(lambda: dict(SENS))
        self.cfg = cfg

    def _detection_settings(self):
        return App._detection_settings(self)

    def _dispatch(self, gid, aid, params, log_path=None):
        self.dispatched.append((gid, aid, log_path))


def test_a_fired_gesture_is_logged_and_dispatched(tmp_path):
    app = _GestureApp(tmp_path)
    App.on_gesture(app, "Victory", [_hand(1.0)])
    (gid, aid, path), = app.dispatched
    assert (gid, aid) == ("Victory", "lock_pc") and path.exists()


def test_nothing_is_logged_when_turned_off(tmp_path):
    app = _GestureApp(tmp_path, enabled=False)
    App.on_gesture(app, "Victory", [_hand(1.0)])
    assert app.dispatched[0][2] is None
    assert not list(tmp_path.glob("trigger_*.json"))
