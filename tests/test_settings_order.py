"""Gestures tab: assigned gestures first, the rest in their usual order."""
from visualcommand.gestures import catalogue
from visualcommand.settings_ui import order_gestures


def test_assigned_first_then_rest_in_catalogue_order():
    cat = catalogue()
    maps = {"Victory": {"action": "lock_pc"}, "Thumb_Up": {"action": "screenshot"},
            "OK_Sign": {"action": "show_desktop", "params": {}}}
    assigned, unassigned = order_gestures(cat, maps)
    ids = [g.id for g in cat]
    assert [g.id for g in assigned] == [i for i in ids if i in maps]       # catalogue order kept
    assert [g.id for g in unassigned] == [i for i in ids if i not in maps]
    assert len(assigned) + len(unassigned) == len(cat)


class _FakeTracker:
    status, lighting, preview = "running", "good", False
    def wake(self): pass
    def request_camera_settings(self): pass


class _FakeApp:
    def __init__(self, cfg):
        self.cfg, self.tracker, self.last_event = cfg, _FakeTracker(), ""
    def is_paused(self): return False
    def toggle_preview(self): pass
    def set_tracking(self, on): pass
    def test_action(self, a, p): pass
    def post(self, fn): fn()
    def notify(self, *a, **k): pass


def _sections(ui):
    """Gesture ids under each heading, top to bottom."""
    import tkinter.ttk as ttk
    out, current = {}, None
    rows = sorted(ui._gesture_body.grid_slaves(column=0), key=lambda w: int(w.grid_info()["row"]))
    by_row = {int(r["anchor"].grid_info()["row"]): gid for gid, r in ui._rows.items()}
    for w in rows:
        r = int(w.grid_info()["row"])
        if isinstance(w, ttk.Label) and str(w.cget("style")) == "Section.TLabel":
            current = w.cget("text")
            out[current] = []
        elif r in by_row:
            out[current].append(by_row[r])
    return out


def _pick(ui, tk_root, gid, item):
    row = ui._rows[gid]
    combo = row["anchor"]
    combo.set(item)
    combo.event_generate("<<ComboboxSelected>>")
    tk_root.update()          # runs the deferred re-sort


def test_assigning_and_unassigning_moves_the_gesture_immediately(tk_root, tmp_path):
    from visualcommand.config import Config
    from visualcommand.settings_ui import NOTHING, SettingsWindow
    cfg = Config(tmp_path / "config.json")
    ui = SettingsWindow(tk_root, _FakeApp(cfg))
    tk_root.update()
    assert "Rock" in _sections(ui)["Not assigned"]

    _pick(ui, tk_root, "Rock", ui._item_by_id["screenshot"])           # assign
    s = _sections(ui)
    assert "Rock" in s["In use"] and "Rock" not in s["Not assigned"]
    assert cfg.mappings()["Rock"]["action"] == "screenshot"

    _pick(ui, tk_root, "Rock", NOTHING)                                 # unassign
    s = _sections(ui)
    assert "Rock" in s["Not assigned"] and "Rock" not in s.get("In use", [])
    assert "Rock" not in cfg.mappings()
    tk_root.withdraw()


def test_empty_or_cleared_mapping_counts_as_unassigned():
    cat = catalogue()
    assigned, unassigned = order_gestures(cat, {"Victory": {"action": ""}, "Rock": {}})
    assert assigned == [] and len(unassigned) == len(cat)
