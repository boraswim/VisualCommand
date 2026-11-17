"""Up to two hands at once.

MediaPipe returns hands in no fixed order, so each detection is matched to a
"slot" by distance to where a hand was last seen. Every slot has its own
GestureEngine (so each hand's hold timer is its own), and a gesture fired by
either hand is de-duplicated by a shared cooldown.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from visualcommand.engine import ArmState, GestureEngine
from visualcommand.features import FrameFeatures

MATCH_DISTANCE = 0.3   # max palm movement between frames to count as the same hand
FORGET_AFTER = 0.5     # a slot is free again after its hand has been gone this long


@dataclass
class Slot:
    engine: GestureEngine
    center: tuple[float, float] | None = None
    last_seen: float = -1e9
    current: FrameFeatures | None = field(default=None, repr=False)


class HandSlots:
    def __init__(self, n: int = 2) -> None:
        self.arm = ArmState()
        self.slots = [Slot(GestureEngine(self.arm)) for _ in range(n)]
        self._last_fire: dict[str, float] = {}

    def _assign(self, t: float, hands: list[FrameFeatures]) -> list[FrameFeatures | None]:
        for s in self.slots:
            if s.center is not None and t - s.last_seen > FORGET_AFTER:
                s.center = None
        out: list[FrameFeatures | None] = [None] * len(self.slots)
        free = list(hands)
        # 1) keep known hands in their slot (closest pairs first)
        pairs = []
        for si, s in enumerate(self.slots):
            if s.center is None:
                continue
            for h in free:
                d = math.dist(s.center, h.palm_center)
                if d <= MATCH_DISTANCE:
                    pairs.append((d, si, h))
        for _, si, h in sorted(pairs, key=lambda p: p[0]):
            if out[si] is None and any(h is x for x in free):
                out[si] = h
                free = [x for x in free if x is not h]
        # 2) new hands take empty slots
        for si, s in enumerate(self.slots):
            if out[si] is None and s.center is None and free:
                out[si] = free.pop(0)
        return out

    def process(self, t: float, hands: list[FrameFeatures], lighting: str, active_ids: set[str],
                sens: dict, arm_id: str = "", arm_window: float = 5.0) -> list[str]:
        events: list[str] = []
        cooldown = sens.get("cooldown", 2.0)
        for slot, f in zip(self.slots, self._assign(t, hands)):
            if f is None:
                f = FrameFeatures(t=t, lighting=lighting)
            else:
                slot.center, slot.last_seen = f.palm_center, t
            slot.current = f
            for gid in slot.engine.process(f, active_ids, sens, arm_id, arm_window):
                if t - self._last_fire.get(gid, -1e9) < cooldown:
                    continue        # the other hand just did the same thing
                self._last_fire[gid] = t
                events.append(gid)
        return events

    def suppress(self, t: float, seconds: float) -> None:
        """Ignore gestures for a moment (e.g. right after the camera starts)."""
        for s in self.slots:
            s.engine.suppress(t + seconds)
