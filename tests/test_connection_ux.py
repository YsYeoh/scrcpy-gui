from scrcpy_gui import connection_ux


def test_primary_status_empty() -> None:
    assert "No devices" in connection_ux.primary_status_line([])


def test_guidance_unauthorized() -> None:
    text = connection_ux.primary_status_line([("X", "unauthorized")])
    assert "allow" in text.lower() or "usb" in text.lower()


def test_can_start_one_device_no_selection_needed() -> None:
    d = [("A", "device")]
    assert connection_ux.can_start_mirroring(d, None) is True
    assert connection_ux.resolve_serial(d, None) == "A"


def test_two_devices_require_selection() -> None:
    d = [("A", "device"), ("B", "device")]
    assert connection_ux.can_start_mirroring(d, None) is False
    assert connection_ux.resolve_serial(d, "B") == "B"
