"""Real market breadth + limit-up quality inputs for the Livermore market gate.

Covers:
- core_finance golden samples (pass / fail / missing) for breadth_5d and
  limit-up seal quality;
- the materialize task (aggregation from choice_stock_daily_observation,
  idempotency, missing-data degradation);
- service integration (real breadth preferred, CSI300 proxy fallback).
"""

from __future__ import annotations

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


def _seed_daily_observation(duckdb_path: Path, specs: list[tuple[str, dict[str, int]]]) -> None:
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

            for _ in range(spec["up"]):
                add(2.5, 10.0, 10.2, "11.00")
            for _ in range(spec["down"]):
                add(-1.8, 9.5, 9.8, "11.00")
            for _ in range(spec["flat"]):
                add(0.0, 10.0, 10.0, "11.00")
            for _ in range(spec["sealed"]):
                add(10.0, 11.0, 11.0, "11.00")
            for _ in range(spec["broken"]):
                add(5.0, 10.5, 11.0, "11.00")
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
