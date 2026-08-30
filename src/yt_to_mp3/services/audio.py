from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from yt_to_mp3.models import (
    LoudnessMeasurement,
    MediaInfo,
    NormalizationPlan,
    NormalizationSettings,
)

ProgressCallback = Callable[[float, str], None]
LOUDNORM_JSON_PATTERN = re.compile(r'\{\s*"input_i".*?\}', re.DOTALL)
MAXIMUM_MP3_BITRATE = "320k"


class AudioProcessingError(RuntimeError):
    pass


class ProcessingCancelled(AudioProcessingError):
    pass


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[3]


def find_media_binary(name: str) -> Path:
    executable_name = f"{name}.exe" if os.name == "nt" else name
    configured_directory = os.environ.get("YT_TO_MP3_FFMPEG_DIR")
    candidates = []
    if configured_directory:
        candidates.append(Path(configured_directory) / executable_name)
    root = _application_root()
    candidates.extend(
        (
            root / "ffmpeg" / executable_name,
            root / "vendor" / "ffmpeg" / executable_name,
            root / executable_name,
        )
    )
    discovered = shutil.which(executable_name)
    if discovered:
        candidates.append(Path(discovered))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise AudioProcessingError(
        f"{executable_name} was not found. Install FFmpeg or set "
        "YT_TO_MP3_FFMPEG_DIR to the folder containing ffmpeg and ffprobe."
    )


def verify_media_binary(path: Path) -> None:
    try:
        result = subprocess.run(
            [str(path), "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=_creation_flags(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AudioProcessingError(f"{path.name} could not start: {error}") from error
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip().splitlines()
        message = details[-1] if details else f"exit code {result.returncode}"
        raise AudioProcessingError(f"{path.name} is not usable: {message}")


def probe_media(source: Path, ffprobe_path: Path | None = None) -> MediaInfo:
    ffprobe = ffprobe_path or find_media_binary("ffprobe")
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "format=duration:stream=sample_rate,channels",
        "-of",
        "json",
        str(source),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "FFprobe could not read the downloaded audio."
        raise AudioProcessingError(message)
    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        return MediaInfo(
            duration=float(payload["format"]["duration"]),
            sample_rate=int(stream["sample_rate"]),
            channels=int(stream["channels"]),
        )
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AudioProcessingError("FFprobe returned incomplete audio information.") from error


def analyze_loudness(
    source: Path,
    settings: NormalizationSettings,
    ffmpeg_path: Path | None = None,
) -> LoudnessMeasurement:
    ffmpeg = ffmpeg_path or find_media_binary("ffmpeg")
    audio_filter = (
        f"loudnorm=I={settings.target_lufs}:LRA={settings.loudness_range}:"
        f"TP={settings.true_peak_db}:print_format=json"
    )
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-af",
        audio_filter,
        "-f",
        "null",
        os.devnull,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
        check=False,
    )
    matches = LOUDNORM_JSON_PATTERN.findall(result.stderr)
    if result.returncode != 0 or not matches:
        details = result.stderr.strip().splitlines()
        message = details[-1] if details else "FFmpeg could not measure loudness."
        raise AudioProcessingError(message)
    try:
        values = json.loads(matches[-1])
        measurement = LoudnessMeasurement(
            integrated_lufs=float(values["input_i"]),
            true_peak_db=float(values["input_tp"]),
            loudness_range=float(values["input_lra"]),
            threshold_lufs=float(values["input_thresh"]),
            target_offset=float(values["target_offset"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AudioProcessingError("FFmpeg returned invalid loudness measurements.") from error
    if not all(
        math.isfinite(value)
        for value in (
            measurement.integrated_lufs,
            measurement.true_peak_db,
            measurement.loudness_range,
            measurement.threshold_lufs,
            measurement.target_offset,
        )
    ):
        raise AudioProcessingError("The audio is silent or its loudness could not be measured.")
    return measurement


def create_normalization_plan(
    measurement: LoudnessMeasurement,
    settings: NormalizationSettings,
) -> NormalizationPlan:
    if not settings.enabled or measurement.integrated_lufs >= settings.quiet_threshold_lufs:
        return NormalizationPlan(
            should_normalize=False,
            requested_target_lufs=settings.target_lufs,
            effective_target_lufs=measurement.integrated_lufs,
            estimated_limiter_reduction_db=0.0,
        )

    desired_gain = settings.target_lufs - measurement.integrated_lufs
    peak_safe_gain = settings.true_peak_db - measurement.true_peak_db
    required_limiting = max(0.0, desired_gain - peak_safe_gain)
    maximum_safe_target = (
        measurement.integrated_lufs + peak_safe_gain + settings.max_limiter_reduction_db
    )
    effective_target = min(settings.target_lufs, maximum_safe_target)
    actual_gain = effective_target - measurement.integrated_lufs
    actual_limiting = max(0.0, actual_gain - peak_safe_gain)
    return NormalizationPlan(
        should_normalize=True,
        requested_target_lufs=settings.target_lufs,
        effective_target_lufs=round(effective_target, 2),
        estimated_limiter_reduction_db=round(min(required_limiting, actual_limiting), 2),
    )


def _loudnorm_filter(
    measurement: LoudnessMeasurement,
    plan: NormalizationPlan,
    settings: NormalizationSettings,
    sample_rate: int,
) -> str:
    return (
        f"loudnorm=I={plan.effective_target_lufs}:LRA={settings.loudness_range}:"
        f"TP={settings.true_peak_db}:measured_I={measurement.integrated_lufs}:"
        f"measured_LRA={measurement.loudness_range}:measured_TP={measurement.true_peak_db}:"
        f"measured_thresh={measurement.threshold_lufs}:offset={measurement.target_offset}:"
        f"linear=true:print_format=summary,aresample={sample_rate}"
    )


def encode_mp3(
    source: Path,
    destination: Path,
    media_info: MediaInfo,
    settings: NormalizationSettings,
    measurement: LoudnessMeasurement | None,
    plan: NormalizationPlan | None,
    cancel_event: threading.Event,
    progress_callback: ProgressCallback | None = None,
    ffmpeg_path: Path | None = None,
) -> None:
    ffmpeg = ffmpeg_path or find_media_binary("ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
    ]
    if measurement and plan and plan.should_normalize:
        command.extend(
            ["-af", _loudnorm_filter(measurement, plan, settings, media_info.sample_rate)]
        )
    command.extend(
        [
            "-c:a",
            "libmp3lame",
            "-b:a",
            MAXIMUM_MP3_BITRATE,
            "-id3v2_version",
            "3",
            "-progress",
            "pipe:1",
            "-nostats",
            str(destination),
        ]
    )
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
        )
    except OSError as error:
        raise AudioProcessingError(f"FFmpeg could not start: {error}") from error
    output_lines: list[str] = []
    assert process.stdout is not None
    try:
        for raw_line in process.stdout:
            line = raw_line.strip()
            output_lines.append(line)
            if cancel_event.is_set():
                process.terminate()
                raise ProcessingCancelled("Conversion cancelled.")
            if line.startswith("out_time_ms=") and media_info.duration > 0:
                try:
                    processed_seconds = int(line.partition("=")[2]) / 1_000_000
                    fraction = min(1.0, processed_seconds / media_info.duration)
                    if progress_callback:
                        progress_callback(fraction, "Converting to 320 kbps MP3")
                except ValueError:
                    pass
        return_code = process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    if return_code != 0:
        details = "\n".join(line for line in output_lines if line).strip()
        raise AudioProcessingError(details or "FFmpeg could not create the MP3 file.")
    if progress_callback:
        progress_callback(1.0, "MP3 conversion complete")


def convert_cover_to_jpeg(
    source: Path,
    destination: Path,
    ffmpeg_path: Path | None = None,
) -> Path | None:
    ffmpeg = ffmpeg_path or find_media_binary("ffmpeg")
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-frames:v",
        "1",
        str(destination),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
        check=False,
    )
    return destination if result.returncode == 0 and destination.is_file() else None
