from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def adb_executable(platform_tools_cache: Path) -> Path:
    if sys.platform == "win32":
        return platform_tools_cache / "platform-tools" / "adb.exe"
    return platform_tools_cache / "platform-tools" / "adb"


def parse_adb_devices_output(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        m = re.match(r"^(\S+)\s+(\S+)(?:\s+.*)?$", line)
        if not m:
            continue
        serial, state = m.group(1), m.group(2)
        if serial and state:
            out.append((serial, state))
    return out


def run_adb_devices(adb: Path) -> str:
    result = subprocess.run(
        [str(adb), "devices", "-l"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return (result.stdout or "") + (result.stderr or "")


def restart_adb_server(adb: Path) -> str:
    r1 = subprocess.run(
        [str(adb), "kill-server"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    r2 = subprocess.run(
        [str(adb), "start-server"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return (r1.stdout or r1.stderr or "") + (r2.stdout or r2.stderr or "")
