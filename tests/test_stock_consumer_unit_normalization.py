"""Mixed-vendor stock inputs share one amount/volume scale at core read boundaries."""

from __future__ import annotations

import duckdb
import pytest

from backend.app.core_finance import matched_baseline, portfolio_paths

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_livermore]


@pytest.fixture
def market() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    conn.execute(
        """create table choice_stock_daily_observation (
          trade_date varchar, stock_code varchar, open_value double, high_value double,
          low_value double, close_value double, volume double, amount double,
          tradestatus varchar, highlimit double, lowlimit double, vendor_version varchar
        )"""
    )
    sources = [
        ("N1", 1_000_000, 100_000, "vv_choice_stock_20260904_test"),
        ("T2", 2_000, 2_000, "vv_choice_tushare_stock_20260904_test"),
        ("N3", 3_000_000, 300_000, "vv_choice_stock_20260904_test"),
        ("T3", 3_000, 3_000, "vv_livermore_supplement_tushare_sina_20260904_test"),
        ("T4", 4_000, 4_000, "vv_choice_tushare_stock_20260904_test"),
        ("N5", 5_000_000, 500_000, "vv_choice_stock_20260904_test"),
        ("UNKNOWN", 900_000_000, 9_000_000, "unregistered_source"),
        ("BLANK", 900_000_000, 9_000_000, "   "),
        ("NULL", 900_000_000, 9_000_000, None),
    ]
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, 10, 13, 9, ?, ?, ?, 'Trading', 20, 5, ?)",
        [
            (day, code, close, volume, amount, vendor)
            for day, close in (("2026-09-03", 11), ("2026-09-04", 12))
            for code, amount, volume, vendor in sources
        ],
    )
    try:
        yield conn
    finally:
        conn.close()


def test_price_paths_normalize_once_without_changing_prices_or_returns(market) -> None:
    paths = portfolio_paths.load_position_price_paths(
        market,
        [{"stock_code": code, "entry_date": "2026-09-03"} for code in ("N3", "T3", "UNKNOWN", "BLANK", "NULL")],
        max_horizon_days=2,
    )
    for code in ("N3", "T3"):
        rows = paths[f"{code}|2026-09-03"]
        assert [row["amount"] for row in rows] == [3_000_000, 3_000_000]
        assert [row["volume"] for row in rows] == [300_000, 300_000]
        assert [row["close"] for row in rows] == [11, 12]
        result = portfolio_paths.calculate_path_horizon_exit(
            rows, horizon_days=2, entry_price=10, buy_cost_rate=0,
            sell_cost_rate=0, slippage_rate=0,
        )
        assert result["return_net"] == pytest.approx(0.2)
    assert paths["N3|2026-09-03"] == paths["T3|2026-09-03"]
    for code in ("UNKNOWN", "BLANK", "NULL"):
        rows = paths[f"{code}|2026-09-03"]
        assert all(row["amount"] is None and row["volume"] is None for row in rows)
        assert [row["close"] for row in rows] == [11, 12]


@pytest.mark.parametrize("loader", ["single", "batch", "pit"])
def test_control_universe_mixed_source_liquidity_ranking_uses_yuan(market, loader) -> None:
    if loader == "single":
        rows = matched_baseline._load_control_universe_for_date(market, "2026-09-03")
    elif loader == "batch":
        rows = matched_baseline._load_control_universes_for_dates(market, ["2026-09-03"])["2026-09-03"]
    else:
        rows = matched_baseline._load_control_universes_for_dates_pit_proof(
            market, ["2026-09-03"], evaluation_as_of_date="2026-09-04",
            source_availability_index={},
        )["2026-09-03"]

    amounts = {row["stock_code"]: row["amount"] for row in rows}
    assert amounts == {
        "N1": 1_000_000, "T2": 2_000_000, "N3": 3_000_000, "T3": 3_000_000,
        "T4": 4_000_000, "N5": 5_000_000, "UNKNOWN": None, "BLANK": None, "NULL": None,
    }
    assert matched_baseline._liquidity_buckets(rows) == {
        "N1": 0, "T2": 0, "N3": 1, "T3": 2, "T4": 3, "N5": 4,
    }


def test_candidate_amounts_use_same_scale_and_preserve_execution_returns(market) -> None:
    market.execute(
        """create table livermore_candidate_execution_history as
        select trade_date as signal_date, stock_code, 'stock_candidate' as signal_kind,
               'neutral' as market_state, 1 as candidate_rank, true as entry_executable,
               0.1 as return_1d_net_adj, 0.2 as return_5d_net_adj,
               0.3 as return_10d_net_adj, 0.4 as return_20d_net_adj, 'run' as run_id
        from choice_stock_daily_observation where trade_date='2026-09-03'"""
    )
    rows = matched_baseline._load_candidate_execution_rows(market, start_date=None, end_date=None)
    amounts = {row["stock_code"]: row["amount"] for row in rows}
    assert amounts["N3"] == amounts["T3"] == 3_000_000
    assert amounts["UNKNOWN"] is None
    assert all(float(row["return_5d_net_adj"]) == 0.2 for row in rows)


def test_missing_vendor_column_fails_closed_at_both_read_boundaries(market) -> None:
    market.execute("alter table choice_stock_daily_observation drop column vendor_version")
    paths = portfolio_paths.load_position_price_paths(
        market, [{"stock_code": "N3", "entry_date": "2026-09-03"}], max_horizon_days=2
    )
    assert paths["N3|2026-09-03"][0]["amount"] is None
    assert paths["N3|2026-09-03"][0]["volume"] is None
    rows = matched_baseline._load_control_universes_for_dates(market, ["2026-09-03"])["2026-09-03"]
    assert all(row["amount"] is None for row in rows)


def test_legacy_repo_imports_reexport_the_same_unit_functions() -> None:
    from backend.app.core_finance import choice_stock_units as core
    from backend.app.repositories import choice_stock_units as repo

    for name in ("amount_rmb_sql", "volume_shares_sql", "scale_unknown_sql"):
        assert getattr(repo, name) is getattr(core, name)
