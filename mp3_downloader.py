"""Compatibility launcher for development checkouts."""

import sys
from pathlib import Path

source_directory = Path(__file__).resolve().parent / "src"
if str(source_directory) not in sys.path:
    sys.path.insert(0, str(source_directory))

from yt_to_mp3.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
