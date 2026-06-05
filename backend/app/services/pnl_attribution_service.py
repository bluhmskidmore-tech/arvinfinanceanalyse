"""PnL attribution workbench API — read-only DuckDB access; delegates finance to `core_finance.pnl_attribution`."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

import duckdb

from backend.app.core_finance.pnl_attribution import workbench as pa_wb
from backend.app.core_finance.campisi import (
    campisi_attribution as _core_campisi,
    classify_primary_driver,
)
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
from backend.app.services.campisi_attribution_service import (
    FORMAL_REPORT_BASIS,
    _formal_bridge_has_position_overlap,
    _formal_bridge_to_campisi_result,
    _try_fetch_formal_bridge,
    curve_to_market_dict,
    fetch_credit_spread_market,
    merge_positions,
)
from backend.app.services.formal_result_runtime import build_formal_result_envelope, build_formal_result_meta
from backend.app.services import pnl_service

RULE_VERSION = "rv_pnl_attribution_workbench_v1"
CACHE_VERSION = "cv_pnl_attribution_workbench_v1"
SOURCE_VERSION = "sv_pnl_attribution_formal_fi_v1"
SOURCE_VERSION_BUSINESS_BALANCE = "sv_pnl_attribution_business_balance_v1"
SOURCE_VERSION_MARKET = "sv_pnl_attribution_formal_market_v1"
SOURCE_EMPTY = "sv_pnl_attribution_empty_v1"
WARN = pa_wb.DATA_FALLBACK_MSG
QUALITY_WARN = "正式 FI / 债券分析口径存在数据质量预警；该结果非空，请查看来源元信息和明细 warnings。"
TPL_MARKET_DATA_WARN = "TPL 市场相关性存在 10Y / DR007 市场数据缺口；缺失月份显示为空，不补 0。"

TABLES_BUSINESS_BALANCE = [
    "fact_formal_pnl_fi",
    "fact_nonstd_pnl_bridge",
    "fact_formal_zqtz_balance_daily",
]
TABLES_FORMAL_MARKET = [
    "fact_formal_pnl_fi",
    "fact_formal_bond_analytics_daily",
    "yield_curve_daily",
    "fact_choice_macro_daily",
    "choice_market_snapshot",
]
TABLES_BOND_ANALYTICS = [
    "fact_formal_bond_analytics_daily",
    "yield_curve_daily",
]
RAW_INVEST_TYPE_CODES = {"A", "H", "T"}

CompareType = Literal["mom", "yoy"]


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _meta_ok(
    result_kind: str,
    *,
    source_version: str = SOURCE_VERSION,
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    as_of_date: str | None = None,
):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        as_of_date=as_of_date,
        source_surface="formal_attribution",
    )


def _meta_warn(
    result_kind: str,
    *,
    source_version: str = SOURCE_EMPTY,
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    as_of_date: str | None = None,
):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        source_version=source_version,
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="warning",
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        as_of_date=as_of_date,
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


def _latest_formal_report_date() -> str | None:
    dates = _pnl_repo().list_formal_fi_report_dates()
    return dates[0] if dates else None


def _month_series_descending_until(all_dates: list[str], months: int, end_date: str) -> list[str]:
    return _month_series_descending_from_dates([d for d in all_dates if str(d) <= end_date], months)


def _business_rows_as_pnl_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        category = row.get("business_type_primary") or row.get("business_type") or row.get("invest_type_std")
        category_text = str(category or "Unclassified")
        if category_text in RAW_INVEST_TYPE_CODES and int(row.get("balance_row_count") or 0) == 0:
            category_text = f"未匹配余额-{category_text}"
        out.append({**row, "invest_type_std": category_text})
    return out


def _business_evidence_rows(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        total += int(row.get("pnl_row_count") or 0)
        total += int(row.get("balance_row_count") or 0)
    return total


def _pnl_by_business_snapshot(report_date: str) -> dict[str, Any]:
    settings = get_settings()
    envelope = pnl_service.pnl_by_business_envelope(
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
        report_date=report_date,
    )
    result = dict(envelope.get("result") or {})
    meta = dict(envelope.get("result_meta") or {})
    rows = result.get("rows")
    if not isinstance(rows, list):
        rows = []
    source_tables = result.get("source_tables") or meta.get("tables_used") or TABLES_BUSINESS_BALANCE
    if not isinstance(source_tables, list):
        source_tables = TABLES_BUSINESS_BALANCE
    evidence_rows = meta.get("evidence_rows")
    if not isinstance(evidence_rows, int):
        evidence_rows = _business_evidence_rows(rows)
    return {
        "rows": rows,
        "result": result,
        "meta": meta,
        "source_version": str(meta.get("source_version") or SOURCE_VERSION_BUSINESS_BALANCE),
        "tables_used": [str(table) for table in source_tables],
        "evidence_rows": evidence_rows,
        "quality_flag": str(meta.get("quality_flag") or "ok"),
    }


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


def _treasury_10y_on_or_before(
    curve_repo: YieldCurveRepository,
    trade_date: str,
) -> tuple[float | None, str | None]:
    exact = curve_repo.fetch_curve(trade_date, "treasury")
    exact_value = _treasury_10y(exact) if exact else None
    if exact_value is not None:
        return exact_value, trade_date

    fetch_latest = getattr(curve_repo, "fetch_latest_trade_date_on_or_before", None)
    if fetch_latest is None:
        return None, None
    resolved_date = fetch_latest("treasury", trade_date)
    if resolved_date is None or resolved_date == trade_date:
        return None, None
    fallback = curve_repo.fetch_curve(resolved_date, "treasury")
    fallback_value = _treasury_10y(fallback) if fallback else None
    return fallback_value, resolved_date if fallback_value is not None else None


def _relation_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
    try:
        row = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where table_name = ?
            """,
            [relation_name],
        ).fetchone()
    except duckdb.Error:
        return False
    return bool(row and row[0])


def _choice_macro_value_on_or_before(
    *,
    conn: duckdb.DuckDBPyConnection,
    relation_name: str,
    series_id: str,
    trade_date: str,
) -> tuple[float | None, str | None]:
    if not _relation_exists(conn, relation_name):
        return None, None
    try:
        row = conn.execute(
            f"""
            select value_numeric, cast(trade_date as varchar)
            from {relation_name}
            where series_id = ?
              and cast(trade_date as varchar) <= ?
              and value_numeric is not null
            order by cast(trade_date as varchar) desc
            limit 1
            """,
            [series_id, trade_date],
        ).fetchone()
    except duckdb.Error:
        return None, None
    if row is None:
        return None, None
    return float(row[0]), str(row[1])


def _dr007_on_or_before(duckdb_path: str, trade_date: str) -> tuple[float | None, str | None]:
    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
    except duckdb.Error:
        return None, None
    try:
        for relation_name in ("fact_choice_macro_daily", "choice_market_snapshot"):
            value, resolved_date = _choice_macro_value_on_or_before(
                conn=conn,
                relation_name=relation_name,
                series_id="CA.DR007",
                trade_date=trade_date,
            )
            if value is not None:
                return value, resolved_date
    finally:
        conn.close()
    return None, None


def _anchor_on_or_before(dates: list[str], day: str) -> str | None:
    eligible = [d for d in dates if d <= day]
    return max(eligible) if eligible else None


def _resolve_formal_report_date(dates: list[str], report_date: str | None) -> str:
    requested = report_date or dates[0]
    return _anchor_on_or_before(dates, requested) or dates[0]


def _resolve_bond_report_date(dates: list[str], report_date: str | None) -> str:
    requested = report_date or _latest_formal_report_date() or dates[0]
    return _anchor_on_or_before(dates, requested) or dates[0]


def _mv_tpl_scale(
    pnl_rows: list[dict[str, Any]],
    bond_rows: list[dict[str, Any]],
) -> float:
    mv_by = pa_wb.mv_index(bond_rows)
    s = 0.0
    for r in pnl_rows:
        if not pa_wb.is_tpl_accounting(str(r.get("accounting_basis") or "")):
            continue
        s += mv_by.get(pa_wb.position_key(r), 0.0)
    return s


def _warning_message_for_evidence(evidence_rows: int | None) -> str:
    return QUALITY_WARN if int(evidence_rows or 0) > 0 else WARN


def _with_optional_warnings(
    payload: dict[str, Any],
    *,
    warn: bool,
    warning_message: str | None = None,
) -> dict[str, Any]:
    if warn:
        out = dict(payload)
        w = list(out.get("warnings") or [])
        message = warning_message or WARN
        if message not in w:
            w.append(message)
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


def _signed_number(
    value: float,
    *,
    precision: int,
    sign_aware: bool,
    suffix: str = "",
) -> str:
    if sign_aware and value >= 0:
        return f"+{value:,.{precision}f}{suffix}"
    return f"{value:,.{precision}f}{suffix}"


def _numeric_dict(raw: float | None, unit: NumericUnit, sign_aware: bool) -> dict[str, Any]:
    if raw is None or unit != "pct":
        return numeric_from_raw(raw=raw, unit=unit, sign_aware=sign_aware).model_dump(mode="json")

    percent_points = float(raw)
    return Numeric(
        raw=percent_points / 100.0,
        unit=unit,
        display=_signed_number(percent_points, precision=2, sign_aware=sign_aware, suffix="%"),
        precision=2,
        sign_aware=sign_aware,
    ).model_dump(mode="json")


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


def _to_workbook_percent_point_scalars(
    payload: dict[str, Any],
    pct_fields: set[str],
) -> dict[str, Any]:
    """Strip Numeric dicts while restoring pct fields to legacy percent points."""
    out = _to_workbook_scalars(payload)
    for field in pct_fields:
        value = payload.get(field)
        if not isinstance(value, dict):
            continue
        if value.get("unit") != "pct":
            continue
        raw = value.get("raw")
        out[field] = None if raw is None else float(raw) * 100.0
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

    rd = _resolve_formal_report_date(dates, report_date)
    ym = rd[:7]
    prev_ym = _prev_year_same_month_ym(ym) if compare_type == "yoy" else _prev_month_ym(ym)
    cur_snap = _max_date_in_month(dates, ym) or rd
    prev_snap = _max_date_in_month(dates, prev_ym)

    cur_business = _pnl_by_business_snapshot(cur_snap)
    prev_business = _pnl_by_business_snapshot(prev_snap) if prev_snap else None
    cur_rows = cur_business["rows"]
    prev_rows = prev_business["rows"] if prev_business else []
    cur_group_rows = _business_rows_as_pnl_rows(cur_rows)
    prev_group_rows = _business_rows_as_pnl_rows(prev_rows)

    payload = pa_wb.build_volume_rate_attribution_from_grouped_rows(
        current_rows=cur_group_rows,
        prior_rows=prev_group_rows if prev_snap else None,
        current_period=ym,
        previous_period=prev_ym if prev_snap else "",
        compare_type=compare_type,
        group_field="invest_type_std",
        pnl_field="total_pnl",
        scale_field="scale_amount",
    )
    warn = (
        not cur_rows
        or not prev_snap
        or not prev_rows
        or cur_business["quality_flag"] != "ok"
        or (prev_business is not None and prev_business["quality_flag"] != "ok")
    )
    filters = {
        "requested_report_date": report_date,
        "resolved_report_date": cur_snap,
        "previous_report_date": prev_snap,
        "compare_type": compare_type,
    }
    evidence_rows = int(cur_business["evidence_rows"]) + int(prev_business["evidence_rows"] if prev_business else 0)
    source_version = str(cur_business["source_version"])
    tables_used = list(cur_business["tables_used"])
    promoted = _promote_payload_numerics(payload, VolumeRateAttributionPayload)
    p = VolumeRateAttributionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.volume_rate",
                source_version=source_version if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=tables_used,
                evidence_rows=evidence_rows,
                as_of_date=cur_snap,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.volume_rate",
                source_version=source_version,
                filters_applied=filters,
                tables_used=tables_used,
                evidence_rows=evidence_rows,
                as_of_date=cur_snap,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=_warning_message_for_evidence(evidence_rows),
        ),
    )


def tpl_market_correlation_envelope(*, months: int = 12, report_date: str | None = None) -> dict[str, object]:
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

    requested = report_date or pnl_dates[0]
    rd = _anchor_on_or_before(pnl_dates, requested) or pnl_dates[0]
    series = _month_series_descending_until(pnl_dates, months, rd)
    series = list(reversed(series))
    bdates = set(bond.list_report_dates())
    points: list[dict[str, Any]] = []
    prev_tsy: float | None = None
    if series:
        prior_ym = _prev_month_ym(series[0])
        prior_snap = _max_date_in_month(pnl_dates, prior_ym)
        if prior_snap:
            prev_tsy, _ = _treasury_10y_on_or_before(curve, prior_snap)
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
        tsy, _tsy_date = _treasury_10y_on_or_before(curve, snap)
        dtsy = ((tsy - prev_tsy) * 100.0) if tsy is not None and prev_tsy is not None else None
        prev_tsy = tsy if tsy is not None else prev_tsy
        curve_path = str(getattr(curve, "path", "") or "")
        dr007, _dr007_date = _dr007_on_or_before(curve_path, snap) if curve_path else (None, None)
        points.append(
            {
                "period": ym,
                "period_label": _period_label_cn(ym),
                "tpl_fair_value_change": tpl_fv,
                "tpl_total_pnl": tpl_tot,
                "tpl_scale": tpl_scale,
                "treasury_10y": tsy,
                "treasury_10y_change": dtsy,
                "dr007": dr007,
            }
        )

    start_p = series[0] if series else ""
    end_p = series[-1] if series else ""
    payload = pa_wb.build_tpl_market_correlation(
        monthly_points=points,
        start_period=start_p,
        end_period=end_p,
    )
    warn = len(points) < 2 or any(
        point.get("treasury_10y") is None or point.get("dr007") is None
        for point in points
    )
    promoted = _promote_payload_numerics(payload, TPLMarketCorrelationPayload)
    p = TPLMarketCorrelationPayload.model_validate(promoted).model_dump(mode="json")
    filters = {
        "requested_report_date": report_date,
        "resolved_report_date": rd,
        "months": months,
    }
    evidence_rows = len(points)
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.tpl_market",
                source_version=SOURCE_VERSION_MARKET if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_FORMAL_MARKET,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.tpl_market",
                source_version=SOURCE_VERSION_MARKET,
                filters_applied=filters,
                tables_used=TABLES_FORMAL_MARKET,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=TPL_MARKET_DATA_WARN if evidence_rows else _warning_message_for_evidence(evidence_rows),
        ),
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

    rd = _resolve_formal_report_date(dates, report_date)
    ym = rd[:7]
    business_snapshot = _pnl_by_business_snapshot(rd)
    business_rows = business_snapshot["rows"]
    rows = _business_rows_as_pnl_rows(business_rows)
    trend: list[dict[str, Any]] = []
    if include_trend:
        months = _month_series_descending_until(dates, trend_months, rd)
        months = list(reversed(months))
        for m in months:
            snap = _max_date_in_month(dates, m)
            if not snap:
                continue
            pr = _pnl_by_business_snapshot(snap)["rows"]
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
    warn = not business_rows or business_snapshot["quality_flag"] != "ok"
    filters = {
        "requested_report_date": report_date,
        "resolved_report_date": rd,
        "include_trend": include_trend,
        "trend_months": trend_months,
    }
    evidence_rows = int(business_snapshot["evidence_rows"])
    source_version = str(business_snapshot["source_version"])
    tables_used = list(business_snapshot["tables_used"])
    promoted = _promote_payload_numerics(payload, PnlCompositionPayload)
    p = PnlCompositionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.composition",
                source_version=source_version if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=tables_used,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.composition",
                source_version=source_version,
                filters_applied=filters,
                tables_used=tables_used,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=_warning_message_for_evidence(evidence_rows),
        ),
    )


def attribution_analysis_summary_envelope(*, report_date: str | None) -> dict[str, object]:
    """Summarizes only the formal FI / bond-analysis attribution lens."""
    repo_dates = _pnl_repo().list_formal_fi_report_dates()
    rd = report_date or (repo_dates[0] if repo_dates else "")
    vol_env = volume_rate_attribution_envelope(report_date=rd or None, compare_type="mom")
    tpl_env = tpl_market_correlation_envelope(months=12, report_date=rd or None)
    vol_meta = dict(vol_env.get("result_meta") or {})
    tpl_meta = dict(tpl_env.get("result_meta") or {})
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
    tables_used = list(
        dict.fromkeys(
            [
                str(table)
                for meta in (vol_meta, tpl_meta)
                for table in (meta.get("tables_used") or [])
            ]
        )
    )
    source_versions = [
        str(version)
        for version in (vol_meta.get("source_version"), tpl_meta.get("source_version"))
        if version and str(version) != SOURCE_EMPTY
    ]
    evidence_rows = sum(
        int(meta.get("evidence_rows") or 0)
        for meta in (vol_meta, tpl_meta)
    )
    filters = {
        "requested_report_date": report_date,
        "resolved_report_date": rd or None,
        "components": ["volume_rate", "tpl_market"],
    }
    source_version = "__".join(dict.fromkeys(source_versions)) if evidence_rows else SOURCE_EMPTY
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.summary",
                source_version=source_version,
                filters_applied=filters,
                tables_used=tables_used,
                evidence_rows=evidence_rows,
                as_of_date=rd or None,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.summary",
                source_version=source_version or SOURCE_VERSION,
                filters_applied=filters,
                tables_used=tables_used,
                evidence_rows=evidence_rows,
                as_of_date=rd or None,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=_warning_message_for_evidence(evidence_rows),
        ),
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

    rd = _resolve_bond_report_date(dates, report_date)
    rows = bond.fetch_bond_analytics_rows(report_date=rd) if rd in dates else []
    cur_repo = _curve_repo()
    c_end = cur_repo.fetch_curve(rd, "treasury")
    payload = pa_wb.build_carry_roll_down(
        report_date=rd,
        bond_rows=rows,
        ftp_rate_pct=ftp,
        curve_slope_bp=None,
        treasury_curve=c_end,
    )
    warn = not rows
    evidence_rows = len(rows)
    filters = {
        "requested_report_date": report_date,
        "resolved_report_date": rd,
    }
    promoted = _promote_payload_numerics(payload, CarryRollDownPayload)
    p = CarryRollDownPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.carry_rolldown",
                source_version=SOURCE_VERSION_MARKET if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.carry_rolldown",
                source_version=SOURCE_VERSION_MARKET,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=_warning_message_for_evidence(evidence_rows),
        ),
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

    rd = _resolve_bond_report_date(dates, report_date)
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
    evidence_rows = len(rows_e) + len(rows_s)
    filters = {
        "requested_report_date": report_date,
        "resolved_report_date": rd,
        "start_date": anchor or start_iso,
        "lookback_days": lookback_days,
    }
    promoted = _promote_payload_numerics(payload, SpreadAttributionPayload)
    p = SpreadAttributionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.spread",
                source_version=SOURCE_VERSION_MARKET if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.spread",
                source_version=SOURCE_VERSION_MARKET,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=_warning_message_for_evidence(evidence_rows),
        ),
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

    rd = _resolve_bond_report_date(dates, report_date)
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
    evidence_rows = len(rows_e) + len(rows_s)
    filters = {
        "requested_report_date": report_date,
        "resolved_report_date": rd,
        "start_date": anchor or start_d.isoformat(),
        "lookback_days": lookback_days,
    }
    promoted = _promote_payload_numerics(payload, KRDAttributionPayload)
    p = KRDAttributionPayload.model_validate(promoted).model_dump(mode="json")
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.krd",
                source_version=SOURCE_VERSION_MARKET if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.krd",
                source_version=SOURCE_VERSION_MARKET,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=rd,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=_warning_message_for_evidence(evidence_rows),
        ),
    )


def advanced_attribution_summary_envelope(*, report_date: str | None) -> dict[str, object]:
    c = carry_roll_down_envelope(report_date=report_date)
    s = spread_attribution_envelope(report_date=report_date, lookback_days=30)
    k = krd_attribution_envelope(report_date=report_date, lookback_days=30)
    child_metas = [dict(x.get("result_meta") or {}) for x in (c, s, k)]
    payload = pa_wb.build_advanced_attribution_summary(
        report_date=str(report_date or ""),
        carry_payload=_to_workbook_percent_point_scalars(
            dict(c.get("result") or {}),
            {"portfolio_carry", "portfolio_rolldown", "portfolio_static_return"},
        ),
        spread_payload=_to_workbook_scalars(dict(s.get("result") or {})),
        krd_payload=_to_workbook_scalars(dict(k.get("result") or {})),
    )
    rd = report_date or dict(c.get("result") or {}).get("report_date") or ""
    payload["report_date"] = str(rd or payload["report_date"])
    warn = any(bool(dict(x.get("result") or {}).get("warnings")) for x in (c, s, k))
    promoted = _promote_payload_numerics(payload, AdvancedAttributionSummary)
    p = AdvancedAttributionSummary.model_validate(promoted).model_dump(mode="json")
    tables_used = list(
        dict.fromkeys(
            [
                str(table)
                for meta in child_metas
                for table in (meta.get("tables_used") or [])
            ]
        )
    )
    source_versions = [
        str(version)
        for meta in child_metas
        for version in [meta.get("source_version")]
        if version and str(version) != SOURCE_EMPTY
    ]
    evidence_rows = sum(int(meta.get("evidence_rows") or 0) for meta in child_metas)
    filters = {
        "requested_report_date": report_date,
        "resolved_report_date": rd or None,
        "components": ["carry_rolldown", "spread", "krd"],
    }
    source_version = "__".join(dict.fromkeys(source_versions)) if evidence_rows else SOURCE_EMPTY
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.advanced_summary",
                source_version=source_version,
                filters_applied=filters,
                tables_used=tables_used,
                evidence_rows=evidence_rows,
                as_of_date=str(rd or "") or None,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.advanced_summary",
                source_version=source_version or SOURCE_VERSION_MARKET,
                filters_applied=filters,
                tables_used=tables_used,
                evidence_rows=evidence_rows,
                as_of_date=str(rd or "") or None,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=_warning_message_for_evidence(evidence_rows),
        ),
    )


def _empty_path_a_payload(period_start: str, period_end: str) -> dict[str, Any]:
    """Empty Path A Campisi payload (matches `CampisiAttributionPayload` shape)."""
    return {
        "report_date": period_end,
        "period_start": period_start,
        "period_end": period_end,
        "num_days": 0,
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


def _core_campisi_result_to_path_a_payload(
    result: Any,
    *,
    report_date: str,
    period_start: str,
    period_end: str,
) -> dict[str, Any]:
    """Adapt `CampisiResult` (Path B / single-bond core) into `CampisiAttributionPayload` shape."""
    totals = dict(result.totals or {})
    total_mv = float(totals.get("market_value_start") or 0.0)
    total_return = float(totals.get("total_return") or 0.0)
    tot_inc = float(totals.get("income_return") or 0.0)
    tot_t = float(totals.get("treasury_effect") or 0.0)
    tot_s = float(totals.get("spread_effect") or 0.0)
    tot_sel = float(totals.get("selection_effect") or 0.0)

    # Relative zero-guard: effects may cancel to a tiny residual while each part is large.
    # Use 1e-6 × max(|total_mv|, |part|) as the "effectively zero" threshold for total_return.
    _share_eps = max(abs(total_mv), abs(tot_inc), abs(tot_t), abs(tot_s), abs(tot_sel)) * 1e-6

    def _share(part: float) -> float:
        if abs(total_return) <= _share_eps:
            return 0.0
        return part / total_return * 100.0

    items: list[dict[str, Any]] = []
    for b in result.by_asset_class or []:
        # Core returns Decimal for mv/effects and Decimal *_pct already expressed in percent points.
        mv = float(b.get("market_value_start") or 0)
        tr = float(b.get("total_return") or 0)
        ir = float(b.get("income_return") or 0)
        te = float(b.get("treasury_effect") or 0)
        sp = float(b.get("spread_effect") or 0)
        se = float(b.get("selection_effect") or 0)
        weight_pct = float(b.get("weight_pct") or 0)
        items.append(
            {
                "category": str(b.get("asset_class") or "未分类"),
                "market_value": round(mv, 4),
                "weight": round(weight_pct / 100.0, 6),  # ratio for schema
                "total_return": round(tr, 4),
                "total_return_pct": round(float(b.get("total_return_pct") or 0), 4),
                "income_return": round(ir, 4),
                "income_return_pct": round(float(b.get("income_return_pct") or 0), 4),
                "treasury_effect": round(te, 4),
                "treasury_effect_pct": round(float(b.get("treasury_effect_pct") or 0), 4),
                "spread_effect": round(sp, 4),
                "spread_effect_pct": round(float(b.get("spread_effect_pct") or 0), 4),
                "selection_effect": round(se, 4),
                "selection_effect_pct": round(float(b.get("selection_effect_pct") or 0), 4),
            }
        )

    total_return_pct = (total_return / total_mv * 100.0) if abs(total_mv) >= 1e-9 else 0.0

    payload: dict[str, Any] = {
        "report_date": report_date,
        "period_start": period_start,
        "period_end": period_end,
        "num_days": int(result.num_days or 0),
        "total_market_value": round(total_mv, 4),
        "total_return": round(total_return, 4),
        "total_return_pct": round(total_return_pct, 4),
        "total_income": round(tot_inc, 4),
        "total_treasury_effect": round(tot_t, 4),
        "total_spread_effect": round(tot_s, 4),
        "total_selection_effect": round(tot_sel, 4),
        "income_contribution_pct": round(_share(tot_inc), 4),
        "treasury_contribution_pct": round(_share(tot_t), 4),
        "spread_contribution_pct": round(_share(tot_s), 4),
        "selection_contribution_pct": round(_share(tot_sel), 4),
        "primary_driver": classify_primary_driver(tot_inc, tot_t, tot_s, tot_sel),
        "interpretation": "Campisi 四效应（单券级，AC 类仅票息）：收入、国债平移、信用利差、选券残差。",
        "items": items,
    }
    if result.diagnostics:
        payload["warnings"] = list(result.diagnostics)
    return payload


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
        payload = _empty_path_a_payload("", "")
        promoted = _promote_payload_numerics(payload, CampisiAttributionPayload)
        p = CampisiAttributionPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.campisi"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    rd_end = _resolve_bond_report_date(dates, end_date)
    if start_date:
        rd_start = start_date
    else:
        rd_start = (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat()

    anchor_start = _anchor_on_or_before(dates, rd_start)
    anchor_end = rd_end if rd_end in dates else _anchor_on_or_before(dates, rd_end)

    if not anchor_start or not anchor_end:
        payload = _empty_path_a_payload(rd_start, rd_end)
        promoted = _promote_payload_numerics(payload, CampisiAttributionPayload)
        p = CampisiAttributionPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn("pnl_attribution.campisi"),
            result_payload=_with_optional_warnings(p, warn=True),
        )

    rows_start = bond.fetch_bond_analytics_rows(report_date=anchor_start)
    rows_end = bond.fetch_bond_analytics_rows(report_date=anchor_end)
    positions = merge_positions(rows_start, rows_end)
    evidence_rows = len(rows_start) + len(rows_end)
    filters = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "resolved_start_date": anchor_start,
        "resolved_end_date": anchor_end,
        "lookback_days": lookback_days,
    }

    if not positions:
        payload = _empty_path_a_payload(anchor_start, anchor_end)
        promoted = _promote_payload_numerics(payload, CampisiAttributionPayload)
        p = CampisiAttributionPayload.model_validate(promoted).model_dump(mode="json")
        return build_formal_result_envelope(
            result_meta=_meta_warn(
                "pnl_attribution.campisi",
                source_version=SOURCE_VERSION_MARKET if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=_with_optional_warnings(
                p,
                warn=True,
                warning_message=_warning_message_for_evidence(evidence_rows),
            ),
        )

    formal_bridge = _try_fetch_formal_bridge(settings=get_settings(), report_date=anchor_end)
    if _formal_bridge_has_position_overlap(formal_bridge, positions):
        result = _formal_bridge_to_campisi_result(
            bridge_envelope=formal_bridge,
            positions=positions,
            start_date=date.fromisoformat(anchor_start),
            end_date=date.fromisoformat(anchor_end),
        )
        payload = _core_campisi_result_to_path_a_payload(
            result,
            report_date=anchor_end,
            period_start=anchor_start,
            period_end=anchor_end,
        )
        payload["basis"] = FORMAL_REPORT_BASIS
        payload["interpretation"] = (
            "Campisi 正式报表口径：总收益锚定 pnl.bridge actual_pnl；"
            "收入取 carry，国债效应取 roll-down + treasury_curve，利差取 credit_spread，"
            "选择效应吸收正式 PnL 中其余已确认损益。"
        )
        promoted = _promote_payload_numerics(payload, CampisiAttributionPayload)
        p = CampisiAttributionPayload.model_validate(promoted).model_dump(mode="json")
        p["basis"] = FORMAL_REPORT_BASIS
        return build_formal_result_envelope(
            result_meta=_meta_ok(
                "pnl_attribution.campisi",
                source_version=SOURCE_VERSION_MARKET,
                filters_applied=filters,
                tables_used=sorted(set([*TABLES_FORMAL_MARKET, "fact_formal_zqtz_balance_daily"])),
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=p,
        )

    treasury_start = curve_to_market_dict(curve.fetch_curve(anchor_start, "treasury"))
    treasury_end = curve_to_market_dict(curve.fetch_curve(anchor_end, "treasury"))
    spread_start = fetch_credit_spread_market(curve, anchor_start)
    spread_end = fetch_credit_spread_market(curve, anchor_end)
    market_start: dict[str, Any] = {**treasury_start, **spread_start}
    market_end: dict[str, Any] = {**treasury_end, **spread_end}

    result = _core_campisi(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=date.fromisoformat(anchor_start),
        end_date=date.fromisoformat(anchor_end),
    )

    payload = _core_campisi_result_to_path_a_payload(
        result,
        report_date=anchor_end,
        period_start=anchor_start,
        period_end=anchor_end,
    )
    diagnostics = list(payload.get("warnings") or [])
    warn = bool(diagnostics)  # diagnostics (e.g. accrued_interest_missing) must surface as quality_flag=warning
    promoted = _promote_payload_numerics(payload, CampisiAttributionPayload)
    p = CampisiAttributionPayload.model_validate(promoted).model_dump(mode="json")
    if diagnostics:
        p["warnings"] = diagnostics
    return build_formal_result_envelope(
        result_meta=(
            _meta_warn(
                "pnl_attribution.campisi",
                source_version=SOURCE_VERSION_MARKET if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            )
            if warn
            else _meta_ok(
                "pnl_attribution.campisi",
                source_version=SOURCE_VERSION_MARKET,
                filters_applied=filters,
                tables_used=TABLES_BOND_ANALYTICS,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            )
        ),
        result_payload=_with_optional_warnings(
            p,
            warn=warn,
            warning_message=_warning_message_for_evidence(evidence_rows),
        ),
    )
