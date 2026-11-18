"""Gestures only count when the hand is clearly shown to the camera."""
import numpy as np

from visualcommand.deliberate import hand_height, presentation_problem
from visualcommand.engine import GestureEngine
from visualcommand.features import FrameFeatures

SENS = {"hold_time": 0.4, "cooldown": 2.0, "min_score": 0.55, "gesture_zone": 0.60}


def hand_at(cy, size=0.16, width=0.7, half=0.12, t=0.0, label="Victory", score=0.9):
    """A hand whose outline spans cy-half .. cy+half vertically."""
    lm = np.zeros((21, 2), np.float32)
    lm[:, 0] = np.linspace(0.40, 0.55, 21)
    lm[:, 1] = np.linspace(cy - half, cy + half, 21)
    return FrameFeatures(t=t, hand=True, landmarks=lm, palm_center=(0.47, cy + half / 2),
                         palm_size=size, palm_width=width, mp_label=label, mp_score=score)


def test_raised_hand_shown_to_camera_counts():
    assert presentation_problem(hand_at(0.42)) is None


def test_measured_false_triggers_are_rejected():
    """Values from trigger-log records that were all false triggers."""
    assert "low" in presentation_problem(hand_at(0.89, size=0.04))        # resting at the bottom
    assert "low" in presentation_problem(hand_at(0.72, size=0.11))
    assert "small" in presentation_problem(hand_at(0.42, size=0.04))
    assert "toward" in presentation_problem(hand_at(0.42, width=1.06))     # foreshortened
    cut = hand_at(0.42)
    cut.landmarks[3, 1] = -0.05
    assert "out of view" in presentation_problem(cut)


def test_height_uses_the_middle_of_the_hand_not_the_palm():
    """A thumbs up's palm sits low under the raised thumb."""
    f = hand_at(0.55, half=0.15)
    f.palm_center = (0.47, 0.66)              # palm below the line ...
    assert abs(hand_height(f) - 0.55) < 1e-6  # ... but the hand as a whole is raised
    assert presentation_problem(f) is None


def test_zone_is_adjustable():
    f = hand_at(0.65)
    assert presentation_problem(f, zone=0.60) is not None
    assert presentation_problem(f, zone=0.70) is None


def _run(frames, active=frozenset({"Victory"})):
    e = GestureEngine()
    fired = []
    for f in frames:
        fired += e.process(f, set(active), SENS)
    return fired, e


def test_resting_hand_never_fires_and_says_why():
    frames = [hand_at(0.75, t=i / 15) for i in range(30)]
    fired, e = _run(frames)
    assert fired == [] and "low" in e.last_problem


def test_flickering_pose_does_not_fire():
    """The false triggers flipped between finger readings during the hold."""
    frames = []
    for i in range(30):
        f = hand_at(0.42, t=i / 15)
        if i % 3 == 0:                        # every third frame: a different reading
            f.mp_label = "None"
        frames.append(f)
    fired, _ = _run(frames)
    assert fired == []


def test_steady_raised_pose_fires():
    fired, e = _run([hand_at(0.42, t=i / 15) for i in range(15)])
    assert fired == ["Victory"] and e.last_problem is None
