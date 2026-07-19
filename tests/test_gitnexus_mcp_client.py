import json
from typing import Any

import pytest

from backend.app.services.gitnexus_mcp_client import _GitNexusMcpSession


def _frame(payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


class _BufferedStdout:
    def __init__(self, *chunks: bytes) -> None:
        self._chunks = list(chunks)
        self._buffer = bytearray()

    def peek(self, size: int) -> bytes:
        if not self._buffer and self._chunks:
            self._buffer.extend(self._chunks.pop(0))
        return bytes(self._buffer[:size])

    def read(self, size: int) -> bytes:
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data


class _FakeProcess:
    def __init__(self, *chunks: bytes) -> None:
        self.stdout = _BufferedStdout(*chunks)


def _session_with_bytes(*chunks: bytes) -> _GitNexusMcpSession:
    session = _GitNexusMcpSession(["unused"], timeout_seconds=0.05)
    session._process = _FakeProcess(*chunks)
    return session


def test_read_message_preserves_a_trailing_complete_frame() -> None:
    first = {"jsonrpc": "2.0", "id": 1, "result": {"value": "first"}}
    second = {"jsonrpc": "2.0", "id": 2, "result": {"value": "second"}}
    session = _session_with_bytes(_frame(first) + _frame(second))

    assert session._read_message() == first
    assert session._read_message() == second


def test_read_message_accepts_a_split_response_body() -> None:
    response = {"jsonrpc": "2.0", "id": 1, "result": {"value": "split"}}
    framed = _frame(response)
    split_at = framed.index(b"\r\n\r\n") + 6
    session = _session_with_bytes(framed[:split_at], framed[split_at:])

    assert session._read_message() == response


def test_request_skips_notification_before_matching_response(monkeypatch: pytest.MonkeyPatch) -> None:
    notification = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {}}
    response = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    session = _session_with_bytes(_frame(notification) + _frame(response))
    monkeypatch.setattr(session, "_send", lambda _payload: None)

    assert session._request("resources/read", {"uri": "gitnexus://repos"}) == response


def test_request_rejects_a_nonmatching_response_id(monkeypatch: pytest.MonkeyPatch) -> None:
    response = {"jsonrpc": "2.0", "id": 2, "result": {"ok": True}}
    session = _session_with_bytes(_frame(response))
    monkeypatch.setattr(session, "_send", lambda _payload: None)

    with pytest.raises(RuntimeError, match="Unexpected GitNexus MCP response id"):
        session._request("resources/read", {"uri": "gitnexus://repos"})
