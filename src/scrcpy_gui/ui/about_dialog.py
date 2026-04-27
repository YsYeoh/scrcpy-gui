from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def show_about_dialog(parent: QWidget | None, version: str) -> None:
    """About box: version, MIT, and short inline third-party credits (no repo-only files)."""
    QMessageBox.about(
        parent,
        "About scrcpy-gui",
        f"scrcpy-gui {version}\n\n"
        "A small open-source Windows helper to install and run scrcpy (Android screen "
        "mirroring) with bundled ADB. Not affiliated with Genymobile, Google, or The Qt "
        "Company.\n\n"
        "This program’s own code is under the MIT License.\n\n"
        "Third-party components bundled or used at runtime: scrcpy (Apache-2.0; "
        "separate project by Genymobile); Android platform-tools / ADB (Google’s terms "
        "for the SDK tools); PySide6 and Qt (LGPL-3.0; The Qt Company); Python standard "
        "library (PSF License).",
    )
