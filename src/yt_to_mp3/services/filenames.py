from __future__ import annotations

import re
import unicodedata
from pathlib import Path

INVALID_WINDOWS_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SPACE_PATTERN = re.compile(r"\s+")
DECORATION_PATTERN = re.compile(
    r"\s*[\[(](?:official\s+(?:music\s+)?video|official\s+audio|"
    r"lyric(?:s|\s+video)?|audio|visuali[sz]er|hd|4k)[\])]\s*$",
    flags=re.IGNORECASE,
)
QUOTED_TITLE_PATTERN = re.compile(r"^[\"'“”‘’](.*)[\"'“”‘’]$")
ARTIST_SUFFIX_PATTERN = re.compile(
    r"\s*(?:-|–|—)?\s*(?:official|vevo|topic)\s*$",
    flags=re.IGNORECASE,
)


def clean_component(value: str) -> str:
    value = unicodedata.normalize("NFC", value or "")
    value = INVALID_WINDOWS_CHARACTERS.sub("-", value)
    value = SPACE_PATTERN.sub(" ", value).strip(" .-")
    return value or "Unknown"


def clean_song_title(value: str) -> str:
    value = SPACE_PATTERN.sub(" ", value or "").strip()
    previous = None
    while value != previous:
        previous = value
        value = DECORATION_PATTERN.sub("", value).strip()
    quoted = QUOTED_TITLE_PATTERN.match(value)
    if quoted:
        value = quoted.group(1).strip()
    return clean_component(value)


def clean_artist(value: str) -> str:
    value = ARTIST_SUFFIX_PATTERN.sub("", value or "").strip()
    return clean_component(value)


def split_video_title(value: str) -> tuple[str, str] | None:
    cleaned = clean_song_title(value)
    for separator in (" - ", " – ", " — "):
        if separator in cleaned:
            artist, title = cleaned.split(separator, 1)
            if artist.strip() and title.strip():
                return clean_artist(artist), clean_song_title(title)
    return None


def build_filename(artist: str, title: str, max_length: int = 180) -> str:
    artist = clean_artist(artist)
    title = clean_song_title(title)
    suffix = ".mp3"
    stem = f"{artist} - {title}"
    if len(stem) + len(suffix) > max_length:
        stem_budget = max_length - len(suffix)
        separator_length = len(" - ")
        artist_budget = min(len(artist), max(20, stem_budget // 3))
        title_budget = stem_budget - artist_budget - separator_length
        artist = artist[:artist_budget].rstrip(" .-")
        title = title[:title_budget].rstrip(" .-")
        stem = f"{artist} - {title}"
    return f"{stem}{suffix}"


def available_output_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    for index in range(2, 10_000):
        numbered = directory / f"{stem} ({index}){candidate.suffix}"
        if not numbered.exists():
            return numbered
    raise RuntimeError(f"Could not find an available filename for {filename}")
