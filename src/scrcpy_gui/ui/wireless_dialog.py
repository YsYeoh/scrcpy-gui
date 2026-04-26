from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSettings, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from scrcpy_gui import adb
from scrcpy_gui.workers import AdbRunThread

LogFn = Callable[[str], None]
RefreshFn = Callable[[], None]
SerialFn = Callable[[], str | None]


class WirelessDialog(QDialog):
    def __init__(
        self,
        parent,
        adb_path: Path,
        get_usb_serial: SerialFn,
        append_log: LogFn,
        refresh: RefreshFn,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Wireless ADB")
        self._adb = adb_path
        self._get_usb_serial = get_usb_serial
        self._append = append_log
        self._refresh = refresh
        self._active: AdbRunThread | None = None
        self._cmd_title = ""

        s = QSettings("scrcpy-gui", "scrcpy-gui")

        usb_box = QGroupBox("Switch to network (USB required first)")
        usb_lay = QFormLayout()
        self._sp_tcp = QSpinBox()
        self._sp_tcp.setRange(1, 65535)
        self._sp_tcp.setValue(int(s.value("wireless/tcpip_port", 5555) or 5555))
        self._btn_tcpip = QPushButton("Run adb tcpip (uses selected “device” over USB)")
        self._ed_connect_a = QLineEdit()
        self._ed_connect_a.setPlaceholderText("e.g. 192.168.0.5:5555")
        self._ed_connect_a.setText(str(s.value("wireless/last_connect", "") or ""))
        u_row = QHBoxLayout()
        u_row.addWidget(self._btn_tcpip)
        u_row.addWidget(QLabel("port:"))
        u_row.addWidget(self._sp_tcp)
        usb_lay.addRow(u_row)
        usb_lay.addRow("Then connect to", self._ed_connect_a)
        self._b_connect_a = QPushButton("adb connect (run after tcpip + Wi-Fi)")
        self._b_connect_a.clicked.connect(self._on_connect_a)
        self._btn_tcpip.clicked.connect(self._on_tcpip)
        usb_lay.addRow(self._b_connect_a)
        usb_box.setLayout(usb_lay)

        pair_box = QGroupBox("Pair new device (Android 11+ wireless debugging)")
        p_lay = QFormLayout()
        self._ed_pair_addr = QLineEdit()
        self._ed_pair_addr.setPlaceholderText("IP:port from phone (pairing)")
        self._ed_pair_addr.setText(str(s.value("wireless/last_pair_addr", "") or ""))
        self._ed_pair_code = QLineEdit()
        self._ed_pair_code.setPlaceholderText("Pairing code (digits)")
        p_lay.addRow("Pairing address", self._ed_pair_addr)
        p_lay.addRow("Code", self._ed_pair_code)
        self._b_pair = QPushButton("Pair")
        self._b_pair.clicked.connect(self._on_pair)
        p_lay.addRow(self._b_pair)
        self._ed_connect_b = QLineEdit()
        self._ed_connect_b.setPlaceholderText("IP:port (session / connect – from phone after pair)")
        self._ed_connect_b.setText(str(s.value("wireless/last_session_connect", "") or ""))
        p_lay.addRow("Connect to", self._ed_connect_b)
        self._b_connect_b = QPushButton("adb connect (session)")
        self._b_connect_b.clicked.connect(self._on_connect_b)
        p_lay.addRow(self._b_connect_b)
        pair_box.setLayout(p_lay)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        top = QVBoxLayout(self)
        top.addWidget(
            QLabel(
                "If both phone and PC are on the same Wi-Fi, you can use ADB over the "
                "network. Use the USB + tcpip flow when the phone is plugged in, or the "
                "Pair flow when the phone only shows “Wireless debugging.” After connect, "
                "return to the main window and tap Refresh, then start mirroring.",
            )
        )
        top.addWidget(usb_box)
        top.addWidget(pair_box)
        top.addWidget(buttons)

    def _save_w(self) -> None:
        s = QSettings("scrcpy-gui", "scrcpy-gui")
        s.setValue("wireless/tcpip_port", self._sp_tcp.value())
        s.setValue("wireless/last_connect", self._ed_connect_a.text().strip())
        s.setValue("wireless/last_pair_addr", self._ed_pair_addr.text().strip())
        s.setValue("wireless/last_session_connect", self._ed_connect_b.text().strip())

    @Slot()
    def _on_tcpip(self) -> None:
        if self._active is not None:
            return
        self._save_w()
        serial = self._get_usb_serial()
        if not serial:
            QMessageBox.information(
                self,
                "scrcpy-gui",
                "Connect the phone with USB, ensure it shows as “device” in the main list, "
                "select its row if there are several, then try again.",
            )
            return
        port = int(self._sp_tcp.value())
        th = AdbRunThread(self._adb, adb.argv_tcpip(port, serial))
        self._wire_run(th, f"adb tcpip (serial {serial}, port {port})")

    def _captured_output(self, cp: subprocess.CompletedProcess[str], title: str) -> None:
        combined = (cp.stdout or "") + (cp.stderr or "")
        if combined.strip():
            self._append(combined.rstrip())
        if cp.returncode != 0:
            self._append(f"ADB exited with code {cp.returncode} ({title}).")
            QMessageBox.warning(
                self,
                "scrcpy-gui",
                f"Command failed (exit {cp.returncode}). See the main log for details.",
            )
        else:
            QMessageBox.information(
                self,
                "scrcpy-gui",
                f"{title} finished. Tap Refresh on the main window if a device does not yet appear.",
            )
            self._refresh()

    @Slot()
    def _on_connect_a(self) -> None:
        if self._active is not None:
            return
        self._save_w()
        addr = self._ed_connect_a.text().strip()
        if not addr:
            QMessageBox.information(self, "scrcpy-gu", "Enter the phone’s IP:port, then try again.")
            return
        th = AdbRunThread(self._adb, adb.argv_connect(addr))
        self._wire_run(th, "adb connect")

    @Slot()
    def _on_pair(self) -> None:
        if self._active is not None:
            return
        self._save_w()
        addr = self._ed_pair_addr.text().strip()
        code = self._ed_pair_code.text().strip()
        if not addr or not code:
            QMessageBox.information(
                self,
                "scrcpy-gui",
                "Enter the pairing address and the pairing code from the phone.",
            )
            return
        th = AdbRunThread(self._adb, adb.argv_pair(addr, code))
        self._wire_run(th, "adb pair")

    @Slot()
    def _on_connect_b(self) -> None:
        if self._active is not None:
            return
        self._save_w()
        addr = self._ed_connect_b.text().strip()
        if not addr:
            QMessageBox.information(
                self,
                "scrcpy-gui",
                "Enter the connect IP:port from the phone, then try again.",
            )
            return
        th = AdbRunThread(self._adb, adb.argv_connect(addr))
        self._wire_run(th, "adb connect (after pair)")

    def _wire_run(self, th: AdbRunThread, title: str) -> None:
        self._active = th
        self._cmd_title = title
        th.done.connect(self._on_adb_done)
        th.finished.connect(th.deleteLater)
        th.start()

    @Slot(object)
    def _on_adb_done(self, cp: object) -> None:
        try:
            if not isinstance(cp, subprocess.CompletedProcess):
                return
            self._captured_output(cp, self._cmd_title)
        finally:
            self._active = None
