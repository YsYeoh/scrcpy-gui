from __future__ import annotations

import hashlib
import shutil
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import TypeAlias

ProgressCallback: TypeAlias = Callable[[int, int | None], None]  # (bytes_read, content_length or None)


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def verify_file_sha256(path: Path, expected_hex: str) -> None:
    got = _sha256_file(path).lower()
    want = expected_hex.strip().lower()
    if got != want:
        msg = f"hash mismatch for {path}: got {got}, expected {want}"
        raise RuntimeError(msg)


def download_url_to_file(
    url: str,
    dest: Path,
    on_progress: ProgressCallback | None = None,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "scrcpy-gui/0.4"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        total = None
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit():
            total = int(cl)
        read = 0
        with tmp.open("wb") as out:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if on_progress:
                    on_progress(read, total)
    tmp.replace(dest)


def extract_zip(zip_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target_dir)
