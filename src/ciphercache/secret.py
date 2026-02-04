"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Defines `Secret` and `SecretEnvelope` to prevent accidental secret leakage.
- `Secret` redacts its string/repr output, while `reveal()` returns the raw value.
- `SecretEnvelope` wraps a mapping of secrets and provides `use()` helpers.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-04
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Secret:
    """Secret string wrapper with redacted string and repr output."""

    value: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Return a redacted string representation."""
        return "<*redacted*>" if self.value else ""

    def __repr__(self) -> str:  # pragma: no cover - trivial
        """Return a redacted repr representation."""
        return "<*redacted*>" if self.value else ""

    def reveal(self) -> str:
        """Return the underlying secret value."""
        return self.value

    def use(self, func: Callable[[str], T]) -> T:
        """Call a single-argument function with the revealed value."""
        return func(self.value)


class SecretEnvelope(dict[str, Secret]):
    """Dictionary of secrets with redacted display and helper usage methods."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Return a redacted string representation of the envelope."""
        return str({key: str(value) for key, value in self.items()})

    def __repr__(self) -> str:  # pragma: no cover - trivial
        """Return a redacted repr representation of the envelope."""
        return repr({key: str(value) for key, value in self.items()})

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "SecretEnvelope":
        """Convert a raw secret payload dict into a SecretEnvelope."""
        envelope = cls()
        for key, value in payload.items():
            if value is None:
                text = ""
            elif isinstance(value, str):
                text = value
            else:
                text = str(value)
            envelope[str(key)] = Secret(text)
        return envelope

    def use(self, keys: str | Iterable[str], func: Callable[..., T]) -> T:
        """Call a function with revealed secrets in the order of keys."""
        if isinstance(keys, str):
            key_list = [keys]
        else:
            key_list = list(keys)
        values = [self[key].reveal() for key in key_list]
        return func(*values)
