from scrcpy_gui import manifest


def test_loads_vendor_windows() -> None:
    m = manifest.load_windows()
    assert m.platform_tools.version
    assert m.scrcpy.version
    assert m.platform_tools.url.startswith("https://")
    assert m.scrcpy.url.startswith("https://")
    assert len(m.platform_tools.expected_sha256) == 64
    assert len(m.scrcpy.expected_sha256) == 64
