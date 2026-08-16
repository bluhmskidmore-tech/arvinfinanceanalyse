from __future__ import annotations

import copy
from pathlib import Path
from datetime import UTC, datetime

import duckdb
import pandas as pd
import pytest

from backend.app.repositories.governance_repo import (
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)


RULE_VERSION = "rv_choice_stock_materialization_front_layer_v1"


def _create_choice_landing(
    path: Path,
    *,
    report_date: str = "2026-07-08",
    run_id: str = "choice_stock_materialize:2026-07-08:fixture",
    source_version: str = "sv_choice_fixture",
    vendor_version: str = "vv_choice_fixture",
    materialized_row_count: int = 12,
) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              pctchange double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_materialize_run (
              run_id varchar,
              as_of_date varchar,
              status varchar,
              catalog_path varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              request_count integer,
              row_count integer,
              started_at varchar,
              completed_at varchar,
              error_message varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    report_date,
                    "000001.SZ",
                    8.2,
                    source_version,
                    vendor_version,
                    RULE_VERSION,
                    run_id,
                ),
                (
                    report_date,
                    "000002.SZ",
                    5.1,
                    source_version,
                    vendor_version,
                    RULE_VERSION,
                    run_id,
                ),
                (
                    "2026-07-07",
                    "000001.SZ",
                    1.0,
                    "sv_older",
                    "vv_older",
                    RULE_VERSION,
                    "choice_stock_materialize:2026-07-07:fixture",
                ),
            ],
        )
        conn.execute(
            "insert into choice_stock_materialize_run values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                run_id,
                report_date,
                "completed",
                "fixture-catalog.json",
                source_version,
                vendor_version,
                RULE_VERSION,
                9,
                materialized_row_count,
                f"{report_date}T22:00:00Z",
                f"{report_date}T22:30:00Z",
                "",
            ],
        )
    finally:
        conn.close()


def test_resolver_proves_latest_unique_committed_choice_observation(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path, materialized_row_count=12)

    resolved = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )

    assert resolved.report_date == "2026-07-08"
    assert resolved.materialization_run_id == (
        "choice_stock_materialize:2026-07-08:fixture"
    )
    assert resolved.daily_observation_row_count == 2
    assert resolved.stock_code_count == 2
    assert resolved.materialized_row_count == 12
    assert resolved.source_version == "sv_choice_fixture"
    assert resolved.vendor_version == "vv_choice_fixture"
    assert resolved.rule_version == RULE_VERSION
    assert resolved.daily_by_key == {
        ("2026-07-08", "000001.SZ"): {
            "trade_date": "2026-07-08",
            "stock_code": "000001.SZ",
            "pctchange": 8.2,
        },
        ("2026-07-08", "000002.SZ"): {
            "trade_date": "2026-07-08",
            "stock_code": "000002.SZ",
            "pctchange": 5.1,
        },
    }


def test_resolver_rejects_expected_date_that_is_not_latest(tmp_path: Path) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path)

    with pytest.raises(ValueError, match="latest daily observation date"):
        resolve_latest_committed_choice_stock_observation(
            duckdb_path=db_path,
            expected_report_date="2026-07-07",
        )


def test_resolver_rejects_ambiguous_target_date_lineage(tmp_path: Path) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            [
                "2026-07-08",
                "000003.SZ",
                7.0,
                "sv_other",
                "vv_other",
                RULE_VERSION,
                "choice_stock_materialize:2026-07-08:other",
            ],
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="unique lineage tuple"):
        resolve_latest_committed_choice_stock_observation(
            duckdb_path=db_path,
            expected_report_date="2026-07-08",
        )


@pytest.mark.parametrize(
    ("update_sql", "message"),
    [
        (
            "update choice_stock_materialize_run set status = 'failed'",
            "exactly one matching completed",
        ),
        (
            "update choice_stock_materialize_run set row_count = 0",
            "materialized row_count",
        ),
        (
            "update choice_stock_materialize_run set source_version = 'sv_other'",
            "exactly one matching completed",
        ),
    ],
)
def test_resolver_rejects_missing_or_inconsistent_completed_run(
    tmp_path: Path,
    update_sql: str,
    message: str,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(update_sql)
    finally:
        conn.close()

    with pytest.raises(ValueError, match=message):
        resolve_latest_committed_choice_stock_observation(
            duckdb_path=db_path,
            expected_report_date="2026-07-08",
        )


def test_resolver_rejects_duplicate_materialization_run_identity(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            insert into choice_stock_materialize_run
            select
              run_id,
              as_of_date,
              'failed',
              catalog_path,
              source_version,
              vendor_version,
              rule_version,
              request_count,
              row_count,
              started_at,
              completed_at,
              'duplicate fixture'
            from choice_stock_materialize_run
            """
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="exactly one matching completed"):
        resolve_latest_committed_choice_stock_observation(
            duckdb_path=db_path,
            expected_report_date="2026-07-08",
        )


class _FakeTushareClient:
    def ths_index(self, **_kwargs: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ts_code": "885001.TI",
                    "name": "算力",
                    "exchange": "A",
                    "list_date": "20200101",
                    "type": "N",
                }
            ]
        )

    def ths_member(self, **kwargs: object) -> pd.DataFrame:
        stock_code = str(kwargs["con_code"])
        return pd.DataFrame(
            [
                {
                    "ts_code": "885001.TI",
                    "con_code": stock_code,
                    "con_name": "fixture",
                    "is_new": "Y",
                }
            ]
        )


def test_public_ths_wrappers_select_probe_stocks_and_emit_overlay_only_fields() -> None:
    from backend.app.tasks.choice_stock_materialize import (
        load_tushare_ths_current_overlay_members,
        select_tushare_ths_current_overlay_probe_stock_codes,
    )

    daily_by_key = {
        ("2026-07-08", "000001.SZ"): {"pctchange": 5.2},
        ("2026-07-08", "000002.SZ"): {"pctchange": 8.1},
        ("2026-07-08", "000003.SZ"): {"pctchange": 4.9},
    }
    stock_codes = select_tushare_ths_current_overlay_probe_stock_codes(
        daily_by_key,
        as_of_date="2026-07-08",
        stock_codes=["000001.SZ", "000002.SZ", "000003.SZ"],
    )
    members = load_tushare_ths_current_overlay_members(
        _FakeTushareClient(),
        as_of_date="2026-07-08",
        stock_codes=stock_codes,
    )

    assert stock_codes == ["000002.SZ", "000001.SZ"]
    assert members == [
        {
            "stock_code": "000001.SZ",
            "theme_key": "885001.TI",
            "theme_name": "算力",
        },
        {
            "stock_code": "000002.SZ",
            "theme_key": "885001.TI",
            "theme_name": "算力",
        },
    ]
    assert all(
        set(member) <= {"stock_code", "stock_name", "theme_key", "theme_name"}
        for member in members
    )


def test_ensure_observation_manifest_repairs_missing_anchor_and_is_idempotent(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path)
    resolved = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    repo = GovernanceRepository(base_dir=tmp_path / "governance")

    manifest, written = ensure_choice_stock_observation_manifest(
        governance_repo=repo,
        observation=resolved,
        created_at="2026-07-08T23:00:00Z",
        publish=True,
    )
    second_manifest, second_written = ensure_choice_stock_observation_manifest(
        governance_repo=repo,
        observation=resolved,
        created_at="2026-07-08T23:01:00Z",
        publish=True,
    )

    assert written is True
    assert second_written is False
    assert second_manifest == manifest
    assert manifest["cache_key"] == CHOICE_STOCK_OBSERVATION_CACHE_KEY
    assert manifest["report_date"] == "2026-07-08"
    assert manifest["source_version"] == "sv_choice_fixture"
    assert manifest["vendor_version"] == "vv_choice_fixture"
    assert manifest["lineage"] == {
        "materialization_run_id": "choice_stock_materialize:2026-07-08:fixture",
        "refresh_run_id": manifest["run_id"],
        "materialization_status": "completed",
        "daily_observation_report_date": "2026-07-08",
        "daily_observation_row_count": 2,
        "materialized_row_count": 12,
        "stock_code_count": 2,
    }
    assert len(repo.read_all(CACHE_MANIFEST_STREAM)) == 1


def test_ensure_observation_manifest_dry_check_returns_in_memory_anchor_without_writes(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path)
    resolved = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    repo = GovernanceRepository(base_dir=tmp_path / "governance")

    manifest, written = ensure_choice_stock_observation_manifest(
        governance_repo=repo,
        observation=resolved,
        created_at="2026-07-08T23:00:00Z",
        publish=False,
    )

    assert written is False
    assert manifest["report_date"] == "2026-07-08"
    assert repo.read_all(CACHE_MANIFEST_STREAM) == []


def test_ensure_observation_manifest_never_regresses_newer_anchor(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        build_choice_stock_observation_manifest,
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path)
    resolved = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    repo = GovernanceRepository(base_dir=tmp_path / "governance")
    newer = build_choice_stock_observation_manifest(
        history_result={
            "status": "completed",
            "run_id": "choice_stock_materialize:2026-07-09:newer",
            "as_of_date": "2026-07-09",
            "row_count": 14,
            "stock_code_count": 3,
            "source_version": "sv_newer",
            "vendor_version": "vv_newer",
        },
        refresh_run_id="choice_stock_refresh:2026-07-09:newer",
        report_date="2026-07-09",
        daily_observation_row_count=3,
        created_at="2026-07-09T23:00:00Z",
    )
    repo.append(CACHE_MANIFEST_STREAM, newer)

    with pytest.raises(ValueError, match="newer observation manifest"):
        ensure_choice_stock_observation_manifest(
            governance_repo=repo,
            observation=resolved,
            created_at="2026-07-10T00:00:00Z",
            publish=True,
        )

    assert repo.read_latest_manifest(str(newer["cache_key"])) == newer


def test_ensure_observation_manifest_repairs_malformed_same_landing_anchor(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )

    db_path = tmp_path / "moss.duckdb"
    _create_choice_landing(db_path)
    resolved = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    repo = GovernanceRepository(base_dir=tmp_path / "governance")
    malformed, _written = ensure_choice_stock_observation_manifest(
        governance_repo=None,
        observation=resolved,
        created_at="2026-07-08T22:00:00Z",
        publish=False,
    )
    malformed_lineage = dict(malformed["lineage"])
    malformed_lineage["refresh_run_id"] = ""
    malformed["lineage"] = malformed_lineage
    repo.append(CACHE_MANIFEST_STREAM, malformed)

    repaired, written = ensure_choice_stock_observation_manifest(
        governance_repo=repo,
        observation=resolved,
        created_at="2026-07-08T23:00:00Z",
        publish=True,
    )

    assert written is True
    assert repaired["lineage"]["refresh_run_id"] == repaired["run_id"]
    assert len(repo.read_all(CACHE_MANIFEST_STREAM)) == 2


def _overlay_members() -> list[dict[str, object]]:
    return [
        {
            "stock_code": "000001.SZ",
            "theme_key": "885001.TI",
            "theme_name": "算力",
        }
    ]


def test_theme_overlay_refresh_off_touches_no_external_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.tasks import choice_stock_theme_overlay_refresh as refresh_module

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("off mode must return before any external read or write")

    monkeypatch.setattr(
        refresh_module,
        "resolve_latest_committed_choice_stock_observation",
        forbidden,
    )
    monkeypatch.setattr(refresh_module, "GovernanceRepository", forbidden)
    monkeypatch.setattr(
        refresh_module,
        "load_tushare_ths_current_overlay_members",
        forbidden,
    )

    result = refresh_module.refresh_choice_stock_theme_overlay(mode="off")

    assert result == {
        "mode": "off",
        "status": "off",
        "observation_status": "not_checked",
        "observation_manifest_written": False,
        "overlay_status": "not_run",
    }
    assert not (tmp_path / "moss.duckdb").exists()
    assert not (tmp_path / "governance").exists()
    assert not (tmp_path / "archive").exists()


def test_theme_overlay_refresh_dry_run_uses_in_memory_anchor_and_writes_nothing(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_theme_overlay_refresh import (
        refresh_choice_stock_theme_overlay,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance-must-not-exist"
    archive_root = tmp_path / "archive-must-not-exist"
    _create_choice_landing(db_path)
    before = db_path.read_bytes()

    result = refresh_choice_stock_theme_overlay(
        mode="dry_run",
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
        run_id="theme-overlay:2026-07-08:dry-run",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 8, 23, 0, tzinfo=UTC),
        load_members=_overlay_members,
    )

    assert result["status"] == "dry_run"
    assert result["observation_status"] == "validated_in_memory"
    assert result["observation_manifest_written"] is False
    assert result["overlay_status"] == "dry_run"
    assert result["member_count"] == 1
    assert db_path.read_bytes() == before
    assert not governance_path.exists()
    assert not archive_root.exists()
    assert not (tmp_path / "authority.db").exists()


def test_theme_overlay_archive_validates_write_paths_before_any_read_or_fetch(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_theme_overlay_refresh import (
        refresh_choice_stock_theme_overlay,
    )

    def forbidden_members() -> list[dict[str, object]]:
        pytest.fail("invalid archive configuration must fail before source fetch")

    with pytest.raises(ValueError, match="archive_root"):
        refresh_choice_stock_theme_overlay(
            mode="archive",
            duckdb_path=tmp_path / "missing.duckdb",
            governance_dir=tmp_path / "governance-must-not-exist",
            archive_root=None,
            expected_report_date="2026-07-08",
            run_id="theme-overlay:2026-07-08:invalid-path",
            source_version="sv_tushare_ths_current_fixture",
            vendor_version="vv_tushare_ths_current_fixture",
            membership_observed_at=datetime(2026, 7, 8, 23, 0, tzinfo=UTC),
            load_members=forbidden_members,
        )

    assert not (tmp_path / "governance-must-not-exist").exists()


def test_theme_overlay_refresh_returns_source_unavailable_for_corrupt_duckdb(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_theme_overlay_refresh import (
        refresh_choice_stock_theme_overlay,
    )

    db_path = tmp_path / "corrupt.duckdb"
    db_path.write_bytes(b"not-a-duckdb-file")

    result = refresh_choice_stock_theme_overlay(
        mode="dry_run",
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
        run_id="theme-overlay:2026-07-08:corrupt-db",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 8, 23, 0, tzinfo=UTC),
        load_members=lambda: pytest.fail("corrupt DB must stop before source fetch"),
    )

    assert result["status"] == "source_unavailable"
    assert result["observation_status"] == "source_unavailable"
    assert result["overlay_status"] == "not_run"
    assert "not a valid DuckDB database file" in str(result["message"])


def test_theme_overlay_refresh_repairs_anchor_before_fetch_and_only_archives_overlay(
    tmp_path: Path,
) -> None:
    from backend.app.governance.locks import acquire_lock
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        CHOICE_STOCK_OBSERVATION_MANIFEST_LOCK,
    )
    from backend.app.tasks.choice_stock_theme_overlay_refresh import (
        refresh_choice_stock_theme_overlay,
    )
    from backend.app.tasks.stock_analysis_theme_overlay_archive import (
        THEME_OVERLAY_CACHE_KEY,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _create_choice_landing(db_path)
    before = db_path.read_bytes()
    fetch_events: list[str] = []

    def load_members_after_anchor_lock_is_released() -> list[dict[str, object]]:
        with acquire_lock(
            CHOICE_STOCK_OBSERVATION_MANIFEST_LOCK,
            base_dir=governance_path,
            timeout_seconds=0.2,
        ):
            fetch_events.append("lock_reacquired")
        repo = GovernanceRepository(base_dir=governance_path)
        assert repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY) is not None
        fetch_events.append("anchor_visible")
        return _overlay_members()

    result = refresh_choice_stock_theme_overlay(
        mode="archive",
        duckdb_path=db_path,
        governance_dir=governance_path,
        archive_root=archive_root,
        expected_report_date="2026-07-08",
        run_id="theme-overlay:2026-07-08:archive",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 8, 23, 0, tzinfo=UTC),
        load_members=load_members_after_anchor_lock_is_released,
    )

    assert result["status"] == "completed"
    assert result["observation_status"] == "ready"
    assert result["observation_manifest_written"] is True
    assert result["overlay_status"] == "completed"
    assert fetch_events == ["lock_reacquired", "anchor_visible"]
    assert db_path.read_bytes() == before
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    finally:
        conn.close()
    assert "choice_stock_concept_membership" not in tables
    repo = GovernanceRepository(base_dir=governance_path)
    assert repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY) is not None
    overlay_manifest = repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY)
    assert overlay_manifest is not None
    assert overlay_manifest["lineage"]["point_in_time"] is False
    assert overlay_manifest["lineage"]["historical_use_allowed"] is False
    assert Path(str(result["archived_path"])).is_file()


def test_theme_overlay_source_failure_keeps_committed_observation_ready(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    )
    from backend.app.tasks.choice_stock_theme_overlay_refresh import (
        refresh_choice_stock_theme_overlay,
    )
    from backend.app.tasks.stock_analysis_theme_overlay_archive import (
        THEME_OVERLAY_CACHE_KEY,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    _create_choice_landing(db_path)

    def fail_source() -> list[dict[str, object]]:
        raise RuntimeError("fixture source unavailable")

    result = refresh_choice_stock_theme_overlay(
        mode="archive",
        duckdb_path=db_path,
        governance_dir=governance_path,
        archive_root=tmp_path / "archive",
        expected_report_date="2026-07-08",
        run_id="theme-overlay:2026-07-08:source-failure",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 8, 23, 0, tzinfo=UTC),
        load_members=fail_source,
    )

    assert result["status"] == "source_failed"
    assert result["observation_status"] == "ready"
    assert result["overlay_status"] == "source_failed"
    repo = GovernanceRepository(base_dir=governance_path)
    assert repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY) is not None
    assert repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY) is None


def test_theme_overlay_archive_failure_is_returned_without_invalidating_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.tasks import choice_stock_theme_overlay_refresh as refresh_module
    from backend.app.tasks.choice_stock_observation_manifest import (
        CHOICE_STOCK_OBSERVATION_CACHE_KEY,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    _create_choice_landing(db_path)

    def fail_archive(**_kwargs: object) -> None:
        raise OSError("fixture archive write failed")

    monkeypatch.setattr(
        refresh_module,
        "archive_tushare_ths_current_overlay",
        fail_archive,
    )

    result = refresh_module.refresh_choice_stock_theme_overlay(
        mode="archive",
        duckdb_path=db_path,
        governance_dir=governance_path,
        archive_root=tmp_path / "archive",
        expected_report_date="2026-07-08",
        run_id="theme-overlay:2026-07-08:archive-failure",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 8, 23, 0, tzinfo=UTC),
        load_members=_overlay_members,
    )

    assert result["status"] == "archive_failed"
    assert result["observation_status"] == "ready"
    assert result["observation_manifest_written"] is True
    assert result["overlay_status"] == "archive_failed"
    assert "fixture archive write failed" in str(result["message"])
    assert (
        GovernanceRepository(base_dir=governance_path).read_latest_manifest(
            CHOICE_STOCK_OBSERVATION_CACHE_KEY
        )
        is not None
    )


def test_theme_overlay_refresh_rejects_future_existing_anchor_before_fetch(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )
    from backend.app.tasks.choice_stock_theme_overlay_refresh import (
        refresh_choice_stock_theme_overlay,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    _create_choice_landing(db_path)
    resolved = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    future_manifest, _written = ensure_choice_stock_observation_manifest(
        governance_repo=None,
        observation=resolved,
        created_at="2026-07-09T00:00:00Z",
        publish=False,
    )
    GovernanceRepository(base_dir=governance_path).append(
        CACHE_MANIFEST_STREAM,
        future_manifest,
    )

    def forbidden_members() -> list[dict[str, object]]:
        pytest.fail("invalid future anchor must stop before source fetch")

    result = refresh_choice_stock_theme_overlay(
        mode="archive",
        duckdb_path=db_path,
        governance_dir=governance_path,
        archive_root=tmp_path / "archive",
        expected_report_date="2026-07-08",
        run_id="theme-overlay:2026-07-08:future-anchor",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 8, 23, 0, tzinfo=UTC),
        load_members=forbidden_members,
    )

    assert result["status"] == "source_unavailable"
    assert result["observation_status"] == "source_unavailable"
    assert result["overlay_status"] == "not_run"
    assert not (tmp_path / "archive").exists()


def test_theme_overlay_refresh_rechecks_anchor_after_fetch_before_archive(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        build_choice_stock_observation_manifest,
    )
    from backend.app.tasks.choice_stock_theme_overlay_refresh import (
        refresh_choice_stock_theme_overlay,
    )
    from backend.app.tasks.stock_analysis_theme_overlay_archive import (
        THEME_OVERLAY_CACHE_KEY,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _create_choice_landing(db_path)

    def advance_anchor_during_fetch() -> list[dict[str, object]]:
        newer = build_choice_stock_observation_manifest(
            history_result={
                "status": "completed",
                "run_id": "choice_stock_materialize:2026-07-09:newer",
                "as_of_date": "2026-07-09",
                "row_count": 14,
                "stock_code_count": 3,
                "source_version": "sv_newer",
                "vendor_version": "vv_newer",
            },
            refresh_run_id="choice_stock_refresh:2026-07-09:newer",
            report_date="2026-07-09",
            daily_observation_row_count=3,
            created_at="2026-07-09T23:00:00Z",
        )
        GovernanceRepository(base_dir=governance_path).append(
            CACHE_MANIFEST_STREAM,
            newer,
        )
        return _overlay_members()

    result = refresh_choice_stock_theme_overlay(
        mode="archive",
        duckdb_path=db_path,
        governance_dir=governance_path,
        archive_root=archive_root,
        expected_report_date="2026-07-08",
        run_id="theme-overlay:2026-07-08:race",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 9, 23, 30, tzinfo=UTC),
        load_members=advance_anchor_during_fetch,
    )

    assert result["status"] == "source_unavailable"
    assert result["observation_status"] == "ready"
    assert result["overlay_status"] == "source_unavailable"
    assert "changed before theme overlay archive" in str(result["message"])
    assert (
        GovernanceRepository(base_dir=governance_path).read_latest_manifest(
            THEME_OVERLAY_CACHE_KEY
        )
        is None
    )
    assert not archive_root.exists()


def test_archive_entrypoint_rechecks_expected_anchor_after_member_loader(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        build_choice_stock_observation_manifest,
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )
    from backend.app.tasks.stock_analysis_theme_overlay_archive import (
        THEME_OVERLAY_CACHE_KEY,
        archive_tushare_ths_current_overlay,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _create_choice_landing(db_path)
    observation = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    repo = GovernanceRepository(base_dir=governance_path)
    expected_manifest, _written = ensure_choice_stock_observation_manifest(
        governance_repo=repo,
        observation=observation,
        created_at="2026-07-08T23:00:00Z",
        publish=True,
    )

    def advance_anchor() -> list[dict[str, object]]:
        newer = build_choice_stock_observation_manifest(
            history_result={
                "status": "completed",
                "run_id": "choice_stock_materialize:2026-07-09:newer-direct",
                "as_of_date": "2026-07-09",
                "row_count": 14,
                "stock_code_count": 3,
                "source_version": "sv_newer_direct",
                "vendor_version": "vv_newer_direct",
            },
            refresh_run_id="choice_stock_refresh:2026-07-09:newer-direct",
            report_date="2026-07-09",
            daily_observation_row_count=3,
            created_at="2026-07-09T23:00:00Z",
        )
        repo.append(CACHE_MANIFEST_STREAM, newer)
        return _overlay_members()

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_path,
        archive_root=archive_root,
        load_members=advance_anchor,
        run_id="theme-overlay:2026-07-08:direct-race",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 9, 23, 30, tzinfo=UTC),
        governance_repo=repo,
        expected_observation_manifest=expected_manifest,
    )

    assert result.status == "source_unavailable"
    assert result.message is not None
    assert "changed during theme overlay source load" in result.message
    assert repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY) is None
    assert not archive_root.exists()


def test_archive_without_explicit_expected_rejects_anchor_advance_in_loader(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        build_choice_stock_observation_manifest,
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )
    from backend.app.tasks.stock_analysis_theme_overlay_archive import (
        THEME_OVERLAY_CACHE_KEY,
        archive_tushare_ths_current_overlay,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _create_choice_landing(db_path)
    observation = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    repo = GovernanceRepository(base_dir=governance_path)
    ensure_choice_stock_observation_manifest(
        governance_repo=repo,
        observation=observation,
        created_at="2026-07-08T23:00:00Z",
        publish=True,
    )

    def advance_anchor() -> list[dict[str, object]]:
        newer = build_choice_stock_observation_manifest(
            history_result={
                "status": "completed",
                "run_id": "choice_stock_materialize:2026-07-09:no-expected",
                "as_of_date": "2026-07-09",
                "row_count": 14,
                "stock_code_count": 3,
                "source_version": "sv_newer_no_expected",
                "vendor_version": "vv_newer_no_expected",
            },
            refresh_run_id="choice_stock_refresh:2026-07-09:no-expected",
            report_date="2026-07-09",
            daily_observation_row_count=3,
            created_at="2026-07-09T23:00:00Z",
        )
        repo.append(CACHE_MANIFEST_STREAM, newer)
        return _overlay_members()

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_path,
        archive_root=archive_root,
        load_members=advance_anchor,
        run_id="theme-overlay:2026-07-08:no-expected-race",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 9, 23, 30, tzinfo=UTC),
        governance_repo=repo,
    )

    assert result.status == "source_unavailable"
    assert result.message is not None
    assert "changed during theme overlay source load" in result.message
    assert repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY) is None
    assert list(archive_root.rglob("*.json")) == []


def test_archive_commit_guard_rejects_anchor_advance_after_outer_final_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.repositories.stock_analysis_theme_overlay_archive_repo import (
        StockAnalysisThemeOverlayArchiveRepository,
    )
    from backend.app.tasks.choice_stock_observation_manifest import (
        build_choice_stock_observation_manifest,
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )
    from backend.app.tasks.stock_analysis_theme_overlay_archive import (
        THEME_OVERLAY_CACHE_KEY,
        archive_tushare_ths_current_overlay,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _create_choice_landing(db_path)
    observation = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    repo = GovernanceRepository(base_dir=governance_path)
    expected_manifest, _written = ensure_choice_stock_observation_manifest(
        governance_repo=repo,
        observation=observation,
        created_at="2026-07-08T23:00:00Z",
        publish=True,
    )
    original_archive = StockAnalysisThemeOverlayArchiveRepository.archive

    def advance_after_outer_check(
        self: StockAnalysisThemeOverlayArchiveRepository,
        **kwargs: object,
    ) -> Path:
        newer = build_choice_stock_observation_manifest(
            history_result={
                "status": "completed",
                "run_id": "choice_stock_materialize:2026-07-09:commit-gap",
                "as_of_date": "2026-07-09",
                "row_count": 14,
                "stock_code_count": 3,
                "source_version": "sv_newer_commit_gap",
                "vendor_version": "vv_newer_commit_gap",
            },
            refresh_run_id="choice_stock_refresh:2026-07-09:commit-gap",
            report_date="2026-07-09",
            daily_observation_row_count=3,
            created_at="2026-07-09T23:00:00Z",
        )
        repo.append(CACHE_MANIFEST_STREAM, newer)
        return original_archive(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        StockAnalysisThemeOverlayArchiveRepository,
        "archive",
        advance_after_outer_check,
    )

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_path,
        archive_root=archive_root,
        load_members=_overlay_members,
        run_id="theme-overlay:2026-07-08:commit-gap",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 9, 23, 30, tzinfo=UTC),
        governance_repo=repo,
        expected_observation_manifest=expected_manifest,
    )

    assert result.status == "source_unavailable"
    assert result.message is not None
    assert "changed before overlay commit" in result.message
    assert repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY) is None
    assert list(archive_root.rglob("*.json")) == []


@pytest.mark.parametrize(
    "mismatch",
    [
        "daily_observation_row_count",
        "cache_version",
        "materialization_run_id",
    ],
)
def test_archive_rejects_full_expected_manifest_mismatch_before_source_fetch(
    tmp_path: Path,
    mismatch: str,
) -> None:
    from backend.app.tasks.choice_stock_observation_manifest import (
        ensure_choice_stock_observation_manifest,
        resolve_latest_committed_choice_stock_observation,
    )
    from backend.app.tasks.stock_analysis_theme_overlay_archive import (
        THEME_OVERLAY_CACHE_KEY,
        archive_tushare_ths_current_overlay,
    )

    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _create_choice_landing(db_path)
    observation = resolve_latest_committed_choice_stock_observation(
        duckdb_path=db_path,
        expected_report_date="2026-07-08",
    )
    expected_manifest, _written = ensure_choice_stock_observation_manifest(
        governance_repo=None,
        observation=observation,
        created_at="2026-07-08T23:00:00Z",
        publish=False,
    )
    actual_manifest = copy.deepcopy(expected_manifest)
    if mismatch == "cache_version":
        actual_manifest["cache_version"] = "choice_stock_refresh_wrong"
    else:
        lineage = dict(actual_manifest["lineage"])
        lineage[mismatch] = (
            999
            if mismatch == "daily_observation_row_count"
            else "choice_stock_materialize:2026-07-08:wrong"
        )
        actual_manifest["lineage"] = lineage
    repo = GovernanceRepository(base_dir=governance_path)
    repo.append(CACHE_MANIFEST_STREAM, actual_manifest)
    source_calls = 0

    def load_members() -> list[dict[str, object]]:
        nonlocal source_calls
        source_calls += 1
        return _overlay_members()

    result = archive_tushare_ths_current_overlay(
        governance_dir=governance_path,
        archive_root=archive_root,
        load_members=load_members,
        run_id=f"theme-overlay:2026-07-08:expected-{mismatch}",
        source_version="sv_tushare_ths_current_fixture",
        vendor_version="vv_tushare_ths_current_fixture",
        membership_observed_at=datetime(2026, 7, 8, 23, 30, tzinfo=UTC),
        governance_repo=repo,
        expected_observation_manifest=expected_manifest,
    )

    assert result.status == "source_unavailable"
    assert source_calls == 0
    assert repo.read_latest_manifest(THEME_OVERLAY_CACHE_KEY) is None
    assert list(archive_root.rglob("*.json")) == []
