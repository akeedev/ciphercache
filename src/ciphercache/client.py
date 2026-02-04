"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Implements the Python client SDK for ciphercache.
- Primary classes: `ClientConfig` (connection configuration) and `Client` (SDK API).
- Supporting dataclass: `Status` for typed status responses.
- Request flow: build IPC envelope, encode frame, open Unix socket, send, read response,
  decode, map errors to exceptions, return typed results.
- Discovery: uses `agent.json` if present, otherwise a fixed socket path under data_dir.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ciphercache.ipc.framing import decode_single_frame, encode_message
from ciphercache.secret import SecretEnvelope

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Status:
    """Typed status response returned by the daemon."""

    locked: bool
    ttl_remaining_seconds: int


@dataclass(slots=True)
class ClientConfig:
    """Configuration for the client SDK."""

    data_dir: Path = field(default_factory=lambda: _default_data_dir())
    socket_path: Path | None = None
    ticket_path: Path | None = None
    client_name: str = "default"
    max_frame_bytes: int = 1_000_000
    read_timeout_seconds: float = 5.0
    write_timeout_seconds: float = 5.0
    retries: int = 3
    retry_backoff_seconds: float = 0.1

    def __post_init__(self) -> None:
        """Populate derived defaults for socket and ticket paths."""
        if self.socket_path is None:
            self.socket_path = self.data_dir / "ciphercached.sock"
        if self.ticket_path is None:
            self.ticket_path = self.data_dir / "tickets" / f"{self.client_name}.ticket"


@dataclass(slots=True)
class Client:
    """Client SDK for communicating with ciphercached."""

    config: ClientConfig
    _ticket: str | None = None

    def __post_init__(self) -> None:
        """Eagerly load the ticket if the file already exists."""
        path = self.config.ticket_path
        if path is not None and path.exists():
            self.load_ticket()

    def load_ticket(self) -> str:
        """Load the ticket token from disk."""
        path = self.config.ticket_path
        if path is None:
            raise ValueError("ticket_path is required")
        try:
            token = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise OSError(f"Failed to read ticket file: {path}") from exc
        if not token:
            raise ValueError("Ticket file is empty")
        self._ticket = token
        return token

    def ping(self) -> bool:
        """Return True if the daemon responds to ping."""
        payload: dict[str, Any] = {}
        response = self.request("ping", payload)
        return bool(response.get("ok"))

    def status(self) -> Status:
        """Return typed status from the daemon."""
        payload: dict[str, Any] = {}
        response = self.request("status", payload)
        locked = bool(response.get("locked"))
        ttl_value = response.get("ttl_remaining_seconds")
        if not isinstance(ttl_value, int):
            raise ValueError("Invalid ttl_remaining_seconds in response")
        ttl_remaining = ttl_value
        return Status(locked=locked, ttl_remaining_seconds=ttl_remaining)

    def shutdown(self) -> bool:
        """Request daemon shutdown and secret cache wipe."""
        response = self.request("shutdown", {})
        return bool(response.get("ok"))

    def client_init(self, client_name: str) -> Path:
        """Request a new client ticket from the daemon."""
        payload: dict[str, Any] = {"client_name": client_name}
        response = self.request("client_init", payload)
        ticket_path = response.get("ticket_path")
        if not isinstance(ticket_path, str) or not ticket_path:
            raise ValueError("Missing ticket_path in response")
        return Path(ticket_path)

    def get_secret(self, name: str) -> SecretEnvelope:
        """Fetch a secret by name from the daemon as a SecretEnvelope."""
        payload = self._build_get_secret_payload(name)
        try:
            response = self.request("get_secret", payload)
        except PermissionError:
            ticket = self._refresh_ticket()
            payload = {"ticket": ticket, "secret_name": name}
            response = self.request("get_secret", payload)
        secret = response.get("secret")
        if not isinstance(secret, dict):
            raise ValueError("Missing secret in response")
        return SecretEnvelope.from_payload(secret)

    def _ensure_ticket(self) -> str:
        """Ensure a client ticket exists, auto-initializing if needed."""
        path = self.config.ticket_path
        if path is not None and path.exists():
            return self.load_ticket()
        ticket_path = self.client_init(self.config.client_name)
        self.config.ticket_path = ticket_path
        return self.load_ticket()

    def _build_get_secret_payload(self, name: str) -> dict[str, Any]:
        """Build the get_secret payload with a valid ticket."""
        ticket = self._ticket or self._ensure_ticket()
        payload: dict[str, Any] = {"ticket": ticket, "secret_name": name}
        return payload

    def _refresh_ticket(self) -> str:
        """Re-initialize a ticket after an unauthorized response."""
        self._ticket = None
        ticket_path = self.client_init(self.config.client_name)
        self.config.ticket_path = ticket_path
        return self.load_ticket()

    def request(
        self,
        op: str,
        payload: dict[str, Any],
        read_timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        """Send a request and return the response payload."""
        envelope = _request_envelope(op, payload)
        response = _send_with_retries(self.config, envelope, read_timeout_seconds=read_timeout_seconds)
        return _parse_response(response)


def _default_data_dir() -> Path:
    """Return the default data directory path."""
    return Path.home() / "Library" / "Application Support" / "ciphercache"


def _load_agent_socket_path(data_dir: Path) -> Path | None:
    """Read agent.json and return socket path if present."""
    agent_path = data_dir / "agent.json"
    if not agent_path.exists():
        return None
    try:
        payload = json.loads(agent_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _LOGGER.debug("Failed to read agent.json at %s: %s", agent_path, exc)
        return None
    socket_path = payload.get("socket_path")
    if not isinstance(socket_path, str) or not socket_path:
        return None
    return Path(socket_path)


def _request_envelope(op: str, payload: dict[str, Any]) -> dict[str, object]:
    """Build an IPC request envelope."""
    # Millisecond-timestamp ID is sufficient for single-threaded, single-client use.
    # Collisions within the same ms are benign: the daemon processes one request per
    # connection and does not deduplicate by ID.
    return {
        "version": "v0",
        "id": f"req-{int(time.time() * 1000)}",
        "type": "request",
        "op": op,
        "payload": payload,
    }


def _send_with_retries(
    config: ClientConfig,
    envelope: dict[str, object],
    read_timeout_seconds: float | None = None,
) -> dict[str, object]:
    """Send a request envelope, retrying transient connection errors."""
    attempts = max(1, config.retries)
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return _send_once(config, envelope, read_timeout_seconds=read_timeout_seconds)
        except (FileNotFoundError, ConnectionRefusedError, ConnectionResetError, BrokenPipeError) as exc:
            last_exc = exc
            if attempt == attempts - 1:
                break
            time.sleep(config.retry_backoff_seconds)
    assert last_exc is not None
    raise last_exc


def _send_once(
    config: ClientConfig,
    envelope: dict[str, object],
    read_timeout_seconds: float | None = None,
) -> dict[str, object]:
    """Send a single request and return the decoded response envelope."""
    socket_path = config.socket_path
    if socket_path is None:
        raise ValueError("socket_path is required")
    agent_socket = _load_agent_socket_path(config.data_dir)
    if agent_socket is not None:
        socket_path = agent_socket

    frame = encode_message(envelope)
    if len(frame) > config.max_frame_bytes + 4:
        raise ValueError("Frame exceeds max_frame_bytes")

    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        conn.settimeout(config.read_timeout_seconds)
        conn.connect(str(socket_path))
        conn.settimeout(config.write_timeout_seconds)
        conn.sendall(frame)
        conn.settimeout(read_timeout_seconds or config.read_timeout_seconds)
        length_prefix = _recv_exact(conn, 4)
        if length_prefix is None:
            raise RuntimeError("No response from daemon")
        length = int.from_bytes(length_prefix, "big")
        if length > config.max_frame_bytes:
            raise ValueError("Response frame too large")
        payload = _recv_exact(conn, length)
        if payload is None:
            raise RuntimeError("Incomplete response from daemon")
        return decode_single_frame(length_prefix + payload)
    except OSError as exc:
        raise exc.__class__(f"Failed to communicate with daemon at {socket_path}") from exc
    finally:
        conn.close()


def _parse_response(envelope: dict[str, object]) -> dict[str, object]:
    """Validate a response envelope and return its payload or raise."""
    message_type = envelope.get("type")
    if message_type == "response":
        payload = envelope.get("payload")
        if isinstance(payload, dict):
            return payload
        raise ValueError("Invalid response payload")
    if message_type == "error":
        payload = envelope.get("payload")
        if isinstance(payload, dict):
            code = payload.get("code")
            message = payload.get("message", "Unknown error")
            _raise_error(code, message)
        raise RuntimeError("Unknown error")
    raise ValueError("Invalid response envelope")


def _raise_error(code: object, message: object) -> None:
    """Raise an exception matching a daemon error code."""
    text = str(message)
    if code == "invalid_request":
        raise ValueError(text)
    if code == "unauthorized":
        raise PermissionError(text)
    if code == "locked":
        raise RuntimeError(text)
    if code == "not_found":
        raise LookupError(text)
    if code == "internal_error":
        raise RuntimeError(text)
    raise RuntimeError(text)


def _recv_exact(conn: socket.socket, length: int) -> bytes | None:
    """Receive an exact number of bytes or return None on timeout/EOF."""
    if length <= 0:
        return None
    chunks: list[bytes] = []
    remaining = length
    while remaining > 0:
        try:
            chunk = conn.recv(remaining)
        except socket.timeout:
            return None
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
