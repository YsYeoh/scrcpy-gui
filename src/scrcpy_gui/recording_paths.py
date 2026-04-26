from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path


def _home() -> Path:
    return Path.home()


def default_output_dir() -> Path:
    v = _home() / "Videos"
    if v.is_dir():
        return v
    return _home()


def effective_output_dir(
    from_settings: str | None,
    *,
    log: Callable[[str], None] | None = None,
) -> Path:
    if from_settings is None or not (s := from_settings.strip()):
        return default_output_dir().resolve()
    p = Path(s).expanduser()
    if p.is_dir():
        return p.resolve()
    if log is not None:
        log("Recording: saved output folder is missing; using the default…")
    return default_output_dir().resolve()


def next_automatic_record_path(
    output_dir: Path,
    *,
    when: datetime | None = None,
) -> Path:
    dt = when or datetime.now()
    t = dt.strftime("%Y%m%d-%H%M%S")
    return output_dir / f"scrcpy-record-{t}.mp4"


def build_record_arg(absolute_file: Path) -> list[str]:
    return [f"--record={absolute_file.resolve()}"]
