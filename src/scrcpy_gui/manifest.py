from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class VendorEntry:
    version: str
    url: str
    filename: str
    expected_sha256: str


@dataclass(frozen=True)
class WindowsManifest:
    platform_tools: VendorEntry
    scrcpy: VendorEntry


def load_windows() -> WindowsManifest:
    payload = (
        resources.files("scrcpy_gui.data")
        .joinpath("vendor-windows.json")
        .read_text(encoding="utf-8")
    )
    data = json.loads(payload)
    return WindowsManifest(
        platform_tools=VendorEntry(
            version=data["platform_tools"]["version"],
            url=data["platform_tools"]["url"],
            filename=data["platform_tools"]["filename"],
            expected_sha256=data["platform_tools"]["expected_sha256"].lower(),
        ),
        scrcpy=VendorEntry(
            version=data["scrcpy"]["version"],
            url=data["scrcpy"]["url"],
            filename=data["scrcpy"]["filename"],
            expected_sha256=data["scrcpy"]["expected_sha256"].lower(),
        ),
    )
