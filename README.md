# YouTube to MP3 Converter

A Windows app that downloads the best available YouTube audio and converts it to a 320 kbps MP3. Quiet tracks can be normalized automatically.

## Install and use

[Download the Windows installer](https://github.com/SergeChaanine/YT-Video-to-MP3/releases/download/v2.0.2/YT-to-MP3-Converter-Setup-2.0.2.exe)

1. Run the installer. If Windows SmartScreen appears, select **More info** and then **Run anyway**.
2. Open **YT to MP3 Converter**.
3. Paste one or more YouTube links.
4. Choose the save folder and volume setting.
5. Review the detected filename, then select **Download**.

Files are saved as `Singer - Music name.mp3` with no cover picture or artist/song metadata. The installer includes all required tools.

## Run from source

Requires Python 3.11+, FFmpeg, FFprobe, and Deno.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m yt_to_mp3
```

Only download content you have permission to use.
