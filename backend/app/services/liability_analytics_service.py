from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from backend.app.core_finance.liability_analytics_compat import (
    compute_liabilities_monthly,
    compute_liability_counterparty,
    compute_liability_risk_buckets,
    compute_liability_yield_metrics,
    is_interest_bearing_bond_asset,
    normalize_bond_rate_decimal,
)
from backend.app.core_finance.liability_cockpit import (
    compute_cockpit_warnings,
    compute_contribution_split,
)
from backend.app.core_finance.yield_by_period import rollup_yield_periods
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.liability_analytics import (
    LiabilitiesMonthlyPayload,
    LiabilityBucketAmountItem,
    LiabilityCounterpartyByTypeItem,
    LiabilityCounterpartyPayload,
    LiabilityCounterpartyTopItem,
    LiabilityMonthlyBreakdownRow,
    LiabilityMonthlyItem,
    LiabilityNameAmountItem,
    LiabilityRiskBucketsPayload,
    LiabilityYieldHistoryPoint,
    LiabilityYieldKpi,
    LiabilityYieldMetricsPayload,
    LiabilityYieldScatterPoint,
)
from backend.app.services.explicit_numeric import promote_payload_numerics
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.runtime_cache import InMemoryTTLCache, get_runtime_cache

LIABILITY_ANALYTICS_CACHE_VERSION = "cv_liability_analytics_v1"
LIABILITY_ANALYTICS_RULE_VERSION = "rv_liability_analytics_compat_v1"
LIABILITY_ANALYTICS_EMPTY_SOURCE_VERSION = "sv_liability_analytics_empty"
NIM_STRESS_SHOCK_DECIMAL = Decimal("0.005")
NIM_STRESS_DELTA_BP = Decimal("-50")

_LIABILITY_MONTH_LIST_FIELDS = {
    "counterparty_top10": LiabilityMonthlyBreakdownRow,
    "by_institution_type": LiabilityMonthlyBreakdownRow,
    "structure_overview": LiabilityMonthlyBreakdownRow,
    "term_buckets": LiabilityMonthlyBreakdownRow,
    "interbank_by_type": LiabilityMonthlyBreakdownRow,
    "interbank_term_buckets": LiabilityMonthlyBreakdownRow,
    "issued_by_type": LiabilityMonthlyBreakdownRow,
    "issued_term_buckets": LiabilityMonthlyBreakdownRow,
    "counterparty_details": LiabilityMonthlyBreakdownRow,
}

_YIELD_METRICS_CACHE_TTL_SECONDS = 300.0
_YieldMetricsCacheKey = tuple[object, ...]
_YIELD_METRICS_CACHE: InMemoryTTLCache[_YieldMetricsCacheKey, dict[str, object]] = get_runtime_cache(
    "liability_analytics.yield_metrics",
    ttl_seconds=_YIELD_METRICS_CACHE_TTL_SECONDS,
)


def _yield_metrics_runtime_cache_enabled() -> bool:
    """Only cache when the module-level repo/compute symbols are the canonical
    ones — tests monkeypatch them on this module, and cached results must not
    leak across those substitutions."""
    from backend.app.core_finance.liability_analytics_compat import (
        compute_liability_yield_metrics as _canonical_compute,
    )
    from backend.app.repositories.liability_analytics_repo import (
        LiabilityAnalyticsRepository as _canonical_repo,
    )

    return (
        LiabilityAnalyticsRepository is _canonical_repo
        and compute_liability_yield_metrics is _canonical_compute
    )


def _yield_metrics_cache_key(duckdb_path: str, report_date: str | None) -> _YieldMetricsCacheKey | None:
    """Key bound to the DuckDB file identity (mtime/size, WAL folded in) so the
    entry expires as soon as the underlying data is rewritten."""
    if not _yield_metrics_runtime_cache_enabled():
        return None
    path = Path(duckdb_path)
    try:
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
        size = stat.st_size
        resolved = str(path.resolve())
    except OSError:
        return None
    try:
        mtime_ns = max(mtime_ns, Path(f"{duckdb_path}.wal").stat().st_mtime_ns)
    except OSError:
        pass
    return (
        "liability_analytics.yield_metrics",
        LIABILITY_ANALYTICS_CACHE_VERSION,
        LIABILITY_ANALYTICS_RULE_VERSION,
        resolved,
        mtime_ns,
        size,
        str(report_date or "").strip() or None,
    )


def _resolve_report_date(repo: LiabilityAnalyticsRepository, report_date: str | None) -> str:
    candidate = str(report_date or "").strip()
    if candidate:
        return candidate
    return repo.resolve_latest_report_date() or ""


def _merge_lineage(rows: list[dict[str, object]]) -> tuple[str, str]:
    source_versions = sorted(
        {
            str(row.get("source_version") or "").strip()
            for row in rows
            if str(row.get("source_version") or "").strip()
        }
    )
    rule_versions = sorted(
        {
            str(row.get("rule_version") or "").strip()
            for row in rows
            if str(row.get("rule_version") or "").strip()
        }
    )
    return (
        "__".join(source_versions) or LIABILITY_ANALYTICS_EMPTY_SOURCE_VERSION,
        "__".join(rule_versions) or LIABILITY_ANALYTICS_RULE_VERSION,
    )


def _envelope(
    *,
    result_kind: str,
    result_payload: dict[str, object],
    source_rows: list[dict[str, object]],
    quality_flag: str = "ok",
) -> dict[str, object]:
    source_version, rule_version = _merge_lineage(source_rows)
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_{result_kind}",
        result_kind=result_kind,
        cache_version=LIABILITY_ANALYTICS_CACHE_VERSION,
        source_version=source_version,
        rule_version=rule_version,
        quality_flag=quality_flag,
        vendor_version="vv_none",
        source_surface="formal_liability",
        result_payload=result_payload,
    )


def _promote_liability_month(item: dict[str, object]) -> dict[str, object]:
    promoted = promote_payload_numerics(
        item,
        LiabilityMonthlyItem,
        list_fields=_LIABILITY_MONTH_LIST_FIELDS,
    )
    return promoted if isinstance(promoted, dict) else item


def _promote_liability_payload(payload: dict[str, object], payload_cls: type) -> dict[str, object]:
    if payload_cls is LiabilityRiskBucketsPayload:
        promoted = promote_payload_numerics(
            payload,
            payload_cls,
            list_fields={
                "liabilities_structure": LiabilityNameAmountItem,
                "liabilities_term_buckets": LiabilityBucketAmountItem,
                "interbank_liabilities_structure": LiabilityNameAmountItem,
                "interbank_liabilities_term_buckets": LiabilityBucketAmountItem,
                "issued_liabilities_structure": LiabilityNameAmountItem,
                "issued_liabilities_term_buckets": LiabilityBucketAmountItem,
            },
        )
        return promoted if isinstance(promoted, dict) else payload
    if payload_cls is LiabilityYieldMetricsPayload:
        promoted = promote_payload_numerics(
            payload,
            payload_cls,
            object_fields={"kpi": LiabilityYieldKpi},
            list_fields={
                "history": LiabilityYieldHistoryPoint,
                "scatter": LiabilityYieldScatterPoint,
            },
        )
        return promoted if isinstance(promoted, dict) else payload
    if payload_cls is LiabilityCounterpartyPayload:
        promoted = promote_payload_numerics(
            payload,
            payload_cls,
            list_fields={
                "top_10": LiabilityCounterpartyTopItem,
                "by_type": LiabilityCounterpartyByTypeItem,
            },
        )
        return promoted if isinstance(promoted, dict) else payload
    if payload_cls is LiabilitiesMonthlyPayload:
        promoted = promote_payload_numerics(payload, payload_cls, list_fields={"months": LiabilityMonthlyItem})
        if not isinstance(promoted, dict):
            return payload
        months = promoted.get("months")
        if isinstance(months, list):
            promoted["months"] = [
                _promote_liability_month(item) if isinstance(item, dict) else item
                for item in months
            ]
        return promoted
    return payload


def _parse_iso_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()[:10]
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _raw_decimal(value: object) -> Decimal | None:
    if isinstance(value, dict):
        value = value.get("raw")
    if value is None:
        return None
    try:
        out = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return out if out.is_finite() else None


def _build_nim_stress(nim: object) -> dict[str, float | None]:
    nim_decimal = _raw_decimal(nim)
    if nim_decimal is None:
        return {"nim_stressed": None, "delta_bp": None}
    return {
        "nim_stressed": float(nim_decimal - NIM_STRESS_SHOCK_DECIMAL),
        "delta_bp": float(NIM_STRESS_DELTA_BP),
    }


def _build_yield_history_series(
    repo: LiabilityAnalyticsRepository,
    anchor_date: str,
    *,
    max_points: int = 72,
) -> list[dict[str, object]]:
    all_dates = repo.list_report_dates()
    if anchor_date not in all_dates:
        return []
    idx = all_dates.index(anchor_date)
    slice_desc = all_dates[idx : idx + max_points]
    slice_asc = list(reversed(slice_desc))
    zqtz_rows_by_date: dict[str, list[dict[str, Any]]] = {}
    tyw_rows_by_date: dict[str, list[dict[str, Any]]] = {}
    fetch_yield_rows = getattr(repo, "fetch_yield_rows_for_dates", None)
    if callable(fetch_yield_rows):
        try:
            zqtz_rows_by_date, tyw_rows_by_date = fetch_yield_rows(slice_desc)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            zqtz_rows_by_date, tyw_rows_by_date = {}, {}
    history: list[dict[str, object]] = []
    for d in slice_asc:
        if d in zqtz_rows_by_date:
            zq = zqtz_rows_by_date[d]
        else:
            zq = repo.fetch_zqtz_yield_rows(d)
        if d in tyw_rows_by_date:
            ty = tyw_rows_by_date[d]
        else:
            ty = repo.fetch_tyw_rows(d)
        try:
            m = compute_liability_yield_metrics(d, zq, ty)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            continue
        kpi = m.get("kpi") if isinstance(m, dict) else None
        if not isinstance(kpi, dict):
            continue
        history.append(
            {
                "date": d,
                "asset_yield": kpi.get("asset_yield"),
                "liability_cost": kpi.get("liability_cost"),
                "market_liability_cost": kpi.get("market_liability_cost"),
                "nim": kpi.get("nim"),
            }
        )
    return history


def _build_yield_scatter_points(zqtz_rows: list[dict[str, Any]], report_date: str) -> list[dict[str, object]]:
    rd = _parse_iso_date(report_date)
    if rd is None:
        return []
    out: list[dict[str, object]] = []
    for row in zqtz_rows:
        if bool(row.get("is_issuance_like")):
            continue
        if not is_interest_bearing_bond_asset(row):
            continue
        md = _parse_iso_date(row.get("maturity_date"))
        if md is None:
            continue
        years = (md - rd).days / 365.25
        if years <= 0:
            years = 0.05
        ytm = normalize_bond_rate_decimal(row.get("ytm_value"))
        if ytm is None:
            continue
        mv = row.get("market_value_native")
        if mv is None:
            mv = row.get("face_value_native")
        try:
            z = abs(float(mv))
        except (TypeError, ValueError):
            z = 0.0
        name = str(row.get("instrument_name") or row.get("instrument_code") or "")[:120]
        out.append({"x": float(years), "y": float(ytm), "z": float(z), "name": name})
        if len(out) >= 500:
            break
    return out


def liability_risk_buckets_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    zqtz_rows = repo.fetch_zqtz_rows(resolved_date) if resolved_date else []
    tyw_rows = repo.fetch_tyw_rows(resolved_date) if resolved_date else []
    if not resolved_date:
        return _envelope(
            result_kind="liability_analytics.risk_buckets",
            source_rows=[],
            quality_flag="warning",
            result_payload=LiabilityRiskBucketsPayload(
                report_date="",
                liabilities_structure=[],
                liabilities_term_buckets=[],
                interbank_liabilities_structure=[],
                interbank_liabilities_term_buckets=[],
                issued_liabilities_structure=[],
                issued_liabilities_term_buckets=[],
            ).model_dump(mode="json"),
        )
    payload = compute_liability_risk_buckets(
        resolved_date,
        zqtz_rows,
        tyw_rows,
    )
    return _envelope(
        result_kind="liability_analytics.risk_buckets",
        source_rows=[*zqtz_rows, *tyw_rows],
        result_payload=LiabilityRiskBucketsPayload.model_validate(
            _promote_liability_payload(payload, LiabilityRiskBucketsPayload)
        ).model_dump(mode="json"),
    )


def liability_yield_metrics_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    cache_key = _yield_metrics_cache_key(duckdb_path, report_date)
    if cache_key is None:
        return _compute_liability_yield_metrics_payload(duckdb_path=duckdb_path, report_date=report_date)
    envelope = _YIELD_METRICS_CACHE.get_or_set(
        cache_key,
        lambda: _compute_liability_yield_metrics_payload(
            duckdb_path=duckdb_path,
            report_date=report_date,
        ),
    )
    return deepcopy(envelope)


def _compute_liability_yield_metrics_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    zqtz_rows = repo.fetch_zqtz_yield_rows(resolved_date) if resolved_date else []
    tyw_rows = repo.fetch_tyw_rows(resolved_date) if resolved_date else []
    if not resolved_date:
        return _envelope(
            result_kind="liability_analytics.yield_metrics",
            source_rows=[],
            quality_flag="warning",
            result_payload=LiabilityYieldMetricsPayload(
                report_date="",
                kpi=LiabilityYieldKpi(),
                history=[],
                scatter=[],
            ).model_dump(mode="json"),
        )
    payload = compute_liability_yield_metrics(
        resolved_date,
        zqtz_rows,
        tyw_rows,
    )
    kpi = payload.get("kpi")
    if isinstance(kpi, dict):
        kpi = dict(kpi)
        kpi["nim_stress"] = _build_nim_stress(kpi.get("nim"))
        payload = {**payload, "kpi": kpi}
    history_dicts = _build_yield_history_series(repo, resolved_date, max_points=72)
    scatter_dicts = _build_yield_scatter_points(zqtz_rows, resolved_date)
    merged: dict[str, object] = {
        **payload,
        "history": history_dicts,
        "scatter": scatter_dicts,
    }
    return _envelope(
        result_kind="liability_analytics.yield_metrics",
        source_rows=[*zqtz_rows, *tyw_rows],
        result_payload=LiabilityYieldMetricsPayload.model_validate(
            _promote_liability_payload(merged, LiabilityYieldMetricsPayload)
        ).model_dump(mode="json"),
    )


def liability_yield_by_period_payload(
    *,
    duckdb_path: str,
    year: int,
    period_type: str,
) -> dict[str, object]:
    """V1-compatible shape: roll up formal PnL-by-business rows by calendar period."""
    normalized_type = str(period_type or "monthly").strip().lower()
    if normalized_type not in {"monthly", "quarterly", "yearly"}:
        normalized_type = "monthly"
    try:
        rows = PnlRepository(duckdb_path).fetch_yearly_business_rows(year)
    except RuntimeError as exc:
        if "unavailable" in str(exc).lower():
            return _envelope(
                result_kind="liability_analytics.yield_by_period",
                source_rows=[],
                quality_flag="warning",
                result_payload={
                    "year": int(year),
                    "period_type": normalized_type,
                    "periods": [],
                },
            )
        raise
    periods = rollup_yield_periods(rows, year=year, period_type=normalized_type)
    source_rows = rows[: min(500, len(rows))]
    return _envelope(
        result_kind="liability_analytics.yield_by_period",
        source_rows=source_rows,
        quality_flag="ok" if periods else "warning",
        result_payload={
            "year": int(year),
            "period_type": normalized_type,
            "periods": periods,
        },
    )


def liability_counterparty_payload(
    *,
    duckdb_path: str,
    report_date: str | None,
    top_n: int,
) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    tyw_rows = repo.fetch_tyw_rows(resolved_date) if resolved_date else []
    if not resolved_date:
        return _envelope(
            result_kind="liability_analytics.counterparty",
            source_rows=[],
            quality_flag="warning",
            result_payload=LiabilityCounterpartyPayload(
                report_date="",
                total_value=0.0,
                top10_share=None,
                hhi=None,
                population_count=0,
                is_truncated=False,
                top_10=[],
                by_type=[],
            ).model_dump(mode="json"),
        )
    payload = compute_liability_counterparty(
        resolved_date,
        tyw_rows,
        top_n=top_n,
    )
    return _envelope(
        result_kind="liability_analytics.counterparty",
        source_rows=tyw_rows,
        result_payload=LiabilityCounterpartyPayload.model_validate(
            _promote_liability_payload(payload, LiabilityCounterpartyPayload)
        ).model_dump(mode="json"),
    )


def liabilities_monthly_payload(*, duckdb_path: str, year: int) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    zqtz_rows = repo.fetch_zqtz_liability_rows_for_year(year)
    tyw_rows = repo.fetch_tyw_liability_rows_for_year(year)
    payload = compute_liabilities_monthly(
        year,
        zqtz_rows,
        tyw_rows,
    )
    return _envelope(
        result_kind="liability_analytics.monthly",
        source_rows=[*zqtz_rows, *tyw_rows],
        quality_flag="warning" if not payload.get("months") else "ok",
        result_payload=LiabilitiesMonthlyPayload.model_validate(
            _promote_liability_payload(payload, LiabilitiesMonthlyPayload)
        ).model_dump(mode="json"),
    )


def cockpit_warnings_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    if not resolved_date:
        return _envelope(
            result_kind="liability_analytics.cockpit_warnings",
            source_rows=[],
            quality_flag="warning",
            result_payload={"report_date": "", "watch_items": [], "alert_events": []},
        )
    zqtz_rows = repo.fetch_zqtz_rows(resolved_date)
    tyw_rows = repo.fetch_tyw_rows(resolved_date)
    payload = compute_cockpit_warnings(resolved_date, zqtz_rows, tyw_rows)
    return _envelope(
        result_kind="liability_analytics.cockpit_warnings",
        source_rows=[*zqtz_rows, *tyw_rows],
        result_payload=payload,
    )


def contribution_split_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    if not resolved_date:
        return _envelope(
            result_kind="liability_analytics.contribution_split",
            source_rows=[],
            quality_flag="warning",
            result_payload={"report_date": "", "contributions": []},
        )
    zqtz_rows = repo.fetch_zqtz_rows(resolved_date)
    tyw_rows = repo.fetch_tyw_rows(resolved_date)
    payload = compute_contribution_split(resolved_date, zqtz_rows, tyw_rows)
    return _envelope(
        result_kind="liability_analytics.contribution_split",
        source_rows=[*zqtz_rows, *tyw_rows],
        result_payload=payload,
    )
