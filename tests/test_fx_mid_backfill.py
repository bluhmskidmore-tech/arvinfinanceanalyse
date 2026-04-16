from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import duckdb
import pytest

from tests.helpers import load_module


def test_fx_mid_backfill_validates_explicit_date_range():
    module = load_module(
        "backend.app.tasks.fx_mid_backfill",
        "backend/app/tasks/fx_mid_backfill.py",
    )

    with pytest.raises(ValueError, match="start_date is required"):
        module.backfill_fx_mid_history.fn(start_date="", end_date="2026-02-28")
    with pytest.raises(ValueError, match="end_date must be on or after start_date"):
        module.backfill_fx_mid_history.fn(start_date="2026-02-28", end_date="2026-02-27")


def test_fx_mid_backfill_is_idempotent_for_same_range(tmp_path, monkeypatch):
    module = load_module(
        "backend.app.tasks.fx_mid_backfill",
        "backend/app/tasks/fx_mid_backfill.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              vendor_name varchar,
              vendor_version varchar,
              vendor_series_code varchar,
              observed_trade_date date
            )
            """
        )
    finally:
        conn.close()

    def fake_materialize(*, report_date, duckdb_path, data_input_root, official_csv_path="", explicit_csv_path=""):
        conn = duckdb.connect(duckdb_path, read_only=False)
        try:
            conn.execute(
                "delete from fx_daily_mid where trade_date = ? and base_currency = 'USD' and quote_currency = 'CNY'",
                [report_date],
            )
            conn.execute(
                """
                insert into fx_daily_mid values (?, 'USD', 'CNY', ?, 'CFETS', true, false, ?, 'choice', 'vv_choice_fixture', 'EMM00058124', ?)
                """,
                [report_date, Decimal("7.24"), f"sv_{report_date}", report_date],
            )
        finally:
            conn.close()
        return {
            "status": "completed",
            "report_date": report_date,
            "row_count": 1,
            "source_version": f"sv_{report_date}",
            "vendor_version": "vv_choice_fixture",
            "source_kind": "choice",
        }

    monkeypatch.setattr(
        module,
        "materialize_fx_mid_for_report_date",
        SimpleNamespace(fn=fake_materialize),
    )

    first = module.backfill_fx_mid_history.fn(
        start_date="2026-02-27",
        end_date="2026-02-28",
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
    )
    second = module.backfill_fx_mid_history.fn(
        start_date="2026-02-27",
        end_date="2026-02-28",
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
    )

    assert first["status"] == "completed"
    assert second["status"] == "completed"

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        total_rows = conn.execute("select count(*) from fx_daily_mid").fetchone()[0]
        keyed_rows = conn.execute(
            "select trade_date, count(*) from fx_daily_mid group by trade_date order by trade_date"
        ).fetchall()
    finally:
        conn.close()

    assert total_rows == 2
    assert keyed_rows == [(date(2026, 2, 27), 1), (date(2026, 2, 28), 1)]
