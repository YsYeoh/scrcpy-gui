from __future__ import annotations

import platform
import sys
import traceback
from collections import deque
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, Qt, QThread, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from scrcpy_gui import (
    __version__,
    adb,
    connection_ux,
    manifest,
    mirroring_options,
    recording_paths,
    scrcpy_runner,
)
from scrcpy_gui.ui.about_dialog import show_about_dialog
from scrcpy_gui.ui.connection_help_dialog import ConnectionHelpDialog
from scrcpy_gui.ui.wireless_dialog import WirelessDialog
from scrcpy_gui.workers import AdbListDevicesThread, AdbRestartThread

MAX_LOG_LINES = 300


class BootstrapThread(QThread):
    line = Signal(str)
    error = Signal(str)
    progress = Signal(int, int)  # n, total (total < 0 = unknown, indeterminate bar)
    # PySide6 needs `object` for the device list.
    ready = Signal(str, str, object)

    def run(self) -> None:  # noqa: PLR0911
        try:
            w = manifest.load_windows()
        except (OSError, KeyError, ValueError) as e:
            self.error.emit(f"Manifest: {e!s}")
            return
        try:
            from scrcpy_gui.ensure import ensure_tooling

            def log(msg: str) -> None:
                self.line.emit(msg)

            def on_progress(read: int, total: int | None) -> None:
                t = -1 if total is None else int(total)
                self.progress.emit(int(read), t)

            a, s = ensure_tooling(w, log, on_progress)
            out = adb.run_adb_devices(a)
            devs = adb.parse_adb_devices_output(out)
            self.ready.emit(str(a), str(s), devs)
        except Exception as e:  # noqa: BLE071
            self.error.emit(f"{e!s}\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"scrcpy-gui v{__version__}")
        self._adb: Path | None = None
        self._scrcpy_exe: Path | None = None
        self._mirror: QProcess | None = None
        self._log_deque: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self._last_log_for_copy: str = ""
        self._devices: list[adb.AdbDevice] = []

        self._list_thread: AdbListDevicesThread | None = None
        self._restart_thread: AdbRestartThread | None = None
        self._thread: BootstrapThread | None = None
        self._pending_mirroring_start: bool = False

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self._dev_status = QLabel("Starting…")
        self._dev_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._dev_status)

        self._mir_status = QLabel("Mirroring: stopped")
        self._mir_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._mir_status)

        self._dl_progress = QProgressBar()
        self._dl_progress.setTextVisible(True)
        self._dl_progress.setFormat("%p%")
        self._dl_progress.setVisible(False)
        layout.addWidget(self._dl_progress)

        self._settings = QSettings("scrcpy-gui", "scrcpy-gui")
        self._record_oneshot: Path | None = None
        self._last_record_path_for_copy: Path | None = None
        self._chk_record = QCheckBox("Record to file")
        self._btn_record_saveas = QPushButton("Save as…")
        self._btn_record_saveas.setEnabled(False)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Serial", "State", "Model"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._sync_start_and_status)
        layout.addWidget(self._table)

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
        self._row_record = QHBoxLayout()
        self._row_record.addWidget(self._chk_record)
        self._row_record.addWidget(self._btn_record_saveas)
        self._row_record.addStretch(1)
        opt_lay.addRow(self._row_record)
        self._opt_group.setLayout(opt_lay)
        layout.addWidget(self._opt_group)
        self._load_mirroring_settings()
        self._combo_preset.currentIndexChanged.connect(self._save_mirroring_settings)
        self._chk_stay.stateChanged.connect(self._save_mirroring_settings)
        self._chk_touches.stateChanged.connect(self._save_mirroring_settings)
        self._chk_ontop.stateChanged.connect(self._save_mirroring_settings)
        self._chk_record.stateChanged.connect(self._save_mirroring_settings)
        self._btn_record_saveas.clicked.connect(self._on_record_saveas)

        sc_row = QHBoxLayout()
        self._btn_start = QPushButton("Start mirroring")
        self._btn_start.setEnabled(False)
        self._btn_stop = QPushButton("Stop scrcpy")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop_mirror)
        self._btn_start.clicked.connect(self._on_start)
        sc_row.addWidget(self._btn_start)
        sc_row.addWidget(self._btn_stop)
        sc_row.addStretch(1)
        layout.addLayout(sc_row)

        row2 = QHBoxLayout()
        self._btn_refresh = QPushButton("Refresh devices")
        self._btn_refresh.setEnabled(False)
        self._btn_help = QPushButton("Connection help")
        self._btn_wireless = QPushButton("Wireless ADB…")
        self._btn_wireless.setEnabled(False)
        self._btn_reset_adb = QPushButton("Reset ADB")
        self._btn_copy = QPushButton("Copy details")
        self._btn_about = QPushButton("About")
        self._btn_reset_adb.setEnabled(False)
        self._btn_refresh.clicked.connect(self._on_refresh)
        self._btn_help.clicked.connect(self._on_connection_help)
        self._btn_wireless.clicked.connect(self._on_wireless)
        self._btn_reset_adb.clicked.connect(self._on_reset_adb)
        self._btn_copy.clicked.connect(self._copy)
        self._btn_about.clicked.connect(self._on_about)
        row2.addWidget(self._btn_refresh)
        row2.addWidget(self._btn_help)
        row2.addWidget(self._btn_wireless)
        row2.addWidget(self._btn_reset_adb)
        row2.addWidget(self._btn_copy)
        row2.addWidget(self._btn_about)
        row2.addStretch(1)
        layout.addLayout(row2)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        layout.addWidget(self._log)

        sh_f5 = QShortcut(QKeySequence("F5"), self)
        sh_f5.activated.connect(self._shortcut_refresh)
        sh_s = QShortcut(QKeySequence("Ctrl+Return"), self)
        sh_s.activated.connect(self._shortcut_start)

    def _row_selected_ready_serial(self) -> str | None:
        d = self._devices
        r = connection_ux.ready_serials(d)
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

    def _append_log(self, text: str) -> None:
        s = text.rstrip()
        if s:
            self._log_deque.append(s)
        self._log.setPlainText("\n".join(self._log_deque))
        self._last_log_for_copy = "\n".join(self._log_deque)

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
        self._chk_record.blockSignals(True)
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
        self._chk_record.setChecked(
            str(self._settings.value("mirroring/record_enabled", "false")).lower()
            in ("1", "true", "yes", "on"),
        )
        self._chk_stay.blockSignals(False)
        self._chk_touches.blockSignals(False)
        self._chk_ontop.blockSignals(False)
        self._chk_record.blockSignals(False)
        self._sync_record_saveas_enabled()

    @Slot()
    def _save_mirroring_settings(self) -> None:
        preset = self._combo_preset.currentData()
        if not isinstance(preset, str) or preset not in mirroring_options.ALL_PRESETS:
            preset = mirroring_options.PRESET_BALANCED
        self._settings.setValue("mirroring/preset", preset)
        self._settings.setValue("mirroring/stay_awake", "true" if self._chk_stay.isChecked() else "false")
        self._settings.setValue("mirroring/show_touches", "true" if self._chk_touches.isChecked() else "false")
        self._settings.setValue("mirroring/always_on_top", "true" if self._chk_ontop.isChecked() else "false")
        self._settings.setValue("mirroring/record_enabled", "true" if self._chk_record.isChecked() else "false")
        if not self._chk_record.isChecked():
            self._last_record_path_for_copy = None
        self._sync_record_saveas_enabled()

    def _sync_record_saveas_enabled(self) -> None:
        self._btn_record_saveas.setEnabled(self._chk_record.isChecked())

    @Slot()
    def _on_record_saveas(self) -> None:
        if not self._chk_record.isChecked():
            return
        start_dir = self._settings.value("mirroring/record_last_dir", None, str)
        if isinstance(start_dir, str) and start_dir.strip():
            base = Path(start_dir)
            if not base.is_dir():
                base = recording_paths.default_output_dir()
        else:
            base = recording_paths.default_output_dir()
        suggested = (
            recording_paths.next_automatic_record_path(base) if base.is_dir() else base / "scrcpy-record.mp4"
        )
        path, _ok = QFileDialog.getSaveFileName(
            self,
            "Record to file",
            str(suggested),
            "Video (*.mp4 *.mkv);;All files (*.*)",
        )
        if not path:
            return
        p = Path(path)
        self._record_oneshot = p.resolve()
        self._settings.setValue("mirroring/record_last_dir", str(p.parent.resolve()))

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

    @Slot()
    def _shortcut_refresh(self) -> None:
        if not self._adb or self._list_thread is not None:
            return
        self._on_refresh()

    @Slot()
    def _shortcut_start(self) -> None:
        if self._btn_start.isEnabled():
            self._on_start()

    @Slot()
    def _on_download_progress(self, n: int, total: int) -> None:
        self._dl_progress.setVisible(True)
        if total < 0:
            self._dl_progress.setRange(0, 0)
        else:
            self._dl_progress.setRange(0, int(total))
            self._dl_progress.setValue(min(int(n), int(total)))

    @Slot()
    def _on_about(self) -> None:
        show_about_dialog(self, __version__)

    def _mirror_is_running(self) -> bool:
        p = self._mirror
        return p is not None and p.state() == QProcess.ProcessState.Running

    def _set_mirroring_label_stopped(self) -> None:
        self._mir_status.setText("Mirroring: stopped")

    def _set_mirroring_label(self, sub: str) -> None:
        self._mir_status.setText(f"Mirroring: {sub}")

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def, override]
        super().showEvent(event)
        if self._thread is not None or self._adb is not None:
            return
        th = BootstrapThread()
        th.line.connect(self._append_log)
        th.progress.connect(self._on_download_progress)
        th.error.connect(self._on_bootstrap_error)
        th.ready.connect(self._on_ready)
        self._thread = th
        th.finished.connect(self._on_bootstrap_thread_finished)
        th.start()
        self._dev_status.setText("Downloading or preparing tools (first run may take a while)…")
        self._dl_progress.setVisible(True)
        self._dl_progress.setRange(0, 0)

    @Slot()
    def _on_bootstrap_thread_finished(self) -> None:
        self._thread = None
        self._dl_progress.setVisible(False)

    @Slot(str, str, object)
    def _on_ready(self, adb_s: str, sc: str, devices) -> None:  # type: ignore[no-untyped-def, override]
        self._adb = Path(adb_s)
        self._scrcpy_exe = Path(sc)
        self._thread = None
        self._apply_devices(devices)
        self._dl_progress.setVisible(False)
        self._btn_refresh.setEnabled(True)
        self._btn_reset_adb.setEnabled(True)
        self._btn_wireless.setEnabled(True)

    @Slot(str)
    def _on_bootstrap_error(self, err: str) -> None:
        self._thread = None
        self._append_log(err)
        self._dev_status.setText("Setup failed — see log.")
        self._dl_progress.setVisible(False)
        QMessageBox.critical(
            self,
            "scrcpy-gui",
            "First-time setup or device listing failed. Check the log, then retry."
            f"\n\n{err[:800]}",
        )

    def _apply_devices(self, devices) -> None:  # type: ignore[no-untyped-def, override]
        if not devices:
            self._devices = []
        else:
            o = next(iter(devices), None)
            if isinstance(o, adb.AdbDevice):
                self._devices = list(devices)
            else:
                self._devices = [adb.AdbDevice(s, st) for s, st in list(devices)]  # type: ignore[arg-type]
        self._table.setRowCount(0)
        for d in self._devices:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(d.serial))
            self._table.setItem(r, 1, QTableWidgetItem(d.state))
            m = d.model or "\u2014"
            self._table.setItem(r, 2, QTableWidgetItem(m))
        self._select_default_row()
        self._sync_start_and_status()
        if self._adb:
            self._dev_status.setText(connection_ux.primary_status_line(self._devices))

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

    def _target_ready_serial(self, d: list[adb.AdbDevice]) -> str | None:
        r = set(connection_ux.ready_serials(d))
        if not r:
            return None
        if len(r) == 1:
            return next(iter(r))
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
        if not self._adb or not self._scrcpy_exe:
            return
        if not self._mirror_is_running():
            self._set_mirroring_label_stopped()
        self._dev_status.setText(connection_ux.primary_status_line(self._devices))
        sel = self._row_selected_ready_serial()
        running = self._mirror_is_running()
        self._btn_start.setEnabled(
            connection_ux.can_start_mirroring(self._devices, sel) and not running
        )
        self._btn_stop.setEnabled(running)

    @Slot()
    def _on_refresh(self) -> None:
        if not self._adb or not self._scrcpy_exe:
            return
        self._pending_mirroring_start = False
        self._start_device_list()

    def _start_device_list(self) -> None:
        if not self._adb or self._list_thread is not None:
            return
        t = AdbListDevicesThread(self._adb)
        self._list_thread = t
        t.list_ready.connect(self._on_async_list_ready)
        t.failed.connect(self._on_list_failed)
        t.finished.connect(self._on_list_thread_finished)
        t.start()
        self._dev_status.setText("Refreshing device list…")

    @Slot()
    def _on_list_thread_finished(self) -> None:
        self._list_thread = None

    @Slot(object)
    def _on_async_list_ready(self, devs) -> None:  # type: ignore[no-untyped-def, override]
        dlist: list[adb.AdbDevice] = list(devs) if devs else []
        self._apply_devices(dlist)
        want_start = self._pending_mirroring_start
        self._pending_mirroring_start = False
        if want_start:
            self._complete_mirroring_after_list(self._devices)

    @Slot(str)
    def _on_list_failed(self, msg: str) -> None:
        self._append_log(msg)
        if self._pending_mirroring_start:
            self._pending_mirroring_start = False
        self._dev_status.setText("Could not list devices (see log).")

    def _complete_mirroring_after_list(self, dlist: list[adb.AdbDevice]) -> None:
        if self._mirror_is_running():
            return
        serial = self._target_ready_serial(dlist)
        if serial is None:
            QMessageBox.information(
                self,
                "scrcpy-gui",
                "Select a device row in the “device” state, or connect only one phone, then try again.",
            )
            return
        self._launch_scrcpy(serial)

    @Slot()
    def _on_start(self) -> None:
        if not self._adb or not self._scrcpy_exe:
            return
        if self._mirror_is_running():
            return
        if self._list_thread is not None:
            return
        self._pending_mirroring_start = True
        self._start_device_list()

    def _launch_scrcpy(self, serial: str) -> None:
        ex = self._scrcpy_exe
        a = self._adb
        if not ex or not a or self._mirror is not None:
            return
        base_args = self._current_scrcpy_extra_args()
        if not self._chk_record.isChecked():
            self._last_record_path_for_copy = None
            extras = list(base_args)
        else:
            oneshot = self._record_oneshot
            if oneshot is not None:
                path = oneshot
            else:
                raw = self._settings.value("mirroring/record_last_dir", None, str)
                sval = str(raw) if isinstance(raw, str) and str(raw).strip() else None
                out_dir = recording_paths.effective_output_dir(sval, log=self._append_log)
                path = recording_paths.next_automatic_record_path(out_dir)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self._append_log(f"Recording: cannot create output folder: {e!s}")
                return
            if oneshot is not None:
                self._record_oneshot = None
            self._settings.setValue("mirroring/record_last_dir", str(path.parent.resolve()))
            extras = list(base_args) + recording_paths.build_record_arg(path)
            self._last_record_path_for_copy = path.resolve()
        p = QProcess(self)
        self._mirror = p
        p.setProgram(str(ex))
        p.setArguments(
            scrcpy_runner.scrcpy_arguments_list(serial, extras),
        )
        env = QProcessEnvironment.systemEnvironment()
        env.insert("ADB", str(a))
        p.setProcessEnvironment(env)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        p.readyReadStandardOutput.connect(self._on_scrcpy_output)
        p.finished.connect(self._on_scrcpy_finished)
        p.errorOccurred.connect(self._on_scrcpy_error)
        self._set_mirroring_label("running…")
        p.start()
        self._btn_stop.setEnabled(True)
        self._btn_start.setEnabled(False)

    @Slot()
    def _on_scrcpy_error(self) -> None:
        p = self._mirror
        if p is None:
            return
        self._append_log(f"scrcpy: {p.errorString()}")
        self._clear_scrcpy_process()

    @Slot()
    def _on_scrcpy_output(self) -> None:
        p = self._mirror
        if p is None:
            return
        out = bytes(p.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in out.splitlines():
            t = line.rstrip()
            if t:
                self._append_log(t)

    @Slot()
    def _on_scrcpy_finished(self) -> None:
        p = self._mirror
        if p is None:
            return
        code = p.exitCode()
        self._append_log(f"scrcpy process exited (code {code})")
        self._set_mirroring_label(f"exited (code {code})")
        self._clear_scrcpy_process()

    def _clear_scrcpy_process(self) -> None:
        p = self._mirror
        if p is not None:
            p.deleteLater()
        self._mirror = None
        self._btn_stop.setEnabled(False)
        self._sync_start_and_status()

    @Slot()
    def _on_stop_mirror(self) -> None:
        p = self._mirror
        if p is not None and p.state() == QProcess.ProcessState.Running:
            self._append_log("Stopping scrcpy…")
            p.kill()

    @Slot()
    def _on_connection_help(self) -> None:
        ConnectionHelpDialog(self).exec()

    @Slot()
    def _on_wireless(self) -> None:
        if not self._adb:
            return
        dlg = WirelessDialog(
            self,
            self._adb,
            self._row_selected_ready_serial,
            self._append_log,
            self._on_refresh,
        )
        dlg.exec()

    @Slot()
    def _on_reset_adb(self) -> None:
        if not self._adb or self._restart_thread is not None:
            return
        th = AdbRestartThread(self._adb)
        self._restart_thread = th
        th.done.connect(self._on_adb_restarted)
        th.finished.connect(self._on_restart_thread_finished)
        th.start()
        self._dev_status.setText("Restarting ADB server…")

    @Slot()
    def _on_restart_thread_finished(self) -> None:
        self._restart_thread = None

    @Slot(str)
    def _on_adb_restarted(self, out: str) -> None:
        if out.strip():
            self._append_log(out.strip())
        self._append_log("ADB server restarted. Refreshing device list…")
        self._on_refresh()

    @Slot()
    def _copy(self) -> None:
        tail = self._last_log_for_copy[-5000:]
        s = _details_text(
            __version__,
            self._adb,
            self._scrcpy_exe,
            tail,
            " ".join(self._current_scrcpy_extra_args()) or "(defaults)",
            record_to_file=self._chk_record.isChecked(),
            last_record_path=str(self._last_record_path_for_copy)
            if self._last_record_path_for_copy is not None
            else "",
        )
        QApplication.clipboard().setText(s)

def _details_text(
    version: str,
    adb_path: Path | None,
    sc: Path | None,
    last_log: str,
    mirroring_args: str = "",
    *,
    record_to_file: bool = False,
    last_record_path: str = "",
) -> str:
    if not record_to_file:
        rline = "off"
    elif not last_record_path:
        rline = "on, file: (none started yet with recording)"
    else:
        rline = f"on, file: {last_record_path}"
    return (
        f"scrcpy-gui {version}\n"
        f"OS: {platform.platform()}\n"
        f"Python: {sys.version.splitlines()[0]}\n"
        f"adb: {adb_path}\n"
        f"scrcpy: {sc}\n"
        f"mirroring extra args: {mirroring_args}\n"
        f"record to file: {rline}\n"
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
