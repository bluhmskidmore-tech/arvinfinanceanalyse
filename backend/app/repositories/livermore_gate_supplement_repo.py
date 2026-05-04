from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from backend.app.core_finance.livermore_strategy import MarketGateSupplement

TABLE_NAME = "fact_livermore_gate_supplement_daily"


def fetch_market_gate_supplement(*, duckdb_path: str, trade_date: date) -> MarketGateSupplement | None:
    path = Path(duckdb_path)
    if not path.is_file():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return None
    try:
        row = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'main' and table_name = ?
            limit 1
            """,
            [TABLE_NAME],
        ).fetchone()
        if row is None:
            return None
        hit = conn.execute(
            f"""
            select breadth_5d, limit_up_quality_ok
            from {TABLE_NAME}
            where trade_date = ?
            """,
            [trade_date.isoformat()],
        ).fetchone()
    except duckdb.Error:
        return None
    finally:
        conn.close()

    if not hit:
        return None
    b_raw, lim_raw = hit[0], hit[1]
    breadth = float(b_raw) if b_raw is not None else None
    lim_ok: bool | None
    if lim_raw is None:
        lim_ok = None
    else:
        lim_ok = bool(lim_raw)
    return MarketGateSupplement(
        trade_date=trade_date,
        breadth_5d=breadth,
        limit_up_quality_ok=lim_ok,
    )
