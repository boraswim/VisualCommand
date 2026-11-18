"""Volume up/down change the app that's playing, not the whole PC."""
import math

from visualcommand import actions
from visualcommand.actions import app_volume as av


def test_target_is_the_app_making_sound():
    """Measured: Spotify playing ~0.5-0.7, idle Discord / driver helpers ~0.003."""
    peaks = {"Spotify.exe": 0.62, "Discord.exe": 0.004, "nvcontainer.exe": 0.003, "brave.exe": 0.0}
    assert av.pick_target(peaks, last=None) == "Spotify.exe"


def test_loudest_wins_when_two_play():
    assert av.pick_target({"Spotify.exe": 0.3, "brave.exe": 0.7}, last="Spotify.exe") == "brave.exe"


def test_nothing_playing_uses_last_adjusted_app_if_still_there():
    assert av.pick_target({"Spotify.exe": 0.0, "Discord.exe": 0.004}, last="Spotify.exe") == "Spotify.exe"
    assert av.pick_target({"Discord.exe": 0.004}, last="Spotify.exe") is None    # Spotify closed


class _Vol:
    def __init__(self, v):
        self.v = v

    def GetMasterVolume(self):
        return self.v

    def SetMasterVolume(self, v, ctx):
        self.v = v


def _fake(monkeypatch, volumes, peaks):
    apps = {name: [type("S", (), {"SimpleAudioVolume": _Vol(v)})() for v in vs]
            for name, vs in volumes.items()}
    monkeypatch.setattr(av, "_app_sessions", lambda: apps)
    monkeypatch.setattr(av, "_peaks", lambda a: dict(peaks))
    av._last_app["name"] = None
    return apps


def test_volume_down_changes_only_the_playing_app_by_an_audible_step(monkeypatch):
    """Regression: 1.0 -> 0.9 amplitude is ~1 dB, inaudible. One step must be 4 dB."""
    apps = _fake(monkeypatch, {"Spotify.exe": [1.0], "Discord.exe": [1.0]},
                 {"Spotify.exe": 0.6, "Discord.exe": 0.004})
    assert actions.run_action("volume_down", {}, ctx=None) == "Spotify volume 90%"
    level = apps["Spotify.exe"][0].SimpleAudioVolume.v
    assert abs(20 * math.log10(level) - (-4.0)) < 0.01            # -4 dB
    assert apps["Discord.exe"][0].SimpleAudioVolume.v == 1.0


def test_volume_up_at_full_volume_says_so(monkeypatch):
    """Regression: Spotify was already at 100%, so 'up' silently did nothing."""
    _fake(monkeypatch, {"Spotify.exe": [1.0]}, {"Spotify.exe": 0.6})
    assert actions.run_action("volume_up", {}, ctx=None) == "Spotify is already at full volume"


def test_ten_steps_cover_the_whole_range_both_ways():
    level = 1.0
    for _ in range(10):
        level = av.step_level(level, -1)
    assert level == 0.0
    for _ in range(10):
        level = av.step_level(level, +1)
    assert abs(level - 1.0) < 1e-9


def test_loudness_scale_round_trips():
    for pos in (0.1, 0.35, 0.5, 0.8, 1.0):
        assert abs(av.level_to_loudness(av.loudness_to_level(pos)) - pos) < 1e-9


def test_volume_down_clamps_at_zero_and_covers_all_sessions_of_the_app(monkeypatch):
    apps = _fake(monkeypatch, {"Discord.exe": [0.012, 0.012]}, {"Discord.exe": 0.5})
    assert actions.run_action("volume_down", {}, ctx=None) == "Discord volume 0%"
    assert all(s.SimpleAudioVolume.v == 0.0 for s in apps["Discord.exe"])


def test_nothing_playing_falls_back_to_system_volume(monkeypatch):
    _fake(monkeypatch, {"Discord.exe": [1.0]}, {"Discord.exe": 0.002})
    pressed = []
    import visualcommand.actions.keys as keys
    monkeypatch.setattr(keys, "press", lambda *k: pressed.append(k))
    assert "system volume up" in actions.run_action("volume_up", {}, ctx=None)
    assert pressed == [("volume_up",)] * 3


def test_system_volume_actions_still_available():
    specs = {a.id: a for a in actions.catalogue()}
    assert specs["system_volume_up"].group == "Audio" and specs["system_volume_down"].name
    assert specs["volume_up"].group == "Media"
