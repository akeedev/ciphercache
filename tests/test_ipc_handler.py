from __future__ import annotations

import time
from pathlib import Path

import pytest

import ciphercache.ipc.handler as handler
from ciphercache.daemon.state import DaemonConfig, DaemonState
from ciphercache.ipc.handler import ERROR_INVALID_REQUEST, ERROR_LOCKED, ERROR_NOT_FOUND, handle_request
from ciphercache.store.keepassxc import KeePassXCConfig


@pytest.fixture()
def locked_state(tmp_path: Path) -> DaemonState:
    config = DaemonConfig(data_dir=tmp_path)
    return DaemonState(config=config)


def test_missing_envelope_fields(locked_state: DaemonState) -> None:
    response = handle_request(locked_state, {"op": "ping"})
    assert response["type"] == "error"
    assert response["payload"]["code"] == ERROR_INVALID_REQUEST


def test_invalid_message_type(locked_state: DaemonState) -> None:
    request = {"version": "v0", "id": "1", "type": "response", "op": "ping", "payload": {}}
    response = handle_request(locked_state, request)
    assert response["payload"]["code"] == ERROR_INVALID_REQUEST


def test_invalid_version(locked_state: DaemonState) -> None:
    request = {"version": "v1", "id": "1", "type": "request", "op": "ping", "payload": {}}
    response = handle_request(locked_state, request)
    assert response["payload"]["code"] == ERROR_INVALID_REQUEST


def test_get_secret_locked_returns_locked(tmp_path: Path) -> None:
    config = DaemonConfig(data_dir=tmp_path)
    state = DaemonState(config=config)
    request = {
        "version": "v0",
        "id": "1",
        "type": "request",
        "op": "get_secret",
        "payload": {"ticket": "nope", "secret_name": "service/api"},
    }
    response = handle_request(state, request)
    assert response["payload"]["code"] == ERROR_LOCKED


def test_get_secret_expired_ttl_returns_locked(tmp_path: Path) -> None:
    config = DaemonConfig(data_dir=tmp_path)
    state = DaemonState(config=config)
    state.unlock(60, ["service/api"])
    state.secrets["default"] = {"service/api": {"api_key": "test"}}
    ticket_path = state.issue_ticket("demo")
    ticket = ticket_path.read_text(encoding="utf-8")
    state.ttl_expiry = time.monotonic() - 1

    request = {
        "version": "v0",
        "id": "1",
        "type": "request",
        "op": "get_secret",
        "payload": {"ticket": ticket, "secret_name": "service/api"},
    }
    response = handle_request(state, request)
    assert response["payload"]["code"] == ERROR_LOCKED


@pytest.mark.parametrize("payload", [{"ttl": ""}, {"ttl": "1w"}, {"ttl": 10}])

def test_unlock_invalid_ttl(locked_state: DaemonState, payload: dict[str, object]) -> None:
    payload["secrets"] = ["service/api"]
    request = {"version": "v0", "id": "1", "type": "request", "op": "unlock", "payload": payload}
    response = handle_request(locked_state, request)
    assert response["payload"]["code"] == ERROR_INVALID_REQUEST


def test_unlock_sets_state(tmp_path: Path) -> None:
    config = DaemonConfig(data_dir=tmp_path)
    state = DaemonState(config=config)
    request = {
        "version": "v0",
        "id": "1",
        "type": "request",
        "op": "unlock",
        "payload": {"ttl": "5s", "secrets": ["service/api"]},
    }
    response = handle_request(state, request)
    assert response["type"] == "response"
    assert state.locked is False
    assert state.ttl_remaining_seconds() > 0


def test_unlock_infinity_sets_no_expiry(tmp_path: Path) -> None:
    config = DaemonConfig(data_dir=tmp_path)
    state = DaemonState(config=config)
    request = {
        "version": "v0",
        "id": "1",
        "type": "request",
        "op": "unlock",
        "payload": {"ttl": "infinity", "secrets": ["service/api"]},
    }
    response = handle_request(state, request)
    assert response["type"] == "response"
    assert state.ttl_expiry is None
    assert state.ttl_remaining_seconds() > 0


@pytest.mark.parametrize("payload", [{}, {"secrets": []}, {"secrets": [""]}, {"secrets": [123]}])
def test_unlock_invalid_secrets(locked_state: DaemonState, payload: dict[str, object]) -> None:
    payload["ttl"] = "5s"
    request = {"version": "v0", "id": "1", "type": "request", "op": "unlock", "payload": payload}
    response = handle_request(locked_state, request)
    assert response["payload"]["code"] == ERROR_INVALID_REQUEST


def test_unlock_with_store_config_populates_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = DaemonConfig(data_dir=tmp_path, store_config=KeePassXCConfig(database_path=Path("demo.kdbx")))
    state = DaemonState(config=config)

    def fake_load_secrets(_config: KeePassXCConfig, names: list[str]) -> dict[str, dict[str, object]]:
        assert names == ["service/api"]
        return {"service/api": {"title": "service/api"}}

    monkeypatch.setattr(handler, "load_secrets", fake_load_secrets)

    request = {
        "version": "v0",
        "id": "1",
        "type": "request",
        "op": "unlock",
        "payload": {"ttl": "5s", "secrets": ["service/api"]},
    }
    response = handle_request(state, request)
    assert response["type"] == "response"
    assert state.secrets["default"]["service/api"]["title"] == "service/api"


def test_unlock_with_store_config_missing_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = DaemonConfig(data_dir=tmp_path, store_config=KeePassXCConfig(database_path=Path("demo.kdbx")))
    state = DaemonState(config=config)

    def fake_load_secrets(_config: KeePassXCConfig, names: list[str]) -> dict[str, dict[str, object]]:
        _ = names
        return {}

    monkeypatch.setattr(handler, "load_secrets", fake_load_secrets)

    request = {
        "version": "v0",
        "id": "1",
        "type": "request",
        "op": "unlock",
        "payload": {"ttl": "5s", "secrets": ["service/api"]},
    }
    response = handle_request(state, request)
    assert response["payload"]["code"] == ERROR_NOT_FOUND
