"""Update check and install from the project's GitHub releases.

This is the ONLY module that uses the network, and only when the user asks: the
"Check for updates" button, or the once-a-day check they can turn on (off by
default). It asks GitHub for the latest release; if the user chooses to update, it
downloads that release's installer, verifies it (size and SHA-256 published by
GitHub; download only from this repository's releases) and runs it. Nothing about
the user or their gestures is ever sent.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from visualcommand import APP_NAME, __version__

log = logging.getLogger(__name__)

REPO = "boraswim/VisualCommand"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
TIMEOUT = 15
CHECK_EVERY_SECONDS = 24 * 3600


@dataclass(frozen=True)
class Release:
    version: str               # "0.1.24"
    url: str                   # installer download URL
    size: int
    sha256: str                # hex, from GitHub's asset digest
    page: str


def parse_version(text: str) -> tuple[int, ...]:
    """'v0.1.24' / '0.1.24' -> (0, 1, 24). Non-numeric parts count as 0."""
    parts = []
    for p in text.strip().lstrip("vV").split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer(latest: str, current: str = __version__) -> bool:
    a, b = parse_version(latest), parse_version(current)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def _request(url: str) -> urllib.request.Request:
    # A generic user agent: no personal or machine details.
    return urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{__version__}",
                                                "Accept": "application/vnd.github+json"})


def release_from_api(data: dict) -> Release | None:
    """Pick the installer out of GitHub's 'latest release' JSON (None if unusable)."""
    if data.get("draft") or data.get("prerelease"):
        return None
    version = str(data.get("tag_name", "")).lstrip("vV")
    for a in data.get("assets", []):
        name = a.get("name", "")
        url = a.get("browser_download_url", "")
        digest = a.get("digest") or ""
        if (name.startswith("VisualCommand-Setup-") and name.endswith(".exe")
                and url.startswith(DOWNLOAD_PREFIX) and digest.startswith("sha256:")):
            return Release(version, url, int(a.get("size", 0)), digest.split(":", 1)[1].lower(),
                           data.get("html_url", RELEASES_PAGE))
    return None


def check() -> Release | None:
    """Ask GitHub for the latest release. Returns it if it's newer than this app."""
    with urllib.request.urlopen(_request(API_LATEST), timeout=TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8"))
    release = release_from_api(data)
    log.info("Update check: latest %s, running %s", release.version if release else "?", __version__)
    if release and is_newer(release.version):
        return release
    return None


def download(release: Release, progress: Callable[[float], None] | None = None) -> Path:
    """Download the installer to a temp folder and verify it. Raises on any mismatch."""
    if not release.url.startswith(DOWNLOAD_PREFIX):
        raise ValueError("Refusing to download from outside this project's releases")
    folder = Path(tempfile.gettempdir()) / f"{APP_NAME}-update"
    folder.mkdir(exist_ok=True)
    target = folder / f"VisualCommand-Setup-{release.version}.exe"
    partial = target.with_suffix(".part")
    sha = hashlib.sha256()
    done = 0
    with urllib.request.urlopen(_request(release.url), timeout=TIMEOUT) as r, open(partial, "wb") as out:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress and release.size:
                progress(min(1.0, done / release.size))
    if done != release.size:
        partial.unlink(missing_ok=True)
        raise ValueError(f"Download incomplete ({done} of {release.size} bytes)")
    if sha.hexdigest() != release.sha256:
        partial.unlink(missing_ok=True)
        raise ValueError("Downloaded installer doesn't match the published checksum")
    partial.replace(target)
    log.info("Update %s downloaded and verified (%d bytes)", release.version, done)
    return target


def install(installer: Path) -> None:
    """Start the installer: it shows its progress, closes this app, updates it in place
    (settings kept) and starts the new version (RESTARTAPP=1)."""
    subprocess.Popen([str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                      "/RESTARTAPP=1"], close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


def open_release_page(url: str = RELEASES_PAGE) -> None:
    os.startfile(url)
