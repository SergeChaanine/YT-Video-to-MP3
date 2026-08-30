from __future__ import annotations

import os
import re
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yt_dlp
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, WOAS, ID3NoHeaderError

from yt_to_mp3.models import NormalizationSettings, TrackMetadata
from yt_to_mp3.services.audio import (
    AudioProcessingError,
    ProcessingCancelled,
    analyze_loudness,
    convert_cover_to_jpeg,
    create_normalization_plan,
    encode_mp3,
    find_media_binary,
    probe_media,
    verify_media_binary,
)
from yt_to_mp3.services.javascript import (
    find_deno_runtime,
    javascript_options,
    verify_ejs_package,
)
from yt_to_mp3.services.metadata import metadata_from_info

ProgressCallback = Callable[[float, str], None]
LogCallback = Callable[[str], None]
AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mka",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
}
IMAGE_EXTENSIONS = {".avif", ".jpeg", ".jpg", ".png", ".webp"}
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class DownloadError(RuntimeError):
    pass


class DownloadCancelled(DownloadError):
    pass


class _Logger:
    def __init__(self, callback: LogCallback | None = None) -> None:
        self.callback = callback

    def debug(self, message: str) -> None:
        if self.callback and message.startswith("[download]"):
            self.callback(message)

    def warning(self, message: str) -> None:
        if self.callback:
            self.callback(f"Warning: {_strip_terminal_codes(message)}")

    def error(self, message: str) -> None:
        if self.callback:
            self.callback(f"Error: {_strip_terminal_codes(message)}")


class DownloadService:
    def __init__(self, log_callback: LogCallback | None = None) -> None:
        self.log_callback = log_callback

    def check_dependencies(self) -> tuple[Path, Path, Path]:
        ffmpeg = find_media_binary("ffmpeg")
        ffprobe = find_media_binary("ffprobe")
        verify_media_binary(ffmpeg)
        verify_media_binary(ffprobe)
        deno = find_deno_runtime()
        verify_ejs_package()
        return ffmpeg, ffprobe, deno

    def _youtube_options(self, deno: Path | None = None) -> dict[str, Any]:
        runtime = deno or find_deno_runtime()
        verify_ejs_package()
        return javascript_options(runtime)

    def fetch_metadata(self, url: str, allow_playlists: bool = False) -> list[TrackMetadata]:
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": not allow_playlists,
            "logger": _Logger(self.log_callback),
        }
        options.update(self._youtube_options())
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as error:
            raise DownloadError(_clean_yt_dlp_error(str(error))) from error
        if not info:
            raise DownloadError("No downloadable audio was found for this URL.")

        entries = info.get("entries") if isinstance(info, dict) else None
        if entries is not None:
            if not allow_playlists:
                raise DownloadError(
                    "This is a playlist. Enable playlist downloads to add every track."
                )
            tracks = [
                metadata_from_info(entry, url)
                for entry in entries
                if isinstance(entry, dict) and entry.get("url")
            ]
            if not tracks:
                raise DownloadError("The playlist does not contain downloadable tracks.")
            return tracks
        return [metadata_from_info(info, url)]

    def download_track(
        self,
        metadata: TrackMetadata,
        destination: Path,
        normalization: NormalizationSettings,
        overwrite: bool,
        cancel_event: threading.Event,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        if destination.exists() and not overwrite:
            raise DownloadError(f"A file named '{destination.name}' already exists.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg, ffprobe, deno = self.check_dependencies()

        with tempfile.TemporaryDirectory(prefix="yt_to_mp3_") as temporary_directory:
            workspace = Path(temporary_directory)
            source = self._download_source(
                metadata.url,
                workspace,
                cancel_event,
                progress_callback,
                deno,
            )
            if cancel_event.is_set():
                raise DownloadCancelled("Download cancelled.")

            media_info = probe_media(source, ffprobe)
            measurement = None
            plan = None
            if normalization.enabled:
                _report(progress_callback, 0.66, "Analyzing loudness")
                try:
                    measurement = analyze_loudness(source, normalization, ffmpeg)
                    plan = create_normalization_plan(measurement, normalization)
                    if self.log_callback:
                        if plan.should_normalize:
                            self.log_callback(
                                f"Measured {measurement.integrated_lufs:.2f} LUFS; "
                                f"normalizing toward {plan.effective_target_lufs:.2f} LUFS."
                            )
                        else:
                            self.log_callback(
                                f"Measured {measurement.integrated_lufs:.2f} LUFS; "
                                "no volume change needed."
                            )
                except AudioProcessingError as error:
                    if self.log_callback:
                        self.log_callback(
                            f"Loudness could not be measured ({error}); "
                            "converting without a volume change."
                        )

            encoded_file = workspace / "completed.mp3"

            def conversion_progress(fraction: float, message: str) -> None:
                _report(progress_callback, 0.70 + (fraction * 0.25), message)

            try:
                encode_mp3(
                    source=source,
                    destination=encoded_file,
                    media_info=media_info,
                    settings=normalization,
                    measurement=measurement,
                    plan=plan,
                    cancel_event=cancel_event,
                    progress_callback=conversion_progress,
                    ffmpeg_path=ffmpeg,
                )
            except ProcessingCancelled as error:
                raise DownloadCancelled(str(error)) from error

            if cancel_event.is_set():
                raise DownloadCancelled("Download cancelled.")
            _report(progress_callback, 0.96, "Adding artist, title, and cover art")
            thumbnail = _find_thumbnail(workspace, source)
            cover = None
            if thumbnail:
                cover = convert_cover_to_jpeg(thumbnail, workspace / "cover.jpg", ffmpeg)
            _write_id3_tags(encoded_file, metadata, cover)

            if destination.exists() and not overwrite:
                raise DownloadError(
                    f"A file named '{destination.name}' was created while downloading."
                )
            os.replace(encoded_file, destination)
            _report(progress_callback, 1.0, "Completed")
            return destination

    def _download_source(
        self,
        url: str,
        workspace: Path,
        cancel_event: threading.Event,
        progress_callback: ProgressCallback | None,
        deno: Path,
    ) -> Path:
        def hook(status: dict[str, Any]) -> None:
            if cancel_event.is_set():
                raise DownloadCancelled("Download cancelled.")
            if status.get("status") == "downloading":
                downloaded = status.get("downloaded_bytes") or 0
                total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
                fraction = min(1.0, downloaded / total) if total else 0.0
                speed = status.get("speed")
                description = "Downloading best available audio"
                if isinstance(speed, (int, float)) and speed > 0:
                    description += f" · {_human_bytes(speed)}/s"
                _report(progress_callback, fraction * 0.62, description)
            elif status.get("status") == "finished":
                _report(progress_callback, 0.63, "Audio download complete")

        options: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": str(workspace / "source.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "overwrites": True,
            "continuedl": True,
            "writethumbnail": True,
            "progress_hooks": [hook],
            "logger": _Logger(self.log_callback),
        }
        options.update(self._youtube_options(deno))
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                prepared_filename = Path(ydl.prepare_filename(info)) if info else None
        except DownloadCancelled:
            raise
        except yt_dlp.utils.DownloadError as error:
            if cancel_event.is_set():
                raise DownloadCancelled("Download cancelled.") from error
            raise DownloadError(_clean_yt_dlp_error(str(error))) from error

        candidates: list[Path] = []
        if prepared_filename and prepared_filename.is_file():
            candidates.append(prepared_filename)
        candidates.extend(
            path
            for path in workspace.glob("source.*")
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        )
        if not candidates:
            raise DownloadError(
                "yt-dlp finished, but the downloaded audio file could not be found."
            )
        return max(set(candidates), key=lambda path: path.stat().st_size)


def _write_id3_tags(mp3_path: Path, metadata: TrackMetadata, cover_path: Path | None) -> None:
    try:
        tags = ID3(mp3_path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("TIT2")
    tags.delall("TPE1")
    tags.add(TIT2(encoding=3, text=metadata.title))
    tags.add(TPE1(encoding=3, text=metadata.artist))
    if metadata.album:
        tags.delall("TALB")
        tags.add(TALB(encoding=3, text=metadata.album))
    if metadata.release_year:
        tags.delall("TDRC")
        tags.add(TDRC(encoding=3, text=metadata.release_year))
    if metadata.url:
        tags.delall("WOAS")
        tags.add(WOAS(url=metadata.url))
    if cover_path and cover_path.is_file():
        tags.delall("APIC")
        tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=cover_path.read_bytes(),
            )
        )
    tags.save(mp3_path, v2_version=3)


def _find_thumbnail(workspace: Path, source: Path) -> Path | None:
    thumbnails = [
        path
        for path in workspace.iterdir()
        if path.is_file() and path != source and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return max(thumbnails, key=lambda path: path.stat().st_size) if thumbnails else None


def _clean_yt_dlp_error(message: str) -> str:
    message = _strip_terminal_codes(message)
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    cleaned = lines[-1] if lines else "yt-dlp could not process this URL."
    return cleaned.removeprefix("ERROR: ")


def _strip_terminal_codes(message: str) -> str:
    return ANSI_ESCAPE_PATTERN.sub("", message)


def _report(callback: ProgressCallback | None, fraction: float, message: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, fraction)), message)


def _human_bytes(value: float) -> str:
    units = ("B", "KB", "MB", "GB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
