"""SPDX-License-Identifier: Apache-2.0
Blocking Unix domain socket server for ciphercached.
"""

from __future__ import annotations

import json
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
from ciphercache.ipc.handler import ERROR_INVALID_REQUEST, handle_request


_SO_PEERCRED = 0x11


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
        data_dir = self.config.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(data_dir, 0o700)

        socket_path = self.config.socket_path
        if socket_path is None:
            raise ValueError("socket_path is required")
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(socket_path.parent, 0o700)
        if socket_path.exists():
            socket_path.unlink()

        if self.config.write_agent_metadata:
            self.agent_metadata_path = data_dir / "agent.json"
            _write_agent_metadata(self.agent_metadata_path, socket_path, data_dir)

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        listener.listen()
        self.listener = listener

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

    def _handle_connection(self, conn: socket.socket) -> None:
        """Validate peer credentials, read a frame, and respond."""
        if not _validate_peer(conn, self.config.expected_uid, self.config.expected_gid):
            return

        conn.settimeout(self.config.read_timeout_seconds)
        length_prefix = _recv_exact(conn, 4)
        if length_prefix is None:
            return
        length = int.from_bytes(length_prefix, "big")
        if length > self.config.max_frame_bytes:
            error = _error_envelope(ERROR_INVALID_REQUEST, "Frame too large")
            conn.settimeout(self.config.write_timeout_seconds)
            conn.sendall(encode_message(error))
            return
        payload = _recv_exact(conn, length)
        if payload is None:
            return
        frame = length_prefix + payload

        try:
            message = decode_single_frame(frame)
            response = handle_request(self.state, message)
        except Exception as exc:
            response = _error_envelope(ERROR_INVALID_REQUEST, f"Invalid frame: {exc}")

        conn.settimeout(self.config.write_timeout_seconds)
        conn.sendall(encode_message(response))

    def _handle_signal(self, signum: int, _frame: object | None) -> None:
        _ = signum
        self._running = False
        if self.listener is not None:
            self.listener.close()


def _error_envelope(code: str, message: str) -> dict[str, Any]:
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


def _recv_exact(conn: socket.socket, length: int) -> bytes | None:
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


def _validate_peer(conn: socket.socket, expected_uid: int | None, expected_gid: int | None) -> bool:
    uid, gid = _get_peer_credentials(conn)
    if expected_uid is not None and uid is not None and uid != expected_uid:
        return False
    if expected_gid is not None and gid is not None and gid != expected_gid:
        return False
    return True


def _get_peer_credentials(conn: socket.socket) -> tuple[int | None, int | None]:
    if hasattr(socket, "getpeereid"):
        uid, gid = socket.getpeereid(conn)  # type: ignore[attr-defined]
        return uid, gid
    try:
        creds = conn.getsockopt(socket.SOL_SOCKET, _SO_PEERCRED, 12)
    except OSError:
        return None, None
    pid = int.from_bytes(creds[0:4], "little")
    uid = int.from_bytes(creds[4:8], "little")
    gid = int.from_bytes(creds[8:12], "little")
    _ = pid
    return uid, gid


def _write_agent_metadata(path: Path, socket_path: Path, data_dir: Path) -> None:
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
    previous: dict[int, Any] = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, handler)
    return previous


def _restore_signal_handlers(previous: dict[int, Any]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)
