from __future__ import annotations

import json
import os
import socket
import tempfile
from pathlib import Path
from shutil import rmtree

import pytest

from ciphercache.daemon.runner import DemoDaemonState, _unlock_all_on_start
from ciphercache.daemon.server import UnixSocketServer
from ciphercache.daemon.state import DaemonConfig, DaemonState
from ciphercache.ipc.framing import decode_single_frame, encode_message
from ciphercache.ipc.handler import ERROR_UNAUTHORIZED
from ciphercache.store.keepassxc import KeePassXCConfig


def _short_temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="ciphercache-"))


def test_agent_metadata_written_and_removed() -> None:
    data_dir = _short_temp_dir()
    config = DaemonConfig(data_dir=data_dir, write_agent_metadata=True)
    state = DaemonState(config=config)
    server = UnixSocketServer(config=config, state=state)

    try:
        server.setup()
        agent_path = data_dir / "agent.json"
        assert agent_path.exists()
        mode = agent_path.stat().st_mode & 0o777
        assert mode == 0o600

        payload = json.loads(agent_path.read_text(encoding="utf-8"))
        assert payload["version"] == "v0"
        assert payload["socket_path"] == str(config.socket_path)
        assert payload["data_dir"] == str(config.data_dir)
        assert payload["uid"] == os.getuid()
        assert payload["gid"] == os.getgid()

        server.close()
        assert not agent_path.exists()
    finally:
        rmtree(data_dir, ignore_errors=True)

def test_socket_file_permissions_and_cleanup() -> None:
    data_dir = _short_temp_dir()
    config = DaemonConfig(data_dir=data_dir, write_agent_metadata=False)
    state = DaemonState(config=config)
    server = UnixSocketServer(config=config, state=state)

    try:
        server.setup()
        socket_path = config.socket_path
        assert socket_path is not None
        assert socket_path.exists()
        mode = socket_path.stat().st_mode & 0o777
        assert mode == 0o600

        server.close()
        assert not socket_path.exists()
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_handle_connection_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _short_temp_dir()
    config = DaemonConfig(data_dir=data_dir, write_agent_metadata=False)
    state = DaemonState(config=config)
    server = UnixSocketServer(config=config, state=state)

    monkeypatch.setattr(
        "ciphercache.daemon.server._get_peer_credentials",
        lambda _conn: (os.getuid(), os.getgid()),
    )

    try:
        client, server_sock = socket.socketpair()
        try:
            request = {"version": "v0", "id": "ping", "type": "request", "op": "ping", "payload": {}}
            client.sendall(encode_message(request))
            server._handle_connection(server_sock)
            response_frame = client.recv(4096)
        finally:
            client.close()
            server_sock.close()

        response = decode_single_frame(response_frame)
        assert response["type"] == "response"
        assert response["payload"]["ok"] is True
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_handle_connection_ignores_broken_pipe() -> None:
    """Server should ignore clients that disconnect before response."""
    data_dir = _short_temp_dir()
    config = DaemonConfig(data_dir=data_dir, write_agent_metadata=False)
    state = DaemonState(config=config)
    server = UnixSocketServer(config=config, state=state)

    try:
        client, server_sock = socket.socketpair()
        try:
            request = {"version": "v0", "id": "ping", "type": "request", "op": "ping", "payload": {}}
            client.sendall(encode_message(request))
            client.close()
            server._handle_connection(server_sock)
        finally:
            server_sock.close()
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_handle_connection_allows_when_peer_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _short_temp_dir()
    config = DaemonConfig(data_dir=data_dir, write_agent_metadata=False)
    state = DaemonState(config=config)
    server = UnixSocketServer(config=config, state=state)

    def fake_get_peer(_conn: socket.socket) -> tuple[int | None, int | None]:
        return None, None

    monkeypatch.setattr("ciphercache.daemon.server._get_peer_credentials", fake_get_peer)

    try:
        client, server_sock = socket.socketpair()
        try:
            request = {"version": "v0", "id": "ping", "type": "request", "op": "ping", "payload": {}}
            client.sendall(encode_message(request))
            server._handle_connection(server_sock)
            response_frame = client.recv(4096)
        finally:
            client.close()
            server_sock.close()

        response = decode_single_frame(response_frame)
        assert response["type"] == "response"
        assert response["payload"]["ok"] is True
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_handle_connection_rejects_when_peer_required(monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _short_temp_dir()
    config = DaemonConfig(data_dir=data_dir, write_agent_metadata=False, require_peer_credentials=True)
    state = DaemonState(config=config)
    server = UnixSocketServer(config=config, state=state)

    def fake_get_peer(_conn: socket.socket) -> tuple[int | None, int | None]:
        return None, None

    monkeypatch.setattr("ciphercache.daemon.server._get_peer_credentials", fake_get_peer)

    try:
        client, server_sock = socket.socketpair()
        try:
            request = {"version": "v0", "id": "ping", "type": "request", "op": "ping", "payload": {}}
            client.sendall(encode_message(request))
            server._handle_connection(server_sock)
            response_frame = client.recv(4096)
        finally:
            client.close()
            server_sock.close()

        response = decode_single_frame(response_frame)
        assert response["type"] == "error"
        assert response["payload"]["code"] == ERROR_UNAUTHORIZED
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_rejects_large_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = _short_temp_dir()
    config = DaemonConfig(data_dir=data_dir, max_frame_bytes=32, write_agent_metadata=False)
    state = DaemonState(config=config)
    server = UnixSocketServer(config=config, state=state)

    monkeypatch.setattr(
        "ciphercache.daemon.server._get_peer_credentials",
        lambda _conn: (os.getuid(), os.getgid()),
    )

    try:
        client, server_sock = socket.socketpair()
        try:
            length_prefix = (config.max_frame_bytes + 1).to_bytes(4, "big")
            client.sendall(length_prefix + b"x")
            server._handle_connection(server_sock)
            response_frame = client.recv(4096)
        finally:
            client.close()
            server_sock.close()

        response = decode_single_frame(response_frame)
        assert response["type"] == "error"
        assert response["payload"]["code"] == "invalid_request"
    finally:
        rmtree(data_dir, ignore_errors=True)


def test_handle_signal_closes_listener() -> None:
    data_dir = _short_temp_dir()
    config = DaemonConfig(data_dir=data_dir, write_agent_metadata=False)
    state = DaemonState(config=config)
    server = UnixSocketServer(config=config, state=state)

    try:
        server.setup()
        assert server.listener is not None
        assert server.listener.fileno() >= 0

        server._handle_signal(15, None)
        assert server._running is False
        assert server.listener is not None
        assert server.listener.fileno() == -1
    finally:
        server.close()
        rmtree(data_dir, ignore_errors=True)


@pytest.mark.skipif(
    not hasattr(socket, "getpeereid"),
    reason="getpeereid is not available on this platform",
)
def test_peer_credentials_match_current_user() -> None:
    client, server_sock = socket.socketpair()
    try:
        uid, gid = socket.getpeereid(server_sock)  # type: ignore[attr-defined]
    finally:
        client.close()
        server_sock.close()

    assert uid == os.getuid()
    assert gid == os.getgid()


def test_demo_daemon_state_seeds_secrets(tmp_path: Path) -> None:
    """DemoDaemonState should seed demo secrets for requested names on unlock."""
    config = DaemonConfig(data_dir=tmp_path)
    state = DemoDaemonState(config=config)
    state.unlock(60, ["service/api", "service/db"])
    store = state.secrets.get("default", {})
    assert "service/api" in store
    assert store["service/api"]["demo"] is True
    assert store["service/api"]["value"] == "demo:service/api"
    assert "service/db" in store
    assert store["service/db"]["value"] == "demo:service/db"


def test_unlock_all_on_start_populates_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_unlock_all_on_start should load and cache all secrets from the store."""
    store_config = KeePassXCConfig(database_path=Path("demo.kdbx"))
    config = DaemonConfig(data_dir=tmp_path, store_config=store_config, unlock_all_ttl=3600)
    state = DaemonState(config=config)

    import ciphercache.daemon.runner as runner

    def fake_load_all(_config: KeePassXCConfig) -> dict[str, dict[str, object]]:
        return {
            "service/api": {"title": "service/api", "password": "s3cret"},
            "service/db": {"title": "service/db", "password": "dbpass"},
        }

    monkeypatch.setattr(runner, "load_all_secrets", fake_load_all)
    _unlock_all_on_start(state)

    assert state.locked is False
    assert "service/api" in state.secrets["default"]
    assert "service/db" in state.secrets["default"]
    assert state.secrets["default"]["service/api"]["password"] == "s3cret"


def test_unlock_all_on_start_requires_store_config(tmp_path: Path) -> None:
    """_unlock_all_on_start should raise when store_config is None."""
    config = DaemonConfig(data_dir=tmp_path)
    state = DaemonState(config=config)
    with pytest.raises(ValueError, match="store_config is required"):
        _unlock_all_on_start(state)
