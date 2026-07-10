from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.governance.settings import get_settings
from tests.helpers import load_module

EXPECTED_MAX_LEDGER_IMPORT_BYTES = 16 * 1024 * 1024
EXPECTED_MAX_LEDGER_MULTIPART_OVERHEAD_BYTES = 64 * 1024


def _scoped_import(service_mod, duckdb_path, *, run_id="ledger_import:test", **kwargs):
    from backend.app.tasks.ledger_import import run_ledger_import

    content = kwargs.pop("content")
    return run_ledger_import.fn(
        duckdb_path=str(duckdb_path),
        content_base64=base64.b64encode(content).decode("ascii"),
        run_id=run_id,
        **kwargs,
    )


def test_fastapi_application_registers_ledger_import_routes(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)

    app = load_module("backend.app.main", "backend/app/main.py").app
    paths = {route.path for route in app.routes}

    assert "/api/ledger/import" in paths
    assert "/api/ledger/imports" in paths
    responses = app.openapi()["paths"]["/api/ledger/import"]["post"]["responses"]
    assert "202" in responses
    assert "200" not in responses
    get_settings.cache_clear()


def test_ledger_import_api_queues_json_safe_payload_without_writing_batch(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks.ledger_import import run_ledger_import

    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    content = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="ROUTE-001",
                account_category="",
                asset_class="",
                face_amount="1",
                as_of_date="2026-03-17",
            )
        ],
    ).rstrip(b"\r\n")
    sent: dict[str, object] = {}
    monkeypatch.setattr(run_ledger_import, "send", lambda **kwargs: sent.update(kwargs))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post(
        "/api/ledger/import",
        files={"file": ("ZQTZSHOW-20260317.csv", content, "text/csv")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["data"]["status"] == "queued"
    assert payload["data"]["file_name"] == "ZQTZSHOW-20260317.csv"
    assert payload["data"]["run_id"] == sent["run_id"]
    assert payload["trace"]["run_id"] == sent["run_id"]
    assert payload["trace"]["request_id"].startswith("req_ledger_")
    assert sent["file_name"] == "ZQTZSHOW-20260317.csv"
    assert sent["duckdb_path"] == str(duckdb_path)
    assert base64.b64decode(str(sent["content_base64"]), validate=True) == content
    json.dumps(sent)
    assert not any(isinstance(value, bytes) for value in sent.values())

    listed = client.get("/api/ledger/imports").json()
    assert listed["data"]["items"] == []
    assert listed["data"]["total"] == 0
    get_settings.cache_clear()


def test_ledger_import_api_enforces_file_limit_when_content_length_is_false_or_missing(
    tmp_path,
    monkeypatch,
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks.ledger_import import run_ledger_import

    sent: list[dict[str, object]] = []
    monkeypatch.setattr(run_ledger_import, "send", lambda **kwargs: sent.append(kwargs))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    below_limit = b"x" * (EXPECTED_MAX_LEDGER_IMPORT_BYTES - 1)
    accepted = client.post(
        "/api/ledger/import",
        files={"file": ("ZQTZSHOW-20260317.csv", below_limit, "text/csv")},
    )
    assert accepted.status_code == 202
    assert len(base64.b64decode(sent.pop()["content_base64"], validate=True)) == len(below_limit)

    above_limit_body, content_type = _multipart_body(
        b"x" * (EXPECTED_MAX_LEDGER_IMPORT_BYTES + 1),
        file_name="ZQTZSHOW-20260317.csv",
    )
    false_length = client.post(
        "/api/ledger/import",
        content=above_limit_body,
        headers={"content-type": content_type, "content-length": "1"},
    )
    assert false_length.status_code == 413
    assert false_length.json()["error"]["code"] == "LEDGER_IMPORT_TOO_LARGE"
    assert sent == []

    missing_length_request = client.build_request(
        "POST",
        "/api/ledger/import",
        content=above_limit_body,
        headers={"content-type": content_type},
    )
    del missing_length_request.headers["content-length"]
    missing_length = client.send(missing_length_request)
    assert missing_length.status_code == 413
    assert missing_length.json()["error"]["code"] == "LEDGER_IMPORT_TOO_LARGE"
    assert sent == []

    small_body, small_content_type = _multipart_body(
        b"small",
        file_name="ZQTZSHOW-20260317.csv",
    )
    declared_too_large = client.post(
        "/api/ledger/import",
        content=small_body,
        headers={
            "content-type": small_content_type,
            "content-length": str(
                EXPECTED_MAX_LEDGER_IMPORT_BYTES
                + EXPECTED_MAX_LEDGER_MULTIPART_OVERHEAD_BYTES
                + 1
            ),
        },
    )
    assert declared_too_large.status_code == 413
    assert sent == []


def test_ledger_import_api_rejects_unsupported_suffix_without_enqueue(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks.ledger_import import run_ledger_import

    sent: list[dict[str, object]] = []
    monkeypatch.setattr(run_ledger_import, "send", lambda **kwargs: sent.append(kwargs))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post(
        "/api/ledger/import",
        files={"file": ("ledger.txt", b"not a ledger", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LEDGER_IMPORT_INVALID_REQUEST"
    assert "Unsupported ledger import file type" in response.json()["error"]["message"]
    assert sent == []


def test_ledger_import_actor_imports_csv_lists_batch_and_preserves_unknown_raw_json(
    tmp_path,
    monkeypatch,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="240001.IB",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="100.25",
                as_of_date="2026-03-17",
            )
        ],
        unknown_value="kept-in-raw-json",
    )

    payload = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317.csv",
        content=csv_bytes,
        run_id="ledger_import:actor-success",
    )

    assert payload["data"]["batch_id"] == 1
    assert payload["data"]["file_name"] == "ZQTZSHOW-20260317.csv"
    assert payload["data"]["file_hash"].startswith("sha256:")
    assert payload["data"]["as_of_date"] == "2026-03-17"
    assert payload["data"]["status"] == "success"
    assert payload["data"]["row_count"] == 1
    assert payload["data"]["error_count"] == 0
    assert payload["data"]["source_version"].startswith("sv_ledger_")
    assert payload["data"]["rule_version"] == "position_key_contract_v1"
    assert payload["metadata"]["no_data"] is False
    assert payload["trace"]["source_file_hash"] == payload["data"]["file_hash"]
    assert payload["data"]["run_id"] == "ledger_import:actor-success"
    assert payload["trace"]["run_id"] == "ledger_import:actor-success"

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    list_response = client.get("/api/ledger/imports")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["data"]["items"][0]["batch_id"] == 1
    assert listed["data"]["items"][0]["filename"] == "ZQTZSHOW-20260317.csv"
    assert listed["data"]["total"] == 1
    assert listed["metadata"]["no_data"] is False

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        raw_json = conn.execute("select raw_json from ledger_raw_row where batch_id = 1 and row_no = 1").fetchone()[0]
        snapshot = conn.execute(
            """
            select direction, face_amount, account_category_std, asset_class_std
            from position_snapshot
            where batch_id = 1 and row_no = 1
            """
        ).fetchone()
    finally:
        conn.close()

    assert "kept-in-raw-json" in raw_json
    assert snapshot == ("ASSET", pytest.approx(100.25), "银行账户", "持有至到期类资产")
    get_settings.cache_clear()


def test_ledger_import_actor_rejects_invalid_base64_before_service_call(monkeypatch):
    from backend.app.tasks import ledger_import as task_mod

    called = False

    class UnexpectedService:
        def __init__(self, duckdb_path: str) -> None:
            nonlocal called
            called = True

    monkeypatch.setattr(task_mod, "LedgerImportService", UnexpectedService)

    with pytest.raises(ValueError, match="base64"):
        task_mod.run_ledger_import.fn(
            file_name="ZQTZSHOW-20260317.csv",
            content_base64="not-base64!",
            duckdb_path="unused.duckdb",
            run_id="ledger_import:invalid",
        )

    assert called is False


def test_ledger_import_actor_rejects_oversize_base64_before_decode(monkeypatch):
    from backend.app.tasks import ledger_import as task_mod

    monkeypatch.setattr(
        task_mod.base64,
        "b64decode",
        lambda *args, **kwargs: pytest.fail("oversize payload reached base64 decode"),
    )
    maximum_base64_chars = 4 * ((EXPECTED_MAX_LEDGER_IMPORT_BYTES + 2) // 3)

    with pytest.raises(ValueError, match="too large"):
        task_mod.run_ledger_import.fn(
            file_name="ZQTZSHOW-20260317.csv",
            content_base64="A" * (maximum_base64_chars + 4),
            duckdb_path="unused.duckdb",
            run_id="ledger_import:oversize-encoded",
        )


def test_ledger_import_actor_rejects_oversize_decoded_bytes_before_service(monkeypatch):
    from backend.app.tasks import ledger_import as task_mod

    called = False

    class UnexpectedService:
        def __init__(self, duckdb_path: str) -> None:
            nonlocal called
            called = True

    monkeypatch.setattr(task_mod, "LedgerImportService", UnexpectedService)
    content_base64 = base64.b64encode(b"x" * (EXPECTED_MAX_LEDGER_IMPORT_BYTES + 1)).decode("ascii")

    with pytest.raises(ValueError, match="too large"):
        task_mod.run_ledger_import.fn(
            file_name="ZQTZSHOW-20260317.csv",
            content_base64=content_base64,
            duckdb_path="unused.duckdb",
            run_id="ledger_import:oversize-decoded",
        )

    assert called is False


def test_ledger_import_service_requires_task_scope_while_actor_succeeds(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="GUARD-001",
                account_category="",
                asset_class="",
                face_amount="1",
                as_of_date="2026-03-17",
            )
        ],
    )

    with pytest.raises(PermissionError, match="task write scope"):
        service_mod.LedgerImportService(str(duckdb_path)).import_file(
            file_name="ZQTZSHOW-20260317.csv",
            content=csv_bytes,
        )
    assert service_mod.LedgerImportService(str(duckdb_path)).list_imports()["data"]["items"] == []

    success = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317.csv",
        content=csv_bytes,
        run_id="ledger_import:guard-success",
    )
    duplicate = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317-copy.csv",
        content=csv_bytes,
        run_id="ledger_import:guard-duplicate",
    )
    assert success["data"]["status"] == "success"
    assert duplicate["data"]["status"] == "duplicate"


def test_ledger_import_actor_propagates_write_failure_and_rolls_back(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="ROLLBACK-001",
                account_category="",
                asset_class="",
                face_amount="1",
                as_of_date="2026-03-17",
            )
        ],
    )
    from backend.app.repositories import ledger_import_repo as repo_mod

    real_connect = repo_mod.duckdb.connect

    class FailingConnection:
        def __init__(self, connection):
            self._connection = connection

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def executemany(self, statement, parameters):
            if "insert into position_snapshot" in statement:
                raise RuntimeError("injected snapshot failure")
            return self._connection.executemany(statement, parameters)

    def failing_connect(*args, **kwargs):
        return FailingConnection(real_connect(*args, **kwargs))

    with monkeypatch.context() as patch:
        patch.setattr(repo_mod.duckdb, "connect", failing_connect)
        with pytest.raises(RuntimeError, match="injected snapshot failure"):
            _scoped_import(
                service_mod,
                duckdb_path,
                file_name="ZQTZSHOW-20260317.csv",
                content=csv_bytes,
                run_id="ledger_import:rollback",
            )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        assert conn.execute("select count(*) from ledger_import_batch").fetchone()[0] == 0
        assert conn.execute("select count(*) from ledger_raw_row").fetchone()[0] == 0
        assert conn.execute("select count(*) from position_snapshot").fetchone()[0] == 0
    finally:
        conn.close()


def test_ledger_import_position_key_matches_frozen_contract(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="abc001.ib",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="10",
                as_of_date="2026-03-17",
            )
        ],
    )

    result = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317.csv",
        content=csv_bytes,
    )

    expected_canonical = "|".join(
        [
            "ABC001.IB",
            "ABC001.IB-NAME",
            "FIOA",
            "银行账户",
            "5010",
            "持有至到期类资产",
            "CNY",
            "3000000001",
            "ID-001",
            "LEGAL-001",
            "2024-01-01",
            "2029-01-01",
            "BANK",
        ]
    )
    expected_key = hashlib.sha256(expected_canonical.encode("utf-8")).hexdigest()

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        position_key = conn.execute(
            "select position_key from position_snapshot where batch_id = ?",
            [result["data"]["batch_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert position_key == expected_key
    assert len(position_key) == 64
    get_settings.cache_clear()


def test_ledger_import_parser_supports_xlsx_blank_amounts_and_liability_alias(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    xlsx_bytes = _ledger_xlsx_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="BOND-LIABILITY",
                account_category="发行类债劵",
                asset_class="发行类债券",
                face_amount="",
                as_of_date="2026-03-17",
            )
        ],
        unknown_value="xlsx-unknown",
    )

    result = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317.xlsx",
        content=xlsx_bytes,
    )

    assert result["data"]["status"] == "success"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select direction, face_amount, account_category_std, asset_class_std, raw_json
            from position_snapshot s
            join ledger_raw_row r using (batch_id, row_no)
            where s.batch_id = ?
            """,
            [result["data"]["batch_id"]],
        ).fetchone()
    finally:
        conn.close()

    assert row[0] == "LIABILITY"
    assert row[1] is None
    assert row[2] == "发行类债券"
    assert row[3] == "发行类债券"
    assert "xlsx-unknown" in row[4]
    get_settings.cache_clear()


def test_ledger_import_returns_contract_error_envelope_for_invalid_request(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post("/api/ledger/import", content=b"not multipart")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "LEDGER_IMPORT_INVALID_REQUEST"
    assert payload["error"]["retryable"] is False
    assert "Content-Type must be multipart/form-data" in payload["error"]["message"]
    assert payload["trace"]["request_id"].startswith("req_ledger_")
    assert "detail" not in payload
    get_settings.cache_clear()


def test_ledger_import_queue_failure_returns_structured_503(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks.ledger_import import run_ledger_import

    def fail_send(**kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(run_ledger_import, "send", fail_send)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post(
        "/api/ledger/import",
        files={"file": ("ZQTZSHOW-20260317.csv", b"non-empty", "text/csv")},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"] == {
        "code": "LEDGER_LOADING_FAILURE",
        "message": "queue unavailable",
        "retryable": True,
    }
    assert payload["trace"]["request_id"].startswith("req_ledger_")


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_ledger_import_task_import_failure_returns_structured_503(
    tmp_path,
    monkeypatch,
    error_type,
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    app = load_module("backend.app.main", "backend/app/main.py").app
    route_mod = import_module("backend.app.api.routes.ledger")

    def fail_import_task():
        raise error_type("task import failed")

    monkeypatch.setattr(route_mod, "_import_task", fail_import_task)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/api/ledger/import",
        files={"file": ("ZQTZSHOW-20260317.csv", b"non-empty", "text/csv")},
    )

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "LEDGER_LOADING_FAILURE",
        "message": "task import failed",
        "retryable": True,
    }
    assert response.json()["trace"]["request_id"].startswith("req_ledger_")


def test_ledger_import_actor_duplicate_preserves_run_id_and_does_not_duplicate_snapshots(
    tmp_path,
    monkeypatch,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="DUP-001",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="10",
                as_of_date="2026-03-17",
            )
        ],
    )
    first = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317.csv",
        content=csv_bytes,
        run_id="ledger_import:first",
    )
    duplicate_payload = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317-copy.csv",
        content=csv_bytes,
        run_id="ledger_import:duplicate",
    )

    assert duplicate_payload["error"]["code"] == "LEDGER_IMPORT_DUPLICATE"
    assert duplicate_payload["data"]["status"] == "duplicate"
    assert duplicate_payload["data"]["run_id"] == "ledger_import:duplicate"
    assert duplicate_payload["trace"]["run_id"] == "ledger_import:duplicate"
    assert duplicate_payload["trace"]["duplicate_of_batch_id"] == first["data"]["batch_id"]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        batch_count = conn.execute("select count(*) from ledger_import_batch").fetchone()[0]
        snapshot_count = conn.execute("select count(*) from position_snapshot").fetchone()[0]
    finally:
        conn.close()

    assert batch_count == 1
    assert snapshot_count == 1
    get_settings.cache_clear()


def test_ledger_import_concurrent_duplicate_file_creates_one_successful_snapshot(
    tmp_path,
    monkeypatch,
):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    csv_bytes = _ledger_csv_bytes(
        service_mod,
        [
            _ledger_row_values(
                service_mod,
                bond_code="DUP-CONCURRENT",
                account_category="银行账户",
                asset_class="持有至到期类资产",
                face_amount="10",
                as_of_date="2026-03-17",
            )
        ],
    )

    def import_copy(file_name: str) -> str:
        payload = _scoped_import(
            service_mod,
            duckdb_path,
            file_name=file_name,
            content=csv_bytes,
        )
        return str(payload["data"]["status"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(
            executor.map(
                import_copy,
                ["ZQTZSHOW-20260317-a.csv", "ZQTZSHOW-20260317-b.csv"],
            )
        )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        batch_count = conn.execute("select count(*) from ledger_import_batch").fetchone()[0]
        snapshot_count = conn.execute("select count(*) from position_snapshot").fetchone()[0]
    finally:
        conn.close()

    assert statuses == ["duplicate", "success"]
    assert batch_count == 1
    assert snapshot_count == 1
    get_settings.cache_clear()


def test_ledger_import_real_pack_seven_xls_samples_import_without_errors(tmp_path, monkeypatch):
    pack_dir = _pack_dir()
    if pack_dir is None:
        pytest.skip("bank ledger pack sample_ledgers directory is not available")
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    sample_names = [
        "ZQTZSHOW-20260301(3).xls",
        "ZQTZSHOW-20260303.xls",
        "ZQTZSHOW-20260310.xls",
        "ZQTZSHOW-20260311.xls",
        "ZQTZSHOW-20260312.xls",
        "ZQTZSHOW-20260314.xls",
        "ZQTZSHOW-20260317.xls",
    ]
    missing_samples = [
        sample_name for sample_name in sample_names if not (pack_dir / "sample_ledgers" / sample_name).is_file()
    ]
    if missing_samples:
        pytest.skip(f"bank ledger pack samples are not available: {', '.join(missing_samples)}")

    payloads = []
    for sample_name in sample_names:
        payloads.append(
            _scoped_import(
                service_mod,
                duckdb_path,
                file_name=sample_name,
                content=(pack_dir / "sample_ledgers" / sample_name).read_bytes(),
            )
        )

    assert [payload["data"]["status"] for payload in payloads] == ["success"] * 7
    assert all(payload["data"]["row_count"] > 0 for payload in payloads)
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        batch_count = conn.execute("select count(*) from ledger_import_batch").fetchone()[0]
        raw_count = conn.execute("select count(*) from ledger_raw_row").fetchone()[0]
        snapshot_count = conn.execute("select count(*) from position_snapshot").fetchone()[0]
    finally:
        conn.close()

    assert batch_count == 7
    assert raw_count == snapshot_count
    get_settings.cache_clear()


def test_ledger_import_real_pack_20260317_golden_counts(tmp_path, monkeypatch):
    sample = _pack_sample("ZQTZSHOW-20260317.xls")
    if sample is None:
        pytest.skip("bank ledger pack sample ZQTZSHOW-20260317.xls is not available")
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )

    result = _scoped_import(
        service_mod,
        duckdb_path,
        file_name=sample.name,
        content=sample.read_bytes(),
    )

    assert result["data"]["row_count"] == 1838
    assert result["data"]["as_of_date"] == "2026-03-17"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        counts = conn.execute(
            """
            select
              count(*) as total_rows,
              sum(case when direction = 'ASSET' then 1 else 0 end) as asset_rows,
              sum(case when direction = 'LIABILITY' then 1 else 0 end) as liability_rows,
              round(sum(case when direction = 'ASSET' then face_amount else 0 end) / 100000000, 2) as asset_face_100m,
              round(sum(case when direction = 'LIABILITY' then face_amount else 0 end) / 100000000, 2) as liability_face_100m
            from position_snapshot
            where batch_id = ?
            """,
            [result["data"]["batch_id"]],
        ).fetchone()
        traced = conn.execute(
            """
            select count(*)
            from position_snapshot s
            join ledger_raw_row r using (batch_id, row_no)
            where s.batch_id = ?
            """,
            [result["data"]["batch_id"]],
        ).fetchone()[0]
    finally:
        conn.close()

    assert counts == (1838, 1706, 132, pytest.approx(3289.07), pytest.approx(1231.77))
    assert traced == 1838
    get_settings.cache_clear()


def test_ledger_import_schema_registry_adds_batch_raw_and_snapshot_tables():
    loader = load_module(
        "backend.app.schema_registry.duckdb_loader",
        "backend/app/schema_registry/duckdb_loader.py",
    )
    conn = duckdb.connect(":memory:")
    try:
        loader.apply_registry_sql(conn)
        tables = {
            row[0]
            for row in conn.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'main'
                """
            ).fetchall()
        }
    finally:
        conn.close()

    assert {"ledger_import_batch", "ledger_raw_row", "position_snapshot"} <= tables


def _configure_ledger_import_env(tmp_path, monkeypatch) -> Path:
    duckdb_path = tmp_path / "moss.duckdb"
    auth_scope_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{auth_scope_path.as_posix()}")
    get_settings.cache_clear()
    from backend.app.repositories.user_scope_repo import UserScopeRepository

    repo = UserScopeRepository(f"sqlite:///{auth_scope_path.as_posix()}")
    repo.grant_scope(
        user_id="*",
        role=None,
        resource="ledger.data",
        action="import",
    )
    repo.grant_scope(
        user_id="*",
        role=None,
        resource="ledger.data",
        action="read",
    )
    return duckdb_path


def _ledger_csv_bytes(service_mod, rows: list[list[object]], *, unknown_value: str = "") -> bytes:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["ZQTZSHOW"])
    writer.writerow([spec.source_field for spec in service_mod.FIELD_SPECS] + ["未知列"])
    for row in rows:
        writer.writerow([*row, unknown_value])
    return output.getvalue().encode("utf-8-sig")


def _ledger_xlsx_bytes(service_mod, rows: list[list[object]], *, unknown_value: str = "") -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "ZQTZSHOW"
    worksheet.append(["ZQTZSHOW"])
    worksheet.append([spec.source_field for spec in service_mod.FIELD_SPECS] + ["未知列"])
    for row in rows:
        worksheet.append([*row, unknown_value])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _ledger_row_values(
    service_mod,
    *,
    bond_code: str,
    account_category: str,
    asset_class: str,
    face_amount: str,
    as_of_date: str,
) -> list[object]:
    values = {
        "bond_code": bond_code,
        "bond_name": f"{bond_code}-name",
        "counterparty_cif_no": "3000000001",
        "portfolio": "FIOA",
        "as_of_date": as_of_date,
        "business_type": "资产支持证券",
        "business_type_1": "资产支持证券",
        "account_category_std": account_category,
        "cost_center": "5010      ",
        "asset_class_std": asset_class,
        "face_amount": face_amount,
        "fair_value": "99.50",
        "amortized_cost": "98.25",
        "accrued_interest": "1.25",
        "interest_method": "固定",
        "coupon_rate": "0.025",
        "interest_start_date": "2024-01-01",
        "maturity_date": "2029-01-01",
        "credit_customer_id": "ID-001",
        "credit_customer_rating": "AAA",
        "credit_customer_industry": "金融",
        "interest_receivable_payable": "1.25",
        "currency": "CNY",
        "channel": "BANK",
        "legal_customer_id": "LEGAL-001",
        "quantity": "100",
        "latest_face_value": "100",
        "yield_to_maturity": "0.026",
        "option_or_special_maturity_date": "2029-01-01",
    }
    return [values.get(spec.standard_field, "") for spec in service_mod.FIELD_SPECS]


def _pack_sample(file_name: str) -> Path | None:
    pack_dir = _pack_dir()
    if pack_dir is None:
        return None
    sample = pack_dir / "sample_ledgers" / file_name
    return sample if sample.exists() else None


def _pack_dir() -> Path | None:
    candidates: list[Path] = []
    env_dir = os.getenv("MOSS_BANK_LEDGER_PACK_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(
        Path(
            r"C:\Users\arvin\AppData\Local\Temp\bank_ledger_codex_pack_20260427_readonly\bank_ledger_codex_pack"
        )
    )
    for base in candidates:
        if (base / "sample_ledgers").is_dir():
            return base
    return None


def _multipart_body(content: bytes, *, file_name: str) -> tuple[bytes, str]:
    boundary = "ledger-import-test-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
        "Content-Type: application/octet-stream\r\n"
        "\r\n"
    ).encode("ascii") + content + f"\r\n--{boundary}--\r\n".encode("ascii")
    return body, f"multipart/form-data; boundary={boundary}"
