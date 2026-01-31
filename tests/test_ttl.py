from __future__ import annotations

import pytest

from ciphercache.ttl import parse_ttl


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0s", 0),
        ("5s", 5),
        ("1m", 60),
        ("2h", 7200),
        ("3d", 259200),
        ("1h 30m", 5400),
        ("10m 5s", 605),
    ],
)
def test_parse_ttl_valid(value: str, expected: int) -> None:
    assert parse_ttl(value) == expected


def test_parse_ttl_infinity() -> None:
    assert parse_ttl("infinity") is None


def test_parse_ttl_strips_whitespace() -> None:
    assert parse_ttl("  5s  ") == 5


@pytest.mark.parametrize("value", ["", " ", "1", "1w", "1h30m", "-1s", "foo"])
def test_parse_ttl_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        parse_ttl(value)
