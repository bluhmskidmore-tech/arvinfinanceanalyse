from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC
from decimal import Decimal
from functools import partial
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories import financial_result_publication_repo as publication_repo
from backend.app.repositories.financial_result_publication_repo import (
    FINANCIAL_PUBLICATION_API_VERSION,
    FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    FinancialPublicationIncompatible,
    FinancialPublicationUnavailable,
    open_financial_generation,
    read_publication_pointer,
    resolve_financial_generation,
)
from backend.app.tasks import financial_result_publication as publication_task
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationCapacityError,
    FinancialPublicationConflict,
    FinancialPublicationPlan,
    FinancialTablePublicationSpec,
    invalidate_financial_generation,
    publish_financial_result,
)


def _create_source(path: Path, value: int = 11) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute("CREATE TABLE fact_result(report_date DATE, value INTEGER)")
        conn.execute("INSERT INTO fact_result VALUES (DATE '2026-06-30', ?)", [value])
        conn.execute("CREATE TABLE dim_scope(scope VARCHAR)")
        conn.execute("INSERT INTO dim_scope VALUES ('all')")
        conn.execute("CREATE TABLE publication_dependency_state(name VARCHAR, version VARCHAR)")
        conn.executemany(
            "INSERT INTO publication_dependency_state VALUES (?, ?)",
            [
                ("source", "source-v1"),
                ("rules", "rules-v3"),
                ("adjustments", "adjustments-v2"),
            ],
        )
    finally:
        conn.close()


def _replace_source_value(path: Path, value: int) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute("UPDATE fact_result SET value = ?", [value])
    finally:
        conn.close()


def _source_dependency_versions(conn: duckdb.DuckDBPyConnection) -> dict[str, str]:
    return {
        str(name): str(version)
        for name, version in conn.execute(
            "SELECT name, version FROM publication_dependency_state ORDER BY name"
        ).fetchall()
    }


def _plan(
    generation: str,
    previous: str | None,
    *,
    supported_api_versions: tuple[str, ...] = (FINANCIAL_PUBLICATION_API_VERSION,),
    expires_at: str | None = None,
) -> FinancialPublicationPlan:
    return FinancialPublicationPlan(
        generation=generation,
        expected_previous_generation=previous,
        tables=(
            FinancialTablePublicationSpec(
                name="fact_result",
                date_column="report_date",
                required_dates=("2026-06-30",),
            ),
            FinancialTablePublicationSpec(name="dim_scope"),
        ),
        required_steps=("materialize", "verify"),
        step_receipts=(
            {
                "name": "materialize",
                "status": "completed",
                "result": {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "source_version": "source-v1",
                },
            },
            {
                "name": "verify",
                "status": "completed",
                "result": {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "check_count": 2,
                },
            },
        ),
        required_dependency_keys=("source", "rules", "adjustments"),
        dependency_versions={
            "source": "source-v1",
            "rules": "rules-v3",
            "adjustments": "adjustments-v2",
        },
        coverage_dates={"current": ("2026-06-30",)},
        supported_api_versions=supported_api_versions,
        supported_schema_versions=(FINANCIAL_PUBLICATION_SCHEMA_VERSION,),
        quality={
            "status": "passed",
            "checks": (
                {"name": "table_coverage", "status": "passed"},
                {"name": "business_tieout", "status": "passed"},
            ),
        },
        source_dependency_validator=_source_dependency_versions,
        expires_at=expires_at,
    )


def _publish(source: Path, root: Path, plan: FinancialPublicationPlan, **kwargs):
    return publish_financial_result(
        source_duckdb_path=source,
        publication_root=root,
        plan=plan,
        **kwargs,
    )


def _value(conn: duckdb.DuckDBPyConnection) -> int:
    return int(conn.execute("SELECT value FROM fact_result").fetchone()[0])


def test_publish_seals_manifest_and_opens_only_committed_generation(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)

    receipt = _publish(source, root, _plan("generation-1", None))

    assert receipt.status == "published"
    pointer = read_publication_pointer(root)
    assert pointer is not None
    assert pointer["generation"] == "generation-1"
    assert pointer["manifest_sha256"] == receipt.manifest_sha256
    with open_financial_generation(
        root,
        generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    ) as (conn, resolved):
        assert resolved.generation == "generation-1"
        assert _value(conn) == 11
        assert conn.execute("SELECT count(*) FROM dim_scope").fetchone() == (1,)
    manifest = json.loads(receipt.manifest_path.read_text(encoding="utf-8"))
    assert manifest["sealed_payload"]["dependency_versions"] == {
        "adjustments": "adjustments-v2",
        "rules": "rules-v3",
        "source": "source-v1",
    }
    fact = next(item for item in manifest["sealed_payload"]["tables"] if item["name"] == "fact_result")
    assert fact["coverage_row_counts"] == {"2026-06-30": 1}


def test_crash_before_pointer_keeps_previous_and_rejects_uncommitted_candidate(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    _publish(source, root, _plan("generation-1", None))
    _replace_source_value(source, 22)

    def fail_before_pointer(stage: str) -> None:
        if stage == "candidate_validated":
            raise RuntimeError("injected pre-pointer crash")

    with pytest.raises(RuntimeError, match="pre-pointer crash"):
        _publish(source, root, _plan("generation-2", "generation-1"), on_stage=fail_before_pointer)

    assert read_publication_pointer(root)["generation"] == "generation-1"  # type: ignore[index]
    with open_financial_generation(
        root,
        generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    ) as (conn, _):
        assert _value(conn) == 11
    with pytest.raises(FinancialPublicationUnavailable, match="retention window"):
        resolve_financial_generation(
            root,
            generation="generation-2",
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )
    recovered = _publish(source, root, _plan("generation-2", "generation-1"))
    assert recovered.status == "published"
    assert read_publication_pointer(root)["generation"] == "generation-2"  # type: ignore[index]


def test_crash_after_pointer_is_recoverable_by_generation_identity(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    plan = _plan("generation-1", None)

    def fail_after_pointer(stage: str) -> None:
        if stage == "pointer_committed":
            raise RuntimeError("injected receipt crash")

    with pytest.raises(RuntimeError, match="receipt crash"):
        _publish(source, root, plan, on_stage=fail_after_pointer)

    assert read_publication_pointer(root)["generation"] == "generation-1"  # type: ignore[index]
    recovered = _publish(source, root, plan)
    assert recovered.status == "already_published"
    assert recovered.recovered_after_commit is True


def test_crash_after_database_seal_recovers_missing_external_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    plan = _plan("generation-1", None)

    def fail_after_database_seal(stage: str) -> None:
        if stage == "candidate_sealed":
            raise RuntimeError("injected manifest gap")

    with pytest.raises(RuntimeError, match="manifest gap"):
        _publish(source, root, plan, on_stage=fail_after_database_seal)
    assert (root / "generations" / "generation-1.duckdb").is_file()
    assert not (root / "generations" / "generation-1.manifest.json").exists()
    assert not (root / "current.json").exists()

    recovered = _publish(source, root, plan)
    assert recovered.status == "published"
    assert recovered.manifest_path.is_file()
    assert read_publication_pointer(root)["generation"] == "generation-1"  # type: ignore[index]


def test_late_publisher_cannot_overwrite_newer_pointer(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    _publish(source, root, _plan("generation-1", None))
    _publish(source, root, _plan("generation-2", "generation-1"))

    with pytest.raises(FinancialPublicationConflict, match="Expected previous"):
        _publish(source, root, _plan("late-generation", "generation-1"))
    assert read_publication_pointer(root)["generation"] == "generation-2"  # type: ignore[index]


def test_old_connection_stays_pinned_and_new_connection_reads_new_generation(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source, 11)
    _publish(source, root, _plan("generation-1", None))
    with open_financial_generation(
        root,
        generation="generation-1",
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    ) as (old_conn, _):
        _replace_source_value(source, 22)
        _publish(source, root, _plan("generation-2", "generation-1"))
        with open_financial_generation(
            root,
            generation=None,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        ) as (new_conn, resolved):
            assert resolved.generation == "generation-2"
            assert _value(new_conn) == 22
        assert _value(old_conn) == 11
    generation_1 = resolve_financial_generation(
        root,
        generation="generation-1",
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    assert generation_1.generation == "generation-1"
    _replace_source_value(source, 33)
    _publish(source, root, _plan("generation-3", "generation-2"))
    assert generation_1.database_path.is_file()
    with pytest.raises(FinancialPublicationUnavailable, match="retention window"):
        resolve_financial_generation(
            root,
            generation="generation-1",
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )


def test_disk_capacity_preflight_leaves_no_candidate_or_pointer(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    monkeypatch.setattr(
        publication_task.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(total=100, used=99, free=1),
    )

    with pytest.raises(FinancialPublicationCapacityError, match="Insufficient free space"):
        _publish(source, root, _plan("generation-1", None))
    assert not (root / "current.json").exists()
    assert list((root / "generations").iterdir()) == []


def test_partial_receipt_and_missing_business_coverage_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    complete = _plan("generation-1", None)
    partial = FinancialPublicationPlan(
        **{
            **complete.__dict__,
            "step_receipts": (
                complete.step_receipts[0],
                {"name": "verify", "status": "failed", "result": {"status": "failed"}},
            ),
        }
    )
    with pytest.raises(publication_repo.FinancialPublicationInvalid, match="incomplete"):
        _publish(source, root, partial)

    missing_coverage = FinancialPublicationPlan(
        **{
            **complete.__dict__,
            "tables": (
                FinancialTablePublicationSpec(
                    name="fact_result",
                    date_column="report_date",
                    required_dates=("2026-07-31",),
                ),
                complete.tables[1],
            ),
            "coverage_dates": {"current": ("2026-07-31",)},
        }
    )
    with pytest.raises(publication_repo.FinancialPublicationInvalid, match="0 rows"):
        _publish(source, root, missing_coverage)
    assert not (root / "current.json").exists()


@pytest.mark.parametrize("existing_connection", [False, True])
@pytest.mark.parametrize("full_database", [False, True])
def test_failed_candidate_is_removed_without_touching_committed_generation(
    tmp_path: Path, existing_connection: bool, full_database: bool,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    receipt = _publish(source, root, _plan("generation-1", None))
    original_database = receipt.database_path.read_bytes()
    original_pointer = (root / "current.json").read_bytes()
    plan = _plan("generation-2", "generation-1")
    plan = replace(
        plan,
        tables=(replace(plan.tables[0], required_dates=("2026-07-31",)), plan.tables[1]),
        coverage_dates={"current": ("2026-07-31",)},
        full_database=full_database,
        system_read_bundle={
            "protocol_version": 1,
            "active_database_identity": str(source.resolve()),
            "full_database": True,
            "governance_base_identity": str((tmp_path / "governance").resolve()),
            "governance_streams": {
                "cache_build_run": [{
                    "run_id": "formal-run", "cache_key": "formal-cache", "status": "completed",
                }],
                "cache_manifest": [{"cache_key": "formal-cache", "fact_tables": ["fact_result"]}],
            },
            "pnl_generation": "pnl-generation",
            "pnl_manifest_sha256": "a" * 64,
            "data_update_run_id": "data-update-run",
            "global_run_id": "global-run",
            "workflow": "core_financial",
            "report_date": "2026-07-31",
        } if full_database else None,
    )
    unrelated_candidate = root / "generations" / ".another-attempt.building"
    unrelated_candidate.write_bytes(b"owned by another attempt")
    initial_files = set((root / "generations").iterdir())

    def fail_twice(**kwargs) -> None:
        for _ in range(2):
            with pytest.raises(publication_repo.FinancialPublicationInvalid, match="0 rows"):
                _publish(source, root, plan, **kwargs)
            assert set((root / "generations").iterdir()) == initial_files
            assert (root / "current.json").read_bytes() == original_pointer
            assert receipt.database_path.read_bytes() == original_database
            assert unrelated_candidate.read_bytes() == b"owned by another attempt"

    if existing_connection:
        with acquire_lock(resolve_duckdb_writer_lock(source), base_dir=source.parent):
            conn = duckdb.connect(str(source))
            try:
                fail_twice(source_connection=conn, writer_lock_already_held=True)
                assert _value(conn) == 11
            finally:
                conn.close()
    else:
        fail_twice()


def test_failed_candidate_cleans_its_wal_and_preserves_the_original_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)

    def fail_after_creating_files(*, candidate_path: Path, **kwargs):
        candidate_path.write_bytes(b"unfinished candidate")
        Path(str(candidate_path) + ".wal").write_bytes(b"unfinished WAL")
        raise RuntimeError("candidate build failed")

    monkeypatch.setattr(
        publication_task, "_build_candidate_from_attached_source", fail_after_creating_files,
    )
    with pytest.raises(RuntimeError, match="candidate build failed"):
        _publish(source, root, _plan("generation-1", None))
    assert list((root / "generations").iterdir()) == []
    assert not (root / "current.json").exists()


def test_candidate_rename_failure_cleans_only_unpublished_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    _publish(source, root, _plan("generation-1", None))
    initial_files = set((root / "generations").iterdir())
    original_pointer = (root / "current.json").read_bytes()
    real_replace = os.replace

    def reject_candidate_rename(source_path, destination_path):
        if str(source_path).endswith(".building"):
            raise PermissionError("candidate rename denied")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(publication_task.os, "replace", reject_candidate_rename)
    with pytest.raises(PermissionError, match="candidate rename denied"):
        _publish(source, root, _plan("generation-2", "generation-1"))
    assert set((root / "generations").iterdir()) == initial_files
    assert (root / "current.json").read_bytes() == original_pointer


def test_plan_is_rejected_when_source_revision_changes_before_writer_lock(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    stale_plan = _plan("generation-1", None)
    conn = duckdb.connect(str(source))
    try:
        conn.execute(
            "UPDATE publication_dependency_state SET version = 'source-v2' WHERE name = 'source'"
        )
        conn.execute("UPDATE fact_result SET value = 99")
    finally:
        conn.close()

    with pytest.raises(FinancialPublicationConflict, match="dependencies changed"):
        _publish(source, root, stale_plan)
    assert not (root / "current.json").exists()
    assert list((root / "generations").iterdir()) == []


def test_incompatible_expired_and_invalidated_generations_fail_closed(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    _publish(
        source,
        root,
        _plan(
            "generation-1",
            None,
            supported_api_versions=(FINANCIAL_PUBLICATION_API_VERSION, "financial-api/v2"),
            expires_at="2099-01-01T00:00:00+00:00",
        ),
    )
    with pytest.raises(FinancialPublicationIncompatible, match="incompatible"):
        resolve_financial_generation(
            root,
            generation="generation-1",
            reader_api_version="financial-api/v0",
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )

    real_datetime = publication_repo.datetime

    class ExpiredClock(real_datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2100, 1, 1, tzinfo=UTC)
            return value if tz is not None else value.replace(tzinfo=None)

    monkeypatch.setattr(publication_repo, "datetime", ExpiredClock)
    with pytest.raises(FinancialPublicationUnavailable, match="expired"):
        resolve_financial_generation(
            root,
            generation="generation-1",
            reader_api_version="financial-api/v2",
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )
    monkeypatch.setattr(publication_repo, "datetime", real_datetime)

    invalidate_financial_generation(root, generation="generation-1", reason="source approval revoked")
    with pytest.raises(FinancialPublicationUnavailable, match="not valid|invalidated"):
        resolve_financial_generation(
            root,
            generation=None,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )


def test_generation_paths_cannot_be_injected_from_request(tmp_path: Path) -> None:
    with pytest.raises(publication_repo.FinancialPublicationInvalid, match="generation"):
        resolve_financial_generation(
            tmp_path,
            generation="../source.duckdb",
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )


def test_invalid_current_generation_does_not_block_explicit_compatible_previous(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    _publish(source, root, _plan("generation-1", None))
    _replace_source_value(source, 22)
    _publish(source, root, _plan("generation-2", "generation-1"))
    invalidate_financial_generation(root, generation="generation-2", reason="current rules revoked")

    with pytest.raises(FinancialPublicationUnavailable, match="not valid"):
        resolve_financial_generation(
            root,
            generation=None,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )
    previous = resolve_financial_generation(
        root,
        generation="generation-1",
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    assert previous.generation == "generation-1"


def test_database_digest_and_catalog_validation_are_cached_by_file_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    _publish(source, root, _plan("generation-1", None))
    publication_repo.reset_financial_publication_validation_cache()
    first = resolve_financial_generation(
        root,
        generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    monkeypatch.setattr(
        publication_repo,
        "sha256_file",
        lambda _: (_ for _ in ()).throw(AssertionError("database was rehashed")),
    )

    second = resolve_financial_generation(
        root,
        generation="generation-1",
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )

    assert second.database_path == first.database_path



def _cold_validation_fixture(tmp_path: Path, *, expires_at: str | None = None):
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    receipt = _publish(source, root, _plan("generation-1", None, expires_at=expires_at))
    publication_repo.reset_financial_publication_validation_cache()
    return root, receipt


def _track_cold_validation_lookups(monkeypatch, readers: int) -> threading.Event:
    all_lookups = threading.Event()
    miss_threads: set[int] = set()

    class CountingCache(dict):
        def get(self, key, default=None):
            value = super().get(key, default)
            if value is None:
                miss_threads.add(threading.get_ident())
                if len(miss_threads) == readers:
                    all_lookups.set()
            return value

    monkeypatch.setattr(publication_repo, "_VALIDATION_CACHE", CountingCache())
    return all_lookups


def test_cold_same_generation_readers_share_database_validation(tmp_path: Path, monkeypatch) -> None:
    root, _ = _cold_validation_fixture(tmp_path)
    readers = 6
    all_lookups = _track_cold_validation_lookups(monkeypatch, readers)
    release_validation = threading.Event()
    validator_started = threading.Event()
    validation_calls: list[Path] = []
    calls_lock = threading.Lock()
    original_validate = publication_repo._validate_database_artifact

    def hold_validation(path: Path, manifest):
        with calls_lock:
            validation_calls.append(path)
        validator_started.set()
        assert release_validation.wait(10), "Concurrent validation gate was not released."
        original_validate(path, manifest)

    monkeypatch.setattr(publication_repo, "_validate_database_artifact", hold_validation)
    with ThreadPoolExecutor(max_workers=readers) as pool:
        pending = [
            pool.submit(
                resolve_financial_generation,
                root,
                generation=None,
                reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
                reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
            )
            for _ in range(readers)
        ]
        try:
            assert validator_started.wait(10)
            assert all_lookups.wait(10), "All six readers must overlap the cold validation."
        finally:
            release_validation.set()
        results = [future.result(timeout=10) for future in pending]

    assert len(validation_calls) == 1, "The same immutable database was validated more than once."
    assert all(result.generation == "generation-1" for result in results)



def _observe_validation_waiter(monkeypatch, *, pause_after_completion: bool = False):
    waiting = threading.Event()
    completed = threading.Event()
    release_waiter = threading.Event()
    if not pause_after_completion:
        release_waiter.set()

    class ObservedFuture(Future):
        def result(self, *args, **kwargs):
            waiting.set()
            value = super().result(*args, **kwargs)
            completed.set()
            assert release_waiter.wait(10), "Completed waiter was not released."
            return value

    monkeypatch.setattr(publication_repo, "Future", ObservedFuture)
    return waiting, completed, release_waiter


def test_failed_shared_validation_releases_waiters_and_can_retry(tmp_path: Path, monkeypatch) -> None:
    root, _ = _cold_validation_fixture(tmp_path)
    waiting, _, _ = _observe_validation_waiter(monkeypatch)
    validator_started = threading.Event()
    release_validation = threading.Event()
    original_validate = publication_repo._validate_database_artifact
    validation_calls = 0

    def fail_first_validation(path: Path, manifest):
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 1:
            validator_started.set()
            assert release_validation.wait(10)
            raise publication_repo.FinancialPublicationInvalid("Injected artifact validation failure")
        original_validate(path, manifest)

    monkeypatch.setattr(publication_repo, "_validate_database_artifact", fail_first_validation)
    read_generation = partial(
        resolve_financial_generation, root, generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(read_generation)
        try:
            assert validator_started.wait(10)
            waiter = pool.submit(read_generation)
            assert waiting.wait(10), "The second reader must join the in-flight validation."
        finally:
            release_validation.set()
        for request in (owner, waiter):
            with pytest.raises(publication_repo.FinancialPublicationInvalid, match="Injected artifact"):
                request.result(timeout=10)

    assert validation_calls == 1
    assert not publication_repo._VALIDATION_IN_FLIGHT
    assert read_generation().generation == "generation-1"
    assert validation_calls == 2


def test_reset_during_shared_validation_does_not_strand_waiters(tmp_path: Path, monkeypatch) -> None:
    root, _ = _cold_validation_fixture(tmp_path)
    waiting, _, _ = _observe_validation_waiter(monkeypatch)
    validator_started = threading.Event()
    release_validation = threading.Event()
    original_validate = publication_repo._validate_database_artifact
    validation_calls = 0

    def hold_validation(path: Path, manifest):
        nonlocal validation_calls
        validation_calls += 1
        validator_started.set()
        assert release_validation.wait(10)
        original_validate(path, manifest)

    monkeypatch.setattr(publication_repo, "_validate_database_artifact", hold_validation)
    read_generation = partial(
        resolve_financial_generation, root, generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(read_generation)
        try:
            assert validator_started.wait(10)
            waiter = pool.submit(read_generation)
            assert waiting.wait(10)
            publication_repo.reset_financial_publication_validation_cache()
        finally:
            release_validation.set()
        assert owner.result(timeout=10).generation == "generation-1"
        assert waiter.result(timeout=10).generation == "generation-1"
    assert validation_calls == 1
    assert not publication_repo._VALIDATION_IN_FLIGHT


def test_different_generations_validate_in_parallel(tmp_path: Path, monkeypatch) -> None:
    root, _ = _cold_validation_fixture(tmp_path)
    _publish(tmp_path / "source.duckdb", root, _plan("generation-2", "generation-1"))
    publication_repo.reset_financial_publication_validation_cache()
    started = {generation: threading.Event() for generation in ("generation-1", "generation-2")}
    release_validation = threading.Event()
    original_validate = publication_repo._validate_database_artifact

    def hold_validation(path: Path, manifest):
        started[path.stem].set()
        assert release_validation.wait(10)
        original_validate(path, manifest)

    monkeypatch.setattr(publication_repo, "_validate_database_artifact", hold_validation)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(
                resolve_financial_generation, root, generation=generation,
                reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
                reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
            )
            for generation in started
        ]
        try:
            assert all(event.wait(10) for event in started.values()), "Different keys were serialized."
        finally:
            release_validation.set()
        assert {request.result(timeout=10).generation for request in pending} == set(started)


@pytest.mark.parametrize("version_field", ["reader_api_version", "reader_schema_version"])
def test_incompatible_reader_does_not_poison_in_flight_validation(
    tmp_path: Path, monkeypatch, version_field: str
) -> None:
    root, _ = _cold_validation_fixture(tmp_path)
    validator_started = threading.Event()
    release_validation = threading.Event()
    original_validate = publication_repo._validate_database_artifact

    def hold_validation(path: Path, manifest):
        validator_started.set()
        assert release_validation.wait(10)
        original_validate(path, manifest)

    monkeypatch.setattr(publication_repo, "_validate_database_artifact", hold_validation)
    versions = {
        "reader_api_version": FINANCIAL_PUBLICATION_API_VERSION,
        "reader_schema_version": FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(resolve_financial_generation, root, generation=None, **versions)
        try:
            assert validator_started.wait(10)
            incompatible = pool.submit(
                resolve_financial_generation, root, generation=None,
                **{**versions, version_field: "unsupported/v0"},
            )
            with pytest.raises(FinancialPublicationIncompatible, match="incompatible"):
                incompatible.result(timeout=10)
        finally:
            release_validation.set()
        assert owner.result(timeout=10).generation == "generation-1"
    assert resolve_financial_generation(root, generation=None, **versions).generation == "generation-1"


@pytest.mark.parametrize("change", ["manifest", "database", "invalidation", "expiry"])
def test_validation_owner_rechecks_artifacts_revocation_and_expiry(
    tmp_path: Path, monkeypatch, change: str
) -> None:
    root, receipt = _cold_validation_fixture(tmp_path, expires_at="2099-01-01T00:00:00+00:00")
    validated = threading.Event()
    release_validation = threading.Event()
    original_validate = publication_repo._validate_database_artifact

    def pause_after_validation(path: Path, manifest):
        original_validate(path, manifest)
        validated.set()
        assert release_validation.wait(10), "Validated owner was not released."

    monkeypatch.setattr(publication_repo, "_validate_database_artifact", pause_after_validation)
    with ThreadPoolExecutor(max_workers=1) as pool:
        owner = pool.submit(
            resolve_financial_generation, root, generation="generation-1",
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )
        try:
            assert validated.wait(10), "The owner must finish artifact validation before the change."
            if change == "manifest":
                original_stat = receipt.manifest_path.stat()
                receipt.manifest_path.write_bytes(receipt.manifest_path.read_bytes().replace(
                    b'"generation":"generation-1"', b'"generation":"generation-x"', 1
                ))
                os.utime(receipt.manifest_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
                error, message = publication_repo.FinancialPublicationInvalid, "manifest"
            elif change == "database":
                original_stat = receipt.database_path.stat()
                _replace_source_value(receipt.database_path, 99)
                os.utime(
                    receipt.database_path,
                    ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1_000_000_000),
                )
                error, message = publication_repo.FinancialPublicationInvalid, "identity"
            elif change == "invalidation":
                invalidate_financial_generation(root, generation="generation-1", reason="Owner revoked")
                error, message = FinancialPublicationUnavailable, "invalidated"
            else:
                real_datetime = publication_repo.datetime

                class ExpiredClock(real_datetime):
                    @classmethod
                    def now(cls, tz=None):
                        value = cls(2100, 1, 1, tzinfo=UTC)
                        return value if tz is not None else value.replace(tzinfo=None)

                monkeypatch.setattr(publication_repo, "datetime", ExpiredClock)
                error, message = FinancialPublicationUnavailable, "expired"
        finally:
            release_validation.set()
        with pytest.raises(error, match=message):
            owner.result(timeout=10)
    assert not publication_repo._VALIDATION_IN_FLIGHT


@pytest.mark.parametrize("change", ["manifest", "database", "invalidation", "expiry"])
def test_waiting_reader_rechecks_artifacts_revocation_and_expiry(
    tmp_path: Path, monkeypatch, change: str
) -> None:
    root, receipt = _cold_validation_fixture(tmp_path, expires_at="2099-01-01T00:00:00+00:00")
    waiting, completed, release_waiter = _observe_validation_waiter(monkeypatch, pause_after_completion=True)
    validator_started = threading.Event()
    release_validation = threading.Event()
    original_validate = publication_repo._validate_database_artifact

    def hold_validation(path: Path, manifest):
        validator_started.set()
        assert release_validation.wait(10)
        original_validate(path, manifest)

    monkeypatch.setattr(publication_repo, "_validate_database_artifact", hold_validation)
    read_generation = partial(
        resolve_financial_generation, root, generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(read_generation)
        try:
            assert validator_started.wait(10)
            waiter = pool.submit(read_generation)
            assert waiting.wait(10)
            release_validation.set()
            assert owner.result(timeout=10).generation == "generation-1"
            assert completed.wait(10)
            if change == "manifest":
                original_stat = receipt.manifest_path.stat()
                changed = receipt.manifest_path.read_bytes().replace(
                    b'"generation":"generation-1"', b'"generation":"generation-x"', 1
                )
                receipt.manifest_path.write_bytes(changed)
                os.utime(receipt.manifest_path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
                error, message = publication_repo.FinancialPublicationInvalid, "pointer"
            elif change == "database":
                original_stat = receipt.database_path.stat()
                _replace_source_value(receipt.database_path, 99)
                os.utime(
                    receipt.database_path,
                    ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1_000_000_000),
                )
                error, message = publication_repo.FinancialPublicationInvalid, "database digest"
            elif change == "invalidation":
                invalidate_financial_generation(root, generation="generation-1", reason="Waiting reader revoked")
                error, message = FinancialPublicationUnavailable, "invalidated"
            else:
                real_datetime = publication_repo.datetime

                class ExpiredClock(real_datetime):
                    @classmethod
                    def now(cls, tz=None):
                        value = cls(2100, 1, 1, tzinfo=UTC)
                        return value if tz is not None else value.replace(tzinfo=None)

                monkeypatch.setattr(publication_repo, "datetime", ExpiredClock)
                error, message = FinancialPublicationUnavailable, "expired"
        finally:
            release_validation.set()
            release_waiter.set()
        with pytest.raises(error, match=message):
            waiter.result(timeout=10)


@pytest.mark.parametrize("generation", [None, "generation-1"], ids=["default", "explicit"])
@pytest.mark.parametrize("pointer_change", ["retained", "discarded", "digest_changed"])
def test_waiting_reader_rechecks_retention_without_following_new_current(
    tmp_path: Path, monkeypatch, generation: str | None, pointer_change: str
) -> None:
    root, _ = _cold_validation_fixture(tmp_path)
    original_pointer = (root / "current.json").read_bytes()
    source = tmp_path / "source.duckdb"
    _publish(source, root, _plan("generation-2", "generation-1"))
    retained_pointer = (root / "current.json").read_bytes()
    _publish(source, root, _plan("generation-3", "generation-2"))
    discarded_pointer = (root / "current.json").read_bytes()
    (root / "current.json").write_bytes(original_pointer)
    publication_repo.reset_financial_publication_validation_cache()
    waiting, completed, release_waiter = _observe_validation_waiter(monkeypatch, pause_after_completion=True)
    validator_started = threading.Event()
    release_validation = threading.Event()
    original_validate = publication_repo._validate_database_artifact

    def hold_validation(path: Path, manifest):
        validator_started.set()
        assert release_validation.wait(10)
        original_validate(path, manifest)

    monkeypatch.setattr(publication_repo, "_validate_database_artifact", hold_validation)
    read_generation = partial(
        resolve_financial_generation, root, generation=generation,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(read_generation)
        try:
            assert validator_started.wait(10)
            waiter = pool.submit(read_generation)
            assert waiting.wait(10)
            release_validation.set()
            assert owner.result(timeout=10).generation == "generation-1"
            assert completed.wait(10)
            if pointer_change == "retained":
                updated_pointer = retained_pointer
            elif pointer_change == "discarded":
                updated_pointer = discarded_pointer
            else:
                payload = json.loads(original_pointer)
                payload["manifest_sha256"] = "0" * 64
                payload["retained_generations"][0]["manifest_sha256"] = "0" * 64
                updated_pointer = publication_repo.canonical_json_bytes(payload)
            (root / "current.json").write_bytes(updated_pointer)
        finally:
            release_validation.set()
            release_waiter.set()
        if pointer_change == "retained":
            assert waiter.result(timeout=10).generation == "generation-1"
        else:
            error = FinancialPublicationUnavailable if pointer_change == "discarded" else publication_repo.FinancialPublicationInvalid
            message = "retention window" if pointer_change == "discarded" else "pointer"
            with pytest.raises(error, match=message):
                waiter.result(timeout=10)


def test_warm_validation_still_reads_and_hashes_manifest_but_reuses_parsed_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    receipt = _publish(source, root, _plan("generation-1", None))
    publication_repo.reset_financial_publication_validation_cache()
    manifest_bytes = receipt.manifest_path.read_bytes()
    real_read_bytes = Path.read_bytes
    real_sha256_bytes = publication_repo.sha256_bytes
    real_parse_json_object = publication_repo._parse_json_object
    manifest_reads: list[Path] = []
    manifest_hashes = 0
    manifest_parses = 0

    def track_read_bytes(path: Path) -> bytes:
        if path == receipt.manifest_path:
            manifest_reads.append(path)
        return real_read_bytes(path)

    def track_sha256_bytes(payload: bytes) -> str:
        nonlocal manifest_hashes
        if payload == manifest_bytes:
            manifest_hashes += 1
        return real_sha256_bytes(payload)

    def track_parse_json_object(payload: bytes, *, label: str) -> dict[str, object]:
        nonlocal manifest_parses
        if label == "publication manifest":
            manifest_parses += 1
        return real_parse_json_object(payload, label=label)

    monkeypatch.setattr(Path, "read_bytes", track_read_bytes)
    monkeypatch.setattr(publication_repo, "sha256_bytes", track_sha256_bytes)
    monkeypatch.setattr(publication_repo, "_parse_json_object", track_parse_json_object)

    resolve_financial_generation(
        root,
        generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    counts_after_first = (len(manifest_reads), manifest_hashes, manifest_parses)
    resolve_financial_generation(
        root,
        generation="generation-1",
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )

    assert counts_after_first == (2, 2, 1)
    assert (len(manifest_reads), manifest_hashes, manifest_parses) == (3, 3, 1)


def test_warm_validation_rejects_same_identity_manifest_tampering(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    receipt = _publish(source, root, _plan("generation-1", None))
    publication_repo.reset_financial_publication_validation_cache()
    resolve_financial_generation(
        root,
        generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    original_stat = receipt.manifest_path.stat()
    tampered = receipt.manifest_path.read_bytes().replace(
        b'"generation":"generation-1"',
        b'"generation":"generation-x"',
        1,
    )
    assert len(tampered) == original_stat.st_size
    receipt.manifest_path.write_bytes(tampered)
    os.utime(
        receipt.manifest_path,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )

    with pytest.raises(publication_repo.FinancialPublicationInvalid, match="pointer"):
        resolve_financial_generation(
            root,
            generation=None,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )


def test_warm_validation_rejects_database_change_after_file_identity_changes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    receipt = _publish(source, root, _plan("generation-1", None))
    publication_repo.reset_financial_publication_validation_cache()
    resolve_financial_generation(
        root,
        generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    original_stat = receipt.database_path.stat()
    _replace_source_value(receipt.database_path, 99)
    os.utime(
        receipt.database_path,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1_000_000_000),
    )

    with pytest.raises(publication_repo.FinancialPublicationInvalid, match="database digest"):
        resolve_financial_generation(
            root,
            generation=None,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )


def test_enabled_global_refresh_runs_publication_as_terminal_step(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from scripts import run_global_data_refresh as refresh

    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    settings = SimpleNamespace(
        duckdb_path=str(source),
        financial_publication_enabled=True,
        financial_publication_root=str(root),
    )
    monkeypatch.setattr(refresh, "get_settings", lambda: settings)
    monkeypatch.setattr(
        refresh,
        "_build_refresh_steps",
        lambda **_: [
            (
                "materialize",
                lambda: {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "source_version": "source-v1",
                },
            ),
            (
                "verify",
                lambda: {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "check_count": 2,
                },
            ),
        ],
    )

    def plan_factory(report_date, _run_id, previous_generation, step_receipts):
        assert report_date == "2026-06-30"
        plan = _plan("generation-1", previous_generation)
        return FinancialPublicationPlan(
            **{
                **plan.__dict__,
                "step_receipts": step_receipts,
            }
        )

    receipt = refresh.run_global_data_refresh(
        report_date="2026-06-30",
        publication_plan_factory=plan_factory,
    )

    assert receipt["status"] == "completed"
    assert [step["name"] for step in receipt["steps"]] == ["materialize", "verify", "publish"]
    assert receipt["steps"][-1]["result"]["generation"] == "generation-1"
    with open_financial_generation(
        root,
        generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    ) as (conn, _):
        assert _value(conn) == 11


def test_enabled_global_refresh_bounds_direct_publication_and_reports_limits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from backend.app.tasks import pnl_by_business_resource_scope as resource_scope_module
    from scripts import run_global_data_refresh as refresh

    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    settings = SimpleNamespace(
        duckdb_path=str(source),
        financial_publication_enabled=True,
        financial_publication_root=str(root),
    )
    monkeypatch.setattr(refresh, "get_settings", lambda: settings)
    monkeypatch.setattr(
        refresh,
        "_build_refresh_steps",
        lambda **_: [
            (
                "materialize",
                lambda: {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "source_version": "source-v1",
                },
            ),
            (
                "verify",
                lambda: {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "check_count": 2,
                },
            ),
        ],
    )
    monkeypatch.setenv(
        resource_scope_module.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
        resource_scope_module.PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
    )

    receipt = refresh.run_global_data_refresh(
        report_date="2026-06-30",
        publication_plan_factory=lambda _date, _run_id, previous, _steps: _plan(
            "generation-bounded",
            previous,
        ),
    )

    publication_result = receipt["steps"][-1]["result"]
    resource_limits = publication_result["resource_limits"]
    assert publication_result["generation"] == "generation-bounded"
    assert resource_limits["profile"] == "bounded_v1"
    assert resource_limits["scope"] == "global_refresh_pnl_by_business_publication"
    assert resource_limits["max_database_instances"] == 2
    assert resource_limits["completed_at_monotonic"] is not None
    assert all(item["threads"] <= 8 for item in resource_limits["observations"])
    assert read_publication_pointer(root)["generation"] == "generation-bounded"  # type: ignore[index]


def test_enabled_global_refresh_resource_failure_does_not_commit_publication(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from backend.app.tasks import pnl_by_business_resource_scope as resource_scope_module
    from scripts import run_global_data_refresh as refresh

    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    _publish(source, root, _plan("generation-before", None))
    settings = SimpleNamespace(
        duckdb_path=str(source),
        financial_publication_enabled=True,
        financial_publication_root=str(root),
    )
    monkeypatch.setattr(refresh, "get_settings", lambda: settings)
    monkeypatch.setattr(
        refresh,
        "_build_refresh_steps",
        lambda **_: [
            (
                "materialize",
                lambda: {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "source_version": "source-v1",
                },
            ),
            (
                "verify",
                lambda: {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "check_count": 2,
                },
            ),
        ],
    )
    monkeypatch.setenv(
        resource_scope_module.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
        resource_scope_module.PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
    )

    def fail_before_pointer(
        scope: resource_scope_module.PnlByBusinessTaskResourceScope,
    ) -> None:
        raise resource_scope_module.PnlByBusinessResourceBudgetExceeded(
            "injected process-tree memory budget breach",
            receipt=scope.receipt(stage="before_pointer_commit"),
        )

    monkeypatch.setattr(
        resource_scope_module.PnlByBusinessTaskResourceScope,
        "freeze_for_pointer_commit",
        fail_before_pointer,
    )

    with pytest.raises(refresh.GlobalDataRefreshFailed) as caught:
        refresh.run_global_data_refresh(
            report_date="2026-06-30",
            publication_plan_factory=lambda _date, _run_id, previous, _steps: _plan(
                "generation-blocked",
                previous,
            ),
        )

    failed_step = caught.value.receipt["steps"][-1]
    assert caught.value.receipt["failed_step"] == "publish"
    assert failed_step["status"] == "failed"
    assert failed_step["failure_category"] == "resource_over_budget"
    assert failed_step["resource_limits"]["stage"] == "before_pointer_commit"
    assert read_publication_pointer(root)["generation"] == "generation-before"  # type: ignore[index]


def test_enabled_refresh_uses_default_page_plan_builder(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from backend.app.tasks import pnl_by_business_page_publication as page_publication
    from scripts import run_global_data_refresh as refresh

    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    settings = SimpleNamespace(
        duckdb_path=str(source),
        financial_publication_enabled=True,
        financial_publication_root=str(root),
    )
    monkeypatch.setattr(refresh, "get_settings", lambda: settings)
    monkeypatch.setattr(
        refresh,
        "_build_refresh_steps",
        lambda **_: [
            (
                "materialize",
                lambda: {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "source_version": "source-v1",
                },
            ),
            (
                "verify",
                lambda: {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "check_count": 2,
                },
            ),
        ],
    )
    builder_calls: list[dict[str, object]] = []

    def default_builder(
        active_settings,
        *,
        report_date,
        run_id,
        expected_previous_generation,
        step_receipts,
    ):
        builder_calls.append(
            {
                "settings": active_settings,
                "report_date": report_date,
                "run_id": run_id,
                "previous": expected_previous_generation,
            }
        )
        plan = _plan("generation-default", expected_previous_generation)
        return FinancialPublicationPlan(
            **{
                **plan.__dict__,
                "step_receipts": step_receipts,
            }
        )

    monkeypatch.setattr(
        page_publication,
        "build_pnl_by_business_financial_publication_plan",
        default_builder,
    )

    receipt = refresh.run_global_data_refresh(report_date="2026-06-30")

    assert receipt["status"] == "completed"
    assert receipt["steps"][-1]["result"]["generation"] == "generation-default"
    assert len(builder_calls) == 1
    assert builder_calls[0]["settings"] is settings
    assert builder_calls[0]["report_date"] == "2026-06-30"
    assert builder_calls[0]["previous"] is None


def test_enabled_refresh_prepare_step_uses_explicit_active_database(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from backend.app.tasks import pnl_by_business_page_publication as page_publication
    from scripts import run_global_data_refresh as refresh

    source = tmp_path / "source.duckdb"
    governance = tmp_path / "governance"
    settings = SimpleNamespace(
        duckdb_path=str(source),
        governance_path=str(governance),
        financial_publication_enabled=True,
    )
    calls: list[dict[str, object]] = []

    def prepare(**kwargs):
        calls.append(kwargs)
        return {"status": "completed", "report_date": kwargs["as_of_date"], "records": 1}

    monkeypatch.setattr(page_publication, "prepare_pnl_by_business_page_envelope", prepare)
    steps = refresh._build_refresh_steps(
        settings=settings,
        report_date="2026-06-30",
        run_id="refresh-run",
        fx_source_path=None,
    )

    step_name, execute = steps[-1]
    result = execute()

    assert step_name == refresh.FINANCIAL_PUBLICATION_PREPARE_STEP_NAME
    assert result["status"] == "completed"
    assert calls == [
        {
            "duckdb_path": str(source),
            "governance_dir": str(governance),
            "year": 2026,
            "as_of_date": "2026-06-30",
            "run_id": "refresh-run:pnl_by_business_page_prepare",
        }
    ]


def test_enabled_refresh_prepare_step_uses_bounded_scope(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from backend.app.tasks import pnl_by_business_page_publication as page_publication
    from backend.app.tasks import pnl_by_business_resource_scope as resource_scope_module
    from scripts import run_global_data_refresh as refresh

    source = tmp_path / "source.duckdb"
    governance = tmp_path / "governance"
    _create_source(source)
    settings = SimpleNamespace(
        duckdb_path=str(source),
        governance_path=str(governance),
        financial_publication_enabled=True,
    )
    calls: list[dict[str, object]] = []

    def prepare(**kwargs):
        calls.append(kwargs)
        scope = kwargs["resource_scope"]
        assert kwargs["writer_lock_already_held"] is True
        assert scope.database_connection(source) is not None
        return {"status": "completed", "report_date": kwargs["as_of_date"], "records": 1}

    monkeypatch.setenv(
        resource_scope_module.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
        resource_scope_module.PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
    )
    monkeypatch.setattr(page_publication, "prepare_pnl_by_business_page_envelope", prepare)
    steps = refresh._build_refresh_steps(
        settings=settings,
        report_date="2026-06-30",
        run_id="refresh-run",
        fx_source_path=None,
    )

    step_name, execute = steps[-1]
    result = execute()

    assert step_name == refresh.FINANCIAL_PUBLICATION_PREPARE_STEP_NAME
    assert len(calls) == 1
    assert result["resource_limits"]["profile"] == "bounded_v1"
    assert result["resource_limits"]["scope"] == (
        "global_refresh_pnl_by_business_page_prepare"
    )
    assert result["resource_limits"]["max_database_instances"] == 1
    assert result["resource_limits"]["completed_at_monotonic"] is not None


@pytest.mark.parametrize("stored_ftp_rate", ["2", "2.0", "2.000"])
def test_actual_page_prepare_builder_and_publisher_use_ready_dependency_cutoffs(
    tmp_path: Path,
    monkeypatch,
    stored_ftp_rate: str,
) -> None:
    from types import SimpleNamespace

    from backend.app.tasks import pnl_by_business_page_publication as page_publication
    from backend.app.tasks import pnl_by_business_resource_scope as resource_scope_module

    monkeypatch.setattr(resource_scope_module.os, "cpu_count", lambda: 16)
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    governance = tmp_path / "governance"
    governance.mkdir()
    monkeypatch.setenv(
        resource_scope_module.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
        resource_scope_module.PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
    )
    conn = duckdb.connect(str(source))
    try:
        conn.execute(
            """
            create table fact_pnl_by_business_precompute_cutoff_state (
                scope_key varchar,
                year integer,
                as_of_date date,
                required_event_revision bigint,
                prepared_event_revision bigint,
                status varchar,
                source_version varchar,
                rule_version varchar,
                effective_ftp_rate_pct varchar,
                supplemental_source_version varchar,
                protocol_version varchar
            )
            """
        )
        for dependency_year, cutoff in (
            (2026, "2026-06-30"),
            (2025, "2025-06-30"),
            (2025, "2025-12-31"),
        ):
            conn.execute(
                "insert into fact_pnl_by_business_precompute_cutoff_state values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    page_publication.PNL_BY_BUSINESS_PRECOMPUTE_SCOPE,
                    dependency_year,
                    cutoff,
                    7,
                    7,
                    "ready",
                    f"source-{cutoff}",
                    page_publication.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
                    stored_ftp_rate,
                    "adjustments-v1",
                    "pnl-precompute/v1",
                ],
            )
    finally:
        conn.close()

    snapshot_threads: list[int] = []

    def dependency_snapshot(*, duckdb_path, dependencies, **_):
        read_connection = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            snapshot_threads.append(
                int(
                    read_connection.execute(
                        "select current_setting('threads')"
                    ).fetchone()[0]
                )
            )
        finally:
            read_connection.close()
        return tuple(
            {
                "key": str(item["key"]),
                "year": int(item["year"]),
                "requested_report_date": str(item["requested_report_date"]),
                "resolved_report_date": str(item["requested_report_date"]),
                "dependency_revision": 7,
                "source_version": f"source-{item['requested_report_date']}",
                "rule_version": page_publication.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
                "ftp_rate_pct": "2.0",
                "adjustment_version": "adjustments-v1",
                "protocol_version": "pnl-precompute/v1",
            }
            for item in dependencies
        )

    envelope = {
        "result": {"year": 2026, "as_of_date": "2026-06-30", "items": []},
        "result_meta": {
            "resolved_report_date": "2026-06-30",
            "result_kind": "pnl.by_business_insights",
            "formal_use_allowed": True,
            "source_version": "source-2026-06-30",
        },
    }
    monkeypatch.setattr(page_publication, "_dependency_snapshot", dependency_snapshot)
    monkeypatch.setattr(page_publication, "pnl_by_business_insights_envelope", lambda **_: envelope)
    monkeypatch.setattr(
        page_publication,
        "require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    settings = SimpleNamespace(
        duckdb_path=str(source),
        governance_path=str(governance),
        ftp_rate_pct=Decimal("2.0"),
        financial_publication_enabled=True,
        financial_publication_root=str(root),
    )
    prepare_receipt = page_publication.prepare_pnl_by_business_page_envelope(
        settings,
        report_date="2026-06-30",
        run_id="page-prepare",
    )
    prepare_step_only = (
        {
            "name": page_publication.PNL_BY_BUSINESS_PAGE_JOB_NAME,
            "status": "completed",
            "result": prepare_receipt,
        },
    )
    with pytest.raises(RuntimeError, match="complete ordered global refresh receipts"):
        page_publication.build_pnl_by_business_financial_publication_plan(
            settings,
            report_date="2026-06-30",
            run_id="partial-global-run",
            expected_previous_generation=None,
            step_receipts=prepare_step_only,
        )
    bad_dependencies = dict(prepare_receipt["dependency_versions"])
    bad_dependencies["pnl_by_business.current_ytd.source_version"] = "stale-source"
    with pytest.raises(RuntimeError, match="does not match the prepared page lineage"):
        page_publication.build_pnl_by_business_page_only_financial_publication_plan(
            settings,
            report_date="2026-06-30",
            run_id="page-prepare",
            expected_previous_generation=None,
            prepare_receipt={**prepare_receipt, "dependency_versions": bad_dependencies},
        )
    step_receipts = tuple(
        {
            "name": step_name,
            "status": "completed",
            "result": (
                prepare_receipt
                if step_name == page_publication.PNL_BY_BUSINESS_PAGE_JOB_NAME
                else {
                    "status": "completed",
                    "report_date": "2026-06-30",
                    "evidence": f"synthetic-{step_name}",
                }
            ),
        }
        for step_name in page_publication.PNL_BY_BUSINESS_FINANCIAL_PUBLICATION_REQUIRED_STEPS
    )
    plan = page_publication.build_pnl_by_business_financial_publication_plan(
        settings,
        report_date="2026-06-30",
        run_id="refresh-run",
        expected_previous_generation=None,
        step_receipts=step_receipts,
    )

    receipt = publish_financial_result(
        source_duckdb_path=source,
        publication_root=root,
        plan=plan,
    )

    assert receipt.status == "published"
    assert set(plan.coverage_dates) == {"pnl_by_business_page"}
    assert "pnl_by_business_page.payload_sha256" in plan.required_dependency_keys
    with open_financial_generation(
        root,
        generation=receipt.generation,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    ) as (published, _):
        row = published.execute(
            f"select payload_json from {page_publication.PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE}"
        ).fetchone()
        assert json.loads(str(row[0])) == envelope

    stale_plan = page_publication.build_pnl_by_business_financial_publication_plan(
        settings,
        report_date="2026-06-30",
        run_id="stale-after-plan",
        expected_previous_generation=receipt.generation,
        step_receipts=step_receipts,
    )
    conn = duckdb.connect(str(source))
    try:
        conn.execute(
            """
            update fact_pnl_by_business_precompute_cutoff_state
            set required_event_revision = required_event_revision + 1, status = 'dirty'
            where year = 2026 and as_of_date = date '2026-06-30'
            """
        )
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="dependency state is stale"):
        publish_financial_result(
            source_duckdb_path=source,
            publication_root=root,
            plan=stale_plan,
        )
    conn = duckdb.connect(str(source))
    try:
        conn.execute(
            """
            update fact_pnl_by_business_precompute_cutoff_state
            set required_event_revision = prepared_event_revision, status = 'ready'
            where year = 2026 and as_of_date = date '2026-06-30'
            """
        )
    finally:
        conn.close()

    conn = duckdb.connect(str(source))
    try:
        conn.execute(
            """
            update fact_pnl_by_business_precompute_cutoff_state
            set effective_ftp_rate_pct = '2.01'
            where year = 2026 and as_of_date = date '2026-06-30'
            """
        )
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="dependency state is stale"):
        publish_financial_result(
            source_duckdb_path=source,
            publication_root=root,
            plan=stale_plan,
        )
    conn = duckdb.connect(str(source))
    try:
        conn.execute(
            """
            update fact_pnl_by_business_precompute_cutoff_state
            set effective_ftp_rate_pct = ?
            where year = 2026 and as_of_date = date '2026-06-30'
            """,
            [stored_ftp_rate],
        )
    finally:
        conn.close()

    monkeypatch.setattr(page_publication, "get_settings", lambda: settings)
    page_only = page_publication._prepare_pnl_by_business_page_envelope_actor(
        duckdb_path=str(source),
        governance_dir=str(governance),
        year=2026,
        as_of_date="2026-06-30",
        expected_previous_generation=receipt.generation,
        run_id="page-only-run",
    )
    repeated = page_publication._prepare_pnl_by_business_page_envelope_actor(
        duckdb_path=str(source),
        governance_dir=str(governance),
        year=2026,
        as_of_date="2026-06-30",
        expected_previous_generation=receipt.generation,
        run_id="page-only-run",
    )

    assert page_only["publication_status"] == "published"
    assert page_only["generation"] != receipt.generation
    assert repeated["publication_status"] == "already_published"
    assert repeated["generation"] == page_only["generation"]
    assert snapshot_threads[-2:] == [8, 8]
    assert read_publication_pointer(root)["generation"] == page_only["generation"]  # type: ignore[index]

    predecessor_after_resource_failure = str(page_only["generation"])
    resource_failure_run_id = "page-only-resource-over-budget"
    original_freeze = resource_scope_module.PnlByBusinessTaskResourceScope.freeze_for_pointer_commit

    def fail_at_pointer_budget(
        resource_scope: resource_scope_module.PnlByBusinessTaskResourceScope,
    ) -> None:
        raise resource_scope_module.PnlByBusinessResourceBudgetExceeded(
            "injected process-tree memory budget breach",
            receipt=resource_scope.receipt(stage="before_pointer_commit"),
        )

    monkeypatch.setattr(
        resource_scope_module.PnlByBusinessTaskResourceScope,
        "freeze_for_pointer_commit",
        fail_at_pointer_budget,
    )
    resource_failure = page_publication._prepare_pnl_by_business_page_envelope_actor(
        duckdb_path=str(source),
        governance_dir=str(governance),
        year=2026,
        as_of_date="2026-06-30",
        expected_previous_generation=predecessor_after_resource_failure,
        run_id=resource_failure_run_id,
    )
    failed_generation = page_publication._publication_generation(
        report_date="2026-06-30",
        run_id=resource_failure_run_id,
    )
    assert resource_failure["status"] == "failed"
    assert resource_failure["failure_category"] == "resource_over_budget"
    assert publication_repo.generation_database_path(root, failed_generation).is_file()
    assert read_publication_pointer(root)["generation"] == predecessor_after_resource_failure  # type: ignore[index]
    resource_limits = resource_failure["resource_limits"]
    assert resource_limits["max_database_instances"] == 2
    assert resource_limits["per_database_memory_budget_bytes"] * 2 <= resource_limits[
        "duckdb_memory_budget_bytes"
    ]
    assert all(item["threads"] <= 8 for item in resource_limits["observations"])

    monkeypatch.delenv(resource_scope_module.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV)
    durable_retry = page_publication._prepare_pnl_by_business_page_envelope_actor(
        duckdb_path=str(source),
        governance_dir=str(governance),
        year=2026,
        as_of_date="2026-06-30",
        expected_previous_generation=predecessor_after_resource_failure,
        run_id=resource_failure_run_id,
    )
    assert durable_retry["run_id"] == resource_failure["run_id"]
    assert durable_retry["failure_category"] == "resource_over_budget"
    assert durable_retry["resource_limits"] == resource_failure["resource_limits"]
    assert read_publication_pointer(root)["generation"] == predecessor_after_resource_failure  # type: ignore[index]
    monkeypatch.setenv(
        resource_scope_module.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
        resource_scope_module.PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
    )
    monkeypatch.setattr(
        resource_scope_module.PnlByBusinessTaskResourceScope,
        "freeze_for_pointer_commit",
        original_freeze,
    )
    monkeypatch.setattr(
        page_publication,
        "require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("governance stale")),
    )
    with pytest.raises(RuntimeError, match="governance stale"):
        page_publication._prepare_pnl_by_business_page_envelope_actor(
            duckdb_path=str(source),
            governance_dir=str(governance),
            year=2026,
            as_of_date="2026-06-30",
            expected_previous_generation=receipt.generation,
            run_id="page-only-run",
        )
    monkeypatch.setattr(
        page_publication,
        "require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )

    predecessor = str(page_only["generation"])
    real_publish = page_publication.publish_financial_result
    monkeypatch.setattr(
        page_publication,
        "publish_financial_result",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("crash before publication")),
    )
    with pytest.raises(RuntimeError, match="crash before publication"):
        page_publication._prepare_pnl_by_business_page_envelope_actor(
            duckdb_path=str(source),
            governance_dir=str(governance),
            year=2026,
            as_of_date="2026-06-30",
            expected_previous_generation=predecessor,
            run_id="older-page-intent",
        )
    monkeypatch.setattr(page_publication, "publish_financial_result", real_publish)
    newer = page_publication._prepare_pnl_by_business_page_envelope_actor(
        duckdb_path=str(source),
        governance_dir=str(governance),
        year=2026,
        as_of_date="2026-06-30",
        expected_previous_generation=predecessor,
        run_id="newer-page-intent",
    )
    with pytest.raises(FinancialPublicationConflict, match="predecessor"):
        page_publication._prepare_pnl_by_business_page_envelope_actor(
            duckdb_path=str(source),
            governance_dir=str(governance),
            year=2026,
            as_of_date="2026-06-30",
            expected_previous_generation=predecessor,
            run_id="older-page-intent",
        )

    assert read_publication_pointer(root)["generation"] == newer["generation"]  # type: ignore[index]
    invalidate_financial_generation(
        root,
        generation=str(newer["generation"]),
        reason="superseded source approval",
    )
    replacement = page_publication._prepare_pnl_by_business_page_envelope_actor(
        duckdb_path=str(source),
        governance_dir=str(governance),
        year=2026,
        as_of_date="2026-06-30",
        expected_previous_generation=str(newer["generation"]),
        run_id="replacement-after-revocation",
    )

    assert replacement["publication_status"] == "published"
    assert read_publication_pointer(root)["generation"] == replacement["generation"]  # type: ignore[index]

    monkeypatch.delenv(resource_scope_module.PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV)
    failed_dependency_revision = page_publication.PnlRepository(
        str(source)
    ).pnl_by_business_precompute_dependency_revision(
        year=2026,
        as_of_date="2026-06-30",
    )
    precompute_failure = {
        "run_id": "precompute-resource-strong-kill",
        "job_name": "pnl_by_business_precompute",
        "status": "failed",
        "failure_category": "resource_over_budget",
        "target_year": 2026,
        "dependency_revision": failed_dependency_revision,
        "report_date": "2026-06-30",
        "resource_limits": {"profile": "bounded_v1", "stage": "memory_sample"},
    }
    page_publication.GovernanceRepository(base_dir=governance).append(
        page_publication.CACHE_BUILD_RUN_STREAM,
        precompute_failure,
    )
    cutoff_state = duckdb.connect(str(source), read_only=True)
    try:
        assert cutoff_state.execute(
            "select status from fact_pnl_by_business_precompute_cutoff_state "
            "where year = 2026 and as_of_date = date '2026-06-30'"
        ).fetchone() == ("ready",)
    finally:
        cutoff_state.close()
    predecessor_before_dependency_failure = str(replacement["generation"])
    blocked_by_dependency = page_publication._prepare_pnl_by_business_page_envelope_actor(
        duckdb_path=str(source),
        governance_dir=str(governance),
        year=2026,
        as_of_date="2026-06-30",
        expected_previous_generation=predecessor_before_dependency_failure,
        run_id="new-page-after-precompute-resource-strong-kill",
    )

    assert blocked_by_dependency["status"] == "failed"
    assert blocked_by_dependency["failure_category"] == "resource_over_budget"
    assert blocked_by_dependency["dependency_run_id"] == precompute_failure["run_id"]
    assert read_publication_pointer(root)["generation"] == predecessor_before_dependency_failure  # type: ignore[index]


def test_existing_writer_connection_path_avoids_nested_lock_acquisition(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    _create_source(source)
    writer_lock = resolve_duckdb_writer_lock(source)

    with acquire_lock(writer_lock, base_dir=source.parent):
        conn = duckdb.connect(str(source), read_only=False)
        try:
            receipt = publish_financial_result(
                source_duckdb_path=source,
                publication_root=root,
                plan=_plan("generation-1", None),
                writer_lock_already_held=True,
                source_connection=conn,
            )
        finally:
            conn.close()

    assert receipt.status == "published"
    with open_financial_generation(
        root,
        generation=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    ) as (published, _):
        assert _value(published) == 11


def test_separate_reader_process_uses_published_file_while_source_writer_is_active(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    ready = tmp_path / "writer.ready"
    release = tmp_path / "writer.release"
    _create_source(source)
    _publish(source, root, _plan("generation-1", None))
    writer_code = "\n".join(
        [
            "import os, time, duckdb",
            "from pathlib import Path",
            "source=Path(os.environ['MOSS_TEST_SOURCE'])",
            "ready=Path(os.environ['MOSS_TEST_READY'])",
            "release=Path(os.environ['MOSS_TEST_RELEASE'])",
            "conn=duckdb.connect(str(source), read_only=False)",
            "conn.execute('BEGIN TRANSACTION')",
            "conn.execute('UPDATE fact_result SET value=77')",
            "ready.write_text('ready', encoding='utf-8')",
            "deadline=time.monotonic()+15",
            "while not release.exists() and time.monotonic()<deadline: time.sleep(0.02)",
            "conn.execute('ROLLBACK')",
            "conn.close()",
        ]
    )
    env = {
        **os.environ,
        "MOSS_TEST_SOURCE": str(source),
        "MOSS_TEST_READY": str(ready),
        "MOSS_TEST_RELEASE": str(release),
    }
    writer = subprocess.Popen(
        [sys.executable, "-c", writer_code],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), writer.stderr.read() if writer.stderr else "writer did not start"
        reader_code = "\n".join(
            [
                "import os",
                "from backend.app.repositories.financial_result_publication_repo import open_financial_generation",
                "with open_financial_generation(os.environ['MOSS_TEST_ROOT'], generation=None, reader_api_version='financial-api/v1', reader_schema_version='financial-results/v1') as pair:",
                " print(pair[0].execute('select value from fact_result').fetchone()[0])",
            ]
        )
        reader = subprocess.run(
            [sys.executable, "-c", reader_code],
            cwd=Path(__file__).resolve().parents[1],
            env={**env, "MOSS_TEST_ROOT": str(root)},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert reader.returncode == 0, reader.stderr
        assert reader.stdout.strip() == "11"
    finally:
        release.write_text("release", encoding="utf-8")
        stdout, stderr = writer.communicate(timeout=10)
        assert writer.returncode == 0, f"{stdout}\n{stderr}"


def test_concurrent_publishers_with_same_expected_previous_have_one_cas_winner(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "published"
    gate = tmp_path / "publish.gate"
    _create_source(source)
    _publish(source, root, _plan("generation-1", None))
    child_code = "\n".join(
        [
            "import json, os, time",
            "from pathlib import Path",
            "import duckdb",
            "from backend.app.tasks.financial_result_publication import FinancialPublicationPlan, FinancialTablePublicationSpec, publish_financial_result, FinancialPublicationConflict",
            "def versions(conn): return {str(k):str(v) for k,v in conn.execute('select name, version from publication_dependency_state order by name').fetchall()}",
            "ready=Path(os.environ['MOSS_TEST_READY']); gate=Path(os.environ['MOSS_TEST_GATE'])",
            "ready.write_text('ready', encoding='utf-8')",
            "deadline=time.monotonic()+15",
            "while not gate.exists() and time.monotonic()<deadline: time.sleep(0.02)",
            "plan=FinancialPublicationPlan(generation=os.environ['MOSS_TEST_GENERATION'], expected_previous_generation='generation-1', tables=(FinancialTablePublicationSpec(name='fact_result', date_column='report_date', required_dates=('2026-06-30',)), FinancialTablePublicationSpec(name='dim_scope')), required_steps=('materialize','verify'), step_receipts=({'name':'materialize','status':'completed','result':{'status':'completed','report_date':'2026-06-30','source_version':'source-v1'}},{'name':'verify','status':'completed','result':{'status':'completed','report_date':'2026-06-30','check_count':2}}), required_dependency_keys=('source','rules','adjustments'), dependency_versions={'source':'source-v1','rules':'rules-v3','adjustments':'adjustments-v2'}, coverage_dates={'current':('2026-06-30',)}, supported_api_versions=('financial-api/v1',), supported_schema_versions=('financial-results/v1',), quality={'status':'passed','checks':({'name':'coverage','status':'passed'},)}, source_dependency_validator=versions)",
            "try:",
            " receipt=publish_financial_result(source_duckdb_path=os.environ['MOSS_TEST_SOURCE'], publication_root=os.environ['MOSS_TEST_ROOT'], plan=plan)",
            " print(json.dumps({'status':receipt.status,'generation':receipt.generation}))",
            "except FinancialPublicationConflict as exc:",
            " print(json.dumps({'status':'conflict','generation':os.environ['MOSS_TEST_GENERATION'],'error':str(exc)}))",
        ]
    )
    children: list[subprocess.Popen[str]] = []
    ready_paths = [tmp_path / "publisher-a.ready", tmp_path / "publisher-b.ready"]
    base_env = {
        **os.environ,
        "MOSS_TEST_SOURCE": str(source),
        "MOSS_TEST_ROOT": str(root),
        "MOSS_TEST_GATE": str(gate),
    }
    for generation, ready_path in zip(("generation-2a", "generation-2b"), ready_paths, strict=True):
        children.append(
            subprocess.Popen(
                [sys.executable, "-c", child_code],
                cwd=Path(__file__).resolve().parents[1],
                env={
                    **base_env,
                    "MOSS_TEST_GENERATION": generation,
                    "MOSS_TEST_READY": str(ready_path),
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    deadline = time.monotonic() + 10
    while not all(path.exists() for path in ready_paths) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert all(path.exists() for path in ready_paths)
    gate.write_text("go", encoding="utf-8")
    results = []
    for child in children:
        stdout, stderr = child.communicate(timeout=20)
        assert child.returncode == 0, stderr
        results.append(json.loads(stdout))

    assert sorted(result["status"] for result in results) == ["conflict", "published"]
    winner = next(result["generation"] for result in results if result["status"] == "published")
    assert read_publication_pointer(root)["generation"] == winner  # type: ignore[index]
