from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

PRICE_ADJUSTMENT_MODE = "adj_factor_ratio"
STOCK_ADJUSTMENT_FACTOR_TABLE = "stock_adjustment_factor"
SIGNAL_PRICE_ADJUSTMENT_MODE = "raw_price_times_factor_over_signal_factor"


@dataclass(frozen=True)
class SignalPriceHistory:
    closes: tuple[float, ...] = ()
    raw_closes: tuple[float, ...] = ()
    factors: tuple[float, ...] = ()
    unavailable_reason: str = ""


def signal_price_history(
    *,
    raw_prices: Sequence[object],
    trade_dates: Sequence[object],
    price_bases: Sequence[str],
    factor_rows: Sequence[tuple[object, object]],
    signal_date: str,
) -> SignalPriceHistory:
    """P(raw,t) * F(t) / F(signal), without filling or dropping window rows.

    The anchor is the signal day's raw close. Every supplied observation needs
    an unambiguous raw-price basis and exactly one positive finite factor.
    """
    if not raw_prices or len(raw_prices) != len(trade_dates) or len(raw_prices) != len(price_bases):
        return SignalPriceHistory(unavailable_reason="price_window_alignment_invalid")
    try:
        anchor = date.fromisoformat(signal_date)
        dates = [date.fromisoformat(str(value)) for value in trade_dates]
    except (TypeError, ValueError):
        return SignalPriceHistory(unavailable_reason="price_window_date_invalid")
    if dates[-1] != anchor or any(left >= right for left, right in zip(dates, dates[1:], strict=False)):
        return SignalPriceHistory(unavailable_reason="price_window_date_invalid")
    if any(value != "raw" for value in price_bases):
        return SignalPriceHistory(unavailable_reason="price_basis_unconfirmed_or_mixed")
    prices = [_positive_finite_float(value) for value in raw_prices]
    if any(value is None for value in prices):
        return SignalPriceHistory(unavailable_reason="raw_price_nonpositive_or_nonfinite")
    factors_by_date: dict[date, list[object]] = {}
    for factor_date, factor in factor_rows:
        try:
            parsed_date = date.fromisoformat(str(factor_date))
        except (TypeError, ValueError):
            return SignalPriceHistory(unavailable_reason="adjustment_factor_date_invalid")
        if parsed_date > anchor:
            return SignalPriceHistory(unavailable_reason="adjustment_factor_after_signal_date")
        factors_by_date.setdefault(parsed_date, []).append(factor)
    factors: list[float] = []
    for trade_day in dates:
        values = factors_by_date.get(trade_day, [])
        if not values:
            return SignalPriceHistory(unavailable_reason="adjustment_factor_missing")
        if len(values) != 1:
            return SignalPriceHistory(unavailable_reason="adjustment_factor_duplicate")
        factor = _positive_finite_float(values[0])
        if factor is None:
            return SignalPriceHistory(unavailable_reason="adjustment_factor_nonpositive_or_nonfinite")
        factors.append(factor)
    raw_closes = tuple(float(value) for value in prices if value is not None)
    closes = tuple(price * (factor / factors[-1]) for price, factor in zip(raw_closes, factors, strict=True))
    if not all(math.isfinite(value) and value > 0 for value in closes):
        return SignalPriceHistory(unavailable_reason="adjusted_price_nonpositive_or_nonfinite")
    return SignalPriceHistory(closes=closes, raw_closes=raw_closes, factors=tuple(factors))


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
    """Round-trip net return with costs charged multiplicatively on notional.

    ``(1 + r) * (1 - c) - 1`` with ``c = buy + sell + 2 * slippage``; the
    previous additive approximation ``r - c`` overstated net returns by the
    second-order term ``r * c``.
    """
    if gross_return is None:
        return None
    round_trip_cost_rate = buy_cost_rate + sell_cost_rate + 2 * slippage_rate
    return (1.0 + gross_return) * (1.0 - round_trip_cost_rate) - 1.0


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


def _positive_finite_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None
