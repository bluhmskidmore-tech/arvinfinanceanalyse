from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import duckdb
import pytest

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)


def _history_result(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "completed",
        "run_id": "choice_stock_materialize:2026-07-08:fixture",
        "as_of_date": "2026-07-08",
        "row_count": 321,
        "stock_code_count": 107,
        "source_version": "sv_choice_stock_fixture",
        "vendor_version": "vv_choice_stock_fixture",
    }
    result.update(overrides)
    return result


def _completed_payload(
    *,
    run_id: str,
    report_date: str,
    cache_key: str = "choice_stock.history_and_factor_snapshot",
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "job_name": "choice_stock_refresh",
        "status": "completed",
        "cache_key": cache_key,
        "cache_version": "choice_stock_refresh_v1",
        "lock": "lock:choice_stock_refresh",
        "source_version": "sv_factor_fixture",
        "vendor_version": "vv_factor_fixture",
        "rule_version": "rv_choice_stock_materialization_front_layer_v1",
        "report_date": report_date,
        "created_at": f"{report_date}T23:30:00Z",
    }


def _observation_manifest(
    *,
    report_date: str,
    refresh_run_id: str,
    created_at: str,
) -> dict[str, object]:
    from backend.app.tasks.choice_stock_observation_manifest import (
        build_choice_stock_observation_manifest,
    )

    return build_choice_stock_observation_manifest(
        history_result=_history_result(
            run_id=f"choice_stock_materialize:{report_date}:fixture",
            as_of_date=report_date,
            source_version=f"sv_choice_stock_{report_date}",
            vendor_version=f"vv_choice_stock_{report_date}",
        ),
        refresh_run_id=refresh_run_id,
        report_date=report_date,
        daily_observation_row_count=107,
        created_at=created_at,
    )


def test_choice_stock_observation_manifest_preserves_actual_materialization_lineage() -> (
    None
):
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        build_choice_stock_observation_manifest,
    )

    manifest = build_choice_stock_observation_manifest(
        history_result=_history_result(),
        refresh_run_id="choice_stock_refresh:2026-07-08:fixture",
        report_date="2026-07-08",
        daily_observation_row_count=107,
        created_at="2026-07-08T23:00:00Z",
    )

    assert manifest["cache_key"] == CHOICE_STOCK_OBSERVATION_CACHE_KEY
    assert manifest["report_date"] == "2026-07-08"
    assert manifest["source_version"] == "sv_choice_stock_fixture"
    assert manifest["vendor_version"] == "vv_choice_stock_fixture"
    assert manifest["run_id"] == "choice_stock_refresh:2026-07-08:fixture"
    assert manifest["fact_tables"] == ["choice_stock_daily_observation"]
    assert manifest["lineage"] == {
        "materialization_run_id": "choice_stock_materialize:2026-07-08:fixture",
        "refresh_run_id": "choice_stock_refresh:2026-07-08:fixture",
        "materialization_status": "completed",
        "daily_observation_report_date": "2026-07-08",
        "daily_observation_row_count": 107,
        "materialized_row_count": 321,
        "stock_code_count": 107,
    }


@pytest.mark.parametrize(
    ("overrides", "report_date"),
    [
        ({"status": "partial"}, "2026-07-08"),
        ({"as_of_date": "2026-07-07"}, "2026-07-08"),
        ({"run_id": ""}, "2026-07-08"),
        ({"source_version": ""}, "2026-07-08"),
        ({"vendor_version": ""}, "2026-07-08"),
        ({"row_count": 0}, "2026-07-08"),
        ({"stock_code_count": 0}, "2026-07-08"),
    ],
)
def test_choice_stock_observation_manifest_rejects_untrustworthy_materialization(
    overrides: dict[str, object],
    report_date: str,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        build_choice_stock_observation_manifest,
    )

    with pytest.raises(ValueError):
        build_choice_stock_observation_manifest(
            history_result=_history_result(**overrides),
            refresh_run_id="choice_stock_refresh:2026-07-08:fixture",
            report_date=report_date,
            daily_observation_row_count=107,
            created_at="2026-07-08T23:00:00Z",
        )


def test_choice_stock_observation_manifest_verifies_matching_landed_rows(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        verify_choice_stock_daily_observation_landing,
    )

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-07-08",
                    "000001.SZ",
                    "sv_choice_stock_fixture",
                    "vv_choice_stock_fixture",
                    "rv_choice_stock_materialization_front_layer_v1",
                    "choice_stock_materialize:2026-07-08:fixture",
                ),
                (
                    "2026-07-08",
                    "000002.SZ",
                    "sv_other",
                    "vv_other",
                    "rv_choice_stock_materialization_front_layer_v1",
                    "other-run",
                ),
            ],
        )
    finally:
        conn.close()

    count = verify_choice_stock_daily_observation_landing(
        duckdb_path=db_path,
        history_result=_history_result(),
        report_date="2026-07-08",
    )
    assert count == 1
    with pytest.raises(ValueError):
        verify_choice_stock_daily_observation_landing(
            duckdb_path=db_path,
            history_result=_history_result(source_version="sv_missing"),
            report_date="2026-07-08",
        )


def test_choice_stock_refresh_appends_completed_run_and_observation_manifest_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import macro_toolkit_service
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    )

    governance_path = tmp_path / "governance"
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: _history_result(),
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_factor_snapshot",
        lambda **_kwargs: {
            "status": "completed",
            "row_count": 107,
            "source_version": "sv_factor_fixture",
            "vendor_version": "vv_factor_fixture",
        },
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 107,
    )

    macro_toolkit_service._run_choice_stock_refresh_job(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "catalog.json"),
        governance_path=str(governance_path),
        run_id="choice_stock_refresh:2026-07-08:fixture",
        as_of_date="2026-07-08",
        queued_at="2026-07-08T22:59:00Z",
        refresh_history=True,
        refresh_factors=True,
        factor_max_stock_count=None,
        permission={"mode": "fixture"},
    )

    repo = GovernanceRepository(base_dir=governance_path)
    runs = [
        row
        for row in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if row.get("run_id") == "choice_stock_refresh:2026-07-08:fixture"
    ]
    assert [row["status"] for row in runs] == ["running", "completed"]
    manifest = repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    assert manifest is not None
    assert manifest["report_date"] == "2026-07-08"
    assert manifest["source_version"] == "sv_choice_stock_fixture"
    assert manifest["vendor_version"] == "vv_choice_stock_fixture"


def test_choice_stock_refresh_does_not_record_completed_when_manifest_append_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import macro_toolkit_service
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    )

    governance_path = tmp_path / "governance"
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: _history_result(),
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_factor_snapshot",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 107,
    )
    original_append_many = GovernanceRepository.append_many_atomic

    def fail_completion_batch(self, entries):  # type: ignore[no-untyped-def]
        if any(stream == "cache_manifest" for stream, _payload in entries):
            raise OSError("fixture manifest append failed")
        return original_append_many(self, entries)

    monkeypatch.setattr(
        GovernanceRepository, "append_many_atomic", fail_completion_batch
    )

    with pytest.raises(OSError, match="fixture manifest append failed"):
        macro_toolkit_service._run_choice_stock_refresh_job(
            duckdb_path=str(tmp_path / "moss.duckdb"),
            catalog_path=str(tmp_path / "catalog.json"),
            governance_path=str(governance_path),
            run_id="choice_stock_refresh:2026-07-08:failure-fixture",
            as_of_date="2026-07-08",
            queued_at="2026-07-08T22:59:00Z",
            refresh_history=True,
            refresh_factors=False,
            factor_max_stock_count=None,
            permission={"mode": "fixture"},
        )

    repo = GovernanceRepository(base_dir=governance_path)
    runs = [
        row
        for row in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if row.get("run_id") == "choice_stock_refresh:2026-07-08:failure-fixture"
    ]
    assert [row["status"] for row in runs] == ["running", "retrying"]
    assert runs[-1]["retryable"] is True
    assert repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY) is None


def test_factor_only_choice_stock_refresh_does_not_fabricate_observation_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import macro_toolkit_service
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    )

    governance_path = tmp_path / "governance"
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: pytest.fail("history materialization must stay disabled"),
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_factor_snapshot",
        lambda **_kwargs: {
            "status": "completed",
            "row_count": 107,
            "source_version": "sv_factor_fixture",
            "vendor_version": "vv_factor_fixture",
        },
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: pytest.fail(
            "factor-only refresh must not verify history landing"
        ),
    )

    macro_toolkit_service._run_choice_stock_refresh_job(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "catalog.json"),
        governance_path=str(governance_path),
        run_id="choice_stock_refresh:2026-07-08:factor-only",
        as_of_date="2026-07-08",
        queued_at="2026-07-08T22:59:00Z",
        refresh_history=False,
        refresh_factors=True,
        factor_max_stock_count=None,
        permission={"mode": "fixture"},
    )

    repo = GovernanceRepository(base_dir=governance_path)
    runs = [
        row
        for row in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if row.get("run_id") == "choice_stock_refresh:2026-07-08:factor-only"
    ]
    assert [row["status"] for row in runs] == ["running", "completed"]
    assert repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY) is None


def test_historical_choice_stock_refresh_does_not_regress_latest_observation_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import macro_toolkit_service
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        build_choice_stock_observation_manifest,
    )

    governance_path = tmp_path / "governance"
    repo = GovernanceRepository(base_dir=governance_path)
    newer_manifest = build_choice_stock_observation_manifest(
        history_result=_history_result(
            run_id="choice_stock_materialize:2026-07-09:newer",
            as_of_date="2026-07-09",
            source_version="sv_choice_stock_newer",
            vendor_version="vv_choice_stock_newer",
        ),
        refresh_run_id="choice_stock_refresh:2026-07-09:newer",
        report_date="2026-07-09",
        daily_observation_row_count=107,
        created_at="2026-07-09T23:00:00Z",
    )
    repo.append("cache_manifest", newer_manifest)
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: _history_result(),
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 107,
    )

    macro_toolkit_service._run_choice_stock_refresh_job(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        catalog_path=str(tmp_path / "catalog.json"),
        governance_path=str(governance_path),
        run_id="choice_stock_refresh:2026-07-08:historical",
        as_of_date="2026-07-08",
        queued_at="2026-07-08T22:59:00Z",
        refresh_history=True,
        refresh_factors=False,
        factor_max_stock_count=None,
        permission={"mode": "fixture"},
    )

    latest = repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    assert latest is not None
    assert latest["report_date"] == "2026-07-09"
    assert latest["source_version"] == "sv_choice_stock_newer"
    runs = [
        row
        for row in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if row.get("run_id") == "choice_stock_refresh:2026-07-08:historical"
    ]
    assert [row["status"] for row in runs] == ["running", "completed"]


def test_same_day_older_manifest_created_at_does_not_replace_newer_lineage(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        append_choice_stock_refresh_completion,
    )

    repo = GovernanceRepository(base_dir=tmp_path / "governance")
    newer_run_id = "choice_stock_refresh:2026-07-08:newer"
    older_run_id = "choice_stock_refresh:2026-07-08:older"
    append_choice_stock_refresh_completion(
        governance_repo=repo,
        completed_run_payload=_completed_payload(
            run_id=newer_run_id,
            report_date="2026-07-08",
        ),
        observation_manifest=_observation_manifest(
            report_date="2026-07-08",
            refresh_run_id=newer_run_id,
            created_at="2026-07-08T23:00:00Z",
        ),
    )
    appended = append_choice_stock_refresh_completion(
        governance_repo=repo,
        completed_run_payload=_completed_payload(
            run_id=older_run_id,
            report_date="2026-07-08",
        ),
        observation_manifest=_observation_manifest(
            report_date="2026-07-08",
            refresh_run_id=older_run_id,
            created_at="2026-07-08T22:00:00Z",
        ),
    )

    assert appended is False
    latest = repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    assert latest is not None
    assert latest["run_id"] == newer_run_id
    assert latest["created_at"] == "2026-07-08T23:00:00Z"


def test_same_timestamp_uses_run_id_as_deterministic_tie_breaker(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        append_choice_stock_refresh_completion,
    )

    repo = GovernanceRepository(base_dir=tmp_path / "governance")
    preferred_run_id = "choice_stock_refresh:2026-07-08:z"
    rejected_run_id = "choice_stock_refresh:2026-07-08:a"
    append_choice_stock_refresh_completion(
        governance_repo=repo,
        completed_run_payload=_completed_payload(
            run_id=preferred_run_id,
            report_date="2026-07-08",
        ),
        observation_manifest=_observation_manifest(
            report_date="2026-07-08",
            refresh_run_id=preferred_run_id,
            created_at="2026-07-08T23:00:00Z",
        ),
    )

    appended = append_choice_stock_refresh_completion(
        governance_repo=repo,
        completed_run_payload=_completed_payload(
            run_id=rejected_run_id,
            report_date="2026-07-08",
        ),
        observation_manifest=_observation_manifest(
            report_date="2026-07-08",
            refresh_run_id=rejected_run_id,
            created_at="2026-07-08T23:00:00Z",
        ),
    )

    assert appended is False
    latest = repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    assert latest is not None
    assert latest["run_id"] == preferred_run_id


@pytest.mark.parametrize(
    ("completed_overrides", "manifest_overrides"),
    [
        ({"run_id": "choice_stock_refresh:other"}, {}),
        ({"cache_key": "wrong-cache"}, {}),
        ({"cache_version": "wrong-version"}, {}),
        ({"rule_version": "wrong-rule"}, {}),
        ({"report_date": "2026-07-09"}, {}),
        ({}, {"run_id": "choice_stock_refresh:other"}),
        ({}, {"cache_version": "wrong-version"}),
        ({}, {"rule_version": "wrong-rule"}),
        ({}, {"fact_tables": ["wrong_table"]}),
        ({}, {"created_at": None}),
        ({}, {"report_date": "2026-07-09"}),
    ],
)
def test_completion_and_observation_manifest_must_describe_the_same_refresh(
    tmp_path: Path,
    completed_overrides: dict[str, object],
    manifest_overrides: dict[str, object],
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        append_choice_stock_refresh_completion,
    )

    run_id = "choice_stock_refresh:2026-07-08:paired"
    completed = _completed_payload(run_id=run_id, report_date="2026-07-08")
    completed.update(completed_overrides)
    manifest = _observation_manifest(
        report_date="2026-07-08",
        refresh_run_id=run_id,
        created_at="2026-07-08T23:00:00Z",
    )
    manifest.update(manifest_overrides)
    repo = GovernanceRepository(base_dir=tmp_path / "governance")

    with pytest.raises(ValueError):
        append_choice_stock_refresh_completion(
            governance_repo=repo,
            completed_run_payload=completed,
            observation_manifest=manifest,
        )
    assert repo.read_all(CACHE_BUILD_RUN_STREAM) == []


def test_history_refresh_requires_an_observation_manifest(tmp_path: Path) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        append_choice_stock_refresh_completion,
    )

    completed = _completed_payload(
        run_id="choice_stock_refresh:2026-07-08:missing-manifest",
        report_date="2026-07-08",
    )
    completed["refresh_history"] = True
    repo = GovernanceRepository(base_dir=tmp_path / "governance")

    with pytest.raises(ValueError):
        append_choice_stock_refresh_completion(
            governance_repo=repo,
            completed_run_payload=completed,
            observation_manifest=None,
        )
    assert repo.read_all(CACHE_BUILD_RUN_STREAM) == []


def test_sql_authority_lock_is_shared_across_shadow_directories_and_prevents_date_regression(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        append_choice_stock_refresh_completion,
    )

    sql_dsn = f"sqlite:///{(tmp_path / 'authority.db').as_posix()}"
    newer_repo = GovernanceRepository(
        base_dir=tmp_path / "shadow-newer",
        sql_dsn=sql_dsn,
        backend_mode="sql-authority",
    )
    older_repo = GovernanceRepository(
        base_dir=tmp_path / "shadow-older",
        sql_dsn=sql_dsn,
        backend_mode="sql-authority",
    )
    newer_started = Event()
    older_invoked = Event()
    older_started = Event()
    release_newer = Event()
    release_older = Event()
    original_append = newer_repo.append_many_atomic
    original_older_append = older_repo.append_many_atomic

    def append_newer_then_hold(entries):  # type: ignore[no-untyped-def]
        newer_started.set()
        assert release_newer.wait(timeout=5.0)
        return original_append(entries)

    def append_older_then_hold(entries):  # type: ignore[no-untyped-def]
        older_started.set()
        assert release_older.wait(timeout=5.0)
        return original_older_append(entries)

    def append_older_refresh():
        older_invoked.set()
        return append_choice_stock_refresh_completion(
            governance_repo=older_repo,
            completed_run_payload=_completed_payload(
                run_id=older_run_id,
                report_date="2026-07-09",
            ),
            observation_manifest=_observation_manifest(
                report_date="2026-07-09",
                refresh_run_id=older_run_id,
                created_at="2026-07-09T23:00:00Z",
            ),
        )

    object.__setattr__(newer_repo, "append_many_atomic", append_newer_then_hold)
    object.__setattr__(older_repo, "append_many_atomic", append_older_then_hold)
    newer_run_id = "choice_stock_refresh:2026-07-10:newer"
    older_run_id = "choice_stock_refresh:2026-07-09:older"

    with ThreadPoolExecutor(max_workers=2) as executor:
        newer_future = executor.submit(
            append_choice_stock_refresh_completion,
            governance_repo=newer_repo,
            completed_run_payload=_completed_payload(
                run_id=newer_run_id,
                report_date="2026-07-10",
            ),
            observation_manifest=_observation_manifest(
                report_date="2026-07-10",
                refresh_run_id=newer_run_id,
                created_at="2026-07-10T23:00:00Z",
            ),
        )
        assert newer_started.wait(timeout=5.0)
        older_future = executor.submit(append_older_refresh)
        assert older_invoked.wait(timeout=5.0)
        older_entered_append_before_newer_finished = older_started.wait(timeout=1.0)
        release_newer.set()
        assert newer_future.result(timeout=5.0) is True
        release_older.set()
        assert older_future.result(timeout=5.0) is False

    assert older_entered_append_before_newer_finished is False
    latest = older_repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    assert latest is not None
    assert latest["report_date"] == "2026-07-10"
    assert latest["run_id"] == newer_run_id
