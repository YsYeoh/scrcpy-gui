from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from scrcpy_gui import adb, download, paths
from scrcpy_gui.download import ProgressCallback
from scrcpy_gui.manifest import WindowsManifest

LogFn = Callable[[str], None]


def find_scrcpy_exe(extract_root: Path) -> Path:
    for p in extract_root.rglob("scrcpy.exe"):
        if p.is_file():
            return p
    msg = f"scrcpy.exe not found under {extract_root}"
    raise FileNotFoundError(msg)


def _download_verify_extract(
    url: str,
    expected_sha: str,
    filename: str,
    extract_root: Path,
    log: LogFn,
    on_progress: ProgressCallback | None,
) -> None:
    with tempfile.TemporaryDirectory(prefix="scrcpy-gui-dl-") as td:
        z = Path(td) / filename
        download.download_url_to_file(url, z, on_progress)
        download.verify_file_sha256(z, expected_sha)
        if extract_root.exists():
            shutil.rmtree(extract_root)
        extract_root.mkdir(parents=True, parents=True)
        log("Extracting…")
        download.extract_zip(z, extract_root)


def ensure_tooling(
    m: WindowsManifest,
    log: LogFn,
    on_progress: ProgressCallback | None = None,
) -> tuple[Path, Path]:
    pdir = paths.platform_tools_dir()
    sdir = paths.scrcpy_dir()
    adb_path = adb.adb_executable(pdir)

    if not adb_path.is_file():
        log(f"Downloading {m.platform_tools.filename} (Android platform-tools)…")
        _download_verify_extract(
            m.platform_tools.url,
            m.platform_tools.expected_sha256,
            m.platform_tools.filename,
            pdir,
            log,
            on_progress,
        )
    if not adb_path.is_file():
        msg = f"adb not found at {adb_path} after install"
        raise RuntimeError(msg)

    if not list(sdir.rglob("scrcpy.exe")):
        log(f"Downloading {m.scrcpy.filename} (scrcpy)…")
        if sdir.exists():
            shutil.rmtree(sdir)
        _download_verify_extract(
            m.scrcpy.url,
            m.scrcpy.expected_sha256,
            m.scrcpy.filename,
            sdir,
            log,
            on_progress,
        )

    sc = find_scrcpy_exe(sdir)
    return adb_path, sc
