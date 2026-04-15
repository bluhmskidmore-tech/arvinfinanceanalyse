import json
import time
from pathlib import Path

import pytest

from tests.helpers import load_module


def test_governance_repository_appends_jsonl_records(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)

    repo.append("job_runs", {"job_name": "ingest", "status": "completed"})
    repo.append("cache_build_run", {"job_name": "materialize", "status": "completed"})

    job_log = tmp_path / "job_runs.jsonl"
    build_log = tmp_path / "cache_build_run.jsonl"
    assert job_log.exists()
    assert build_log.exists()
    assert "ingest" in job_log.read_text(encoding="utf-8")
    assert "materialize" in build_log.read_text(encoding="utf-8")


def test_governance_repository_normalizes_jsonl_stream_contract_fields(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)

    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "job_name": "materialize",
            "status": "completed",
        },
    )
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {
            "cache_key": "demo:key",
            "source_version": "sv_demo",
            "vendor_version": "vv_demo",
            "rule_version": "rv_demo",
        },
    )

    build_rows = repo.read_all(module.CACHE_BUILD_RUN_STREAM)
    manifest_rows = repo.read_all(module.CACHE_MANIFEST_STREAM)

    for field_name in module.STREAM_CONTRACT_FIELDS[module.CACHE_BUILD_RUN_STREAM]:
        assert field_name in build_rows[0]
    for field_name in module.STREAM_CONTRACT_FIELDS[module.CACHE_MANIFEST_STREAM]:
        assert field_name in manifest_rows[0]


def test_governance_latest_helpers_tolerate_sparse_legacy_jsonl_rows(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)

    (tmp_path / "cache_manifest.jsonl").write_text(
        '{"cache_key":"demo:key","source_version":"sv_old"}\n'
        '{"cache_key":"demo:key","source_version":"sv_new","vendor_version":"vv_new","rule_version":"rv_new"}\n',
        encoding="utf-8",
    )
    (tmp_path / "cache_build_run.jsonl").write_text(
        '{"run_id":"run-legacy","status":"completed","cache_key":"demo:key"}\n'
        '{"run_id":"run-new","job_name":"job-a","status":"completed","cache_key":"demo:key","report_date":"2026-01-31","source_version":"sv_new"}\n',
        encoding="utf-8",
    )

    latest_manifest = repo.read_latest_manifest("demo:key")
    latest_build = repo.read_latest_completed_run("demo:key", job_name="job-a", report_date="2026-01-31")

    assert latest_manifest is not None
    assert latest_manifest["source_version"] == "sv_new"
    assert latest_manifest["vendor_version"] == "vv_new"
    assert latest_manifest["rule_version"] == "rv_new"

    assert latest_build is not None
    assert latest_build["run_id"] == "run-new"
    assert latest_build["source_version"] == "sv_new"


def test_build_run_record_uses_fresh_created_at_per_instance():
    module = load_module("backend.app.tasks.build_runs", "backend/app/tasks/build_runs.py")

    first = module.BuildRunRecord(job_name="materialize", status="completed")
    time.sleep(0.001)
    second = module.BuildRunRecord(job_name="materialize", status="completed")

    assert first.created_at != second.created_at


def test_append_many_atomic_rolls_back_without_deleting_existing_records(tmp_path, monkeypatch):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(module.CACHE_BUILD_RUN_STREAM, {"job_name": "existing", "status": "completed"})

    original_append_unlocked = repo._append_unlocked

    def failing_append_unlocked(stream: str, payload: dict[str, object]):
        if stream == module.CACHE_MANIFEST_STREAM:
            raise RuntimeError("manifest failed")
        return original_append_unlocked(stream, payload)

    monkeypatch.setattr(repo, "_append_unlocked", failing_append_unlocked)

    with pytest.raises(RuntimeError, match="manifest failed"):
        repo.append_many_atomic(
            [
                (module.CACHE_BUILD_RUN_STREAM, {"job_name": "new", "status": "completed"}),
                (module.CACHE_MANIFEST_STREAM, {"cache_key": "k"}),
            ]
        )

    records = repo.read_all(module.CACHE_BUILD_RUN_STREAM)
    assert len(records) == 1
    assert records[0]["job_name"] == "existing"
    assert records[0]["status"] == "completed"
    for field_name in module.STREAM_CONTRACT_FIELDS[module.CACHE_BUILD_RUN_STREAM]:
        assert field_name in records[0]


@pytest.mark.parametrize("backend_mode", ["sql-authority", "sql-shadow"])
def test_append_many_atomic_sql_backends_roll_back_sql_and_jsonl_when_jsonl_write_fails(
    tmp_path,
    monkeypatch,
    backend_mode,
):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    sql_path = tmp_path / f"{backend_mode}.db"
    repo = module.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=f"sqlite:///{sql_path.as_posix()}",
        backend_mode=backend_mode,
    )
    existing_payload = {"job_name": "existing", "status": "completed"}
    repo.append(module.CACHE_BUILD_RUN_STREAM, existing_payload)

    original_append_unlocked = repo._append_unlocked

    def failing_append_unlocked(stream: str, payload: dict[str, object]):
        if stream == module.CACHE_MANIFEST_STREAM:
            raise RuntimeError("manifest failed")
        return original_append_unlocked(stream, payload)

    monkeypatch.setattr(repo, "_append_unlocked", failing_append_unlocked)

    with pytest.raises(RuntimeError, match="manifest failed"):
        repo.append_many_atomic(
            [
                (
                    module.CACHE_BUILD_RUN_STREAM,
                    {
                        "run_id": "run-new",
                        "job_name": "source_preview_refresh",
                        "status": "completed",
                        "cache_key": "source_preview.foundation",
                    },
                ),
                (
                    module.CACHE_MANIFEST_STREAM,
                    {
                        "cache_key": "source_preview.foundation",
                        "source_version": "sv_new",
                        "rule_version": "rv_new",
                    },
                ),
            ]
        )

    jsonl_build_runs = [
        json.loads(line)
        for line in (tmp_path / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert jsonl_build_runs[0]["job_name"] == existing_payload["job_name"]
    assert jsonl_build_runs[0]["status"] == existing_payload["status"]
    assert jsonl_build_runs[0]["run_id"] is None
    for field_name in module.STREAM_CONTRACT_FIELDS[module.CACHE_BUILD_RUN_STREAM]:
        assert field_name in jsonl_build_runs[0]

    sql_repo = module.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=f"sqlite:///{sql_path.as_posix()}",
        backend_mode="sql-authority",
    )
    sql_build_runs = sql_repo.read_all(module.CACHE_BUILD_RUN_STREAM)
    sql_manifests = sql_repo.read_all(module.CACHE_MANIFEST_STREAM)

    assert sql_build_runs[0]["job_name"] == existing_payload["job_name"]
    assert sql_build_runs[0]["status"] == existing_payload["status"]
    assert sql_build_runs[0]["run_id"] is None
    for field_name in module.STREAM_CONTRACT_FIELDS[module.CACHE_BUILD_RUN_STREAM]:
        assert field_name in sql_build_runs[0]
    assert sql_manifests == []


def test_governance_batch_lock_uses_canonical_base_dir(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    relative_repo = module.GovernanceRepository(base_dir=tmp_path)
    absolute_repo = module.GovernanceRepository(base_dir=tmp_path.resolve())

    assert relative_repo._batch_lock().key == absolute_repo._batch_lock().key


def test_governance_repository_sql_authority_reads_sql_records_even_if_jsonl_shadow_changes(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    sql_path = tmp_path / "governance.db"
    repo = module.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=f"sqlite:///{sql_path.as_posix()}",
        backend_mode="sql-authority",
    )
    payload = {
        "run_id": "run-sql",
        "job_name": "source_preview_refresh",
        "status": "queued",
        "cache_key": module.CACHE_BUILD_RUN_STREAM,
        "lock": "lock:preview",
        "source_version": "sv_preview_pending",
        "vendor_version": "vv_none",
        "preview_sources": ["zqtz", "tyw"],
    }

    repo.append(module.CACHE_BUILD_RUN_STREAM, payload)

    (tmp_path / "cache_build_run.jsonl").write_text(
        '{"run_id":"run-jsonl","status":"failed"}\n',
        encoding="utf-8",
    )

    rows = repo.read_all(module.CACHE_BUILD_RUN_STREAM)
    assert len(rows) == 1
    assert rows[0]["run_id"] == payload["run_id"]
    assert rows[0]["status"] == payload["status"]
    for field_name in module.STREAM_CONTRACT_FIELDS[module.CACHE_BUILD_RUN_STREAM]:
        assert field_name in rows[0]


def test_governance_repository_sql_shadow_reads_jsonl_records_while_keeping_sql_copy(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    sql_path = tmp_path / "governance.db"
    repo = module.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=f"sqlite:///{sql_path.as_posix()}",
        backend_mode="sql-shadow",
    )
    payload = {
        "cache_key": "source_preview.foundation",
        "source_version": "sv_shadow",
        "vendor_version": "vv_none",
        "rule_version": "rv_test",
    }

    repo.append(module.CACHE_MANIFEST_STREAM, payload)

    (tmp_path / "cache_manifest.jsonl").write_text(
        '{"cache_key":"jsonl-authority","source_version":"sv_jsonl"}\n',
        encoding="utf-8",
    )

    assert repo.read_all(module.CACHE_MANIFEST_STREAM) == [
        {"cache_key": "jsonl-authority", "source_version": "sv_jsonl"}
    ]


@pytest.mark.parametrize("backend_mode", ["sql-authority", "sql-shadow"])
def test_governance_repository_append_rolls_back_sql_when_jsonl_write_fails(
    tmp_path,
    monkeypatch,
    backend_mode,
):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    sql_path = tmp_path / f"append-{backend_mode}.db"
    repo = module.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=f"sqlite:///{sql_path.as_posix()}",
        backend_mode=backend_mode,
    )

    monkeypatch.setattr(
        repo,
        "_append_unlocked",
        lambda stream, payload: (_ for _ in ()).throw(RuntimeError("jsonl write failed")),
    )

    payload = {
        "run_id": "run-append-fail",
        "job_name": "source_preview_refresh",
        "status": "queued",
        "cache_key": "source_preview.foundation",
    }

    with pytest.raises(RuntimeError, match="jsonl write failed"):
        repo.append(module.CACHE_BUILD_RUN_STREAM, payload)

    assert not (tmp_path / "cache_build_run.jsonl").exists()

    sql_repo = module.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=f"sqlite:///{sql_path.as_posix()}",
        backend_mode="sql-authority",
    )
    assert sql_repo.read_all(module.CACHE_BUILD_RUN_STREAM) == []


def test_governance_repository_rejects_unknown_backend_mode(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")

    with pytest.raises(ValueError, match="Unsupported governance backend mode"):
        module.GovernanceRepository(
            base_dir=tmp_path,
            sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
            backend_mode="sql-autority",
        )


def test_governance_repository_rewrites_postgresql_dsn_to_psycopg_driver():
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")

    assert (
        module._normalize_sqlalchemy_dsn("postgresql://moss:moss@127.0.0.1:55432/moss")
        == "postgresql+psycopg://moss:moss@127.0.0.1:55432/moss"
    )
    assert (
        module._normalize_sqlalchemy_dsn("postgresql+psycopg://moss:moss@127.0.0.1:55432/moss")
        == "postgresql+psycopg://moss:moss@127.0.0.1:55432/moss"
    )


def test_governance_sql_record_uses_datetime_created_at_for_postgres_compatibility():
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")

    record = module._sql_record_for_stream(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-1",
            "job_name": "source_preview_refresh",
            "status": "queued",
            "cache_key": "source_preview.foundation",
        },
    )

    assert hasattr(record["created_at"], "isoformat")


def test_governance_repository_uses_null_pool_for_sql_backend(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}",
        backend_mode="sql-shadow",
    )

    assert repo._sql_engine is not None
    assert repo._sql_engine.pool.__class__.__name__ == "NullPool"


def test_read_latest_manifest_returns_latest_cache_key_row(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {
            "cache_key": "demo:key",
            "source_version": "sv_old",
            "vendor_version": "vv_old",
            "rule_version": "rv_old",
        },
    )
    repo.append(
        module.CACHE_MANIFEST_STREAM,
        {
            "cache_key": "demo:key",
            "source_version": "sv_new",
            "vendor_version": "vv_new",
            "rule_version": "rv_new",
        },
    )

    latest = repo.read_latest_manifest("demo:key")
    assert latest is not None
    assert latest["source_version"] == "sv_new"
    assert latest["vendor_version"] == "vv_new"
    assert latest["rule_version"] == "rv_new"


def test_read_latest_completed_run_filters_by_cache_key_and_optional_dimensions(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-1",
            "job_name": "job-a",
            "status": "completed",
            "cache_key": "demo:key",
            "report_date": "2025-12-31",
            "source_version": "sv-1",
        },
    )
    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-2",
            "job_name": "job-a",
            "status": "running",
            "cache_key": "demo:key",
            "report_date": "2025-12-31",
            "source_version": "sv-2",
        },
    )
    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-3",
            "job_name": "job-b",
            "status": "completed",
            "cache_key": "demo:key",
            "report_date": "2026-01-31",
            "source_version": "sv-3",
        },
    )

    latest_any = repo.read_latest_completed_run("demo:key")
    assert latest_any is not None
    assert latest_any["run_id"] == "run-3"

    latest_job = repo.read_latest_completed_run("demo:key", job_name="job-a")
    assert latest_job is not None
    assert latest_job["run_id"] == "run-1"

    latest_job_day = repo.read_latest_completed_run(
        "demo:key",
        job_name="job-b",
        report_date="2026-01-31",
    )
    assert latest_job_day is not None
    assert latest_job_day["run_id"] == "run-3"


def test_read_latest_completed_run_can_require_non_empty_source_version(tmp_path):
    module = load_module("backend.app.repositories.governance_repo", "backend/app/repositories/governance_repo.py")
    repo = module.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-filled",
            "job_name": "job-a",
            "status": "completed",
            "cache_key": "demo:key",
            "report_date": "2025-12-31",
            "source_version": "sv-filled",
        },
    )
    repo.append(
        module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-empty",
            "job_name": "job-a",
            "status": "completed",
            "cache_key": "demo:key",
            "report_date": "2025-12-31",
            "source_version": "",
        },
    )

    latest_any = repo.read_latest_completed_run("demo:key", job_name="job-a", report_date="2025-12-31")
    latest_with_source = repo.read_latest_completed_run(
        "demo:key",
        job_name="job-a",
        report_date="2025-12-31",
        require_source_version=True,
    )

    assert latest_any is not None
    assert latest_any["run_id"] == "run-empty"
    assert latest_with_source is not None
    assert latest_with_source["run_id"] == "run-filled"
