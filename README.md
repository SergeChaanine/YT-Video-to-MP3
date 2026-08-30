# YouTube to MP3 Converter

A Windows desktop application that downloads the best available YouTube audio and creates a
maximum-quality MP3 named `Singer - Music name.mp3`.

## Highlights

- Downloads the best audio stream available through yt-dlp.
- Encodes once with LAME at 320 kbps, the maximum standard MP3 bitrate.
- Measures loudness before encoding and raises only quiet tracks.
- Uses a balanced −16 LUFS target, a −1 dBTP peak ceiling, and a limit on compression.
- Detects artist and song naming and lets you correct the filename before downloading.
- Leaves embedded MP3 metadata empty and does not download or embed cover artwork.
- Supports multiple URLs, YouTube Music, Shorts, optional playlists, and clipboard detection.
- Provides live progress, cancellation, retries, light/dark themes, and remembered settings.

Use the application only for content you have permission to download and in accordance with the
applicable platform terms and local laws.

## Download and install

[Download YT to MP3 Converter 2.0.2 for Windows](https://github.com/SergeChaanine/YT-Video-to-MP3/releases/download/v2.0.2/YT-to-MP3-Converter-Setup-2.0.2.exe)

1. Download `YT-to-MP3-Converter-Setup-2.0.2.exe`.
2. Open the installer and follow the setup wizard.
3. If Windows SmartScreen appears, select **More info**, verify that the file came from this
   repository, and then select **Run anyway**.

The Windows installer includes the application, FFmpeg, FFprobe, Deno, and the YouTube JavaScript
solver. Python and the supporting tools do not need to be installed separately. The installer is
currently unsigned, so Windows may display the SmartScreen notice.

Published installer SHA-256:

```text
122A93DEF535D96AE9DE9C17EF4FD15A12582F0D1FA80DB4234C6DE40712CFEC
```

You can verify it from PowerShell after downloading:

```powershell
Get-FileHash .\YT-to-MP3-Converter-Setup-2.0.2.exe -Algorithm SHA256
```

## Run from source

### Requirements

- Python 3.11 or newer
- FFmpeg and FFprobe with `libmp3lame`
- Deno 2.3 or newer for YouTube's JavaScript challenges

The application finds FFmpeg in this order:

1. The directory specified by `YT_TO_MP3_FFMPEG_DIR`
2. The bundled `ffmpeg` directory
3. `vendor/ffmpeg` in a development checkout
4. The system `PATH`

Set `YT_TO_MP3_DENO_PATH` to a Deno executable or its directory during development. Release builds
bundle Deno and the matching `yt-dlp-ejs` solver, so users do not need to install either tool.

Install the Python project and development tools:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"
```

Run the application:

```powershell
.venv\Scripts\python -m yt_to_mp3
```

Run the tests and lint checks:

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
```

## Volume normalization

Balanced mode measures every source but changes it only when integrated loudness is below
−20 LUFS. Quiet audio is normalized toward −16 LUFS with a −1 dBTP true-peak ceiling. When the
requested target would require excessive peak limiting, the app automatically uses a gentler
target. Gentle mode targets −18 LUFS with an even lower compression allowance.

The original downloaded source is analyzed before the final 320 kbps MP3 is encoded, so
normalization does not introduce an additional MP3-to-MP3 conversion. A high output bitrate cannot
restore information absent from YouTube's source, but it minimizes additional MP3 encoding loss.

## Filename resolution

The application prioritizes structured artist and track metadata. If those fields are unavailable,
it parses conventional `Artist - Song` video titles and then falls back to the uploader and video
title. Ambiguous results are marked for review and can be edited by double-clicking the queue row.

Windows-invalid filename characters are replaced, while Unicode letters and accents are retained.

## Building the Windows application

Place redistributable `ffmpeg.exe` and `ffprobe.exe` files in `vendor/ffmpeg` and `deno.exe` in
`vendor/deno`, or pass their locations to the build script:

```powershell
.\scripts\build.ps1 `
    -FfmpegDirectory C:\path\to\ffmpeg\bin `
    -DenoPath C:\path\to\deno.exe
```

The script runs tests and lint checks, creates a PyInstaller one-folder application, and uses Inno
Setup when `ISCC.exe` is installed. Generated output is written under `dist` and remains ignored by
Git.
