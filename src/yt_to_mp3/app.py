from __future__ import annotations

import ctypes
import sys
from contextlib import suppress
from pathlib import Path

from yt_to_mp3.services.audio import AudioProcessingError
from yt_to_mp3.services.downloader import DownloadService
from yt_to_mp3.ui.main_window import MainWindow


def _enable_high_dpi() -> None:
    if sys.platform != "win32":
        return
    with suppress(AttributeError, OSError):
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]


def _resource_path(relative_path: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / relative_path


def _self_test() -> int:
    try:
        DownloadService().check_dependencies()
        return 0
    except AudioProcessingError:
        return 1


def main() -> int:
    _enable_high_dpi()
    if "--self-test" in sys.argv:
        return _self_test()
    window = MainWindow()
    icon = _resource_path("assets/app.ico")
    if icon.is_file():
        with suppress(Exception):
            window.iconbitmap(default=str(icon))
    window.mainloop()
    return 0
