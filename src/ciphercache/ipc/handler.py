"""SPDX-License-Identifier: Apache-2.0
Copyright (c) 2026 @drakee

Provided "AS IS", without warranties or guarantees; use at your own risk.

Module overview:
- IPC request handling and dispatch for ciphercache.
- `handle_request` normalizes a raw dict into an `Envelope`, dispatches to per-op handlers,
  and maps exceptions to error envelopes.
- `process_frame` wraps frame decoding + handling for the server.

Version metadata (update when releasing):
- Version: 0.1.0
- Date: 2026-02-01
- Author: @drakee
- Repository: https://github.com/drakee/ciphercache
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from ciphercache.daemon.state import DaemonState
from ciphercache.ipc.framing import decode_single_frame, encode_message
from ciphercache.ttl import parse_ttl
from ciphercache.store.keepassxc import load_secrets


ERROR_INVALID_REQUEST = "invalid_request"
ERROR_UNAUTHORIZED = "unauthorized"
ERROR_LOCKED = "locked"
ERROR_NOT_FOUND = "not_found"
ERROR_INTERNAL = "internal_error"


@dataclass(frozen=True, slots=True)
class Envelope:
    """Normalized request envelope."""

    version: str
    message_id: str
    message_type: str
    op: str
    payload: dict[str, Any]


def _normalize_request(raw: dict[str, Any]) -> Envelope:
    """Validate and normalize a raw request dict into an Envelope."""
    if not isinstance(raw, dict):
        raise ValueError("Request must be an object")
    version = raw.get("version")
    message_id = raw.get("id")
    message_type = raw.get("type")
    op = raw.get("op")
    payload = raw.get("payload")

    if not all(isinstance(value, str) for value in (version, message_id, message_type, op)):
        raise ValueError("Missing or invalid envelope fields")
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object")

    return Envelope(
        version=cast(str, version),
        message_id=cast(str, message_id),
        message_type=cast(str, message_type),
        op=cast(str, op),
        payload=payload,
    )


def _response(request: Envelope, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a standard response envelope for a request."""
    return {
        "version": request.version,
        "id": request.message_id,
        "type": "response",
        "op": request.op,
        "payload": payload,
    }


def _error(message_id: str, op: str, code: str, message: str, version: str = "v0") -> dict[str, Any]:
    """Build a standard error envelope."""
    return {
        "version": version,
        "id": message_id,
        "type": "error",
        "op": op,
        "payload": {
            "code": code,
            "message": message,
        },
    }


def handle_request(state: DaemonState, raw: dict[str, Any]) -> dict[str, Any]:
    """Handle a request dict and return a response dict."""
    try:
        request = _normalize_request(raw)
    except ValueError as exc:
        return _error("unknown", "unknown", ERROR_INVALID_REQUEST, str(exc))

    if request.version != "v0":
        return _error(request.message_id, request.op, ERROR_INVALID_REQUEST, "Unsupported protocol version")
    if request.message_type != "request":
        return _error(request.message_id, request.op, ERROR_INVALID_REQUEST, "Invalid message type")

    state.expire_if_needed()

    handler = _HANDLERS.get(request.op)
    if handler is None:
        return _error(request.message_id, request.op, ERROR_INVALID_REQUEST, "Unknown operation")

    try:
        return handler(state, request)
    except ValueError as exc:
        return _error(request.message_id, request.op, ERROR_INVALID_REQUEST, str(exc))
    except PermissionError as exc:
        return _error(request.message_id, request.op, ERROR_UNAUTHORIZED, str(exc))
    except LookupError as exc:
        return _error(request.message_id, request.op, ERROR_NOT_FOUND, str(exc))
    except RuntimeError as exc:
        return _error(request.message_id, request.op, ERROR_LOCKED, str(exc))
    except Exception:
        return _error(request.message_id, request.op, ERROR_INTERNAL, "Internal error")


def process_frame(state: DaemonState, frame: bytes) -> bytes:
    """Decode a frame, handle it, and return a response frame."""
    try:
        message = decode_single_frame(frame)
    except Exception as exc:
        error = _error("unknown", "unknown", ERROR_INVALID_REQUEST, f"Invalid frame: {exc}")
        return encode_message(error)

    response = handle_request(state, message)
    return encode_message(response)


def _require_string(payload: dict[str, Any], key: str) -> str:
    """Return a required non-empty string from a payload."""
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing or invalid '{key}'")
    return value


def _require_string_list(payload: dict[str, Any], key: str) -> list[str]:
    """Return a required list of non-empty strings from a payload."""
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Missing or invalid '{key}'")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"Missing or invalid '{key}'")
        items.append(item)
    return items


def _handle_ping(state: DaemonState, request: Envelope) -> dict[str, Any]:
    """Handle ping requests."""
    _ = state
    return _response(request, {"ok": True})


def _handle_status(state: DaemonState, request: Envelope) -> dict[str, Any]:
    """Handle status requests."""
    payload = {
        "locked": state.locked,
        "ttl_remaining_seconds": state.ttl_remaining_seconds(),
    }
    return _response(request, payload)


def _handle_unlock(state: DaemonState, request: Envelope) -> dict[str, Any]:
    """Handle unlock requests."""
    ttl_value = _require_string(request.payload, "ttl")
    secret_names = _require_string_list(request.payload, "secrets")
    ttl_seconds = parse_ttl(ttl_value)
    if state.config.store_config is not None:
        secrets = load_secrets(state.config.store_config, secret_names)
        if len(secrets) != len(secret_names):
            raise LookupError("Secret not found")
        state.unlock(ttl_seconds, secret_names)
        store_alias = state.active_store_alias or state.config.store_alias_default
        state.secrets[store_alias] = secrets
    else:
        state.unlock(ttl_seconds, secret_names)
    return _response(request, {"ok": True})


def _handle_lock(state: DaemonState, request: Envelope) -> dict[str, Any]:
    """Handle lock requests."""
    state.lock()
    return _response(request, {"ok": True})


def _handle_close_store(state: DaemonState, request: Envelope) -> dict[str, Any]:
    """Handle close_store requests."""
    state.close_store()
    return _response(request, {"ok": True})


def _handle_client_init(state: DaemonState, request: Envelope) -> dict[str, Any]:
    """Handle client_init requests."""
    client_name = _require_string(request.payload, "client_name")
    ticket_path = state.issue_ticket(client_name)
    return _response(request, {"ticket_path": str(ticket_path)})


def _handle_get_secret(state: DaemonState, request: Envelope) -> dict[str, Any]:
    """Handle get_secret requests."""
    if state.locked:
        raise RuntimeError("Daemon is locked")
    ticket = _require_string(request.payload, "ticket")
    if not state.validate_ticket(ticket):
        raise PermissionError("Invalid ticket")

    store_alias = request.payload.get("store")
    if store_alias is None:
        store_alias = state.active_store_alias
    if not isinstance(store_alias, str) or not store_alias:
        raise ValueError("Missing or invalid 'store'")
    if state.active_store_alias and store_alias != state.active_store_alias:
        raise LookupError("Unknown store alias")

    secret_name = _require_string(request.payload, "secret_name")
    secret = state.get_secret(store_alias, secret_name)
    if secret is None:
        raise LookupError("Secret not found")

    return _response(request, {"secret": secret})


_HANDLERS = {
    "ping": _handle_ping,
    "status": _handle_status,
    "unlock": _handle_unlock,
    "lock": _handle_lock,
    "close_store": _handle_close_store,
    "client_init": _handle_client_init,
    "get_secret": _handle_get_secret,
}
