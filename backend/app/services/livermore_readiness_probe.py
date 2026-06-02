from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from backend.app.repositories.choice_stock_adapter import load_choice_stock_readiness
from backend.app.services.market_data_livermore_service import _load_broad_index_history


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

    def to_printable_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    )
