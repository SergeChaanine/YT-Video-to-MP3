from pathlib import Path

import pytest

from yt_to_mp3.services import javascript
from yt_to_mp3.services.javascript import JavaScriptRuntimeError


def test_javascript_options_use_explicit_deno_path() -> None:
    runtime = Path("C:/Tools/deno.exe")

    assert javascript.javascript_options(runtime) == {
        "js_runtimes": {"deno": {"path": str(runtime)}},
        "no_color": True,
    }


def test_find_deno_runtime_accepts_configured_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "deno.exe"
    runtime.touch()
    monkeypatch.setenv("YT_TO_MP3_DENO_PATH", str(tmp_path))
    monkeypatch.setattr(javascript, "_read_deno_version", lambda path: (2, 8, 3))
    monkeypatch.setattr(javascript.shutil, "which", lambda name: None)

    assert javascript.find_deno_runtime() == runtime


def test_find_deno_runtime_rejects_old_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "deno.exe"
    runtime.touch()
    monkeypatch.setenv("YT_TO_MP3_DENO_PATH", str(runtime))
    monkeypatch.setattr(javascript, "_read_deno_version", lambda path: (2, 2, 9))
    monkeypatch.setattr(javascript.shutil, "which", lambda name: None)
    monkeypatch.setattr(javascript, "_application_root", lambda: tmp_path / "empty")

    with pytest.raises(JavaScriptRuntimeError, match="too old"):
        javascript.find_deno_runtime()
