from yt_to_mp3.ui.main_window import canonical_url_key, extract_youtube_urls, format_duration


def test_extract_urls_supports_standard_short_and_music_links() -> None:
    text = """
    https://www.youtube.com/watch?v=alpha
    https://youtu.be/beta?t=10
    https://music.youtube.com/watch?v=gamma&list=RDAMVMgamma
    """

    assert extract_youtube_urls(text) == [
        "https://www.youtube.com/watch?v=alpha",
        "https://youtu.be/beta?t=10",
        "https://music.youtube.com/watch?v=gamma&list=RDAMVMgamma",
    ]


def test_canonical_key_deduplicates_equivalent_video_urls() -> None:
    assert canonical_url_key("https://youtu.be/abc123?t=5") == "video:abc123"
    assert canonical_url_key("https://www.youtube.com/watch?v=abc123&list=example") == (
        "video:abc123"
    )


def test_duration_formatting() -> None:
    assert format_duration(133.5) == "2:13"
    assert format_duration(3_661) == "1:01:01"
    assert format_duration(None) == "—"
