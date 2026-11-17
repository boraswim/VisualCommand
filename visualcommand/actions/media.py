"""Media and volume keys (work with Spotify, browsers, most players)."""
from __future__ import annotations

from visualcommand.actions.base import register_action
from visualcommand.actions.keys import press

_MEDIA = [
    ("media_play_pause", "Play / pause", 30),
    ("media_next", "Next track", 31),
    ("media_prev", "Previous track", 32),
    ("volume_up", "Volume up", 33),
    ("volume_down", "Volume down", 34),
    ("volume_mute", "Mute / unmute speakers", 35),
]


def _make(key: str, name: str, order: int) -> None:
    def action(ctx, params):
        times = 3 if key.startswith("volume_") and key != "volume_mute" else 1
        for _ in range(times):           # one key press is only 2%; three feels right
            press(key)
        return None

    register_action(key, name, group="Media", order=order)(action)


for _key, _name, _order in _MEDIA:
    _make(_key, _name, _order)
