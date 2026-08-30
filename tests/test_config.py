import json
from pathlib import Path

from yt_to_mp3.config import AppSettings, SettingsStore


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    expected = AppSettings(
        output_directory="C:/Music",
        normalize_quiet_audio=False,
        normalization_mode="gentle",
        auto_add_clipboard_urls=False,
        allow_playlists=True,
        theme="light",
    )

    store.save(expected)

    assert store.load() == expected


def test_unknown_settings_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "light", "future_option": True}), encoding="utf-8")

    result = SettingsStore(path).load()

    assert result.theme == "light"
    assert not hasattr(result, "future_option")
