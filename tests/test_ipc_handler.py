from __future__ import annotations

import time
from pathlib import Path

import pytest

from ciphercache.daemon.state import DaemonConfig, DaemonState
from ciphercache.ipc.handler import ERROR_INVALID_REQUEST, ERROR_LOCKED, handle_request


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
    state.unlock(60)
    state.secrets = {"service/api": {"api_key": "test"}}
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
    assert state.secrets == {}
    assert state.tickets == set()

def test_shutdown_wipes_state_and_requests_exit(tmp_path: Path) -> None:
    config = DaemonConfig(data_dir=tmp_path)
    state = DaemonState(config=config)
    state.unlock(60)
    state.secrets = {"service/api": {"api_key": "demo"}}
    ticket_path = state.issue_ticket("demo")
    token = ticket_path.read_text(encoding="utf-8")

    request = {"version": "v0", "id": "1", "type": "request", "op": "shutdown", "payload": {}}
    response = handle_request(state, request)
    assert response["type"] == "response"
    assert state.locked is True
    assert state.secrets == {}
    assert token not in state.tickets
    assert state.shutdown_requested is True
