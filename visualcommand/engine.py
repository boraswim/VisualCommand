"""Turns per-frame features into gesture events (hold time, cooldown, re-arm, arm gesture)."""
from __future__ import annotations

from visualcommand.deliberate import DEFAULT_ZONE, MIN_STEADY, presentation_problem
from visualcommand.features import FrameFeatures
from visualcommand.gestures import catalogue
from visualcommand.lighting import GOOD

GRACE = 0.25            # a pose may drop out for this long without restarting its hold


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
        self._suppress_until = 0.0
        self._frames = 0          # frames since the current candidate pose started
        self._matches = 0         # ...of which actually showed it
        self.last_pose: tuple[str, float] = ("", 0.0)   # for the preview overlay
        self.last_problem: str | None = None             # why the hand didn't count (preview)

    def _instance(self, gid: str):
        inst = self._instances.get(gid)
        if inst is None and gid in self._classes:
            inst = self._instances[gid] = self._classes[gid]()
        return inst

    def suppress(self, until: float) -> None:
        self._suppress_until = max(self._suppress_until, until)

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
        t = f.t

        def allowed(gid: str) -> bool:
            """Arm gating. Blocked gestures don't start a cooldown."""
            if not arm_id:
                return True
            if gid == arm_id:
                self.arm.armed_until = t + arm_window
                return True
            return t <= self.arm.armed_until

        # A pose only counts while the hand is clearly shown to the camera.
        self.last_problem = presentation_problem(f, sens.get("gesture_zone", DEFAULT_ZONE)) \
            if f.hand else None
        best, best_score = None, 0.0
        if f.hand and self.last_problem is None:
            for gid in wanted:
                inst = self._instance(gid)
                if inst is None:
                    continue        # e.g. a mapping left over from a removed gesture
                s = inst.score(f)
                if s >= min_score and s > best_score:
                    best, best_score = gid, s
        self.last_pose = (best or "", best_score)

        if best is not None:
            if best != self._candidate:
                self._candidate, self._since, self._fired = best, t, False
                self._frames = self._matches = 0
            self._last_seen = t
        elif self._candidate is not None and t - self._last_seen > GRACE:
            self._candidate, self._fired = None, False   # hand left the pose: re-armed
        if self._candidate is not None:
            self._frames += 1
            self._matches += best == self._candidate

        c = self._candidate
        steady = self._frames > 0 and self._matches / self._frames >= MIN_STEADY
        if (c is not None and best == c and not self._fired and t - self._since >= hold
                and steady
                and t >= self._suppress_until
                and t - self._last_fire.get(c, -1e9) >= cooldown
                and allowed(c)):
            self._fired = True
            self._last_fire[c] = t
            if c in active_ids:
                return [c]
        return []
