"""
债券持仓「动作」粗粒度归因（V1 action_attribution 的 DuckDB 可落地简化版）。

基于期初/期末快照对比 + 区间内 fact_pnl_daily 汇总，将事件分为：
买入、卖出、增持、减持；信用/利率类别变化记为 SWITCH；其余归入调整。

不含 Wind 个券深度规则；正式使用需结合数据完整性与 warnings。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from .safe_decimal import safe_decimal

ACTION_TYPE_NAMES: dict[str, str] = {
    "TIMING_BUY": "择时买入",
    "TIMING_SELL": "择时卖出",
    "ADD_DURATION": "加久期",
    "REDUCE_DURATION": "减久期",
    "SWITCH": "换券/结构调整",
    "ADJUST": "持仓调整",
    # 存续且久期/市值均无显著变化（未落入以上任一动作分桶）的持仓，
    # 仅在 by_action_type 中以汇总行披露，不生成 action_details 明细行。
    "UNALLOCATED": "存续未变动（未分配）",
}


def bond_analytics_action_line_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    portfolio_name = str(row.get("portfolio_name") or "").strip()
    cost_center = str(row.get("cost_center") or "").strip()
    return {
        "bond_code": str(row.get("instrument_code") or "").strip(),
        "book_id": f"{portfolio_name}::{cost_center}",
        "market_value": row.get("market_value"),
        "modified_duration": row.get("modified_duration"),
        "asset_class": str(row.get("asset_class_std") or row.get("accounting_class") or ""),
    }


def build_action_attribution_success_payload(
    *,
    report_date: date,
    period_type: str,
    raw: Mapping[str, Any],
    prior_snapshot_date: str | None,
    pnl_by_key: Mapping[str, Decimal],
    pnl_warning_codes: list[str],
    computed_at: str,
) -> dict[str, Any]:
    warn_parts: list[str | None] = [str(w) for w in (raw.get("warnings") or [])]
    if not prior_snapshot_date:
        warn_parts.append("ACTION_ATTRIBUTION_NO_PRIOR_SNAPSHOT")
    warn_parts.extend(pnl_warning_codes)
    warnings = _ordered_unique_warnings(warn_parts)

    missing_inputs: list[str] = []
    if not pnl_by_key:
        missing_inputs.append("fact_formal_pnl_fi_capital_gain_517")

    return {
        "report_date": report_date,
        "period_type": period_type,
        "period_start": date.fromisoformat(str(raw["period_start"])),
        "period_end": date.fromisoformat(str(raw["period_end"])),
        "total_actions": int(raw["total_actions"]),
        "total_pnl_from_actions": raw["total_pnl_from_actions"],
        "by_action_type": list(raw.get("by_action_type", [])),
        "action_details": list(raw.get("action_details", [])),
        "period_start_duration": raw["period_start_duration"],
        "period_end_duration": raw["period_end_duration"],
        "duration_change_from_actions": raw["duration_change_from_actions"],
        "period_start_dv01": raw["period_start_dv01"],
        "period_end_dv01": raw["period_end_dv01"],
        "status": "ready",
        "available_components": ["snapshot_diff", "capital_gain_517_allocation"],
        "missing_inputs": missing_inputs,
        "blocked_components": [],
        "computed_at": computed_at,
        "warnings": warnings,
        "warnings_detail": [
            {"code": warning, "level": "warning", "message": warning}
            for warning in warnings
        ],
    }


def build_action_attribution_placeholder_payload(
    *,
    report_date: date,
    summary: Mapping[str, Any],
    facets: Mapping[str, list[dict[str, Any]]],
    warnings: list[Mapping[str, str]],
    generated_at: str,
    default_status: str,
) -> dict[str, Any]:
    warning_messages = _ordered_unique_warnings([warning.get("message") for warning in warnings])
    warning_details: list[dict[str, str]] = []
    seen_details: set[tuple[str, str, str]] = set()
    for warning in warnings:
        detail = {
            "code": str(warning.get("code") or ""),
            "level": str(warning.get("level") or "warning"),
            "message": str(warning.get("message") or ""),
        }
        key = (detail["code"], detail["level"], detail["message"])
        if key in seen_details:
            continue
        seen_details.add(key)
        warning_details.append(detail)

    return {
        "report_date": report_date,
        "period_type": str(summary["period_type"]),
        "period_start": date.fromisoformat(str(summary["period_start"])),
        "period_end": date.fromisoformat(str(summary["period_end"])),
        "total_actions": int(summary["total_actions"]),
        "total_pnl_from_actions": summary["total_pnl_from_actions"],
        "by_action_type": list(facets.get("by_action_type", [])),
        "action_details": list(facets.get("action_details", [])),
        "period_start_duration": summary["period_start_duration"],
        "period_end_duration": summary["period_end_duration"],
        "duration_change_from_actions": summary["duration_change_from_actions"],
        "period_start_dv01": summary["period_start_dv01"],
        "period_end_dv01": summary["period_end_dv01"],
        "status": str(summary.get("status") or default_status),
        "available_components": [str(item) for item in list(summary.get("available_components") or [])],
        "missing_inputs": [str(item) for item in list(summary.get("missing_inputs") or [])],
        "blocked_components": [str(item) for item in list(summary.get("blocked_components") or [])],
        "computed_at": str(summary.get("computed_at") or generated_at),
        "warnings": warning_messages,
        "warnings_detail": warning_details,
    }


def select_action_attribution_pnl_report_dates(
    *,
    available_report_dates: list[str],
    period_type: str,
    period_start: date,
    period_end: date,
) -> tuple[list[str], list[str]]:
    codes: list[str] = []
    if period_type == "MoM":
        return [period_end.isoformat()], codes

    selected: list[str] = []
    for raw in available_report_dates:
        try:
            ds = date.fromisoformat(str(raw))
        except ValueError:
            continue
        if period_start <= ds <= period_end:
            selected.append(str(raw))

    selected = sorted(set(selected))
    if len(selected) > 1:
        codes.append("ACTION_ATTRIBUTION_PNL517_MULTI_MONTH_SUM")
    return selected, codes


def _ordered_unique_warnings(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


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
    """按期初/期末快照对比 + 区间 PnL 归因到粗粒度「动作」。

    占位说明：本函数尚无独立的会计口径（accrual/OCI 等）PnL 来源，
    因此每条 detail 与 by_action_type 汇总行的 ``pnl_accounting`` /
    ``total_pnl_accounting`` 目前直接复制自 ``pnl_economic``，并非真实的
    会计口径重算结果。前端会直接渲染该字段（见 ActionAttributionView），
    在接入真实会计口径来源前保留复制值以避免破坏契约，但消费方不应将其
    视为独立于经济口径的会计真值。

    闭合语义：``keys_union``（期初∪期末持仓键）覆盖的 PnL 应等于
    ``by_action_type`` 各行之和。存续且久期变动 ≤ ``duration_epsilon`` 且
    市值变动比例 < ``mv_ratio_epsilon`` 的持仓不生成 action_details 明细行，
    其 PnL 会汇总进 ``by_action_type`` 的 ``UNALLOCATED`` 行以保持闭合。
    """
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
    # 记录已生成 detail 行的持仓键，用于之后定位「存续无显著变化」的未分配残余。
    covered_keys: set[str] = set()
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
            covered_keys.add(k)
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
            covered_keys.add(k)
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
            covered_keys.add(k)
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
            covered_keys.add(k)
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
            covered_keys.add(k)
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

    # 未分配残余：存续且久期/市值均无显著变化（或其他未落入以上分桶）的持仓
    # 不生成 action_details 明细行，但其 PnL 仍计入 total_period_pnl；此处显式
    # 汇总一行披露，使 by_action_type 合计与 total_pnl_from_actions 闭合。
    allocated = sum((Decimal(str(d["pnl_economic"])) for d in details), Decimal("0"))
    unallocated_keys = keys_union - covered_keys
    unallocated_pnl = total_period_pnl - allocated
    reconciliation_epsilon = Decimal("0.01")
    if unallocated_keys and abs(unallocated_pnl) > reconciliation_epsilon:
        unallocated_count = len(unallocated_keys)
        by_type.append(
            {
                "action_type": "UNALLOCATED",
                "action_type_name": ACTION_TYPE_NAMES["UNALLOCATED"],
                "action_count": unallocated_count,
                "total_pnl_economic": float(unallocated_pnl),
                "total_pnl_accounting": float(unallocated_pnl),
                "avg_pnl_per_action": float(unallocated_pnl / Decimal(unallocated_count)),
            }
        )
        allocated += unallocated_pnl

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

    # `allocated` 现已包含上面追加的 UNALLOCATED 汇总行，因此正常情况下应与
    # total_period_pnl 精确闭合；此检查仅用于捕捉真正的异常缺口（例如未来
    # 引入新分桶但遗漏归集、或存在浮点误差之外的计算错误）。
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
