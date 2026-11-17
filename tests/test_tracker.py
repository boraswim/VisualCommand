import threading

from visualcommand.tracker import Tracker


class _FakeApp:
    class cfg:
        @staticmethod
        def get(key, default=None):
            return default
    paused_until = 0.0

    def on_tracker_status(self): pass
    def notify(self, *a, **k): pass


def test_tracker_does_not_shadow_thread_internals():
    """Regression: 0.1.1 stored an Event in `self._stop`, hiding Thread._stop(),
    so join() on quit raised "'Event' object is not callable"."""
    t = Tracker(_FakeApp())
    own = set(vars(t)) - set(vars(threading.Thread()))
    clashes = own & set(dir(threading.Thread))
    assert not clashes, f"Tracker attributes shadow threading.Thread: {clashes}"


def test_unstarted_tracker_can_be_stopped():
    t = Tracker(_FakeApp())
    t.stop()


def test_new_hands_are_detected_leniently_but_confirmed_strictly():
    """A pose made straight into the frame (fist, thumbs up) scores low on palm
    detection; strictness must not gate detection, only the hand-presence check."""
    from visualcommand.tracker import recognizer_thresholds
    th = recognizer_thresholds(0.7)
    assert th["min_hand_detection_confidence"] <= 0.5
    assert th["min_hand_presence_confidence"] == 0.7
    lenient = recognizer_thresholds(0.3)
    assert lenient["min_hand_detection_confidence"] == 0.3


def test_recognizer_builds_with_bundled_model():
    from visualcommand.tracker import create_recognizer
    rec = create_recognizer(0.7)
    rec.close()


def test_idle_fps_migrated_to_new_default(tmp_path):
    import json
    from visualcommand.config import Config
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"version": 3, "idle_fps": 4}), encoding="utf-8")
    assert Config(p).get("idle_fps") == 6
    p.write_text(json.dumps({"version": 3, "idle_fps": 2}), encoding="utf-8")
    assert Config(p).get("idle_fps") == 2          # user's own choice kept
