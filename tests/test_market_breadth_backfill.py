from __future__ import annotations

import json
from pathlib import Path

import duckdb

from backend.app.tasks.market_breadth_backfill import (
    apply_market_breadth_backfill,
    build_market_breadth_backfill_plan,
    main,
)
from backend.app.tasks.market_breadth_materialize import RULE_VERSION


_TRADE_DATES = ("2026-01-05", "2026-01-06", "2026-01-07")
_SOURCE_ONLY_PRIOR_DATE = "2025-12-31"


def _seed_backfill_scenario(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar, stock_code varchar, open_value double, high_value double,
              low_value double, close_value double, volume double, amount double,
              pctchange double, turn double, amplitude double, tradestatus varchar,
              highlimit varchar, lowlimit varchar, field_keys_json varchar,
              source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_market_breadth_daily (
              trade_date varchar primary key,
              total_count integer, advancing_count integer, declining_count integer,
              unchanged_count integer, limit_up_sealed_count integer,
              limit_up_broken_count integer, source_version varchar,
              vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    trade_date,
                    f"60000{index}.SH",
                    10.0,
                    10.2,
                    10.0,
                    10.1,
                    1000.0,
                    10000.0,
                    1.0,
                    1.0,
                    2.0,
                    "Trading",
                    "否",
                    "否",
                    "[]",
                    "sv_source",
                    "vv_source",
                    "rv_source",
                    "run_source",
                )
                for index, trade_date in enumerate(
                    (_SOURCE_ONLY_PRIOR_DATE, *_TRADE_DATES),
                    start=1,
                )
            ],
        )
        conn.executemany(
            "insert into fact_market_breadth_daily values "
            "(?, 1, 1, 0, 0, 0, 0, 'sv_old', 'vv_old', ?, 'run_old')",
            [
                (_TRADE_DATES[0], "rv_market_breadth_daily_v1"),
                (_TRADE_DATES[1], "rv_market_breadth_daily_v2"),
                (_TRADE_DATES[2], RULE_VERSION),
            ],
        )
    finally:
        conn.close()


def _rule_versions(duckdb_path: Path) -> list[tuple[str, str]]:
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        return [
            (str(row[0]), str(row[1]))
            for row in conn.execute(
                "select trade_date, rule_version from fact_market_breadth_daily order by trade_date"
            ).fetchall()
        ]
    finally:
        conn.close()


def test_dry_run_plan_lists_stale_dates_without_writing(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_backfill_scenario(db)
    before = _rule_versions(db)

    plan = build_market_breadth_backfill_plan(
        duckdb_path=str(db),
        start_date="2026-01-01",
        end_date="2026-01-31",
        min_observations_per_day=1,
    )

    assert plan["status"] == "dry_run"
    assert plan["would_recompute_row_count"] == 2
    assert plan["trade_dates"] == ["2026-01-05", "2026-01-06"]
    assert _rule_versions(db) == before


def test_cli_dry_run_emits_json_plan(tmp_path: Path, capsys) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_backfill_scenario(db)

    exit_code = main(
        [
            "--db-path",
            str(db),
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-01-31",
            "--min-observations-per-day",
            "1",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "dry_run"
    assert payload["would_recompute_row_count"] == 2
    assert payload["trade_dates"] == ["2026-01-05", "2026-01-06"]


def test_apply_is_idempotent_and_skips_current_v3_rows(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_backfill_scenario(db)

    first = apply_market_breadth_backfill(
        duckdb_path=str(db),
        start_date="2026-01-01",
        end_date="2026-01-31",
        min_observations_per_day=1,
    )
    second = apply_market_breadth_backfill(
        duckdb_path=str(db),
        start_date="2026-01-01",
        end_date="2026-01-31",
        min_observations_per_day=1,
    )

    assert first["status"] == "completed"
    assert first["recomputed_row_count"] == 2
    assert second["status"] == "noop"
    assert second["recomputed_row_count"] == 0
    assert _rule_versions(db) == [(trade_date, RULE_VERSION) for trade_date in _TRADE_DATES]
