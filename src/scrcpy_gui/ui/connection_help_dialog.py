from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from scrcpy_gui import connection_ux


class ConnectionHelpDialog(QDialog):
    def __init__(self, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setWindowTitle("Connection help")
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(connection_ux.detailed_help_text())
        self.resize(500, 320)
        b = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        b.accepted.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.addWidget(text)
        lay.addWidget(b)
