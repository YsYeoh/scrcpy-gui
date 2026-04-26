from __future__ import annotations

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

from scrcpy_gui import __version__, adb, connection_ux, manifest, scrcpy_runner
from scrcpy_gui.ui.connection_help_dialog import ConnectionHelpDialog


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
        self._devices: list[tuple[str, str]] = []

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self._status = QLabel("Starting…")
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._status)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Serial", "State"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._sync_start_and_status)
        layout.addWidget(self._table)

        row2 = QHBoxLayout()
        self._btn_start = QPushButton("Start mirroring")
        self._btn_start.setEnabled(False)
        self._btn_refresh = QPushButton("Refresh devices")
        self._btn_refresh.setEnabled(False)
        self._btn_help = QPushButton("Connection help")
        self._btn_reset_adb = QPushButton("Reset ADB")
        self._btn_copy = QPushButton("Copy details")
        self._btn_reset_adb.setEnabled(False)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_refresh.clicked.connect(self._refresh)
        self._btn_help.clicked.connect(self._on_connection_help)
        self._btn_reset_adb.clicked.connect(self._on_reset_adb)
        self._btn_copy.clicked.connect(self._copy)
        row2.addWidget(self._btn_start)
        row2.addWidget(self._btn_refresh)
        row2.addWidget(self._btn_help)
        row2.addWidget(self._btn_reset_adb)
        row2.addWidget(self._btn_copy)
        row2.addStretch(1)
        layout.addLayout(row2)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        layout.addWidget(self._log)

        self._thread: BootstrapThread | None = None

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
        self._apply_devices(devices)
        self._btn_refresh.setEnabled(True)
        self._btn_reset_adb.setEnabled(True)

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

    def _apply_devices(self, devices) -> None:  # type: ignore[no-untyped-def]
        self._devices = list(devices)
        self._table.setRowCount(0)
        for serial, state in self._devices:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(serial))
            self._table.setItem(r, 1, QTableWidgetItem(state))
        self._select_default_row()
        self._sync_start_and_status()

    def _select_default_row(self) -> None:
        r = connection_ux.ready_serials(self._devices)
        if len(r) == 1:
            only = r[0]
            for i in range(self._table.rowCount()):
                it = self._table.item(i, 0)
                if it is not None and it.text() == only:
                    self._table.selectRow(i)
                    return
        self._table.clearSelection()

    def _selected_serial_for_mirroring(self) -> str | None:
        return self._serial_to_use(self._devices)

    def _serial_to_use(self, d: list[tuple[str, str]]) -> str | None:
        """Pick serial to mirror given current table selection and a device list from adb."""
        r = connection_ux.ready_serials(d)
        if not r:
            return None
        if len(r) == 1:
            return r[0]
        row = self._table.currentRow()
        if row < 0:
            return None
        it0 = self._table.item(row, 0)
        it1 = self._table.item(row, 1)
        if it0 is None or it1 is None:
            return None
        if it1.text() != "device":
            return None
        s = it0.text()
        return s if s in r else None

    @Slot()
    def _sync_start_and_status(self) -> None:
        if not self._adb or not self._scrcpy:
            return
        self._status.setText(connection_ux.primary_status_line(self._devices))
        sel = self._selected_serial_for_mirroring()
        self._btn_start.setEnabled(
            connection_ux.can_start_mirroring(self._devices, sel),
        )

    @Slot()
    def _refresh(self) -> None:
        if not self._adb or not self._scrcpy:
            return
        out = adb.run_adb_devices(self._adb)
        d = adb.parse_adb_devices_output(out)
        self._apply_devices(d)

    @Slot()
    def _on_start(self) -> None:
        if not self._adb or not self._scrcpy:
            return
        out = adb.run_adb_devices(self._adb)
        d = adb.parse_adb_devices_output(out)
        # Fresh `adb devices` + current table row (if several are in "device" state).
        serial = self._serial_to_use(d)
        if serial is None:
            QMessageBox.information(
                self,
                "scrcpy-gui",
                "Select a device row in the “device” state, or connect only one phone, then try again.",
            )
            return
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
    def _on_connection_help(self) -> None:
        ConnectionHelpDialog(self).exec()

    @Slot()
    def _on_reset_adb(self) -> None:
        if not self._adb:
            return
        try:
            out = adb.restart_adb_server(self._adb)
        except OSError as e:
            QMessageBox.critical(self, "scrcpy-gui", f"Reset ADB failed: {e!s}")
            return
        if out.strip():
            self._append_log(out.strip())
        self._append_log("ADB server restarted. Refreshing device list…")
        self._refresh()

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
