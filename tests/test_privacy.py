"""Guards the 'no visual data kept, local except update checks' promise at the source level."""
import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "visualcommand"
UPDATER = SRC / "updater.py"

FORBIDDEN = {
    r"\bimwrite\b": "writes images to disk",
    r"\bVideoWriter\s*\(": "records video",
    r"\bimencode\b": "encodes frames (could be stored or sent)",
    r"\bpickle\.dump": "serialises objects (could include frames)",
    r"np\.save": "saves arrays (could include frames)",
}
NETWORK = r"^\s*(import|from)\s+(requests|urllib|http|socket|httpx|aiohttp|websocket)"


def _lines():
    for path in SRC.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            yield path, n, line


def test_no_frame_saving_code_anywhere():
    problems = [f"{p.relative_to(SRC.parent)}:{n} {why}: {line.strip()}"
                for p, n, line in _lines() for pat, why in FORBIDDEN.items() if re.search(pat, line)]
    assert not problems, "\n".join(problems)


def test_network_code_only_in_the_updater():
    """The update check is the only online feature; everything else stays offline."""
    problems = [f"{p.relative_to(SRC.parent)}:{n}: {line.strip()}"
                for p, n, line in _lines() if re.search(NETWORK, line) and p != UPDATER]
    assert not problems, "network access outside updater.py:\n" + "\n".join(problems)


def test_updater_only_talks_to_this_projects_github():
    text = UPDATER.read_text(encoding="utf-8")
    urls = set(re.findall(r"https?://[^\s\"'{}]+", text))
    allowed = ("https://api.github.com/repos/", "https://github.com/")
    assert urls and all(u.startswith(allowed) for u in urls), urls
    assert 'REPO = "boraswim/VisualCommand"' in text


def test_updater_cannot_reach_camera_gesture_or_log_data():
    """It imports nothing that holds frames, hand data, settings or logs."""
    tree = ast.parse(UPDATER.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    banned = ("cv2", "mediapipe", "numpy", "visualcommand.tracker", "visualcommand.features",
              "visualcommand.hands", "visualcommand.engine", "visualcommand.triggerlog",
              "visualcommand.config", "visualcommand.gestures", "visualcommand.actions")
    assert not [m for m in imported if m.startswith(banned)], imported


def test_model_is_loaded_from_local_bytes():
    text = (SRC / "tracker.py").read_text(encoding="utf-8")
    assert "model_asset_buffer" in text
    assert "http" not in text.lower()
