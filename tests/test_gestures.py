import pytest

from visualcommand.engine import GestureEngine
from visualcommand.features import FrameFeatures
from visualcommand.gestures import catalogue, registry

SENS = {"hold_time": 0.4, "cooldown": 2.0, "min_score": 0.7}
OPEN = (True, True, True, True, True)


# Engine tests use Thumb_Up as an example pose; give the hand a valid thumbs-up shape.
THUMB_SHAPE = dict(thumb_lift=0.75, fist_tightness=0.2, thumb_angle=18.0)


def frame(t, label="None", score=0.0, hand=True, center=(0.5, 0.5), extended=OPEN, **kw):
    kw = {**THUMB_SHAPE, **kw}
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

def test_catalogue_has_builtin_and_rule_poses():
    ids = {g.id for g in catalogue()}
    assert {"Thumb_Up", "Closed_Fist", "Victory", "Open_Palm"} <= ids
    assert {"Pinch", "OK_Sign", "Rock", "Call_Me", "Point_Left"} <= ids


def test_no_motion_gestures_left():
    ids = {g.id for g in catalogue()}
    assert not any(i.startswith(("Swipe_", "Circle_", "Pinch_Drag")) for i in ids)
    assert not {"Push", "Wave"} & ids


def test_every_gesture_has_display_metadata():
    for g in catalogue():
        assert g.name and g.description and g.icon and callable(g().score)


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


def test_mapping_for_unknown_gesture_is_ignored():
    e = GestureEngine()
    fired = run(e, [frame(t, "Thumb_Up", 0.9) for t in steps(0, 1.0)], {"Swipe_Left", "Thumb_Up"})
    assert [g for _, g in fired] == ["Thumb_Up"]


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
    ("Point_Right", (True, True, False, False, False), 2.0, (1, 0)),
    ("Point_Left", (True, True, False, False, False), 2.0, (-1, 0)),
])
def test_rule_pose_matches_only_its_shape(gid, extended, pinch, index_dir):
    f = frame(0, extended=extended, pinch=pinch, index_dir=index_dir, thumb_index_angle=70)
    rule_ids = ["Rock", "Call_Me", "Three_Fingers", "OK_Sign", "Pinch", "Point_Right", "Point_Left"]
    matches = [r for r in rule_ids if registry()[r]().score(f) > 0]
    assert matches == [gid]


def _gun(**over):
    kw = dict(extended=(True, True, False, False, False), index_dir=(1.0, 0.0),
              thumb_index_angle=70.0, pinch=2.0)
    kw.update(over)
    return frame(0, **kw)


def test_finger_gun_points_both_ways_and_tolerates_tilt():
    reg = registry()
    assert reg["Point_Right"]().score(_gun()) > 0
    assert reg["Point_Left"]().score(_gun(index_dir=(-1.0, 0.0))) > 0
    # measured: pointing up to ~40 degrees above horizontal
    assert reg["Point_Left"]().score(_gun(index_dir=(-0.77, -0.64))) > 0
    assert reg["Point_Right"]().score(_gun(index_dir=(0.6, -0.8))) == 0   # too steep


def test_plain_pointing_with_thumb_tucked_is_not_a_finger_gun():
    """Measured: thumb lies along the index (11-20 degrees) when tucked."""
    reg = registry()
    tucked = _gun(extended=(False, True, False, False, False), thumb_index_angle=15)
    thumb_along = _gun(thumb_index_angle=15)
    for f in (tucked, thumb_along):
        assert reg["Point_Right"]().score(f) == 0


def test_finger_gun_needs_other_fingers_closed():
    assert registry()["Point_Right"]().score(_gun(extended=(True, True, True, False, False))) == 0
