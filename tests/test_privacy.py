"""Guards the 'no visual data kept, fully local' promise at the source level."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "visualcommand"

FORBIDDEN = {
    r"\bimwrite\b": "writes images to disk",
    r"\bVideoWriter\s*\(": "records video",
    r"\bimencode\b": "encodes frames (could be stored or sent)",
    r"^\s*(import|from)\s+(requests|urllib|http|socket|httpx|aiohttp|websocket)": "network access",
    r"\bpickle\.dump": "serialises objects (could include frames)",
    r"np\.save": "saves arrays (could include frames)",
}


def test_no_frame_saving_or_network_code():
    problems = []
    for path in SRC.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, why in FORBIDDEN.items():
                if re.search(pattern, line):
                    problems.append(f"{path.relative_to(SRC.parent)}:{n} {why}: {line.strip()}")
    assert not problems, "\n".join(problems)


def test_model_is_loaded_from_local_bytes():
    text = (SRC / "tracker.py").read_text(encoding="utf-8")
    assert "model_asset_buffer" in text
    assert "http" not in text.lower()
