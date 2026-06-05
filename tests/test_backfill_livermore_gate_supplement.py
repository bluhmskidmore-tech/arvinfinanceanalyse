from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb

from scripts.backfill_livermore_gate_supplement import backfill_livermore_gate_supplement


def _seed_csi300(duckdb_path: Path, *, start: date, n_days: int) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
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
        rows = []
        for offset in range(n_days):
            trade_date = (start + timedelta(days=offset)).isoformat()
            rows.append(
                (
                    "CA.CSI300",
                    "CSI300",
                    trade_date,
                    3200.0 + offset * 8.0,
                    "daily",
                    "index",
                    "sv",
                    "vv",
                    "rv",
                    "ok",
                    "run",
                )
            )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def test_backfill_gate_supplement_writes_rows(tmp_path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_csi300(db, start=date(2026, 1, 1), n_days=40)
    result = backfill_livermore_gate_supplement(
        duckdb_path=db,
        as_of_date=date(2026, 2, 9),
        lookback_days=60,
    )
    assert result["status"] == "completed"
    assert int(result["computed_rows"]) > 0

    conn = duckdb.connect(str(db), read_only=True)
    try:
        count = conn.execute("select count(*) from fact_livermore_gate_supplement_daily").fetchone()[0]
        latest = conn.execute("select max(trade_date) from fact_livermore_gate_supplement_daily").fetchone()[0]
    finally:
        conn.close()
    assert int(count) > 0
    assert str(latest)[:10] == "2026-02-09"
