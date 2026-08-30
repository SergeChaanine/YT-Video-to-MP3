from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

APP_DIRECTORY_NAME = "YT to MP3 Converter"


def default_output_directory() -> Path:
    desktop = Path.home() / "Desktop"
    base = desktop if desktop.exists() else Path.home()
    return base / "YT-MP3"


def settings_path() -> Path:
    app_data = os.environ.get("APPDATA")
    base = Path(app_data) if app_data else Path.home() / ".config"
    return base / APP_DIRECTORY_NAME / "settings.json"


@dataclass(slots=True)
class AppSettings:
    output_directory: str = ""
    normalize_quiet_audio: bool = True
    normalization_mode: str = "balanced"
    auto_add_clipboard_urls: bool = True
    allow_playlists: bool = False
    theme: str = "dark"

    def __post_init__(self) -> None:
        if not self.output_directory:
            self.output_directory = str(default_output_directory())

    @property
    def output_path(self) -> Path:
        return Path(self.output_directory).expanduser()


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()

    def load(self) -> AppSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            known_fields = AppSettings.__dataclass_fields__
            return AppSettings(**{key: value for key, value in data.items() if key in known_fields})
        except (OSError, ValueError, TypeError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(asdict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
