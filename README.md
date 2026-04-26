# scrcpy-gui

Small open-source **desktop** wrapper around **[scrcpy](https://github.com/Genymobile/scrcpy)** so **Windows** users can go from *install* → *USB* → *mirror* without a terminal. **v1** targets **Windows 10/11**; other OS support may follow.

## What it does

- On first run, **downloads and caches** pinned versions of:
  - **Android platform-tools** (ADB) from Google  
  - **scrcpy** for Windows (zip from GitHub releases)  
- Lists **connected devices** (`adb devices` style).  
- Starts **one** mirroring window when **exactly one** device is in the `device` state (see in-app help for USB debugging).

## Requirements

- **Windows 10+** (v1).  
- A USB data cable, Android **USB debugging** enabled, and **accepting the USB debugging** prompt on the device.

## Develop / run from source

```text
py -3.12 -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m scrcpy_gui
```

(Use `python -m` if the `scrcpy-gui` entry script is not on your `PATH`.)

**Tests:** `python -m pytest -q`

## Windows executable (optional)

With dev dependencies (`pyinstaller`), from the repository root (after `pip install -e ".[dev]"`):

```text
py -m PyInstaller --noconfirm --windowed --name scrcpy-gui --add-data "src/scrcpy_gui/data;scrcpy_gui/data" src/scrcpy_gui/__main__.py
```

If the GUI cannot find `vendor-windows.json` at runtime, add `--collect-data scrcpy_gui` (PyInstaller 6+) or list `scrcpy_gui` hidden imports in a `.spec` and rebuild.

## Cache location

- Windows: under `%LOCALAPPDATA%\scrcpy-gui\cache\` (platform-tools and scrcpy folders).

## Legal

- Project license: `LICENSE` (MIT) for *this* repository’s own code.  
- Third-party components: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).  
- This project is not affiliated with Genymobile, Google, or The Qt Company.

## Disclaimer

- Software is provided **as-is**, without warranty. Screen mirroring depends on ADB, drivers, and device settings; see the scrcpy project for upstream behavior and limitations.
