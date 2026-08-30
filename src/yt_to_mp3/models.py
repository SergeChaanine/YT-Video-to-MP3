from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class ItemStatus(StrEnum):
    PENDING = "Pending"
    READING_METADATA = "Reading metadata"
    READY = "Ready"
    DOWNLOADING = "Downloading"
    ANALYZING = "Analyzing loudness"
    CONVERTING = "Converting"
    TAGGING = "Adding metadata"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass(slots=True)
class TrackMetadata:
    url: str
    artist: str
    title: str
    video_id: str = ""
    duration: float | None = None
    thumbnail_url: str | None = None
    album: str | None = None
    release_year: str | None = None
    needs_review: bool = False


@dataclass(slots=True)
class QueueItem:
    url: str
    id: str = field(default_factory=lambda: uuid4().hex)
    metadata: TrackMetadata | None = None
    status: ItemStatus = ItemStatus.PENDING
    progress: float = 0.0
    message: str = ""
    output_path: Path | None = None
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class NormalizationSettings:
    enabled: bool = True
    quiet_threshold_lufs: float = -20.0
    target_lufs: float = -16.0
    true_peak_db: float = -1.0
    loudness_range: float = 11.0
    max_limiter_reduction_db: float = 3.0


@dataclass(frozen=True, slots=True)
class LoudnessMeasurement:
    integrated_lufs: float
    true_peak_db: float
    loudness_range: float
    threshold_lufs: float
    target_offset: float


@dataclass(frozen=True, slots=True)
class NormalizationPlan:
    should_normalize: bool
    requested_target_lufs: float
    effective_target_lufs: float
    estimated_limiter_reduction_db: float


@dataclass(frozen=True, slots=True)
class MediaInfo:
    duration: float
    sample_rate: int
    channels: int


@dataclass(slots=True)
class AppEvent:
    kind: str
    item_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
