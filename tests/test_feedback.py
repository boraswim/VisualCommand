"""Popup + sound after an action, and silence for Test-button runs."""
import wave

from visualcommand.main import App
from visualcommand.paths import resource_path
from visualcommand.sound import SOUNDS

fb = App.feedback_for


def test_gesture_action_gets_popup_and_sound():
    assert fb(True, "screenshot", "Screenshot saved", False, True, True) == (True, "action")


def test_test_button_gets_no_popup_and_no_sound():
    assert fb(False, "screenshot", "Screenshot saved", False, True, True) == (False, None)
    assert fb(False, "mute_mic", "boom", True, True, True) == (False, None)   # even on error


def test_failed_gesture_action_plays_error_sound_and_always_shows():
    assert fb(True, "run_command", "Couldn't run", True, False, True) == (True, "error")


def test_settings_turn_popup_and_sound_off_separately():
    assert fb(True, "screenshot", "ok", False, False, True) == (False, "action")
    assert fb(True, "screenshot", "ok", False, True, False) == (True, None)


def test_lock_pc_plays_sound_but_no_popup():
    assert fb(True, "lock_pc", None, False, True, True) == (False, "action")


def test_sound_files_are_short_valid_wavs():
    for rel in SOUNDS.values():
        with wave.open(str(resource_path(rel))) as w:
            seconds = w.getnframes() / w.getframerate()
            assert w.getnchannels() == 1 and 0.05 < seconds < 0.6
