from __future__ import annotations

import csv
import sys
from datetime import date
from decimal import Decimal

import duckdb

from tests.helpers import load_module


def _load_fx_task_module():
    fx_mod = sys.modules.get("backend.app.tasks.fx_mid_materialize")
    if fx_mod is None:
        fx_mod = load_module(
            "backend.app.tasks.fx_mid_materialize",
            "backend/app/tasks/fx_mid_materialize.py",
        )
    return fx_mod


def test_fx_mid_materialize_populates_duckdb_from_csv(tmp_path):
    fx_mod = _load_fx_task_module()

    csv_path = tmp_path / "fx_mid.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "trade_date",
                "base_currency",
                "quote_currency",
                "mid_rate",
                "source_name",
                "is_business_day",
                "is_carry_forward",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "trade_date": "2026-02-27",
                "base_currency": "美元",
                "quote_currency": "人民币",
                "mid_rate": "7.24",
                "source_name": "CFETS",
                "is_business_day": "true",
                "is_carry_forward": "false",
            }
        )

    payload = fx_mod.materialize_fx_mid_rows.fn(
        csv_path=str(csv_path),
        duckdb_path=str(duckdb_path),
    )

    assert payload["status"] == "completed"
    assert payload["row_count"] == 1

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, base_currency, quote_currency, mid_rate, source_name,
                   is_business_day, is_carry_forward
            from fx_daily_mid
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [(date(2026, 2, 27), "USD", "CNY", Decimal("7.24000000"), "CFETS", True, False)]


def test_fx_mid_materialize_preserves_existing_unrelated_rows(tmp_path):
    fx_mod = _load_fx_task_module()

    csv_path = tmp_path / "fx_mid.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "trade_date",
                "base_currency",
                "quote_currency",
                "mid_rate",
                "source_name",
                "is_business_day",
                "is_carry_forward",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "trade_date": "2026-02-27",
                "base_currency": "USD",
                "quote_currency": "CNY",
                "mid_rate": "7.24",
                "source_name": "CFETS",
                "is_business_day": "true",
                "is_carry_forward": "false",
            }
        )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ["2026-02-26", "USD", "CNY", Decimal("7.20"), "CFETS", True, False, "sv_old"],
        )
    finally:
        conn.close()

    fx_mod.materialize_fx_mid_rows.fn(
        csv_path=str(csv_path),
        duckdb_path=str(duckdb_path),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, base_currency, quote_currency, mid_rate, source_version
            from fx_daily_mid
            order by trade_date
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        (date(2026, 2, 26), "USD", "CNY", Decimal("7.20000000"), "sv_old"),
        (date(2026, 2, 27), "USD", "CNY", Decimal("7.24000000"), rows[1][4]),
    ]
