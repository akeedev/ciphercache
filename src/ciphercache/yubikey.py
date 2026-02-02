"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Optional YubiKey autodetect using `ykman list`.
- Exposes helpers to detect a single attached YubiKey or raise clear errors.

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
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class YubiKeyDetectResult:
    """Result of a YubiKey autodetect operation."""

    serials: list[str]


def is_ykman_available() -> bool:
    """Return True if ykman is available in PATH."""
    return _find_in_path("ykman") is not None


def detect_yubikey() -> str:
    """Detect a single YubiKey serial using ykman list."""
    ykman = _find_in_path("ykman")
    if ykman is None:
        raise RuntimeError("ykman is not available in PATH")
    result = _run_ykman_list(ykman)
    if not result.serials:
        raise RuntimeError("No YubiKey detected")
    if len(result.serials) > 1:
        serials = ", ".join(result.serials)
        raise RuntimeError(f"Multiple YubiKeys detected: {serials}")
    return result.serials[0]


def _run_ykman_list(ykman_path: Path) -> YubiKeyDetectResult:
    """Run ykman list and return parsed serials."""
    try:
        completed = subprocess.run(
            [str(ykman_path), "list"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("ykman list failed") from exc
    serials: list[str] = []
    for line in completed.stdout.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        match = re.search(r"\bSerial:\s*(\d+)\b", cleaned)
        if match:
            serials.append(match.group(1))
            continue
        if cleaned.isdigit():
            serials.append(cleaned)
    return YubiKeyDetectResult(serials=serials)


def _find_in_path(executable: str) -> Path | None:
    """Find an executable in PATH."""
    path_env = os.environ.get("PATH", "")
    for folder in path_env.split(os.pathsep):
        if not folder:
            continue
        candidate = Path(folder) / executable
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None
