from __future__ import annotations

import os
import platform
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from scrcpy_gui import __version__, adb, manifest, scrcpy_runner


class BootstrapThread(QThread):
    line = Signal(str)
    error = Signal(str)
    # PySide6 needs `object` for the device list (list[tuple] payload).
    ready = Signal(str, str, object)

    def run(self) -> None:
        try:
            w = manifest.load_windows()
        except (OSError, KeyError, ValueError) as e:
            self.error.emit(f"Manifest: {e!s}")
            return
        try:
            from scrcpy_gui.ensure import ensure_tooling

            def log(msg: str) -> None:
                self.line.emit(msg)

            a, s = ensure_tooling(w, log, None)
            out = adb.run_adb_devices(a)
            devs = adb.parse_adb_devices_output(out)
            self.ready.emit(str(a), str(s), devs)
        except Exception as e:  # noqa: BLE071
            self.error.emit(f"{e!s}\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("scrcpy-gui")
        self._adb: Path | None = None
        self._scrcpy: Path | None = None
        self._proc: object | None = None
        self._last_log = ""

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        help_box = QTextEdit(
            self._help_text()
        )
        help_box.setReadOnly(True)
        help_box.setMaximumHeight(100)
        layout.addWidget(help_box)

        self._status = QLabel("Starting…")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._status)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Serial", "State"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        row2 = QHBoxLayout()
        self._btn_start = QPushButton("Start mirroring")
        self._btn_start.setEnabled(False)
        self._btn_refresh = QPushButton("Refresh devices")
        self._btn_refresh.setEnabled(False)
        self._btn_copy = QPushButton("Copy details")
        self._btn_start.clicked.connect(self._on_start)
        self._btn_refresh.clicked.connect(self._refresh)
        self._btn_copy.clicked.connect(self._copy)
        row2.addWidget(self._btn_start)
        row2.addWidget(self._btn_refresh)
        row2.addWidget(self._btn_copy)
        row2.addStretch(1)
        layout.addLayout(row2)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        layout.addWidget(self._log)

        self._thread: BootstrapThread | None = None

    @staticmethod
    def _help_text() -> str:
        return (
            "USB debugging: On the phone, enable Developer options, then enable USB debugging. "
            "Connect with USB, choose file transfer (MTP) if prompted, and accept the "
            "“Allow USB debugging?” fingerprint dialog when it appears. "
            "Unplug other Android devices if you see more than one listed."
        )

    def _append_log(self, text: str) -> None:
        self._last_log += text + "\n"
        self._log.append(text.rstrip())

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def, override]
        super().showEvent(event)
        if self._thread is not None or self._adb is not None:
            return
        th = BootstrapThread()
        th.line.connect(self._append_log)
        th.error.connect(self._on_bootstrap_error)
        th.ready.connect(self._on_ready)
        self._thread = th
        th.finished.connect(lambda: setattr(self, "_thread", None))
        th.start()
        self._status.setText("Downloading or preparing tools (first run may take a while)…")

    @Slot(str, str, object)
    def _on_ready(self, adb_s: str, sc: str, devices) -> None:  # type: ignore[no-untyped-def, override]
        self._adb = Path(adb_s)
        self._scrcpy = Path(sc)
        self._thread = None
        self._status.setText("Tooling ready. Connect a device, then use Refresh if needed.")
        self._apply_devices(devices)
        self._btn_start.setEnabled(self._can_start(self._ready_devices(devices)))
        self._btn_refresh.setEnabled(True)

    @Slot(str)
    def _on_bootstrap_error(self, err: str) -> None:
        self._thread = None
        self._append_log(err)
        self._status.setText("Setup failed — see log.")
        QMessageBox.critical(
            self,
            "scrcpy-gui",
            "First-time setup or device listing failed. Check the log, then retry."
            f"\n\n{err[:800]}",
        )

    @staticmethod
    def _ready_devices(
        devs: list,
    ) -> list[tuple[str, str]]:
        return [(a, b) for (a, b) in devs if b == "device"]

    @staticmethod
    def _can_start(ready: list[tuple[str, str]]) -> bool:
        return len(ready) == 1

    @Slot()
    def _refresh(self) -> None:
        if not self._adb or not self._scrcpy:
            return
        out = adb.run_adb_devices(self._adb)
        d = adb.parse_adb_devices_output(out)
        self._apply_devices(d)
        r = self._ready_devices(d)
        self._btn_start.setEnabled(self._can_start(r))
        u = [x for x in d if "unauthor" in x[1] or x[1] == "unauthorized"]
        if u:
            self._status.setText("Unlock the phone and accept the USB debugging prompt.")
        elif not r and d:
            self._status.setText("No device in 'device' state. Check cable and USB mode.")
        elif not d:
            self._status.setText("No devices — connect USB and enable USB debugging.")
        else:
            self._status.setText("Tooling ready.")

    def _apply_devices(self, devices) -> None:  # type: ignore[no-untyped-def]
        self._table.setRowCount(0)
        for serial, state in devices:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(serial))
            self._table.setItem(r, 1, QTableWidgetItem(state))

    @Slot()
    def _on_start(self) -> None:
        if not self._adb or not self._scrcpy:
            return
        out = adb.run_adb_devices(self._adb)
        d = adb.parse_adb_devices_output(out)
        ready = self._ready_devices(d)
        if not self._can_start(ready):
            QMessageBox.information(
                self,
                "scrcpy-gui",
                "Connect exactly one device in “device” state, or plug out extras.",
            )
            return
        serial = ready[0][0]
        self._append_log(f"Starting scrcpy for {serial}…")

        def line(s: str) -> None:
            self._append_log(s)

        try:
            self._proc = scrcpy_runner.start_scrcpy(
                self._scrcpy,
                self._adb,
                serial,
                line,
            )
        except OSError as e:
            QMessageBox.critical(self, "scrcpy-gui", f"Failed to start scrcpy: {e!s}")

    @Slot()
    def _copy(self) -> None:
        s = _details_text(
            __version__,
            self._adb,
            self._scrcpy,
            self._last_log[-4000:],
        )
        QApplication.clipboard().setText(s)


def _details_text(
    version: str,
    adb_path: Path | None,
    sc: Path | None,
    last_log: str,
) -> str:
    return (
        f"scrcpy-gui {version}\n"
        f"OS: {platform.platform()}\n"
        f"Python: {sys.version.splitlines()[0]}\n"
        f"adb: {adb_path}\n"
        f"scrcpy: {sc}\n"
        f"---\n{last_log}"
    )


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(700, 520)
    w.show()
    return app.exec()
