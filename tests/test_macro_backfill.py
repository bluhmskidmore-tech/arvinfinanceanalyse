from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest
import xlrd

from backend.app.tasks import macro_backfill as macro_backfill_module
from backend.app.tasks.macro_backfill import (
    BackfillRow,
    BackfillSource,
    SeriesBackfillPlan,
    _coerce_float,
    _fetch_rows_for_plan,
    _infer_frequency,
    _fetch_from_choice_edb,
    _is_tushare_macro_series,
    _map_tushare_records,
    _resolve_sources,
    _resolve_tushare_api,
    backfill_macro_series,
)


@contextmanager
def _noop_lock(*_args, **_kwargs):
    yield Path("/tmp/noop.lock")


def test_materialization_run_id_uses_real_utc_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedDatetime:
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            assert tz is UTC
            return datetime(2026, 7, 13, 2, 5, 6, tzinfo=UTC)

    monkeypatch.setattr(macro_backfill_module, "datetime", FixedDatetime)

    assert macro_backfill_module._materialization_run_id() == (
        "backfill_macro_v1:20260713T020506Z"
    )


def test_resolve_sources_for_macro_and_rates() -> None:
    assert BackfillSource.TUSHARE_MACRO in _resolve_sources("CPI:当月同比", "EMM00072301", snapshot_rows=0)
    assert _resolve_sources("中债国债到期收益率:10年", "EMM00166466", snapshot_rows=5)[0] == BackfillSource.CHOICE_SNAPSHOT
    assert _resolve_sources("存款类机构质押式回购加权利率:DR007", "CA.DR007", snapshot_rows=0) == (
        BackfillSource.CHOICE_EDB,
    )


def test_fetch_rows_for_plan_retries_transient_source_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = SeriesBackfillPlan(
        series_id="M0017126",
        series_name="制造业PMI",
        existing_rows=0,
        start_date="2024-01-01",
        end_date="2026-05-20",
        frequency="monthly",
        unit="index",
        sources=(BackfillSource.TUSHARE_MACRO,),
        snapshot_rows_in_range=0,
        notes="test",
    )
    attempts = 0

    def flaky_fetch(_source: BackfillSource, **_kwargs: object) -> list[BackfillRow]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("transient upstream timeout")
        return [
            BackfillRow(
                series_id="M0017126",
                series_name="制造业PMI",
                trade_date="2026-05-01",
                value_numeric=49.5,
                frequency="monthly",
                unit="index",
            )
        ]

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", flaky_fetch)
    monkeypatch.setattr(macro_backfill_module.time, "sleep", lambda _seconds: None)

    outcome = _fetch_rows_for_plan(
        plan,
        duckdb_path=tmp_path / "unused.duckdb",
        vendor_series_code="M0017126",
        start_date="2024-01-01",
        end_date="2026-05-20",
        sources_filter=["tushare_macro"],
    )

    assert attempts == 3
    assert outcome.source == BackfillSource.TUSHARE_MACRO
    assert len(outcome.rows) == 1
    assert _resolve_sources("信用利差:AAA-国债", "SPREAD.AAA", snapshot_rows=0) == (
        BackfillSource.CHOICE_EDB,
    )
    assert _resolve_sources("螺纹钢现货价格", "CA.STEEL", snapshot_rows=0) == (
        BackfillSource.TUSHARE_MACRO,
        BackfillSource.CHOICE_EDB,
    )


def test_backfill_macro_series_dry_run_lists_sparse_series(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('EMM00072301', 'CPI:当月同比', '2026-05-01', 0.1, 'monthly', '%', 'sv', 'vv', 'rv', 'ok', 'run'),
            ('EMM00166466', '中债国债到期收益率:10年', '2026-05-01', 2.1, 'daily', '%', 'sv', 'vv', 'rv', 'ok', 'run')
            """
        )
    finally:
        conn.close()

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["EMM00072301", "EMM00166466"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=True,
    )
    assert payload["dry_run"] is True
    assert payload["incomplete_count"] == 2
    ids = {item["series_id"] for item in payload["series_plans"]}
    assert ids == {"EMM00072301", "EMM00166466"}


def test_backfill_macro_series_dry_run_includes_zero_row_catalog_series(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar,
              vendor_series_code varchar,
              batch_id varchar,
              catalog_version varchar,
              theme varchar,
              is_core boolean,
              tags_json varchar,
              request_options varchar,
              fetch_mode varchar,
              fetch_granularity varchar,
              refresh_tier varchar,
              policy_note varchar
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
            ('M0017126', '制造业PMI', 'choice', 'vv', 'monthly', 'index', 'M0017126',
             'batch', 'catalog', 'macro_leading', true, '[]', '', 'date_slice', 'batch', 'stable', 'test')
            """
        )
    finally:
        conn.close()

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=True,
    )
    assert payload["incomplete_count"] == 1
    assert payload["series_plans"][0]["series_id"] == "M0017126"
    assert payload["series_plans"][0]["existing_rows"] == 0


def test_backfill_macro_series_dry_run_discovers_unregistered_cycle_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    def fail_fixture_seed(**_kwargs: object) -> None:
        raise AssertionError("production macro_backfill dry-run must not call fixture seed")

    monkeypatch.setattr(
        macro_backfill_module,
        "materialize_cycle_rotation_macro_fixture",
        fail_fixture_seed,
        raising=False,
    )

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=True,
    )

    assert payload["incomplete_count"] == 3
    assert {row["series_id"] for row in payload["series_plans"]} == {
        "M0017126",
        "M5525763",
        "M0001385",
    }
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 0
    finally:
        conn.close()


def test_backfill_macro_series_explicit_request_replans_complete_configured_target(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "M0017126",
                    "制造业PMI",
                    f"2025-{month:02d}-01",
                    50.0,
                    "monthly",
                    "index",
                    "sv",
                    "vv",
                    "rv",
                    "ok",
                    "run",
                )
                for month in range(1, 11)
            ],
        )
    finally:
        conn.close()

    automatic_payload = backfill_macro_series(
        duckdb_path=str(db_path),
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=True,
    )
    explicit_payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=True,
    )

    assert "M0017126" not in {
        plan["series_id"] for plan in automatic_payload["series_plans"]
    }
    assert explicit_payload["incomplete_count"] == 1
    assert explicit_payload["series_plans"][0]["series_id"] == "M0017126"
    assert explicit_payload["series_plans"][0]["existing_rows"] == 10


def test_cycle_macro_production_refresh_path_excludes_fixture_seed() -> None:
    config_path = Path(__file__).resolve().parents[1] / "config" / "cycle_rotation_macro_series.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert payload["series"][0]["series_id"] == "M0017126"
    assert all("seed_cycle_rotation_macro" not in command for command in payload["refresh_path"])


def test_backfill_macro_series_dry_run_source_filter_keeps_fallback_source(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('EMM00072301', 'CPI:当月同比', '2026-05-01', 0.1, 'monthly', '%', 'sv', 'vv', 'rv', 'ok', 'run')
            """
        )
    finally:
        conn.close()

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["EMM00072301"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=True,
        sources_filter=["choice_edb"],
    )
    assert payload["incomplete_count"] == 1
    assert payload["source_allocation"] == {"choice_edb": 1}
    assert payload["series_plans"][0]["sources"] == ["choice_edb"]


def test_backfill_macro_series_rejects_unknown_source_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="Unsupported macro backfill source"):
        backfill_macro_series(
            duckdb_path=str(db_path),
            series_names=["M0017126"],
            start_date="2024-01-01",
            end_date="2026-05-20",
            dry_run=True,
            sources_filter=["unknown_vendor"],
        )


def test_backfill_macro_series_rejects_source_incompatible_with_requested_target(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="not supported for requested series M0017126"):
        backfill_macro_series(
            duckdb_path=str(db_path),
            series_names=["M0017126"],
            start_date="2024-01-01",
            end_date="2026-05-20",
            dry_run=True,
            sources_filter=["choice_snapshot"],
        )


def test_cycle_macro_tushare_series_rejects_unmapped_choice_source(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="not supported for requested series M0017126"):
        backfill_macro_series(
            duckdb_path=str(db_path),
            series_names=["M0017126"],
            start_date="2024-01-01",
            end_date="2026-05-20",
            dry_run=True,
            sources_filter=["choice_edb"],
        )


def test_backfill_macro_series_fetch_preview_fetches_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    fetched_rows = [
        BackfillRow(
            series_id="M0017126",
            series_name="制造业PMI",
            trade_date="2026-04-01",
            value_numeric=50.3,
            frequency="monthly",
            unit="index",
        ),
        BackfillRow(
            series_id="M0017126",
            series_name="制造业PMI",
            trade_date="2026-05-01",
            value_numeric=49.5,
            frequency="monthly",
            unit="index",
        ),
    ]

    def mock_fetch_by_source(source: BackfillSource, **_kwargs: object) -> list[BackfillRow]:
        assert source == BackfillSource.TUSHARE_MACRO
        return fetched_rows

    @contextmanager
    def fail_if_locked(*_args: object, **_kwargs: object):
        raise AssertionError("fetch preview must not acquire the write lock")
        yield Path("unreachable")

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", mock_fetch_by_source)
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(macro_backfill_module, "acquire_lock", fail_if_locked)
    before_bytes = db_path.read_bytes()
    before_stat = (db_path.stat().st_mtime_ns, db_path.stat().st_size)

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        fetch_preview=True,
        sources_filter=["tushare_macro"],
    )

    assert payload["dry_run"] is False
    assert payload["fetch_preview"] is True
    assert payload["total_added"] == 0
    assert payload["total_fetched"] == 2
    assert payload["errors"] == {}
    assert payload["source_by_series"] == {"M0017126": "tushare_macro"}
    assert payload["previews"]["M0017126"] == {
        "series_name": "制造业PMI",
        "source": "tushare_macro",
        "row_count": 2,
        "first_trade_date": "2026-04-01",
        "last_trade_date": "2026-05-01",
        "first_value": 50.3,
        "last_value": 49.5,
        "min_value": 49.5,
        "max_value": 50.3,
        "frequency": "monthly",
        "unit": "index",
    }
    assert db_path.read_bytes() == before_bytes
    assert (db_path.stat().st_mtime_ns, db_path.stat().st_size) == before_stat
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 0
    finally:
        conn.close()


def test_backfill_macro_series_fetch_preview_blocks_unit_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    monkeypatch.setattr(
        macro_backfill_module,
        "_fetch_by_source",
        lambda *_args, **_kwargs: [
            BackfillRow(
                series_id="M0017126",
                series_name="制造业PMI",
                trade_date="2026-05-01",
                value_numeric=49.5,
                frequency="monthly",
                unit="%",
            )
        ],
    )
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)

    @contextmanager
    def fail_if_locked(*_args: object, **_kwargs: object):
        raise AssertionError("invalid preview must not acquire the write lock")
        yield Path("unreachable")

    monkeypatch.setattr(macro_backfill_module, "acquire_lock", fail_if_locked)

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        fetch_preview=True,
        sources_filter=["tushare_macro"],
    )

    assert payload["status"] == "blocked"
    assert payload["total_added"] == 0
    assert len(payload["errors"]) == 1
    assert "unit mismatch" in next(iter(payload["errors"].values()))
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 0
    finally:
        conn.close()


def test_backfill_macro_series_fetch_preview_blocks_invalid_calendar_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    monkeypatch.setattr(
        macro_backfill_module,
        "_fetch_by_source",
        lambda *_args, **_kwargs: [
            BackfillRow(
                series_id="M0017126",
                series_name="制造业PMI",
                trade_date="2026-00-01",
                value_numeric=49.5,
                frequency="monthly",
                unit="index",
            )
        ],
    )
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        fetch_preview=True,
        sources_filter=["tushare_macro"],
    )

    assert payload["status"] == "blocked"
    assert "invalid trade_date" in next(iter(payload["errors"].values()))


def test_macro_backfill_cli_accepts_explicit_sources_for_plan(tmp_path: Path) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.app.tasks.macro_backfill",
            "--dry-run",
            "--sources",
            "tushare_macro",
            "--series-names",
            "M0017126",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2026-05-20",
            "--duckdb-path",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["source_allocation"] == {"tushare_macro": 1}
    assert payload["series_plans"][0]["sources"] == ["tushare_macro"]


def test_backfill_macro_series_mock_fetch_and_insert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              frequency varchar,
              unit varchar,
              vendor_series_code varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('EMM00072301', 'CPI:当月同比', '2026-05-01', 0.1, 'monthly', '%', 'sv', 'vv', 'rv', 'ok', 'run')
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
            ('EMM00072301', 'monthly', '%', 'EMM00072301')
            """
        )
    finally:
        conn.close()

    fetched_rows = [
        BackfillRow(
            series_id="EMM00072301",
            series_name="CPI:当月同比",
            trade_date="2026-05-02",
            value_numeric=0.2,
            frequency="monthly",
            unit="%",
        )
    ]

    def mock_fetch_by_source(source: BackfillSource, **kwargs: object) -> list[BackfillRow]:
        assert kwargs["unit"] == "%"
        return fetched_rows if source == BackfillSource.TUSHARE_MACRO else []

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", mock_fetch_by_source)
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(macro_backfill_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(macro_backfill_module, "apply_pending_migrations_on_connection", lambda _conn: None)
    monkeypatch.setattr(macro_backfill_module, "ensure_choice_macro_schema_if_missing", lambda _conn: None)

    results = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["EMM00072301"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=False,
    )

    assert results["results"]["CPI:当月同比"] == 1
    assert results["total_added"] == 1
    assert results["source_by_series"] == {"EMM00072301": "tushare_macro"}
    assert set(results["vendor_versions"]) == {"EMM00072301"}
    vendor_version = results["vendor_versions"]["EMM00072301"]
    assert vendor_version.startswith("vv_backfill_macro_tushare_macro_20260520_")
    assert len(vendor_version.rsplit("_", 1)[-1]) == 16
    assert results["run_id"].startswith("backfill_macro_v1:")

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select trade_date, value_numeric, unit, source_version, vendor_version, run_id
            from fact_choice_macro_daily
            where trade_date = '2026-05-02'
            """
        ).fetchone()
        assert row[:5] == (
            "2026-05-02",
            0.2,
            "%",
            "backfill_macro_v1",
            vendor_version,
        )
        assert str(row[5]).startswith("backfill_macro_v1:")
        total = conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0]
        assert total == 2
    finally:
        conn.close()


def test_backfill_macro_series_reports_empty_fetch_as_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(macro_backfill_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(macro_backfill_module, "apply_pending_migrations_on_connection", lambda _conn: None)
    monkeypatch.setattr(macro_backfill_module, "ensure_choice_macro_schema_if_missing", lambda _conn: None)

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=False,
        sources_filter=["tushare_macro"],
    )

    assert payload["total_added"] == 0
    assert len(payload["errors"]) == 1
    error = next(iter(payload["errors"].values()))
    assert "M0017126" in error
    assert "tushare_macro" in error
    assert payload["source_by_series"] == {}
    assert payload["vendor_versions"] == {}


def test_backfill_macro_series_treats_duplicate_fetch_as_idempotent_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('M0017126', '制造业PMI', '2026-05-01', 49.5, 'monthly', 'index',
             'backfill_macro_v1', 'vv_existing', 'rv_backfill_macro_v1', 'ok',
             'backfill_macro_v1:20260520T120000Z')
            """
        )
    finally:
        conn.close()

    monkeypatch.setattr(
        macro_backfill_module,
        "_fetch_by_source",
        lambda *_args, **_kwargs: [
            BackfillRow(
                series_id="M0017126",
                series_name="制造业PMI",
                trade_date="2026-05-01",
                value_numeric=49.5,
                frequency="monthly",
                unit="index",
            )
        ],
    )
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(macro_backfill_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(macro_backfill_module, "apply_pending_migrations_on_connection", lambda _conn: None)
    monkeypatch.setattr(macro_backfill_module, "ensure_choice_macro_schema_if_missing", lambda _conn: None)

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=False,
        sources_filter=["tushare_macro"],
    )

    assert payload["status"] == "completed"
    assert payload["total_fetched"] == 1
    assert payload["total_added"] == 0
    assert payload["errors"] == {}
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 1
    finally:
        conn.close()


def test_backfill_macro_series_does_not_write_when_any_requested_fetch_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    def mock_fetch_by_source(_source: BackfillSource, **kwargs: object) -> list[BackfillRow]:
        if kwargs["series_id"] != "M0017126":
            return []
        return [
            BackfillRow(
                series_id="M0017126",
                series_name="制造业PMI",
                trade_date="2026-05-01",
                value_numeric=49.5,
                frequency="monthly",
                unit="index",
            )
        ]

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", mock_fetch_by_source)
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)

    @contextmanager
    def fail_if_locked(*_args: object, **_kwargs: object):
        raise AssertionError("blocked fetch batch must not acquire the write lock")
        yield Path("unreachable")

    def fail_if_migrated(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("blocked fetch batch must not run schema checks")

    monkeypatch.setattr(macro_backfill_module, "acquire_lock", fail_if_locked)
    monkeypatch.setattr(macro_backfill_module, "apply_pending_migrations_on_connection", fail_if_migrated)
    monkeypatch.setattr(macro_backfill_module, "ensure_choice_macro_schema_if_missing", fail_if_migrated)

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126", "M5525763"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=False,
        sources_filter=["tushare_macro"],
    )

    assert payload["total_added"] == 0
    assert len(payload["errors"]) == 1
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 0
    finally:
        conn.close()


def test_backfill_macro_series_rolls_back_all_series_when_later_insert_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar unique,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()

    fetch_order: list[str] = []

    def mock_fetch_by_source(_source: BackfillSource, **kwargs: object) -> list[BackfillRow]:
        fetch_order.append(str(kwargs["series_name"]))
        return [
            BackfillRow(
                series_id=str(kwargs["series_id"]),
                series_name=str(kwargs["series_name"]),
                trade_date="2026-05-01",
                value_numeric=49.5,
                frequency=str(kwargs["frequency"]),
                unit=str(kwargs["unit"]),
            )
        ]

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", mock_fetch_by_source)
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(macro_backfill_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(macro_backfill_module, "apply_pending_migrations_on_connection", lambda _conn: None)
    monkeypatch.setattr(macro_backfill_module, "ensure_choice_macro_schema_if_missing", lambda _conn: None)

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["M0017126", "M5525763"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=False,
        sources_filter=["tushare_macro"],
    )

    assert payload["status"] == "failed"
    assert payload["total_fetched"] == 2
    assert payload["total_added"] == 0
    assert len(payload["results"]) == 2
    assert set(payload["results"].values()) == {0}
    assert list(payload["errors"]) == [fetch_order[1]]
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 0
    finally:
        conn.close()


def test_backfill_macro_series_records_choice_fallback_as_actual_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              frequency varchar,
              unit varchar,
              vendor_series_code varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('EMM00072301', 'CPI:同比', '2026-04-01', 0.1, 'monthly', '%',
             'sv_existing', 'vv_existing', 'rv_existing', 'ok', 'run_existing')
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
            ('EMM00072301', 'CPI:同比', 'monthly', '%', 'EMM00072301')
            """
        )
    finally:
        conn.close()

    attempted_sources: list[BackfillSource] = []

    def mock_fetch_by_source(source: BackfillSource, **_kwargs: object) -> list[BackfillRow]:
        attempted_sources.append(source)
        if source != BackfillSource.CHOICE_EDB:
            return []
        return [
            BackfillRow(
                series_id="EMM00072301",
                series_name="CPI:同比",
                trade_date="2026-05-01",
                value_numeric=0.2,
                frequency="monthly",
                unit="%",
            )
        ]

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", mock_fetch_by_source)
    monkeypatch.setattr(macro_backfill_module, "_count_snapshot_rows", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(macro_backfill_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(macro_backfill_module, "apply_pending_migrations_on_connection", lambda _conn: None)
    monkeypatch.setattr(macro_backfill_module, "ensure_choice_macro_schema_if_missing", lambda _conn: None)

    payload = backfill_macro_series(
        duckdb_path=str(db_path),
        series_names=["EMM00072301"],
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=False,
    )

    assert attempted_sources == [BackfillSource.TUSHARE_MACRO, BackfillSource.CHOICE_EDB]
    assert payload["source_by_series"] == {"EMM00072301": "choice_edb"}
    vendor_version = payload["vendor_versions"]["EMM00072301"]
    assert vendor_version.startswith("vv_backfill_macro_choice_edb_20260520_")
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        stored = conn.execute(
            """
            select source_version, vendor_version
            from fact_choice_macro_daily
            where trade_date = '2026-05-01'
            """
        ).fetchone()
    finally:
        conn.close()
    assert stored == ("backfill_macro_v1", vendor_version)


def test_social_financing_stock_yoy_uses_stock_end_value_not_monthly_increment() -> None:
    rows = _map_tushare_records(
        "sf_month",
        [
            {"month": "202405", "inc_month": 33000, "stk_endval": 391.93},
            {"month": "202505", "inc_month": 22900, "stk_endval": 426.16},
        ],
        series_name="社会融资规模存量:同比",
    )

    assert len(rows) == 1
    assert rows[0]["trade_date"] == "2025-05-01"
    assert rows[0]["value"] == pytest.approx(8.7337, rel=1e-4)


def test_social_financing_stock_yoy_accepts_stable_macro_alias_name() -> None:
    rows = _map_tushare_records(
        "sf_month",
        [
            {"month": "202405", "inc_month": 33000, "stk_endval": 391.93},
            {"month": "202505", "inc_month": 22900, "stk_endval": 426.16},
        ],
        series_name="social_financing_stock_yoy",
    )

    assert len(rows) == 1
    assert rows[0]["trade_date"] == "2025-05-01"
    assert rows[0]["value"] == pytest.approx(8.7337, rel=1e-4)


def test_stable_social_financing_alias_routes_to_tushare_monthly_api() -> None:
    assert _resolve_tushare_api("social_financing_stock_yoy") == "sf_month"
    assert _is_tushare_macro_series("social_financing_stock_yoy") is True
    assert _infer_frequency("social_financing_stock_yoy", "unknown") == "monthly"


def test_cn_pmi_uses_tushare_month_and_manufacturing_pmi_code() -> None:
    rows = _map_tushare_records(
        "cn_pmi",
        [
            {"month": "202605", "pmi010000": 50.0, "pmi010100": 51.1},
            {"MONTH": "202604", "PMI010000": 50.3, "PMI010100": 50.2},
        ],
        series_name="制造业PMI",
    )

    assert rows == [
        {"trade_date": "2026-05-01", "value": 50.0},
        {"trade_date": "2026-04-01", "value": 50.3},
    ]


def test_manufacturing_pmi_does_not_substitute_new_orders_series() -> None:
    rows = _map_tushare_records(
        "cn_pmi",
        [{"month": "202605", "pmi010500": 48.5}],
        series_name="制造业PMI",
    )

    assert rows == []


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_tushare_mapping_rejects_non_finite_values(value: float) -> None:
    assert _coerce_float(value) is None
    assert (
        _map_tushare_records(
            "cn_pmi",
            [{"month": "202605", "pmi010000": value}],
            series_name="制造业PMI",
        )
        == []
    )


def test_choice_edb_rejects_excluded_new_orders_vendor_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnexpectedChoiceClient:
        def __init__(self) -> None:
            raise AssertionError("excluded vendor code must be rejected before Choice EDB fetch")

    monkeypatch.setattr(macro_backfill_module, "ChoiceClient", UnexpectedChoiceClient)

    rows = _fetch_from_choice_edb(
        series_id="M0017126",
        series_name="制造业PMI",
        vendor_series_code="M0017127",
        start_date="2026-01-01",
        end_date="2026-05-31",
        frequency="monthly",
        unit="index",
    )

    assert rows == []


def test_cn_pmi_new_orders_uses_tushare_new_orders_code() -> None:
    rows = _map_tushare_records(
        "cn_pmi",
        [
            {"month": "202605", "pmi010300": 47.2, "pmi010500": 48.5},
            {"MONTH": "202604", "PMI010300": 47.0, "PMI010500": 49.1},
        ],
        series_name="PMI:新订单",
    )

    assert rows == [
        {"trade_date": "2026-05-01", "value": 48.5},
        {"trade_date": "2026-04-01", "value": 49.1},
    ]


class _FakeXlsSheet:
    def __init__(self, rows: list[list[object]]) -> None:
        self._rows = rows
        self.nrows = len(rows)

    def row_values(self, row_index: int) -> list[object]:
        return self._rows[row_index]


class _FakeXlsBook:
    def __init__(self, rows: list[list[object]]) -> None:
        self._sheet = _FakeXlsSheet(rows)

    def sheet_by_index(self, sheet_index: int) -> _FakeXlsSheet:
        assert sheet_index == 0
        return self._sheet


def _nbs_pmi_manifest(artifact_bytes: bytes) -> dict[str, str]:
    return {
        "release_url": "https://www.stats.gov.cn/sj/zxfbhjd/202606/t20260630_1964032.html",
        "artifact_url": "https://www.stats.gov.cn/sj/zxfbhjd/202606/P020260630315076364750.xls",
        "published_at": "2026-06-30T09:30:00+08:00",
        "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "source_unit": "%",
        "target_unit": "index",
        "value_transform": "identity_percentage_points_to_index_points",
    }


def _nbs_pmi_table_rows() -> list[list[object]]:
    return [
        ["表1 中国制造业PMI及构成指数（经季节调整）"],
        ["统计期", "PMI", "生产", "新订单", "原材料库存", "从业人员", "供应商配送时间"],
        ["2025年6月", 49.7, 51.0, 50.2, 48.0, 47.9, 50.2],
        ["2025年7月", 49.3, 50.5, 49.4, 47.7, 48.0, 50.3],
        ["2025年8月", 49.4, 50.8, 49.5, 48.0, 47.9, 50.5],
        ["2025年9月", 49.8, 51.9, 49.7, 48.5, 48.5, 50.8],
        ["2025年10月", 49.0, 49.7, 48.8, 47.3, 48.3, 50.0],
        ["2025年11月", 49.2, 50.0, 49.2, 47.3, 48.4, 50.1],
        ["2025年12月", 50.1, 51.7, 50.8, 47.8, 48.2, 50.2],
        ["2026年1月", 49.3, 50.6, 49.2, 47.4, 48.1, 50.1],
        ["2026年2月", 49.0, 49.6, 48.6, 47.5, 48.0, 49.1],
        ["2026年3月", 50.4, 51.4, 51.6, 47.7, 48.6, 49.5],
        ["2026年4月", 50.3, 51.5, 50.6, 49.3, 48.8, 49.5],
        ["2026年5月", 50.0, 51.2, 49.9, 48.6, 48.6, 49.2],
        ["2026年6月", 50.3, 51.4, 51.2, 48.4, 48.5, 49.9],
    ]


def _map_nbs_pmi_release_xls(*args: object, **kwargs: object) -> list[BackfillRow]:
    mapper = getattr(macro_backfill_module, "_map_nbs_pmi_release_xls", None)
    assert mapper is not None, "NBS PMI release XLS mapper is not implemented"
    return mapper(*args, **kwargs)


def test_nbs_pmi_manifest_xls_maps_manufacturing_pmi_without_using_new_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_bytes = b"governed-nbs-pmi-xls-artifact"
    monkeypatch.setattr(
        xlrd,
        "open_workbook",
        lambda *, file_contents: _FakeXlsBook(_nbs_pmi_table_rows()),
    )

    rows = _map_nbs_pmi_release_xls(
        artifact_bytes,
        manifest=_nbs_pmi_manifest(artifact_bytes),
        series_id="M0017126",
        series_name="制造业PMI",
        start_date="2025-06-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="index",
    )

    assert len(rows) == 13
    assert rows[-1] == BackfillRow(
        series_id="M0017126",
        series_name="制造业PMI",
        trade_date="2026-06-01",
        value_numeric=50.3,
        frequency="monthly",
        unit="index",
    )
    assert rows[-1].value_numeric != 51.2


@pytest.mark.parametrize(
    "manifest_override",
    [
        {
            "release_url": "https://www.stats.gov.cn.evil.example/pmi.html",
        },
        {
            "artifact_sha256": "0" * 64,
        },
        {
            "published_at": "2026-07-14T09:30:00+08:00",
        },
        {
            "source_unit": "",
        },
        {
            "target_unit": "",
        },
        {
            "value_transform": "",
        },
    ],
    ids=[
        "non-official-domain",
        "artifact-sha-mismatch",
        "published-after-end-date",
        "missing-source-unit",
        "missing-target-unit",
        "missing-value-transform",
    ],
)
def test_nbs_pmi_manifest_validation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    manifest_override: dict[str, str],
) -> None:
    artifact_bytes = b"governed-nbs-pmi-xls-artifact"
    manifest = {**_nbs_pmi_manifest(artifact_bytes), **manifest_override}
    monkeypatch.setattr(
        xlrd,
        "open_workbook",
        lambda *, file_contents: _FakeXlsBook(_nbs_pmi_table_rows()),
    )

    rows = _map_nbs_pmi_release_xls(
        artifact_bytes,
        manifest=manifest,
        series_id="M0017126",
        series_name="制造业PMI",
        start_date="2025-06-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="index",
    )

    assert rows == []


def test_manufacturing_pmi_prefers_nbs_release_before_tushare() -> None:
    nbs_source = getattr(BackfillSource, "NBS_PMI_RELEASE", None)
    assert nbs_source is not None, "NBS PMI release source is not implemented"

    assert _resolve_sources("制造业PMI", "M0017126", snapshot_rows=0) == (
        nbs_source,
        BackfillSource.TUSHARE_MACRO,
    )


def test_manufacturing_pmi_records_tushare_as_actual_fallback_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = SeriesBackfillPlan(
        series_id="M0017126",
        series_name="制造业PMI",
        existing_rows=0,
        start_date="2025-06-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="index",
        sources=(BackfillSource.NBS_PMI_RELEASE, BackfillSource.TUSHARE_MACRO),
        snapshot_rows_in_range=0,
        notes="governed NBS PMI release with Tushare fallback",
    )
    attempted: list[BackfillSource] = []

    def fake_fetch(source: BackfillSource, **_kwargs: object) -> list[BackfillRow]:
        attempted.append(source)
        if source == BackfillSource.NBS_PMI_RELEASE:
            return []
        return [
            BackfillRow(
                series_id="M0017126",
                series_name="制造业PMI",
                trade_date="2026-05-01",
                value_numeric=50.0,
                frequency="monthly",
                unit="index",
            )
        ]

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", fake_fetch)

    outcome = _fetch_rows_for_plan(
        plan,
        duckdb_path=tmp_path / "unused.duckdb",
        vendor_series_code="M0017126",
        start_date=plan.start_date,
        end_date=plan.end_date,
    )

    assert attempted == [BackfillSource.NBS_PMI_RELEASE, BackfillSource.TUSHARE_MACRO]
    assert outcome.source == BackfillSource.TUSHARE_MACRO
    assert outcome.provenance is None


def test_nbs_pmi_preview_includes_governed_artifact_lineage() -> None:
    nbs_source = getattr(BackfillSource, "NBS_PMI_RELEASE", None)
    assert nbs_source is not None, "NBS PMI release source is not implemented"
    artifact_bytes = b"governed-nbs-pmi-xls-artifact"
    manifest = _nbs_pmi_manifest(artifact_bytes)
    plan = SeriesBackfillPlan(
        series_id="M0017126",
        series_name="制造业PMI",
        existing_rows=0,
        start_date="2025-06-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="index",
        sources=(nbs_source,),
        snapshot_rows_in_range=0,
        notes="governed NBS PMI release",
    )
    outcome_factory = macro_backfill_module.FetchOutcome
    try:
        outcome = outcome_factory(
            source=nbs_source,
            rows=(
                BackfillRow(
                    series_id="M0017126",
                    series_name="制造业PMI",
                    trade_date="2026-06-01",
                    value_numeric=50.3,
                    frequency="monthly",
                    unit="index",
                ),
            ),
            attempted_sources=(nbs_source,),
            provenance=manifest,
        )
    except TypeError as exc:
        pytest.fail(f"FetchOutcome does not preserve NBS artifact provenance: {exc}")

    preview = macro_backfill_module._fetch_preview_payload(plan=plan, outcome=outcome)

    assert preview["source"] == "nbs_pmi_release"
    assert preview["release_url"] == manifest["release_url"]
    assert preview["published_at"] == manifest["published_at"]
    assert preview["artifact_sha256"] == manifest["artifact_sha256"]


def _pbc_financial_statistics_html(
    *,
    report_month: str = "2026-05",
    release_title: str | None = None,
    social_financing_yoy: str = "7.7",
    social_financing_balance: str = "458.81",
    cumulative_social_financing: str = "17.48",
    m2_yoy: str = "8.6",
    m2_balance: str = "353.67",
    m1_yoy: str = "5.5",
) -> str:
    year, month_text = report_month.split("-")
    month = int(month_text)
    if release_title is None:
        release_title = f"{year}年{month}月金融统计数据报告"
    cumulative_label = f"前{month}个月" if month < 6 else "上半年"
    return f"""
    <html>
      <head><title>{release_title}</title></head>
      <body>
        <div id="zoom">
          <p>一、社会融资规模存量同比增长{social_financing_yoy}%</p>
          <p>初步统计，{year}年{month}月末社会融资规模存量为{social_financing_balance}万亿元，同比增长{social_financing_yoy}%。</p>
          <p>二、{cumulative_label}社会融资规模增量累计为{cumulative_social_financing}万亿元</p>
          <p>三、广义货币增长{m2_yoy}%</p>
          <p>{month}月末，广义货币(M2)余额{m2_balance}万亿元,同比增长{m2_yoy}%。狭义货币(M1)余额114.89万亿元,同比增长{m1_yoy}%。</p>
        </div>
      </body>
    </html>
    """


def _pbc_financial_statistics_manifest(
    artifact_bytes: bytes,
    *,
    report_month: str = "2026-05",
    release_title: str | None = None,
    release_url: str = "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/202606/t20260613_123456.html",
    published_at: str = "2026-06-13T17:00:00+08:00",
) -> dict[str, object]:
    year, month_text = report_month.split("-")
    month = int(month_text)
    if release_title is None:
        release_title = f"{year}年{month}月金融统计数据报告"
    return {
        "release_url": release_url,
        "published_at": published_at,
        "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "release_title": release_title,
        "report_month": report_month,
        "source_unit": "%",
        "target_unit": "%",
        "value_transform": "identity_percentage_points",
        "field_mappings": {
            "M5525763": "社会融资规模存量:同比",
            "M0001385": "广义货币M2:同比",
        },
    }


def _map_pbc_financial_statistics_release_html(
    *args: object,
    **kwargs: object,
) -> list[BackfillRow]:
    mapper = getattr(macro_backfill_module, "_map_pbc_financial_statistics_release_html", None)
    assert mapper is not None, "PBC financial-statistics release HTML mapper is not implemented"
    return mapper(*args, **kwargs)


@pytest.mark.parametrize(
    ("series_id", "series_name", "expected_value", "forbidden_values"),
    [
        ("M5525763", "社会融资规模存量:同比", 7.7, {17.48, 458.81}),
        ("M0001385", "M2:同比", 8.6, {5.5}),
    ],
    ids=["social-financing-stock-yoy", "m2-yoy"],
)
def test_pbc_financial_statistics_release_maps_governed_yoy_fields_only(
    series_id: str,
    series_name: str,
    expected_value: float,
    forbidden_values: set[float],
) -> None:
    artifact_bytes = _pbc_financial_statistics_html().encode("utf-8")

    rows = _map_pbc_financial_statistics_release_html(
        artifact_bytes,
        manifest=_pbc_financial_statistics_manifest(artifact_bytes),
        series_id=series_id,
        series_name=series_name,
        start_date="2026-05-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="%",
    )

    assert rows == [
        BackfillRow(
            series_id=series_id,
            series_name=series_name,
            trade_date="2026-05-01",
            value_numeric=expected_value,
            frequency="monthly",
            unit="%",
        )
    ]
    assert rows[0].value_numeric not in forbidden_values


def test_pbc_m2_mapper_accepts_official_fullwidth_parentheses() -> None:
    html = _pbc_financial_statistics_html().replace("(M2)", "（M2）")
    artifact_bytes = html.encode("utf-8")

    rows = _map_pbc_financial_statistics_release_html(
        artifact_bytes,
        manifest=_pbc_financial_statistics_manifest(artifact_bytes),
        series_id="M0001385",
        series_name="M2:同比",
        start_date="2026-05-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="%",
    )

    assert [row.value_numeric for row in rows] == [8.6]


@pytest.mark.parametrize(
    ("series_id", "series_name", "expected_value"),
    [
        ("M5525763", "社会融资规模存量:同比", 7.4),
        ("M0001385", "M2:同比", 8.0),
    ],
    ids=["half-year-social-financing-stock-yoy", "half-year-m2-yoy"],
)
def test_pbc_financial_statistics_release_accepts_half_year_title_for_june_only(
    series_id: str,
    series_name: str,
    expected_value: float,
) -> None:
    release_title = "2026年上半年金融统计数据报告"
    artifact_bytes = _pbc_financial_statistics_html(
        report_month="2026-06",
        release_title=release_title,
        social_financing_yoy="7.4",
        social_financing_balance="462.06",
        cumulative_social_financing="20.84",
        m2_yoy="8",
        m2_balance="356.71",
        m1_yoy="4",
    ).encode("utf-8")

    rows = _map_pbc_financial_statistics_release_html(
        artifact_bytes,
        manifest=_pbc_financial_statistics_manifest(
            artifact_bytes,
            report_month="2026-06",
            release_title=release_title,
            release_url="https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026071515025183948/index.html",
            published_at="2026-07-15T15:00:09+08:00",
        ),
        series_id=series_id,
        series_name=series_name,
        start_date="2026-06-01",
        end_date="2026-07-23",
        frequency="monthly",
        unit="%",
    )

    assert rows == [
        BackfillRow(
            series_id=series_id,
            series_name=series_name,
            trade_date="2026-06-01",
            value_numeric=expected_value,
            frequency="monthly",
            unit="%",
        )
    ]


def test_pbc_financial_statistics_release_accepts_monthly_title_for_june() -> None:
    release_title = "2026年6月金融统计数据报告"
    artifact_bytes = _pbc_financial_statistics_html(
        report_month="2026-06",
        release_title=release_title,
        m2_yoy="8",
    ).encode("utf-8")

    rows = _map_pbc_financial_statistics_release_html(
        artifact_bytes,
        manifest=_pbc_financial_statistics_manifest(
            artifact_bytes,
            report_month="2026-06",
            release_title=release_title,
        ),
        series_id="M0001385",
        series_name="M2:同比",
        start_date="2026-06-01",
        end_date="2026-07-23",
        frequency="monthly",
        unit="%",
    )

    assert rows == [
        BackfillRow(
            series_id="M0001385",
            series_name="M2:同比",
            trade_date="2026-06-01",
            value_numeric=8.0,
            frequency="monthly",
            unit="%",
        )
    ]


def test_pbc_financial_statistics_release_rejects_half_year_title_for_non_june_month() -> None:
    release_title = "2026年上半年金融统计数据报告"
    artifact_bytes = _pbc_financial_statistics_html(
        report_month="2026-05",
        release_title=release_title,
    ).encode("utf-8")

    rows = _map_pbc_financial_statistics_release_html(
        artifact_bytes,
        manifest=_pbc_financial_statistics_manifest(
            artifact_bytes,
            report_month="2026-05",
            release_title=release_title,
        ),
        series_id="M5525763",
        series_name="社会融资规模存量:同比",
        start_date="2026-05-01",
        end_date="2026-07-23",
        frequency="monthly",
        unit="%",
    )

    assert rows == []


@pytest.mark.parametrize(
    ("case", "series_id"),
    [
        ("non-official-domain", "M5525763"),
        ("artifact-sha-mismatch", "M5525763"),
        ("published-after-end-date", "M5525763"),
        ("title-mismatch", "M5525763"),
        ("report-month-mismatch", "M5525763"),
        ("missing-unit", "M5525763"),
        ("missing-field-mapping", "M0001385"),
    ],
)
def test_pbc_financial_statistics_release_validation_fails_closed(
    case: str,
    series_id: str,
) -> None:
    html = _pbc_financial_statistics_html()
    if case == "title-mismatch":
        html = html.replace("2026年5月金融统计数据报告", "2026年5月社会融资规模增量统计数据报告")
    artifact_bytes = html.encode("utf-8")
    manifest = _pbc_financial_statistics_manifest(artifact_bytes)
    if case == "non-official-domain":
        manifest["release_url"] = "https://www.pbc.gov.cn.evil.example/financial-statistics.html"
    elif case == "artifact-sha-mismatch":
        manifest["artifact_sha256"] = "0" * 64
    elif case == "published-after-end-date":
        manifest["published_at"] = "2026-07-14T09:30:00+08:00"
    elif case == "report-month-mismatch":
        manifest["report_month"] = "2026-04"
    elif case == "missing-unit":
        manifest["source_unit"] = ""
    elif case == "missing-field-mapping":
        manifest["field_mappings"] = {}

    rows = _map_pbc_financial_statistics_release_html(
        artifact_bytes,
        manifest=manifest,
        series_id=series_id,
        series_name="社会融资规模存量:同比" if series_id == "M5525763" else "M2:同比",
        start_date="2026-05-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="%",
    )

    assert rows == []


@pytest.mark.parametrize(
    ("series_id", "series_name"),
    [
        ("M5525763", "社会融资规模存量:同比"),
        ("M0001385", "M2:同比"),
    ],
)
def test_credit_macro_series_prefer_pbc_release_before_tushare(
    series_id: str,
    series_name: str,
) -> None:
    pbc_source = getattr(BackfillSource, "PBC_FINANCIAL_STATISTICS_RELEASE", None)
    assert pbc_source is not None, "PBC financial-statistics release source is not implemented"

    assert _resolve_sources(series_name, series_id, snapshot_rows=0) == (
        pbc_source,
        BackfillSource.TUSHARE_MACRO,
    )


def test_credit_macro_records_tushare_as_actual_fallback_after_empty_pbc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pbc_source = getattr(BackfillSource, "PBC_FINANCIAL_STATISTICS_RELEASE", None)
    assert pbc_source is not None, "PBC financial-statistics release source is not implemented"
    plan = SeriesBackfillPlan(
        series_id="M5525763",
        series_name="社会融资规模存量:同比",
        existing_rows=0,
        start_date="2026-05-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="%",
        sources=(pbc_source, BackfillSource.TUSHARE_MACRO),
        snapshot_rows_in_range=0,
        notes="governed PBC release with Tushare fallback",
    )
    attempted: list[BackfillSource] = []

    def fake_fetch(source: BackfillSource, **_kwargs: object) -> list[BackfillRow]:
        attempted.append(source)
        if source == pbc_source:
            return []
        return [
            BackfillRow(
                series_id="M5525763",
                series_name="社会融资规模存量:同比",
                trade_date="2026-05-01",
                value_numeric=7.7,
                frequency="monthly",
                unit="%",
            )
        ]

    monkeypatch.setattr(macro_backfill_module, "_fetch_by_source", fake_fetch)

    outcome = _fetch_rows_for_plan(
        plan,
        duckdb_path=tmp_path / "unused.duckdb",
        vendor_series_code="M5525763",
        start_date=plan.start_date,
        end_date=plan.end_date,
    )

    assert attempted == [pbc_source, BackfillSource.TUSHARE_MACRO]
    assert outcome.source == BackfillSource.TUSHARE_MACRO
    assert outcome.provenance is None


def test_pbc_release_source_aggregates_adjacent_months_with_artifact_set_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    may_bytes = _pbc_financial_statistics_html().encode("utf-8")
    april_html = _pbc_financial_statistics_html().replace("2026年5月", "2026年4月").replace(
        "同比增长7.7%",
        "同比增长7.8%",
    )
    april_bytes = april_html.encode("utf-8")
    may_manifest = _pbc_financial_statistics_manifest(may_bytes)
    may_manifest["release_url"] = "https://www.pbc.gov.cn/releases/2026-05.html"
    april_manifest = _pbc_financial_statistics_manifest(april_bytes)
    april_manifest.update(
        {
            "release_url": "https://www.pbc.gov.cn/releases/2026-04.html",
            "published_at": "2026-05-14T17:00:00+08:00",
            "release_title": "2026年4月金融统计数据报告",
            "report_month": "2026-04",
        }
    )
    manifests = [april_manifest, may_manifest]

    class FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    artifacts = {
        str(april_manifest["release_url"]): april_bytes,
        str(may_manifest["release_url"]): may_bytes,
    }
    monkeypatch.setattr(
        macro_backfill_module,
        "_pbc_financial_statistics_release_manifests",
        lambda **_kwargs: manifests,
        raising=False,
    )
    monkeypatch.setattr(
        macro_backfill_module.requests,
        "get",
        lambda url, **_kwargs: FakeResponse(artifacts[url]),
    )
    plan = SeriesBackfillPlan(
        series_id="M5525763",
        series_name="社会融资规模存量:同比",
        existing_rows=0,
        start_date="2026-04-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="%",
        sources=(BackfillSource.PBC_FINANCIAL_STATISTICS_RELEASE,),
        snapshot_rows_in_range=0,
        notes="two governed PBC releases",
    )

    outcome = _fetch_rows_for_plan(
        plan,
        duckdb_path=tmp_path / "unused.duckdb",
        vendor_series_code="M5525763",
        start_date=plan.start_date,
        end_date=plan.end_date,
    )

    assert [(row.trade_date, row.value_numeric) for row in outcome.rows] == [
        ("2026-04-01", 7.8),
        ("2026-05-01", 7.7),
    ]
    assert outcome.provenance is not None
    assert outcome.provenance["artifact_count"] == "2"
    assert len(outcome.provenance["artifact_set_sha256"]) == 64
    artifact_rows = json.loads(outcome.provenance["artifacts_json"])
    assert [row["report_month"] for row in artifact_rows] == ["2026-04", "2026-05"]
    vendor_version = macro_backfill_module._vendor_version_for_rows(
        source=BackfillSource.PBC_FINANCIAL_STATISTICS_RELEASE,
        end_date=plan.end_date,
        rows=outcome.rows,
        provenance=outcome.provenance,
    )
    assert f"_{outcome.provenance['artifact_set_sha256'][:16]}_" in vendor_version


def test_pbc_financial_statistics_preview_includes_governed_release_lineage() -> None:
    pbc_source = getattr(BackfillSource, "PBC_FINANCIAL_STATISTICS_RELEASE", None)
    assert pbc_source is not None, "PBC financial-statistics release source is not implemented"
    artifact_bytes = _pbc_financial_statistics_html().encode("utf-8")
    manifest = _pbc_financial_statistics_manifest(artifact_bytes)
    plan = SeriesBackfillPlan(
        series_id="M5525763",
        series_name="社会融资规模存量:同比",
        existing_rows=0,
        start_date="2026-05-01",
        end_date="2026-07-13",
        frequency="monthly",
        unit="%",
        sources=(pbc_source,),
        snapshot_rows_in_range=0,
        notes="governed PBC financial-statistics release",
    )
    outcome = macro_backfill_module.FetchOutcome(
        source=pbc_source,
        rows=(
            BackfillRow(
                series_id="M5525763",
                series_name="社会融资规模存量:同比",
                trade_date="2026-05-01",
                value_numeric=7.7,
                frequency="monthly",
                unit="%",
            ),
        ),
        attempted_sources=(pbc_source,),
        provenance=manifest,
    )

    preview = macro_backfill_module._fetch_preview_payload(plan=plan, outcome=outcome)

    assert preview["source"] == "pbc_financial_statistics_release"
    assert preview["release_url"] == manifest["release_url"]
    assert preview["published_at"] == manifest["published_at"]
    assert preview["artifact_sha256"] == manifest["artifact_sha256"]


def test_pbc_financial_statistics_preview_includes_artifact_set_lineage() -> None:
    source = BackfillSource.PBC_FINANCIAL_STATISTICS_RELEASE
    artifacts = [
        {"report_month": "2026-04", "artifact_sha256": "a" * 64},
        {"report_month": "2026-05", "artifact_sha256": "b" * 64},
    ]
    provenance = {
        "release_url": "https://www.pbc.gov.cn/releases/2026-05.html",
        "published_at": "2026-06-12T17:00:01+08:00",
        "artifact_sha256": "b" * 64,
        "artifact_count": "2",
        "artifact_set_sha256": "c" * 64,
        "artifacts_json": json.dumps(artifacts, sort_keys=True),
    }
    plan = SeriesBackfillPlan(
        series_id="M0001385",
        series_name="M2:同比",
        existing_rows=0,
        start_date="2026-04-01",
        end_date="2026-07-10",
        frequency="monthly",
        unit="%",
        sources=(source,),
        snapshot_rows_in_range=0,
        notes="two governed PBC releases",
    )
    outcome = macro_backfill_module.FetchOutcome(
        source=source,
        rows=(
            BackfillRow(
                series_id="M0001385",
                series_name="M2:同比",
                trade_date="2026-05-01",
                value_numeric=8.6,
                frequency="monthly",
                unit="%",
            ),
        ),
        attempted_sources=(source,),
        provenance=provenance,
    )

    preview = macro_backfill_module._fetch_preview_payload(plan=plan, outcome=outcome)

    assert preview["artifact_count"] == "2"
    assert preview["artifact_set_sha256"] == "c" * 64
    assert preview["artifacts_json"] == provenance["artifacts_json"]
