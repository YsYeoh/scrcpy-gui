from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AdbDevice:
    """One row from `adb devices -l` (or plain `adb devices` without extras)."""

    serial: str
    state: str
    model: str | None = None


def adb_executable(platform_tools_cache: Path) -> Path:
    if sys.platform == "win32":
        return platform_tools_cache / "platform-tools" / "adb.exe"
    return platform_tools_cache / "platform-tools" / "adb"


def _model_from_trailer(trailer: str) -> str | None:
    m = re.search(r"(?:\s|^)model:([^\s]+)", trailer, flags=re.IGNORECASE)
    return m.group(1) if m else None


def parse_adb_devices_output(text: str) -> list[AdbDevice]:
    out: list[AdbDevice] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        m = re.match(r"^(\S+)\s+(\S+)(?:\s+(.*))?$", line)
        if not m:
            continue
        serial, state, trailer = m.group(1), m.group(2), m.group(3) or ""
        if serial and state:
            model = _model_from_trailer(trailer) if trailer else None
            out.append(AdbDevice(serial=serial, state=state, model=model))
    return out


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def run_adb(adb: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(adb), *args],
        capture_output=True,
        text=True,
        check=False,
        creationflags=_creationflags(),
    )


def run_adb_devices(adb: Path) -> str:
    result = run_adb(adb, ["devices", "-l"])
    return (result.stdout or "") + (result.stderr or "")


def run_adb_pair(adb: Path, address: str, code: str) -> subprocess.CompletedProcess[str]:
    """`adb pair ADDR:PORT CODE` (separate args; no shell)."""
    return run_adb(adb, ["pair", address, code])


def run_adb_connect(adb: Path, address: str) -> subprocess.CompletedProcess[str]:
    return run_adb(adb, ["connect", address])


def run_adb_tcpip(adb: Path, port: int, device_serial: str | None) -> subprocess.CompletedProcess[str]:
    if device_serial is not None:
        return run_adb(adb, ["-s", device_serial, "tcpip", str(port)])
    return run_adb(adb, ["tcpip", str(port)])


def restart_adb_server(adb: Path) -> str:
    r1 = run_adb(adb, ["kill-server"])
    r2 = run_adb(adb, ["start-server"])
    return (r1.stdout or r1.stderr or "") + (r2.stdout or r2.stderr or "")


# —— Argv builders (unit tests; no subprocess) ——
def argv_tcpip(port: int, device_serial: str | None) -> list[str]:
    if device_serial is not None:
        return ["-s", device_serial, "tcpip", str(port)]
    return ["tcpip", str(port)]


def argv_connect(address: str) -> list[str]:
    return ["connect", address]


def argv_pair(address: str, code: str) -> list[str]:
    return ["pair", address, code]
