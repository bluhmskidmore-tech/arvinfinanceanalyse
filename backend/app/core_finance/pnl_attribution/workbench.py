"""PnL attribution workbench — pure functions over in-memory fact rows (float payloads for API).

Formal calculations live here; services only read DuckDB (read-only) and pass rows in.
Reuses `read_models` aggregators where applicable (iron rule: no duplicate bucket/KRD math).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from backend.app.core_finance.field_normalization import ACCOUNTING_BASIS_FVTPL

from backend.app.core_finance.bond_analytics.read_models import (
    build_asset_class_risk_summary,
    build_krd_distribution,
    summarize_portfolio_risk,
)

CompareType = Literal["mom", "yoy"]
DATA_FALLBACK_MSG = "数据尚未物化，当前展示空白结构。"


def _f(x: object | None) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _pearson_r(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    denx = sum((xi - mx) ** 2 for xi in xs)
    deny = sum((yi - my) ** 2 for yi in ys)
    if denx <= 0 or deny <= 0:
        return None
    return num / (denx**0.5 * deny**0.5)


def _period_label_cn(ym: str) -> str:
    y, m = ym.split("-", 1)
    return f"{y}年{int(m)}月"


def is_tpl_accounting(accounting_basis: str) -> bool:
    u = (accounting_basis or "").upper()
    raw = accounting_basis or ""
    return "TPL" in u or ACCOUNTING_BASIS_FVTPL in u or "交易性" in raw


def _category_type_for_invest(inv: str) -> str:
    if "负债" in inv:
        return "liability"
    return "asset"


def mv_index(bond_rows: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = defaultdict(float)
    for r in bond_rows:
        k = (str(r.get("instrument_code") or ""), str(r.get("portfolio_name") or ""))
        out[k] += _f(r.get("market_value"))
    return dict(out)


def _aggregate_scale_pnl_by_group(
    pnl_rows: list[dict[str, Any]],
    mv_by_key: dict[tuple[str, str], float],
    group_field: str = "invest_type_std",
) -> dict[str, dict[str, float]]:
    agg: dict[str, dict[str, float]] = defaultdict(lambda: {"pnl": 0.0, "scale": 0.0})
    for r in pnl_rows:
        g = str(r.get(group_field) or "未分类")
        k = (str(r.get("instrument_code") or ""), str(r.get("portfolio_name") or ""))
        mv = mv_by_key.get(k, 0.0)
        agg[g]["pnl"] += _f(r.get("total_pnl"))
        agg[g]["scale"] += mv
    return dict(agg)


def _treasury_10y_pct(curve: dict[str, Decimal]) -> float | None:
    for key in ("10Y", "10y", "10"):
        if key in curve:
            return float(curve[key])
    return None


def _tenor_bucket_mid_years(tenor: str) -> float:
    t = (tenor or "").strip().upper().replace(" ", "")
    fixed = {"1Y": 1.0, "2Y": 2.0, "3Y": 3.0, "5Y": 5.0, "7Y": 7.0, "10Y": 10.0, "20Y": 20.0, "30Y": 30.0}
    if t in fixed:
        return fixed[t]
    if "-" in t and t.endswith("Y"):
        body = t[:-1]
        parts = body.split("-")
        if len(parts) == 2:
            try:
                return (float(parts[0]) + float(parts[1])) / 2.0
            except ValueError:
                pass
    return 5.0


def _weighted_ytm_decimal(rows: list[dict[str, Any]]) -> float | None:
    num = sum(_f(r.get("market_value")) * _f(r.get("ytm")) for r in rows)
    den = sum(_f(r.get("market_value")) for r in rows)
    if den <= 0:
        return None
    return num / den


def _rows_for_bucket(all_rows: list[dict[str, Any]], tenor_bucket: str) -> list[dict[str, Any]]:
    return [r for r in all_rows if str(r.get("tenor_bucket") or "") == tenor_bucket]


def build_volume_rate_attribution(
    *,
    current_pnl: list[dict[str, Any]],
    prior_pnl: list[dict[str, Any]] | None,
    current_bond: list[dict[str, Any]],
    prior_bond: list[dict[str, Any]] | None,
    current_period: str,
    previous_period: str,
    compare_type: CompareType,
) -> dict[str, Any]:
    """Two-period volume / rate / interaction on scale×yield proxy (PnL FI + bond MV)."""
    mv_c = mv_index(current_bond)
    cur = _aggregate_scale_pnl_by_group(current_pnl, mv_c)
    has_prior = bool(prior_pnl and prior_bond)
    mv_p = mv_index(prior_bond) if has_prior else {}
    prev = _aggregate_scale_pnl_by_group(prior_pnl or [], mv_p) if has_prior else {}

    items: list[dict[str, Any]] = []
    categories = sorted(set(cur) | set(prev))
    total_cur_pnl = sum(v["pnl"] for v in cur.values())
    total_prev_pnl = sum(v["pnl"] for v in prev.values()) if has_prior else None
    total_pnl_change = (total_cur_pnl - total_prev_pnl) if has_prior and total_prev_pnl is not None else None

    total_vol = total_rate = total_ix = 0.0
    for cat in categories:
        c = cur.get(cat, {"pnl": 0.0, "scale": 0.0})
        p = prev.get(cat, {"pnl": 0.0, "scale": 0.0}) if has_prior else None
        Qc, Pc = c["scale"], c["pnl"]
        Qp = p["scale"] if p else None
        Pp = p["pnl"] if p else None
        yc = (Pc / Qc) if Qc > 0 else None
        yp = (Pp / Qp) if p and Qp is not None and Qp > 0 else None
        pnl_change = (Pc - Pp) if p and Pp is not None else None
        pnl_change_pct = ((pnl_change / Pp) * 100.0) if p and Pp not in (None, 0) and pnl_change is not None else None
        vol_eff = rate_eff = ix_eff = None
        if p is not None and Qp is not None and yp is not None and yc is not None:
            vol_eff = (Qc - Qp) * yp
            rate_eff = Qp * (yc - yp)
            ix_eff = (Qc - Qp) * (yc - yp)
        attrib_sum = None
        if vol_eff is not None and rate_eff is not None and ix_eff is not None:
            attrib_sum = vol_eff + rate_eff + ix_eff
        recon = (pnl_change - attrib_sum) if pnl_change is not None and attrib_sum is not None else None
        vol_pct = (
            (vol_eff / pnl_change * 100.0)
            if vol_eff is not None and pnl_change not in (None, 0)
            else None
        )
        rate_pct = (
            (rate_eff / pnl_change * 100.0)
            if rate_eff is not None and pnl_change not in (None, 0)
            else None
        )
        if vol_eff is not None:
            total_vol += vol_eff
        if rate_eff is not None:
            total_rate += rate_eff
        if ix_eff is not None:
            total_ix += ix_eff
        items.append(
            {
                "category": cat,
                "category_type": _category_type_for_invest(cat),
                "level": 0,
                "current_scale": Qc,
                "current_pnl": Pc,
                "current_yield_pct": (yc * 100.0) if yc is not None else None,
                "previous_scale": Qp,
                "previous_pnl": Pp,
                "previous_yield_pct": (yp * 100.0) if yp is not None else None,
                "pnl_change": pnl_change,
                "pnl_change_pct": pnl_change_pct,
                "volume_effect": vol_eff,
                "rate_effect": rate_eff,
                "interaction_effect": ix_eff,
                "attrib_sum": attrib_sum,
                "recon_error": recon,
                "volume_contribution_pct": vol_pct,
                "rate_contribution_pct": rate_pct,
            }
        )

    return {
        "current_period": current_period,
        "previous_period": previous_period,
        "compare_type": compare_type,
        "total_current_pnl": total_cur_pnl,
        "total_previous_pnl": total_prev_pnl,
        "total_pnl_change": total_pnl_change,
        "total_volume_effect": total_vol if has_prior else None,
        "total_rate_effect": total_rate if has_prior else None,
        "total_interaction_effect": total_ix if has_prior else None,
        "items": items,
        "has_previous_data": has_prior,
    }


def build_tpl_market_correlation(
    *,
    monthly_points: list[dict[str, Any]],
    start_period: str,
    end_period: str,
) -> dict[str, Any]:
    """monthly_points: period (YYYY-MM), tpl_fair_value_change, tpl_total_pnl, tpl_scale, treasury_10y, treasury_10y_change, dr007."""
    xs: list[float] = []
    ys: list[float] = []
    for p in monthly_points:
        dty = p.get("treasury_10y_change")
        dfv = p.get("tpl_fair_value_change")
        if dty is None or dfv is None:
            continue
        xs.append(float(dty))
        ys.append(float(dfv))
    r = _pearson_r(xs, ys)
    interpretation = (
        "样本不足或缺曲线点位，无法估计相关系数。"
        if r is None
        else (
            "TPL 公允价值月度变动与 10Y 国债收益率变动呈负相关，方向与久期逻辑一致。"
            if r < -0.3
            else (
                "TPL 公允价值月度变动与 10Y 国债收益率变动呈正相关。"
                if r > 0.3
                else "TPL 与国债收益率变动的线性相关性较弱。"
            )
        )
    )
    total_tpl = sum(float(p.get("tpl_fair_value_change") or 0) for p in monthly_points)
    t_changes = [float(p["treasury_10y_change"]) for p in monthly_points if p.get("treasury_10y_change") is not None]
    t_levels = [float(p["treasury_10y"]) for p in monthly_points if p.get("treasury_10y") is not None]
    avg_dt = sum(t_changes) / len(t_changes) if t_changes else None
    t0 = t_levels[0] if t_levels else None
    t1 = t_levels[-1] if t_levels else None
    ttot = ((t1 - t0) * 100.0) if t0 is not None and t1 is not None else None
    summary = (
        "样本期内数据不足，无法生成解读。"
        if not monthly_points
        else "样本期内利率与 TPL 估值变动的对照关系见相关系数与散点结构。"
    )
    return {
        "start_period": start_period,
        "end_period": end_period,
        "num_periods": len(monthly_points),
        "correlation_coefficient": r,
        "correlation_interpretation": interpretation,
        "total_tpl_fv_change": total_tpl,
        "avg_treasury_10y_change": avg_dt,
        "treasury_10y_total_change_bp": ttot,
        "data_points": monthly_points,
        "analysis_summary": summary,
    }


def build_pnl_composition(
    *,
    report_period: str,
    report_date: str,
    pnl_rows: list[dict[str, Any]],
    trend_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """trend_rows: list of {period, period_label, interest_income, fair_value_change, capital_gain, total_pnl}."""
    items: list[dict[str, Any]] = []
    by_cat: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "interest": 0.0,
            "fv": 0.0,
            "cg": 0.0,
            "oth": 0.0,
            "total": 0.0,
        }
    )
    for r in pnl_rows:
        cat = str(r.get("invest_type_std") or "未分类")
        by_cat[cat]["interest"] += _f(r.get("interest_income_514"))
        by_cat[cat]["fv"] += _f(r.get("fair_value_change_516"))
        by_cat[cat]["cg"] += _f(r.get("capital_gain_517"))
        by_cat[cat]["oth"] += _f(r.get("manual_adjustment"))
        by_cat[cat]["total"] += _f(r.get("total_pnl"))

    tot_i = sum(v["interest"] for v in by_cat.values())
    tot_f = sum(v["fv"] for v in by_cat.values())
    tot_c = sum(v["cg"] for v in by_cat.values())
    tot_o = sum(v["oth"] for v in by_cat.values())
    tot_p = sum(v["total"] for v in by_cat.values())

    def _pct(part: float, whole: float) -> float:
        return (part / whole * 100.0) if whole else 0.0

    for cat, v in sorted(by_cat.items()):
        t = v["total"]
        items.append(
            {
                "category": cat,
                "category_type": _category_type_for_invest(cat),
                "level": 0,
                "total_pnl": t,
                "interest_income": v["interest"],
                "fair_value_change": v["fv"],
                "capital_gain": v["cg"],
                "other_income": v["oth"],
                "interest_pct": _pct(v["interest"], t),
                "fair_value_pct": _pct(v["fv"], t),
                "capital_gain_pct": _pct(v["cg"], t),
                "other_pct": _pct(v["oth"], t),
            }
        )

    return {
        "report_period": report_period,
        "report_date": report_date,
        "total_pnl": tot_p,
        "total_interest_income": tot_i,
        "total_fair_value_change": tot_f,
        "total_capital_gain": tot_c,
        "total_other_income": tot_o,
        "interest_pct": _pct(tot_i, tot_p),
        "fair_value_pct": _pct(tot_f, tot_p),
        "capital_gain_pct": _pct(tot_c, tot_p),
        "other_pct": _pct(tot_o, tot_p),
        "items": items,
        "trend_data": trend_rows,
    }


def build_pnl_attribution_analysis_summary(
    *,
    report_date: str,
    volume_effect: float | None,
    rate_effect: float | None,
    correlation_tpl_treasury: float | None,
) -> dict[str, Any]:
    vol = abs(volume_effect or 0.0)
    rate = abs(rate_effect or 0.0)
    if vol == 0 and rate == 0:
        primary: Literal["volume", "rate", "market", "unknown"] = "unknown"
        pct = 0.0
    elif vol >= rate:
        primary = "volume"
        pct = (vol / (vol + rate) * 100.0) if (vol + rate) > 0 else 0.0
    else:
        primary = "rate"
        pct = (rate / (vol + rate) * 100.0) if (vol + rate) > 0 else 0.0

    aligned = correlation_tpl_treasury is not None and correlation_tpl_treasury < -0.4
    note = (
        "相关系数为负且绝对值较大时，TPL 与利率走势更一致。"
        if correlation_tpl_treasury is not None
        else "缺少 TPL–利率样本，暂不评价对齐程度。"
    )
    findings = [
        "本期损益变动的规模与利率分解见规模/利率页签。",
    ]
    if primary != "unknown":
        findings.append(f"主驱动归类为 {primary}（约 {pct:.0f}% 相对占比）。")
    if correlation_tpl_treasury is not None:
        findings.append(f"TPL 与 10Y 国债月度变动的样本相关系数约为 {correlation_tpl_treasury:.2f}。")

    return {
        "report_date": report_date,
        "primary_driver": primary,
        "primary_driver_pct": round(pct, 1),
        "key_findings": findings,
        "tpl_market_aligned": aligned,
        "tpl_market_note": note,
    }


def build_carry_roll_down(
    *,
    report_date: str,
    bond_rows: list[dict[str, Any]],
    ftp_rate_pct: float,
    curve_slope_bp: float | None,
) -> dict[str, Any]:
    """Grouped by asset_class_std; uses read-model-style weights from rows."""
    if not bond_rows:
        return {
            "report_date": report_date,
            "total_market_value": 0.0,
            "portfolio_carry": 0.0,
            "portfolio_rolldown": 0.0,
            "portfolio_static_return": 0.0,
            "total_carry_pnl": 0.0,
            "total_rolldown_pnl": 0.0,
            "total_static_pnl": 0.0,
            "ftp_rate": ftp_rate_pct,
            "items": [],
        }

    by_ac: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in bond_rows:
        by_ac[str(r.get("asset_class_std") or "未分类")].append(r)

    total_mv = sum(_f(r.get("market_value")) for r in bond_rows)
    items: list[dict[str, Any]] = []
    port_carry = port_roll = port_static = 0.0
    t_carry_pnl = t_roll_pnl = t_static_pnl = 0.0
    slope = curve_slope_bp if curve_slope_bp is not None else 0.0

    for ac, rows in sorted(by_ac.items()):
        mv = sum(_f(r.get("market_value")) for r in rows)
        w = (mv / total_mv * 100.0) if total_mv > 0 else 0.0
        num_c = sum(_f(r.get("market_value")) * _f(r.get("coupon_rate")) for r in rows)
        den = mv
        coupon_dec = (num_c / den) if den > 0 else 0.0
        coupon_pct = coupon_dec * 100.0
        ytm_dec = _weighted_ytm_decimal(rows)
        ytm_pct = ytm_dec * 100.0 if ytm_dec is not None else None
        num_d = sum(_f(r.get("market_value")) * _f(r.get("modified_duration")) for r in rows)
        dur = (num_d / den) if den > 0 else 0.0
        funding = ftp_rate_pct
        carry_pct = coupon_pct - funding
        carry_dec = carry_pct / 100.0
        carry_pnl = mv * carry_dec / 12.0
        rolldown_pct = (slope / 100.0) * dur
        rolldown_pnl = mv * (rolldown_pct / 100.0) / 12.0
        static_pct = carry_pct + rolldown_pct
        static_pnl = carry_pnl + rolldown_pnl
        weight_port = (mv / total_mv) if total_mv > 0 else 0.0
        port_carry += carry_pct * weight_port
        port_roll += rolldown_pct * weight_port
        port_static += static_pct * weight_port
        t_carry_pnl += carry_pnl
        t_roll_pnl += rolldown_pnl
        t_static_pnl += static_pnl
        items.append(
            {
                "category": ac,
                "category_type": "asset",
                "market_value": mv,
                "weight": round(w, 4),
                "coupon_rate": round(coupon_pct, 4),
                "ytm": round(ytm_pct, 4) if ytm_pct is not None else None,
                "funding_cost": funding,
                "carry": round(carry_pct, 4),
                "carry_pnl": round(carry_pnl, 4),
                "duration": round(dur, 4),
                "curve_slope": round(slope, 4) if curve_slope_bp is not None else None,
                "rolldown": round(rolldown_pct, 4),
                "rolldown_pnl": round(rolldown_pnl, 4),
                "static_return": round(static_pct, 4),
                "static_pnl": round(static_pnl, 4),
            }
        )

    return {
        "report_date": report_date,
        "total_market_value": total_mv,
        "portfolio_carry": round(port_carry, 4),
        "portfolio_rolldown": round(port_roll, 4),
        "portfolio_static_return": round(port_static, 4),
        "total_carry_pnl": round(t_carry_pnl, 4),
        "total_rolldown_pnl": round(t_roll_pnl, 4),
        "total_static_pnl": round(t_static_pnl, 4),
        "ftp_rate": ftp_rate_pct,
        "items": items,
    }


def build_spread_attribution(
    *,
    report_date: str,
    start_date: str,
    end_date: str,
    bond_rows_end: list[dict[str, Any]],
    bond_rows_start: list[dict[str, Any]],
    treasury_10y_start_pct: float | None,
    treasury_10y_end_pct: float | None,
) -> dict[str, Any]:
    risk_end = summarize_portfolio_risk(bond_rows_end)
    total_mv = float(risk_end["total_market_value"])
    port_dur = float(risk_end["portfolio_modified_duration"])

    dt_pct = (
        (treasury_10y_end_pct - treasury_10y_start_pct)
        if treasury_10y_start_pct is not None and treasury_10y_end_pct is not None
        else None
    )
    dt_dec = (dt_pct / 100.0) if dt_pct is not None else None
    d_bp = (dt_pct * 100.0) if dt_pct is not None else None

    y_end = _weighted_ytm_decimal(bond_rows_end)
    y_start = _weighted_ytm_decimal(bond_rows_start)
    dy_bond_dec = (y_end - y_start) if y_end is not None and y_start is not None else None
    spread_chg_dec = (
        (dy_bond_dec - dt_dec) if dy_bond_dec is not None and dt_dec is not None else None
    )

    items: list[dict[str, Any]] = []
    t_eff_tot = s_eff_tot = 0.0
    by_ac: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in bond_rows_end:
        by_ac[str(r.get("asset_class_std") or "未分类")].append(r)

    by_ac_s: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in bond_rows_start:
        by_ac_s[str(r.get("asset_class_std") or "未分类")].append(r)

    for ac, rows_e in sorted(by_ac.items()):
        mv = sum(_f(r.get("market_value")) for r in rows_e)
        w = (mv / total_mv * 100.0) if total_mv > 0 else 0.0
        num_d = sum(_f(r.get("market_value")) * _f(r.get("modified_duration")) for r in rows_e)
        dur = (num_d / mv) if mv > 0 else 0.0
        ye = _weighted_ytm_decimal(rows_e)
        ys = _weighted_ytm_decimal(by_ac_s.get(ac, []))
        ychg = ((ye - ys) * 10000.0) if ye is not None and ys is not None else None
        tchg_bp = (dt_pct * 100.0) if dt_pct is not None else None
        schg_bp = (
            (ychg - tchg_bp) if ychg is not None and tchg_bp is not None else None
        )
        t_dec = dt_dec if dt_dec is not None else 0.0
        s_dec = (spread_chg_dec if spread_chg_dec is not None else 0.0) if dy_bond_dec is not None else 0.0
        if ychg is not None and tchg_bp is not None:
            s_dec_row = (ychg - tchg_bp) / 10000.0
        else:
            s_dec_row = s_dec
        tre_eff = -mv * dur * t_dec if dt_dec is not None else 0.0
        spr_eff = -mv * dur * s_dec_row
        price = tre_eff + spr_eff
        t_pct = (abs(tre_eff) / abs(price) * 100.0) if price else 0.0
        s_pct = (abs(spr_eff) / abs(price) * 100.0) if price else 0.0
        t_eff_tot += tre_eff
        s_eff_tot += spr_eff
        items.append(
            {
                "category": ac,
                "category_type": "asset",
                "market_value": mv,
                "duration": round(dur, 4),
                "weight": round(w, 4),
                "yield_change": ychg,
                "treasury_change": tchg_bp,
                "spread_change": schg_bp,
                "treasury_effect": round(tre_eff, 4),
                "spread_effect": round(spr_eff, 4),
                "total_price_effect": round(price, 4),
                "treasury_contribution_pct": round(t_pct, 4),
                "spread_contribution_pct": round(s_pct, 4),
            }
        )

    total_price = t_eff_tot + s_eff_tot
    driver = (
        "treasury"
        if abs(t_eff_tot) >= abs(s_eff_tot)
        else "spread"
    )
    interp = (
        "国债收益率变动主导估值效应。"
        if driver == "treasury"
        else "利差变动对估值效应贡献更大。"
    )
    return {
        "report_date": report_date,
        "start_date": start_date,
        "end_date": end_date,
        "treasury_10y_start": treasury_10y_start_pct,
        "treasury_10y_end": treasury_10y_end_pct,
        "treasury_10y_change": d_bp,
        "total_market_value": total_mv,
        "portfolio_duration": round(port_dur, 4),
        "total_treasury_effect": round(t_eff_tot, 4),
        "total_spread_effect": round(s_eff_tot, 4),
        "total_price_change": round(total_price, 4),
        "primary_driver": driver,
        "interpretation": interp,
        "items": items,
    }


def build_krd_attribution(
    *,
    report_date: str,
    start_date: str,
    end_date: str,
    bond_rows_end: list[dict[str, Any]],
    bond_rows_start: list[dict[str, Any]],
    treasury_shift_bp: float | None,
) -> dict[str, Any]:
    risk = summarize_portfolio_risk(bond_rows_end)
    total_mv = float(risk["total_market_value"])
    port_dur = float(risk["portfolio_modified_duration"])
    port_dv01 = float(risk["portfolio_dv01"])
    dist_end = build_krd_distribution(bond_rows_end)
    by_bucket_start: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in bond_rows_start:
        by_bucket_start[str(r.get("tenor_bucket") or "")].append(r)

    buckets_out: list[dict[str, Any]] = []
    total_dur_eff = 0.0
    shift_bp = treasury_shift_bp if treasury_shift_bp is not None else 0.0
    for b in dist_end:
        tenor = str(b["tenor_bucket"])
        mv = float(b["market_value"])
        w = (mv / total_mv * 100.0) if total_mv > 0 else 0.0
        krd = float(b["krd"])
        rows_s = by_bucket_start.get(tenor, [])
        ye = _weighted_ytm_decimal(_rows_for_bucket(bond_rows_end, tenor))
        ys = _weighted_ytm_decimal(rows_s)
        ychg = ((ye - ys) * 10000.0) if ye is not None and ys is not None else None
        contrib = -mv * krd * (shift_bp / 10000.0)
        total_dur_eff += contrib
        bond_count = len(_rows_for_bucket(bond_rows_end, tenor))
        buckets_out.append(
            {
                "tenor": tenor,
                "tenor_years": _tenor_bucket_mid_years(tenor),
                "market_value": mv,
                "weight": round(w, 4),
                "bond_count": bond_count,
                "bucket_duration": krd,
                "krd": round(krd, 4),
                "yield_change": ychg,
                "duration_contribution": round(contrib, 4),
                "contribution_pct": 0.0,
            }
        )
    for b in buckets_out:
        b["contribution_pct"] = (
            round(abs(b["duration_contribution"]) / abs(total_dur_eff) * 100.0, 4)
            if total_dur_eff
            else 0.0
        )
    max_tenor = ""
    max_val = 0.0
    for b in buckets_out:
        if abs(b["duration_contribution"]) >= abs(max_val):
            max_val = b["duration_contribution"]
            max_tenor = str(b["tenor"])
    curve_type = "parallel"
    if shift_bp is not None and shift_bp < -5:
        curve_type = "bull_steepener" if port_dur > 4 else "bull_flattener"
    interp = "组合 KRD 桶贡献基于关键久期近似与国债平移假设。"
    return {
        "report_date": report_date,
        "start_date": start_date,
        "end_date": end_date,
        "total_market_value": total_mv,
        "portfolio_duration": round(port_dur, 4),
        "portfolio_dv01": round(port_dv01, 4),
        "total_duration_effect": round(total_dur_eff, 4),
        "curve_shift_type": curve_type,
        "curve_interpretation": interp,
        "buckets": buckets_out,
        "max_contribution_tenor": max_tenor,
        "max_contribution_value": round(float(max_val), 4),
    }


def build_advanced_attribution_summary(
    *,
    report_date: str,
    carry_payload: dict[str, Any],
    spread_payload: dict[str, Any],
    krd_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "report_date": report_date,
        "portfolio_carry": float(carry_payload.get("portfolio_carry") or 0.0),
        "portfolio_rolldown": float(carry_payload.get("portfolio_rolldown") or 0.0),
        "static_return_annualized": float(carry_payload.get("portfolio_static_return") or 0.0),
        "treasury_effect_total": float(spread_payload.get("total_treasury_effect") or 0.0),
        "spread_effect_total": float(spread_payload.get("total_spread_effect") or 0.0),
        "spread_driver": str(spread_payload.get("primary_driver") or "unknown"),
        "max_krd_tenor": str(krd_payload.get("max_contribution_tenor") or ""),
        "curve_shape_change": str(krd_payload.get("curve_shift_type") or ""),
        "key_insights": [
            "Carry / 骑乘与利差分解见高级归因各子图。",
            f"利差主导项归类为 {spread_payload.get('primary_driver') or 'unknown'}。",
        ],
    }


def build_campisi_attribution(
    *,
    report_date: str,
    period_start: str,
    period_end: str,
    bond_rows: list[dict[str, Any]],
    treasury_dy_decimal: float | None,
) -> dict[str, Any]:
    """Campisi-style split using `build_asset_class_risk_summary` buckets; selection as residual."""
    if not bond_rows:
        num_days_empty = 0
        if period_start and period_end:
            num_days_empty = max(
                0,
                (date.fromisoformat(period_end) - date.fromisoformat(period_start)).days + 1,
            )
        return {
            "report_date": report_date,
            "period_start": period_start,
            "period_end": period_end,
            "num_days": num_days_empty,
            "total_market_value": 0.0,
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "total_income": 0.0,
            "total_treasury_effect": 0.0,
            "total_spread_effect": 0.0,
            "total_selection_effect": 0.0,
            "income_contribution_pct": 0.0,
            "treasury_contribution_pct": 0.0,
            "spread_contribution_pct": 0.0,
            "selection_contribution_pct": 0.0,
            "primary_driver": "unknown",
            "interpretation": "缺债券持仓事实，Campisi 分解为空。",
            "items": [],
        }

    days = max(1, (date.fromisoformat(period_end) - date.fromisoformat(period_start)).days + 1)
    dy = treasury_dy_decimal if treasury_dy_decimal is not None else 0.0
    summaries = build_asset_class_risk_summary(bond_rows)
    total_mv = sum(float(s["market_value"]) for s in summaries)
    items: list[dict[str, Any]] = []
    tot_inc = tot_t = tot_s = tot_sel = 0.0
    for s in summaries:
        ac = str(s["asset_class"])
        mv = float(s["market_value"])
        d = float(s["duration"])
        w = float(s["weight"]) * 100.0 if s.get("weight") is not None else (mv / total_mv * 100.0 if total_mv else 0.0)
        rows = [r for r in bond_rows if str(r.get("asset_class_std") or "") == ac]
        coupon_dec = (
            sum(_f(r.get("market_value")) * _f(r.get("coupon_rate")) for r in rows) / mv if mv > 0 else 0.0
        )
        income = mv * coupon_dec * (days / 365.0)
        tre = -mv * d * dy
        spread = 0.0  # STUB: requires credit curve data, not yet implemented
        total_ret = income + tre + spread
        sel = 0.0  # STUB: depends on spread, not yet implemented
        tot_inc += income
        tot_t += tre
        tot_s += spread
        tot_sel += sel
        items.append(
            {
                "category": ac,
                "market_value": mv,
                "weight": round(w, 4),
                "total_return": round(total_ret, 4),
                "total_return_pct": round((total_ret / mv * 100.0) if mv else 0.0, 4),
                "income_return": round(income, 4),
                "income_return_pct": round((income / total_ret * 100.0) if total_ret else 0.0, 4),
                "treasury_effect": round(tre, 4),
                "treasury_effect_pct": round((tre / total_ret * 100.0) if total_ret else 0.0, 4),
                "spread_effect": round(spread, 4),
                "spread_effect_pct": round((spread / total_ret * 100.0) if total_ret else 0.0, 4),
                "selection_effect": round(sel, 4),
                "selection_effect_pct": 0.0,
            }
        )

    total_return = tot_inc + tot_t + tot_s + tot_sel

    def _share(part: float) -> float:
        return (part / total_return * 100.0) if total_return else 0.0

    parts = [("income", tot_inc), ("treasury", tot_t), ("spread", tot_s), ("selection", tot_sel)]
    primary = max(parts, key=lambda x: abs(x[1]))[0]

    return {
        "report_date": report_date,
        "period_start": period_start,
        "period_end": period_end,
        "num_days": days,
        "total_market_value": total_mv,
        "total_return": round(total_return, 4),
        "total_return_pct": round((total_return / total_mv * 100.0) if total_mv else 0.0, 4),
        "total_income": round(tot_inc, 4),
        "total_treasury_effect": round(tot_t, 4),
        "total_spread_effect": round(tot_s, 4),
        "total_selection_effect": round(tot_sel, 4),
        "income_contribution_pct": round(_share(tot_inc), 4),
        "treasury_contribution_pct": round(_share(tot_t), 4),
        "spread_contribution_pct": round(_share(tot_s), 4),
        "selection_contribution_pct": round(_share(tot_sel), 4),
        "primary_driver": primary,
        "interpretation": "Campisi 四效应为收入、国债平移、利差与选择（此处利差/选择按简化残差框架可扩展）。",
        "items": items,
    }
