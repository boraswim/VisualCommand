"""Take screenshot captures only the main (primary) display."""
from visualcommand.actions.system import primary_monitor

ALL = {"left": 0, "top": 0, "width": 4480, "height": 1443}
MAIN = {"left": 0, "top": 0, "width": 2560, "height": 1440, "is_primary": True}
SIDE = {"left": 2560, "top": 363, "width": 1920, "height": 1080, "is_primary": False}


def test_uses_the_display_marked_primary():
    assert primary_monitor([ALL, MAIN, SIDE]) is MAIN
    assert primary_monitor([ALL, SIDE, MAIN]) is MAIN        # order doesn't matter


def test_falls_back_to_the_display_at_origin():
    main = {k: v for k, v in MAIN.items() if k != "is_primary"}
    side = {k: v for k, v in SIDE.items() if k != "is_primary"}
    assert primary_monitor([ALL, side, main]) is main


def test_never_the_whole_desktop_when_displays_are_listed():
    side_left = {"left": -1920, "top": 0, "width": 1920, "height": 1080}
    assert primary_monitor([ALL, side_left]) is side_left    # not monitors[0]


def test_clicking_the_screenshot_popup_runs_its_action(tk_root):
    from visualcommand.toast import Toast
    t, clicked = Toast(tk_root), []
    assert t.show("👍 Thumbs up", "Screenshot saved: x.png", on_click=lambda: clicked.append(1),
                  click_hint="Click to open the folder")
    tk_root.update()
    t._win.event_generate("<Button-1>")
    tk_root.update()
    assert clicked == [1] and t._win is None


def test_clicking_a_plain_popup_only_closes_it(tk_root):
    from visualcommand.toast import Toast
    t = Toast(tk_root)
    t.show("✊ Fist", "Microphone muted")
    tk_root.update()
    t._win.event_generate("<Button-1>")
    tk_root.update()
    assert t._win is None


def test_reveal_selects_the_file_in_explorer(tmp_path, monkeypatch):
    from visualcommand.actions import system
    shot = tmp_path / "Screenshot_1.png"
    shot.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(system.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    system.reveal_in_explorer(shot)
    assert calls == [["explorer", f"/select,{shot}"]]


def test_reveal_falls_back_to_the_folder(tmp_path, monkeypatch):
    from visualcommand.actions import system
    opened = []
    monkeypatch.setattr(system.os, "startfile", lambda p: opened.append(p))
    system.reveal_in_explorer(tmp_path / "deleted.png")
    assert opened == [tmp_path]


def test_other_actions_still_return_plain_messages():
    from visualcommand import actions
    r = actions.run_action_result("pause_tracking", {}, ctx=type("C", (), {"pause": lambda self, minutes: None})())
    assert r.message == "Tracking paused for 10 minutes" and r.reveal is None


def test_real_capture_matches_primary_size(tmp_path, monkeypatch):
    """Takes a real screenshot of the primary display into a temp folder."""
    from visualcommand.actions import system
    monkeypatch.setattr(system, "screenshots_dir", lambda: tmp_path)
    result = system.screenshot(ctx=None, params={})
    files = list(tmp_path.glob("Screenshot_*.png"))
    assert result.message.startswith("Screenshot saved") and len(files) == 1
    assert result.reveal == files[0]           # clicking the popup selects this file
    import mss
    from PIL import Image
    open_mss = getattr(mss, "MSS", None) or mss.mss
    with open_mss() as sct:
        main = primary_monitor(sct.monitors)
    try:
        with Image.open(files[0]) as img:
            assert img.size == (main["width"], main["height"])
    finally:
        files[0].unlink()          # it's a real picture of the screen: don't leave it around
