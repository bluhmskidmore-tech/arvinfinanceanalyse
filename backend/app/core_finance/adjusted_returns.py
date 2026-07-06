from __future__ import annotations

from pathlib import Path

import duckdb

from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

PRICE_ADJUSTMENT_MODE = "adj_factor_ratio"
STOCK_ADJUSTMENT_FACTOR_TABLE = "stock_adjustment_factor"


def ensure_stock_adjustment_factor_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "30_stock_adjustment_factor.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def adjusted_return(
    *,
    start_price: float | None,
    start_adj_factor: float | None,
    end_price: float | None,
    end_adj_factor: float | None,
) -> float | None:
    if not all(_is_positive(value) for value in (start_price, start_adj_factor, end_price, end_adj_factor)):
        return None
    assert start_price is not None
    assert start_adj_factor is not None
    assert end_price is not None
    assert end_adj_factor is not None
    return (end_price * end_adj_factor) / (start_price * start_adj_factor) - 1.0


def net_return_after_costs(
    gross_return: float | None,
    *,
    buy_cost_rate: float,
    sell_cost_rate: float,
    slippage_rate: float,
) -> float | None:
    if gross_return is None:
        return None
    return gross_return - buy_cost_rate - sell_cost_rate - 2 * slippage_rate


def factors_changed(values: list[float | None], *, tolerance: float = 1e-12) -> bool:
    valid = [float(value) for value in values if _is_positive(value)]
    if len(valid) < 2:
        return False
    first = valid[0]
    return any(abs(value - first) > tolerance for value in valid[1:])


def normalize_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _is_positive(value: float | None) -> bool:
    return value is not None and value > 0
