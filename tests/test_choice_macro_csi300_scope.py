"""Fail-closed date/scope guards for the existing public headline write task."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest

from backend.app.tasks import choice_macro as task

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_macro_data]

SERIES = {"CA.CSI300", "CA.CSI300_PCT_CHG", "CA.CSI300_PE"}
TABLES = (
    "fact_choice_macro_daily", "choice_market_snapshot",
    "phase1_macro_vendor_catalog", "market_data_series_category",
)


@pytest.fixture
def scoped(tmp_path, monkeypatch):
    path = tmp_path / "scoped.duckdb"
    with duckdb.connect(str(path)) as conn:
        task._ensure_tables(conn)
    daily = [{"ts_code": "000300.SH", "trade_date": "20260915", "close": 4500.0, "pct_chg": -1.25}]
    basic = [{"ts_code": "000300.SH", "trade_date": "20260915", "pe": 14.5}]
    calls = []

    def fetch(name, records, **kwargs):
        calls.append((name, kwargs))
        return pd.DataFrame(records)

    pro = SimpleNamespace(
        index_daily=lambda **kw: fetch("index_daily", daily, **kw),
        index_dailybasic=lambda **kw: fetch("index_dailybasic", basic, **kw),
    )
    monkeypatch.setattr(task, "resolve_tushare_token_with_settings_fallback", lambda _: "test-token")
    monkeypatch.setattr(task, "import_tushare_pro", lambda: SimpleNamespace(pro_api=lambda _: pro))

    def no_broad_fetch(**kwargs):
        pytest.fail("scoped recovery must not fetch broad cross-asset sources")

    monkeypatch.setattr(task, "_load_public_cross_asset_history_rows", no_broad_fetch)
    return path, daily, basic, calls


def _state(path):
    with duckdb.connect(str(path), read_only=True) as conn:
        return {table: conn.execute(f"select * from {table} order by all").fetchall() for table in TABLES}


def _run(path):
    return task.refresh_public_cross_asset_headlines(
        duckdb_path=str(path), report_date="2026-09-15", csi300_only=True,
    )


def test_scope_requests_only_two_exact_date_endpoints_and_retains_lineage(scoped):
    path, _, _, calls = scoped
    result = _run(path)
    assert result["status"] == "completed"
    assert result["row_count"] == result["series_count"] == 3
    assert result["scope"] == {
        "mode": "csi300_single_date", "series_ids": sorted(SERIES),
        "start_date": "2026-09-15", "end_date": "2026-09-15",
        "ts_code": "000300.SH", "endpoints": ["index_daily", "index_dailybasic"],
        "pe_field": "pe",
    }
    assert result["required_series_count"] == 3
    assert result["missing_required_series"] == []
    assert calls == [(name, {
        "ts_code": "000300.SH", "start_date": "20260915", "end_date": "20260915", "fields": fields,
    }) for name, fields in (("index_daily", "ts_code,trade_date,close,pct_chg"),
                           ("index_dailybasic", "ts_code,trade_date,pe"))]
    assert len(result["source_evidence"]) == 2
    for item in result["source_evidence"]:
        raw = json.dumps(item["records"], ensure_ascii=False, sort_keys=True, default=str)
        assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == item["records_sha256"]
        assert item["source_version"].endswith(item["records_sha256"][:12])
        assert item["retrieved_at"]
    with duckdb.connect(str(path), read_only=True) as conn:
        rows = conn.execute("select series_id, trade_date, value_numeric, unit, source_version from fact_choice_macro_daily order by series_id").fetchall()
        assert [(r[0], r[1], r[2]) for r in rows] == [
            ("CA.CSI300", "2026-09-15", 4500.0),
            ("CA.CSI300_PCT_CHG", "2026-09-15", -1.25),
            ("CA.CSI300_PE", "2026-09-15", 14.5),
        ]
        assert all(r[4].startswith("sv_tushare_index_daily") for r in rows)
        assert conn.execute("select count(*) from phase1_macro_vendor_catalog where request_options like '%2026-09-15%'").fetchone()[0] == 3


def test_scope_preserves_prior_future_and_unrelated_rows_and_newer_snapshots(scoped):
    path, _, _, _ = scoped
    _run(path)
    with duckdb.connect(str(path)) as conn:
        for table in ("fact_choice_macro_daily", "choice_market_snapshot"):
            conn.execute(f"update {table} set trade_date='2026-09-16', value_numeric=99")
        conn.execute("insert into fact_choice_macro_daily select * replace ('2026-09-14' as trade_date) from fact_choice_macro_daily")
        for table in TABLES:
            conn.execute(f"insert into {table} select * replace ('unrelated' as series_id) from {table} where series_id='CA.CSI300'")
    before = _state(path)
    result = _run(path)
    after = _state(path)
    assert result["row_count"] == 3
    assert result["snapshot_row_count"] == 0
    assert all(row in after["fact_choice_macro_daily"] for row in before["fact_choice_macro_daily"])
    assert len(after["fact_choice_macro_daily"]) == len(before["fact_choice_macro_daily"]) + 3
    for table in TABLES[1:]:
        assert before[table] == after[table]
    _run(path)
    assert _state(path) == after


@pytest.mark.parametrize("bad", [
    "missing_pe", "pe_ttm_only", "duplicate_daily", "duplicate_basic", "old_daily",
    "future_basic", "other_index", "empty_daily", "nan_close", "infinite_pct", "negative_pe",
])
def test_invalid_scope_input_never_mutates_existing_rows(scoped, bad):
    path, daily, basic, _ = scoped
    _run(path)
    before = _state(path)
    if bad == "missing_pe":
        basic[0]["pe"] = None
    elif bad == "pe_ttm_only":
        basic[0].pop("pe")
        basic[0]["pe_ttm"] = 20
    elif bad == "duplicate_daily":
        daily.append(dict(daily[0]))
    elif bad == "duplicate_basic":
        basic.append(dict(basic[0]))
    elif bad == "old_daily":
        daily[0]["trade_date"] = "20260914"
    elif bad == "future_basic":
        basic[0]["trade_date"] = "20260916"
    elif bad == "other_index":
        daily[0]["ts_code"] = "000905.SH"
    elif bad == "empty_daily":
        daily.clear()
    elif bad == "nan_close":
        daily[0]["close"] = float("nan")
    elif bad == "infinite_pct":
        daily[0]["pct_chg"] = float("inf")
    elif bad == "negative_pe":
        basic[0]["pe"] = -1
    with pytest.raises(ValueError, match="CSI300"):
        _run(path)
    assert _state(path) == before


def test_scope_requires_explicit_date_before_fetch(scoped):
    path, _, _, calls = scoped
    before = _state(path)
    with pytest.raises(ValueError, match="report_date"):
        task.refresh_public_cross_asset_headlines(duckdb_path=str(path), csi300_only=True)
    assert calls == []
    assert _state(path) == before


def test_scoped_recovery_never_runs_global_schema_migrations(scoped, monkeypatch):
    path, _, _, _ = scoped

    def prohibited(conn):
        pytest.fail("single-date repair must use existing schema")

    monkeypatch.setattr(task, "_ensure_tables", prohibited)
    assert _run(path)["row_count"] == 3


def test_scoped_recovery_rolls_back_all_tables_on_write_failure(scoped, monkeypatch):
    path, daily, _, _ = scoped
    _run(path)
    before = _state(path)
    daily[0]["close"] = 5000

    def fail_during_catalog_write(*args, **kwargs):
        raise RuntimeError("fixture catalog insert failure")

    monkeypatch.setattr(task, "_insert_market_data_series_category", fail_during_catalog_write)
    with pytest.raises(RuntimeError, match="fixture catalog"):
        _run(path)
    assert _state(path) == before
