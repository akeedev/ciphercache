from __future__ import annotations

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


@pytest.mark.parametrize("payload", [{"ttl": ""}, {"ttl": "1w"}, {"ttl": 10}])

def test_unlock_invalid_ttl(locked_state: DaemonState, payload: dict[str, object]) -> None:
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
        "payload": {"ttl": "5s"},
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
        "payload": {"ttl": "infinity"},
    }
    response = handle_request(state, request)
    assert response["type"] == "response"
    assert state.ttl_expiry is None
    assert state.ttl_remaining_seconds() > 0
