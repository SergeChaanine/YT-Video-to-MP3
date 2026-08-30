from pathlib import Path

from yt_to_mp3.services.filenames import (
    available_output_path,
    build_filename,
    clean_artist,
    clean_song_title,
    split_video_title,
)


def test_build_filename_preserves_required_format_and_accents() -> None:
    assert build_filename("Charles Aznavour", "Hier encore") == (
        "Charles Aznavour - Hier encore.mp3"
    )
    assert build_filename("Céline Dion", "Pour que tu m'aimes encore") == (
        "Céline Dion - Pour que tu m'aimes encore.mp3"
    )


def test_title_parser_removes_only_known_video_decoration() -> None:
    assert split_video_title("Charles Aznavour - Hier encore (Official Audio)") == (
        "Charles Aznavour",
        "Hier encore",
    )
    assert clean_song_title("Song (Live in Paris)") == "Song (Live in Paris)"


def test_artist_cleanup_handles_topic_and_vevo_channels() -> None:
    assert clean_artist("Charles Aznavour - Topic") == "Charles Aznavour"
    assert clean_artist("ArtistVEVO") == "Artist"


def test_invalid_windows_filename_characters_are_replaced() -> None:
    assert build_filename("AC/DC", 'Song: "Live"') == "AC-DC - Song- -Live.mp3"


def test_available_output_path_adds_number_without_changing_format(tmp_path: Path) -> None:
    existing = tmp_path / "Artist - Song.mp3"
    existing.touch()

    assert available_output_path(tmp_path, existing.name).name == "Artist - Song (2).mp3"


def test_filename_length_is_bounded() -> None:
    result = build_filename("A" * 300, "T" * 300)

    assert len(result) <= 180
    assert " - " in result
    assert result.endswith(".mp3")
