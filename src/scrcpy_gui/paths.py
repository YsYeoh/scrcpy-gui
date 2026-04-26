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
