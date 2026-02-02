from __future__ import annotations

from pathlib import Path

import time

import pytest

from ciphercache.daemon.state import DaemonConfig, DaemonState
from ciphercache.ttl import parse_ttl


def test_ticket_files_are_0600(tmp_path: Path) -> None:
    state = DaemonState(config=DaemonConfig(data_dir=tmp_path))
    ticket_path = state.issue_ticket("demo")
    mode = ticket_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_lock_wipes_cached_secrets(tmp_path: Path) -> None:
    state = DaemonState(config=DaemonConfig(data_dir=tmp_path))
    state.unlock(parse_ttl("1h"), ["service/api"])
    state.secrets["default"] = {"service/api": {"api_key": "value"}}
    state.lock()
    assert state.secrets == {}


def test_tickets_invalid_when_locked(tmp_path: Path) -> None:
    state = DaemonState(config=DaemonConfig(data_dir=tmp_path))
    ticket_path = state.issue_ticket("demo")
    token = ticket_path.read_text(encoding="utf-8")
    assert state.validate_ticket(token) is False

    state.unlock(parse_ttl("1h"), ["service/api"])
    assert state.validate_ticket(token) is True

    state.lock()
    assert state.validate_ticket(token) is False


def test_lock_clears_tickets(tmp_path: Path) -> None:
    state = DaemonState(config=DaemonConfig(data_dir=tmp_path))
    state.unlock(parse_ttl("1h"), ["service/api"])
    ticket_path = state.issue_ticket("demo")
    token = ticket_path.read_text(encoding="utf-8")
    assert state.validate_ticket(token) is True

    state.lock()
    state.unlock(parse_ttl("1h"), ["service/api"])
    assert state.validate_ticket(token) is False


def test_expired_ttl_invalidates_tickets(tmp_path: Path) -> None:
    state = DaemonState(config=DaemonConfig(data_dir=tmp_path))
    state.unlock(parse_ttl("1h"), ["service/api"])
    ticket_path = state.issue_ticket("demo")
    token = ticket_path.read_text(encoding="utf-8")
    state.ttl_expiry = time.monotonic() - 1

    assert state.validate_ticket(token) is False
    assert state.locked is True


def test_default_store_alias_set_on_unlock(tmp_path: Path) -> None:
    state = DaemonState(config=DaemonConfig(data_dir=tmp_path))
    state.unlock(parse_ttl("1h"), ["service/api"])
    assert state.active_store_alias == "default"


@pytest.mark.parametrize("client_name", ["../oops", "..", "bad/name", "bad\\name", ""])
def test_issue_ticket_rejects_invalid_client_name(tmp_path: Path, client_name: str) -> None:
    state = DaemonState(config=DaemonConfig(data_dir=tmp_path))
    with pytest.raises(ValueError):
        state.issue_ticket(client_name)
