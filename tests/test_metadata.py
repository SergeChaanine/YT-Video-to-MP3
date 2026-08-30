from yt_to_mp3.services.metadata import metadata_from_info


def test_structured_music_metadata_has_priority() -> None:
    result = metadata_from_info(
        {
            "id": "abc123",
            "webpage_url": "https://www.youtube.com/watch?v=abc123",
            "artist": "Charles Aznavour",
            "track": "Hier encore",
            "title": "A title that should not win",
            "duration": 133.5,
        },
        "https://youtu.be/abc123",
    )

    assert result.artist == "Charles Aznavour"
    assert result.title == "Hier encore"
    assert result.needs_review is False


def test_conventional_video_title_is_parsed() -> None:
    result = metadata_from_info(
        {
            "id": "abc123",
            "title": "Charles Aznavour - Hier encore (Official Video)",
            "uploader": "Some channel",
        },
        "https://youtu.be/abc123",
    )

    assert result.artist == "Charles Aznavour"
    assert result.title == "Hier encore"
    assert result.needs_review is False


def test_ambiguous_title_uses_clean_uploader_and_requests_review() -> None:
    result = metadata_from_info(
        {
            "id": "abc123",
            "title": "Hier encore",
            "uploader": "Charles Aznavour - Topic",
        },
        "https://youtu.be/abc123",
    )

    assert result.artist == "Charles Aznavour"
    assert result.title == "Hier encore"
    assert result.needs_review is True
