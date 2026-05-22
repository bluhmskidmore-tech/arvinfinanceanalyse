from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import duckdb
import pytest

from backend.app.tasks import macro_backfill as macro_backfill_module
from backend.app.tasks.macro_backfill import (
    BackfillRow,
    BackfillSource,
    _fetch_from_wind,
    _map_tushare_records,
    _resolve_sources,
    backfill_macro_series,
)


@contextmanager
def _noop_lock(*_args, **_kwargs):
    yield Path("/tmp/noop.lock")


def test_resolve_sources_for_macro_and_rates() -> None:
    assert BackfillSource.TUSHARE_MACRO in _resolve_sources("CPI:当月同比", "EMM00072301", snapshot_rows=0)
    assert _resolve_sources("中债国债到期收益率:10年", "EMM00166466", snapshot_rows=5)[0] == BackfillSource.CHOICE_SNAPSHOT
    assert BackfillSource.AKSHARE in _resolve_sources("存款类机构质押式回购加权利率:DR007", "CA.DR007", snapshot_rows=0)


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
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=True,
    )
    assert payload["incomplete_count"] == 1
    assert payload["series_plans"][0]["series_id"] == "M0017126"
    assert payload["series_plans"][0]["existing_rows"] == 0


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
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=True,
        sources_filter=["choice_edb"],
    )
    assert payload["incomplete_count"] == 1
    assert payload["source_allocation"] == {"choice_edb": 1}
    assert payload["series_plans"][0]["sources"] == ["choice_edb"]


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
        start_date="2024-01-01",
        end_date="2026-05-20",
        dry_run=False,
    )

    assert results["results"]["CPI:当月同比"] == 1
    assert results["total_added"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select trade_date, value_numeric, unit
            from fact_choice_macro_daily
            where trade_date = '2026-05-02'
            """
        ).fetchone()
        assert row == ("2026-05-02", 0.2, "%")
        total = conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0]
        assert total == 2
    finally:
        conn.close()


def test_fetch_from_wind_prefers_vendor_series_code(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class FakePayload:
        ErrorCode = 0
        Times = [date(2026, 5, 1)]
        Data = [[2.5]]

    class FakeW:
        @staticmethod
        def isconnected() -> bool:
            return True

        @staticmethod
        def wsd(wind_code: str, _field: str, _start: str, _end: str, _opts: str) -> FakePayload:
            captured["wind_code"] = wind_code
            return FakePayload()

    monkeypatch.setattr(macro_backfill_module, "_wind_available", lambda: True)
    fake_wind = type(sys)("WindPy")
    fake_wind.w = FakeW()
    monkeypatch.setitem(sys.modules, "WindPy", fake_wind)

    rows = _fetch_from_wind(
        series_id="EMM00166466",
        series_name="中债国债到期收益率:10年",
        vendor_series_code="S0059749",
        start_date="2026-05-01",
        end_date="2026-05-01",
        frequency="daily",
        unit="%",
    )

    assert captured["wind_code"] == "S0059749"
    assert len(rows) == 1
    assert rows[0].trade_date == "2026-05-01"
    assert rows[0].value_numeric == 2.5


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
