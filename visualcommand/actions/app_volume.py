"""Volume up / down for the app that's playing (e.g. Spotify), not the whole PC.

Uses Windows' per-app volume (the same sliders as the Volume mixer) via pycaw.
The target is the app currently making sound: each audio session's peak meter is
sampled briefly and the loudest one wins (measured: Spotify playing ~0.5-0.7,
idle apps like Discord or driver helpers ~0.003). If nothing is playing, the app
adjusted last is used; if there is none, the system volume changes instead.
"""
from __future__ import annotations

import logging
import math
import os
import time

from visualcommand.actions.base import register_action

log = logging.getLogger(__name__)

STEP = 0.10            # per gesture, on the loudness scale below (10 steps = full range)
RANGE_DB = 40.0        # loudness scale: 100% = full volume, 0% just above silence = -40 dB
ACTIVE_PEAK = 0.01     # a session louder than this is "playing"
SAMPLES, SAMPLE_GAP = 5, 0.03   # sample meters over ~0.15 s (music has quiet moments)

_last_app: dict[str, str | None] = {"name": None}


def pick_target(peaks: dict[str, float], last: str | None) -> str | None:
    """App to change: the loudest one playing, else the last one adjusted (if it
    still has audio), else None (= use the system volume)."""
    playing = {name: p for name, p in peaks.items() if p >= ACTIVE_PEAK}
    if playing:
        return max(playing, key=playing.get)
    if last and last in peaks:
        return last
    return None


def _app_sessions() -> dict[str, list]:
    """Audio sessions grouped by app, without system sounds and VisualCommand itself."""
    import comtypes
    from pycaw.pycaw import AudioUtilities

    comtypes.CoInitialize()  # safe to call repeatedly on the action thread
    own = os.getpid()
    apps: dict[str, list] = {}
    for s in AudioUtilities.GetAllSessions():
        if s.Process is None or s.ProcessId == own:
            continue
        try:
            name = s.Process.name()
        except Exception:
            continue
        apps.setdefault(name, []).append(s)
    return apps


def _peaks(apps: dict[str, list]) -> dict[str, float]:
    from pycaw.pycaw import IAudioMeterInformation

    meters = {name: [s._ctl.QueryInterface(IAudioMeterInformation) for s in ss]
              for name, ss in apps.items()}
    peaks = {name: 0.0 for name in apps}
    for i in range(SAMPLES):
        for name, ms in meters.items():
            for m in ms:
                peaks[name] = max(peaks[name], float(m.GetPeakValue()))
        if i < SAMPLES - 1:
            time.sleep(SAMPLE_GAP)
    return peaks


def _pretty(name: str) -> str:
    return name[:-4] if name.lower().endswith(".exe") else name


# Windows' per-app volume is a plain amplitude multiplier: 1.0 -> 0.9 is only ~1 dB,
# which you can hardly hear (the first version stepped like that and "did nothing").
# Steps are taken on a loudness scale instead: each 10% step is RANGE_DB/10 = 4 dB.
def level_to_loudness(level: float) -> float:
    """Amplitude (0..1) -> loudness position (0..1)."""
    if level <= 10 ** (-RANGE_DB / 20) + 1e-9:
        return 0.0
    return max(0.0, min(1.0, 1.0 + 20 * math.log10(level) / RANGE_DB))


def loudness_to_level(pos: float) -> float:
    """Loudness position (0..1) -> amplitude (0..1); 0 = silent."""
    if pos <= 1e-6:
        return 0.0
    return 10 ** ((min(pos, 1.0) - 1.0) * RANGE_DB / 20)


def step_level(level: float, direction: int) -> float:
    pos = round(level_to_loudness(level) / STEP) * STEP     # snap to the 10% grid
    return loudness_to_level(max(0.0, min(1.0, pos + direction * STEP)))


def change_app_volume(direction: int) -> str:
    apps = _app_sessions()
    peaks = _peaks(apps)
    target = pick_target(peaks, _last_app["name"])
    if target is None:
        from visualcommand.actions.keys import press
        for _ in range(3):
            press("volume_up" if direction > 0 else "volume_down")
        log.info("App volume: nothing playing, system volume %s", "up" if direction > 0 else "down")
        return "Nothing playing: system volume " + ("up" if direction > 0 else "down")
    sessions = apps[target]                      # an app can have several sessions
    before = max(s.SimpleAudioVolume.GetMasterVolume() for s in sessions)
    _last_app["name"] = target
    if direction > 0 and before >= 0.999:
        log.info("App volume: %s already at full volume", target)
        return f"{_pretty(target)} is already at full volume"
    level = step_level(before, direction)
    for s in sessions:
        s.SimpleAudioVolume.SetMasterVolume(level, None)
    pct = round(level_to_loudness(level) * 100)
    log.info("App volume: %s %.2f -> %.2f (%d%%), peak %.2f", target, before, level, pct,
             peaks.get(target, 0.0))
    return f"{_pretty(target)} volume {pct}%"


@register_action("volume_up", "Volume up",
                 "Turns up the app that's playing (e.g. Spotify) one clear step. If nothing "
                 "is playing: the app you adjusted last, else the system volume.",
                 "Media", order=33)
def volume_up(ctx, params):
    return change_app_volume(+1)


@register_action("volume_down", "Volume down",
                 "Turns down the app that's playing (e.g. Spotify) one clear step. If nothing "
                 "is playing: the app you adjusted last, else the system volume.",
                 "Media", order=34)
def volume_down(ctx, params):
    return change_app_volume(-1)
