from __future__ import annotations

from collections.abc import Iterable

from backend.app.repositories import governance_repo as governance_module
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)


def _strip_storage_fields(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    storage_fields = {"id", "row_id"}
    return [
        {key: value for key, value in row.items() if key not in storage_fields}
        for row in rows
    ]


def _write_events(
    repo: GovernanceRepository,
    events: Iterable[tuple[str, dict[str, object]]],
) -> None:
    for stream, payload in events:
        repo.append(stream, dict(payload))


def test_sql_authority_read_helpers_match_jsonl_append_order_semantics(tmp_path, monkeypatch):
    monkeypatch.delenv("MOSS_ENVIRONMENT", raising=False)
    monkeypatch.delenv("MOSS_GOVERNANCE_BACKEND", raising=False)
    monkeypatch.delenv("MOSS_GOVERNANCE_SQL_DSN", raising=False)

    shared_created_at = "2026-01-01T00:00:00+00:00"
    events: list[tuple[str, dict[str, object]]] = [
        (
            CACHE_MANIFEST_STREAM,
            {
                "cache_key": "demo:key",
                "cache_version": "cv_first",
                "source_version": "sv_z_first",
                "vendor_version": "vv_first",
                "rule_version": "rv_first",
                "report_date": "2026-01-31",
                "created_at": shared_created_at,
            },
        ),
        (
            CACHE_BUILD_RUN_STREAM,
            {
                "run_id": "run-z-first",
                "job_name": "job-a",
                "status": "completed",
                "cache_key": "demo:key",
                "cache_version": "cv_first",
                "source_version": "sv_z_first",
                "vendor_version": "vv_first",
                "rule_version": "rv_first",
                "report_date": "2026-01-31",
                "created_at": shared_created_at,
            },
        ),
        (
            CACHE_BUILD_RUN_STREAM,
            {
                "run_id": "run-y-running",
                "job_name": "job-a",
                "status": "running",
                "cache_key": "demo:key",
                "source_version": "sv_running",
                "report_date": "2026-01-31",
                "created_at": shared_created_at,
            },
        ),
        (
            CACHE_MANIFEST_STREAM,
            {
                "cache_key": "other:key",
                "source_version": "sv_other",
                "vendor_version": "vv_other",
                "rule_version": "rv_other",
                "report_date": "2026-01-31",
                "created_at": shared_created_at,
            },
        ),
        (
            CACHE_MANIFEST_STREAM,
            {
                "cache_key": "demo:key",
                "cache_version": "cv_latest",
                "source_version": "sv_a_latest",
                "vendor_version": "vv_latest",
                "rule_version": "rv_latest",
                "report_date": "2026-01-31",
                "created_at": shared_created_at,
                "lineage": {"steps": [{"name": "manifest-latest"}]},
                "custom": {"keep": [1, 2, 3]},
            },
        ),
        (
            CACHE_MANIFEST_STREAM,
            {
                "cache_key": "demo:key",
                "source_version": "sv_wrong_date_decoy",
                "report_date": "2026-02-28",
                "created_at": "2099-01-01T00:00:00+00:00",
            },
        ),
        (
            CACHE_BUILD_RUN_STREAM,
            {
                "run_id": "run-a-latest",
                "job_name": "job-a",
                "status": "completed",
                "cache_key": "demo:key",
                "cache_version": "cv_latest",
                "source_version": "sv_a_latest",
                "vendor_version": "vv_latest",
                "rule_version": "rv_latest",
                "report_date": "2026-01-31",
                "created_at": shared_created_at,
                "lineage": {"steps": [{"name": "run-latest"}]},
                "custom": {"keep": [4, 5, 6]},
            },
        ),
        (
            CACHE_BUILD_RUN_STREAM,
            {
                "run_id": "run-empty-source-decoy",
                "job_name": "job-a",
                "status": "completed",
                "cache_key": "demo:key",
                "source_version": " ",
                "report_date": "2026-01-31",
                "created_at": "2099-01-01T00:00:00+00:00",
            },
        ),
    ]

    jsonl_repo = GovernanceRepository(base_dir=tmp_path / "jsonl", backend_mode="jsonl")
    sql_repo = GovernanceRepository(
        base_dir=tmp_path / "sql",
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-authority",
    )
    _write_events(jsonl_repo, events)
    _write_events(sql_repo, events)

    assert _strip_storage_fields(sql_repo.read_all(CACHE_MANIFEST_STREAM)) == _strip_storage_fields(
        jsonl_repo.read_all(CACHE_MANIFEST_STREAM)
    )
    assert _strip_storage_fields(sql_repo.read_all(CACHE_BUILD_RUN_STREAM)) == _strip_storage_fields(
        jsonl_repo.read_all(CACHE_BUILD_RUN_STREAM)
    )
    sql_manifest = sql_repo.read_latest_manifest(
        "demo:key",
        report_date="2026-01-31",
    )
    jsonl_manifest = jsonl_repo.read_latest_manifest(
        "demo:key",
        report_date="2026-01-31",
    )
    sql_completed = sql_repo.read_latest_completed_run(
        "demo:key",
        job_name="job-a",
        report_date="2026-01-31",
        require_source_version=True,
    )
    jsonl_completed = jsonl_repo.read_latest_completed_run(
        "demo:key",
        job_name="job-a",
        report_date="2026-01-31",
        require_source_version=True,
    )
    assert sql_manifest == jsonl_manifest
    assert sql_completed == jsonl_completed
    assert sql_manifest is not None
    assert jsonl_manifest is not None
    assert sql_completed is not None
    assert jsonl_completed is not None

    sql_manifest["lineage"]["steps"][0]["name"] = "mutated"
    jsonl_manifest["custom"]["keep"].append(4)
    sql_completed["lineage"]["steps"][0]["name"] = "mutated"
    jsonl_completed["custom"]["keep"].append(7)

    assert sql_repo.read_latest_manifest("demo:key", report_date="2026-01-31")["lineage"] == {
        "steps": [{"name": "manifest-latest"}]
    }
    assert jsonl_repo.read_latest_manifest("demo:key", report_date="2026-01-31")["custom"] == {
        "keep": [1, 2, 3]
    }
    assert sql_repo.read_latest_completed_run(
        "demo:key",
        job_name="job-a",
        report_date="2026-01-31",
        require_source_version=True,
    )["lineage"] == {"steps": [{"name": "run-latest"}]}
    assert jsonl_repo.read_latest_completed_run(
        "demo:key",
        job_name="job-a",
        report_date="2026-01-31",
        require_source_version=True,
    )["custom"] == {"keep": [4, 5, 6]}


def test_sql_authority_read_all_supported_streams_do_not_take_jsonl_batch_lock(tmp_path, monkeypatch):
    repo = GovernanceRepository(
        base_dir=tmp_path / "sql",
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-authority",
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-sql",
            "job_name": "job-a",
            "status": "completed",
            "cache_key": "demo:key",
        },
    )

    def fail_if_locked(*_args, **_kwargs):
        raise AssertionError("sql-authority read_all should not take JSONL lock")

    monkeypatch.setattr(governance_module, "acquire_lock", fail_if_locked)

    rows = repo.read_all(CACHE_BUILD_RUN_STREAM)

    assert rows[0]["run_id"] == "run-sql"


def test_sql_latest_manifest_uses_descending_row_id_batches_and_stops_at_match(tmp_path, monkeypatch):
    repo = GovernanceRepository(
        base_dir=tmp_path / "sql",
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-authority",
    )
    result_state = {"fetchall_called": False, "fetchmany_called": False, "requested_after_hit": False}
    statements = []
    decoy = {"cache_key": "other:key", "report_date": "2026-01-31"}
    match = {
        "cache_key": " demo:key ",
        "report_date": " 2026-01-31 ",
        "source_version": "sv_match",
        "lineage": {"steps": [{"name": "match"}]},
    }

    class FakeResult:
        delivered = False

        def fetchall(self):
            result_state["fetchall_called"] = True
            raise AssertionError("latest SQL reads must not fetchall")

        def fetchmany(self, _size):
            result_state["fetchmany_called"] = True
            if self.delivered:
                result_state["requested_after_hit"] = True
                return []
            self.delivered = True
            return [
                (governance_module.json.dumps(decoy),),
                (governance_module.json.dumps(match),),
                ("{invalid-json-after-match",),
            ]

    fake_result = FakeResult()

    class FakeConnection:
        def execute(self, statement):
            statements.append(statement)
            return fake_result

    class FakeConnectionContext:
        def __enter__(self):
            return FakeConnection()

        def __exit__(self, _exc_type, _exc, _tb):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConnectionContext()

    monkeypatch.setattr(repo, "_sql_engine", FakeEngine())

    latest = repo.read_latest_manifest("demo:key", report_date="2026-01-31")

    assert latest == match
    assert result_state == {
        "fetchall_called": False,
        "fetchmany_called": True,
        "requested_after_hit": False,
    }
    assert len(statements) == 1
    normalized_sql = " ".join(str(statements[0]).lower().split())
    assert "order by cache_manifest.row_id desc" in normalized_sql
