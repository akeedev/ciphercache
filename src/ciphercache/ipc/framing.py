"""Length-prefixed JSON framing helpers for the IPC protocol."""

from __future__ import annotations

import json
import struct
from typing import Any

_LENGTH_PREFIX_SIZE = 4


def encode_message(message: dict[str, Any]) -> bytes:
    """Serialize a message dict to a length-prefixed JSON frame."""
    payload = json.dumps(message, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def decode_single_frame(frame: bytes) -> dict[str, Any]:
    """Decode a single length-prefixed frame into a dict."""
    if len(frame) < _LENGTH_PREFIX_SIZE:
        raise ValueError("Frame too short")
    length = struct.unpack(">I", frame[:_LENGTH_PREFIX_SIZE])[0]
    if len(frame) != length + _LENGTH_PREFIX_SIZE:
        raise ValueError("Frame length mismatch")
    payload = frame[_LENGTH_PREFIX_SIZE:]
    return json.loads(payload.decode("utf-8"))


def decode_frames(buffer: bytes) -> tuple[list[dict[str, Any]], bytes]:
    """Decode all complete frames in a buffer and return (messages, remainder)."""
    messages: list[dict[str, Any]] = []
    offset = 0
    while len(buffer) - offset >= _LENGTH_PREFIX_SIZE:
        length = struct.unpack(">I", buffer[offset : offset + _LENGTH_PREFIX_SIZE])[0]
        if len(buffer) - offset - _LENGTH_PREFIX_SIZE < length:
            break
        start = offset + _LENGTH_PREFIX_SIZE
        end = start + length
        payload = buffer[start:end]
        messages.append(json.loads(payload.decode("utf-8")))
        offset = end

    return messages, buffer[offset:]
