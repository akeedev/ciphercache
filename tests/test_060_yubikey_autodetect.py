"""Tests for spec 060: YubiKey autodetect via ykman."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from ciphercache.yubikey import (
    YubiKeyDetectResult,
    _find_in_path,
    _run_ykman_list,
    detect_yubikey,
    is_ykman_available,
)


def _make_executable(path: Path) -> None:
    """Create a dummy executable file."""
    path.write_text("", encoding="utf-8")
    path.chmod(0o755)


def test_is_ykman_available_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return True when ykman exists in PATH."""
    _make_executable(tmp_path / "ykman")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert is_ykman_available() is True


def test_is_ykman_available_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return False when ykman is not in PATH."""
    monkeypatch.setenv("PATH", "")
    assert is_ykman_available() is False


def test_detect_yubikey_raises_when_ykman_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """detect_yubikey raises RuntimeError when ykman is not found."""
    monkeypatch.setenv("PATH", "")
    with pytest.raises(RuntimeError, match="ykman is not available"):
        detect_yubikey()


def test_detect_yubikey_raises_when_no_device(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """detect_yubikey raises RuntimeError when no YubiKey is connected."""
    _make_executable(tmp_path / "ykman")
    monkeypatch.setenv("PATH", str(tmp_path))

    with patch("ciphercache.yubikey._run_ykman_list", return_value=YubiKeyDetectResult(serials=[])):
        with pytest.raises(RuntimeError, match="No YubiKey detected"):
            detect_yubikey()


def test_detect_yubikey_raises_when_multiple_devices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """detect_yubikey raises RuntimeError listing serials when multiple devices found."""
    _make_executable(tmp_path / "ykman")
    monkeypatch.setenv("PATH", str(tmp_path))

    with patch("ciphercache.yubikey._run_ykman_list", return_value=YubiKeyDetectResult(serials=["111", "222"])):
        with pytest.raises(RuntimeError, match="Multiple YubiKeys detected"):
            detect_yubikey()


def test_detect_yubikey_returns_serial_for_single_device(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """detect_yubikey returns the serial when exactly one device is found."""
    _make_executable(tmp_path / "ykman")
    monkeypatch.setenv("PATH", str(tmp_path))

    with patch("ciphercache.yubikey._run_ykman_list", return_value=YubiKeyDetectResult(serials=["12345678"])):
        assert detect_yubikey() == "12345678"


def test_run_ykman_list_parses_serial_colon_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parse ykman list output with 'Serial: <id>' format."""
    from ciphercache import yubikey

    class _Result:
        stdout = "YubiKey 5C Nano (5.4.3) [OTP+FIDO+CCID] Serial: 12345678\n"

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result()

    monkeypatch.setattr(yubikey.subprocess, "run", _fake_run)
    result = _run_ykman_list(Path("/usr/local/bin/ykman"))
    assert result.serials == ["12345678"]


def test_run_ykman_list_parses_plain_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parse ykman list output that is a plain numeric serial per line."""
    from ciphercache import yubikey

    class _Result:
        stdout = "12345678\n87654321\n"

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result()

    monkeypatch.setattr(yubikey.subprocess, "run", _fake_run)
    result = _run_ykman_list(Path("/usr/local/bin/ykman"))
    assert result.serials == ["12345678", "87654321"]


def test_run_ykman_list_ignores_blank_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank lines in ykman output are ignored."""
    from ciphercache import yubikey

    class _Result:
        stdout = "\n\n12345678\n\n"

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result()

    monkeypatch.setattr(yubikey.subprocess, "run", _fake_run)
    result = _run_ykman_list(Path("/usr/local/bin/ykman"))
    assert result.serials == ["12345678"]


def test_run_ykman_list_raises_on_cli_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """RuntimeError is raised when ykman list exits non-zero."""
    from ciphercache import yubikey

    def _fake_run(*_args: object, **_kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, "ykman list")

    monkeypatch.setattr(yubikey.subprocess, "run", _fake_run)
    with pytest.raises(RuntimeError, match="ykman list failed"):
        _run_ykman_list(Path("/usr/local/bin/ykman"))


def test_find_in_path_returns_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_find_in_path returns executable path when found."""
    exe = tmp_path / "mytool"
    _make_executable(exe)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert _find_in_path("mytool") == exe


def test_find_in_path_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """_find_in_path returns None when executable is not found."""
    monkeypatch.setenv("PATH", "")
    assert _find_in_path("nonexistent") is None


def test_find_in_path_skips_non_executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_find_in_path skips files that exist but are not executable."""
    non_exe = tmp_path / "mytool"
    non_exe.write_text("", encoding="utf-8")
    non_exe.chmod(0o644)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert _find_in_path("mytool") is None
