"""Roll up formal PnL-by-business rows into V1-compatible yield-by-period summaries.

Reads the same persisted facts as ``PnlRepository.fetch_yearly_business_rows``:
``fact_formal_pnl_fi``, ``fact_nonstd_pnl_bridge``, ``fact_formal_zqtz_balance_daily``.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any


def _dec(x: object) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _month_length(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def _month_bounds(year: int, month: int) -> tuple[str, str, int]:
    start = date(year, month, 1)
    end = date(year, month, _month_length(year, month))
    return start.isoformat(), end.isoformat(), (end - start).days + 1


def _quarter_bounds(year: int, quarter: int) -> tuple[str, str, int]:
    first_month = (quarter - 1) * 3 + 1
    last_month = first_month + 2
    start = date(year, first_month, 1)
    end = date(year, last_month, _month_length(year, last_month))
    return start.isoformat(), end.isoformat(), (end - start).days + 1


def _year_bounds(year: int) -> tuple[str, str, int]:
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    return start.isoformat(), end.isoformat(), (end - start).days + 1


def _pct_yield(total_pnl: Decimal, scale: Decimal) -> float | None:
    if scale == 0:
        return None
    return float(total_pnl / scale * Decimal("100"))


def _annualized_pct(total_pnl: Decimal, scale: Decimal, num_days: int) -> float | None:
    if scale == 0 or num_days <= 0:
        return None
    daily = total_pnl / scale
    return float(daily * (Decimal("365") / Decimal(num_days)) * Decimal("100"))


def _items_for_rows(group_rows: list[dict[str, object]]) -> list[dict[str, Any]]:
    by_bt: dict[str, list[dict[str, object]]] = defaultdict(list)
    for r in group_rows:
        bt = str(r.get("business_type_primary") or "未分类")
        by_bt[bt].append(r)
    out: list[dict[str, Any]] = []
    for bt, rlist in sorted(by_bt.items(), key=lambda x: x[0]):
        tp = sum(_dec(x["total_pnl"]) for x in rlist)
        sc = sum(_dec(x["scale_amount"]) for x in rlist)
        out.append(
            {
                "business_type_primary": bt,
                "total_pnl": float(tp),
                "scale_amount": float(sc),
                "yield_pct": _pct_yield(tp, sc),
            }
        )
    return out


def _sort_quarter_keys(keys: list[str]) -> list[str]:
    def key_fn(k: str) -> tuple[int, int]:
        if "-Q" not in k:
            return (0, 0)
        y, _, q = k.partition("-Q")
        return int(y), int(q)

    return sorted(keys, key=key_fn)


def rollup_yield_periods(
    rows: list[dict[str, object]],
    *,
    year: int,
    period_type: str,
) -> list[dict[str, Any]]:
    """Aggregate yearly business rows into period buckets."""
    norm = str(period_type or "monthly").strip().lower()
    if norm not in {"monthly", "quarterly", "yearly"}:
        norm = "monthly"

    ys = str(year)
    year_rows = [r for r in rows if str(r.get("report_date", ""))[:4] == ys]
    if not year_rows:
        return []

    if norm == "yearly":
        tp = sum(_dec(r["total_pnl"]) for r in year_rows)
        sc = sum(_dec(r["scale_amount"]) for r in year_rows)
        start, end, nd = _year_bounds(year)
        oy = _pct_yield(tp, sc)
        ann = _annualized_pct(tp, sc, nd)
        return [
            {
                "period": ys,
                "period_type": norm,
                "start_date": start,
                "end_date": end,
                "num_days": nd,
                "total_avg_balance": float(sc),
                "total_pnl": float(tp),
                "overall_yield": oy,
                "overall_annualized_yield": ann,
                "weighted_portfolio_yield": oy,
                "weighted_portfolio_annualized_yield": ann,
                "items": _items_for_rows(year_rows),
            }
        ]

    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    for r in year_rows:
        rd = str(r.get("report_date") or "")[:10]
        if len(rd) < 10:
            continue
        if norm == "monthly":
            key = rd[:7]
        else:
            d = date.fromisoformat(rd)
            q = (d.month - 1) // 3 + 1
            key = f"{d.year}-Q{q}"
        buckets[key].append(r)

    if norm == "monthly":
        ordered = sorted(buckets.keys())
    else:
        ordered = _sort_quarter_keys(list(buckets.keys()))

    out: list[dict[str, Any]] = []
    for key in ordered:
        group = buckets[key]
        tp = sum(_dec(r["total_pnl"]) for r in group)
        sc = sum(_dec(r["scale_amount"]) for r in group)

        if norm == "monthly":
            ym = key.split("-")
            y, m = int(ym[0]), int(ym[1])
            start, end, nd = _month_bounds(y, m)
        else:
            y_part, _, q_part = key.partition("-Q")
            y_i, q_i = int(y_part), int(q_part)
            start, end, nd = _quarter_bounds(y_i, q_i)

        oy = _pct_yield(tp, sc)
        ann = _annualized_pct(tp, sc, nd)
        out.append(
            {
                "period": key,
                "period_type": norm,
                "start_date": start,
                "end_date": end,
                "num_days": nd,
                "total_avg_balance": float(sc),
                "total_pnl": float(tp),
                "overall_yield": oy,
                "overall_annualized_yield": ann,
                "weighted_portfolio_yield": oy,
                "weighted_portfolio_annualized_yield": ann,
                "items": _items_for_rows(group),
            }
        )
    return out
