from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MINIMUM_DENO_VERSION = (2, 3, 0)
DENO_VERSION_PATTERN = re.compile(r"^deno\s+(\d+)\.(\d+)\.(\d+)", re.MULTILINE)


class JavaScriptRuntimeError(RuntimeError):
    pass


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[3]


def _configured_deno_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_dir():
        return path / ("deno.exe" if os.name == "nt" else "deno")
    return path


def _deno_candidates() -> list[Path]:
    executable_name = "deno.exe" if os.name == "nt" else "deno"
    candidates: list[Path] = []
    configured_path = os.environ.get("YT_TO_MP3_DENO_PATH")
    if configured_path:
        candidates.append(_configured_deno_path(configured_path))

    root = _application_root()
    candidates.extend(
        (
            root / "deno" / executable_name,
            root / "vendor" / "deno" / executable_name,
            root / executable_name,
        )
    )
    discovered = shutil.which(executable_name)
    if discovered:
        candidates.append(Path(discovered))
    return list(dict.fromkeys(candidates))


def _read_deno_version(path: Path) -> tuple[int, int, int]:
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=_creation_flags(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise JavaScriptRuntimeError(f"{path.name} could not start: {error}") from error

    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    match = DENO_VERSION_PATTERN.search(output)
    if result.returncode != 0 or not match:
        raise JavaScriptRuntimeError(f"{path.name} is not a usable Deno runtime.")
    return tuple(int(value) for value in match.groups())


def find_deno_runtime() -> Path:
    unusable: list[str] = []
    for candidate in _deno_candidates():
        if not candidate.is_file():
            continue
        try:
            version = _read_deno_version(candidate)
        except JavaScriptRuntimeError as error:
            unusable.append(str(error))
            continue
        if version >= MINIMUM_DENO_VERSION:
            return candidate
        unusable.append(
            f"{candidate.name} {'.'.join(str(value) for value in version)} is too old; "
            "version 2.3.0 or newer is required."
        )

    details = f" ({unusable[-1]})" if unusable else ""
    raise JavaScriptRuntimeError(
        "Deno 2.3.0 or newer was not found. Install the latest application build, "
        "or set YT_TO_MP3_DENO_PATH to deno.exe for development."
        f"{details}"
    )


def verify_ejs_package() -> None:
    if importlib.util.find_spec("yt_dlp_ejs") is None:
        raise JavaScriptRuntimeError(
            "The YouTube JavaScript solver is missing. Reinstall the application, or run "
            'pip install -U "yt-dlp[default]" for development.'
        )


def javascript_options(runtime: Path) -> dict[str, object]:
    return {
        "js_runtimes": {"deno": {"path": str(runtime)}},
        "no_color": True,
    }
