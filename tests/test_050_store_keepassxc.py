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
    found = _find_keepassxc_cli([root])
    assert found == paths[1]
