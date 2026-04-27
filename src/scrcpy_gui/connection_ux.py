from __future__ import annotations

from scrcpy_gui.adb import AdbDevice


def ready_serials(devs: list[AdbDevice]) -> list[str]:
    return [d.serial for d in devs if d.state == "device"]


def primary_status_line(devs: list[AdbDevice]) -> str:
    if not devs:
        return "No devices found — connect USB, enable USB debugging, then tap Refresh."
    if any(d.state == "unauthorized" for d in devs):
        return "On the phone, allow USB debugging when prompted, then tap Refresh."
    if any(d.state == "offline" for d in devs):
        return "A device looks offline — try another port or USB cable, then tap Refresh."
    r = ready_serials(devs)
    if not r:
        return "No device in “device” state yet — fix the state in the list, then tap Refresh."
    if len(r) == 1:
        return "One device is ready. Tap Start mirroring."
    return "More than one device is ready — select a row, then tap Start mirroring."


def can_start_mirroring(
    devs: list[AdbDevice],
    selected_serial: str | None,
) -> bool:
    r = ready_serials(devs)
    if not r:
        return False
    if len(r) == 1:
        return True
    if selected_serial is None or selected_serial not in r:
        return False
    return True


def resolve_serial(
    devs: list[AdbDevice],
    selected_serial: str | None,
) -> str | None:
    r = set(ready_serials(devs))
    if not r:
        return None
    if len(r) == 1:
        return next(iter(r))
    if selected_serial in r:
        return selected_serial
    return None


def _wireless_howto_table() -> str:
    return (
        "\n"
        "— Wireless ADB: which method to use? —\n"
        "• You already have USB + “device”: use “Switch to network (USB)”: enable tcpip, "
        "enter IP:port, Connect, then Refresh. Fastest for home Wi‑Fi.\n"
        "• Phone only offers “Wireless debugging” (Android 11+): use “Pair new device”: "
        "enter the pairing address and code from the phone, Pair, then connect to the IP "
        "and port the phone shows for the session, then Refresh.\n"
    )


def detailed_help_text() -> str:
    return (
        "1) Use a data-capable USB cable and port (avoid charge-only USB).\n"
        "2) On the phone, enable Developer options and turn on USB debugging.\n"
        "3) If asked, set USB to File transfer (MTP) or “USB controlled by: This device”.\n"
        "4) On the “Allow USB debugging?” screen, check “Always” if you like, then tap OK.\n"
        "5) In this app, tap Refresh. If the list is stuck, try Reset ADB, then Refresh.\n"
        "6) If more than one phone is ready, select the correct row, then Start mirroring.\n"
        "7) For Wi‑Fi, use the Wireless ADB action and follow the in-dialog steps, then "
        "Refresh the device list.\n"
    ) + _wireless_howto_table()
