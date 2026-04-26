# scrcpy-gui Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a **Windows** PySide6 GUI that downloads and caches **Android platform-tools** and **scrcpy**, runs `adb` to list devices, and starts **one** scrcpy session from the UI, with a **small** first installer (PyInstaller) and **open source** GitHub releases.

**Architecture:** Small Python package under `src/scrcpy_gui/` split by **paths**, **manifest (pinned URLs + SHA-256)**, **download+verify+extract**, **adb output parsing and subprocess calls**, **scrcpy subprocess**, and **one main window**. Pytest covers parsing and path logic; CI runs tests on **push/PR to main**.

**Tech stack:** Python **3.12** (3.11+), **PySide6**, **pytest**, **PyInstaller** (dev dependency or docs-only install), stdlib **urllib** + **zipfile** (avoid extra HTTP deps in v1 unless you add `httpx` later for simpler timeouts).

**Spec:** `docs/superpowers/specs/2026-04-26-scrcpy-gui-design.md`

---

## File map (v1)

| Path | Role |
|------|------|
| `pyproject.toml` | Build system, `scrcpy-gui` package, entry point `scrcpy-gui = "scrcpy_gui.__main__:main"` |
| `src/scrcpy_gui/__init__.py` | Version `__version__` |
| `src/scrcpy_gui/__main__.py` | `main()`; imports Qt and opens `MainWindow` |
| `src/scrcpy_gui/paths.py` | Windows `%LOCALAPPDATA%` cache root `scrcpy-gui/cache`, subdirs for `platform-tools` and `scrcpy` |
| `src/scrcpy_gui/manifest.py` + `data/vendor-windows.json` | Pinned **download URL**, **archive filename**, **sha256** for `platform-tools` and `scrcpy` (win64 zip) |
| `src/scrcpy_gui/download.py` | `download_to_temp`, `verify_sha256`, `extract_zip` to target dir |
| `src/scrcpy_gui/adb.py` | `adb_path`, `list_devices` → structured list, parse `adb devices` |
| `src/scrcpy_gui/scrcpy_runner.py` | `start_scrcpy(adb_serial: str | None, log: Callable[[str], None])` |
| `src/scrcpy_gui/ensure.py` | `ensure_tooling(manifest, progress, log) -> bool` if anything missing, download+extract both |
| `src/scrcpy_gui/ui/main_window.py` | PySide6: help text, table, start button, log, **Copy details** |
| `tests/test_paths.py` | `pathlib` and env mocking |
| `tests/test_adb.py` | Sample stdout fixtures |
| `tests/test_download.py` | Local tiny zip, hash verify, extract (no network) |
| `tests/test_manifest.py` | JSON load |
| `THIRD_PARTY_NOTICES.md` | scrcpy (Apache-2.0), platform-tools (Google), PySide6/Qt (LGPL) |
| `README.md` | Install, first run, device setup, where cache lives |
| `.github/workflows/ci.yml` | `python -m pytest`, on `ubuntu` + `windows` (or windows-only if Linux paths differ — keep tests pure) |
| `scrcpy-gui.spec` (optional) | PyInstaller, generated after app runs |

**Multi-device v1 rule:** list all devices; **Start mirroring** is enabled only if **exactly one** device in `device` state (or user selects a row if you add selection — the simpler rule is “exactly one authorized device” for v1 to avoid extra UI; spec allows row selection; **take the simpler: exactly one**).

---

### Task 1: Project skeleton and `pyproject.toml`

**Files:**

- Create: `pyproject.toml`, `src/scrcpy_gui/__init__.py`, `src/scrcpy_gui/__main__.py` (stub), `tests/conftest.py` (empty or `pytest` import)

- [ ] **Step 1: Add `pyproject.toml` (replace entire file)**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "scrcpy-gui"
version = "0.1.0"
description = "Open-source GUI for scrcpy (Android screen mirroring)"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = [
  "PySide6>=6.6,<7",
]
[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4.0", "pyinstaller>=6.0"]
[project.scripts]
scrcpy-gui = "scrcpy_gui.__main__:main"

[tool.setuptools]
package-dir = { "" = "src" }
[tool.setuptools.packages.find]
where = ["src"]
[tool.setuptools.package-data]
scrcpy_gui = ["data/*.json"]
```

- [ ] **Step 2: `src/scrcpy_gui/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: `src/scrcpy_gui/__main__.py` (stub, real UI in later task)**

```python
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
```

- [ ] **Step 4: Editable install and import**

Run: `cd c:\Users\yeohy\Documents\playground\scrcpy-gui` then `py -3.12 -m pip install -e ".[dev]"` (or your Python)

Expected: exit code 0, `scrcpy-gui` on PATH in that env.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/scrcpy_gui/__init__.py src/scrcpy_gui/__main__.py
git commit -m "chore: add pyproject and package skeleton"
```

---

### Task 2: Cache paths (Windows) + test

**Files:**

- Create: `src/scrcpy_gui/paths.py`, `tests/test_paths.py`

- [ ] **Step 1: Failing test `tests/test_paths.py`**

```python
import os
from unittest import mock
from scrcpy_gui import paths

def test_cache_root_uses_localappdata_on_windows() -> None:
    fake = { "LOCALAPPDATA": r"C:\Users\X\AppData\Local" }
    with mock.patch.dict(os.environ, fake, clear=True):
        assert paths.cache_root() == r"C:\Users\X\AppData\Local\scrcpy-gui\cache"
```

- [ ] **Step 2: Run to failure**

Run: `pytest tests/test_paths.py -q`

Expected: `ImportError` or `AttributeError` for `cache_root` missing.

- [ ] **Step 3: Implement `src/scrcpy_gui/paths.py`**

```python
from __future__ import annotations
import os
import sys
from pathlib import Path

def _win_cache_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return Path.home() / "AppData" / "Local" / "scrcpy-gui" / "cache"
    return Path(local) / "scrcpy-gui" / "cache"

def cache_root() -> Path:
    if sys.platform == "win32":
        return _win_cache_root()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "scrcpy-gui" / "cache"
    return Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    ) / "scrcpy-gui" / "cache"

def platform_tools_dir() -> Path:
    return cache_root() / "platform-tools"

def scrcpy_dir() -> Path:
    return cache_root() / "scrcpy"
```

- [ ] **Step 4: Pass tests**

Run: `pytest tests/test_paths.py -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/scrcpy_gui/paths.py tests/test_paths.py
git commit -m "feat: resolve per-user cache paths"
```

---

### Task 3: `vendor-windows.json` manifest and loader

**Files:**

- Create: `src/scrcpy_gui/data/vendor-windows.json` (example structure — **you must** fill real `sha256` and URLs for the versions you support in that release)
- Create: `src/scrycpy_gui/manifest.py` — **typo fix: use** `scrcpy_gui/manifest.py`

*Correction:* path must be `src/scrcpy_gui/manifest.py` (not scrycpy).

- [ ] **Step 1: Failing test `tests/test_manifest.py`**

```python
from scrcpy_gui import manifest
from importlib import resources

def test_loads_vendor_windows() -> None:
    m = manifest.load_windows()
    assert m.platform_tools.version
    assert m.scrcpy.version
    assert m.platform_tools.url.startswith("https://")
    assert m.scrcpy.url.startswith("https://")
```

Define `load_windows()` returning a `dataclass` with nested objects `platform_tools` and `scrcpy` fields: `version`, `url`, `filename`, `sha256` (or `expected_sha256`).

- [ ] **Step 2: Run failure**

`pytest tests/test_manifest.py` → fails until `manifest.py` and JSON exist.

- [ ] **Step 3: `src/scrcpy_gui/data/vendor-windows.json`**

Start from real releases you will ship, for example (URLs must be valid for your build; **replace sha256** after you verify):

```json
{
  "platform_tools": {
    "version": "35.0.2",
    "url": "https://dl.google.com/android/repository/platform-tools_r35.0.2-win.zip",
    "expected_sha256": "REPLACE_WITH_CERTUTIL_OR_SHASUM_OUTPUT"
  },
  "scrcpy": {
    "version": "3.2",
    "url": "https://github.com/Genymobile/scrcpy/releases/download/v3.2/scrcpy-win64-v3.2.zip",
    "expected_sha256": "REPLACE_WITH_OFFICIAL_RELEASE_FILE_HASH"
  }
}
```

- [ ] **Step 4: `src/scrcpy_gui/manifest.py`**

Use `importlib.resources.files("scrcpy_gui.data") / "vendor-windows.json"`, `json.load`, and `@dataclass` for typed access.

- [ ] **Step 5: Set real SHA-256**

On a **trusted** machine, download each URL once, compute:

```powershell
certutil -hashfile platform-tools_r35.0.2-win.zip SHA256
certutil -hashfile scrcpy-win64-v3.2.zip SHA256
```

Put lowercase hex in JSON.

- [ ] **Step 6: Pass tests, commit**

```bash
git add src/scrcpy_gui/manifest.py src/scrcpy_gui/data/vendor-windows.json tests/test_manifest.py
git commit -m "feat: add Windows vendor manifest with verified hashes"
```

---

### Task 4: Download, verify, extract (no network in test)

**Files:** `src/scrcpy_gui/download.py`, `tests/test_download.py`

- [ ] **Step 1: Failing test — tiny zip, known sha256**

In test: create bytes `hello`, zip one file, write to temp, compute `hashlib.sha256(zip_bytes).hexdigest()`, call `download.verify_file_sha256`, `download.extract_zip`.

- [ ] **Step 2: Implement `download.py`**

- `def verify_file_sha256(path: Path, expected_hex: str) -> None: ...` lower-case compare, raise `RuntimeError` with "hash mismatch"  
- `def extract_zip(zip_path: Path, target_dir: Path) -> None:` `zipfile.ZipFile` extractall; if needed strip single top-level folder (only if you choose flat extract — for Google zip, platform-tools is top-level; match real layout in manual test once)  
- `def download_url_to_file(url: str, dest: Path, on_progress) -> None:` `urllib.request.urlopen` in chunks, write, optional progress callback (bytes, total or None)

- [ ] **Step 3: `pytest tests/test_download.py` passes**

- [ ] **Step 4: Commit**

```bash
git add src/scrcpy_gui/download.py tests/test_download.py
git commit -m "feat: add download and zip extraction utilities"
```

---

### Task 5: `adb` device listing

**Files:** `src/scrcpy_gui/adb.py`, `tests/test_adb.py`

- [ ] **Step 1: Tests for parser only** (use raw multi-line string fixture from scrcpy docs / real sample)

```python
from scrcpy_gui import adb
SAMPLE = """
List of devices attached
R58M123ABCD\tdevice
"""
def test_parse():
    d = adb.parse_adb_devices_output(SAMPLE)
    assert d == [("R58M123ABCD", "device")]
```

Include cases: empty, `unauthorized`, `offline`, multiple lines, ignore header.

- [ ] **Step 2: Implement** `parse_adb_devices_output`, `def adb_executable(platform_tools: Path) -> Path` return `platform_tools / "platform-tools" / "adb.exe"` on Windows, `adb` on others.

- [ ] **Step 3: Optional integration (manual):** with real ADB, run `list_devices(adb_path)`; keep out of CI.

- [ ] **Step 4: Commit**

```bash
git add src/scrcpy_gui/adb.py tests/test_adb.py
git commit -m "feat: parse adb devices and resolve adb path"
```

---

### Task 6: Ensure tooling (orchestration)

**Files:** `src/scrcpy_gui/ensure.py`, wire tests with **temp dirs** and **no network** by pre-placing files if you add small helpers, or one **manual** checklist.

- [ ] **Step 1: `ensure_bootstrap(manifest, paths, log)`**

If `platform_tools` dir has no `adb.exe` under `platform-tools/adb.exe` (per extract layout), run download+extract. Same for scrcpy (your zip may extract to a folder; detect `scrcpy.exe` under `scrcpy_dir` recursively or known subpath — **run real extract once** locally, then encode that path in code, e.g. `scrcpy_dir() / "scrcpy-win64-v3.2" / "scrcpy.exe"` or flatten on extract.

- [ ] **Step 2: Log messages** to the callable for UI: "Downloading platform-tools…", "Verifying…", "Extracting…", "Done."

- [ ] **Step 3: Commit** when a manual test on your PC succeeds (download from internet allowed).

```bash
git add src/scrcpy_gui/ensure.py
git commit -m "feat: ensure ADB and scrcpy in cache on first run"
```

---

### Task 7: Scrcpy subprocess

**Files:** `src/scrcpy_gui/scrcpy_runner.py`

- [ ] **Step 1: `start_scrcpy(adb: Path, scrcpy: Path, serial: str, log_line)`** using `subprocess.Popen` and threads to read stderr/stdout into `log_line` callback.

- [ ] **Step 2: If multiple devices:** pass `"-s", serial`.

- [ ] **Step 3: Commit**

```bash
git add src/scrcpy_gui/scrcpy_runner.py
git commit -m "feat: start scrcpy and stream logs to UI"
```

---

### Task 8: `MainWindow` (replace `__main__` stub)

**Files:** `src/scrcpy_gui/ui/main_window.py`, update `__main__.py`, add `ui/__init__.py`

- [ ] **Step 1: `MainWindow` with**

- `QTextEdit` or `QPlainTextEdit` for log; `QTableWidget` with serial + state; **Start** and **Copy details** and **Refresh devices**; label with short **USB debugging** help (4 sentences max).

- [ ] **Step 2: On show:** `QThread` or `QRunnable` + `QThreadPool` to run `ensure_tooling` without blocking UI, then `adb devices`.

- [ ] **Step 3: Start** enabled if exactly one `device` row; else show `QMessageBox` or status tip.

- [ ] **Step 4: `__main__.py` creates `QApplication` and `MainWindow`.**

- [ ] **Step 5: Manual test** with one Android phone; commit.

```bash
git add src/scrcpy_gui/ui/main_window.py src/scrcpy_gui/ui/__init__.py src/scrcpy_gui/__main__.py
git commit -m "feat: main window with start mirroring"
```

---

### Task 9: PyInstaller (Windows)

**Files:** `README.md` section, optional `scrcpy-gui.spec` generated

- [ ] **Step 1: Run** `pyinstaller --name scrcpy-gui --noconfirm -w -m scrcpy_gui` or hook entry; include `datas` for `scrcpy_gui.data`.

- [ ] **Step 2: Document** exact command in README; confirm `scrcpy-gui.exe` starts on clean VM if possible.

- [ ] **Step 3: Commit** spec if you keep it: `scrcpy-gui.spec` + README.

```bash
git add scrcpy-gui.spec README.md
git commit -m "chore: document PyInstaller Windows build"
```

---

### Task 10: GitHub Actions CI

**Files:** `.github/workflows/ci.yml`

- [ ] **Step 1: `on: push, pull_request` to `main`; jobs: `test` on `windows-latest` and `ubuntu-latest`; `python 3.12`**

- [ ] **Step 2: Steps: checkout, `pip install -e ".[dev]"`, `pytest`**

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run pytest on Windows and Linux"
```

---

### Task 11: Docs and `THIRD_PARTY_NOTICES.md`

**Files:** `THIRD_PARTY_NOTICES.md`, expand `README.md`

- [ ] **Step 1:** List scrcpy Apache-2.0 and link, Google platform-tools terms link, PySide6 LGPL and link to “About Qt”.

- [ ] **Step 2:** README: one screenshot (optional in v1), steps to enable USB debugging, “first run downloads ~XX MB”.

- [ ] **Step 3: Commit**

```bash
git add THIRD_PARTY_NOTICES.md README.md
git commit -m "docs: add notices and user README"
```

---

## Plan self-review

- **Spec coverage:** Paths, manifest, download, ADB, scrcpy, minimal UI, Windows v1, open source, portfolio docs — all mapped. macOS cache paths in `paths.py` are a small forward-compat extra; v1 is Windows.  
- **No forbidden placeholders in committed JSON:** replace `REPLACE_*` in Task 3 before you merge.  
- **Type names:** `load_windows()` and manifest dataclasses are consistent across tasks.

---

**Plan complete and saved to** `docs/superpowers/plans/2026-04-26-scrcpy-gui.md`.

**Two execution options:**

1. **Subagent-driven (recommended)** — a fresh subagent per task, review between tasks, fast iteration. **Required sub-skill:** `superpowers:subagent-driven-development`.  
2. **Inline execution** — run tasks in this session with checkpoints. **Required sub-skill:** `superpowers:executing-plans`.

**Which approach do you want?**