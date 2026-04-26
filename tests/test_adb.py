from pathlib import Path
import sys
from unittest import mock

from scrcpy_gui import adb

SAMPLE = """
List of devices attached
R58M123ABCD\tdevice
"""


def test_parse_one_device() -> None:
    d = adb.parse_adb_devices_output(SAMPLE)
    assert d == [("R58M123ABCD", "device")]


def test_parse_unauthorized() -> None:
    text = "List of devices attached\nX\tunauthorized"
    d = adb.parse_adb_devices_output(text)
    assert d == [("X", "unauthorized")]


def test_parse_offline() -> None:
    text = "List of devices attached\nY\toffline"
    d = adb.parse_adb_devices_output(text)
    assert d == [("Y", "offline")]


def test_parse_empty() -> None:
    assert adb.parse_adb_devices_output("List of devices attached\n\n") == []


def test_adb_executable_win() -> None:
    base = Path("C:/cache/platform-tools")
    with mock.patch.object(sys, "platform", "win32"):
        p = adb.adb_executable(base)
    assert p.name == "adb.exe"
    assert "platform-tools" in str(p).replace("\\", "/")


def test_adb_executable_non_win() -> None:
    base = Path("/tmp/pt")
    with mock.patch.object(sys, "platform", "linux"):
        p = adb.adb_executable(base)
    assert p.name == "adb"
