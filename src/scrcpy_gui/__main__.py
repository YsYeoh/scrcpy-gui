import sys

def main() -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication(sys.argv)
    w = QMessageBox()
    w.setText("scrcpy-gui stub: replace in Task 6+")
    w.show()
    raise SystemExit(app.exec())

if __name__ == "__main__":
    main()
