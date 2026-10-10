"""Synthetic multipart bytes -> actual route/dispatch -> Ledger parser contracts.

Only queue transport and request identity are substituted. Scope authorization,
governance receipts, base64 encoding and CSV parsing/hashing are production code.
These tests do not run a worker, import financial data, or validate binary workbooks.
"""
from __future__ import annotations

import asyncio
import _socket
import base64
import hashlib
import importlib
import json
import os
import socket
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app.api.routes import ledger
from backend.app.repositories.job_state_repo import JobStateRepository
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services import ledger_import_run_service as runs
from backend.app.services import ledger_import_service as service

pytestmark = pytest.mark.integration
BOUNDARY = b"SYNTHETIC-BOUNDARY"


@pytest.fixture(autouse=True)
def deny_external_io(monkeypatch):
    def blocked(*args, **kwargs):
        # CPython implements socketpair with a private loopback connection on
        # Windows. Permit only that exact stdlib frame, socket and destination;
        # all request/provider networking remains denied.
        frame = sys._getframe(1)
        if (
            os.name == "nt"
            and frame.f_code is getattr(socket.socketpair, "__code__", None)
            and len(args) == 2
            and args[0] is frame.f_locals.get("csock")
            and args[1] == (frame.f_locals.get("addr"), frame.f_locals.get("port"))
            and args[1][0] in {"127.0.0.1", "::1"}
        ):
            return _socket.socket.connect(*args, **kwargs)
        raise AssertionError("No network/provider access in synthetic multipart tests")

    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, name, blocked)
    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, blocked)
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "false")


@pytest.mark.parametrize("destination", [("127.0.0.1", 9), ("198.51.100.1", 443)])
def test_network_guard_rejects_unrelated_connections(destination):
    with socket.socket() as client:
        with pytest.raises(AssertionError, match="No network/provider access"):
            client.connect(destination)


def multipart(payload, *, boundary=BOUNDARY, filename="synthetic.csv", fields=False):
    parts = []
    if fields:
        parts.append(b'Content-Disposition: form-data; name="description"\r\n\r\nSYNTHETIC')
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        'Content-Type: application/octet-stream\r\n\r\n'.encode("latin-1") + payload
    )
    if fields:
        parts.append(b'Content-Disposition: form-data; name="after"\r\n\r\nDONE')
    return b"".join(b"--" + boundary + b"\r\n" + part + b"\r\n" for part in parts) + b"--" + boundary + b"--\r\n"


def request_for(body, *, boundary=BOUNDARY, content_length=None, chunk_size=None, content_type=None):
    headers = [(b"content-type", content_type or b"multipart/form-data; boundary=" + boundary)]
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode("ascii")))
    chunks = [body] if chunk_size is None else [body[i:i + chunk_size] for i in range(0, len(body), chunk_size)]
    if not chunks:
        chunks = [b""]
    state = SimpleNamespace(reads=0)

    async def receive():
        state.reads += 1
        index = state.reads - 1
        assert index < len(chunks), "Unexpected receive after request completion"
        return {"type": "http.request", "body": chunks[index], "more_body": index + 1 < len(chunks)}

    return Request({"type": "http", "method": "POST", "path": "/api/ledger/import", "headers": headers}, receive), state


BYTE_CASES = [
    pytest.param(b"Bond", id="ordinary"),
    pytest.param(b"Bond--", id="trailing-hyphens"),
    pytest.param(b"----", id="only-four-hyphens"),
    pytest.param(b"--", id="only-two-hyphens"),
    pytest.param(b"Bond--\r\n", id="hyphens-payload-crlf"),
    pytest.param(b"Bond\r", id="final-cr"),
    pytest.param(b"Bond\n", id="final-lf"),
    pytest.param(b"Bond\r\n", id="final-crlf"),
    pytest.param(b"Bond\r\n\r\n", id="multiple-final-crlf"),
    pytest.param(b"\r\n", id="only-payload-crlf"),
    pytest.param(b"\x00\xff\x80--", id="binary-high-nul-hyphens"),
    pytest.param(b"\x00\xff\r\n--\r\n", id="binary-high-newlines"),
    pytest.param(b"abc--" + BOUNDARY + b"xyz", id="inline-token"),
    pytest.param(b"--" + BOUNDARY + b"xyz", id="start-token"),
    pytest.param(b"abc--" + BOUNDARY, id="end-token"),
    pytest.param(b"abc\r\n--" + BOUNDARY + b"xyz", id="crlf-token-nonsuffix"),
    pytest.param(b"abc\r\n--" + BOUNDARY + b"--xyz", id="false-close-nonsuffix"),
    pytest.param(b"abc\n--" + BOUNDARY + b"\r\nZ", id="bare-lf-token"),
    pytest.param(b"abc\r--" + BOUNDARY + b"\r\nZ", id="bare-cr-token"),
]


@pytest.mark.parametrize("payload", BYTE_CASES)
def test_extract_preserves_original_bytes(payload):
    request, _ = request_for(multipart(payload))
    assert asyncio.run(ledger._extract_multipart_file(request, max_file_bytes=1024)) == ("synthetic.csv", payload)


@pytest.mark.parametrize("chunk_size", [1, 2, 7, 31])
def test_fragmented_request_fields_and_literal_boundary(chunk_size):
    boundary = b"literal.+*?^$[](){}|boundary"
    payload = b"B\r\n--" + boundary + b"suffix\x00\xff--\r\n\r\n"
    body = multipart(payload, boundary=boundary, fields=True)
    request, state = request_for(body, boundary=boundary, chunk_size=chunk_size)
    assert asyncio.run(ledger._extract_multipart_file(request, max_file_bytes=1024)) == ("synthetic.csv", payload)
    assert state.reads == (len(body) + chunk_size - 1) // chunk_size


@pytest.mark.parametrize("tail", [b"", b"\r\n", b"\r\nEPILOGUE"])
def test_actual_closing_delimiter_and_first_file(tail):
    first = multipart(b"FIRST--", filename="first.csv")
    second = multipart(b"SECOND", filename="second.csv")
    body = first[:-(len(BOUNDARY) + 6)] + second
    body = body[:-2] + tail
    request, _ = request_for(body)
    assert asyncio.run(ledger._extract_multipart_file(request, max_file_bytes=1024)) == ("first.csv", b"FIRST--")


@pytest.mark.parametrize("padding", ["opening", "closing", "both"])
@pytest.mark.parametrize("payload", [b"SYNTHETIC", b"SYNTHETIC--"], ids=["ordinary", "hyphens"])
def test_delimiter_transport_padding_preserves_payload(padding, payload):
    body = multipart(payload)
    if padding in {"opening", "both"}:
        body = body.replace(b"--" + BOUNDARY + b"\r\n", b"--" + BOUNDARY + b" \t\r\n")
    if padding in {"closing", "both"}:
        body = body.replace(b"--" + BOUNDARY + b"--\r\n", b"--" + BOUNDARY + b"--\t \r\n")
    request, _ = request_for(body, chunk_size=1)
    assert asyncio.run(ledger._extract_multipart_file(request, max_file_bytes=1024)) == ("synthetic.csv", payload)


@pytest.mark.parametrize("kind", ["no-field", "no-filename", "empty-file", "no-header-separator", "no-opening", "no-final", "wrong-final", "invalid-close-suffix"])
def test_malformed_or_missing_file_rejected(kind):
    body = multipart(b"SYNTHETIC")
    if kind == "no-field":
        body = body.replace(b'name="file"', b'name="other"')
    elif kind == "no-filename":
        body = body.replace(b'; filename="synthetic.csv"', b"")
    elif kind == "empty-file":
        body = multipart(b"")
    elif kind == "no-header-separator":
        body = body.replace(b"\r\n\r\n", b"\r\n")
    elif kind == "no-opening":
        body = body[len(BOUNDARY) + 4:]
    elif kind == "no-final":
        body = body[:-(len(BOUNDARY) + 8)]
    elif kind == "wrong-final":
        body = body.replace(b"--" + BOUNDARY + b"--\r\n", b"--OTHER--\r\n")
    elif kind == "invalid-close-suffix":
        body = body.replace(b"--" + BOUNDARY + b"--\r\n", b"--" + BOUNDARY + b"--junk\r\n")
    request, _ = request_for(body)
    with pytest.raises(ValueError):
        asyncio.run(ledger._extract_multipart_file(request, max_file_bytes=1024))


@pytest.mark.parametrize("content_type", [b"application/octet-stream", b"multipart/form-data", b"multipart/form-data; boundary=\"\""])
def test_missing_boundary_rejected_before_body(content_type):
    request, state = request_for(b"unused", content_type=content_type)
    with pytest.raises(ValueError):
        asyncio.run(ledger._extract_multipart_file(request, max_file_bytes=16))
    assert state.reads == 0


@pytest.mark.parametrize("declared", ["-1", "not-an-integer", "17"])
def test_content_length_guards_precede_receive(declared):
    request, state = request_for(b"unused", content_length=declared)
    error = ledger._LedgerImportTooLargeError if declared == "17" else ValueError
    with pytest.raises(error):
        asyncio.run(ledger._read_bounded_request_body(request, max_body_bytes=16))
    assert state.reads == 0


@pytest.mark.parametrize("declared", [None, "1"])
def test_stream_overflow_cannot_hide_behind_absent_or_small_length(declared):
    request, state = request_for(b"x" * 17, content_length=declared, chunk_size=8)
    with pytest.raises(ledger._LedgerImportTooLargeError):
        asyncio.run(ledger._read_bounded_request_body(request, max_body_bytes=16))
    assert state.reads == 3


def test_exact_body_and_file_limits_and_file_overflow():
    request, _ = request_for(b"x" * 16, content_length=16, chunk_size=3)
    assert asyncio.run(ledger._read_bounded_request_body(request, max_body_bytes=16)) == b"x" * 16
    request, _ = request_for(multipart(b"x" * 16))
    assert asyncio.run(ledger._extract_multipart_file(request, max_file_bytes=16))[1] == b"x" * 16
    request, _ = request_for(multipart(b"x" * 17))
    with pytest.raises(ledger._LedgerImportTooLargeError):
        asyncio.run(ledger._extract_multipart_file(request, max_file_bytes=16))
    assert service.MAX_LEDGER_IMPORT_BYTES == 16 * 1024 * 1024
    assert ledger.MAX_LEDGER_MULTIPART_OVERHEAD_BYTES == 64 * 1024


@pytest.fixture
def route_chain(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        governance_path=tmp_path / "governance", governance_backend="jsonl",
        governance_sql_dsn=f"sqlite:///{tmp_path / 'scopes.sqlite'}",
        postgres_dsn=f"sqlite:///{tmp_path / 'scopes.sqlite'}",
        job_state_dsn=f"sqlite:///{tmp_path / 'jobs.sqlite'}",
        duckdb_path=tmp_path / "unused-synthetic.duckdb",
    )
    scopes = UserScopeRepository(settings.governance_sql_dsn)
    scopes.grant_scope(user_id="synthetic-importer", role="admin", resource="ledger.data", action="import",
                       operator="synthetic-test", reason="Isolated multipart byte contract")
    scopes.engine.dispose()
    monkeypatch.setattr(ledger, "get_settings", lambda: settings)
    task = importlib.import_module("backend.app.tasks.ledger_import")
    sends = []
    monkeypatch.setattr(task.run_ledger_import, "send", lambda **kwargs: sends.append(kwargs))
    app = FastAPI()
    app.include_router(ledger.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id="synthetic-importer", role="admin", identity_source="synthetic-test")
    yield SimpleNamespace(app=app, settings=settings, sends=sends, task=task, root=tmp_path)


def post(chain, payload, *, filename="synthetic.csv", query=""):
    with TestClient(chain.app) as client:
        return client.post("/api/ledger/import" + query, content=multipart(payload, filename=filename, fields=True),
                           headers={"content-type": "multipart/form-data; boundary=" + BOUNDARY.decode()})


@pytest.mark.parametrize("text", ["Bond", "Bond--", "abc--SYNTHETIC-BOUNDARYxyz"], ids=["ordinary", "trailing-hyphens", "inline-token"])
def test_real_route_dispatch_csv_parser_and_hash(route_chain, text, record_property):
    content = ("SYNTHETIC fixture\r\n日期,债券名称\r\n2026-10-06," + text).encode("utf-8")
    (route_chain.root / "submitted.csv").write_bytes(content)
    response = post(route_chain, content, filename=r"C:\synthetic\folder\SYNTHETIC.CSV")
    assert response.status_code == 202, response.text
    assert len(route_chain.sends) == 1
    sent = route_chain.sends[0]
    actual = base64.b64decode(sent["content_base64"], validate=True)
    (route_chain.root / "queued.csv").write_bytes(actual)
    parsed = service.parse_ledger_file(file_name=sent["file_name"], content=actual)
    different = service.parse_ledger_file(file_name="different.csv", content=content + b"X")
    digest = hashlib.sha256(content).hexdigest()
    observations = {"submitted_sha256": digest, "queued_sha256": hashlib.sha256(actual).hexdigest(),
                    "parser_file_hash": parsed.file_hash, "parser_source_version": parsed.source_version,
                    "parsed_bond_name": parsed.rows[0]["bond_name"], "different_file_hash": different.file_hash}
    (route_chain.root / "hash-observations.json").write_text(json.dumps(observations, indent=2), encoding="utf-8")
    record_property("hash_observations", json.dumps(observations))
    assert actual == content
    assert parsed.file_hash == "sha256:" + digest
    assert parsed.source_version == "sv_ledger_" + digest[:12]
    # The existing business parser uppercases standardized text. Raw source text
    # remains available separately; framing must preserve both hash and content.
    assert parsed.rows[0]["bond_name"] == text.upper()
    assert json.loads(parsed.rows[0]["raw_json"])["债券名称"] == text
    assert parsed.as_of_date == "2026-10-06"
    assert different.file_hash != parsed.file_hash
    body = response.json()
    assert body["data"] == {"status": "queued", "run_id": sent["run_id"], "file_name": "SYNTHETIC.CSV"}
    assert body["trace"]["run_id"] == sent["run_id"]
    assert sent["duckdb_path"] == str(route_chain.settings.duckdb_path)
    assert sent["governance_dir"] == str(route_chain.settings.governance_path)
    status = runs.get_ledger_import_run_status(
        governance_dir=route_chain.settings.governance_path, governance_backend="jsonl",
        governance_sql_dsn=route_chain.settings.governance_sql_dsn, run_id=sent["run_id"])
    assert status["status"] == "queued"
    jobs = JobStateRepository(route_chain.settings.job_state_dsn)
    try:
        assert jobs.get_latest_run(sent["run_id"])["status"] == "queued"
    finally:
        jobs.engine.dispose()


@pytest.mark.parametrize("filename", ["synthetic.csv", "synthetic.xls", "synthetic.xlsx"])
def test_allowed_suffix_binary_queue_integrity(route_chain, filename):
    payload = b"\x00\xffSYNTHETIC--" + BOUNDARY + b"inline\r\n\r\n--"
    response = post(route_chain, payload, filename=filename)
    assert response.status_code == 202
    assert base64.b64decode(route_chain.sends[0]["content_base64"], validate=True) == payload


@pytest.mark.parametrize("case", ["unsupported-extension", "unknown-query", "forbidden", "unavailable-auth", "declared-oversize"])
def test_route_guards_no_dispatch(route_chain, monkeypatch, case):
    body_reads = []
    original_stream = Request.stream

    async def counted_stream(request):
        body_reads.append(True)
        async for chunk in original_stream(request):
            yield chunk

    monkeypatch.setattr(Request, "stream", counted_stream)
    filename, query, expected, code = "synthetic.csv", "", 400, "LEDGER_IMPORT_INVALID_REQUEST"
    if case == "unsupported-extension":
        filename = "synthetic.txt"
    elif case == "unknown-query":
        query = "?unexpected=1"
    elif case == "forbidden":
        route_chain.app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            user_id="ungranted-synthetic-user", role="admin", identity_source="synthetic-test")
        expected, code = 403, "LEDGER_IMPORT_FORBIDDEN"
    elif case == "unavailable-auth":
        route_chain.settings.governance_sql_dsn = f"sqlite:///{route_chain.root / 'missing-parent' / 'scopes.sqlite'}"
        expected, code = 503, "LEDGER_AUTH_UNAVAILABLE"
    elif case == "declared-oversize":
        expected, code = 413, "LEDGER_IMPORT_TOO_LARGE"
    headers = {"content-type": "multipart/form-data; boundary=" + BOUNDARY.decode()}
    if case == "declared-oversize":
        headers["content-length"] = str(service.MAX_LEDGER_IMPORT_BYTES + ledger.MAX_LEDGER_MULTIPART_OVERHEAD_BYTES + 1)
    with TestClient(route_chain.app) as client:
        response = client.post("/api/ledger/import" + query, content=multipart(b"SYNTHETIC", filename=filename), headers=headers)
    assert response.status_code == expected, response.text
    assert response.json()["error"]["code"] == code
    assert route_chain.sends == []
    assert bool(body_reads) is (case == "unsupported-extension")


@pytest.mark.parametrize("failure", ["queued-receipt", "dispatch"])
def test_existing_failure_receipts(route_chain, monkeypatch, failure):
    if failure == "queued-receipt":
        route_chain.settings.governance_path.write_text("SYNTHETIC blocker", encoding="utf-8")
    else:
        def broken_send(**kwargs):
            route_chain.sends.append(kwargs)
            raise RuntimeError("Synthetic queue rejection")
        monkeypatch.setattr(route_chain.task.run_ledger_import, "send", broken_send)
    response = post(route_chain, b"SYNTHETIC--")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LEDGER_LOADING_FAILURE"
    if failure == "queued-receipt":
        assert route_chain.sends == []
    else:
        run_id = route_chain.sends[0]["run_id"]
        status = runs.get_ledger_import_run_status(
            governance_dir=route_chain.settings.governance_path, governance_backend="jsonl",
            governance_sql_dsn=route_chain.settings.governance_sql_dsn, run_id=run_id)
        assert status["status"] == "failed"
        assert status["error_category"] == "dispatch_failed"
