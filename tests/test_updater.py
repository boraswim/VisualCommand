"""Update check / download / verify, with GitHub replaced by local fakes."""
import hashlib
import io

import pytest

from visualcommand import __version__, updater

PREFIX = updater.DOWNLOAD_PREFIX


def _api(tag="v9.9.9", payload=b"installer bytes", **over):
    asset = {"name": f"VisualCommand-Setup-{tag.lstrip('v')}.exe",
             "browser_download_url": f"{PREFIX}{tag}/VisualCommand-Setup-{tag.lstrip('v')}.exe",
             "size": len(payload), "digest": "sha256:" + hashlib.sha256(payload).hexdigest()}
    asset.update(over)
    return {"tag_name": tag, "draft": False, "prerelease": False,
            "html_url": "https://github.com/boraswim/VisualCommand/releases/tag/" + tag, "assets": [asset]}


def test_version_compare():
    assert updater.is_newer("0.1.24", "0.1.23")
    assert updater.is_newer("v0.2.0", "0.1.99")
    assert updater.is_newer("0.1.10", "0.1.9")          # numeric, not text order
    assert not updater.is_newer("0.1.23", "0.1.23")
    assert not updater.is_newer("0.1.22", "0.1.23")
    assert updater.is_newer("1.0", "0.9.9")


def test_release_picked_from_api():
    r = updater.release_from_api(_api())
    assert r.version == "9.9.9" and r.url.startswith(PREFIX) and len(r.sha256) == 64


def test_unusable_releases_ignored():
    assert updater.release_from_api({**_api(), "draft": True}) is None
    assert updater.release_from_api({**_api(), "prerelease": True}) is None
    assert updater.release_from_api(_api(digest="")) is None               # no checksum
    assert updater.release_from_api(_api(browser_download_url="https://evil.example/x.exe")) is None


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_check_reports_only_newer(monkeypatch):
    import json
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout: _Resp(json.dumps(_api("v" + __version__)).encode()))
    assert updater.check() is None
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout: _Resp(json.dumps(_api("v99.0.0")).encode()))
    assert updater.check().version == "99.0.0"


def test_download_verifies_checksum(monkeypatch, tmp_path):
    payload = b"x" * 200_000
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    rel = updater.release_from_api(_api(payload=payload))
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda req, timeout: _Resp(payload))
    seen = []
    path = updater.download(rel, progress=seen.append)
    assert path.read_bytes() == payload and seen[-1] == 1.0


def test_tampered_download_is_rejected_and_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    rel = updater.release_from_api(_api(payload=b"the real installer"))
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout: _Resp(b"something else entirely"))
    with pytest.raises(ValueError):
        updater.download(rel)
    assert not list(tmp_path.rglob("*.exe")) and not list(tmp_path.rglob("*.part"))


def test_install_runs_silent_installer_that_restarts_the_app(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    updater.install(tmp_path / "VisualCommand-Setup-9.9.9.exe")
    assert "/SILENT" in calls[0] and "/RESTARTAPP=1" in calls[0]


def test_user_agent_has_no_personal_details():
    req = updater._request(updater.API_LATEST)
    assert req.get_header("User-agent") == f"VisualCommand/{__version__}"
