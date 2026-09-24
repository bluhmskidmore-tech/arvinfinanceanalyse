"""Real market breadth + limit-up quality inputs for the Livermore market gate.

Covers:
- core_finance golden samples (pass / fail / missing) for breadth_5d and
  limit-up seal quality;
- the materialize task (aggregation from choice_stock_daily_observation,
  idempotency, missing-data degradation);
- service integration (real breadth preferred, CSI300 proxy fallback).
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.market_breadth import (
    MarketBreadthDaily,
    build_gate_supplement_values,
    compute_breadth_5d,
    compute_limit_up_quality_ok,
)
from backend.app.tasks.market_breadth_materialize import (
    materialize_market_breadth_daily,
)

# ---------------------------------------------------------------------------
# core_finance golden samples
# ---------------------------------------------------------------------------


def _breadth_row(
    trade_date: date,
    *,
    advancing: int,
    declining: int,
    sealed: int = 0,
    broken: int = 0,
) -> MarketBreadthDaily:
    return MarketBreadthDaily(
        trade_date=trade_date,
        advancing_count=advancing,
        declining_count=declining,
        limit_up_sealed_count=sealed,
        limit_up_broken_count=broken,
    )


def test_breadth_5d_golden_sample_positive() -> None:
    start = date(2026, 6, 1)
    nets = [(30, 20), (10, 15), (25, 22), (18, 16), (21, 20)]
    rows = [
        _breadth_row(start + timedelta(days=offset), advancing=up, declining=down)
        for offset, (up, down) in enumerate(nets)
    ]
    # sum of (advancing - declining): 10 - 5 + 3 + 2 + 1 = 11
    assert compute_breadth_5d(rows, as_of=start + timedelta(days=4)) == 11.0


def test_breadth_5d_golden_sample_negative() -> None:
    start = date(2026, 6, 1)
    rows = [
        _breadth_row(start + timedelta(days=offset), advancing=10, declining=30)
        for offset in range(5)
    ]
    assert compute_breadth_5d(rows, as_of=start + timedelta(days=4)) == -100.0


def test_breadth_5d_uses_five_most_recent_trade_dates_only() -> None:
    start = date(2026, 6, 1)
    rows = [
        _breadth_row(start, advancing=1000, declining=0),  # outside 5-day window
        *[
            _breadth_row(start + timedelta(days=offset), advancing=10, declining=12)
            for offset in range(1, 6)
        ],
    ]
    assert compute_breadth_5d(rows, as_of=start + timedelta(days=5)) == -10.0


def test_breadth_5d_missing_when_history_incomplete() -> None:
    start = date(2026, 6, 1)
    rows = [
        _breadth_row(start + timedelta(days=offset), advancing=10, declining=5)
        for offset in range(4)
    ]
    assert compute_breadth_5d(rows, as_of=start + timedelta(days=3)) is None


def test_breadth_5d_missing_when_as_of_not_landed() -> None:
    start = date(2026, 6, 1)
    rows = [
        _breadth_row(start + timedelta(days=offset), advancing=10, declining=5)
        for offset in range(5)
    ]
    assert compute_breadth_5d(rows, as_of=start + timedelta(days=9)) is None


def test_limit_up_quality_pass_fail_missing() -> None:
    day = date(2026, 6, 5)
    assert compute_limit_up_quality_ok(_breadth_row(day, advancing=1, declining=1, sealed=5, broken=2)) is True
    assert compute_limit_up_quality_ok(_breadth_row(day, advancing=1, declining=1, sealed=1, broken=3)) is False
    # Tie counts as not positive.
    assert compute_limit_up_quality_ok(_breadth_row(day, advancing=1, declining=1, sealed=2, broken=2)) is False
    # No limit-up activity at all -> undefined -> missing.
    assert compute_limit_up_quality_ok(_breadth_row(day, advancing=1, declining=1, sealed=0, broken=0)) is None


def test_build_gate_supplement_values_only_for_complete_windows() -> None:
    start = date(2026, 6, 1)
    rows = [
        _breadth_row(
            start + timedelta(days=offset),
            advancing=10 + offset,
            declining=8,
            sealed=3 if offset == 5 else 0,
            broken=1 if offset == 5 else 0,
        )
        for offset in range(6)
    ]
    values = build_gate_supplement_values(rows)
    by_date = {row["trade_date"]: row for row in values}
    assert sorted(by_date) == [start + timedelta(days=4), start + timedelta(days=5)]
    # day5 window: nets (2,3,4,5,6) = 20
    assert by_date[start + timedelta(days=4)]["breadth_5d"] == 20.0
    assert by_date[start + timedelta(days=4)]["limit_up_quality_ok"] is None
    # day6 window: nets (3,4,5,6,7) = 25
    assert by_date[start + timedelta(days=5)]["breadth_5d"] == 25.0
    assert by_date[start + timedelta(days=5)]["limit_up_quality_ok"] is True


# ---------------------------------------------------------------------------
# materialize task
# ---------------------------------------------------------------------------

_DAY_SPECS: list[tuple[str, dict[str, int]]] = [
    ("2026-06-01", {"up": 3, "down": 2, "flat": 1, "sealed": 2, "broken": 1}),
    ("2026-06-02", {"up": 1, "down": 5, "flat": 0, "sealed": 0, "broken": 2}),
    ("2026-06-03", {"up": 4, "down": 1, "flat": 1, "sealed": 1, "broken": 0}),
    ("2026-06-04", {"up": 2, "down": 2, "flat": 2, "sealed": 0, "broken": 0}),
    ("2026-06-05", {"up": 5, "down": 1, "flat": 0, "sealed": 3, "broken": 1}),
    ("2026-06-08", {"up": 1, "down": 6, "flat": 1, "sealed": 1, "broken": 4}),
]


def _expected_counts(spec: dict[str, int]) -> tuple[int, int, int, int]:
    advancing = spec["up"] + spec["sealed"] + spec["broken"]
    declining = spec["down"]
    return advancing, declining, spec["sealed"], spec["broken"]


def _seed_daily_observation(
    duckdb_path: Path,
    specs: list[tuple[str, dict[str, int]]],
) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              volume double,
              amount double,
              pctchange double,
              turn double,
              amplitude double,
              tradestatus varchar,
              highlimit varchar,
              lowlimit varchar,
              field_keys_json varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        rows: list[tuple[object, ...]] = []
        for trade_date, spec in specs:
            code_seq = 0

            def add(pctchange: float, close: float, high: float, highlimit: str) -> None:
                nonlocal code_seq
                code_seq += 1
                rows.append(
                    (
                        trade_date,
                        f"{code_seq:06d}.SZ",
                        close,
                        high,
                        close,
                        close,
                        1000.0,
                        10000.0,
                        pctchange,
                        1.0,
                        2.0,
                        "Trading",
                        highlimit,
                        "1.00",
                        "[]",
                        "sv_test",
                        "vv_test",
                        "rv_test",
                        "run_test",
                    )
                )

            # Choice ships HIGHLIMIT as a yes/no flag; sealed boards carry 是.
            # The derived limit price for these rows is 11.00 (prev_close
            # 10.00 on the main-board 10% band), so unflagged rows whose high
            # reaches 11.00 are the broken boards.
            for _ in range(spec["up"]):
                add(2.5, 10.0, 10.2, "否")
            for _ in range(spec["down"]):
                add(-1.8, 9.5, 9.8, "否")
            for _ in range(spec["flat"]):
                add(0.0, 10.0, 10.0, "否")
            for _ in range(spec["sealed"]):
                add(10.0, 11.0, 11.0, "是")
            for _ in range(spec["broken"]):
                add(5.0, 10.5, 11.0, "否")
        conn.executemany(
            "insert into choice_stock_daily_observation values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def test_materialize_market_breadth_daily_writes_counts_and_supplement(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)

    result = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    assert result["status"] == "completed"
    assert result["daily_row_count"] == 6
    assert result["supplement_row_count"] == 2

    conn = duckdb.connect(str(db), read_only=True)
    try:
        breadth_rows = conn.execute(
            """
            select trade_date, advancing_count, declining_count,
                   limit_up_sealed_count, limit_up_broken_count
            from fact_market_breadth_daily order by trade_date
            """
        ).fetchall()
        supplement_rows = conn.execute(
            """
            select trade_date, breadth_5d, limit_up_quality_ok
            from fact_livermore_gate_supplement_daily order by trade_date
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(breadth_rows) == 6
    for (trade_date, spec), row in zip(_DAY_SPECS, breadth_rows):
        advancing, declining, sealed, broken = _expected_counts(spec)
        assert row == (trade_date, advancing, declining, sealed, broken)

    # nets per day (advancing - declining): +4, -2, +4, 0, +8, 0
    assert supplement_rows == [
        ("2026-06-05", 14.0, True),  # 4 - 2 + 4 + 0 + 8 ; sealed 3 > broken 1
        ("2026-06-08", 10.0, False),  # -2 + 4 + 0 + 8 + 0 ; sealed 1 < broken 4
    ]


def _make_legacy_numeric_highlimit(duckdb_path: Path) -> None:
    """Pre-2026 landings carry Tushare limit prices in the flag column."""
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update choice_stock_daily_observation set highlimit = '11.00', lowlimit = '9.00'"
        )
    finally:
        conn.close()


def test_limit_up_leg_lands_from_flags_without_any_price_source(tmp_path: Path) -> None:
    """The limit-up leg must not depend on an external price vendor."""
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)

    result = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )

    assert result["status"] == "completed"
    assert result["limit_up_quality_available"] is True
    assert result["limit_up_basis"] == "choice_highlimit_flag_and_derived_limit_price"
    assert result["limit_up_sealed_count"] == 1
    assert result["limit_up_broken_count"] == 4
    assert result["limit_price_cross_check"] == "not_attempted"
    assert result["limit_up_sealed_without_derived_touch_count"] == 0
    assert result["limit_up_st_name_source"] == "choice_stock_universe"

    conn = duckdb.connect(str(db), read_only=True)
    try:
        breadth = conn.execute(
            """
            select limit_up_sealed_count, limit_up_broken_count, vendor_version, rule_version
            from fact_market_breadth_daily where trade_date = '2026-06-08'
            """
        ).fetchone()
        supplement = conn.execute(
            """
            select breadth_5d, limit_up_quality_ok
            from fact_livermore_gate_supplement_daily where trade_date = '2026-06-08'
            """
        ).fetchone()
    finally:
        conn.close()

    assert breadth is not None
    assert breadth[:2] == (1, 4)
    assert "choice_highlimit_flag_20260608" in str(breadth[2])
    assert breadth[3] == "rv_market_breadth_daily_v3"
    # nets: -2 + 4 + 0 + 8 + 0 ; sealed 1 < broken 4
    assert supplement == (10.0, False)


def test_limit_price_cross_check_is_evidence_only(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)

    loaded_dates: list[date] = []
    complete_prices = {f"{index:06d}.SZ": 11.0 for index in range(1, 14)}

    def load_limit_prices(trade_date: date) -> dict[str, float]:
        loaded_dates.append(trade_date)
        return complete_prices

    agreed = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
        limit_price_loader=load_limit_prices,
    )

    assert loaded_dates == [date(2026, 6, 8)]
    assert agreed["limit_price_cross_check"] == "agreed"
    assert agreed["limit_price_cross_check_matched_count"] == 13
    assert (agreed["limit_up_sealed_count"], agreed["limit_up_broken_count"]) == (1, 4)

    incomplete = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
        limit_price_loader=lambda _trade_date: dict(list(complete_prices.items())[:-1]),
    )

    assert incomplete["limit_price_cross_check"] == "incomplete"
    assert incomplete["limit_up_quality_available"] is True
    conn = duckdb.connect(str(db), read_only=True)
    try:
        breadth = conn.execute(
            "select limit_up_sealed_count, limit_up_broken_count "
            "from fact_market_breadth_daily where trade_date = '2026-06-08'"
        ).fetchone()
    finally:
        conn.close()
    assert breadth == (1, 4)


def test_limit_price_cross_check_failure_does_not_degrade_quality(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)

    def unavailable_loader(_trade_date: date) -> dict[str, float]:
        raise TimeoutError("fixture timeout")

    result = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
        limit_price_loader=unavailable_loader,
    )

    assert result["limit_price_cross_check"] == "unavailable"
    assert result["limit_up_quality_available"] is True
    conn = duckdb.connect(str(db), read_only=True)
    try:
        supplement = conn.execute(
            "select limit_up_quality_ok from fact_livermore_gate_supplement_daily "
            "where trade_date = '2026-06-08'"
        ).fetchone()
    finally:
        conn.close()
    assert supplement == (False,)


def test_materialize_preserves_earlier_dates_and_stays_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)

    first = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    second = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )

    assert first["daily_written_row_count"] == 6
    assert first["historical_rows_preserved"] == 0
    # Re-running only refreshes the latest date; earlier rows are left alone.
    assert second["daily_written_row_count"] == 1
    assert second["historical_rows_preserved"] == 5

    conn = duckdb.connect(str(db), read_only=True)
    try:
        breadth_rows = conn.execute(
            "select trade_date, count(*) from fact_market_breadth_daily "
            "group by trade_date order by trade_date"
        ).fetchall()
        supplement_rows = conn.execute(
            "select trade_date, breadth_5d, limit_up_quality_ok "
            "from fact_livermore_gate_supplement_daily order by trade_date"
        ).fetchall()
    finally:
        conn.close()
    assert breadth_rows == [(trade_date, 1) for trade_date, _spec in _DAY_SPECS]
    assert supplement_rows == [
        ("2026-06-05", 14.0, True),
        ("2026-06-08", 10.0, False),
    ]


def test_gate_reaches_all_four_conditions_from_the_flag_basis(tmp_path: Path) -> None:
    """The flag basis makes the limit-up leg evaluable, lifting the gate to 4/4."""
    from backend.app.core_finance.livermore_strategy import (
        BroadIndexObservation,
        MarketGateSupplement,
        evaluate_market_gate,
    )

    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)
    materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 5),
        lookback_days=30,
        min_observations_per_day=1,
    )

    conn = duckdb.connect(str(db), read_only=True)
    try:
        landed = conn.execute(
            "select breadth_5d, limit_up_quality_ok "
            "from fact_livermore_gate_supplement_daily where trade_date = '2026-06-05'"
        ).fetchone()
    finally:
        conn.close()
    assert landed == (14.0, True)

    latest_trade_date = date(2026, 6, 5)
    history = [
        BroadIndexObservation(
            trade_date=latest_trade_date - timedelta(days=64 - offset),
            close=3000.0 + offset * 10,
        )
        for offset in range(65)
    ]
    gate = evaluate_market_gate(
        history,
        supplement=MarketGateSupplement(
            trade_date=latest_trade_date,
            breadth_5d=float(landed[0]),
            limit_up_quality_ok=landed[1],
        ),
    )

    assert gate["conditions"][2]["key"] == "breadth_5d_positive"
    assert gate["conditions"][2]["status"] == "pass"
    assert gate["conditions"][3]["status"] == "pass"
    assert gate["available_conditions"] == 4
    assert gate["passed_conditions"] == 4
    assert gate["exposure"] == 1.0
    assert gate["state"] == "OVERHEAT"


def test_legacy_numeric_highlimit_keeps_last_known_limit_up_leg(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)
    materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    _make_legacy_numeric_highlimit(db)

    retry = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )

    assert retry["status"] == "completed"
    # Losing the flag basis must not erase an already materialized leg.
    assert retry["limit_up_quality_available"] is True
    conn = duckdb.connect(str(db), read_only=True)
    try:
        breadth = conn.execute(
            "select limit_up_sealed_count, limit_up_broken_count "
            "from fact_market_breadth_daily where trade_date = '2026-06-08'"
        ).fetchone()
        supplement = conn.execute(
            "select limit_up_quality_ok from fact_livermore_gate_supplement_daily "
            "where trade_date = '2026-06-08'"
        ).fetchone()
    finally:
        conn.close()
    assert breadth == (1, 4)
    assert supplement == (False,)


def test_legacy_numeric_highlimit_lands_breadth_and_degrades_quality(tmp_path: Path) -> None:
    """Breadth does not depend on the limit-up leg, so it still lands in full."""
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)
    _make_legacy_numeric_highlimit(db)

    result = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )

    assert result["status"] == "completed"
    assert result["limit_up_quality_available"] is False
    assert result["limit_up_flag_basis_available"] is False
    assert result["limit_up_unclassified_count"] == 13
    conn = duckdb.connect(str(db), read_only=True)
    try:
        breadth = conn.execute(
            """
            select advancing_count, declining_count,
                   limit_up_sealed_count, limit_up_broken_count
            from fact_market_breadth_daily where trade_date = '2026-06-08'
            """
        ).fetchone()
        supplement = conn.execute(
            "select breadth_5d, limit_up_quality_ok "
            "from fact_livermore_gate_supplement_daily where trade_date = '2026-06-08'"
        ).fetchone()
    finally:
        conn.close()

    # advancing counts the sealed/broken movers regardless of the limit-up leg.
    assert breadth == (6, 6, None, None)
    assert supplement == (10.0, None)


def test_next_trade_date_gets_its_own_leg_without_touching_the_previous_one(
    tmp_path: Path,
) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(
        db,
        [
            *_DAY_SPECS,
            ("2026-06-09", {"up": 3, "down": 2, "flat": 0, "sealed": 2, "broken": 1}),
        ],
    )

    first = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    second = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 9),
        lookback_days=30,
        min_observations_per_day=1,
    )

    assert first["status"] == second["status"] == "completed"
    assert second["daily_written_row_count"] == 1
    conn = duckdb.connect(str(db), read_only=True)
    try:
        breadth = conn.execute(
            """
            select trade_date, limit_up_sealed_count, limit_up_broken_count
            from fact_market_breadth_daily
            where trade_date in ('2026-06-08', '2026-06-09')
            order by trade_date
            """
        ).fetchall()
        supplement = conn.execute(
            """
            select trade_date, limit_up_quality_ok
            from fact_livermore_gate_supplement_daily
            where trade_date in ('2026-06-08', '2026-06-09')
            order by trade_date
            """
        ).fetchall()
    finally:
        conn.close()

    assert breadth == [("2026-06-08", 1, 4), ("2026-06-09", 2, 1)]
    assert supplement == [("2026-06-08", False), ("2026-06-09", True)]


def test_materialize_market_breadth_daily_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)

    first = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    second = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    assert first["status"] == second["status"] == "completed"
    assert first["daily_row_count"] == second["daily_row_count"]

    conn = duckdb.connect(str(db), read_only=True)
    try:
        duplicate_dates = conn.execute(
            "select trade_date from fact_market_breadth_daily group by trade_date having count(*) > 1"
        ).fetchall()
        supplement_duplicates = conn.execute(
            "select trade_date from fact_livermore_gate_supplement_daily group by trade_date having count(*) > 1"
        ).fetchall()
        supplement_values = conn.execute(
            "select trade_date, breadth_5d, limit_up_quality_ok "
            "from fact_livermore_gate_supplement_daily order by trade_date"
        ).fetchall()
    finally:
        conn.close()
    assert duplicate_dates == []
    assert supplement_duplicates == []
    assert supplement_values == [
        ("2026-06-05", 14.0, True),
        ("2026-06-08", 10.0, False),
    ]


def test_materialize_market_breadth_daily_reports_missing_source(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    duckdb.connect(str(db), read_only=False).close()

    result = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    assert result["status"] == "insufficient_data"
    assert result["supplement_row_count"] == 0

    conn = duckdb.connect(str(db), read_only=True)
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "fact_livermore_gate_supplement_daily" in tables:
            count = conn.execute(
                "select count(*) from fact_livermore_gate_supplement_daily"
            ).fetchone()[0]
            assert int(count) == 0
    finally:
        conn.close()


def test_materialize_market_breadth_daily_skips_partial_universe_days(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)

    result = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=8,
    )
    # 2026-06-04 only has 6 observations -> excluded, 5-day windows broken.
    assert result["status"] == "completed"
    assert result["daily_row_count"] < 6
    assert result["supplement_row_count"] == 0


# ---------------------------------------------------------------------------
# service integration: real data preferred, proxy fallback preserved
# ---------------------------------------------------------------------------


def _seed_csi300(duckdb_path: Path, *, start: date, n_days: int) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fact_choice_macro_daily (
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
                    "CA.CSI300",
                    "CSI300",
                    (start + timedelta(days=offset)).isoformat(),
                    3200.0 + offset * 8.0,
                    "daily",
                    "index",
                    "sv",
                    "vv",
                    "rv",
                    "ok",
                    "run",
                )
                for offset in range(n_days)
            ],
        )
    finally:
        conn.close()


def _connect_read_only_with_retry(
    duckdb_path: Path, *, attempts: int = 20, delay_seconds: float = 0.25
) -> duckdb.DuckDBPyConnection:
    """Windows can lag briefly between an external process exiting and the
    OS releasing its DuckDB file lock; retry the verification read instead
    of flaking on that unrelated timing gap."""
    import time

    last_error: duckdb.Error | None = None
    for _ in range(attempts):
        try:
            return duckdb.connect(str(duckdb_path), read_only=True)
        except duckdb.Error as exc:
            last_error = exc
            time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error


@pytest.fixture()
def _isolated_settings(tmp_path: Path, monkeypatch):
    from backend.app.governance.settings import get_settings

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_service_prefers_real_market_breadth(tmp_path: Path, _isolated_settings) -> None:
    from backend.app.services.livermore_gate_supplement_compute_service import (
        compute_and_materialize_gate_supplement,
    )

    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)

    payload = compute_and_materialize_gate_supplement(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    assert payload["status"] == "completed"
    assert payload["basis"] == "market_breadth"

    conn = duckdb.connect(str(db), read_only=True)
    try:
        rows = conn.execute(
            "select trade_date, breadth_5d, limit_up_quality_ok "
            "from fact_livermore_gate_supplement_daily order by trade_date"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [
        ("2026-06-05", 14.0, True),
        ("2026-06-08", 10.0, False),
    ]


def test_service_does_not_overwrite_real_breadth_with_proxy_when_windows_incomplete(
    tmp_path: Path,
    _isolated_settings,
) -> None:
    """Landed source + zero computable supplement windows must NOT trigger the
    CSI300 proxy fallback, which would delete+insert proxy values over
    previously materialized real market_breadth rows."""
    from backend.app.services.livermore_gate_supplement_compute_service import (
        compute_and_materialize_gate_supplement,
    )

    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)
    # CSI300 history is also landed, so the proxy path *could* compute rows.
    _seed_csi300(db, start=date(2026, 5, 1), n_days=40)

    # First run: real market_breadth basis writes real supplement rows.
    first = compute_and_materialize_gate_supplement(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    assert first["basis"] == "market_breadth"

    # Second run: partial-universe threshold breaks every 5-day window
    # (2026-06-04 only has 6 observations), so zero supplement rows compute.
    second = compute_and_materialize_gate_supplement(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=8,
    )
    assert second["basis"] == "market_breadth"
    assert second["status"] == "no_computable_dates"
    assert int(second["computed_rows"]) == 0

    conn = duckdb.connect(str(db), read_only=True)
    try:
        rows = conn.execute(
            "select trade_date, breadth_5d, limit_up_quality_ok "
            "from fact_livermore_gate_supplement_daily order by trade_date"
        ).fetchall()
    finally:
        conn.close()
    # Real rows from the first run survive untouched (no proxy overwrite).
    assert rows == [
        ("2026-06-05", 14.0, True),
        ("2026-06-08", 10.0, False),
    ]


def test_service_does_not_proxy_fallback_when_limit_prices_are_incomplete(
    tmp_path: Path,
    _isolated_settings,
    monkeypatch,
) -> None:
    from backend.app.services import livermore_gate_supplement_compute_service as service

    db = tmp_path / "moss.duckdb"
    _seed_csi300(db, start=date(2026, 5, 1), n_days=40)
    monkeypatch.setattr(
        service,
        "materialize_market_breadth_daily",
        lambda **_kwargs: {
            "status": "limit_price_incomplete",
            "message": "Matched 12 of 13 limit prices.",
            "daily_row_count": 0,
            "supplement_row_count": 0,
            "limit_price_basis": "incomplete_tushare_stk_limit",
            "limit_price_matched_count": 12,
            "table": "fact_market_breadth_daily",
            "rule_version": "rv_market_breadth_daily_v2",
        },
    )

    payload = service.compute_and_materialize_gate_supplement(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
    )

    assert payload["status"] == "limit_price_incomplete"
    assert payload["basis"] == "market_breadth"
    assert payload["computed_rows"] == 0


def _proxy_daily_returns(start: date, pct_changes: list[float | None]) -> list[dict]:
    return [
        {
            "trade_date": (start + timedelta(days=offset)).isoformat(),
            "close": 3000.0,
            "pct_chg": pct,
        }
        for offset, pct in enumerate(pct_changes)
    ]


def test_proxy_breadth_one_up_day_in_window_fails_gate_condition() -> None:
    """Golden sample: with only 1 up-day in the 5-day window ending at as_of,
    the proxy breadth must be negative (net up-days) and the gate breadth
    condition must fail — not pass as it did under the old ratio basis
    (1/5 = 0.2 > 0)."""
    from backend.app.core_finance.livermore_strategy import (
        BroadIndexObservation,
        MarketGateSupplement,
        evaluate_market_gate,
    )
    from backend.app.services.livermore_gate_supplement_compute_service import (
        _compute_supplement_rows,
    )

    start = date(2026, 6, 1)
    # Window ending at day6 (inclusive): day2..day6 = [-1, -1, -1, +2, -1]
    # -> up_days=1, down_days=4 -> net = -3.
    rows = _compute_supplement_rows(
        _proxy_daily_returns(start, [1.0, -1.0, -1.0, -1.0, 2.0, -1.0])
    )
    last = rows[-1]
    assert last["trade_date"] == "2026-06-06"
    assert last["breadth_5d"] == -3.0

    history = [
        BroadIndexObservation(trade_date=start + timedelta(days=offset), close=3000.0 + offset * 10)
        for offset in range(65)
    ]
    gate = evaluate_market_gate(
        history,
        supplement=MarketGateSupplement(
            trade_date=history[-1].trade_date,
            breadth_5d=float(last["breadth_5d"]),
            limit_up_quality_ok=True,
        ),
    )
    condition_by_key = {row["key"]: row for row in gate["conditions"]}
    assert condition_by_key["breadth_5d_positive"]["status"] == "fail"
    assert gate["passed_conditions"] == 3
    assert gate["exposure"] == 0.75


def test_proxy_breadth_window_includes_as_of_day() -> None:
    """Off-by-one: the trailing window must end at (and include) the current
    trade date, matching the formal basis which requires the window to end
    exactly at as_of."""
    from backend.app.services.livermore_gate_supplement_compute_service import (
        _compute_supplement_rows,
    )

    start = date(2026, 6, 1)
    # Window ending at day6 (inclusive): day2..day6 = [-1, +1, +1, -1, +9]
    # -> up=3, down=2 -> net = +1. The as_of day's +9 return must be counted;
    # the old t-5..t-1 window would only see 2 up-days out of day1..day5.
    rows = _compute_supplement_rows(
        _proxy_daily_returns(start, [-1.0, -1.0, 1.0, 1.0, -1.0, 9.0])
    )
    by_date = {row["trade_date"]: row for row in rows}
    assert by_date["2026-06-06"]["breadth_5d"] == 1.0


def test_service_falls_back_to_csi300_proxy_when_breadth_source_missing(
    tmp_path: Path,
    _isolated_settings,
) -> None:
    from backend.app.services.livermore_gate_supplement_compute_service import (
        compute_and_materialize_gate_supplement,
    )

    db = tmp_path / "moss.duckdb"
    _seed_csi300(db, start=date(2026, 5, 1), n_days=30)

    payload = compute_and_materialize_gate_supplement(
        duckdb_path=str(db),
        as_of_date=date(2026, 5, 30),
        lookback_days=60,
    )
    assert payload["status"] == "completed"
    assert payload["basis"] == "csi300_proxy"
    assert int(payload["computed_rows"]) > 0


# ---------------------------------------------------------------------------
# transient DuckDB lock conflict must never trigger a CSI300 proxy overwrite
# ---------------------------------------------------------------------------


def test_service_transient_duckdb_lock_conflict_skips_proxy_overwrite(
    tmp_path: Path,
    _isolated_settings,
) -> None:
    """A real cross-process DuckDB writer-lock conflict (duckdb.IOException,
    e.g. "Cannot open file ... another program is using this file") is a
    transient condition, not a data-missing one. It must not fall back to the
    CSI300 proxy, and any already-landed real supplement rows must survive
    untouched."""
    from backend.app.services.livermore_gate_supplement_compute_service import (
        compute_and_materialize_gate_supplement,
    )

    db = tmp_path / "moss.duckdb"
    _seed_daily_observation(db, _DAY_SPECS)
    # CSI300 history is also landed, so the proxy path *could* compute rows
    # if the lock-conflict guard failed to short-circuit it.
    _seed_csi300(db, start=date(2026, 5, 1), n_days=40)

    first = compute_and_materialize_gate_supplement(
        duckdb_path=str(db),
        as_of_date=date(2026, 6, 8),
        lookback_days=30,
        min_observations_per_day=1,
    )
    assert first["basis"] == "market_breadth"
    assert first["status"] == "completed"

    holder_script = tmp_path / "_hold_duckdb_write_lock.py"
    holder_script.write_text(
        "import duckdb, sys, time\n"
        "conn = duckdb.connect(sys.argv[1], read_only=False)\n"
        "conn.execute('select 1')\n"
        "print('locked', flush=True)\n"
        "time.sleep(float(sys.argv[2]))\n",
        encoding="utf-8",
    )
    holder = subprocess.Popen(
        [sys.executable, str(holder_script), str(db), "10"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"

        second = compute_and_materialize_gate_supplement(
            duckdb_path=str(db),
            as_of_date=date(2026, 6, 8),
            lookback_days=30,
            min_observations_per_day=1,
        )
    finally:
        holder.terminate()
        holder.wait(timeout=10)

    assert second["status"] == "storage_busy"
    assert second["basis"] == "market_breadth"
    assert second.get("computed_rows") == 0

    conn = _connect_read_only_with_retry(db)
    try:
        supplement_rows = conn.execute(
            "select trade_date, breadth_5d, limit_up_quality_ok "
            "from fact_livermore_gate_supplement_daily order by trade_date"
        ).fetchall()
    finally:
        conn.close()
    # Real rows from the first run survive untouched: no proxy overwrite.
    assert supplement_rows == [
        ("2026-06-05", 14.0, True),
        ("2026-06-08", 10.0, False),
    ]


# ---------------------------------------------------------------------------
# defense in depth: the proxy write itself must skip dates with a real row
# ---------------------------------------------------------------------------


def test_service_proxy_guard_skips_dates_with_real_breadth_rows(
    tmp_path: Path,
    _isolated_settings,
    monkeypatch,
) -> None:
    """Even when the real market_breadth basis attempt fails for a reason
    other than a lock conflict (any other exception), the CSI300 proxy
    fallback must never delete+insert over a trade date that already has a
    real row landed in fact_market_breadth_daily."""
    from backend.app.repositories.duckdb_migrations import (
        apply_pending_migrations_on_connection,
    )
    from backend.app.services import livermore_gate_supplement_compute_service as service

    db = tmp_path / "moss.duckdb"
    _seed_csi300(db, start=date(2026, 5, 1), n_days=40)

    conn = duckdb.connect(str(db), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        conn.execute(
            """
            insert into fact_market_breadth_daily (
              trade_date, total_count, advancing_count, declining_count, unchanged_count,
              limit_up_sealed_count, limit_up_broken_count,
              source_version, vendor_version, rule_version, run_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2026-05-30", 5000, 2800, 2200, 0, 30, 5,
                "sv_real", "vv_real_20260530", "rv_market_breadth_daily_v2", "run_real",
            ],
        )
    finally:
        conn.close()

    def _fail(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("boom: unrelated market_breadth materialization failure")

    monkeypatch.setattr(service, "materialize_market_breadth_daily", _fail)

    payload = service.compute_and_materialize_gate_supplement(
        duckdb_path=str(db),
        as_of_date=date(2026, 5, 30),
        lookback_days=60,
    )

    assert payload["basis"] == "csi300_proxy"
    assert "2026-05-30" in payload.get("skipped_real_dates", [])

    conn = duckdb.connect(str(db), read_only=True)
    try:
        count = conn.execute(
            "select count(*) from fact_livermore_gate_supplement_daily "
            "where trade_date = '2026-05-30'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert int(count) == 0
