"""Media and system volume keys (work with Spotify, browsers, most players).

"Volume up / down" for the app that's playing live in app_volume.py.
"""
from __future__ import annotations

from visualcommand.actions.base import register_action
from visualcommand.actions.keys import press

_MEDIA = [
    # id, key to press, name, group, order
    ("media_play_pause", "media_play_pause", "Play / pause", "Media", 30),
    ("media_next", "media_next", "Next track", "Media", 31),
    ("media_prev", "media_prev", "Previous track", "Media", 32),
    ("system_volume_up", "volume_up", "System volume up", "Audio", 21),
    ("system_volume_down", "volume_down", "System volume down", "Audio", 22),
    ("volume_mute", "volume_mute", "Mute / unmute speakers", "Audio", 23),
]


def _make(action_id: str, key: str, name: str, group: str, order: int) -> None:
    def action(ctx, params):
        times = 3 if key in ("volume_up", "volume_down") else 1
        for _ in range(times):           # one key press is only 2%; three feels right
            press(key)
        return None

    register_action(action_id, name, group=group, order=order)(action)


for _row in _MEDIA:
    _make(*_row)
