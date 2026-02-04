"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- Implements a blocking Unix domain socket server for ciphercached.
- Primary class: `UnixSocketServer`, which owns the listener socket and daemon lifecycle.
- Lifecycle flow: `setup()` prepares directories, writes agent.json, binds/listens; `serve_forever()`
  accepts connections; `_handle_connection()` reads a single framed request and writes one response;
  `close()` tears down the socket, metadata, and locks state.
- Frame handling is delegated to `ciphercache.ipc.framing` and `ciphercache.ipc.handler`.
- Security controls include socket permissions, peer UID/GID checks, max-frame enforcement,
  and read/write timeouts.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ciphercache.daemon.state import DaemonConfig, DaemonState
from ciphercache.ipc.framing import decode_single_frame, encode_message
from ciphercache.ipc.handler import ERROR_INVALID_REQUEST, ERROR_UNAUTHORIZED, handle_request


# Linux SO_PEERCRED for getsockopt - for compatibility; macOS uses getpeereid instead.
_SO_PEERCRED = 0x11
_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class UnixSocketServer:
    """Blocking Unix domain socket server for ciphercached."""

    config: DaemonConfig
    state: DaemonState
    listener: socket.socket | None = None
    agent_metadata_path: Path | None = None
    _running: bool = False

    def setup(self) -> None:
        """Prepare the data directory, write metadata, and bind the socket."""
        _LOGGER.info("Daemon setup started")
        data_dir = self.config.data_dir
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(data_dir, 0o700)
        except OSError as exc:
            raise OSError(f"Failed to prepare data directory: {data_dir}") from exc

        socket_path = self.config.socket_path
        if socket_path is None:
            raise ValueError("socket_path is required")
        try:
            socket_path.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(socket_path.parent, 0o700)
            if socket_path.exists():
                socket_path.unlink()
        except OSError as exc:
            raise OSError(f"Failed to prepare socket directory: {socket_path.parent}") from exc

        if self.config.write_agent_metadata:
            self.agent_metadata_path = data_dir / "agent.json"
            try:
                _write_agent_metadata(self.agent_metadata_path, socket_path, data_dir)
            except OSError as exc:
                raise OSError(f"Failed to write agent metadata: {self.agent_metadata_path}") from exc

        try:
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(socket_path))
            os.chmod(socket_path, 0o600)
            listener.listen()
            self.listener = listener
        except OSError as exc:
            raise OSError(f"Failed to bind Unix socket: {socket_path}") from exc
        _LOGGER.info("Daemon listening on %s", socket_path)

    def serve_forever(self) -> None:
        """Accept and handle connections until interrupted."""
        if self.listener is None:
            self.setup()
        assert self.listener is not None
        self._running = True
        previous_handlers = _install_signal_handlers(self._handle_signal)
        try:
            while self._running:
                try:
                    conn, _ = self.listener.accept()
                except OSError:
                    if not self._running:
                        break
                    raise
                _LOGGER.info("Accepted connection")
                try:
                    self._handle_connection(conn)
                finally:
                    conn.close()
        except KeyboardInterrupt:
            pass
        finally:
            _restore_signal_handlers(previous_handlers)
            self.close()

    def close(self) -> None:
        """Close the listener and remove socket and metadata files."""
        _LOGGER.info("Daemon shutdown started")
        self._running = False
        if self.listener is not None:
            self.listener.close()
            self.listener = None
        socket_path = self.config.socket_path
        if socket_path and socket_path.exists():
            socket_path.unlink()
        if self.agent_metadata_path and self.agent_metadata_path.exists():
            self.agent_metadata_path.unlink()
        self.agent_metadata_path = None
        self.state.lock()
        _LOGGER.info("Daemon shutdown complete")

    def _handle_connection(self, conn: socket.socket) -> None:
        """Validate peer credentials, read a frame, and respond."""
        try:
            _validate_peer(
                conn,
                self.config.expected_uid,
                self.config.expected_gid,
                self.config.require_peer_credentials,
            )
        except PermissionError as exc:
            error = _error_envelope(ERROR_UNAUTHORIZED, str(exc))
            conn.settimeout(self.config.write_timeout_seconds)
            _safe_send(conn, encode_message(error))
            return

        conn.settimeout(self.config.read_timeout_seconds)
        length_prefix = _recv_exact(conn, 4)
        if length_prefix is None:
            return
        length = int.from_bytes(length_prefix, "big")
        if length > self.config.max_frame_bytes:
            error = _error_envelope(ERROR_INVALID_REQUEST, "Frame too large")
            conn.settimeout(self.config.write_timeout_seconds)
            _safe_send(conn, encode_message(error))
            return
        payload = _recv_exact(conn, length)
        if payload is None:
            return
        frame = length_prefix + payload

        try:
            message = decode_single_frame(frame)
            _LOGGER.info("Request %s", _summarize_request(message))
            response = handle_request(self.state, message)
        except Exception as exc:
            response = _error_envelope(ERROR_INVALID_REQUEST, f"Invalid frame: {exc}")

        conn.settimeout(self.config.write_timeout_seconds)
        _safe_send(conn, encode_message(response))
        if self.state.shutdown_requested:
            self._running = False
            if self.listener is not None:
                self.listener.close()

    def _handle_signal(self, signum: int, _frame: object | None) -> None:
        """Stop the accept loop and close the listener on signals."""
        _ = signum
        _LOGGER.info("Signal received, stopping daemon")
        self._running = False
        if self.listener is not None:
            self.listener.close()


def _error_envelope(code: str, message: str) -> dict[str, Any]:
    """Build a minimal error response envelope."""
    return {
        "version": "v0",
        "id": "unknown",
        "type": "error",
        "op": "unknown",
        "payload": {
            "code": code,
            "message": message,
        },
    }


def _safe_send(conn: socket.socket, payload: bytes) -> None:
    """Send a response, swallowing broken pipe/connection reset errors."""
    try:
        conn.sendall(payload)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
        _LOGGER.info("Client disconnected before response was sent")


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


def _validate_peer(
    conn: socket.socket,
    expected_uid: int | None,
    expected_gid: int | None,
    require_peer_credentials: bool,
) -> bool:
    """Validate the peer credentials against expected UID/GID."""
    uid, gid = _get_peer_credentials(conn)
    if expected_uid is not None and uid is None:
        if require_peer_credentials:
            raise PermissionError("Peer UID unavailable")
        _LOGGER.debug("Peer UID unavailable; skipping UID/GID validation")
        return True
    if expected_gid is not None and gid is None:
        if require_peer_credentials:
            raise PermissionError("Peer GID unavailable")
        _LOGGER.debug("Peer GID unavailable; skipping UID/GID validation")
        return True
    if expected_uid is not None and uid != expected_uid:
        raise PermissionError("Peer UID mismatch")
    if expected_gid is not None and gid != expected_gid:
        raise PermissionError("Peer GID mismatch")
    return True


def _get_peer_credentials(conn: socket.socket) -> tuple[int | None, int | None]:
    """Return the peer UID/GID if available, otherwise (None, None)."""
    if hasattr(socket, "getpeereid"):
        try:
            uid, gid = socket.getpeereid(conn)  # type: ignore[attr-defined]
            return uid, gid
        except OSError as exc:
            _LOGGER.debug("getpeereid failed: %s", exc)
            return None, None
    try:
        creds = conn.getsockopt(socket.SOL_SOCKET, _SO_PEERCRED, 12)
    except OSError as exc:
        _LOGGER.debug("SO_PEERCRED failed: %s", exc)
        return None, None
    pid = int.from_bytes(creds[0:4], "little")
    uid = int.from_bytes(creds[4:8], "little")
    gid = int.from_bytes(creds[8:12], "little")
    _ = pid
    return uid, gid




def _write_agent_metadata(path: Path, socket_path: Path, data_dir: Path) -> None:
    """Write the agent metadata JSON file with 0600 permissions."""
    payload = {
        "version": "v0",
        "pid": os.getpid(),
        "socket_path": str(socket_path),
        "data_dir": str(data_dir),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "uid": os.getuid(),
        "gid": os.getgid(),
    }
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
    os.chmod(path, 0o600)
    os.utime(path, times=(time.time(), time.time()))


def _install_signal_handlers(handler: Any) -> dict[int, Any]:
    """Install SIGINT/SIGTERM handlers and return previous handlers."""
    previous: dict[int, Any] = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, handler)
    return previous


def _restore_signal_handlers(previous: dict[int, Any]) -> None:
    """Restore previously installed signal handlers."""
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def _summarize_request(message: dict[str, Any]) -> str:
    """Return a safe, brief summary of a request envelope."""
    op = message.get("op")
    message_id = message.get("id")
    payload = message.get("payload", {})
    keys: list[str] = []
    client_name = None
    if isinstance(payload, dict):
        keys = sorted(str(key) for key in payload.keys())
        client_name = payload.get("client_name")
    summary = f"op={op!r} id={message_id!r} keys={keys!r}"
    if isinstance(client_name, str) and client_name:
        summary += f" client_name={client_name!r}"
    return summary
