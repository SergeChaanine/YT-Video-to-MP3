from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from yt_to_mp3.models import TrackMetadata
from yt_to_mp3.services.filenames import clean_artist, clean_song_title, split_video_title


def _first_text(info: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def metadata_from_info(info: Mapping[str, Any], original_url: str) -> TrackMetadata:
    raw_title = _first_text(info, "title", "fulltitle") or "Unknown title"
    artist = _first_text(info, "artist")
    track = _first_text(info, "track", "alt_title")
    needs_review = False

    if not artist or not track:
        split = split_video_title(raw_title)
        if split:
            parsed_artist, parsed_title = split
            artist = artist or parsed_artist
            track = track or parsed_title

    if not artist:
        artist = _first_text(info, "creator", "uploader", "channel") or "Unknown artist"
        needs_review = True
    if not track:
        track = raw_title
        needs_review = True

    duration = info.get("duration")
    return TrackMetadata(
        url=_first_text(info, "webpage_url", "original_url") or original_url,
        artist=clean_artist(artist),
        title=clean_song_title(track),
        video_id=str(info.get("id") or ""),
        duration=float(duration) if isinstance(duration, (int, float)) else None,
        needs_review=needs_review,
    )
