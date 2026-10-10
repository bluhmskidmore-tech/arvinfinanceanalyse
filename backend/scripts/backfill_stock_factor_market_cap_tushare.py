"""One-off / repeatable backfill: total_mv / circ_mv from Tushare daily_basic.

The explicit target is read to choose the latest factor snapshot date (or an
explicit one); schema changes and upserts run through the guarded task writer.

Units: Tushare daily_basic reports total_mv / circ_mv in 万元; this project
normalizes monetary amounts to 元 (docs/data_contracts.md §4.10), so values
are stored multiplied by 10000.

Run: backend/.venv/Scripts/python.exe -m backend.scripts.backfill_stock_factor_market_cap_tushare --duckdb-path <target.duckdb> [as_of_date]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_read_context import active_read_scope
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.tasks.stock_factor_market_cap_backfill import (
    RULE_VERSION as RULE_VERSION,
    SOURCE_VERSION as SOURCE_VERSION,
    TABLE,
    backfill_market_cap_rows,
    market_cap_target_identity,
)

logger = logging.getLogger(__name__)


def _latest_factor_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    row = conn.execute(f"select max(as_of_date) from {TABLE}").fetchone()
    return str(row[0]) if row and row[0] is not None else None


def run(as_of_date: str | None = None, *, duckdb_path: str | Path) -> dict[str, Any]:
    if not str(duckdb_path).strip():
        raise ValueError("duckdb_path must be explicit")
    target = Path(duckdb_path).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"DuckDB file not found: {target}")
    settings = get_settings()
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN is not configured.")

    expected_identity = market_cap_target_identity(target)
    with active_read_scope(), read_only_connection(str(target)) as conn:
        target_date = as_of_date or _latest_factor_date(conn)
        if market_cap_target_identity(target) != expected_identity:
            raise PermissionError("DuckDB target identity changed during the preflight read")
    if not target_date:
        raise RuntimeError(f"{TABLE} is empty; nothing to backfill.")
    trade_date = target_date.replace("-", "")
    pro = import_tushare_pro().pro_api(token)
    df = pro.daily_basic(
        trade_date=trade_date,
        fields="ts_code,trade_date,total_mv,circ_mv",
    )
    if df is None or df.empty:
        raise RuntimeError(f"tushare daily_basic returned no rows for trade_date={trade_date}.")
    counts = backfill_market_cap_rows(
        duckdb_path=target,
        as_of_date=target_date,
        records=df.to_dict("records"),
        expected_identity=expected_identity,
    )
    return {
        "as_of_date": target_date,
        "trade_date": trade_date,
        "tushare_rows": len(df),
        **counts,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("as_of_date", nargs="?")
    parser.add_argument("--duckdb-path", required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    print(run(args.as_of_date, duckdb_path=args.duckdb_path))


if __name__ == "__main__":
    main()
