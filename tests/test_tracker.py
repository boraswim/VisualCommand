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


class _CfgApp(_FakeApp):
    def __init__(self, mirror=True):
        self.values = {"mirror_image": mirror}
        app = self

        class cfg:
            @staticmethod
            def get(key, default=None):
                return app.values.get(key, default)

            @staticmethod
            def set(key, value, save=True):
                app.values[key] = value
        self.cfg = cfg


def _hand(label, score=0.98):
    from visualcommand.features import FrameFeatures
    f = FrameFeatures(t=0, hand=True, handedness=label)
    f.extra["handedness_score"] = score
    return f


def _run_check(app, label, frames=30):
    t = Tracker(app)
    results = []
    t.check_orientation(lambda msg, ok: results.append((msg, ok)), seconds=10)
    for i in range(frames):
        t._feed_orientation_check([_hand(label)] if label else [], 1e9 if i == frames - 1 else 0)
    return results


def test_orientation_check_flips_when_right_hand_reads_as_left():
    """Regression: this user's webcam already mirrors; the app's extra flip made
    MediaPipe see the right hand as a left hand."""
    app = _CfgApp(mirror=True)
    results = _run_check(app, "Left")
    assert app.values["mirror_image"] is False and results[-1][1] is True


def test_orientation_check_keeps_correct_setting():
    app = _CfgApp(mirror=False)
    results = _run_check(app, "Right")
    assert app.values["mirror_image"] is False and "correct" in results[-1][0]


def test_orientation_check_needs_a_hand():
    app = _CfgApp(mirror=True)
    results = _run_check(app, None)
    assert app.values["mirror_image"] is True and results[-1][1] is False


def test_min_score_migrated_to_new_default(tmp_path):
    import json
    from visualcommand.config import Config
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"version": 4, "sensitivity": {"min_score": 0.7}}), encoding="utf-8")
    assert Config(p).sensitivity()["min_score"] == 0.55
    p.write_text(json.dumps({"version": 4, "sensitivity": {"min_score": 0.8}}), encoding="utf-8")
    assert Config(p).sensitivity()["min_score"] == 0.8


def test_idle_fps_migrated_to_new_default(tmp_path):
    import json
    from visualcommand.config import Config
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"version": 3, "idle_fps": 4}), encoding="utf-8")
    assert Config(p).get("idle_fps") == 6
    p.write_text(json.dumps({"version": 3, "idle_fps": 2}), encoding="utf-8")
    assert Config(p).get("idle_fps") == 2          # user's own choice kept
