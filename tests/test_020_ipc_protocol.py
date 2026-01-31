from __future__ import annotations

from pathlib import Path

import pytest

from ciphercache.daemon.state import DaemonConfig, DaemonState
from ciphercache.ipc.framing import decode_single_frame, encode_message
from ciphercache.ipc.handler import (
    ERROR_INVALID_REQUEST,
    ERROR_NOT_FOUND,
    ERROR_UNAUTHORIZED,
    handle_request,
    process_frame,
)
from ciphercache.ttl import parse_ttl


@pytest.fixture()
def daemon_state(tmp_path: Path) -> DaemonState:
    config = DaemonConfig(data_dir=tmp_path)
    state = DaemonState(config=config)
    state.unlock(parse_ttl("1h"))
    state.secrets["default"] = {"service/api": {"api_key": "test"}}
    return state


def test_length_prefixed_roundtrip() -> None:
    message = {"version": "v0", "id": "1", "type": "request", "op": "ping", "payload": {}}
    frame = encode_message(message)
    decoded = decode_single_frame(frame)
    assert decoded == message


def test_invalid_json_returns_invalid_request(daemon_state: DaemonState) -> None:
    invalid_payload = b"{not-json"
    frame = len(invalid_payload).to_bytes(4, "big") + invalid_payload
    response_frame = process_frame(daemon_state, frame)
    response = decode_single_frame(response_frame)
    assert response["type"] == "error"
    assert response["payload"]["code"] == ERROR_INVALID_REQUEST


def test_ping_response(daemon_state: DaemonState) -> None:
    request = {"version": "v0", "id": "ping", "type": "request", "op": "ping", "payload": {}}
    response = handle_request(daemon_state, request)
    assert response["type"] == "response"
    assert response["payload"]["ok"] is True


def test_status_response(daemon_state: DaemonState) -> None:
    request = {"version": "v0", "id": "status", "type": "request", "op": "status", "payload": {}}
    response = handle_request(daemon_state, request)
    assert response["payload"]["locked"] is False
    assert isinstance(response["payload"]["ttl_remaining_seconds"], int)


def test_get_secret_invalid_ticket(daemon_state: DaemonState) -> None:
    request = {
        "version": "v0",
        "id": "secret",
        "type": "request",
        "op": "get_secret",
        "payload": {"ticket": "bad", "secret_name": "service/api"},
    }
    response = handle_request(daemon_state, request)
    assert response["type"] == "error"
    assert response["payload"]["code"] == ERROR_UNAUTHORIZED


def test_get_secret_unknown_store(daemon_state: DaemonState) -> None:
    ticket_path = daemon_state.issue_ticket("demo")
    ticket = ticket_path.read_text(encoding="utf-8")
    request = {
        "version": "v0",
        "id": "secret",
        "type": "request",
        "op": "get_secret",
        "payload": {"ticket": ticket, "secret_name": "service/api", "store": "other"},
    }
    response = handle_request(daemon_state, request)
    assert response["type"] == "error"
    assert response["payload"]["code"] == ERROR_NOT_FOUND


def test_unknown_op_returns_invalid_request(daemon_state: DaemonState) -> None:
    request = {"version": "v0", "id": "oops", "type": "request", "op": "nope", "payload": {}}
    response = handle_request(daemon_state, request)
    assert response["type"] == "error"
    assert response["payload"]["code"] == ERROR_INVALID_REQUEST


def test_parse_ttl_combined() -> None:
    assert parse_ttl("1h 30m") == 5400


def test_get_secret_defaults_store(daemon_state: DaemonState) -> None:
    ticket_path = daemon_state.issue_ticket("demo")
    ticket = ticket_path.read_text(encoding="utf-8")
    request = {
        "version": "v0",
        "id": "secret",
        "type": "request",
        "op": "get_secret",
        "payload": {"ticket": ticket, "secret_name": "service/api"},
    }
    response = handle_request(daemon_state, request)
    assert response["type"] == "response"
    assert response["payload"]["secret"]["api_key"] == "test"
