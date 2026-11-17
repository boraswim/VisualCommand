"""Short feedback sounds, played asynchronously with Windows' built-in winsound.

Sounds: assets/sounds/action.wav and error.wav (processed from Kenney's CC0
Interface Sounds, see assets/sounds/CREDITS.txt and scripts/make_sounds.py).
"""
from __future__ import annotations

import logging

from visualcommand.paths import resource_path

log = logging.getLogger(__name__)

SOUNDS = {
    "action": "assets/sounds/action.wav",        # a gesture ran an action
    "error": "assets/sounds/error.wav",          # the action failed
    "attention": "assets/sounds/attention.wav",  # power action waiting for confirmation
}


def play(name: str = "action") -> bool:
    """Start playing a sound and return immediately. Returns False if it couldn't."""
    path = resource_path(SOUNDS.get(name, SOUNDS["action"]))
    if not path.exists():
        log.warning("Sound file missing: %s", path)
        return False
    try:
        import winsound
        # ASYNC: never blocks the action thread. NODEFAULT: no Windows "ding" if it fails.
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC
                           | winsound.SND_NODEFAULT)
        return True
    except Exception:
        log.exception("Could not play sound %s", name)
        return False
