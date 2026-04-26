from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from scrcpy_gui import adb


class AdbListDevicesThread(QThread):
    """Runs `adb devices -l` off the UI thread."""

    list_ready = Signal(object)  # list[adb.AdbDevice]
    failed = Signal(str)

    def __init__(self, adb_path: Path) -> None:
        super().__init__()
        self._adb = adb_path

    def run(self) -> None:
        try:
            out = adb.run_adb_devices(self._adb)
        except OSError as e:
            self.failed.emit(str(e))
            return
        self.list_ready.emit(adb.parse_adb_devices_output(out))


class AdbRestartThread(QThread):
    done = Signal(str)  # combined log text

    def __init__(self, adb_path: Path) -> None:
        super().__init__()
        self._adb = adb_path

    def run(self) -> None:
        try:
            s = adb.restart_adb_server(self._adb)
        except OSError as e:
            s = f"OSError: {e}"
        self.done.emit(s)


class AdbRunThread(QThread):
    """One-shot `adb` with an explicit argument list (pair, connect, tcpip, …)."""

    done = Signal(object)  # subprocess.CompletedProcess[str]

    def __init__(self, adb_path: Path, args: list[str]) -> None:
        super().__init__()
        self._adb = adb_path
        self._args = list(args)

    def run(self) -> None:
        r: subprocess.CompletedProcess[str] = adb.run_adb(self._adb, self._args)
        self.done.emit(r)
