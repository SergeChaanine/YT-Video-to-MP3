from yt_to_mp3.models import LoudnessMeasurement, NormalizationSettings
from yt_to_mp3.services.audio import (
    MAXIMUM_MP3_BITRATE,
    NO_MP3_METADATA_OPTIONS,
    create_normalization_plan,
)


def measurement(integrated: float, peak: float) -> LoudnessMeasurement:
    return LoudnessMeasurement(
        integrated_lufs=integrated,
        true_peak_db=peak,
        loudness_range=7.7,
        threshold_lufs=integrated - 10,
        target_offset=0.0,
    )


def test_reference_track_reaches_balanced_target_with_limiter_cap() -> None:
    result = create_normalization_plan(
        measurement(-27.18, -9.18),
        NormalizationSettings(),
    )

    assert result.should_normalize is True
    assert result.effective_target_lufs == -16.0
    assert result.estimated_limiter_reduction_db == 3.0


def test_track_above_quiet_threshold_is_not_changed() -> None:
    result = create_normalization_plan(
        measurement(-18.5, -2.0),
        NormalizationSettings(),
    )

    assert result.should_normalize is False
    assert result.effective_target_lufs == -18.5


def test_extremely_dynamic_track_uses_gentler_effective_target() -> None:
    result = create_normalization_plan(
        measurement(-35.0, -10.0),
        NormalizationSettings(),
    )

    assert result.should_normalize is True
    assert result.effective_target_lufs == -23.0
    assert result.estimated_limiter_reduction_db == 3.0


def test_disabled_normalization_never_changes_audio() -> None:
    result = create_normalization_plan(
        measurement(-35.0, -20.0),
        NormalizationSettings(enabled=False),
    )

    assert result.should_normalize is False


def test_mp3_output_uses_maximum_standard_bitrate() -> None:
    assert MAXIMUM_MP3_BITRATE == "320k"


def test_mp3_output_disables_all_embedded_metadata() -> None:
    assert NO_MP3_METADATA_OPTIONS == (
        "-map_metadata",
        "-1",
        "-id3v2_version",
        "0",
        "-write_id3v1",
        "0",
    )
