"""Consolidated dashboard KPIs — analytical basis, reads formal facts + DuckDB aggregates."""
from __future__ import annotations

import uuid
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Literal

from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import FACT_TABLE
from backend.app.repositories.dashboard_repo import TYW_FACT, DashboardRepository
from backend.app.schemas.common_numeric import Numeric, null_numeric, numeric_from_raw
from backend.app.schemas.dashboard import (
    CoreMetricsCardData,
    CoreMetricsPayload,
    DailyChangePeriod,
    DailyChangesPayload,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.runtime_cache import InMemoryTTLCache, get_runtime_cache

_DASHBOARD_CACHE_VERSION = "cv_dashboard_analytical_v1"
_DASHBOARD_RULE_VERSION = "rv_dashboard_read_v1"
_DASHBOARD_SOURCE_VERSION = "sv_dashboard_duckdb"
_DASHBOARD_CACHE_TTL_SECONDS = 300.0
_DashboardCacheKey = tuple[str, str | None, str, int | None]
_DASHBOARD_CACHE: InMemoryTTLCache[_DashboardCacheKey, dict[str, object]] = get_runtime_cache(
    "dashboard.read_models",
    ttl_seconds=_DASHBOARD_CACHE_TTL_SECONDS,
)

_PeriodLiteral = Literal["day", "week", "month"]


def _repo() -> DashboardRepository:
    return DashboardRepository(str(get_settings().duckdb_path))


def _normalize_dashboard_report_date(report_date: str | None) -> str | None:
    normalized = str(report_date or "").strip()
    return normalized or None


def _dashboard_cache_key(endpoint: str, report_date: str | None) -> _DashboardCacheKey:
    duckdb_path = str(get_settings().duckdb_path)
    try:
        duckdb_mtime_ns: int | None = Path(duckdb_path).stat().st_mtime_ns
    except OSError:
        duckdb_mtime_ns = None
    return (endpoint, _normalize_dashboard_report_date(report_date), duckdb_path, duckdb_mtime_ns)


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _with_fresh_trace(envelope: dict[str, object]) -> dict[str, object]:
    response = deepcopy(envelope)
    meta = response.get("result_meta")
    if isinstance(meta, dict):
        meta["trace_id"] = _trace_id()
    return response


def _pct_numeric_from_fraction(frac: Decimal | None, *, precision: int = 2) -> Numeric:
    if frac is None:
        return null_numeric(unit="pct", precision=precision, sign_aware=False)
    pct = frac * Decimal("100")
    return numeric_from_raw(
        raw=float(pct),
        unit="pct",
        precision=precision,
        sign_aware=False,
        signed_format=False,
    )


def _yuan_numeric(val: Decimal, *, sign_aware: bool) -> Numeric:
    numeric = numeric_from_raw(
        raw=float(val),
        unit="yuan",
        precision=2,
        sign_aware=sign_aware,
        signed_format=sign_aware,
    )
    numeric.display = _fmt_yuan_as_yi(val, sign_aware=sign_aware)
    return numeric


def _fmt_yuan_as_yi(value: Decimal, *, sign_aware: bool = False) -> str:
    yi = value / Decimal("100000000")
    prefix = "+" if sign_aware and yi >= 0 else ""
    return f"{prefix}{yi:,.2f} 亿"


def _fmt_rate_pct(value: Decimal | None) -> str:
    if value is None:
        return "—"
    pct = value * Decimal("100")
    return f"{pct:,.2f}%"


def _pct_change_numeric(chg_amt: Decimal, prev: Decimal) -> Numeric:
    if prev <= 0:
        return null_numeric(unit="pct", precision=2, sign_aware=True)
    pct = (chg_amt / prev) * Decimal("100")
    return numeric_from_raw(
        raw=float(pct),
        unit="pct",
        precision=2,
        sign_aware=True,
        signed_format=True,
    )


def _top_3_detail_rows(
    rows: list[tuple[str, Decimal, Decimal | None]],
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for name, amt, rte in rows:
        out.append({"name": name, "amount": _fmt_yuan_as_yi(amt), "rate": _fmt_rate_pct(rte)})
    return out


def _prior_by_offset(canonical_desc: list[str], anchor: str, offset: int) -> str | None:
    if anchor not in canonical_desc:
        return None
    i = canonical_desc.index(anchor)
    j = i + offset
    return canonical_desc[j] if j < len(canonical_desc) else None


def _first_in_month(merged_asc: list[str], anchor: str) -> str | None:
    """First (earliest) merged date in anchor's calendar month, not later than anchor."""
    if len(anchor) < 7:
        return None
    ym = anchor[:7]
    in_month = sorted([d for d in merged_asc if d.startswith(ym) and d <= anchor])
    return in_month[0] if in_month else None


def _prior_for_period(canonical_desc: list[str], anchor: str, kind: _PeriodLiteral) -> str | None:
    if not canonical_desc:
        return None
    asc = sorted(canonical_desc, reverse=False)
    desc_newest_first = sorted(canonical_desc, reverse=True)
    if anchor not in desc_newest_first:
        return None
    if kind == "day":
        return _prior_by_offset(desc_newest_first, anchor, 1)
    if kind == "week":
        return _prior_by_offset(desc_newest_first, anchor, 5)
    if kind == "month":
        return _first_in_month(asc, anchor)
    return None


def _build_one_core_card(
    cur_tot: Decimal,
    cur_wr: Decimal | None,
    top: list[tuple[str, Decimal, Decimal | None]],
    *,
    cur_has_rows: bool,
    prev_tot: Decimal,
    prev_has_rows: bool,
) -> CoreMetricsCardData:
    can_compute_change = cur_has_rows and prev_has_rows
    chg_amt = cur_tot - prev_tot if can_compute_change else None
    return CoreMetricsCardData(
        total_amount=_yuan_numeric(cur_tot, sign_aware=False),
        weighted_avg_rate=_pct_numeric_from_fraction(cur_wr),
        change_amount=(
            _yuan_numeric(chg_amt, sign_aware=True)
            if chg_amt is not None
            else null_numeric(unit="yuan", precision=2, sign_aware=True)
        ),
        change_pct=(
            _pct_change_numeric(chg_amt, prev_tot)
            if chg_amt is not None
            else null_numeric(unit="pct", precision=2, sign_aware=True)
        ),
        top_3_details=_top_3_detail_rows(top),
    )


def _dashboard_anchor(report_date: str | None, canonical_desc: list[str]) -> str | None:
    s = "" if report_date is None else str(report_date).strip()
    if s != "":
        return s
    if canonical_desc:
        return canonical_desc[0]
    return None


_CoreMetricResult = tuple[Decimal, Decimal | None, list[tuple[str, Decimal, Decimal | None]], bool]


def _empty_metric_result() -> _CoreMetricResult:
    return Decimal("0"), None, [], False


def _ordered_unique_dates(report_dates: list[str | None]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in report_dates:
        d = str(raw or "").strip()
        if not d or d in seen:
            continue
        seen.add(d)
        out.append(d)
    return out


def _fetch_bond_metrics_for_dates(
    repo: DashboardRepository,
    report_dates: list[str],
) -> dict[str, _CoreMetricResult]:
    out = {d: _empty_metric_result() for d in report_dates}
    fetch_many = getattr(repo, "fetch_bond_core_metrics_for_dates", None)
    if callable(fetch_many):
        try:
            out.update(fetch_many(report_dates))
            return out
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass
    for d in report_dates:
        out[d] = repo.fetch_bond_core_metrics(d)
    return out


def _fetch_tyw_metrics_for_dates(
    repo: DashboardRepository,
    report_dates: list[str],
    *,
    asset_side: bool,
) -> dict[str, _CoreMetricResult]:
    out = {d: _empty_metric_result() for d in report_dates}
    fetch_many = getattr(repo, "fetch_tyw_core_metrics_for_dates", None)
    if callable(fetch_many):
        try:
            out.update(fetch_many(report_dates, asset_side=asset_side))
            return out
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass
    for d in report_dates:
        out[d] = repo.fetch_tyw_core_metrics(d, asset_side=asset_side)
    return out


def _zeroed_metrics_card() -> CoreMetricsCardData:
    zero = Decimal("0")
    return CoreMetricsCardData(
        total_amount=_yuan_numeric(zero, sign_aware=False),
        weighted_avg_rate=_pct_numeric_from_fraction(None),
        change_amount=_yuan_numeric(zero, sign_aware=True),
        change_pct=null_numeric(unit="pct", precision=2, sign_aware=True),
        top_3_details=[],
    )


def invalidate_dashboard_cache() -> None:
    _DASHBOARD_CACHE.clear()


def get_core_metrics(report_date: str | None = None) -> dict[str, object]:
    normalized_report_date = _normalize_dashboard_report_date(report_date)
    return _with_fresh_trace(
        _DASHBOARD_CACHE.get_or_set(
            _dashboard_cache_key("core_metrics", normalized_report_date),
            lambda: _compute_core_metrics(normalized_report_date),
        )
    )


def _compute_core_metrics(report_date: str | None = None) -> dict[str, object]:
    repo = _repo()
    canonical = sorted(repo.list_merged_report_dates())
    canonical_desc = sorted(canonical, reverse=True)
    anchor = _dashboard_anchor(report_date, canonical_desc)
    trace = _trace_id()

    zcard = _zeroed_metrics_card()
    if anchor is None:
        payload = CoreMetricsPayload(
            report_date="",
            bond_investments=zcard.model_copy(deep=True),
            interbank_assets=zcard.model_copy(deep=True),
            interbank_liabilities=zcard.model_copy(deep=True),
        ).model_dump(mode="json")
        return build_result_envelope(
            basis="analytical",
            trace_id=trace,
            result_kind="dashboard.core_metrics",
            cache_version=_DASHBOARD_CACHE_VERSION,
            source_version=_DASHBOARD_SOURCE_VERSION,
            rule_version=_DASHBOARD_RULE_VERSION,
            quality_flag="warning",
            result_payload=payload,
            tables_used=[FACT_TABLE, TYW_FACT],
            evidence_rows=0,
        )

    prev_day = (
        _prior_for_period(canonical_desc, anchor, "day") if anchor in canonical_desc else None
    )

    metric_dates = _ordered_unique_dates([anchor, prev_day])
    bond_by_date = _fetch_bond_metrics_for_dates(repo, metric_dates)
    asset_by_date = _fetch_tyw_metrics_for_dates(repo, metric_dates, asset_side=True)
    liability_by_date = _fetch_tyw_metrics_for_dates(repo, metric_dates, asset_side=False)

    b_prev, _, _, b_prev_has_rows = (
        bond_by_date.get(prev_day, _empty_metric_result()) if prev_day else _empty_metric_result()
    )
    a_prev, _, _, a_prev_has_rows = (
        asset_by_date.get(prev_day, _empty_metric_result()) if prev_day else _empty_metric_result()
    )
    l_prev, _, _, l_prev_has_rows = (
        liability_by_date.get(prev_day, _empty_metric_result()) if prev_day else _empty_metric_result()
    )
    b_cur, b_wy, b_top, b_cur_has_rows = bond_by_date.get(anchor, _empty_metric_result())
    a_cur, a_wy, a_top, a_cur_has_rows = asset_by_date.get(anchor, _empty_metric_result())
    l_cur, l_wy, l_top, l_cur_has_rows = liability_by_date.get(anchor, _empty_metric_result())

    body = CoreMetricsPayload(
        report_date=anchor,
        bond_investments=_build_one_core_card(
            b_cur,
            b_wy,
            b_top,
            cur_has_rows=b_cur_has_rows,
            prev_tot=b_prev,
            prev_has_rows=b_prev_has_rows,
        ),
        interbank_assets=_build_one_core_card(
            a_cur,
            a_wy,
            a_top,
            cur_has_rows=a_cur_has_rows,
            prev_tot=a_prev,
            prev_has_rows=a_prev_has_rows,
        ),
        interbank_liabilities=_build_one_core_card(
            l_cur,
            l_wy,
            l_top,
            cur_has_rows=l_cur_has_rows,
            prev_tot=l_prev,
            prev_has_rows=l_prev_has_rows,
        ),
    )

    return build_result_envelope(
        basis="analytical",
        trace_id=trace,
        result_kind="dashboard.core_metrics",
        cache_version=_DASHBOARD_CACHE_VERSION,
        source_version=_DASHBOARD_SOURCE_VERSION,
        rule_version=_DASHBOARD_RULE_VERSION,
        quality_flag="ok",
        result_payload=body.model_dump(mode="json"),
        tables_used=[FACT_TABLE, TYW_FACT],
        evidence_rows=len(b_top) + len(a_top) + len(l_top),
    )


def _null_yuan_changes() -> tuple[Numeric, Numeric, Numeric, Numeric]:
    z = null_numeric(unit="yuan", precision=8, sign_aware=True)
    return z, z, z, z


def get_daily_changes(report_date: str | None = None) -> dict[str, object]:
    normalized_report_date = _normalize_dashboard_report_date(report_date)
    return _with_fresh_trace(
        _DASHBOARD_CACHE.get_or_set(
            _dashboard_cache_key("daily_changes", normalized_report_date),
            lambda: _compute_daily_changes(normalized_report_date),
        )
    )


def _compute_daily_changes(report_date: str | None = None) -> dict[str, object]:
    repo = _repo()
    canonical = sorted(repo.list_merged_report_dates())
    canonical_desc = sorted(canonical, reverse=True)
    anchor = _dashboard_anchor(report_date, canonical_desc)
    trace = _trace_id()

    if anchor is None:
        payload = DailyChangesPayload(report_date="", periods=[]).model_dump(mode="json")
        return build_result_envelope(
            basis="analytical",
            trace_id=trace,
            result_kind="dashboard.daily_changes",
            cache_version=_DASHBOARD_CACHE_VERSION,
            source_version=_DASHBOARD_SOURCE_VERSION,
            rule_version=_DASHBOARD_RULE_VERSION,
            quality_flag="warning",
            result_payload=payload,
            tables_used=[FACT_TABLE, TYW_FACT],
            evidence_rows=0,
        )

    zs_b, zs_a, zs_l, zs_n = _null_yuan_changes()
    base_by_period = {
        label: (
            _prior_for_period(canonical_desc, anchor, label)
            if anchor in canonical_desc
            else None
        )
        for label in ("day", "week", "month")
    }
    metric_dates = _ordered_unique_dates([anchor, *base_by_period.values()])
    bond_by_date = _fetch_bond_metrics_for_dates(repo, metric_dates)
    asset_by_date = _fetch_tyw_metrics_for_dates(repo, metric_dates, asset_side=True)
    liability_by_date = _fetch_tyw_metrics_for_dates(repo, metric_dates, asset_side=False)
    periods_out: list[DailyChangePeriod] = []
    for label in ("day", "week", "month"):
        base_rd = base_by_period[label]
        cur_triple = (
            (bond_by_date.get(anchor, _empty_metric_result())[0], bond_by_date.get(anchor, _empty_metric_result())[3]),
            (asset_by_date.get(anchor, _empty_metric_result())[0], asset_by_date.get(anchor, _empty_metric_result())[3]),
            (liability_by_date.get(anchor, _empty_metric_result())[0], liability_by_date.get(anchor, _empty_metric_result())[3]),
        )
        base_triple = (
            (
                bond_by_date.get(base_rd, _empty_metric_result())[0],
                bond_by_date.get(base_rd, _empty_metric_result())[3],
            ),
            (
                asset_by_date.get(base_rd, _empty_metric_result())[0],
                asset_by_date.get(base_rd, _empty_metric_result())[3],
            ),
            (
                liability_by_date.get(base_rd, _empty_metric_result())[0],
                liability_by_date.get(base_rd, _empty_metric_result())[3],
            ),
        ) if base_rd else None

        if cur_triple is None or base_triple is None or base_rd is None:
            periods_out.append(
                DailyChangePeriod(
                    period=label,
                    bond_investments_change=zs_b,
                    interbank_assets_change=zs_a,
                    interbank_liabilities_change=zs_l,
                    net_change=zs_n,
                )
            )
            continue

        (bn, b_cur_has_rows), (an, a_cur_has_rows), (ln, l_cur_has_rows) = cur_triple
        (bp, b_base_has_rows), (ap, a_base_has_rows), (lp, l_base_has_rows) = base_triple
        bd = bn - bp if b_cur_has_rows and b_base_has_rows else None
        ad = an - ap if a_cur_has_rows and a_base_has_rows else None
        ld = ln - lp if l_cur_has_rows and l_base_has_rows else None
        net_d = bd + ad + ld if bd is not None and ad is not None and ld is not None else None
        periods_out.append(
            DailyChangePeriod(
                period=label,
                bond_investments_change=_yuan_numeric(bd, sign_aware=True) if bd is not None else zs_b,
                interbank_assets_change=_yuan_numeric(ad, sign_aware=True) if ad is not None else zs_a,
                interbank_liabilities_change=_yuan_numeric(ld, sign_aware=True) if ld is not None else zs_l,
                net_change=_yuan_numeric(net_d, sign_aware=True) if net_d is not None else zs_n,
            )
        )

    payload = DailyChangesPayload(report_date=anchor, periods=periods_out).model_dump(mode="json")
    return build_result_envelope(
        basis="analytical",
        trace_id=trace,
        result_kind="dashboard.daily_changes",
        cache_version=_DASHBOARD_CACHE_VERSION,
        source_version=_DASHBOARD_SOURCE_VERSION,
        rule_version=_DASHBOARD_RULE_VERSION,
        quality_flag="ok",
        result_payload=payload,
        tables_used=[FACT_TABLE, TYW_FACT],
        evidence_rows=len(periods_out),
    )
