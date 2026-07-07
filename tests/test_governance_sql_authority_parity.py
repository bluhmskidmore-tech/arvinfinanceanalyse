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
    assert sql_repo.read_latest_manifest(
        "demo:key",
        report_date="2026-01-31",
    ) == jsonl_repo.read_latest_manifest(
        "demo:key",
        report_date="2026-01-31",
    )
    assert sql_repo.read_latest_completed_run(
        "demo:key",
        job_name="job-a",
        report_date="2026-01-31",
        require_source_version=True,
    ) == jsonl_repo.read_latest_completed_run(
        "demo:key",
        job_name="job-a",
        report_date="2026-01-31",
        require_source_version=True,
    )


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
