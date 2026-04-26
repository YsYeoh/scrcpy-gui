import os
import sys
from pathlib import Path
from unittest import mock

from scrcpy_gui import paths


def test_cache_root_uses_localappdata_on_windows() -> None:
    """Resolve Windows cache path; sys.platform mocked so this runs on Linux CI too."""
    fake = {"LOCALAPPDATA": r"C:\Users\X\AppData\Local"}
    with mock.patch.dict(os.environ, fake, clear=True):
        with mock.patch.object(sys, "platform", "win32"):
            assert paths.cache_root() == Path(
                r"C:\Users\X\AppData\Local\scrcpy-gui\cache"
            )
