import math

import pytest

from visualcommand.engine import GestureEngine
from visualcommand.features import FrameFeatures
from visualcommand.gestures import MOTION, POSE, catalogue, registry

SENS = {"hold_time": 0.4, "cooldown": 2.0, "min_score": 0.7, "swipe_distance": 0.3}
OPEN = (True, True, True, True, True)
FIST = (False,) * 5


def frame(t, label="None", score=0.0, hand=True, center=(0.5, 0.5), extended=OPEN, **kw):
    return FrameFeatures(t=t, hand=hand, mp_label=label, mp_score=score,
                         palm_center=center, extended=extended, palm_size=0.2, **kw)


def run(engine, frames, active, sens=SENS, **kw):
    fired = []
    for f in frames:
        fired += [(round(f.t, 2), g) for g in engine.process(f, set(active), sens, **kw)]
    return fired


def steps(t0, t1, fps=15):
    n = int(round((t1 - t0) * fps))
    return [t0 + i / fps for i in range(n)]


# --- catalogue -------------------------------------------------------------------

def test_catalogue_has_builtin_rule_and_motion_gestures():
    ids = {g.id for g in catalogue()}
    assert {"Thumb_Up", "Closed_Fist", "Victory", "Open_Palm"} <= ids
    assert {"Pinch", "OK_Sign", "Rock", "Call_Me", "Point_Left"} <= ids
    assert {"Swipe_Left", "Swipe_Right", "Swipe_Up", "Swipe_Down", "Push", "Wave",
            "Circle_CW", "Pinch_Drag_Up"} <= ids


def test_every_gesture_has_display_metadata():
    for g in catalogue():
        assert g.name and g.description and g.icon and g.kind in (POSE, MOTION)


def test_poses_listed_before_motions():
    kinds = [g.kind for g in catalogue()]
    assert kinds == sorted(kinds, key=lambda k: k != POSE)


# --- pose debouncing -------------------------------------------------------------

def test_pose_fires_only_after_hold_time():
    e = GestureEngine()
    fired = run(e, [frame(t, "Thumb_Up", 0.9) for t in steps(0, 1.0)], {"Thumb_Up"})
    assert len(fired) == 1
    assert 0.4 <= fired[0][0] < 0.5


def test_pose_does_not_fire_when_held_too_briefly():
    e = GestureEngine()
    frames = [frame(t, "Thumb_Up", 0.9) for t in steps(0, 0.3)] + \
             [frame(t, hand=False) for t in steps(0.3, 1.0)]
    assert run(e, frames, {"Thumb_Up"}) == []


def test_low_score_ignored():
    e = GestureEngine()
    assert run(e, [frame(t, "Thumb_Up", 0.5) for t in steps(0, 1.0)], {"Thumb_Up"}) == []


def test_holding_pose_fires_once_until_released():
    e = GestureEngine()
    fired = run(e, [frame(t, "Thumb_Up", 0.9) for t in steps(0, 5.0)], {"Thumb_Up"})
    assert len(fired) == 1


def test_refire_needs_release_and_cooldown():
    e = GestureEngine()
    hold = lambda a, b: [frame(t, "Thumb_Up", 0.9) for t in steps(a, b)]
    gone = lambda a, b: [frame(t, hand=False) for t in steps(a, b)]
    # second hold starts at 1.0 s: inside the 2 s cooldown -> no fire
    # third hold starts at 3.0 s: after cooldown -> fires
    fired = run(e, hold(0, 0.6) + gone(0.6, 1.0) + hold(1.0, 1.6) + gone(1.6, 3.0) + hold(3.0, 3.6),
                {"Thumb_Up"})
    assert [g for _, g in fired] == ["Thumb_Up", "Thumb_Up"]
    assert fired[1][0] >= 3.4


def test_brief_dropout_does_not_restart_hold():
    e = GestureEngine()
    frames = [frame(t, "Thumb_Up", 0.9) for t in steps(0, 0.3)]
    frames += [frame(0.3 + 1 / 15, hand=False)]           # one missed frame
    frames += [frame(t, "Thumb_Up", 0.9) for t in steps(0.4, 0.8)]
    fired = run(e, frames, {"Thumb_Up"})
    assert len(fired) == 1 and fired[0][0] < 0.55


def test_unmapped_gestures_are_not_evaluated():
    e = GestureEngine()
    assert run(e, [frame(t, "Thumb_Up", 0.9) for t in steps(0, 1.0)], {"Victory"}) == []
    assert "Thumb_Up" not in e._instances


def test_low_light_requires_longer_hold():
    e = GestureEngine()
    frames = [frame(t, "Thumb_Up", 0.9, lighting="low") for t in steps(0, 1.0)]
    fired = run(e, frames, {"Thumb_Up"})
    assert fired and fired[0][0] >= 0.52   # 0.4 s * 1.3


# --- arm gesture -----------------------------------------------------------------

def test_arm_gesture_gates_other_gestures():
    e = GestureEngine()
    kw = dict(arm_id="ILoveYou", arm_window=3.0)
    # Thumb up without arming: blocked
    assert run(e, [frame(t, "Thumb_Up", 0.9) for t in steps(0, 1.0)], {"Thumb_Up"}, **kw) == []
    # Arm, then thumb up: allowed (arm itself is not reported because it isn't mapped)
    frames = [frame(t, "ILoveYou", 0.9) for t in steps(1.0, 1.6)] + \
             [frame(t, "Thumb_Up", 0.9) for t in steps(1.6, 2.4)]
    fired = run(e, frames, {"Thumb_Up"}, **kw)
    assert [g for _, g in fired] == ["Thumb_Up"]


# --- rule poses ------------------------------------------------------------------

@pytest.mark.parametrize("gid, extended, pinch, index_dir", [
    ("Rock", (False, True, False, False, True), 2.0, (0, -1)),
    ("Call_Me", (True, False, False, False, True), 2.0, (0, -1)),
    ("Three_Fingers", (False, True, True, True, False), 2.0, (0, -1)),
    ("OK_Sign", (False, False, True, True, True), 0.1, (0, -1)),
    ("Pinch", (True, True, False, False, False), 0.1, (0, -1)),
    ("Point_Right", (False, True, False, False, False), 2.0, (1, 0)),
    ("Point_Left", (False, True, False, False, False), 2.0, (-1, 0)),
])
def test_rule_pose_matches_only_its_shape(gid, extended, pinch, index_dir):
    f = frame(0, extended=extended, pinch=pinch, index_dir=index_dir)
    rule_ids = ["Rock", "Call_Me", "Three_Fingers", "OK_Sign", "Pinch", "Point_Right", "Point_Left"]
    matches = [r for r in rule_ids if registry()[r]().score(f) > 0]
    assert matches == [gid]


# --- motions ---------------------------------------------------------------------

def _move(t0, t1, start, end, fps=15, **kw):
    ts = steps(t0, t1, fps)
    n = len(ts) - 1 or 1
    return [frame(t, center=(start[0] + (end[0] - start[0]) * i / n,
                             start[1] + (end[1] - start[1]) * i / n), **kw)
            for i, t in enumerate(ts)]


@pytest.mark.parametrize("gid, start, end", [
    ("Swipe_Right", (0.2, 0.5), (0.7, 0.5)),
    ("Swipe_Left", (0.8, 0.5), (0.3, 0.5)),
    ("Swipe_Up", (0.5, 0.8), (0.5, 0.3)),
    ("Swipe_Down", (0.5, 0.2), (0.5, 0.7)),
])
def test_fast_swipe_fires_in_its_direction_only(gid, start, end):
    e = GestureEngine()
    active = {"Swipe_Left", "Swipe_Right", "Swipe_Up", "Swipe_Down"}
    fired = run(e, _move(0, 0.4, start, end), active)
    assert [g for _, g in fired] == [gid]


def test_slow_drift_is_not_a_swipe():
    e = GestureEngine()
    assert run(e, _move(0, 3.0, (0.1, 0.5), (0.9, 0.5)), {"Swipe_Right"}) == []


def test_swipe_needs_open_hand():
    e = GestureEngine()
    assert run(e, _move(0, 0.4, (0.2, 0.5), (0.8, 0.5), extended=FIST), {"Swipe_Right"}) == []


def test_diagonal_move_is_not_a_swipe():
    e = GestureEngine()
    assert run(e, _move(0, 0.4, (0.2, 0.2), (0.6, 0.6)), {"Swipe_Right", "Swipe_Down"}) == []


def test_swipe_fires_once_per_stroke():
    e = GestureEngine()
    fired = run(e, _move(0, 0.8, (0.05, 0.5), (0.95, 0.5)), {"Swipe_Right"})
    assert len(fired) == 1


def test_swipe_survives_tracking_dropouts():
    """Motion blur makes MediaPipe lose the hand for a frame or two mid-swipe."""
    e = GestureEngine()
    frames = _move(0, 0.5, (0.2, 0.5), (0.7, 0.5))
    for i in (3, 4):                      # two lost frames in the middle
        frames[i] = frame(frames[i].t, hand=False)
    assert [g for _, g in run(e, frames, {"Swipe_Right"})] == ["Swipe_Right"]


def test_swipe_with_half_curled_fingers_mid_motion():
    e = GestureEngine()
    frames = _move(0, 0.5, (0.2, 0.5), (0.7, 0.5))
    for i in range(1, len(frames), 3):    # every third frame looks like a fist
        frames[i].extended = FIST
    assert [g for _, g in run(e, frames, {"Swipe_Right"})] == ["Swipe_Right"]


def test_curved_swipe_counts():
    e = GestureEngine()
    ts = steps(0, 0.5)
    frames = [frame(t, center=(0.2 + 0.5 * i / (len(ts) - 1),
                               0.5 - 0.12 * math.sin(math.pi * i / (len(ts) - 1))))
              for i, t in enumerate(ts)]
    assert [g for _, g in run(e, frames, {"Swipe_Right", "Swipe_Up"})] == ["Swipe_Right"]


def test_long_absence_resets_swipe():
    e = GestureEngine()
    frames = _move(0, 0.3, (0.2, 0.5), (0.4, 0.5)) + \
             [frame(t, hand=False) for t in steps(0.3, 1.0)] + \
             _move(1.0, 1.2, (0.5, 0.5), (0.55, 0.5))
    assert run(e, frames, {"Swipe_Right"}) == []


def test_wave_detected():
    e = GestureEngine()
    frames = []
    for i, t in enumerate(steps(0, 1.4)):
        x = 0.5 + 0.12 * math.sin(2 * math.pi * 2.0 * t)   # 2 Hz side-to-side
        frames.append(frame(t, center=(x, 0.5)))
    fired = run(e, frames, {"Wave"})
    assert [g for _, g in fired] == ["Wave"]


@pytest.mark.parametrize("gid, direction", [("Circle_CW", 1), ("Circle_CCW", -1)])
def test_circle_direction(gid, direction):
    e = GestureEngine()
    pointing = (False, True, False, False, False)
    frames = []
    for t in steps(0, 1.5, fps=20):
        a = direction * 2 * math.pi * t / 1.2   # one full turn in 1.2 s
        frames.append(frame(t, extended=pointing,
                            index_tip=(0.5 + 0.1 * math.cos(a), 0.5 + 0.1 * math.sin(a))))
    fired = run(e, frames, {"Circle_CW", "Circle_CCW"})
    assert [g for _, g in fired] == [gid]


def test_push_detected():
    e = GestureEngine()
    frames = []
    for i, t in enumerate(steps(0, 0.4)):
        f = frame(t)
        f.palm_size = 0.15 + 0.1 * i / 6
        frames.append(f)
    assert [g for _, g in run(e, frames, {"Push"})] == ["Push"]
