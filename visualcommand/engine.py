"""Turns per-frame features into gesture events (debouncing, cooldowns, arm gesture)."""
from __future__ import annotations

from visualcommand.features import FrameFeatures
from visualcommand.gestures import MOTION, POSE, catalogue
from visualcommand.lighting import GOOD

GRACE = 0.25            # a pose may drop out for this long without restarting its hold
MOTION_COOLDOWN = 1.0   # motions are quick; cap their cooldown at this
POSE_SUPPRESS = 0.6     # after a motion fires, ignore poses briefly (the hand is mid-move)


class ArmState:
    """Shared between the per-hand engines: arming with one hand unlocks both."""
    armed_until = 0.0


class GestureEngine:
    def __init__(self, arm: ArmState | None = None) -> None:
        self.arm = arm or ArmState()
        self._classes = {g.id: g for g in catalogue()}
        self._instances: dict[str, object] = {}
        self._candidate: str | None = None
        self._since = 0.0
        self._last_seen = 0.0
        self._fired = False
        self._last_fire: dict[str, float] = {}
        self._suppress_poses_until = 0.0
        self.last_pose: tuple[str, float] = ("", 0.0)   # for the preview overlay

    def _instance(self, gid: str):
        inst = self._instances.get(gid)
        if inst is None and gid in self._classes:
            inst = self._instances[gid] = self._classes[gid]()
        return inst

    def _reset_motions(self) -> None:
        for gid, inst in self._instances.items():
            if self._classes[gid].kind == MOTION:
                inst.reset()

    def process(self, f: FrameFeatures, active_ids: set[str], sens: dict,
                arm_id: str = "", arm_window: float = 5.0) -> list[str]:
        """Return gesture ids that fired on this frame.

        Only gestures in `active_ids` (the mapped ones) plus the arm gesture are
        evaluated, so unused catalogue entries cost nothing.
        """
        wanted = set(active_ids)
        if arm_id:
            wanted.add(arm_id)
        hold = sens.get("hold_time", 0.4)
        min_score = sens.get("min_score", 0.7)
        cooldown = sens.get("cooldown", 2.0)
        if f.lighting != GOOD:
            # Harder scene: accept a slightly weaker match but ask for a longer hold.
            min_score -= 0.1
            hold *= 1.3

        events: list[str] = []
        t = f.t

        def allowed(gid: str) -> bool:
            """Arm gating. Blocked gestures don't start a cooldown."""
            if not arm_id:
                return True
            if gid == arm_id:
                self.arm.armed_until = t + arm_window
                return True
            return t <= self.arm.armed_until

        # --- motions ---
        motion_fired = False
        for gid in wanted:
            cls = self._classes.get(gid)
            if cls is None or cls.kind != MOTION:
                continue
            if (self._instance(gid).update(f, sens)
                    and t - self._last_fire.get(gid, -1e9) >= min(cooldown, MOTION_COOLDOWN)
                    and allowed(gid)):
                self._last_fire[gid] = t
                motion_fired = True
                if gid in active_ids:
                    events.append(gid)
        if motion_fired:
            self._reset_motions()
            self._suppress_poses_until = t + POSE_SUPPRESS
            self._candidate, self._fired = None, False

        # --- poses ---
        best, best_score = None, 0.0
        for gid in wanted:
            cls = self._classes.get(gid)
            if cls is None or cls.kind != POSE:
                continue
            s = self._instance(gid).score(f)
            if s >= min_score and s > best_score:
                best, best_score = gid, s
        self.last_pose = (best or "", best_score)

        if best is not None:
            if best != self._candidate:
                self._candidate, self._since, self._fired = best, t, False
            self._last_seen = t
        elif self._candidate is not None and t - self._last_seen > GRACE:
            self._candidate, self._fired = None, False   # hand left the pose: re-armed

        c = self._candidate
        if (c is not None and best == c and not self._fired and t - self._since >= hold
                and t >= self._suppress_poses_until
                and t - self._last_fire.get(c, -1e9) >= cooldown
                and allowed(c)):
            self._fired = True
            self._last_fire[c] = t
            self._reset_motions()
            if c in active_ids:
                events.append(c)
        return events
