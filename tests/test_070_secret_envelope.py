from __future__ import annotations

from ciphercache.secret import Secret, SecretEnvelope


def test_secret_redacts_str_and_repr() -> None:
    secret = Secret("value")
    assert str(secret) == "<*redacted*>"
    assert repr(secret) == "<*redacted*>"


def test_secret_empty_string_is_blank() -> None:
    secret = Secret("")
    assert str(secret) == ""
    assert repr(secret) == ""


def test_secret_reveal_and_use() -> None:
    secret = Secret("value")
    assert secret.reveal() == "value"
    assert secret.use(lambda value: value.upper()) == "VALUE"


def test_secret_envelope_wraps_payload() -> None:
    payload = {"user": "alice", "password": "s3cret"}
    envelope = SecretEnvelope.from_payload(payload)
    assert isinstance(envelope["user"], Secret)
    assert envelope["password"].reveal() == "s3cret"


def test_secret_envelope_use_multi_key() -> None:
    payload = {"user": "alice", "password": "s3cret"}
    envelope = SecretEnvelope.from_payload(payload)
    combined = envelope.use(["user", "password"], lambda user, password: f"{user}:{password}")
    assert combined == "alice:s3cret"
