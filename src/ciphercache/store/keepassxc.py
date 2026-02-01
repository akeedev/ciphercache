"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Implements KeePassXC store integration via keepassxc-cli export.
- Main types: `KeePassXCConfig`, `KeePassXCClient`, `KeePassXCParser`.
- Lifecycle: execute CLI export (single unlock), strip prompts, parse XML in memory,
  then return only requested secrets by entry title.
- No plaintext export is written to disk.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

import os
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ciphercache.yubikey import detect_yubikey

@dataclass(slots=True)
class KeePassXCConfig:
    """Configuration for KeePassXC CLI export."""

    database_path: Path
    key_file_path: Path | None = None
    yubikey_slot: str | None = None  # "auto" uses ykman autodetect
    no_password: bool = False
    keepassxc_cli_path: Path | None = None
    keepassxc_cli_search_roots: list[Path] = field(default_factory=lambda: [Path("/Applications")])


@dataclass(slots=True)
class KeePassXCClient:
    """Client wrapper around keepassxc-cli export."""

    config: KeePassXCConfig

    def export_xml(self) -> str:
        """Run keepassxc-cli export and return XML output as a string."""
        cli_path = self.config.keepassxc_cli_path or _find_keepassxc_cli(self.config.keepassxc_cli_search_roots)
        if cli_path is None:
            raise FileNotFoundError("keepassxc-cli not found")
        args = [str(cli_path), "export", "--format", "xml"]
        if self.config.key_file_path is not None:
            args.extend(["--key-file", str(self.config.key_file_path)])
        if self.config.yubikey_slot is not None:
            slot = self.config.yubikey_slot
            if slot in {"auto", "autodetect"}:
                serial = detect_yubikey()
                slot = f"1:{serial}"
            args.extend(["--yubikey", slot])
        if self.config.no_password:
            args.append("--no-password")
        args.append(str(self.config.database_path))

        try:
            result = subprocess.run(
                args,
                check=True,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("keepassxc-cli export failed") from exc
        return result.stdout


@dataclass(slots=True)
class KeePassXCParser:
    """Parser for KeePassXC XML export output."""

    def parse(self, raw_output: str) -> dict[str, dict[str, object]]:
        """Parse export output and return entries keyed by title."""
        xml_text = _strip_to_xml(raw_output)
        root = ET.fromstring(xml_text)
        entries: dict[str, dict[str, object]] = {}
        for entry in root.iter("Entry"):
            parsed = _parse_entry(entry)
            title = parsed.get("title")
            if isinstance(title, str) and title:
                entries[title] = parsed
        return entries


def load_secrets(config: KeePassXCConfig, names: Iterable[str]) -> dict[str, dict[str, object]]:
    """Load requested secrets by entry title."""
    requested = {name for name in names if name}
    if not requested:
        raise ValueError("At least one secret name is required")
    client = KeePassXCClient(config=config)
    parser = KeePassXCParser()
    entries = parser.parse(client.export_xml())
    return {name: entries[name] for name in requested if name in entries}


def load_all_secrets(config: KeePassXCConfig) -> dict[str, dict[str, object]]:
    """Load all secrets from the database."""
    client = KeePassXCClient(config=config)
    parser = KeePassXCParser()
    return parser.parse(client.export_xml())


def _strip_to_xml(raw_output: str) -> str:
    """Return substring starting at the first XML prolog."""
    index = raw_output.find("<?xml")
    if index == -1:
        raise ValueError("XML prolog not found in output")
    return raw_output[index:]


def _parse_entry(entry: ET.Element) -> dict[str, object]:
    """Parse an <Entry> element into a secret dict."""
    data: dict[str, object] = {}
    strings = entry.findall("String")
    for item in strings:
        key = item.findtext("Key")
        value = item.findtext("Value") or ""
        if key == "Title":
            data["title"] = value
        elif key == "UserName":
            data["username"] = value
        elif key == "Password":
            data["password"] = value
        elif key == "URL":
            data["url"] = value
    tags_raw = entry.findtext("Tags") or ""
    tags = _split_tags(tags_raw)
    if tags:
        data["tags"] = tags
    return data


def _split_tags(text: str) -> list[str]:
    """Split KeePassXC tag strings on whitespace and commas."""
    if not text:
        return []
    parts = re.split(r"[\s,]+", text.strip())
    return [part for part in parts if part]


def _find_keepassxc_cli(search_roots: Iterable[Path]) -> Path | None:
    """Find keepassxc-cli in standard macOS app bundles."""
    path_cli = _find_keepassxc_in_path()
    if path_cli is not None:
        return path_cli
    candidates: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for app in root.glob("KeePassXC*.app"):
            cli_path = app / "Contents" / "MacOS" / "keepassxc-cli"
            if cli_path.exists():
                candidates.append(cli_path)
    if not candidates:
        return None
    return _prefer_highest_version(candidates)


def _find_keepassxc_in_path() -> Path | None:
    """Find keepassxc-cli in PATH."""
    path_env = os.environ.get("PATH", "")
    for folder in path_env.split(os.pathsep):
        if not folder:
            continue
        candidate = Path(folder) / "keepassxc-cli"
        if candidate.exists():
            return candidate
    return None


def _prefer_highest_version(paths: list[Path]) -> Path:
    """Pick the KeePassXC app path with the highest version suffix."""
    def version_key(path: Path) -> tuple[int, ...]:
        name = path.parts[-4]  # KeePassXC_X.Y.Z.app
        match = re.search(r"(\\d+\\.\\d+\\.\\d+)", name)
        if not match:
            return (0,)
        return tuple(int(part) for part in match.group(1).split("."))

    return sorted(paths, key=version_key, reverse=True)[0]
