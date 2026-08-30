from yt_to_mp3.services.downloader import _clean_yt_dlp_error


def test_yt_dlp_error_removes_color_codes_and_prefix() -> None:
    message = "\x1b[0;31mERROR:\x1b[0m unable to download: HTTP Error 403: Forbidden"

    assert _clean_yt_dlp_error(message) == "unable to download: HTTP Error 403: Forbidden"
