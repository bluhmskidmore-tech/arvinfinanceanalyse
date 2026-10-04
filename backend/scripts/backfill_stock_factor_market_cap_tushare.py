"""One-off / repeatable backfill: total_mv / circ_mv from Tushare daily_basic.

Adds the two market-cap columns to choice_stock_factor_snapshot when missing,
then upserts rows for the latest factor snapshot date (or an explicit one).

Units: Tushare daily_basic reports total_mv / circ_mv in 万元; this project
normalizes monetary amounts to 元 (docs/data_contracts.md §4.10), so values
are stored multiplied by 10000.

Run:  backend/.venv/Scripts/python.exe -m backend.scripts.backfill_stock_factor_market_cap_tushare [as_of_date]
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)

logger = logging.getLogger(__name__)

SOURCE_VERSION = "tushare_daily_basic_market_cap_v1"
RULE_VERSION = "rv_tushare_daily_basic_market_cap_v1"
TABLE = "choice_stock_factor_snapshot"


def _ensure_market_cap_columns(conn: duckdb.DuckDBPyConnection) -> None:
    existing = {str(row[0]).lower() for row in conn.execute(f"describe {TABLE}").fetchall()}
    for column in ("total_mv", "circ_mv"):
        if column not in existing:
            conn.execute(f"alter table {TABLE} add column {column} double")


def _latest_factor_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    row = conn.execute(f"select max(as_of_date) from {TABLE}").fetchone()
    return str(row[0]) if row and row[0] is not None else None


def run(as_of_date: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN is not configured.")

    conn = duckdb.connect(str(settings.duckdb_path))
    try:
        _ensure_market_cap_columns(conn)
        target_date = as_of_date or _latest_factor_date(conn)
        if not target_date:
            raise RuntimeError(f"{TABLE} is empty; nothing to backfill.")
        trade_date = target_date.replace("-", "")

        ts = import_tushare_pro()
        pro = ts.pro_api(token)
        df = pro.daily_basic(
            trade_date=trade_date,
            fields="ts_code,trade_date,total_mv,circ_mv",
        )
        if df is None or df.empty:
            raise RuntimeError(f"tushare daily_basic returned no rows for trade_date={trade_date}.")

        updated = 0
        inserted = 0
        vendor_version = f"vv_tushare_daily_basic_{trade_date}"
        for record in df.to_dict("records"):
            stock_code = str(record.get("ts_code") or "").strip()
            if not stock_code:
                continue
            total_mv = record.get("total_mv")
            circ_mv = record.get("circ_mv")
            total_mv_yuan = float(total_mv) * 10000 if total_mv == total_mv and total_mv is not None else None
            circ_mv_yuan = float(circ_mv) * 10000 if circ_mv == circ_mv and circ_mv is not None else None
            if total_mv_yuan is None and circ_mv_yuan is None:
                continue
            existing = conn.execute(
                f"select 1 from {TABLE} where as_of_date = ? and stock_code = ? limit 1",
                [target_date, stock_code],
            ).fetchone()
            if existing is not None:
                conn.execute(
                    f"update {TABLE} set total_mv = ?, circ_mv = ? where as_of_date = ? and stock_code = ?",
                    [total_mv_yuan, circ_mv_yuan, target_date, stock_code],
                )
                updated += 1
            else:
                conn.execute(
                    f"""
                    insert into {TABLE} (
                      as_of_date, stock_code, pe, pb, ps, roe, gross_margin,
                      three_month_return, twelve_month_return, volatility, dividend_yield,
                      total_mv, circ_mv, industry, source_version, vendor_version, rule_version, run_id
                    ) values (?, ?, null, null, null, null, null, null, null, null, null, ?, ?, null, ?, ?, ?, ?)
                    """,
                    [
                        target_date,
                        stock_code,
                        total_mv_yuan,
                        circ_mv_yuan,
                        SOURCE_VERSION,
                        vendor_version,
                        RULE_VERSION,
                        f"tushare_market_cap:{target_date}",
                    ],
                )
                inserted += 1
        return {
            "as_of_date": target_date,
            "trade_date": trade_date,
            "tushare_rows": len(df),
            "updated": updated,
            "inserted": inserted,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run(sys.argv[1] if len(sys.argv) > 1 else None)
    print(result)
