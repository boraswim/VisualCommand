import json

from visualcommand import actions
from visualcommand.config import DEFAULTS, Config
from visualcommand.gestures import registry as gesture_registry, load_all


def test_defaults_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(path)
    assert cfg.first_run
    cfg.set_mapping("Wave", "media_play_pause")
    cfg.set_sensitivity("hold_time", 0.8)
    again = Config(path)
    assert not again.first_run
    assert again.mappings()["Wave"]["action"] == "media_play_pause"
    assert again.sensitivity()["hold_time"] == 0.8
    assert again.sensitivity()["cooldown"] == DEFAULTS["sensitivity"]["cooldown"]


def test_old_config_gains_new_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"sensitivity": {"hold_time": 1.0}, "mappings": {}}), encoding="utf-8")
    cfg = Config(path)
    assert cfg.sensitivity()["hold_time"] == 1.0
    assert "cooldown" in cfg.sensitivity()
    assert cfg.mappings() == {}          # user's (empty) mapping is kept, not re-filled
    assert cfg.get("lighting_mode") == "auto"


def test_clearing_a_mapping(tmp_path):
    cfg = Config(tmp_path / "c.json")
    cfg.set_mapping("Thumb_Up", "none")
    assert "Thumb_Up" not in cfg.mappings()


def test_corrupt_config_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert Config(path).mappings() == DEFAULTS["mappings"]


def test_default_mappings_reference_real_gestures_and_actions():
    load_all()
    acts = {a.id for a in actions.catalogue()}
    for gid, m in DEFAULTS["mappings"].items():
        assert gid in gesture_registry()
        assert m["action"] in acts


def test_action_catalogue():
    ids = {a.id for a in actions.catalogue()}
    assert {"screenshot", "mute_mic", "lock_pc", "media_play_pause", "media_next",
            "media_prev", "volume_up", "run_command", "pause_tracking"} <= ids
    for a in actions.catalogue():
        assert a.name
