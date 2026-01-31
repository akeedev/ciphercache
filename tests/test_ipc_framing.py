from __future__ import annotations

import json
import struct

import pytest

from ciphercache.ipc.framing import decode_frames, decode_single_frame, encode_message



def test_decode_single_frame_rejects_short_frame() -> None:
    with pytest.raises(ValueError):
        decode_single_frame(b"\x00\x01")


def test_decode_single_frame_length_mismatch() -> None:
    payload = json.dumps({"ok": True}).encode("utf-8")
    frame = struct.pack(">I", len(payload) + 1) + payload
    with pytest.raises(ValueError):
        decode_single_frame(frame)


def test_decode_frames_partial_buffer() -> None:
    message = {"version": "v0", "id": "1", "type": "request", "op": "ping", "payload": {}}
    frame = encode_message(message)
    head = frame[:5]
    tail = frame[5:]

    messages, remainder = decode_frames(head)
    assert messages == []
    assert remainder == head

    messages, remainder = decode_frames(remainder + tail)
    assert messages == [message]
    assert remainder == b""


def test_decode_frames_multiple_messages() -> None:
    message1 = {"version": "v0", "id": "1", "type": "request", "op": "ping", "payload": {}}
    message2 = {"version": "v0", "id": "2", "type": "request", "op": "ping", "payload": {}}
    buffer = encode_message(message1) + encode_message(message2)

    messages, remainder = decode_frames(buffer)
    assert messages == [message1, message2]
    assert remainder == b""
