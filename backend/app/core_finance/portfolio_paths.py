from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import duckdb
from backend.app.core_finance.adjusted_returns import net_return_after_costs
from backend.app.core_finance.field_normalization import is_tradestatus_halted

TABLE_OBS = "choice_stock_daily_observation"
TABLE_ADJ_FACTOR = "stock_adjustment_factor"
TABLE_LIMIT_PRICE = "stock_limit_price_daily"
PATH_BASIS_ADJUSTED = "adjusted"
PATH_BASIS_RAW_FALLBACK = "raw_fallback_missing_adj_factor"
# 涨跌停数值价三态来源标记（docs/data_contracts.md §4.10 覆盖缺口）：
# - stk_limit：stock_limit_price_daily 专用表数值价（tushare stk_limit）命中；
# - observation_cast：新表无行，observation 列 try_cast 出正数值（tushare 代际旧数值）；
# - missing：两者皆无，维持现状 fail-open（choice_native 段无数值价时跌停判定失效）。
LIMIT_PRICE_SOURCE_TABLE = "stk_limit"
LIMIT_PRICE_SOURCE_OBSERVATION = "observation_cast"
LIMIT_PRICE_SOURCE_MISSING = "missing"


def position_path_key(stock_code: object, entry_date: object) -> str:
    return f"{str(stock_code).strip()}|{str(entry_date)[:10]}"


def load_position_price_paths(
    conn: duckdb.DuckDBPyConnection,
    entries: Sequence[Mapping[str, object]],
    *,
    max_horizon_days: int = 25,
) -> dict[str, list[dict[str, object]]]:
    if max_horizon_days <= 0:
        raise ValueError("max_horizon_days must be positive")
    tables = _table_names(conn)
    if TABLE_OBS not in tables:
        return {}
    obs_columns = _columns(conn, TABLE_OBS)
    if not {"trade_date", "stock_code", "close_value"}.issubset(obs_columns):
        return {}
    has_adj = TABLE_ADJ_FACTOR in tables and {"stock_code", "trade_date", "adj_factor"}.issubset(
        _columns(conn, TABLE_ADJ_FACTOR)
    )
    has_limit_price = TABLE_LIMIT_PRICE in tables and {
        "stock_code",
        "trade_date",
        "up_limit",
        "down_limit",
    }.issubset(_columns(conn, TABLE_LIMIT_PRICE))

    entry_keys: list[tuple[str, str]] = []
    for entry in entries:
        stock_code = str(entry.get("stock_code") or "").strip()
        entry_date = str(entry.get("entry_date") or "")[:10]
        if not stock_code or not entry_date:
            continue
        entry_keys.append((stock_code, entry_date))
    if not entry_keys:
        return {}

    raw_rows_by_stock = _load_raw_bars_by_stock(
        conn,
        stock_codes=sorted({stock_code for stock_code, _entry_date in entry_keys}),
        min_entry_date=min(entry_date for _stock_code, entry_date in entry_keys),
        has_adj=has_adj,
        has_limit_price=has_limit_price,
    )
    paths: dict[str, list[dict[str, object]]] = {}
    for stock_code, entry_date in entry_keys:
        rows = [
            row
            for trade_date, row in raw_rows_by_stock.get(stock_code, ())
            if trade_date >= entry_date
        ]
        if rows:
            normalized_rows = _apply_path_price_basis(_normalize_path_rows(rows))
            paths[position_path_key(stock_code, entry_date)] = _truncate_after_horizon_exit(
                normalized_rows,
                max_horizon_days=max_horizon_days,
            )
    return paths


def calculate_path_horizon_exit(
    rows: Sequence[Mapping[str, object]],
    *,
    horizon_days: int,
    entry_price: float | None,
    buy_cost_rate: float,
    sell_cost_rate: float,
    slippage_rate: float,
) -> dict[str, object] | None:
    if horizon_days <= 0 or not rows:
        return None
    entry = path_entry_price(rows[0], fallback=entry_price)
    if entry is None or entry <= 0:
        return None
    exit_row = _first_sellable_path_row_at_or_after(rows, horizon_days - 1)
    if exit_row is None:
        return None
    exit_price = path_mark_price(exit_row)
    exit_date = str(exit_row.get("trade_date") or exit_row.get("date") or "")[:10]
    if exit_price is None or exit_price <= 0 or not exit_date:
        return None
    gross = exit_price / entry - 1.0
    return {
        "exit_date": exit_date,
        "entry_price": entry,
        "exit_price": exit_price,
        "return_net": net_return_after_costs(
            gross,
            buy_cost_rate=buy_cost_rate,
            sell_cost_rate=sell_cost_rate,
            slippage_rate=slippage_rate,
        ),
    }


def path_entry_price(row: Mapping[str, object], *, fallback: float | None) -> float | None:
    if _uses_raw_price_basis(row):
        return _first_float(row.get("open"), row.get("open_value"), fallback)
    return _first_float(row.get("adj_open"), row.get("open"), row.get("open_value"), fallback)


def path_mark_price(row: Mapping[str, object]) -> float | None:
    if _uses_raw_price_basis(row):
        return _first_float(row.get("close"), row.get("close_value"))
    return _first_float(row.get("adj_close"), row.get("close"), row.get("close_value"))


def _load_raw_bars_by_stock(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_codes: Sequence[str],
    min_entry_date: str,
    has_adj: bool,
    has_limit_price: bool = False,
) -> dict[str, list[tuple[str, tuple[Any, ...]]]]:
    if not stock_codes:
        return {}
    adj_select = "af.adj_factor" if has_adj else "cast(null as double) as adj_factor"
    adj_join = (
        f"""
        left join {TABLE_ADJ_FACTOR} af
          on af.stock_code = d.stock_code
         and af.trade_date = d.trade_date
        """
        if has_adj
        else ""
    )
    limit_select = (
        "lp.up_limit, lp.down_limit"
        if has_limit_price
        else "cast(null as double) as up_limit, cast(null as double) as down_limit"
    )
    limit_join = (
        f"""
        left join {TABLE_LIMIT_PRICE} lp
          on lp.stock_code = d.stock_code
         and cast(lp.trade_date as varchar) = cast(d.trade_date as varchar)
        """
        if has_limit_price
        else ""
    )
    stock_placeholders = ", ".join("?" for _stock_code in stock_codes)
    rows = conn.execute(
        f"""
        select
          d.stock_code,
          d.trade_date,
          d.open_value,
          d.high_value,
          d.low_value,
          d.close_value,
          d.volume,
          d.amount,
          d.tradestatus,
          d.highlimit,
          d.lowlimit,
          {adj_select},
          {limit_select}
        from {TABLE_OBS} d
        {adj_join}
        {limit_join}
        where d.stock_code in ({stock_placeholders})
          and cast(d.trade_date as date) >= cast(? as date)
          and d.close_value is not null
        order by d.stock_code, cast(d.trade_date as date)
        """,
        [*stock_codes, min_entry_date],
    ).fetchall()
    by_stock: dict[str, list[tuple[str, tuple[Any, ...]]]] = {}
    for row in rows:
        stock_code = str(row[0]).strip()
        trade_date = str(row[1])[:10]
        by_stock.setdefault(stock_code, []).append((trade_date, row[1:]))
    return by_stock


def _normalize_path_rows(rows: Sequence[tuple[Any, ...]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    previous_close: float | None = None
    previous_adj_close: float | None = None
    previous_adj_factor: float | None = None
    for row in rows:
        (
            trade_date,
            open_value,
            high_value,
            low_value,
            close_value,
            volume,
            amount,
            tradestatus,
            highlimit,
            lowlimit,
            adj_factor,
            table_up_limit,
            table_down_limit,
        ) = row
        raw_close = _float_or_none(close_value)
        halted = is_tradestatus_halted(tradestatus)
        close_for_mark = previous_close if halted and previous_close is not None else raw_close
        source_factor = _positive_float(adj_factor)
        adj_factor_missing = source_factor is None
        factor = source_factor if source_factor is not None else previous_adj_factor
        adj_factor_forward_filled = adj_factor_missing and factor is not None
        adjusted = {
            "adj_open": _adjust_price(open_value, factor),
            "adj_high": _adjust_price(high_value, factor),
            "adj_low": _adjust_price(low_value, factor),
            "adj_close": _adjust_price(close_for_mark, factor),
        }
        if halted and previous_adj_close is not None:
            adjusted = {key: previous_adj_close for key in adjusted}
        resolved_highlimit, resolved_lowlimit, limit_price_source = resolve_limit_prices(
            observation_highlimit=highlimit,
            observation_lowlimit=lowlimit,
            table_up_limit=table_up_limit,
            table_down_limit=table_down_limit,
        )
        out.append(
            {
                "trade_date": str(trade_date)[:10],
                "open": _float_or_none(open_value),
                "high": _float_or_none(high_value),
                "low": _float_or_none(low_value),
                "close": close_for_mark,
                "volume": _float_or_none(volume),
                "amount": _float_or_none(amount),
                "tradestatus": "" if tradestatus is None else str(tradestatus).strip(),
                "highlimit": resolved_highlimit,
                "lowlimit": resolved_lowlimit,
                "limit_price_source": limit_price_source,
                "adj_factor": factor,
                "adj_factor_missing": adj_factor_missing,
                "adj_factor_forward_filled": adj_factor_forward_filled,
                "halted": halted,
                "limit_down": _is_limit_down(close_for_mark, resolved_lowlimit),
                **adjusted,
            }
        )
        if source_factor is not None:
            previous_adj_factor = source_factor
        if close_for_mark is not None:
            previous_close = close_for_mark
        if out[-1]["adj_close"] is not None:
            previous_adj_close = float(out[-1]["adj_close"])
    return out


def _apply_path_price_basis(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    has_unfilled_factor = any(
        bool(row.get("adj_factor_missing"))
        and not bool(row.get("adj_factor_forward_filled"))
        for row in rows
    )
    basis = PATH_BASIS_RAW_FALLBACK if has_unfilled_factor else PATH_BASIS_ADJUSTED
    return [dict(row, path_price_basis=basis) for row in rows]


def _uses_raw_price_basis(row: Mapping[str, object]) -> bool:
    return str(row.get("path_price_basis") or "") == PATH_BASIS_RAW_FALLBACK


def _adjust_price(value: object, factor: float | None) -> float | None:
    price = _float_or_none(value)
    if price is None:
        return None
    if factor is None:
        return price
    return price * factor


def resolve_limit_prices(
    *,
    observation_highlimit: object,
    observation_lowlimit: object,
    table_up_limit: object,
    table_down_limit: object,
) -> tuple[float | None, float | None, str]:
    """三态解析涨跌停数值价（单行、单源，不跨源混合）。

    优先 stock_limit_price_daily 数值价，且要求 up/down 两列同时为有效正数才选
    表来源（半缺失行视为新表不可用，防止摄入异常产生的残行遮蔽 observation
    回退）；否则回退 observation 列 try_cast（tushare 代际旧数值仍可用）；两者
    皆无维持 fail-open（missing），与切换前 choice_native 段行为一致，仅多出
    来源标记。execution bars 消费端
    （backend/app/tasks/livermore_candidate_history_materialize.py）共享本实现，
    两处口径保持一致。
    """
    resolved_high = _positive_float(table_up_limit)
    resolved_low = _positive_float(table_down_limit)
    if resolved_high is not None and resolved_low is not None:
        return resolved_high, resolved_low, LIMIT_PRICE_SOURCE_TABLE
    cast_high = _positive_float(observation_highlimit)
    cast_low = _positive_float(observation_lowlimit)
    if cast_high is not None or cast_low is not None:
        return cast_high, cast_low, LIMIT_PRICE_SOURCE_OBSERVATION
    return None, None, LIMIT_PRICE_SOURCE_MISSING


def _is_limit_down(close_value: object, lowlimit: object) -> bool:
    close = _positive_float(close_value)
    low = _positive_float(lowlimit)
    return bool(close is not None and low is not None and close <= low * 1.001)


def _first_sellable_path_row_at_or_after(
    rows: Sequence[Mapping[str, object]],
    start_index: int,
) -> Mapping[str, object] | None:
    for row in rows[max(start_index, 0) :]:
        if is_tradestatus_halted(row.get("tradestatus")) or bool(row.get("halted")):
            continue
        if _is_limit_down(row.get("close") or row.get("close_value"), row.get("lowlimit")) or bool(row.get("limit_down")):
            continue
        if path_mark_price(row) is None:
            continue
        return row
    return None


def _truncate_after_horizon_exit(
    rows: Sequence[Mapping[str, object]],
    *,
    max_horizon_days: int,
) -> list[dict[str, object]]:
    if len(rows) <= max_horizon_days:
        return [dict(row) for row in rows]
    first_sellable = _first_sellable_path_row_at_or_after(rows, max_horizon_days - 1)
    if first_sellable is None:
        return [dict(row) for row in rows]
    for index, row in enumerate(rows):
        if row is first_sellable:
            return [dict(item) for item in rows[: index + 1]]
    return [dict(row) for row in rows]


def _first_float(*values: object) -> float | None:
    for value in values:
        coerced = _float_or_none(value)
        if coerced is not None:
            return coerced
    return None


def _positive_float(value: object) -> float | None:
    number = _float_or_none(value)
    if number is None or number <= 0:
        return None
    return number


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}
