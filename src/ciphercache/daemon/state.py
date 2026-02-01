"""SPDX-License-Identifier: Apache-2.0
Daemon state and configuration for ciphercache.
"""

from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ciphercache.store.keepassxc import KeePassXCConfig


@dataclass(slots=True)
class DaemonConfig:
    """Configuration for the daemon runtime."""

    data_dir: Path
    store_alias_default: str = "default"
    socket_path: Path | None = None
    expected_uid: int | None = None
    expected_gid: int | None = None
    max_frame_bytes: int = 1_000_000
    read_timeout_seconds: float = 5.0
    write_timeout_seconds: float = 5.0
    write_agent_metadata: bool = True
    store_config: Optional[KeePassXCConfig] = None
    unlock_all_ttl: int | None = None

    def __post_init__(self) -> None:
        """Populate derived defaults for socket and expected credentials."""
        if self.socket_path is None:
            self.socket_path = self.data_dir / "ciphercached.sock"
        if self.expected_uid is None:
            self.expected_uid = os.getuid()
        if self.expected_gid is None:
            self.expected_gid = os.getgid()


@dataclass(slots=True)
class DaemonState:
    """In-memory daemon state for IPC operations and test scaffolding.

    Fields:
        config: Runtime configuration for file locations and defaults.
        locked: Whether the daemon is locked (no secrets available).
        ttl_expiry: Monotonic timestamp for TTL expiry, or None for infinity.
        active_store_alias: Alias of the currently active store (MVP single store).
        secrets: In-memory secrets by store alias and secret name.
        allowed_secrets: Secret names allowed for this unlock session.
        tickets: Active ticket tokens for authorization.
    """

    config: DaemonConfig
    locked: bool = True  # Locked state blocks secret access.
    ttl_expiry: float | None = None  # Monotonic expiry timestamp; None for infinity.
    active_store_alias: str | None = None  # Active store alias for the session.
    secrets: dict[str, dict[str, dict[str, object]]] = field(default_factory=dict)  # Store -> name -> secret.
    allowed_secrets: set[str] = field(default_factory=set)  # Allowed secret names for this unlock.
    tickets: set[str] = field(default_factory=set)  # Active ticket tokens.

    def unlock(
        self,
        ttl_seconds: int | None,
        secrets: list[str],
        store_alias: str | None = None,
    ) -> None:
        """Unlock the daemon and set the active store, TTL, and allowed secrets."""
        self.locked = False
        self.active_store_alias = store_alias or self.config.store_alias_default
        self.allowed_secrets = set(secrets)
        self.secrets.clear()
        if ttl_seconds is None:
            self.ttl_expiry = None
        else:
            self.ttl_expiry = time.monotonic() + ttl_seconds

    def lock(self) -> None:
        """Lock the daemon and wipe cached secrets."""
        self.locked = True
        self.ttl_expiry = None
        self.secrets.clear()
        self.allowed_secrets.clear()
        self.tickets.clear()

    def close_store(self) -> None:
        """Close the active store, wiping cached secrets but preserving tickets."""
        self.locked = True
        self.ttl_expiry = None
        self.active_store_alias = None
        self.secrets.clear()
        self.allowed_secrets.clear()

    def expire_if_needed(self) -> None:
        """Expire the session if TTL has passed."""
        if self.locked or self.ttl_expiry is None:
            return
        if time.monotonic() >= self.ttl_expiry:
            self.lock()

    def ttl_remaining_seconds(self) -> int:
        """Return remaining TTL seconds (0 if locked; large value for infinity)."""
        self.expire_if_needed()
        if self.locked:
            return 0
        if self.ttl_expiry is None:
            return 2**31 - 1
        remaining = int(self.ttl_expiry - time.monotonic())
        return max(0, remaining)

    def issue_ticket(self, client_name: str) -> Path:
        """Create a new ticket for a client and return its file path."""
        token = secrets.token_urlsafe(32)
        tickets_dir = self.config.data_dir / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = tickets_dir / f"{client_name}.ticket"

        fd = os.open(ticket_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token)

        self.tickets.add(token)
        return ticket_path

    def validate_ticket(self, token: str) -> bool:
        """Validate a ticket token against the active set."""
        self.expire_if_needed()
        if self.locked:
            return False
        return token in self.tickets

    def get_secret(self, store_alias: str, secret_name: str) -> dict[str, object] | None:
        """Return a cached secret dict for a store alias and name."""
        if secret_name not in self.allowed_secrets:
            return None
        return self.secrets.get(store_alias, {}).get(secret_name)
