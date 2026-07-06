from __future__ import annotations

import duckdb
import pytest

from backend.app.core_finance.matched_baseline import (
    LIQUIDITY_FALLBACK_CONTROL_GROUP,
    SAME_SECTOR_CONTROL_GROUP,
    generate_matched_baseline_rows,
    write_matched_baseline_rows,
    matched_baseline_stats_from_rows,
    select_matched_controls,
)


def _row(
    code: str,
    *,
    sector_code: str = "S1",
    amount: float = 100.0,
    entry_executable: bool = True,
    stock_name: str = "Stock",
) -> dict[str, object]:
    return {
        "signal_date": "2026-06-12",
        "stock_code": code,
        "sector_code": sector_code,
        "amount": amount,
        "entry_executable": entry_executable,
        "stock_name": stock_name,
    }


def _candidate(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "signal_date": "2026-06-12",
        "stock_code": "000001.SZ",
        "sector_code": "S1",
        "amount": 100.0,
        "run_id": "run-test",
    }
    base.update(overrides)
    return base


def test_matched_baseline_sampling_is_reproducible_with_fixed_seed() -> None:
    universe = [_row("000001.SZ"), *[_row(f"00000{i}.SZ", amount=100.0 + i) for i in range(2, 10)]]
    candidate = _candidate()

    first = select_matched_controls(candidate, universe, sample_size=3, min_same_sector=3)
    second = select_matched_controls(candidate, universe, sample_size=3, min_same_sector=3)
    third = select_matched_controls({**candidate, "run_id": "run-other"}, universe, sample_size=3, min_same_sector=3)

    assert [row["stock_code"] for row in first] == [row["stock_code"] for row in second]
    assert [row["control_group"] for row in first] == [SAME_SECTOR_CONTROL_GROUP] * 3
    assert [row["stock_code"] for row in first] != [row["stock_code"] for row in third]


def test_matched_baseline_falls_back_when_same_sector_pool_is_too_small_and_marks_group() -> None:
    universe = [
        _row("000001.SZ", sector_code="BANK", amount=100),
        _row("000002.SZ", sector_code="BANK", amount=101),
        _row("000003.SZ", sector_code="TECH", amount=99),
        _row("000004.SZ", sector_code="TECH", amount=102),
        _row("000005.SZ", sector_code="TECH", amount=98),
    ]

    controls = select_matched_controls(
        _candidate(sector_code="BANK", amount=100),
        universe,
        sample_size=3,
        min_same_sector=3,
    )

    assert controls
    assert any(row["sector_code"] != "BANK" for row in controls)
    assert {row["control_group"] for row in controls} == {LIQUIDITY_FALLBACK_CONTROL_GROUP}


def test_matched_baseline_excludes_non_buyable_and_st_controls() -> None:
    universe = [
        _row("000001.SZ"),
        _row("000002.SZ", entry_executable=False),
        _row("000003.SZ", stock_name="ST Risk"),
        _row("000004.SZ"),
        _row("000005.SZ"),
    ]

    controls = select_matched_controls(_candidate(), universe, sample_size=5, min_same_sector=2)

    assert {row["stock_code"] for row in controls} == {"000004.SZ", "000005.SZ"}
    assert all(row["entry_executable"] is True for row in controls)


def test_matched_baseline_bootstrap_ci_returns_expected_shape() -> None:
    candidate_rows = [
        {
            "signal_date": "2026-06-12",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "market_state": "HOT",
            "return_5d_net_adj": 0.08,
        },
        {
            "signal_date": "2026-06-13",
            "stock_code": "000002.SZ",
            "signal_kind": "stock_candidate",
            "market_state": "HOT",
            "return_5d_net_adj": -0.01,
        },
    ]
    control_rows = [
        {
            "signal_date": "2026-06-12",
            "candidate_stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "control_return_5d_net_adj": 0.02,
        },
        {
            "signal_date": "2026-06-12",
            "candidate_stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "control_return_5d_net_adj": 0.04,
        },
        {
            "signal_date": "2026-06-13",
            "candidate_stock_code": "000002.SZ",
            "signal_kind": "stock_candidate",
            "control_return_5d_net_adj": -0.02,
        },
    ]

    stats = matched_baseline_stats_from_rows(
        candidate_rows,
        control_rows,
        bootstrap_iterations=200,
        seed="test",
    )
    horizon = stats["stock_candidate"]["return_5d"]
    ci = horizon["bootstrap_ci_95"]

    assert horizon["n"] == 2
    assert horizon["paired_alpha_avg"] == 0.03
    assert ci["confidence"] == 0.95
    assert ci["iterations"] == 200
    assert isinstance(ci["low"], float)
    assert isinstance(ci["high"], float)
    assert ci["low"] <= ci["high"]


def test_matched_baseline_generates_control_returns_and_writes_rows(tmp_path) -> None:
    db_path = tmp_path / "matched.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              signal_kind varchar,
              market_state varchar,
              candidate_rank integer,
              entry_executable boolean,
              return_1d_net_adj double,
              return_5d_net_adj double,
              return_10d_net_adj double,
              return_20d_net_adj double,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-12', '000001.SZ', 'stock_candidate', 'HOT', 1, true, 0.01, 0.10, null, null, 'run-cand')
            """
        )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              signal_kind varchar,
              sector_code varchar,
              sector_name varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_history values
            ('2026-06-12', '000001.SZ', 'stock_candidate', 'S1', 'Sector 1')
            """
        )
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              sw2021 varchar,
              sw2021code varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              amount double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
        stocks = ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"]
        conn.executemany(
            "insert into choice_stock_universe values ('2026-06-12', ?, ?)",
            [(stock, f"Name {stock}") for stock in stocks],
        )
        conn.executemany(
            "insert into choice_stock_sector_membership values ('2026-06-12', ?, 'Sector 1', 'S1')",
            [(stock,) for stock in stocks],
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values ('2026-06-12', ?, 10, 10, ?, '1', 20, 5)",
            [(stock, 100.0 + index) for index, stock in enumerate(stocks)],
        )
        future_dates = ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"]
        obs_rows = []
        factor_rows = []
        for stock in stocks:
            factor_rows.append((stock, "2026-06-12", 1.0, "sv", "run"))
            for day_index, trade_date in enumerate(future_dates):
                highlimit = 10.0 if stock == "000004.SZ" and day_index == 0 else 20.0
                close_value = 11.0 + day_index
                obs_rows.append((trade_date, stock, 10.0, close_value, 100.0, "1", highlimit, 5.0))
                factor_rows.append((stock, trade_date, 1.0, "sv", "run"))
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?)",
            obs_rows,
        )
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
            factor_rows,
        )

        rows = generate_matched_baseline_rows(
            conn,
            start_date="2026-06-12",
            end_date="2026-06-12",
            sample_size=2,
            run_id="run-test",
        )
        inserted = write_matched_baseline_rows(
            conn,
            rows,
            start_date="2026-06-12",
            end_date="2026-06-12",
        )
        count = conn.execute("select count(*) from livermore_matched_baseline_history").fetchone()[0]
    finally:
        conn.close()

    assert inserted == 2
    assert count == 2
    assert {row["control_stock_code"] for row in rows} == {"000002.SZ", "000003.SZ"}
    assert {row["control_group"] for row in rows} == {LIQUIDITY_FALLBACK_CONTROL_GROUP}
    assert rows[0]["control_return_5d_net_adj"] == pytest.approx(0.4959)
