# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).resolve().parent
src = root / "src"
ffmpeg_directory = Path(
    os.environ.get("YT_TO_MP3_FFMPEG_DIR", root / "vendor" / "ffmpeg")
)
ffmpeg = ffmpeg_directory / "ffmpeg.exe"
ffprobe = ffmpeg_directory / "ffprobe.exe"
deno_value = os.environ.get("YT_TO_MP3_DENO_PATH")
deno = Path(deno_value) if deno_value else root / "vendor" / "deno" / "deno.exe"
if deno.is_dir():
    deno = deno / "deno.exe"

if not ffmpeg.is_file() or not ffprobe.is_file():
    raise SystemExit("ffmpeg.exe and ffprobe.exe must be present in vendor/ffmpeg before building.")
if not deno.is_file():
    raise SystemExit("deno.exe must be present in vendor/deno before building.")

charset_normalizer_hiddenimports = collect_submodules("charset_normalizer")
chardet_hiddenimports = collect_submodules("chardet")
ejs_datas, ejs_binaries, ejs_hiddenimports = collect_all("yt_dlp_ejs")

a = Analysis(
    [str(src / "yt_to_mp3" / "__main__.py")],
    pathex=[str(src)],
    binaries=[
        (str(ffmpeg), "ffmpeg"),
        (str(ffprobe), "ffmpeg"),
        (str(deno), "deno"),
        *ejs_binaries,
    ],
    datas=[
        (str(root / "assets"), "assets"),
        *ejs_datas,
    ],
    hiddenimports=[
        *charset_normalizer_hiddenimports,
        *chardet_hiddenimports,
        *ejs_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YT to MP3 Converter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "assets" / "app.ico"),
    version=str(root / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="YT to MP3 Converter",
)
