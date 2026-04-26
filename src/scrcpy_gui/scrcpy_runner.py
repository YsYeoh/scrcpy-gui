from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

LogFn = Callable[[str], None]


def _pump_stream(stream, log: LogFn, prefix: str) -> None:  # type: ignore[no-untyped-def]
    try:
        for line in iter(stream.readline, ""):
            s = (line or "").rstrip()
            if s:
                log(f"{prefix}{s}")
    except OSError:
        pass


def start_scrcpy(
    scrcpy_exe: Path,
    adb_exe: Path,
    serial: str,
    log_line: LogFn,
) -> subprocess.Popen[str]:
    cmd: list[str] = [
        str(scrcpy_exe),
        f"--adb={str(adb_exe)}",
        "-s",
        serial,
    ]
    creation = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(  # noqa: S603 — controlled argv
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creation,
    )
    if proc.stdout is not None:
        t = threading.Thread(
            target=_pump_stream,
            args=(proc.stdout, log_line, ""),
            daemon=True,
        )
        t.start()
    return proc
