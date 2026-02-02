"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- TTL parsing utilities for ciphercache.
- Converts human-readable duration strings (e.g. "1h 30m") to seconds.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

import re

_UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}

_TOKEN_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd])$")


def parse_ttl(value: str) -> int | None:
    """Parse a human-readable TTL into seconds.

    Returns None for infinity.

    Examples:
        >>> parse_ttl("5s")
        5
        >>> parse_ttl("1h 30m")
        5400
        >>> parse_ttl("infinity") is None
        True
    """
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("TTL is empty")
    if normalized == "infinity":
        return None

    total_seconds = 0
    for part in normalized.split():
        match = _TOKEN_RE.match(part)
        if not match:
            raise ValueError(f"Invalid TTL token: {part}")
        amount = int(match.group("value"))
        unit = match.group("unit")
        total_seconds += amount * _UNIT_SECONDS[unit]

    if total_seconds < 0:
        raise ValueError("TTL must be non-negative")

    return total_seconds
