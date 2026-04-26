from __future__ import annotations


def ready_serials(devs: list[tuple[str, str]]) -> list[str]:
    return [s for s, st in devs if st == "device"]


def primary_status_line(devs: list[tuple[str, str]]) -> str:
    if not devs:
        return "No devices found — connect USB, enable USB debugging, then tap Refresh."
    if any(st == "unauthorized" for _, st in devs):
        return "On the phone, allow USB debugging when prompted, then tap Refresh."
    if any(st == "offline" for _, st in devs):
        return "A device looks offline — try another port or USB cable, then tap Refresh."
    r = ready_serials(devs)
    if not r:
        return "No device in “device” state yet — fix the state in the list, then tap Refresh."
    if len(r) == 1:
        return "One device is ready. Tap Start mirroring."
    return "More than one device is ready — select a row, then tap Start mirroring."


def can_start_mirroring(
    devs: list[tuple[str, str]],
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
    devs: list[tuple[str, str]],
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


def detailed_help_text() -> str:
    return (
        "1) Use a data-capable USB cable and port (avoid charge-only USB).\n"
        "2) On the phone, enable Developer options and turn on USB debugging.\n"
        "3) If asked, set USB to File transfer (MTP) or “USB controlled by: This device”.\n"
        "4) On the “Allow USB debugging?” screen, check “Always” if you like, then tap OK.\n"
        "5) In this app, tap Refresh. If the list is stuck, try Reset ADB, then Refresh.\n"
        "6) If more than one phone is ready, select the correct row, then Start mirroring.\n"
    )
