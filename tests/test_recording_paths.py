from __future__ import annotations

from datetime import datetime
from pathlib import Path

import scrcpy_gui.recording_paths as recording_paths
from scrcpy_gui.recording_paths import (
    build_record_arg,
    default_output_dir,
    effective_output_dir,
    next_automatic_record_path,
)


def test_build_record_arg_uses_absolute() -> None:
    p = Path("C:/tmp/relative-ish").resolve() / "x.mp4"
    assert build_record_arg(p) == [f"--record={p}"]


def test_next_automatic_naming_and_suffix() -> None:
    base = Path("C:/out")
    t = datetime(2026, 4, 27, 15, 30, 45)
    got = next_automatic_record_path(base, when=t)
    assert got == base / "scrcpy-record-20260427-153045.mp4"


def test_default_output_dir_prefers_videos(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(recording_paths, "_home", lambda: tmp_path)
    (tmp_path / "Videos").mkdir()
    assert default_output_dir() == tmp_path / "Videos"


def test_default_output_dir_falls_back_to_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(recording_paths, "_home", lambda: tmp_path)
    assert default_output_dir() == tmp_path


def test_effective_output_prefers_valid_settings_dir(tmp_path: Path) -> None:
    sub = tmp_path / "r"
    sub.mkdir()
    assert effective_output_dir(str(sub)) == sub.resolve()


def test_effective_output_ignores_non_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(recording_paths, "_home", lambda: tmp_path)
    (tmp_path / "Videos").mkdir()
    f = tmp_path / "a_file"
    f.write_text("x", encoding="utf-8")
    assert (
        effective_output_dir(str(f), log=lambda _m: None) == (tmp_path / "Videos")
    )
