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
    assert d == [adb.AdbDevice("R58M123ABCD", "device", model=None)]


def test_parse_model_in_devices_l() -> None:
    text = "List of devices attached\nA\tdevice product:foo model:SM_G990B device:bar"
    d = adb.parse_adb_devices_output(text)
    assert len(d) == 1
    assert d[0].serial == "A"
    assert d[0].state == "device"
    assert d[0].model == "SM_G990B"


def test_parse_unauthorized() -> None:
    text = "List of devices attached\nX\tunauthorized"
    d = adb.parse_adb_devices_output(text)
    assert d == [adb.AdbDevice("X", "unauthorized", model=None)]


def test_parse_offline() -> None:
    text = "List of devices attached\nY\toffline"
    d = adb.parse_adb_devices_output(text)
    assert d == [adb.AdbDevice("Y", "offline", model=None)]


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


def test_restart_adb_server_runs_kill_then_start() -> None:
    p = Path("C:/cache/platform-tools/platform-tools/adb.exe")
    with mock.patch("scrcpy_gui.adb.subprocess.run", autospec=True) as run:
        run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        out = adb.restart_adb_server(p)
    assert run.call_count == 2
    assert list(run.call_args_list[0][0][0]) == [str(p), "kill-server"]
    assert list(run.call_args_list[1][0][0]) == [str(p), "start-server"]
    assert isinstance(out, str)


def test_argv_tcpip_with_serial() -> None:
    assert adb.argv_tcpip(5555, "R58M123") == ["-s", "R58M123", "tcpip", "5555"]


def test_argv_tcpip_one_device_omit_serial() -> None:
    assert adb.argv_tcpip(5555, None) == ["tcpip", "5555"]


def test_argv_connect() -> None:
    assert adb.argv_connect("192.168.0.1:5555") == ["connect", "192.168.0.1:5555"]


def test_argv_pair() -> None:
    assert adb.argv_pair("10.0.0.1:12345", "123456") == ["pair", "10.0.0.1:12345", "123456"]
