from __future__ import annotations

import os
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
    extra_scrcpy_args: list[str] | None = None,
) -> subprocess.Popen[str]:
    # scrcpy reads the custom adb path from the ADB environment variable; it
    # does not accept a --adb=… CLI option (see `scrcpy --help` → Environment).
    env = os.environ.copy()
    env["ADB"] = str(adb_exe)
    rest = scrcpy_arguments_list(serial, extra_scrcpy_args)
    cmd: list[str] = [str(scrcpy_exe), *rest]
    creation = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(  # noqa: S603 — controlled argv
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
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


def scrcpy_arguments_list(
    serial: str,
    extra_scrcpy_args: list[str] | None = None,
) -> list[str]:
    """Args after the scrcpy executable; used by subprocess and :class:`QProcess`."""
    return ["-s", serial, *list(extra_scrcpy_args or [])]
