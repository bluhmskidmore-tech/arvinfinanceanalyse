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
    governance_dir = str(get_settings().governance_path)
    result = run_ledger_import.fn(
        duckdb_path=str(duckdb_path),
        content_base64=base64.b64encode(content).decode("ascii"),
        run_id=run_id,
        governance_dir=governance_dir,
        **kwargs,
    )
    return result


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


def test_ledger_import_run_status_reduces_monotonically_and_whitelists_fields(tmp_path):
    run_mod = import_module("backend.app.services.ledger_import_run_service")
    governance_dir = tmp_path / "governance"
    kwargs = {
        "governance_dir": governance_dir,
        "governance_backend": "jsonl",
        "governance_sql_dsn": "",
        "job_state_dsn": "",
        "run_id": "ledger_import:run-status",
        "file_name": r"C:\\private\\queued.csv",
    }

    run_mod.record_ledger_import_transition(status="queued", **kwargs)
    queued = run_mod.get_ledger_import_run_status(
        governance_dir=governance_dir,
        governance_backend="jsonl",
        governance_sql_dsn="",
        run_id=kwargs["run_id"],
    )
    assert queued == {
        "run_id": "ledger_import:run-status",
        "status": "queued",
        "trigger_mode": "api",
        "file_name": "queued.csv",
        "queued_at": queued["queued_at"],
    }

    run_mod.record_ledger_import_transition(
        status="failed",
        error_category="processing_failed",
        error_message="Ledger import processing failed.",
        **kwargs,
    )
    run_mod.record_ledger_import_transition(status="running", **kwargs)
    retried = run_mod.get_ledger_import_run_status(
        governance_dir=governance_dir,
        governance_backend="jsonl",
        governance_sql_dsn="",
        run_id=kwargs["run_id"],
    )
    assert retried["status"] == "running"
    assert "finished_at" not in retried
    assert "error_message" not in retried
    run_mod.record_ledger_import_transition(
        status="completed",
        outcome="duplicate",
        batch_id=7,
        duplicate_of_batch_id=7,
        **kwargs,
    )
    # A later successful retry upgrades duplicate; subsequent duplicate deliveries cannot downgrade it.
    run_mod.record_ledger_import_transition(
        status="completed",
        outcome="success",
        batch_id=8,
        source_version="sv_ledger_safe",
        rule_version="position_key_contract_v1",
        **kwargs,
    )
    run_mod.record_ledger_import_transition(
        status="completed",
        outcome="duplicate",
        batch_id=8,
        duplicate_of_batch_id=8,
        **kwargs,
    )

    completed = run_mod.get_ledger_import_run_status(
        governance_dir=governance_dir,
        governance_backend="jsonl",
        governance_sql_dsn="",
        run_id=kwargs["run_id"],
    )
    assert completed["status"] == "succeeded"
    assert completed["batch_id"] == 8
    assert "duplicate_of_batch_id" not in completed
    assert completed["file_name"] == "queued.csv"
    assert "source_version" not in completed
    assert "rule_version" not in completed
    assert "error_message" not in completed
    assert set(completed) <= {
        "run_id",
        "status",
        "trigger_mode",
        "file_name",
        "batch_id",
        "duplicate_of_batch_id",
        "queued_at",
        "started_at",
        "finished_at",
        "error_category",
        "error_message",
    }


def test_ledger_import_run_status_duplicate_not_found_and_sql_authority_parity(tmp_path):
    run_mod = import_module("backend.app.services.ledger_import_run_service")
    run_id = "ledger_import:parity"
    jsonl_dir = tmp_path / "jsonl"
    sql_dir = tmp_path / "sql"
    sql_dsn = f"sqlite:///{(tmp_path / 'governance.db').as_posix()}"
    transition = {
        "run_id": run_id,
        "status": "completed",
        "outcome": "duplicate",
        "file_name": "../duplicate.csv",
        "batch_id": 3,
        "duplicate_of_batch_id": 2,
    }
    run_mod.record_ledger_import_transition(
        governance_dir=jsonl_dir,
        governance_backend="jsonl",
        governance_sql_dsn="",
        job_state_dsn="",
        **transition,
    )
    run_mod.record_ledger_import_transition(
        governance_dir=sql_dir,
        governance_backend="sql-authority",
        governance_sql_dsn=sql_dsn,
        job_state_dsn="",
        **transition,
    )

    jsonl_status = run_mod.get_ledger_import_run_status(
        governance_dir=jsonl_dir,
        governance_backend="jsonl",
        governance_sql_dsn="",
        run_id=run_id,
    )
    sql_status = run_mod.get_ledger_import_run_status(
        governance_dir=sql_dir,
        governance_backend="sql-authority",
        governance_sql_dsn=sql_dsn,
        run_id=run_id,
    )
    for payload in (jsonl_status, sql_status):
        payload.pop("finished_at")
    assert sql_status == jsonl_status == {
        "run_id": run_id,
        "status": "duplicate",
        "trigger_mode": "api",
        "file_name": "duplicate.csv",
        "batch_id": 3,
        "duplicate_of_batch_id": 2,
    }

    with pytest.raises(run_mod.LedgerImportRunNotFoundError):
        run_mod.get_ledger_import_run_status(
            governance_dir=jsonl_dir,
            governance_backend="jsonl",
            governance_sql_dsn="",
            run_id="ledger_import:missing",
        )


def test_ledger_import_terminal_outbox_is_private_durable_and_whitelisted(tmp_path):
    run_mod = import_module("backend.app.services.ledger_import_run_service")
    run_mod.record_ledger_import_terminal_outbox(
        governance_dir=tmp_path / "governance",
        run_id="ledger_import:outbox",
        file_name=r"C:\\private\\safe.csv",
        status="completed",
        outcome="success",
        batch_id=9,
        duplicate_of_batch_id=None,
        source_version="sv_safe",
        rule_version="rv_safe",
        error_category=None,
        error_message=None,
    )
    for status, outcome in (("completed", "duplicate"), ("failed", None)):
        run_mod.record_ledger_import_terminal_outbox(
            governance_dir=tmp_path / "governance",
            run_id="ledger_import:outbox",
            file_name="redelivery.csv",
            status=status,
            outcome=outcome,
            batch_id=9,
            duplicate_of_batch_id=9 if outcome == "duplicate" else None,
            source_version="sv_safe",
            rule_version="rv_safe",
            error_category="processing_failed" if status == "failed" else None,
            error_message="Ledger import processing failed." if status == "failed" else None,
        )

    facts = run_mod.get_ledger_import_terminal_outbox(
        governance_dir=tmp_path / "governance",
        run_id="ledger_import:outbox",
    )
    assert facts["file_name"] == "safe.csv"
    assert facts["status"] == "completed"
    assert facts["outcome"] == "success"
    serialized = json.dumps(facts)
    assert "private" not in serialized
    assert "content_base64" not in serialized
    assert "duckdb_path" not in serialized
    assert "dsn" not in serialized.lower()


def test_ledger_import_run_transition_job_state_failure_is_best_effort(tmp_path, monkeypatch, caplog):
    run_mod = import_module("backend.app.services.ledger_import_run_service")

    class FailingJobStateRepository:
        def __init__(self, _dsn):
            pass

        def record_transition(self, **_kwargs):
            raise RuntimeError("secret mirror failure")

    monkeypatch.setattr(run_mod, "JobStateRepository", FailingJobStateRepository)
    run_mod.record_ledger_import_transition(
        governance_dir=tmp_path / "governance",
        governance_backend="jsonl",
        governance_sql_dsn="",
        job_state_dsn="sqlite:///unused.db",
        run_id="ledger_import:mirror-failure",
        status="queued",
        file_name="safe.csv",
    )

    assert "mirror failed" in caplog.text.lower()
    assert "secret mirror failure" not in caplog.text
    assert run_mod.get_ledger_import_run_status(
        governance_dir=tmp_path / "governance",
        governance_backend="jsonl",
        governance_sql_dsn="",
        run_id="ledger_import:mirror-failure",
    )["status"] == "queued"


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
    status_seen_at_send: list[str] = []

    def capture_send(**kwargs):
        status_seen_at_send.append(_get_run_status(str(kwargs["run_id"]))["status"])
        sent.update(kwargs)

    monkeypatch.setattr(run_ledger_import, "send", capture_send)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post(
        "/api/ledger/import",
        files={"file": (r"C:\\private\\ZQTZSHOW-20260317.csv", content, "text/csv")},
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
    assert sent["governance_dir"] == str(get_settings().governance_path)
    assert status_seen_at_send == ["queued"]
    assert {"governance_sql_dsn", "job_state_dsn"}.isdisjoint(sent)
    assert base64.b64decode(str(sent["content_base64"]), validate=True) == content
    json.dumps(sent)
    assert not any(isinstance(value, bytes) for value in sent.values())
    assert _get_run_status(str(sent["run_id"]))["status"] == "queued"

    listed = client.get("/api/ledger/imports").json()
    assert listed["data"]["items"] == []
    assert listed["data"]["total"] == 0
    get_settings.cache_clear()


def test_ledger_import_api_preserves_trailing_newlines_in_uploaded_file(tmp_path, monkeypatch):
    """multipart 解析只允许剥离协议分隔用的单个 CRLF；CSV 自身的结尾换行必须原样入队。"""
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks.ledger_import import run_ledger_import

    sent: list[dict[str, object]] = []
    monkeypatch.setattr(run_ledger_import, "send", lambda **kwargs: sent.append(kwargs))
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cases = (
        b"h1,h2\r\nv1,v2\r\n",  # Windows CSV：单个结尾 CRLF
        b"h1,h2\nv1,v2\n",  # Unix CSV：单个结尾 LF
        b"h1,h2\nv1,v2\n\r\n\r\n",  # 末尾多个空行也属于文件内容
    )
    for content in cases:
        body, content_type = _multipart_body(content, file_name="ZQTZSHOW-20260317.csv")
        response = client.post(
            "/api/ledger/import",
            content=body,
            headers={"content-type": content_type},
        )
        assert response.status_code == 202, f"{content!r}: {response.status_code} {response.text}"
        queued = base64.b64decode(str(sent.pop()["content_base64"]), validate=True)
        assert queued == content, f"payload truncated: sent {content!r}, queued {queued!r}"
    assert sent == []
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
    assert payload["data"]["rule_version"] == "rv_ledger_classification_v2"
    assert payload["metadata"]["no_data"] is False
    assert payload["trace"]["source_file_hash"] == payload["data"]["file_hash"]
    assert payload["data"]["run_id"] == "ledger_import:actor-success"
    assert payload["trace"]["run_id"] == "ledger_import:actor-success"
    actor_status = _get_run_status("ledger_import:actor-success")
    assert actor_status["status"] == "succeeded"
    assert actor_status["batch_id"] == 1

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


@pytest.mark.parametrize(
    ("account_category", "asset_class", "expected"),
    [
        ("发行类债券", "发行类债券", "LIABILITY"),
        ("银行账户", "持有至到期类资产", "ASSET"),
        ("银行账户", "可供出售类资产", "ASSET"),
        ("银行账户", "交易性资产", "ASSET"),
        ("交易账户", "交易性资产", "ASSET"),
        ("银行账户", "应收投资款项", "ASSET"),
        ("发行类债券", "交易性资产", "UNCLASSIFIED"),
        ("银行账户", "未知分类", "UNCLASSIFIED"),
        ("__NULL__", "__NULL__", "UNCLASSIFIED"),
    ],
)
def test_ledger_classification_v2_is_a_closed_pair_allowlist(
    account_category,
    asset_class,
    expected,
):
    classification = load_module(
        "backend.app.governance.ledger_classification",
        "backend/app/governance/ledger_classification.py",
    )

    assert classification.LEDGER_CLASSIFICATION_RULE_VERSION == "rv_ledger_classification_v2"
    assert classification.classify_ledger_direction(account_category, asset_class) == expected


def test_ledger_import_materializes_unclassified_with_row_lineage(tmp_path, monkeypatch):
    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    payload = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317-unclassified.csv",
        content=_ledger_csv_bytes(
            service_mod,
            [
                _ledger_row_values(
                    service_mod,
                    bond_code="UNKNOWN-001",
                    account_category="银行账户",
                    asset_class="未知分类",
                    face_amount="100.25",
                    as_of_date="2026-03-17",
                )
            ],
            unknown_value="unclassified-lineage-marker",
        ),
    )

    assert payload["data"]["rule_version"] == "rv_ledger_classification_v2"
    assert payload["data"]["error_count"] == 0
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select s.batch_id, s.row_no, s.position_key, s.direction,
                   s.account_category_std, s.asset_class_std, r.raw_json,
                   s.source_version, s.rule_version
            from position_snapshot s
            join ledger_raw_row r using (batch_id, row_no)
            """
        ).fetchone()
    finally:
        conn.close()

    assert row[:2] == (1, 1)
    assert row[2]
    assert row[3:6] == ("UNCLASSIFIED", "银行账户", "未知分类")
    assert "unclassified-lineage-marker" in row[6]
    assert row[7] == payload["data"]["source_version"]
    assert row[8] == "rv_ledger_classification_v2"

def test_ledger_import_actor_rejects_invalid_base64_before_service_call(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod

    called = False

    class UnexpectedService:
        def __init__(self, duckdb_path: str) -> None:
            nonlocal called
            called = True

    monkeypatch.setattr(task_mod, "LedgerImportService", UnexpectedService)

    result = task_mod.run_ledger_import.fn(
        file_name="ZQTZSHOW-20260317.csv",
        content_base64="not-base64!",
        duckdb_path="unused.duckdb",
        run_id="ledger_import:invalid",
        governance_dir=str(get_settings().governance_path),
    )
    task_mod.reconcile_ledger_import_terminal.fn(
        run_id="ledger_import:invalid",
        governance_dir=str(get_settings().governance_path),
    )

    assert called is False
    assert result["data"]["status"] == "failed"
    assert _get_run_status("ledger_import:invalid") == {
        "run_id": "ledger_import:invalid",
        "status": "failed",
        "trigger_mode": "api",
        "file_name": "ZQTZSHOW-20260317.csv",
        "started_at": _get_run_status("ledger_import:invalid")["started_at"],
        "finished_at": _get_run_status("ledger_import:invalid")["finished_at"],
        "error_category": "invalid_file",
        "error_message": "Ledger import file is invalid.",
    }


def test_ledger_import_actor_rejects_oversize_base64_before_decode(monkeypatch):
    from backend.app.tasks import ledger_import as task_mod

    monkeypatch.setattr(
        task_mod.base64,
        "b64decode",
        lambda *args, **kwargs: pytest.fail("oversize payload reached base64 decode"),
    )
    maximum_base64_chars = 4 * ((EXPECTED_MAX_LEDGER_IMPORT_BYTES + 2) // 3)

    result = task_mod.run_ledger_import.fn(
        file_name="ZQTZSHOW-20260317.csv",
        content_base64="A" * (maximum_base64_chars + 4),
        duckdb_path="unused.duckdb",
        run_id="ledger_import:oversize-encoded",
    )
    assert result["data"]["status"] == "failed"


def test_ledger_import_actor_rejects_oversize_decoded_bytes_before_service(monkeypatch):
    from backend.app.tasks import ledger_import as task_mod

    called = False

    class UnexpectedService:
        def __init__(self, duckdb_path: str) -> None:
            nonlocal called
            called = True

    monkeypatch.setattr(task_mod, "LedgerImportService", UnexpectedService)
    content_base64 = base64.b64encode(b"x" * (EXPECTED_MAX_LEDGER_IMPORT_BYTES + 1)).decode("ascii")

    result = task_mod.run_ledger_import.fn(
        file_name="ZQTZSHOW-20260317.csv",
        content_base64=content_base64,
        duckdb_path="unused.duckdb",
        run_id="ledger_import:oversize-decoded",
    )

    assert called is False
    assert result["data"]["status"] == "failed"


def test_ledger_import_corrupt_xlsx_exhaustion_writes_safe_failed_terminal(
    tmp_path, monkeypatch, caplog
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod

    run_id = "ledger_import:corrupt-xlsx"
    governance_dir = str(get_settings().governance_path)
    corrupt_content = b"PK-not-a-real-xlsx raw=private"
    result = task_mod.run_ledger_import.fn(
        file_name=r"C:\\private\\corrupt.xlsx",
        content_base64=base64.b64encode(corrupt_content).decode("ascii"),
        duckdb_path="C:/private.duckdb",
        run_id=run_id,
        governance_dir=governance_dir,
        retry_attempt=task_mod.MAX_LEDGER_IMPORT_MANUAL_RETRIES,
    )

    assert result["data"]["status"] == "failed"
    task_mod.reconcile_ledger_import_terminal.fn(
        run_id=run_id,
        governance_dir=governance_dir,
    )
    failed = _get_run_status(run_id)
    assert failed["status"] == "failed"
    assert failed["error_category"] == "processing_failed"
    assert failed["error_message"] == "Ledger import processing failed."
    assert "raw=private" not in caplog.text
    assert "private.duckdb" not in caplog.text
    assert "corrupt.xlsx" not in caplog.text


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
        from backend.app.tasks import ledger_import as task_mod

        result = _scoped_import(
            service_mod,
            duckdb_path,
            file_name="ZQTZSHOW-20260317.csv",
            content=csv_bytes,
            run_id="ledger_import:rollback",
            retry_attempt=task_mod.MAX_LEDGER_IMPORT_MANUAL_RETRIES,
        )
        assert result["data"]["status"] == "failed"

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        assert conn.execute("select count(*) from ledger_import_batch").fetchone()[0] == 0
        assert conn.execute("select count(*) from ledger_raw_row").fetchone()[0] == 0
        assert conn.execute("select count(*) from position_snapshot").fetchone()[0] == 0
    finally:
        conn.close()
    task_mod.reconcile_ledger_import_terminal.fn(
        run_id="ledger_import:rollback",
        governance_dir=str(get_settings().governance_path),
    )
    failed_status = _get_run_status("ledger_import:rollback")
    assert failed_status["status"] == "failed"
    assert failed_status["error_category"] == "processing_failed"


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


def test_ledger_import_queue_failure_returns_structured_503(tmp_path, monkeypatch, caplog):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks.ledger_import import run_ledger_import

    def fail_send(**kwargs):
        raise RuntimeError("queue unavailable dsn=secret raw=private")

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
        "message": "Ledger import queue dispatch failed.",
        "retryable": True,
    }
    assert payload["trace"]["request_id"].startswith("req_ledger_")
    run_id = _only_ledger_run_id()
    status = _get_run_status(run_id)
    assert status["status"] == "failed"
    assert status["error_category"] == "dispatch_failed"
    assert status["error_message"] == "Ledger import queue dispatch failed."
    assert "queue unavailable" not in json.dumps(payload)
    assert "dsn=secret" not in caplog.text
    assert "raw=private" not in caplog.text


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
        "message": "Ledger import queue dispatch failed.",
        "retryable": True,
    }
    assert response.json()["trace"]["request_id"].startswith("req_ledger_")


def test_ledger_import_queued_governance_failure_does_not_dispatch(tmp_path, monkeypatch, caplog):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    route_mod = import_module("backend.app.api.routes.ledger")
    run_mod = import_module("backend.app.services.ledger_import_run_service")
    sent: list[dict[str, object]] = []
    monkeypatch.setattr(route_mod._import_task().run_ledger_import, "send", lambda **kwargs: sent.append(kwargs))
    monkeypatch.setattr(
        run_mod,
        "record_ledger_import_transition",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("dsn=secret")),
    )

    response = TestClient(load_module("backend.app.main", "backend/app/main.py").app).post(
        "/api/ledger/import",
        files={"file": ("safe.csv", b"non-empty", "text/csv")},
    )

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Ledger import status is unavailable."
    assert "secret" not in response.text
    assert "dsn=secret" not in caplog.text
    assert sent == []


def test_ledger_import_status_endpoint_contract_and_validation(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    run_mod = import_module("backend.app.services.ledger_import_run_service")
    run_mod.record_ledger_import_transition(
        governance_dir=get_settings().governance_path,
        governance_backend=get_settings().governance_backend,
        governance_sql_dsn=get_settings().governance_sql_dsn,
        job_state_dsn="",
        run_id="ledger_import:status-api",
        status="failed",
        file_name=r"C:\\sensitive\\bad.csv",
        error_category="processing_failed",
        error_message="Ledger import processing failed.",
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/ledger/import-status", params={"run_id": "ledger_import:status-api"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "failed"
    assert payload["data"]["file_name"] == "bad.csv"
    assert payload["trace"]["run_id"] == "ledger_import:status-api"
    assert "sensitive" not in response.text

    missing = client.get("/api/ledger/import-status")
    blank = client.get("/api/ledger/import-status", params={"run_id": " "})
    extra = client.get("/api/ledger/import-status", params={"run_id": "x", "extra": "y"})
    unknown = client.get("/api/ledger/import-status", params={"run_id": "ledger_import:missing"})
    assert {missing.status_code, blank.status_code, extra.status_code} == {400}
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "LEDGER_IMPORT_RUN_NOT_FOUND"


def test_ledger_import_status_governance_read_failure_is_safe_503(tmp_path, monkeypatch):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    run_mod = import_module("backend.app.services.ledger_import_run_service")
    monkeypatch.setattr(
        run_mod,
        "get_ledger_import_run_status",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("postgresql://secret/path")),
    )

    response = TestClient(load_module("backend.app.main", "backend/app/main.py").app).get(
        "/api/ledger/import-status",
        params={"run_id": "ledger_import:any"},
    )

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "LEDGER_IMPORT_STATUS_UNAVAILABLE",
        "message": "Ledger import status is unavailable.",
        "retryable": True,
    }
    assert "secret" not in response.text


def test_ledger_import_actor_running_transition_failure_prevents_import(monkeypatch):
    from backend.app.tasks import ledger_import as task_mod

    called = False

    class UnexpectedService:
        def __init__(self, _duckdb_path):
            nonlocal called
            called = True

    monkeypatch.setattr(task_mod, "LedgerImportService", UnexpectedService)
    monkeypatch.setattr(
        task_mod,
        "record_ledger_import_transition",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("governance unavailable")),
    )

    result = task_mod.run_ledger_import.fn(
        file_name="safe.csv",
        content_base64=base64.b64encode(b"content").decode("ascii"),
        duckdb_path="unused.duckdb",
        run_id="ledger_import:running-failed",
        governance_dir="unused-governance",
        retry_attempt=task_mod.MAX_LEDGER_IMPORT_MANUAL_RETRIES,
    )
    assert result["data"]["status"] == "failed"
    assert called is False


@pytest.mark.parametrize(
    ("data_status", "duplicate_of_batch_id", "expected_public_status"),
    [("success", None, "succeeded"), ("duplicate", 11, "duplicate")],
)
def test_ledger_import_terminal_append_failure_reconciles_without_reimport(
    tmp_path,
    monkeypatch,
    data_status,
    duplicate_of_batch_id,
    expected_public_status,
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod

    calls = 0

    class CountingService:
        def __init__(self, _duckdb_path):
            pass

        def import_file(self, **_kwargs):
            nonlocal calls
            calls += 1
            return {
                "data": {
                    "status": data_status,
                    "batch_id": 12,
                    "source_version": "sv_ledger_test",
                    "rule_version": "position_key_contract_v1",
                },
                "trace": {"duplicate_of_batch_id": duplicate_of_batch_id},
            }

    queued_reconciliation: dict[str, object] = {}
    real_record = task_mod.record_ledger_import_transition
    failed_once = False

    def fail_primary_once(**kwargs):
        nonlocal failed_once
        if kwargs["status"] == "completed" and not failed_once:
            failed_once = True
            raise RuntimeError("primary dsn=secret")
        return real_record(**kwargs)

    monkeypatch.setattr(task_mod, "LedgerImportService", CountingService)
    monkeypatch.setattr(task_mod, "record_ledger_import_transition", fail_primary_once)
    monkeypatch.setattr(
        task_mod.reconcile_ledger_import_terminal,
        "send",
        lambda **kwargs: queued_reconciliation.update(kwargs),
    )

    payload = task_mod.run_ledger_import.fn(
        file_name="safe.csv",
        content_base64=base64.b64encode(b"content").decode("ascii"),
        duckdb_path="ledger-secret.duckdb",
        run_id="ledger_import:terminal-reconcile",
        governance_dir=str(get_settings().governance_path),
    )
    assert payload["data"]["status"] == data_status
    assert calls == 1
    assert {"duckdb_path", "content_base64", "governance_sql_dsn", "job_state_dsn"}.isdisjoint(
        queued_reconciliation
    )
    serialized_reconciliation = json.dumps(queued_reconciliation)
    assert "ledger-secret.duckdb" not in serialized_reconciliation
    assert "content_base64" not in serialized_reconciliation
    assert "traceback" not in serialized_reconciliation

    task_mod.reconcile_ledger_import_terminal.fn(**queued_reconciliation)
    assert calls == 1
    assert _get_run_status("ledger_import:terminal-reconcile")["status"] == expected_public_status


def test_ledger_import_actor_manual_retry_message_is_safe_and_exhaustion_reconciles(
    tmp_path, monkeypatch
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod

    assert task_mod.run_ledger_import.options["max_retries"] == 0
    assert "throws" not in task_mod.run_ledger_import.options
    assert "on_retry_exhausted" not in task_mod.run_ledger_import.options

    class FailingService:
        def __init__(self, _duckdb_path):
            pass

        def import_file(self, **_kwargs):
            raise RuntimeError("duckdb=secret.duckdb raw=private")

    monkeypatch.setattr(task_mod, "LedgerImportService", FailingService)
    kwargs = {
        "file_name": "safe.csv",
        "content_base64": base64.b64encode(b"raw=private").decode("ascii"),
        "duckdb_path": "secret.duckdb",
        "run_id": "ledger_import:retry-exhausted",
        "governance_dir": str(get_settings().governance_path),
    }
    queued: dict[str, object] = {}
    monkeypatch.setattr(
        task_mod.run_ledger_import,
        "send_with_options",
        lambda **options: queued.update(options),
    )
    result = task_mod.run_ledger_import.fn(**kwargs)
    assert result["data"]["status"] == "retrying"
    assert _get_run_status(kwargs["run_id"])["status"] == "running"
    assert set(queued) == {"kwargs", "delay"}
    assert {"traceback", "on_retry_exhausted", "governance_sql_dsn", "job_state_dsn"}.isdisjoint(
        queued["kwargs"]
    )
    assert queued["kwargs"]["retry_attempt"] == 1

    terminal = task_mod.run_ledger_import.fn(
        **{**kwargs, "retry_attempt": task_mod.MAX_LEDGER_IMPORT_MANUAL_RETRIES}
    )
    assert terminal["data"]["status"] == "failed"
    task_mod.reconcile_ledger_import_terminal.fn(
        run_id=kwargs["run_id"],
        governance_dir=kwargs["governance_dir"],
    )
    failed = _get_run_status(kwargs["run_id"])
    assert failed["status"] == "failed"
    assert failed["error_category"] == "processing_failed"
    assert failed["error_message"] == "Ledger import processing failed."


def test_ledger_import_terminal_reconciliation_enqueue_failure_does_not_reimport_or_leak(
    tmp_path, monkeypatch, caplog
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod

    calls = 0

    class SuccessfulService:
        def __init__(self, _duckdb_path):
            pass

        def import_file(self, **_kwargs):
            nonlocal calls
            calls += 1
            return {
                "data": {
                    "status": "success",
                    "batch_id": 1,
                    "source_version": "sv_safe",
                    "rule_version": "rv_safe",
                },
                "trace": {"duplicate_of_batch_id": None},
            }

    monkeypatch.setattr(task_mod, "LedgerImportService", SuccessfulService)
    real_record = task_mod.record_ledger_import_transition
    primary_failed = False

    def fail_primary_once(**kwargs):
        nonlocal primary_failed
        if kwargs["status"] == "completed" and not primary_failed:
            primary_failed = True
            raise RuntimeError("primary dsn=secret")
        return real_record(**kwargs)

    monkeypatch.setattr(task_mod, "record_ledger_import_transition", fail_primary_once)
    monkeypatch.setattr(
        task_mod.reconcile_ledger_import_terminal,
        "send",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("broker raw=private")),
    )

    payload = task_mod.run_ledger_import.fn(
        file_name="safe.csv",
        content_base64=base64.b64encode(b"content").decode("ascii"),
        duckdb_path="C:/private.duckdb",
        run_id="ledger_import:terminal-enqueue-failed",
        governance_dir=str(get_settings().governance_path),
    )

    assert payload["data"]["status"] == "terminal_pending"
    assert calls == 1
    assert _get_run_status("ledger_import:terminal-enqueue-failed")["status"] == "running"
    assert "dsn=secret" not in caplog.text
    assert "raw=private" not in caplog.text
    assert "private.duckdb" not in caplog.text
    task_mod.reconcile_ledger_import_terminal.fn(
        run_id="ledger_import:terminal-enqueue-failed",
        governance_dir=str(get_settings().governance_path),
    )
    assert _get_run_status("ledger_import:terminal-enqueue-failed")["status"] == "succeeded"


def test_ledger_import_reconcile_exhaustion_spools_safe_facts_or_reports_delivery_failure(
    tmp_path, monkeypatch, caplog
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod
    run_mod = import_module("backend.app.services.ledger_import_run_service")

    monkeypatch.setattr(
        task_mod,
        "record_ledger_import_transition",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("primary dsn=secret")),
    )
    facts = {
        "run_id": "ledger_import:reconcile-exhausted",
        "governance_dir": str(get_settings().governance_path),
        "retry_attempt": task_mod.MAX_LEDGER_IMPORT_MANUAL_RETRIES,
        "file_name": "safe.csv",
        "status": "completed",
        "outcome": "success",
        "batch_id": 8,
        "duplicate_of_batch_id": None,
        "source_version": "sv_safe",
        "rule_version": "rv_safe",
        "error_category": None,
        "error_message": None,
        "finished_at": "2026-07-11T00:00:00+00:00",
    }
    pending = task_mod.reconcile_ledger_import_terminal.fn(**facts)
    assert pending["data"]["status"] == "pending_reconciliation"
    spooled = run_mod.get_ledger_import_terminal_outbox(
        governance_dir=facts["governance_dir"],
        governance_backend=get_settings().governance_backend,
        governance_sql_dsn=get_settings().governance_sql_dsn,
        run_id=facts["run_id"],
    )
    assert spooled["outcome"] == "success"
    assert "dsn=secret" not in caplog.text

    monkeypatch.setattr(
        task_mod,
        "record_ledger_import_terminal_outbox",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("spool raw=private")),
    )
    failed_facts = {**facts, "run_id": "ledger_import:reconcile-delivery-failed"}
    delivery_failed = task_mod.reconcile_ledger_import_terminal.fn(**failed_facts)
    assert delivery_failed["data"]["status"] == "delivery_failed"
    assert "raw=private" not in caplog.text


def test_ledger_import_terminal_delivery_total_failure_is_explicit_and_observable(
    tmp_path, monkeypatch, caplog
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod

    class SuccessfulService:
        def __init__(self, _duckdb_path):
            pass

        def import_file(self, **_kwargs):
            return {
                "data": {
                    "status": "success",
                    "batch_id": 5,
                    "source_version": "sv_safe",
                    "rule_version": "rv_safe",
                },
                "trace": {"duplicate_of_batch_id": None},
            }

    real_record = task_mod.record_ledger_import_transition

    def fail_terminal_primary(**kwargs):
        if kwargs["status"] == "completed":
            raise RuntimeError("primary dsn=secret")
        return real_record(**kwargs)

    monkeypatch.setattr(task_mod, "LedgerImportService", SuccessfulService)
    monkeypatch.setattr(task_mod, "record_ledger_import_transition", fail_terminal_primary)
    monkeypatch.setattr(
        task_mod.reconcile_ledger_import_terminal,
        "send",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("broker path=C:/private")),
    )
    monkeypatch.setattr(
        task_mod,
        "record_ledger_import_terminal_outbox",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("spool raw=private")),
    )

    result = task_mod.run_ledger_import.fn(
        file_name="safe.csv",
        content_base64=base64.b64encode(b"content").decode("ascii"),
        duckdb_path="C:/private.duckdb",
        run_id="ledger_import:delivery-failed",
        governance_dir=str(get_settings().governance_path),
    )

    assert result["data"]["status"] == "delivery_failed"
    event = "event=ledger_import_terminal_delivery_failed"
    assert caplog.text.count(event) == 1
    assert "dsn=secret" not in caplog.text
    assert "C:/private" not in caplog.text
    assert "raw=private" not in caplog.text


def test_ledger_import_sensitive_failures_do_not_leak_to_logs_or_status(tmp_path, monkeypatch, caplog):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod

    class SensitiveFailureService:
        def __init__(self, _duckdb_path):
            pass

        def import_file(self, **_kwargs):
            raise RuntimeError("dsn=secret path=C:/private.duckdb raw=private")

    monkeypatch.setattr(task_mod, "LedgerImportService", SensitiveFailureService)
    monkeypatch.setattr(task_mod.run_ledger_import, "send_with_options", lambda **_kwargs: None)
    result = task_mod.run_ledger_import.fn(
        file_name="safe.csv",
        content_base64=base64.b64encode(b"raw=private").decode("ascii"),
        duckdb_path="C:/private.duckdb",
        run_id="ledger_import:safe-log",
        governance_dir=str(get_settings().governance_path),
    )
    assert result["data"]["status"] == "retrying"

    assert "dsn=secret" not in caplog.text
    assert "private.duckdb" not in caplog.text
    assert "raw=private" not in caplog.text


def test_ledger_import_invalid_file_outbox_retries_synchronously_then_reconciles(
    tmp_path, monkeypatch, caplog
):
    _configure_ledger_import_env(tmp_path, monkeypatch)
    from backend.app.tasks import ledger_import as task_mod

    real_outbox = task_mod.record_ledger_import_terminal_outbox
    attempts = 0

    def flaky_outbox(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("dsn=secret raw=private")
        return real_outbox(**kwargs)

    service_called = False

    class UnexpectedService:
        def __init__(self, _duckdb_path):
            nonlocal service_called
            service_called = True

    monkeypatch.setattr(task_mod, "record_ledger_import_terminal_outbox", flaky_outbox)
    monkeypatch.setattr(task_mod, "LedgerImportService", UnexpectedService)
    real_record = task_mod.record_ledger_import_transition
    fail_primary = True

    def flaky_primary(**transition_kwargs):
        if transition_kwargs["status"] == "failed" and fail_primary:
            raise RuntimeError("primary dsn=secret")
        return real_record(**transition_kwargs)

    monkeypatch.setattr(task_mod, "record_ledger_import_transition", flaky_primary)
    monkeypatch.setattr(
        task_mod.reconcile_ledger_import_terminal,
        "send",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("broker raw=private")),
    )
    kwargs = {
        "file_name": "invalid.csv",
        "content_base64": "not-base64!",
        "duckdb_path": "C:/private.duckdb",
        "run_id": "ledger_import:status-retry",
        "governance_dir": str(get_settings().governance_path),
    }

    result = task_mod.run_ledger_import.fn(**kwargs)
    assert result["data"]["status"] == "terminal_pending"
    assert attempts == 3
    assert "dsn=secret" not in caplog.text
    assert "raw=private" not in caplog.text
    assert _get_run_status(kwargs["run_id"])["status"] == "running"
    assert service_called is False
    fail_primary = False
    task_mod.reconcile_ledger_import_terminal.fn(
        run_id=kwargs["run_id"],
        governance_dir=kwargs["governance_dir"],
    )
    status = _get_run_status(kwargs["run_id"])
    assert status["status"] == "failed"
    assert status["error_category"] == "invalid_file"
    assert service_called is False


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
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update ledger_import_batch set rule_version = 'position_key_contract_v1'"
        )
    finally:
        conn.close()

    duplicate_payload = _scoped_import(
        service_mod,
        duckdb_path,
        file_name="ZQTZSHOW-20260317-copy.csv",
        content=csv_bytes,
        run_id="ledger_import:duplicate",
    )

    assert duplicate_payload["error"]["code"] == "LEDGER_IMPORT_DUPLICATE"
    assert duplicate_payload["data"]["status"] == "duplicate"
    assert duplicate_payload["data"]["rule_version"] == "position_key_contract_v1"
    assert duplicate_payload["metadata"]["rule_version"] == "position_key_contract_v1"
    listed = service_mod.LedgerImportService(str(duckdb_path)).list_imports()
    assert listed["data"]["items"][0]["rule_version"] == "position_key_contract_v1"
    assert listed["metadata"]["rule_version"] == "position_key_contract_v1"
    assert duplicate_payload["data"]["run_id"] == "ledger_import:duplicate"
    assert duplicate_payload["trace"]["run_id"] == "ledger_import:duplicate"
    assert duplicate_payload["trace"]["duplicate_of_batch_id"] == first["data"]["batch_id"]
    duplicate_status = _get_run_status("ledger_import:duplicate")
    assert duplicate_status["status"] == "duplicate"
    assert duplicate_status["duplicate_of_batch_id"] == first["data"]["batch_id"]

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


def _get_run_status(run_id: str) -> dict[str, object]:
    run_mod = import_module("backend.app.services.ledger_import_run_service")
    settings = get_settings()
    return run_mod.get_ledger_import_run_status(
        governance_dir=settings.governance_path,
        governance_backend=settings.governance_backend,
        governance_sql_dsn=settings.governance_sql_dsn,
        run_id=run_id,
    )


def _only_ledger_run_id() -> str:
    from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository

    settings = get_settings()
    rows = GovernanceRepository(
        base_dir=settings.governance_path,
        sql_dsn=settings.governance_sql_dsn,
        backend_mode=settings.governance_backend,
    ).read_all(CACHE_BUILD_RUN_STREAM)
    run_ids = {str(row["run_id"]) for row in rows if row.get("job_name") == "ledger_import"}
    assert len(run_ids) == 1
    return run_ids.pop()


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


def test_ledger_import_repo_acquires_lock_before_opening_write_connection(tmp_path, monkeypatch):
    """insert_import 必须先持 LEDGER_IMPORT_LOCK，再打开写连接（B5 审计修复）。"""
    from contextlib import contextmanager

    import backend.app.repositories.ledger_import_repo as repo_module
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    events: list[str] = []
    real_acquire_lock = repo_module.acquire_lock
    real_connect = duckdb.connect

    @contextmanager
    def recording_acquire_lock(definition, *args, **kwargs):
        events.append(f"lock_enter:{definition.key}")
        with real_acquire_lock(definition, *args, **kwargs) as handle:
            try:
                yield handle
            finally:
                events.append(f"lock_exit:{definition.key}")

    class _RecordingConn:
        def __init__(self, inner) -> None:
            self._inner = inner

        def close(self) -> None:
            events.append("connection_closed")
            self._inner.close()

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

    def recording_connect(*args, **kwargs):
        events.append("connection_opened")
        return _RecordingConn(real_connect(*args, **kwargs))

    monkeypatch.setattr(repo_module, "acquire_lock", recording_acquire_lock)
    monkeypatch.setattr(repo_module.duckdb, "connect", recording_connect)

    db_path = tmp_path / "ledger-lock-order.duckdb"
    with repository_task_write_scope("backend.app.tasks.test_ledger_lock_order"):
        summary = repo_module.LedgerImportRepository(str(db_path)).insert_import(
            file_name="lock-order.csv",
            file_hash="hash-lock-order",
            as_of_date="2026-01-31",
            rows=[{"row_no": 2, "raw_json": "{}"}],
            source_version="sv_test",
            rule_version="rv_test",
        )

    assert summary["status"] == "success"
    lock_key = repo_module.LEDGER_IMPORT_LOCK.key
    assert events == [
        f"lock_enter:{lock_key}",
        "connection_opened",
        "connection_closed",
        f"lock_exit:{lock_key}",
    ]
