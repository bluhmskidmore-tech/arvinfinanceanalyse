import json
from pathlib import Path
import sys
import time

import duckdb
import pytest

from tests.helpers import load_module


def _assert_record_contains(record: dict[str, object], expected: dict[str, object]) -> None:
    for key, value in expected.items():
        assert record[key] == value


def test_materialize_schema_exposes_minimal_build_payload():
    schema_module = load_module(
        "backend.app.schemas.materialize",
        "backend/app/schemas/materialize.py",
    )

    build_run = schema_module.CacheBuildRunRecord(
        run_id="materialize:test-run",
        job_name="materialize",
        status="completed",
        cache_key="phase1.native.cache",
        lock="lock:duckdb:materialize",
        source_version="sv_preview_empty",
        vendor_version="vv_none",
    )
    cache_manifest = schema_module.CacheManifestRecord(
        cache_key="phase1.native.cache",
        source_version="sv_preview_empty",
        vendor_version="vv_none",
        rule_version="rv_phase1_source_preview_v1",
    )
    payload = schema_module.MaterializeBuildPayload(
        status="completed",
        lock="lock:duckdb:materialize",
        cache_key="phase1.native.cache",
        run_id="materialize:test-run",
        preview_sources=["zqtz", "tyw"],
        vendor_version="vv_none",
    )

    assert build_run.model_dump() == {
        "run_id": "materialize:test-run",
        "job_name": "materialize",
        "status": "completed",
        "cache_key": "phase1.native.cache",
        "lock": "lock:duckdb:materialize",
        "source_version": "sv_preview_empty",
        "vendor_version": "vv_none",
    }
    assert cache_manifest.model_dump() == {
        "cache_key": "phase1.native.cache",
        "source_version": "sv_preview_empty",
        "vendor_version": "vv_none",
        "rule_version": "rv_phase1_source_preview_v1",
    }
    assert payload.model_dump() == {
        "status": "completed",
        "lock": "lock:duckdb:materialize",
        "cache_key": "phase1.native.cache",
        "run_id": "materialize:test-run",
        "preview_sources": ["zqtz", "tyw"],
        "vendor_version": "vv_none",
    }


def test_materialize_task_creates_duckdb_artifact_and_build_record(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_root = tmp_path / "input"
    data_root.mkdir()
    payload = task_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(data_root),
    )

    assert payload["status"] == "completed"
    assert duckdb_path.exists()
    assert (governance_dir / "cache_build_run.jsonl").exists()
    assert (governance_dir / "cache_manifest.jsonl").exists()

    build_run_records = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(build_run_records) == 1
    _assert_record_contains(
        build_run_records[0],
        {
            "run_id": payload["run_id"],
            "job_name": "materialize",
            "status": "completed",
            "cache_key": payload["cache_key"],
            "lock": payload["lock"],
            "source_version": "sv_preview_empty",
            "vendor_version": "vv_none",
        },
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = conn.execute("select count(*) from phase1_materialize_runs").fetchone()[0]
    finally:
        conn.close()

    assert rows >= 1

    manifest_records = [
        json.loads(line)
        for line in (governance_dir / "cache_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    _assert_record_contains(
        manifest_records[-1],
        {
            "cache_key": payload["cache_key"],
            "source_version": "sv_preview_empty",
            "vendor_version": "vv_none",
            "rule_version": "rv_phase1_source_preview_v1",
        },
    )


def test_materialize_task_records_failed_run_and_skips_manifest_on_manifest_write_error(
    tmp_path,
    monkeypatch,
):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")
    repo_module = sys.modules.get("backend.app.repositories.governance_repo")
    if repo_module is None:
        repo_module = load_module(
            "backend.app.repositories.governance_repo",
            "backend/app/repositories/governance_repo.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    monkeypatch.setattr(
        task_module,
        "materialize_source_previews",
        lambda **_: [{"source_family": "zqtz", "source_version": "sv_preview_stub"}],
    )

    original_append_unlocked = task_module.GovernanceRepository._append_unlocked

    def append_with_manifest_failure(self, stream: str, payload: dict[str, object]):
        if stream == repo_module.CACHE_MANIFEST_STREAM:
            raise RuntimeError("manifest write failed")
        return original_append_unlocked(self, stream, payload)

    monkeypatch.setattr(
        task_module.GovernanceRepository,
        "_append_unlocked",
        append_with_manifest_failure,
    )

    with pytest.raises(RuntimeError, match="manifest write failed"):
        task_module.materialize_cache_view.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            data_root=str(tmp_path / "input"),
        )

    build_run_records = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(build_run_records) == 1
    _assert_record_contains(
        build_run_records[0],
        {
            "run_id": build_run_records[0]["run_id"],
            "job_name": "materialize",
            "status": "failed",
            "cache_key": build_run_records[0]["cache_key"],
            "lock": build_run_records[0]["lock"],
            "source_version": "sv_preview_stub",
            "vendor_version": "vv_none",
        },
    )

    manifest_path = governance_dir / "cache_manifest.jsonl"
    assert not manifest_path.exists()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        run_rows = conn.execute(
            """
            select status
            from phase1_materialize_runs
            order by rowid desc
            limit 1
            """
        ).fetchall()
    finally:
        conn.close()

    assert run_rows == [("failed",)]


def test_materialize_task_rolls_back_manifest_if_success_build_log_append_fails(
    tmp_path,
    monkeypatch,
):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")
    repo_module = sys.modules.get("backend.app.repositories.governance_repo")
    if repo_module is None:
        repo_module = load_module(
            "backend.app.repositories.governance_repo",
            "backend/app/repositories/governance_repo.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    monkeypatch.setattr(
        task_module,
        "materialize_source_previews",
        lambda **_: [{"source_family": "zqtz", "source_version": "sv_preview_stub"}],
    )

    original_append_unlocked = task_module.GovernanceRepository._append_unlocked

    def append_with_build_run_failure(self, stream: str, payload: dict[str, object]):
        if stream == repo_module.CACHE_BUILD_RUN_STREAM and payload["status"] == "completed":
            raise RuntimeError("build run write failed")
        return original_append_unlocked(self, stream, payload)

    monkeypatch.setattr(
        task_module.GovernanceRepository,
        "_append_unlocked",
        append_with_build_run_failure,
    )

    with pytest.raises(RuntimeError, match="build run write failed"):
        task_module.materialize_cache_view.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            data_root=str(tmp_path / "input"),
        )

    assert not (governance_dir / "cache_manifest.jsonl").exists()
    build_run_records = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(build_run_records) == 1
    _assert_record_contains(
        build_run_records[0],
        {
            "run_id": build_run_records[0]["run_id"],
            "job_name": "materialize",
            "status": "failed",
            "cache_key": build_run_records[0]["cache_key"],
            "lock": build_run_records[0]["lock"],
            "source_version": "sv_preview_stub",
            "vendor_version": "vv_none",
        },
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        tables = {
            row[0]
            for row in conn.execute("show tables").fetchall()
        }
        if "phase1_source_preview_summary" in tables:
            assert conn.execute("select count(*) from phase1_source_preview_summary").fetchone()[0] == 0
    finally:
        conn.close()


def test_materialize_failure_preserves_last_good_preview_snapshot(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")
    preview_module = load_module(
        "backend.app.repositories.source_preview_repo",
        "backend/app/repositories/source_preview_repo.py",
    )
    repo_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    def write_preview(version: str):
        def _inner(**_: object):
            summaries = [
                {
                    "ingest_batch_id": "ib_preview_stub",
                    "batch_created_at": "2026-04-09T00:00:00Z",
                    "source_family": "zqtz",
                    "report_date": "2025-12-31",
                    "report_start_date": "2025-12-01",
                    "report_end_date": "2025-12-31",
                    "report_granularity": "daily",
                    "source_file": "ZQTZSHOW-20251231.xls",
                    "total_rows": 1,
                    "manual_review_count": 0,
                    "source_version": version,
                    "rule_version": preview_module.RULE_VERSION,
                    "preview_mode": "manifest",
                    "group_counts": {"债券类": 1},
                }
            ]
            preview_module._write_preview_tables(str(duckdb_path), summaries, [], [])
            return summaries
        return _inner

    monkeypatch.setattr(task_module, "materialize_source_previews", write_preview("sv_first"))
    first_payload = task_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(tmp_path / "input"),
    )
    assert first_payload["status"] == "completed"

    original_append_unlocked = task_module.GovernanceRepository._append_unlocked

    def failing_append_unlocked(self, stream: str, payload: dict[str, object]):
        if stream == repo_module.CACHE_BUILD_RUN_STREAM and payload["status"] == "completed":
            raise RuntimeError("build run write failed")
        return original_append_unlocked(self, stream, payload)

    monkeypatch.setattr(task_module, "materialize_source_previews", write_preview("sv_second"))
    monkeypatch.setattr(task_module.GovernanceRepository, "_append_unlocked", failing_append_unlocked)

    with pytest.raises(RuntimeError, match="build run write failed"):
        task_module.materialize_cache_view.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            data_root=str(tmp_path / "input"),
        )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        version = conn.execute(
            "select source_version from phase1_source_preview_summary"
        ).fetchone()[0]
    finally:
        conn.close()

    assert version == "sv_first"


def test_materialize_cleanup_failure_does_not_flip_success_lineage(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    monkeypatch.setattr(
        task_module,
        "materialize_source_previews",
        lambda **_: [{"source_family": "zqtz", "source_version": "sv_preview_stub"}],
    )
    monkeypatch.setattr(
        task_module,
        "cleanup_preview_backups",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(duckdb.Error("cleanup failed")),
    )

    payload = task_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(tmp_path / "input"),
    )

    assert payload["status"] == "completed"
    build_run_records = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(build_run_records) == 1
    _assert_record_contains(
        build_run_records[0],
        {
            "run_id": payload["run_id"],
            "job_name": "materialize",
            "status": "completed",
            "cache_key": payload["cache_key"],
            "lock": payload["lock"],
            "source_version": "sv_preview_stub",
            "vendor_version": "vv_none",
        },
    )


def test_materialize_restore_failure_is_surfaced(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    monkeypatch.setattr(
        task_module,
        "materialize_source_previews",
        lambda **_: (_ for _ in ()).throw(RuntimeError("preview failed")),
    )
    monkeypatch.setattr(
        task_module,
        "restore_preview_tables",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("restore failed")),
    )
    monkeypatch.setattr(
        task_module,
        "snapshot_preview_tables",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="Failed to restore preview tables after materialize error"):
        task_module.materialize_cache_view.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            data_root=str(tmp_path / "input"),
        )

    build_run_records = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert build_run_records[-1]["status"] == "failed"


def test_materialize_failed_run_append_failure_is_surfaced(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")
    repo_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    monkeypatch.setattr(
        task_module,
        "materialize_source_previews",
        lambda **_: (_ for _ in ()).throw(RuntimeError("preview failed")),
    )

    original_append = repo_module.GovernanceRepository.append

    def failing_append(self, stream: str, payload: dict[str, object]):
        if stream == repo_module.CACHE_BUILD_RUN_STREAM and payload["status"] == "failed":
            raise RuntimeError("failed lineage append failed")
        return original_append(self, stream, payload)

    monkeypatch.setattr(task_module.GovernanceRepository, "append", failing_append)

    with pytest.raises(RuntimeError, match="Failed to append failed materialize lineage"):
        task_module.materialize_cache_view.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            data_root=str(tmp_path / "input"),
        )


def test_materialize_snapshot_failure_preserves_last_good_preview_snapshot(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")
    preview_module = load_module(
        "backend.app.repositories.source_preview_repo",
        "backend/app/repositories/source_preview_repo.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    def write_preview(version: str):
        def _inner(**_: object):
            summaries = [
                {
                    "ingest_batch_id": "preview-direct",
                    "batch_created_at": "preview",
                    "source_family": "zqtz",
                    "report_date": "2025-12-31",
                    "report_start_date": "2025-12-01",
                    "report_end_date": "2025-12-31",
                    "report_granularity": "daily",
                    "source_file": "ZQTZSHOW-20251231.xls",
                    "total_rows": 1,
                    "manual_review_count": 0,
                    "source_version": version,
                    "rule_version": preview_module.RULE_VERSION,
                    "preview_mode": "manifest",
                    "group_counts": {"债券类": 1},
                }
            ]
            preview_module._write_preview_tables(str(duckdb_path), summaries, [], [])
            return summaries
        return _inner

    monkeypatch.setattr(task_module, "materialize_source_previews", write_preview("sv_first"))
    first_payload = task_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(tmp_path / "input"),
    )
    assert first_payload["status"] == "completed"

    monkeypatch.setattr(task_module, "snapshot_preview_tables", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("snapshot failed")))
    with pytest.raises(RuntimeError, match="snapshot failed"):
        task_module.materialize_cache_view.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            data_root=str(tmp_path / "input"),
        )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        version = conn.execute(
            "select source_version from phase1_source_preview_summary"
        ).fetchone()[0]
    finally:
        conn.close()

    assert version == "sv_first"


def test_materialize_task_holds_real_lock_across_critical_section(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")
    locks_module = sys.modules.get("backend.app.governance.locks")
    if locks_module is None:
        locks_module = load_module(
            "backend.app.governance.locks",
            "backend/app/governance/locks.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    observed = {"contention_checked": False}
    materialize_lock = task_module.resolve_materialize_lock(duckdb_path)

    def previews_under_lock(**_: object):
        with pytest.raises(TimeoutError):
            with locks_module.acquire_lock(
                materialize_lock,
                base_dir=duckdb_path.parent,
                timeout_seconds=0.01,
            ):
                pass
        observed["contention_checked"] = True
        return []

    monkeypatch.setattr(task_module, "materialize_source_previews", previews_under_lock)

    payload = task_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        data_root=str(tmp_path / "input"),
    )

    assert payload["status"] == "completed"
    assert observed["contention_checked"] is True


def test_materialize_lock_is_not_stolen_after_ttl_while_owner_is_active(tmp_path):
    locks_module = load_module(
        "backend.app.governance.locks",
        "backend/app/governance/locks.py",
    )
    short_lock = locks_module.LockDefinition(
        key="lock:test:materialize",
        ttl_seconds=0.1,
    )

    with locks_module.acquire_lock(short_lock, base_dir=tmp_path, timeout_seconds=0.2):
        time.sleep(0.2)
        with pytest.raises(TimeoutError):
            with locks_module.acquire_lock(
                short_lock,
                base_dir=tmp_path,
                timeout_seconds=0.05,
            ):
                pass


def test_materialize_uses_same_lock_for_same_duckdb_across_governance_dirs(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")
    locks_module = load_module(
        "backend.app.governance.locks",
        "backend/app/governance/locks.py",
    )

    original_acquire_lock = task_module.acquire_lock

    def short_timeout_acquire_lock(definition, base_dir, timeout_seconds=1.0, **kwargs):
        return original_acquire_lock(definition, base_dir=base_dir, timeout_seconds=0.05, **kwargs)

    monkeypatch.setattr(task_module, "acquire_lock", short_timeout_acquire_lock)

    duckdb_path = tmp_path / "shared.duckdb"
    first_governance_dir = tmp_path / "gov-a"
    second_governance_dir = tmp_path / "gov-b"
    observed = {"cross_dir_contention_checked": False}

    def previews_under_lock(**_: object):
        with pytest.raises(TimeoutError):
            task_module.materialize_cache_view.fn(
                duckdb_path=str(duckdb_path),
                governance_dir=str(second_governance_dir),
                data_root=str(tmp_path / "input"),
            )
        observed["cross_dir_contention_checked"] = True
        return []

    monkeypatch.setattr(task_module, "materialize_source_previews", previews_under_lock)

    payload = task_module.materialize_cache_view.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(first_governance_dir),
        data_root=str(tmp_path / "input"),
    )

    assert payload["status"] == "completed"
    assert observed["cross_dir_contention_checked"] is True


def test_materialize_uses_distinct_locks_for_different_duckdb_files_in_same_directory(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")

    first_duckdb_path = tmp_path / "shared-a.duckdb"
    second_duckdb_path = tmp_path / "shared-b.duckdb"
    first_lock = task_module.resolve_materialize_lock(first_duckdb_path)
    second_lock = task_module.resolve_materialize_lock(second_duckdb_path)

    assert first_lock.key != second_lock.key


def test_materialize_lock_normalizes_case_for_same_duckdb_path(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.materialize")
    if task_module is None:
        task_module = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")

    mixed_case_path = tmp_path / "Shared.DuckDB"
    same_path_different_case = Path(str(mixed_case_path).replace("Shared.DuckDB", "SHARED.DUCKDB"))

    first_lock = task_module.resolve_materialize_lock(mixed_case_path)
    second_lock = task_module.resolve_materialize_lock(same_path_different_case)

    assert first_lock.key == second_lock.key
