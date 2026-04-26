from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def show_about_dialog(parent: QWidget | None, version: str) -> None:
    """About box: version, MIT, third-party note (no hard-coded repo URL)."""
    QMessageBox.about(
        parent,
        "About scrcpy-gui",
        f"scrcpy-gui {version}\n\n"
        "A small open-source Windows helper to install and run scrcpy (Android screen "
        "mirroring) with bundled ADB. Not affiliated with Genymobile, Google, or The Qt "
        "Company.\n\n"
        "This program is distributed under the MIT License. Bundled scrcpy, platform-tools, "
        "and Qt have their own licenses; see THIRD_PARTY_NOTICES in the project.",
    )
