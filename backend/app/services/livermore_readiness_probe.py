from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from backend.app.repositories.choice_stock_adapter import load_choice_stock_readiness
from backend.app.repositories.livermore_gate_supplement_repo import TABLE_NAME as GATE_SUPPLEMENT_TABLE
from backend.app.services.market_data_livermore_service import (
    _load_broad_index_history,
    _risk_exit_input_block_reason,
)


@dataclass(frozen=True)
class LivermoreReadinessReport:
    """只读汇总：Livermore 宽基历史切片与 Choice 股票目录门禁。供脚本与测试复用。"""

    duckdb_path: str
    duckdb_exists: bool
    catalog_path: str
    tables_used: tuple[str, ...]
    history_count: int
    first_trade_date: str | None
    last_trade_date: str | None
    requested_as_of: str | None
    resolved_differs_from_as_of: bool
    stock_ready: bool
    stock_status: str
    stock_message: str
    stock_missing_families: tuple[str, ...]
    gate_supplement_max_date: str | None
    gate_supplement_landed_for_last_trade: bool
    position_active_max_date: str | None
    position_landed_for_last_trade: bool
    risk_exit_block_reason: str

    def to_printable_dict(self) -> dict[str, Any]:
        return asdict(self)


def _probe_gate_supplement_max_date(duckdb_path: str) -> str | None:
    path = Path(duckdb_path)
    if not path.is_file():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return None
    try:
        exists = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'main' and table_name = ?
            limit 1
            """,
            [GATE_SUPPLEMENT_TABLE],
        ).fetchone()
        if exists is None:
            return None
        row = conn.execute(f"select max(trade_date) from {GATE_SUPPLEMENT_TABLE}").fetchone()
    except duckdb.Error:
        return None
    finally:
        conn.close()
    if not row or row[0] is None:
        return None
    value = row[0]
    return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]


def _probe_position_active_max_date(duckdb_path: str) -> str | None:
    path = Path(duckdb_path)
    if not path.is_file():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return None
    try:
        exists = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'main' and table_name = 'livermore_position_snapshot'
            limit 1
            """
        ).fetchone()
        if exists is None:
            return None
        row = conn.execute(
            """
            select max(cast(as_of_date as date))
            from livermore_position_snapshot
            where upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
            """
        ).fetchone()
    except duckdb.Error:
        return None
    finally:
        conn.close()
    if not row or row[0] is None:
        return None
    value = row[0]
    return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]


def probe_livermore_readiness(
    *,
    duckdb_path: str,
    catalog_path: str,
    as_of_date: date | None = None,
) -> LivermoreReadinessReport:
    path_obj = Path(duckdb_path)
    exists = path_obj.is_file()
    tables_used: tuple[str, ...] = ()
    rows: list[Any] = []
    if exists:
        rows, table_list = _load_broad_index_history(duckdb_path=duckdb_path, as_of_date=as_of_date)
        tables_used = tuple(table_list)

    stock = load_choice_stock_readiness(catalog_path)
    first = rows[0].trade_date.isoformat() if rows else None
    last = rows[-1].trade_date.isoformat() if rows else None
    requested = as_of_date.isoformat() if as_of_date is not None else None
    resolved_differs = bool(
        as_of_date is not None and rows and rows[-1].trade_date != as_of_date
    )
    supplement_max = _probe_gate_supplement_max_date(duckdb_path) if exists else None
    position_max = _probe_position_active_max_date(duckdb_path) if exists else None
    supplement_landed = bool(last and supplement_max and supplement_max >= last)
    position_landed = bool(last and position_max and position_max >= last)
    risk_block_reason = (
        _risk_exit_input_block_reason(duckdb_path=duckdb_path, as_of_date=last)
        if exists and last
        else ""
    )
    return LivermoreReadinessReport(
        duckdb_path=str(Path(duckdb_path).resolve()) if exists else duckdb_path,
        duckdb_exists=exists,
        catalog_path=str(Path(catalog_path).resolve()) if Path(catalog_path).exists() else catalog_path,
        tables_used=tables_used,
        history_count=len(rows),
        first_trade_date=first,
        last_trade_date=last,
        requested_as_of=requested,
        resolved_differs_from_as_of=resolved_differs,
        stock_ready=stock.ready,
        stock_status=str(stock.status),
        stock_message=stock.message,
        stock_missing_families=tuple(str(x) for x in stock.missing_input_families),
        gate_supplement_max_date=supplement_max,
        gate_supplement_landed_for_last_trade=supplement_landed,
        position_active_max_date=position_max,
        position_landed_for_last_trade=position_landed,
        risk_exit_block_reason=risk_block_reason,
    )
