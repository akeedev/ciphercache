from __future__ import annotations

import json
import socket
import tempfile
import threading
from pathlib import Path
from shutil import rmtree

import pytest

from ciphercache.client import Client, ClientConfig, Status, _load_agent_socket_path
from ciphercache.ipc.framing import encode_message


def _short_temp_dir() -> Path:
    """Create a short temp directory path to avoid UNIX socket path length issues."""
    return Path(tempfile.mkdtemp(prefix="cc-sdk-"))


def _recv_exact(conn: socket.socket, length: int) -> bytes:
    """Receive an exact number of bytes for test helpers."""
    chunks: list[bytes] = []
    remaining = length
    while remaining > 0:
        chunk = conn.recv(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _serve_once(socket_path: Path, response_envelope: dict[str, object]) -> threading.Thread:
    """Start a one-shot server that replies with the provided envelope."""
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()

    def run() -> None:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(socket_path))
            listener.listen(1)
            conn, _ = listener.accept()
            try:
                length_prefix = _recv_exact(conn, 4)
                if len(length_prefix) == 4:
                    length = int.from_bytes(length_prefix, "big")
                    _recv_exact(conn, length)
                conn.sendall(encode_message(response_envelope))
            finally:
                conn.close()
        finally:
            listener.close()
            if socket_path.exists():
                socket_path.unlink()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def _serve_sequence(socket_path: Path, responses: list[dict[str, object]]) -> threading.Thread:
    """Start a server that replies with a sequence of envelopes."""
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()

    def run() -> None:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(socket_path))
            listener.listen(len(responses))
            for response_envelope in responses:
                conn, _ = listener.accept()
                try:
                    length_prefix = _recv_exact(conn, 4)
                    if len(length_prefix) == 4:
                        length = int.from_bytes(length_prefix, "big")
                        _recv_exact(conn, length)
                    conn.sendall(encode_message(response_envelope))
                finally:
                    conn.close()
        finally:
            listener.close()
            if socket_path.exists():
                socket_path.unlink()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_status_returns_typed_dataclass() -> None:
    """Ensure status returns a typed Status object."""
    data_dir = _short_temp_dir()
    socket_path = data_dir / "ciphercached.sock"
    response: dict[str, object] = {
        "version": "v0",
        "id": "status",
        "type": "response",
        "op": "status",
        "payload": {"locked": False, "ttl_remaining_seconds": 10},
    }
    thread = _serve_once(socket_path, response)
    try:
        client = Client(config=ClientConfig(data_dir=data_dir))
        status = client.status()
        assert isinstance(status, Status)
        assert status.locked is False
        assert status.ttl_remaining_seconds == 10
    finally:
        thread.join(timeout=1.0)
        rmtree(data_dir, ignore_errors=True)


def test_agent_json_overrides_socket_path() -> None:
    """Ensure agent.json socket_path overrides config.socket_path."""
    data_dir = _short_temp_dir()
    socket_path = data_dir / "ciphercached.sock"
    agent_path = data_dir / "agent.json"
    agent_path.write_text(
        json.dumps({"socket_path": str(socket_path)}),
        encoding="utf-8",
    )
    response: dict[str, object] = {
        "version": "v0",
        "id": "ping",
        "type": "response",
        "op": "ping",
        "payload": {"ok": True},
    }
    thread = _serve_once(socket_path, response)
    try:
        config = ClientConfig(data_dir=data_dir, socket_path=data_dir / "bogus.sock")
        client = Client(config=config)
        assert client.ping() is True
    finally:
        thread.join(timeout=1.0)
        rmtree(data_dir, ignore_errors=True)


def test_default_ticket_path_uses_client_name() -> None:
    """Default ticket path should include client_name when ticket_path is unset."""
    data_dir = _short_temp_dir()
    try:
        config = ClientConfig(data_dir=data_dir, client_name="custom")
        assert config.ticket_path == data_dir / "tickets" / "custom.ticket"
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_unlock_requires_non_empty_secrets() -> None:
    """Unlock must reject empty secret lists."""
    data_dir = _short_temp_dir()
    client = Client(config=ClientConfig(data_dir=data_dir))
    try:
        with pytest.raises(ValueError):
            client.unlock("5s", [])
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_get_secret_uses_ticket() -> None:
    """get_secret uses ticket file and returns secret payload."""
    data_dir = _short_temp_dir()
    tickets_dir = data_dir / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = tickets_dir / "default.ticket"
    ticket_path.write_text("token", encoding="utf-8")
    socket_path = data_dir / "ciphercached.sock"

    response: dict[str, object] = {
        "version": "v0",
        "id": "secret",
        "type": "response",
        "op": "get_secret",
        "payload": {"secret": {"api_key": "demo"}},
    }
    thread = _serve_once(socket_path, response)
    try:
        client = Client(config=ClientConfig(data_dir=data_dir))
        secret = client.get_secret("service/api")
        assert secret["api_key"] == "demo"
    finally:
        thread.join(timeout=1.0)
        rmtree(data_dir, ignore_errors=True)


def test_get_secret_auto_client_init_when_missing_ticket() -> None:
    """get_secret auto-initializes a ticket when missing."""
    data_dir = _short_temp_dir()
    tickets_dir = data_dir / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = tickets_dir / "client.ticket"
    ticket_path.write_text("token", encoding="utf-8")
    socket_path = data_dir / "ciphercached.sock"

    responses: list[dict[str, object]] = [
        {
            "version": "v0",
            "id": "init",
            "type": "response",
            "op": "client_init",
            "payload": {"ticket_path": str(ticket_path)},
        },
        {
            "version": "v0",
            "id": "secret",
            "type": "response",
            "op": "get_secret",
            "payload": {"secret": {"api_key": "demo"}},
        },
    ]

    thread = _serve_sequence(socket_path, responses)
    try:
        config = ClientConfig(data_dir=data_dir, ticket_path=tickets_dir / "missing.ticket")
        client = Client(config=config)
        secret = client.get_secret("service/api")
        assert secret["api_key"] == "demo"
    finally:
        thread.join(timeout=1.0)
        rmtree(data_dir, ignore_errors=True)


def test_error_mapping_unauthorized() -> None:
    """Unauthorized errors map to PermissionError."""
    data_dir = _short_temp_dir()
    socket_path = data_dir / "ciphercached.sock"
    response: dict[str, object] = {
        "version": "v0",
        "id": "secret",
        "type": "error",
        "op": "get_secret",
        "payload": {"code": "unauthorized", "message": "nope"},
    }
    thread = _serve_once(socket_path, response)
    try:
        client = Client(config=ClientConfig(data_dir=data_dir))
        with pytest.raises(PermissionError):
            client.request("ping", {})
    finally:
        thread.join(timeout=1.0)
        rmtree(data_dir, ignore_errors=True)


def test_get_secret_retries_on_invalid_ticket() -> None:
    """get_secret should re-init ticket once on unauthorized."""
    data_dir = _short_temp_dir()
    tickets_dir = data_dir / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = tickets_dir / "default.ticket"
    ticket_path.write_text("token", encoding="utf-8")
    socket_path = data_dir / "ciphercached.sock"

    responses: list[dict[str, object]] = [
        {
            "version": "v0",
            "id": "secret",
            "type": "error",
            "op": "get_secret",
            "payload": {"code": "unauthorized", "message": "Invalid ticket"},
        },
        {
            "version": "v0",
            "id": "init",
            "type": "response",
            "op": "client_init",
            "payload": {"ticket_path": str(ticket_path)},
        },
        {
            "version": "v0",
            "id": "secret",
            "type": "response",
            "op": "get_secret",
            "payload": {"secret": {"api_key": "demo"}},
        },
    ]

    thread = _serve_sequence(socket_path, responses)
    try:
        client = Client(config=ClientConfig(data_dir=data_dir))
        secret = client.get_secret("service/api")
        assert secret["api_key"] == "demo"
    finally:
        thread.join(timeout=1.0)
        rmtree(data_dir, ignore_errors=True)


def test_close_store_returns_true() -> None:
    """close_store returns True on success."""
    data_dir = _short_temp_dir()
    socket_path = data_dir / "ciphercached.sock"
    response: dict[str, object] = {
        "version": "v0",
        "id": "close",
        "type": "response",
        "op": "close_store",
        "payload": {"ok": True},
    }
    thread = _serve_once(socket_path, response)
    try:
        client = Client(config=ClientConfig(data_dir=data_dir))
        assert client.close_store() is True
    finally:
        thread.join(timeout=1.0)
        rmtree(data_dir, ignore_errors=True)


def test_retry_on_connection_failure() -> None:
    """Retries are attempted for transient connection failures."""
    data_dir = _short_temp_dir()
    config = ClientConfig(data_dir=data_dir, retries=2, retry_backoff_seconds=0.0)
    client = Client(config=config)
    try:
        with pytest.raises(FileNotFoundError):
            client.ping()
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_load_agent_socket_path_malformed_json(tmp_path: Path) -> None:
    """_load_agent_socket_path returns None when agent.json contains invalid JSON."""
    agent_path = tmp_path / "agent.json"
    agent_path.write_text("{not valid json", encoding="utf-8")
    assert _load_agent_socket_path(tmp_path) is None


def test_load_agent_socket_path_missing_socket_key(tmp_path: Path) -> None:
    """_load_agent_socket_path returns None when socket_path is missing."""
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(json.dumps({"version": "v0"}), encoding="utf-8")
    assert _load_agent_socket_path(tmp_path) is None


def test_load_agent_socket_path_empty_socket(tmp_path: Path) -> None:
    """_load_agent_socket_path returns None when socket_path is empty."""
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(json.dumps({"socket_path": ""}), encoding="utf-8")
    assert _load_agent_socket_path(tmp_path) is None


def test_load_agent_socket_path_valid(tmp_path: Path) -> None:
    """_load_agent_socket_path returns the socket path when valid."""
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(json.dumps({"socket_path": "/tmp/test.sock"}), encoding="utf-8")
    result = _load_agent_socket_path(tmp_path)
    assert result == Path("/tmp/test.sock")
