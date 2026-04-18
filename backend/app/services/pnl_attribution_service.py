"""PnL attribution workbench API — read-only DuckDB access; delegates finance to `core_finance.pnl_attribution`."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from backend.app.core_finance.pnl_attribution import workbench as pa_wb
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw
from backend.app.schemas.pnl_attribution import (
    AdvancedAttributionSummary,
    CampisiAttributionItem,
    CampisiAttributionPayload,
    CarryRollDownItem,
    CarryRollDownPayload,
    KRDAttributionBucket,
    KRDAttributionPayload,
    PnlAttributionAnalysisSummary,
    PnlCompositionItem,
    PnlCompositionPayload,
    PnlCompositionTrendItem,
    SpreadAttributionItem,
    SpreadAttributionPayload,
    TPLMarketCorrelationPayload,
    TPLMarketDataPoint,
    VolumeRateAttributionItem,
    VolumeRateAttributionPayload,
)
from backend.app.services.formal_result_runtime import build_formal_result_envelope, build_formal_result_meta

RULE_VERSION = "rv_pnl_attribution_workbench_v1"
CACHE_VERSION = "cv_pnl_attribution_workbench_v1"
SOURCE_VERSION = "sv_pnl_attribution_formal_fi_v1"
SOURCE_EMPTY = "sv_pnl_attribution_empty_v1"
WARN = pa_wb.DATA_FALLBACK_MSG

CompareType = Literal["mom", "yoy"]


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _meta_ok(result_kind: str):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
        source_surface="formal_attribution",
    )


def _meta_warn(result_kind: str):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        source_version=SOURCE_EMPTY,
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="warning",
        source_surface="formal_attribution",
    )


def _pnl_repo() -> PnlRepository:
    return PnlRepository(str(get_settings().duckdb_path))


def _bond_repo() -> BondAnalyticsRepository:
    return BondAnalyticsRepository(str(get_settings().duckdb_path))


def _curve_repo() -> YieldCurveRepository:
    return YieldCurveRepository(str(get_settings().duckdb_path))


def _prev_month_ym(ym: str) -> str:
    y, m = map(int, ym.split("-", 1))
    if m == 1:
        return f"{y - 1}-12"
    return f"{y}-{m - 1:02d}"


def _prev_year_same_month_ym(ym: str) -> str:
    y, m = map(int, ym.split("-", 1))
    return f"{y - 1}-{m:02d}"


def _max_date_in_month(dates: list[str], ym: str) -> str | None:
    hits = [d for d in dates if str(d).startswith(ym)]
    return max(hits) if hits else None


def _period_label_cn(ym: str) -> str:
    y, m = ym.split("-", 1)
    return f"{y}年{int(m)}月"


def _month_series_descending_from_dates(all_dates: list[str], months: int) -> list[str]:
    seen: list[str] = []
    for d in sorted(all_dates, reverse=True):
        ym = str(d)[:7]
        if ym not in seen:
            seen.append(ym)
        if len(seen) >= months:
            break
    return seen[:months]


def _prior_bond_date(report_date: str, dates: list[str]) -> str | None:
    if report_date not in dates:
        return None
    idx = dates.index(report_date)
    if idx + 1 >= len(dates):
        return None
    return dates[idx + 1]


def _treasury_10y(curve: dict[str, Decimal]) -> float | None:
    for k in ("10Y", "10y", "10"):
        if k in curve:
            return float(curve[k])
    return None


def _anchor_on_or_before(dates: list[str], day: str) -> str | None:
    eligible = [d for d in dates if d <= day]
    return max(eligible) if eligible else None


def _mv_tpl_scale(
    pnl_rows: list[dict[str, Any]],
    bond_rows: list[dict[str, Any]],
) -> float:
    mv_by = pa_wb.mv_index(bond_rows)
    s = 0.0
    for r in pnl_rows:
        if not pa_wb.is_tpl_accounting(str(r.get("accounting_basis") or "")):
            continue
        k = (str(r.get("instrument_code") or ""), str(r.get("portfolio_name") or ""))
        s += mv_by.get(k, 0.0)
    return s


def _with_optional_warnings(payload: dict[str, Any], *, warn: bool) -> dict[str, Any]:
    if warn:
        out = dict(payload)
        w = list(out.get("warnings") or [])
        w.append(WARN)
        out["warnings"] = w
        return out
    return payload


_NUMERIC_JSON_KEYS = frozenset({"raw", "unit", "display", "precision", "sign_aware"})

_LIST_FIELD_ITEM_CLASS: dict[tuple[type, str], type] = {
    (VolumeRateAttributionPayload, "items"): VolumeRateAttributionItem,
    (TPLMarketCorrelationPayload, "data_points"): TPLMarketDataPoint,
    (PnlCompositionPayload, "items"): PnlCompositionItem,
    (PnlCompositionPayload, "trend_data"): PnlCompositionTrendItem,
    (CarryRollDownPayload, "items"): CarryRollDownItem,
    (SpreadAttributionPayload, "items"): SpreadAttributionItem,
    (KRDAttributionPayload, "buckets"): KRDAttributionBucket,
    (CampisiAttributionPayload, "items"): CampisiAttributionItem,
}


def _numeric_dict(raw: float | None, unit: NumericUnit, sign_aware: bool) -> dict[str, Any]:
    return numeric_from_raw(raw=raw, unit=unit, sign_aware=sign_aware).model_dump(mode="json")


def _promote_flat(payload: dict[str, Any], NumericClass: type) -> dict[str, Any]:
    field_map: dict[str, tuple[NumericUnit, bool]] = getattr(NumericClass, "_NUMERIC_FIELDS", {}) or {}
    out = dict(payload)
    for name, (unit, sign_aware) in field_map.items():
        if name not in out:
            continue
        v = out[name]
        if v is None or isinstance(v, Numeric):
            continue
        if isinstance(v, dict) and _NUMERIC_JSON_KEYS <= set(v.keys()):
            continue
        if isinstance(v, (int, float)):
            out[name] = _numeric_dict(float(v), unit, sign_aware)
    return out


def _promote_payload_numerics(payload: dict[str, Any], PayloadClass: type) -> dict[str, Any]:
    out = _promote_flat(payload, PayloadClass)
    for (cls, field_name), item_cls in _LIST_FIELD_ITEM_CLASS.items():
        if cls is not PayloadClass:
            continue
        lst = out.get(field_name)
        if not isinstance(lst, list):
            continue
        out[field_name] = [
            _promote_flat(it, item_cls) if isinstance(it, dict) else it for it in lst
        ]
    return out


def _to_workbook_scalars(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip top-level Numeric JSON dicts to raw scalars for core_finance workbench."""
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, dict) and _NUMERIC_JSON_KEYS <= set(v.keys()):
            out[k] = v.get("raw")
        else:
            out[k] = v
    return out


def volume_rate_attribution_envelope(
    *,
    report_date: str | None,
    compare_type: CompareType = "mom",
) -> dict[str, object]:
    repo = _pnl_repo()
    dates = repo.list_formal_fi_report_dates()
    if not dates:
        payload = pa_wb.build_volume_rate_attribution(
            current_pnl=[],
            prior_pnl=None,
            current_bond=[],
            prior_bond=None,
            current_period="",
            previous_period="",
            compare_type=compare_type,
        )
        promoted = _promote_payload_numerics(payload, VolumeRateAttributionPayload)
        p = VolumeRateAttributionPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.volume_rate"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    rd = report_date or dates[0]
    ym = rd[:7]
    prev_ym = _prev_year_same_month_ym(ym) if compare_type == "yoy" else _prev_month_ym(ym)
    cur_snap = _max_date_in_month(dates, ym) or rd
    prev_snap = _max_date_in_month(dates, prev_ym)

    bond = _bond_repo()
    bdates = bond.list_report_dates()
    cur_bond = bond.fetch_bond_analytics_rows(report_date=cur_snap) if cur_snap in bdates else []
    prev_bond = (
        bond.fetch_bond_analytics_rows(report_date=prev_snap) if prev_snap and prev_snap in bdates else []
    )

    cur_pnl = repo.fetch_formal_fi_rows(cur_snap)
    prev_pnl = repo.fetch_formal_fi_rows(prev_snap) if prev_snap else []

    payload = pa_wb.build_volume_rate_attribution(
        current_pnl=cur_pnl,
        prior_pnl=prev_pnl if prev_snap else None,
        current_bond=cur_bond,
        prior_bond=prev_bond if prev_snap else None,
        current_period=ym,
        previous_period=prev_ym if prev_snap else "",
        compare_type=compare_type,
    )
    warn = not cur_pnl or (compare_type == "mom" and not prev_snap)
    promoted = _promote_payload_numerics(payload, VolumeRateAttributionPayload)
    p = VolumeRateAttributionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.volume_rate") if warn else _meta_ok("pnl_attribution.volume_rate"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )


def tpl_market_correlation_envelope(*, months: int = 12) -> dict[str, object]:
    repo = _pnl_repo()
    curve = _curve_repo()
    bond = _bond_repo()
    pnl_dates = repo.list_formal_fi_report_dates()
    if not pnl_dates:
        payload = pa_wb.build_tpl_market_correlation(
            monthly_points=[],
            start_period="",
            end_period="",
        )
        promoted = _promote_payload_numerics(payload, TPLMarketCorrelationPayload)
        p = TPLMarketCorrelationPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.tpl_market"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    series = _month_series_descending_from_dates(pnl_dates, months)
    series = list(reversed(series))
    bdates = set(bond.list_report_dates())
    points: list[dict[str, Any]] = []
    prev_tsy: float | None = None
    for ym in series:
        snap = _max_date_in_month(pnl_dates, ym)
        if not snap:
            continue
        rows = repo.fetch_formal_fi_rows(snap)
        tpl_fv = sum(
            float(r.get("fair_value_change_516") or 0)
            for r in rows
            if pa_wb.is_tpl_accounting(str(r.get("accounting_basis") or ""))
        )
        tpl_tot = sum(
            float(r.get("total_pnl") or 0)
            for r in rows
            if pa_wb.is_tpl_accounting(str(r.get("accounting_basis") or ""))
        )
        br = bond.fetch_bond_analytics_rows(report_date=snap) if snap in bdates else []
        tpl_scale = _mv_tpl_scale(rows, br)
        c = curve.fetch_curve(snap, "treasury")
        tsy = _treasury_10y(c) if c else None
        dtsy = ((tsy - prev_tsy) * 100.0) if tsy is not None and prev_tsy is not None else None
        prev_tsy = tsy if tsy is not None else prev_tsy
        points.append(
            {
                "period": ym,
                "period_label": _period_label_cn(ym),
                "tpl_fair_value_change": tpl_fv,
                "tpl_total_pnl": tpl_tot,
                "tpl_scale": tpl_scale,
                "treasury_10y": tsy,
                "treasury_10y_change": dtsy,
                "dr007": None,
            }
        )

    start_p = series[0] if series else ""
    end_p = series[-1] if series else ""
    payload = pa_wb.build_tpl_market_correlation(
        monthly_points=points,
        start_period=start_p,
        end_period=end_p,
    )
    warn = len(points) < 2
    promoted = _promote_payload_numerics(payload, TPLMarketCorrelationPayload)
    p = TPLMarketCorrelationPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.tpl_market") if warn else _meta_ok("pnl_attribution.tpl_market"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )


def pnl_composition_envelope(
    *,
    report_date: str | None,
    include_trend: bool = True,
    trend_months: int = 6,
) -> dict[str, object]:
    repo = _pnl_repo()
    dates = repo.list_formal_fi_report_dates()
    if not dates:
        payload = pa_wb.build_pnl_composition(
            report_period="",
            report_date="",
            pnl_rows=[],
            trend_rows=[],
        )
        promoted = _promote_payload_numerics(payload, PnlCompositionPayload)
        p = PnlCompositionPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.composition"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    rd = report_date or dates[0]
    ym = rd[:7]
    rows = repo.fetch_formal_fi_rows(rd)
    trend: list[dict[str, Any]] = []
    if include_trend:
        months = _month_series_descending_from_dates(dates, trend_months)
        months = list(reversed(months))
        for m in months:
            snap = _max_date_in_month(dates, m)
            if not snap:
                continue
            pr = repo.fetch_formal_fi_rows(snap)
            ti = sum(float(r.get("interest_income_514") or 0) for r in pr)
            tf = sum(float(r.get("fair_value_change_516") or 0) for r in pr)
            tc = sum(float(r.get("capital_gain_517") or 0) for r in pr)
            to = sum(float(r.get("manual_adjustment") or 0) for r in pr)
            tt = sum(float(r.get("total_pnl") or 0) for r in pr)
            trend.append(
                {
                    "period": m,
                    "period_label": _period_label_cn(m),
                    "interest_income": ti,
                    "fair_value_change": tf,
                    "capital_gain": tc,
                    "other_income": to,
                    "total_pnl": tt,
                }
            )

    payload = pa_wb.build_pnl_composition(
        report_period=ym,
        report_date=rd,
        pnl_rows=rows,
        trend_rows=trend,
    )
    warn = not rows
    promoted = _promote_payload_numerics(payload, PnlCompositionPayload)
    p = PnlCompositionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.composition") if warn else _meta_ok("pnl_attribution.composition"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )


def attribution_analysis_summary_envelope(*, report_date: str | None) -> dict[str, object]:
    """Uses volume-rate totals and TPL correlation for headline summary."""
    repo_dates = _pnl_repo().list_formal_fi_report_dates()
    rd = report_date or (repo_dates[0] if repo_dates else "")
    vol_env = volume_rate_attribution_envelope(report_date=rd or None, compare_type="mom")
    tpl_env = tpl_market_correlation_envelope(months=12)
    vol_raw = dict(vol_env.get("result") or {})
    tpl_raw = dict(tpl_env.get("result") or {})
    vol = _to_workbook_scalars(vol_raw)
    tpl = _to_workbook_scalars(tpl_raw)

    corr = tpl.get("correlation_coefficient")
    corr_f = float(corr) if corr is not None else None
    summary = pa_wb.build_pnl_attribution_analysis_summary(
        report_date=str(rd or ""),
        volume_effect=vol.get("total_volume_effect"),
        rate_effect=vol.get("total_rate_effect"),
        correlation_tpl_treasury=corr_f,
    )
    warn = bool(vol_raw.get("warnings")) or bool(tpl_raw.get("warnings"))
    promoted = _promote_payload_numerics(summary, PnlAttributionAnalysisSummary)
    p = PnlAttributionAnalysisSummary.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.summary") if warn else _meta_ok("pnl_attribution.summary"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )


def carry_roll_down_envelope(*, report_date: str | None) -> dict[str, object]:
    bond = _bond_repo()
    dates = bond.list_report_dates()
    ftp = float(get_settings().ftp_rate_pct)
    if not dates:
        payload = pa_wb.build_carry_roll_down(report_date="", bond_rows=[], ftp_rate_pct=ftp, curve_slope_bp=None)
        promoted = _promote_payload_numerics(payload, CarryRollDownPayload)
        p = CarryRollDownPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.carry_rolldown"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    rd = report_date or dates[0]
    rows = bond.fetch_bond_analytics_rows(report_date=rd) if rd in dates else []
    cur_repo = _curve_repo()
    c_end = cur_repo.fetch_curve(rd, "treasury")
    prior = _prior_bond_date(rd, dates)
    slope = None
    if prior:
        c_prior = cur_repo.fetch_curve(prior, "treasury")
        e = _treasury_10y(c_end) if c_end else None
        s = _treasury_10y(c_prior) if c_prior else None
        if e is not None and s is not None:
            slope = e - s
    payload = pa_wb.build_carry_roll_down(
        report_date=rd,
        bond_rows=rows,
        ftp_rate_pct=ftp,
        curve_slope_bp=slope,
    )
    warn = not rows
    promoted = _promote_payload_numerics(payload, CarryRollDownPayload)
    p = CarryRollDownPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.carry_rolldown") if warn else _meta_ok("pnl_attribution.carry_rolldown"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )


def spread_attribution_envelope(*, report_date: str | None, lookback_days: int = 30) -> dict[str, object]:
    bond = _bond_repo()
    curve = _curve_repo()
    dates = bond.list_report_dates()
    if not dates:
        payload = pa_wb.build_spread_attribution(
            report_date="",
            start_date="",
            end_date="",
            bond_rows_end=[],
            bond_rows_start=[],
            treasury_10y_start_pct=None,
            treasury_10y_end_pct=None,
        )
        promoted = _promote_payload_numerics(payload, SpreadAttributionPayload)
        p = SpreadAttributionPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.spread"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    rd = report_date or dates[0]
    end_d = date.fromisoformat(rd)
    start_d = end_d - timedelta(days=max(1, lookback_days))
    start_iso = start_d.isoformat()
    rows_e = bond.fetch_bond_analytics_rows(report_date=rd) if rd in dates else []
    anchor = _anchor_on_or_before(dates, start_iso)
    rows_s = bond.fetch_bond_analytics_rows(report_date=anchor) if anchor else []
    t_end = _treasury_10y(curve.fetch_curve(rd, "treasury"))
    t_start = _treasury_10y(curve.fetch_curve(anchor, "treasury")) if anchor else None
    payload = pa_wb.build_spread_attribution(
        report_date=rd,
        start_date=anchor or start_iso,
        end_date=rd,
        bond_rows_end=rows_e,
        bond_rows_start=rows_s,
        treasury_10y_start_pct=t_start,
        treasury_10y_end_pct=t_end,
    )
    warn = not rows_e or not rows_s
    promoted = _promote_payload_numerics(payload, SpreadAttributionPayload)
    p = SpreadAttributionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.spread") if warn else _meta_ok("pnl_attribution.spread"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )


def krd_attribution_envelope(*, report_date: str | None, lookback_days: int = 30) -> dict[str, object]:
    bond = _bond_repo()
    curve = _curve_repo()
    dates = bond.list_report_dates()
    if not dates:
        payload = pa_wb.build_krd_attribution(
            report_date="",
            start_date="",
            end_date="",
            bond_rows_end=[],
            bond_rows_start=[],
            treasury_shift_bp=None,
        )
        promoted = _promote_payload_numerics(payload, KRDAttributionPayload)
        p = KRDAttributionPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.krd"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    rd = report_date or dates[0]
    end_d = date.fromisoformat(rd)
    start_d = end_d - timedelta(days=max(1, lookback_days))
    anchor = _anchor_on_or_before(dates, start_d.isoformat())
    rows_e = bond.fetch_bond_analytics_rows(report_date=rd) if rd in dates else []
    rows_s = bond.fetch_bond_analytics_rows(report_date=anchor) if anchor else []
    t_end = _treasury_10y(curve.fetch_curve(rd, "treasury"))
    t_start = _treasury_10y(curve.fetch_curve(anchor, "treasury")) if anchor else None
    shift_bp = ((t_end - t_start) * 100.0) if t_end is not None and t_start is not None else None
    payload = pa_wb.build_krd_attribution(
        report_date=rd,
        start_date=anchor or start_d.isoformat(),
        end_date=rd,
        bond_rows_end=rows_e,
        bond_rows_start=rows_s,
        treasury_shift_bp=shift_bp,
    )
    warn = not rows_e or not rows_s
    promoted = _promote_payload_numerics(payload, KRDAttributionPayload)
    p = KRDAttributionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.krd") if warn else _meta_ok("pnl_attribution.krd"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )


def advanced_attribution_summary_envelope(*, report_date: str | None) -> dict[str, object]:
    c = carry_roll_down_envelope(report_date=report_date)
    s = spread_attribution_envelope(report_date=report_date, lookback_days=30)
    k = krd_attribution_envelope(report_date=report_date, lookback_days=30)
    payload = pa_wb.build_advanced_attribution_summary(
        report_date=str(report_date or ""),
        carry_payload=_to_workbook_scalars(dict(c.get("result") or {})),
        spread_payload=_to_workbook_scalars(dict(s.get("result") or {})),
        krd_payload=_to_workbook_scalars(dict(k.get("result") or {})),
    )
    rd = report_date or dict(c.get("result") or {}).get("report_date") or ""
    payload["report_date"] = str(rd or payload["report_date"])
    warn = any(bool(dict(x.get("result") or {}).get("warnings")) for x in (c, s, k))
    promoted = _promote_payload_numerics(payload, AdvancedAttributionSummary)
    p = AdvancedAttributionSummary.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.advanced_summary") if warn else _meta_ok("pnl_attribution.advanced_summary"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )


def campisi_attribution_envelope(
    *,
    start_date: str | None,
    end_date: str | None,
    lookback_days: int = 30,
) -> dict[str, object]:
    bond = _bond_repo()
    curve = _curve_repo()
    dates = bond.list_report_dates()
    if not dates:
        payload = pa_wb.build_campisi_attribution(
            report_date="",
            period_start="",
            period_end="",
            bond_rows=[],
            treasury_dy_decimal=None,
        )
        promoted = _promote_payload_numerics(payload, CampisiAttributionPayload)
        p = CampisiAttributionPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.campisi"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    rd_end = end_date or dates[0]
    if start_date:
        rd_start = start_date
    else:
        rd_start = (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat()
    anchor = _anchor_on_or_before(dates, rd_start)
    rows = bond.fetch_bond_analytics_rows(report_date=rd_end) if rd_end in dates else []
    t_end = _treasury_10y(curve.fetch_curve(rd_end, "treasury"))
    t_start = _treasury_10y(curve.fetch_curve(anchor, "treasury")) if anchor else None
    dy = ((t_end - t_start) / 100.0) if t_end is not None and t_start is not None else None
    payload = pa_wb.build_campisi_attribution(
        report_date=rd_end,
        period_start=anchor or rd_start,
        period_end=rd_end,
        bond_rows=rows,
        treasury_dy_decimal=dy,
    )
    warn = not rows
    promoted = _promote_payload_numerics(payload, CampisiAttributionPayload)
    p = CampisiAttributionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=_meta_warn("pnl_attribution.campisi") if warn else _meta_ok("pnl_attribution.campisi"),
        result_payload=_with_optional_warnings(p, warn=warn),
    )
