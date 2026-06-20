"""
债券持仓「动作」粗粒度归因（V1 action_attribution 的 DuckDB 可落地简化版）。

基于期初/期末快照对比 + 区间内 fact_pnl_daily 汇总，将事件分为：
买入、卖出、增持、减持；信用/利率类别变化记为 SWITCH；其余归入调整。

不含 Wind 个券深度规则；正式使用需结合数据完整性与 warnings。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from .safe_decimal import safe_decimal


ACTION_TYPE_NAMES: dict[str, str] = {
    "TIMING_BUY": "择时买入",
    "TIMING_SELL": "择时卖出",
    "ADD_DURATION": "加久期",
    "REDUCE_DURATION": "减久期",
    "SWITCH": "换券/结构调整",
    "ADJUST": "持仓调整",
}


def _key(inst: str, book: str) -> str:
    return f"{inst}::{book}"


def _parse_key(k: str) -> tuple[str, str]:
    a, b = k.split("::", 1)
    return a, b


@dataclass
class _Line:
    instrument_id: str
    book_id: str
    market_value: Decimal
    mod_dur: Decimal
    accounting_class: str


def _line_from_row(row: Mapping[str, Any]) -> _Line | None:
    inst = str(row.get("bond_code") or row.get("instrument_id") or "").strip()
    book = str(row.get("book_id") or "").strip()
    if not inst:
        return None
    mv = safe_decimal(row.get("market_value"))
    md = safe_decimal(row.get("modified_duration"))
    acct = str(row.get("asset_class") or "").strip()
    return _Line(inst, book, mv, md, acct)


def compute_action_attribution_bonds(
    *,
    period_start: date,
    period_end: date,
    positions_start: list[dict[str, Any]],
    positions_end: list[dict[str, Any]],
    pnl_by_key: Mapping[str, Decimal],
    duration_epsilon: Decimal = Decimal("0.15"),
    mv_ratio_epsilon: Decimal = Decimal("0.02"),
) -> dict[str, Any]:
    warnings: list[str] = []
    if not positions_end:
        warnings.append("NO_POSITIONS_END")
        return _empty(period_start, period_end, warnings)

    start_map: dict[str, _Line] = {}
    for row in positions_start:
        ln = _line_from_row(row)
        if ln and ln.market_value != 0:
            start_map[_key(ln.instrument_id, ln.book_id)] = ln

    end_map: dict[str, _Line] = {}
    for row in positions_end:
        ln = _line_from_row(row)
        if ln and ln.market_value != 0:
            end_map[_key(ln.instrument_id, ln.book_id)] = ln

    details: list[dict[str, Any]] = []
    action_id = 1

    # 新增
    for k, e in end_map.items():
        if k not in start_map:
            pnl = pnl_by_key.get(k, Decimal("0"))
            details.append(
                {
                    "action_id": str(action_id),
                    "action_type": "TIMING_BUY",
                    "action_date": period_end.isoformat(),
                    "bonds_involved": [e.instrument_id],
                    "description": f"新增持仓 {e.instrument_id} / {e.book_id}",
                    "pnl_economic": float(pnl),
                    "pnl_accounting": float(pnl),
                    "delta_duration": float(e.mod_dur),
                    "delta_dv01": 0.0,
                    "delta_spread_dv01": 0.0,
                }
            )
            action_id += 1

    # 卖出
    for k, s in start_map.items():
        if k not in end_map:
            pnl = pnl_by_key.get(k, Decimal("0"))
            inst, book = _parse_key(k)
            details.append(
                {
                    "action_id": str(action_id),
                    "action_type": "TIMING_SELL",
                    "action_date": period_end.isoformat(),
                    "bonds_involved": [inst],
                    "description": f"了结持仓 {inst} / {book}",
                    "pnl_economic": float(pnl),
                    "pnl_accounting": float(pnl),
                    "delta_duration": float(-s.mod_dur),
                    "delta_dv01": 0.0,
                    "delta_spread_dv01": 0.0,
                }
            )
            action_id += 1

    # 存续：久期、类别、市值显著变化
    for k, e in end_map.items():
        s = start_map.get(k)
        if s is None:
            continue
        mv_s, mv_e = s.market_value, e.market_value
        if mv_s <= 0:
            continue
        ratio_change = abs(mv_e - mv_s) / mv_s
        dur_delta = e.mod_dur - s.mod_dur
        cls_change = s.accounting_class != e.accounting_class and s.accounting_class and e.accounting_class

        if cls_change:
            pnl = pnl_by_key.get(k, Decimal("0"))
            details.append(
                {
                    "action_id": str(action_id),
                    "action_type": "SWITCH",
                    "action_date": period_end.isoformat(),
                    "bonds_involved": [e.instrument_id],
                    "description": f"{e.instrument_id} 会计分类变化（{s.accounting_class}→{e.accounting_class}）",
                    "pnl_economic": float(pnl),
                    "pnl_accounting": float(pnl),
                    "delta_duration": float(dur_delta),
                    "delta_dv01": 0.0,
                    "delta_spread_dv01": 0.0,
                }
            )
            action_id += 1
        elif abs(dur_delta) > duration_epsilon and ratio_change < mv_ratio_epsilon:
            pnl = pnl_by_key.get(k, Decimal("0"))
            at = "ADD_DURATION" if dur_delta > 0 else "REDUCE_DURATION"
            details.append(
                {
                    "action_id": str(action_id),
                    "action_type": at,
                    "action_date": period_end.isoformat(),
                    "bonds_involved": [e.instrument_id],
                    "description": f"{e.instrument_id} 修正久期变动 {float(dur_delta):+.2f} 年",
                    "pnl_economic": float(pnl),
                    "pnl_accounting": float(pnl),
                    "delta_duration": float(dur_delta),
                    "delta_dv01": 0.0,
                    "delta_spread_dv01": 0.0,
                }
            )
            action_id += 1
        elif ratio_change >= mv_ratio_epsilon:
            pnl = pnl_by_key.get(k, Decimal("0"))
            at = "TIMING_BUY" if mv_e > mv_s else "TIMING_SELL"
            details.append(
                {
                    "action_id": str(action_id),
                    "action_type": at,
                    "action_date": period_end.isoformat(),
                    "bonds_involved": [e.instrument_id],
                    "description": f"{e.instrument_id} 市值变动 {float(ratio_change * 100):.1f}%",
                    "pnl_economic": float(pnl),
                    "pnl_accounting": float(pnl),
                    "delta_duration": float(dur_delta),
                    "delta_dv01": 0.0,
                    "delta_spread_dv01": 0.0,
                }
            )
            action_id += 1

    keys_union = set(start_map) | set(end_map)
    total_period_pnl = sum((pnl_by_key.get(k, Decimal("0")) for k in keys_union), Decimal("0"))

    # 汇总按类型
    buckets: dict[str, dict[str, Any]] = {}
    for d in details:
        t = str(d["action_type"])
        pnl = Decimal(str(d["pnl_economic"]))
        if t not in buckets:
            buckets[t] = {"count": 0, "pnl": Decimal("0")}
        buckets[t]["count"] += 1
        buckets[t]["pnl"] += pnl

    by_type: list[dict[str, Any]] = []
    for at, agg in sorted(buckets.items()):
        cnt = agg["count"]
        p = agg["pnl"]
        by_type.append(
            {
                "action_type": at,
                "action_type_name": ACTION_TYPE_NAMES.get(at, at),
                "action_count": cnt,
                "total_pnl_economic": float(p),
                "total_pnl_accounting": float(p),
                "avg_pnl_per_action": float(p / Decimal(cnt)) if cnt else 0.0,
            }
        )

    # 组合久期（市值加权）
    def _wavg(lines: dict[str, _Line]) -> tuple[Decimal, Decimal]:
        mv_tot = sum((x.market_value for x in lines.values()), Decimal("0"))
        if mv_tot <= 0:
            return Decimal("0"), Decimal("0")
        d_tot = sum((x.mod_dur * x.market_value for x in lines.values()), Decimal("0"))
        return d_tot / mv_tot, mv_tot

    dur_s, mv_s_tot = _wavg(start_map)
    dur_e, mv_e_tot = _wavg(end_map)

    warnings.append("ACTION_ATTRIBUTION_HEURISTIC_NO_WIND")
    if not pnl_by_key:
        warnings.append("ACTION_ATTRIBUTION_NO_PNL_ALLOCATION")

    allocated = sum((Decimal(str(d["pnl_economic"])) for d in details), Decimal("0"))
    if keys_union and abs(total_period_pnl - allocated) > Decimal("0.01"):
        warnings.append("ACTION_ATTRIBUTION_PNL_NOT_FULLY_IN_DETAILS")

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_actions": len(details),
        "total_pnl_from_actions": float(total_period_pnl),
        "by_action_type": by_type,
        "action_details": details,
        "period_start_duration": float(dur_s),
        "period_end_duration": float(dur_e),
        "duration_change_from_actions": float(dur_e - dur_s),
        "period_start_dv01": 0.0,
        "period_end_dv01": 0.0,
        "warnings": warnings,
    }


def _empty(period_start: date, period_end: date, warnings: list[str]) -> dict[str, Any]:
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_actions": 0,
        "total_pnl_from_actions": 0.0,
        "by_action_type": [],
        "action_details": [],
        "period_start_duration": 0.0,
        "period_end_duration": 0.0,
        "duration_change_from_actions": 0.0,
        "period_start_dv01": 0.0,
        "period_end_dv01": 0.0,
        "warnings": warnings,
    }
