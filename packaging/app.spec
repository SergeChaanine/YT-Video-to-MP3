# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).resolve().parent
src = root / "src"
ffmpeg_directory = Path(
    os.environ.get("YT_TO_MP3_FFMPEG_DIR", root / "vendor" / "ffmpeg")
)
ffmpeg = ffmpeg_directory / "ffmpeg.exe"
ffprobe = ffmpeg_directory / "ffprobe.exe"

if not ffmpeg.is_file() or not ffprobe.is_file():
    raise SystemExit("ffmpeg.exe and ffprobe.exe must be present in vendor/ffmpeg before building.")

charset_normalizer_hiddenimports = collect_submodules("charset_normalizer")
chardet_hiddenimports = collect_submodules("chardet")

a = Analysis(
    [str(src / "yt_to_mp3" / "__main__.py")],
    pathex=[str(src)],
    binaries=[
        (str(ffmpeg), "ffmpeg"),
        (str(ffprobe), "ffmpeg"),
    ],
    datas=[
        (str(root / "assets"), "assets"),
    ],
    hiddenimports=[*charset_normalizer_hiddenimports, *chardet_hiddenimports],
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
