from __future__ import annotations

from pathlib import Path

import pytest

from ciphercache.store.keepassxc import (
    KeePassXCClient,
    KeePassXCConfig,
    KeePassXCParser,
    _find_keepassxc_cli,
    _split_tags,
    _strip_to_xml,
    load_secrets,
)
from ciphercache.yubikey import detect_yubikey, is_ykman_available
from ciphercache.daemon.runner import _build_parser


def _demo_export_path() -> Path:
    """Return the demo export XML path."""
    return Path(__file__).resolve().parents[1] / "testdata" / "demopasswords.export.xml"


def test_strip_to_xml_ignores_prefix() -> None:
    """Parser should ignore prompts before XML prolog."""
    raw = "Passwort eingeben\\n<?xml version=\\\"1.0\\\"?><KeePassFile></KeePassFile>"
    xml = _strip_to_xml(raw)
    assert xml.startswith("<?xml")


def test_split_tags_whitespace_and_commas() -> None:
    """Tags should split on whitespace and commas."""
    tags = _split_tags("tag1 tag2,tag3  tag4")
    assert tags == ["tag1", "tag2", "tag3", "tag4"]


def test_parse_demo_export_entries() -> None:
    """Parse demo export and extract expected entries."""
    raw = _demo_export_path().read_text(encoding="utf-8")
    parser = KeePassXCParser()
    entries = parser.parse(raw)

    assert "demoentry1" in entries
    assert "demoentry2" in entries
    assert "Demokey in a group" in entries

    entry = entries["demoentry1"]
    assert entry["title"] == "demoentry1"
    assert entry["username"] == "demouser"
    assert entry["password"] == "demopassword"
    assert entry["url"] == "http://www.x.com"
    assert "tags" in entry


def test_parse_demo_export_tags_split() -> None:
    """Tags should split into a list."""
    raw = _demo_export_path().read_text(encoding="utf-8")
    parser = KeePassXCParser()
    entries = parser.parse(raw)
    tags = entries["Demokey in a group"]["tags"]
    assert isinstance(tags, list)
    assert "tag1" in tags
    assert "tag2" in tags


def test_load_secrets_filters_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_secrets should filter to requested titles."""
    raw = _demo_export_path().read_text(encoding="utf-8")

    def _fake_export(self: KeePassXCClient) -> str:
        return raw

    monkeypatch.setattr(KeePassXCClient, "export_xml", _fake_export)
    config = KeePassXCConfig(database_path=Path("demo.kdbx"))
    secrets = load_secrets(config, ["demoentry1", "missing"])
    assert "demoentry1" in secrets
    assert "missing" not in secrets


def test_find_keepassxc_cli_prefers_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer keepassxc-cli found in PATH."""
    cli_dir = tmp_path / "bin"
    cli_dir.mkdir(parents=True)
    cli_path = cli_dir / "keepassxc-cli"
    cli_path.write_text("", encoding="utf-8")
    cli_path.chmod(0o755)
    monkeypatch.setenv("PATH", str(cli_dir))
    found = _find_keepassxc_cli([])
    assert found == cli_path


def test_find_keepassxc_cli_prefers_highest_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Choose the highest KeePassXC app version under search roots."""
    monkeypatch.setenv("PATH", "")
    root = tmp_path / "Applications"
    paths = [
        root / "KeePassXC_2.7.5.app" / "Contents" / "MacOS" / "keepassxc-cli",
        root / "KeePassXC_2.7.6.app" / "Contents" / "MacOS" / "keepassxc-cli",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        path.chmod(0o755)
    found = _find_keepassxc_cli([root])
    assert found == paths[1]


def test_ttl_arg_parses() -> None:
    """Runner should accept --ttl and parse it."""
    parser = _build_parser()
    args = parser.parse_args(["--ttl", "1h", "--db-path", "demo.kdbx"])
    assert args.ttl == "1h"


def test_ykman_available_false_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_ykman_available should return False when ykman is not in PATH."""
    monkeypatch.setenv("PATH", "")
    assert is_ykman_available() is False


def test_detect_yubikey_errors_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """detect_yubikey should error when ykman is missing."""
    monkeypatch.setenv("PATH", "")
    with pytest.raises(RuntimeError):
        detect_yubikey()


def test_run_ykman_list_parses_serial_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parse ykman list output that includes 'Serial: <id>'."""
    from ciphercache import yubikey

    class _Result:
        stdout = "YubiKey 5C Nano (5.4.3) [OTP+FIDO+CCID] Serial: 12345678\\n"

    def _fake_run(*_args: object, **_kwargs: object) -> _Result:
        return _Result()

    monkeypatch.setattr(yubikey.subprocess, "run", _fake_run)
    result = yubikey._run_ykman_list(Path("/usr/local/bin/ykman"))
    assert result.serials == ["12345678"]
