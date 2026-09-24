from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from backend.app.services import gitnexus_mcp_client as client


def _frame(payload: dict) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


class _FakeStdout:
    def __init__(self, data: bytes) -> None:
        self._data = bytearray(data)
        self._pos = 0

    def peek(self, size: int = 32768) -> bytes:
        return bytes(self._data[self._pos : self._pos + size])

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = bytes(self._data[self._pos :])
            self._pos = len(self._data)
            return chunk
        chunk = bytes(self._data[self._pos : self._pos + size])
        self._pos += len(chunk)
        return chunk


def _session_with_stdout(data: bytes) -> client._GitNexusMcpSession:
    session = client._GitNexusMcpSession(["node", "fake"], timeout_seconds=1.0)
    session._process = SimpleNamespace(stdin=SimpleNamespace(write=lambda *_: None, flush=lambda: None), stdout=_FakeStdout(data))
    return session


def test_request_skips_notification_in_same_read_chunk():
    notification = {"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info"}}
    response = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    session = _session_with_stdout(_frame(notification) + _frame(response))
    session._next_id = 1

    sent: list[dict] = []

    def _capture(payload: dict) -> None:
        sent.append(payload)

    session._send = _capture  # type: ignore[method-assign]
    result = session._request("resources/read", {"uri": "gitnexus://repos"})

    assert sent[0]["id"] == 1
    assert result["id"] == 1
    assert result["result"] == {"ok": True}


def test_read_message_preserves_trailing_frame_for_next_read():
    first = {"jsonrpc": "2.0", "id": 1, "result": {"a": 1}}
    second = {"jsonrpc": "2.0", "id": 2, "result": {"b": 2}}
    session = _session_with_stdout(_frame(first) + _frame(second))

    assert session._read_message() == first
    assert session._read_message() == second


def test_request_skips_notification_but_errors_on_wrong_response_id():
    notification = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {}}
    wrong = {"jsonrpc": "2.0", "id": 99, "result": {"ok": False}}
    session = _session_with_stdout(_frame(notification) + _frame(wrong))
    session._next_id = 1
    session._send = lambda payload: None  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="Unexpected GitNexus MCP response id"):
        session._request("initialize", {"protocolVersion": "2024-11-05"})
