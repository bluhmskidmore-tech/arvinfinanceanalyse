from __future__ import annotations

from collections.abc import Iterable

import pytest

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
            CACHE_BUILD_RUN_STREAM,
            {
                "run_id": "run-whitespace-decoy",
                "job_name": "job-a",
                "status": "completed",
                "cache_key": " demo:key ",
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
    sql_selected_runs = sql_repo.read_by_cache_keys(
        CACHE_BUILD_RUN_STREAM,
        ["demo:key"],
    )
    jsonl_selected_runs = jsonl_repo.read_by_cache_keys(
        CACHE_BUILD_RUN_STREAM,
        ["demo:key"],
    )
    assert _strip_storage_fields(sql_selected_runs) == _strip_storage_fields(
        jsonl_selected_runs
    )
    assert [row["run_id"] for row in sql_selected_runs] == [
        "run-z-first",
        "run-y-running",
        "run-a-latest",
        "run-empty-source-decoy",
    ]
    sql_selected_runs[2]["lineage"]["steps"][0]["name"] = "mutated"
    jsonl_selected_runs[2]["custom"]["keep"].append(7)
    assert sql_repo.read_by_cache_keys(CACHE_BUILD_RUN_STREAM, ["demo:key"])[2][
        "lineage"
    ] == {"steps": [{"name": "run-latest"}]}
    assert jsonl_repo.read_by_cache_keys(CACHE_BUILD_RUN_STREAM, ["demo:key"])[2][
        "custom"
    ] == {"keep": [4, 5, 6]}
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
    assert sql_repo.read_latest_run("demo:key", job_name="job-a", report_date="2026-01-31") == jsonl_repo.read_latest_run(
        "demo:key", job_name="job-a", report_date="2026-01-31",
    )
    assert sql_repo.read_latest_run("demo:key", job_name="job-a", report_date="2026-01-31")["run_id"] == "run-empty-source-decoy"
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


def test_sql_authority_read_by_cache_keys_does_not_read_jsonl(tmp_path, monkeypatch):
    repo = GovernanceRepository(
        base_dir=tmp_path / "sql",
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-authority",
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "selected",
            "job_name": "job-a",
            "status": "completed",
            "cache_key": "demo:key",
        },
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "noise",
            "job_name": "job-b",
            "status": "failed",
            "cache_key": "noise:key",
        },
    )

    def fail_if_jsonl_path_is_used(*_args, **_kwargs):
        raise AssertionError("sql-authority keyed reads must not use JSONL")

    monkeypatch.setattr(governance_module, "acquire_lock", fail_if_jsonl_path_is_used)
    monkeypatch.setattr(
        governance_module,
        "_read_jsonl_rows_and_index_cached",
        fail_if_jsonl_path_is_used,
    )

    rows = repo.read_by_cache_keys(CACHE_BUILD_RUN_STREAM, ["demo:key"])

    assert [row["run_id"] for row in rows] == ["selected"]


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


@pytest.mark.parametrize("status", ["failed", "queued", "running"])
def test_sql_latest_run_filters_unrelated_history_before_decoding(tmp_path, monkeypatch, status):
    repo = GovernanceRepository(
        base_dir=tmp_path / "sql",
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-authority",
    )
    target = {
        "cache_key": "demo:key",
        "job_name": "job-a",
        "report_date": "2026-01-31",
    }
    events = [
        (CACHE_BUILD_RUN_STREAM, {**target, "run_id": "older-success", "status": "completed"}),
        (CACHE_BUILD_RUN_STREAM, {**target, "run_id": "latest-target", "status": status}),
    ]
    for index in range(10):
        events.extend(
            [
                (CACHE_BUILD_RUN_STREAM, {**target, "run_id": f"other-cache-{index}", "cache_key": "other:key"}),
                (CACHE_BUILD_RUN_STREAM, {**target, "run_id": f"other-job-{index}", "job_name": "job-b"}),
                (CACHE_BUILD_RUN_STREAM, {**target, "run_id": f"other-date-{index}", "report_date": "2026-02-28"}),
            ]
        )
    repo.append_many_atomic(events)
    decoded_runs = []
    original_loads = governance_module.json.loads

    def track_decoding(payload, *args, **kwargs):
        row = original_loads(payload, *args, **kwargs)
        if isinstance(row, dict) and "run_id" in row:
            decoded_runs.append(row["run_id"])
        return row

    monkeypatch.setattr(governance_module.json, "loads", track_decoding)

    latest = repo.read_latest_run("demo:key", job_name="job-a", report_date="2026-01-31")

    assert latest is not None
    assert latest["run_id"] == "latest-target"
    assert latest["status"] == status
    assert decoded_runs == ["latest-target"]


@pytest.mark.parametrize(
    ("fields", "query", "expected_run"),
    [
        (
            {"job_name": "\t job-a\n", "report_date": "\n2026-01-31\t"},
            {"job_name": "\njob-a\t", "report_date": "\t2026-01-31\n"},
            "target",
        ),
        (
            {"cache_key": "\u00a0demo:key\u00a0", "job_name": "\u00a0job-a\u00a0", "report_date": "\u00a02026-01-31\u00a0"},
            {"job_name": "job-a", "report_date": "2026-01-31"},
            "target",
        ),
        (
            {"cache_key": "\u3000demo:key\u3000", "job_name": "\u3000job-a\u3000", "report_date": "\u30002026-01-31\u3000"},
            {"job_name": "job-a", "report_date": "2026-01-31"},
            "target",
        ),
        ({"job_name": "\t\n", "report_date": "\n\t"}, {"job_name": "", "report_date": ""}, "target"),
        ({}, {"job_name": "", "report_date": ""}, "target"),
        ({"job_name": None, "report_date": None}, {"job_name": "\t\n", "report_date": "\n\t"}, "target"),
        ({"job_name": "job-a", "report_date": "2026-01-31"}, {}, "other-date"),
        (
            {"job_name": "job-a", "report_date": "2026-01-31"},
            {"job_name": None, "report_date": None},
            "other-date",
        ),
    ],
    ids=["padded", "nonbreaking-space", "fullwidth-space", "blank", "missing", "null", "omitted-filters", "none-filters"],
)
def test_latest_run_sql_jsonl_match_whitespace_and_optional_fields(
    tmp_path, monkeypatch, fields, query, expected_run,
):
    monkeypatch.delenv("MOSS_ENVIRONMENT", raising=False)
    jsonl_repo = GovernanceRepository(base_dir=tmp_path / "jsonl", backend_mode="jsonl")
    sql_repo = GovernanceRepository(
        base_dir=tmp_path / "sql",
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-authority",
    )
    target = {"cache_key": "\t demo:key\n", "run_id": "target", "status": "failed", **fields}
    events = [
        (CACHE_BUILD_RUN_STREAM, target),
        (CACHE_BUILD_RUN_STREAM, {**target, "run_id": "other-job", "job_name": "job-b"}),
        (CACHE_BUILD_RUN_STREAM, {**target, "run_id": "other-date", "report_date": "2026-02-28"}),
        (CACHE_BUILD_RUN_STREAM, {**target, "run_id": "other-cache", "cache_key": "other:key"}),
    ]
    jsonl_repo.append_many_atomic(events)
    sql_repo.append_many_atomic(events)

    sql_latest = sql_repo.read_latest_run("\n demo:key\t", **query)
    jsonl_latest = jsonl_repo.read_latest_run("\n demo:key\t", **query)

    assert sql_latest == jsonl_latest
    assert sql_latest is not None
    assert sql_latest["run_id"] == expected_run


@pytest.mark.parametrize("frozen_is_empty", [True, False], ids=["empty", "latest-failed"])
def test_sql_latest_run_prefers_frozen_rows_without_accessing_live_sql(
    tmp_path, monkeypatch, frozen_is_empty,
):
    repo = GovernanceRepository(
        base_dir=tmp_path / "sql",
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-authority",
    )
    target = {"cache_key": "demo:key", "job_name": "job-a", "report_date": "2026-01-31"}
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {**target, "run_id": "live-success", "status": "completed"},
    )
    frozen_rows = [] if frozen_is_empty else [
        {**target, "run_id": "frozen-older-success", "status": "completed"},
        {**target, "run_id": "frozen-latest-failed", "status": "failed"},
    ]

    def read_frozen_rows(base_dir, stream):
        assert base_dir == repo.base_dir
        assert stream == CACHE_BUILD_RUN_STREAM
        return frozen_rows

    class UnavailableLiveEngine:
        def __getattr__(self, _name):
            raise AssertionError("Frozen run reads must not access live SQL")

    monkeypatch.setattr(governance_module, "frozen_system_governance_rows", read_frozen_rows)
    monkeypatch.setattr(repo, "_sql_engine", UnavailableLiveEngine())

    latest = repo.read_latest_run("demo:key", job_name="job-a", report_date="2026-01-31")

    if frozen_is_empty:
        assert latest is None
    else:
        assert latest is not None
        assert latest["run_id"] == "frozen-latest-failed"
        assert latest["status"] == "failed"
