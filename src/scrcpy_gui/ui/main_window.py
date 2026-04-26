from __future__ import annotations

import platform
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
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

from scrcpy_gui import __version__, adb, connection_ux, manifest, mirroring_options, scrcpy_runner
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

        self._settings = QSettings("scrcpy-gui", "scrcpy-gui")
        self._opt_group = QGroupBox("Mirroring quality")
        opt_lay = QFormLayout()
        self._combo_preset = QComboBox()
        self._combo_preset.addItem(
            "Balanced (default)",
            mirroring_options.PRESET_BALANCED,
        )
        self._combo_preset.addItem(
            "Smoother — lower resolution, less bandwidth",
            mirroring_options.PRESET_FAST,
        )
        self._combo_preset.addItem(
            "Sharper — higher resolution, more bandwidth",
            mirroring_options.PRESET_SHARP,
        )
        self._chk_stay = QCheckBox("Keep device awake while mirroring (when plugged in)")
        self._chk_touches = QCheckBox("Show touch dots on the phone (physical touches only)")
        self._chk_ontop = QCheckBox("Keep scrcpy window above other windows")
        opt_lay.addRow("Preset", self._combo_preset)
        opt_lay.addRow(self._chk_stay)
        opt_lay.addRow(self._chk_touches)
        opt_lay.addRow(self._chk_ontop)
        self._opt_group.setLayout(opt_lay)
        layout.addWidget(self._opt_group)
        self._load_mirroring_settings()
        self._combo_preset.currentIndexChanged.connect(self._save_mirroring_settings)
        self._chk_stay.stateChanged.connect(self._save_mirroring_settings)
        self._chk_touches.stateChanged.connect(self._save_mirroring_settings)
        self._chk_ontop.stateChanged.connect(self._save_mirroring_settings)

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

    def _load_mirroring_settings(self) -> None:
        p = self._settings.value("mirroring/preset", mirroring_options.PRESET_BALANCED, str)
        if p not in mirroring_options.ALL_PRESETS:
            p = mirroring_options.PRESET_BALANCED
        i = self._combo_preset.findData(p)
        self._combo_preset.blockSignals(True)
        self._combo_preset.setCurrentIndex(max(0, i))
        self._combo_preset.blockSignals(False)
        self._chk_stay.blockSignals(True)
        self._chk_touches.blockSignals(True)
        self._chk_ontop.blockSignals(True)
        self._chk_stay.setChecked(
            str(self._settings.value("mirroring/stay_awake", "false")).lower()
            in ("1", "true", "yes", "on"),
        )
        self._chk_touches.setChecked(
            str(self._settings.value("mirroring/show_touches", "false")).lower()
            in ("1", "true", "yes", "on"),
        )
        self._chk_ontop.setChecked(
            str(self._settings.value("mirroring/always_on_top", "false")).lower()
            in ("1", "true", "yes", "on"),
        )
        self._chk_stay.blockSignals(False)
        self._chk_touches.blockSignals(False)
        self._chk_ontop.blockSignals(False)

    @Slot()
    def _save_mirroring_settings(self) -> None:
        preset = self._combo_preset.currentData()
        if not isinstance(preset, str) or preset not in mirroring_options.ALL_PRESETS:
            preset = mirroring_options.PRESET_BALANCED
        self._settings.setValue("mirroring/preset", preset)
        self._settings.setValue("mirroring/stay_awake", "true" if self._chk_stay.isChecked() else "false")
        self._settings.setValue("mirroring/show_touches", "true" if self._chk_touches.isChecked() else "false")
        self._settings.setValue("mirroring/always_on_top", "true" if self._chk_ontop.isChecked() else "false")

    def _current_scrcpy_extra_args(self) -> list[str]:
        p = self._combo_preset.currentData()
        if not isinstance(p, str) or p not in mirroring_options.ALL_PRESETS:
            p = mirroring_options.PRESET_BALANCED
        return mirroring_options.build_scrcpy_args(
            p,
            stay_awake=self._chk_stay.isChecked(),
            show_touches=self._chk_touches.isChecked(),
            always_on_top=self._chk_ontop.isChecked(),
        )

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
        extra = self._current_scrcpy_extra_args()
        if extra:
            self._append_log("Options: " + " ".join(extra))
        self._append_log(f"Starting scrcpy for {serial}…")

        def line(s: str) -> None:
            self._append_log(s)

        try:
            self._proc = scrcpy_runner.start_scrcpy(
                self._scrcpy,
                self._adb,
                serial,
                line,
                extra_scrcpy_args=extra,
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
            " ".join(self._current_scrcpy_extra_args()) or "(defaults)",
        )
        QApplication.clipboard().setText(s)


def _details_text(
    version: str,
    adb_path: Path | None,
    sc: Path | None,
    last_log: str,
    mirroring_args: str = "",
) -> str:
    return (
        f"scrcpy-gui {version}\n"
        f"OS: {platform.platform()}\n"
        f"Python: {sys.version.splitlines()[0]}\n"
        f"adb: {adb_path}\n"
        f"scrcpy: {sc}\n"
        f"mirroring extra args: {mirroring_args}\n"
        f"---\n{last_log}"
    )


def main() -> int:
    from PySide6.QtWidgets import QApplication

    QApplication.setOrganizationName("scrcpy-gui")
    QApplication.setApplicationName("scrcpy-gui")
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(720, 640)
    w.show()
    return app.exec()
