"""Bond analytics service — orchestrates fact reads and delegates finance logic to core_finance."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Literal

from backend.app.core_finance.action_attribution import (
    bond_analytics_action_line_payload,
    build_action_attribution_placeholder_payload,
    build_action_attribution_success_payload,
    compute_action_attribution_bonds,
    select_action_attribution_pnl_report_dates,
)
from backend.app.core_finance.bond_analytics import dv01 as dv01_core
from backend.app.core_finance.bond_analytics.common import (
    STANDARD_SCENARIOS,
    infer_curve_type,
    resolve_period,
    safe_decimal,
)
from backend.app.core_finance.bond_analytics.read_models import (
    build_asset_class_risk_summary,
    build_concentration,
    build_curve_scenarios,
    build_krd_distribution,
    compute_benchmark_excess,
    rating_aa_and_below_portfolio_weight,
    rebucket_return_decomposition,
    summarize_accounting_audit,
    summarize_credit,
    summarize_portfolio_risk,
    summarize_return_decomposition,
    weighted_average_by_market_value,
)
from backend.app.governance.formal_compute_lineage import (
    resolve_formal_dates_lineage,
    resolve_formal_facts_lineage,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings, get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.pnl_repo import PnlRepository

try:
    from backend.app.repositories.yield_curve_repo import (
        FX_LATEST_FALLBACK_PREFIX,
        YIELD_CURVE_LATEST_FALLBACK_PREFIX,
        YieldCurveRepository,
        format_yield_curve_latest_fallback_warning,
    )
except ImportError:
    from backend.app.repositories import yield_curve_repo as _yield_curve_repo

    YieldCurveRepository = _yield_curve_repo.YieldCurveRepository
    FX_LATEST_FALLBACK_PREFIX = getattr(
        _yield_curve_repo,
        "FX_LATEST_FALLBACK_PREFIX",
        "FX_LATEST_FALLBACK",
    )
    YIELD_CURVE_LATEST_FALLBACK_PREFIX = getattr(
        _yield_curve_repo,
        "YIELD_CURVE_LATEST_FALLBACK_PREFIX",
        "YIELD_CURVE_LATEST_FALLBACK",
    )

    def format_yield_curve_latest_fallback_warning(
        *,
        curve_type: str,
        resolved_trade_date: str,
        requested_trade_date: str,
    ) -> str:
        formatter = getattr(_yield_curve_repo, "format_yield_curve_latest_fallback_warning", None)
        if formatter is not None:
            return formatter(
                curve_type=curve_type,
                resolved_trade_date=resolved_trade_date,
                requested_trade_date=requested_trade_date,
            )
        return (
            f"{YIELD_CURVE_LATEST_FALLBACK_PREFIX}: Using latest available {curve_type} curve "
            f"from trade_date={resolved_trade_date} for requested_trade_date={requested_trade_date}."
        )

from backend.app.schemas.analysis_service import AnalysisQuery
from backend.app.schemas.bond_analytics import (
    AccountingClassAuditItem,
    AccountingClassAuditResponse,
    ActionAttributionResponse,
    AssetClassBreakdown,
    AssetClassRiskSummary,
    BenchmarkExcessResponse,
    BondLevelDecomposition,
    BondPositionChangeItem,
    BondPositionChangesResponse,
    BondTopHoldingItem,
    BondTopHoldingsResponse,
    ConcentrationItem,
    ConcentrationMetrics,
    CreditSpreadMigrationResponse,
    DV01ActionBondItem,
    DV01ActionIssuerItem,
    DV01ActionPlanResponse,
    DV01ActionScenarioBreach,
    DV01ActionTenorItem,
    DV01LimitConfigStatusResponse,
    DV01LimitConfigStatusRow,
    DV01MovementAttributionItem,
    DV01MovementBondItem,
    DV01MovementResponse,
    DV01ReconciliationResponse,
    DV01ReconciliationRow,
    DV01RiskResponse,
    DV01ShockScenario,
    DV01TenorBucket,
    DV01TopBondItem,
    DV01TopIssuerItem,
    KRDBucket,
    KRDCurveRiskResponse,
    PortfolioHeadlinesResponse,
    ReturnDecompositionResponse,
    ScenarioResult,
    SpreadScenarioResult,
)
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.services.analysis_adapters import build_bond_action_attribution_placeholder_envelope
from backend.app.services.explicit_numeric import (
    collapse_numeric_json_to_q8_strings,
    numeric_json,
    promote_flat_payload,
)
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
    build_formal_result_envelope_from_lineage,
    build_formal_result_meta,
    build_formal_result_meta_from_lineage,
    build_result_envelope,
)
from backend.app.tasks.bond_analytics_materialize import (
    BOND_ANALYTICS_LOCK,
    CACHE_KEY,
    CACHE_VERSION,
    RULE_VERSION,
    materialize_bond_analytics_facts,
)
from backend.app.tasks.yield_curve_materialize import CACHE_VERSION as YIELD_CURVE_CACHE_VERSION
from backend.app.tasks.yield_curve_materialize import ensure_yield_curve_inputs_on_or_before

logger = logging.getLogger(__name__)

# Backward-compatible module exports used by service tests and legacy route callers.
__all__ = ["STANDARD_SCENARIOS", "build_formal_result_meta"]

JOB_NAME = "bond_analytics_materialize"
EMPTY_SOURCE_VERSION = "sv_bond_analytics_empty"
BOND_ANALYTICS_DATE_BASIS = "bond_analytics_report_date"
BOND_ANALYTICS_FACT_TABLE = "fact_formal_bond_analytics_daily"
EMPTY_WARNING = "DuckDB bond analytics fact table not yet populated — returning empty result"
BOND_ANALYTICS_AMOUNT_CURRENCY_BASIS = "CNY"
BOND_ANALYTICS_AMOUNT_CURRENCY_BASIS_NOTE = (
    "Amount fields in this response, where present, are disclosed on a CNY/RMB basis."
)
BOND_ANALYTICS_FOREIGN_CURRENCY_FALLBACK_WARNING = (
    "Foreign-currency bond positions are disclosed on a CNY/RMB basis where formal CNY closure is available. "
    "The current API model does not expose row-level fallback markers; if upstream formal CNY closure is missing "
    "for some positions, derived amount fields may fall back to native currency values."
)
DV01_UNMAPPED_ACCOUNTING_CLASS_WARNING_PREFIX = (
    "DV01 全部口径包含未映射会计分类"
)
RETURN_TRADING_GAP_WARNING = (
    "Trading PnL remains a Phase 3 placeholder (0); transaction-level trade inputs are not integrated."
)
RETURN_TRADING_GAP_WARNING_DETAIL = {
    "code": "return_decomposition_trading_placeholder_phase3",
    "level": "warning",
    "component": "trading",
    "detail": "transaction_level_trade_inputs_not_integrated",
}
RETURN_TRADING_PNL517_FROM_FORMAL_DETAIL = {
    "code": "return_decomposition_trading_pnl517_formal",
    "level": "info",
    "message": "trading_component_sourced_from_merged_formal_fi_and_nonstd_bridge_capital_gain_517_position_match",
}
RETURN_TRADING_PNL517_PARTIAL_DETAIL = {
    "code": "return_decomposition_trading_pnl517_partial_coverage",
    "level": "warning",
    "message": "some_positions_have_no_matching_pnl517_row_same_instrument_book",
}
RETURN_TRADING_PNL517_PERIOD_DETAIL = {
    "code": "return_decomposition_trading_pnl517_multi_month_aggregate",
    "level": "warning",
    "message": "capital_gain_517_summed_across_multiple_report_dates_interpret_with_caution",
}
RETURN_TRADING_PNL517_NO_PERIOD_DATES_DETAIL = {
    "code": "return_decomposition_trading_pnl517_no_fact_dates_in_period",
    "level": "warning",
    "detail": "union_formal_nonstd_report_dates_empty_for_period_bounds",
}
BENCHMARK_EXCESS_RECON_GAP = (
    "Benchmark excess reconciliation gap (recon_error) is material; verify curve inputs and portfolio snapshot."
)
BENCHMARK_EXCESS_EXPLAINED_MISMATCH = (
    "Benchmark excess Brinson components do not sum to explained_excess (internal consistency check failed)."
)
BENCHMARK_WARNING = "Benchmark index data not yet available; benchmark-side fields remain zero"
BENCHMARK_EXCESS_SPREAD_GAP_WARNING = (
    "Benchmark excess spread_effect is 0 because treasury/aaa_credit snapshots are missing for one or both "
    "period dates; do not treat this component as an informed credit-spread attribution."
)
SPREAD_WARNING = "Spread level input unavailable; weighted_avg_spread remains 0 (curves or inputs incomplete)"
Q8 = Decimal("0.00000001")
ZERO = Decimal("0")
BENCHMARK_NAMES = {
    "TREASURY_INDEX": "中债国债总指数",
    "CDB_INDEX": "中债国开债总指数",
    "AAA_CREDIT_INDEX": "中债AAA信用债指数",
}
PENDING_SOURCE_VERSION = "sv_bond_analytics_pending"
BENCHMARK_CURVE_TYPES = {
    "TREASURY_INDEX": "treasury",
    "CDB_INDEX": "cdb",
    "AAA_CREDIT_INDEX": "aaa_credit",
}
IN_FLIGHT_STATUSES = {"queued", "running"}
STALE_IN_FLIGHT_AFTER = timedelta(hours=1)


class _TTLCache:
    """Thread-safe TTL cache keyed by arbitrary hashable args."""

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[tuple, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def get(self, key: tuple) -> tuple[bool, Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry and time.monotonic() - entry[0] < self._ttl:
                return True, entry[1]
            return False, None

    def set(self, key: tuple, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.monotonic(), value)

    def invalidate(self, key: tuple) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def invalidate_matching(self, predicate) -> None:
        with self._lock:
            for key in list(self._store):
                if predicate(key):
                    self._store.pop(key, None)


_return_decomposition_cache = _TTLCache(ttl_seconds=300)
_benchmark_excess_cache = _TTLCache(ttl_seconds=300)
_action_attribution_cache = _TTLCache(ttl_seconds=300)


def _invalidate_bond_analytics_caches_for_report_date(report_date: object) -> None:
    report_date_text = str(report_date or "").strip()
    if not report_date_text:
        return
    _return_decomposition_cache.invalidate_matching(
        lambda key: len(key) >= 1 and key[0] == report_date_text
    )
    _benchmark_excess_cache.invalidate_matching(
        lambda key: len(key) >= 1 and key[0] == report_date_text
    )
    _action_attribution_cache.invalidate_matching(
        lambda key: len(key) >= 1 and key[0] == report_date_text
    )


def _duckdb_cache_version_token() -> tuple[str, int | None]:
    duckdb_path = str(get_settings().duckdb_path)
    try:
        return duckdb_path, Path(duckdb_path).stat().st_mtime_ns
    except OSError:
        return duckdb_path, None


def _benchmark_excess_brinson_sum_matches_explained(summary: dict[str, object]) -> bool:
    s = (
        safe_decimal(summary["duration_effect"])
        + safe_decimal(summary["curve_effect"])
        + safe_decimal(summary["spread_effect"])
        + safe_decimal(summary["selection_effect"])
        + safe_decimal(summary["allocation_effect"])
    )
    return abs(s - safe_decimal(summary["explained_excess"])) <= Decimal("0.0001")


class BondAnalyticsRefreshServiceError(RuntimeError):
    pass


class BondAnalyticsRefreshConflictError(RuntimeError):
    pass


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _text(value: Decimal) -> str:
    return format(value.quantize(Q8, rounding=ROUND_HALF_UP), "f")


def _bond_analytics_api_payload(payload: dict[str, object]) -> dict[str, object]:
    """Bond analytics formal endpoints expose legacy Q8 strings, not governed Numeric JSON dicts."""
    out = collapse_numeric_json_to_q8_strings(payload)
    scenarios = out.get("spread_scenarios")
    if isinstance(scenarios, list):
        for row in scenarios:
            if not isinstance(row, dict):
                continue
            sc = row.get("spread_change_bp")
            if isinstance(sc, str):
                row["spread_change_bp"] = float(Decimal(sc))
    return out


def _model_payloads(rows: list[dict[str, object]], model_cls: type) -> list:
    return [model_cls.model_validate(promote_flat_payload(row, model_cls)) for row in rows]


def _repo() -> BondAnalyticsRepository:
    return BondAnalyticsRepository(str(get_settings().duckdb_path))


def _pnl_position_key_from_bond_row(row: dict[str, object]) -> str:
    inst = str(row.get("instrument_code") or "").strip()
    pn = str(row.get("portfolio_name") or "").strip()
    cc = str(row.get("cost_center") or "").strip()
    return f"{inst}::{pn}::{cc}"


def _resolve_prior_bond_snapshot_date(repo: BondAnalyticsRepository, period_end: str) -> str | None:
    prior_dates = [d for d in repo.list_report_dates() if d < period_end]
    return max(prior_dates) if prior_dates else None


def _pnl_report_dates_for_action_attribution(
    pnl_repo: PnlRepository,
    *,
    period_type: str,
    period_start: date,
    period_end: date,
) -> tuple[list[str], list[str]]:
    available_report_dates = [] if period_type == "MoM" else pnl_repo.list_union_report_dates()
    return select_action_attribution_pnl_report_dates(
        available_report_dates=available_report_dates,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
    )


def _build_action_attribution_pnl_by_key(
    pnl_repo: PnlRepository,
    *,
    period_type: str,
    period_start: date,
    period_end: date,
) -> tuple[dict[str, Decimal], list[str]]:
    dates, extra = _pnl_report_dates_for_action_attribution(
        pnl_repo,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
    )
    if not dates:
        return {}, extra + ["ACTION_ATTRIBUTION_PNL517_NO_FACT_DATES"]
    merged = pnl_repo.merged_capital_gain_517_by_position_for_dates(dates)
    if not merged:
        extra.append("ACTION_ATTRIBUTION_PNL517_EMPTY_MERGE")
    return merged, extra


def _overlay_return_decomposition_trading_pnl517(
    summary: dict[str, object],
    *,
    period_type: str,
    period_start: date,
    period_end: date,
    duckdb_path: str,
) -> tuple[dict[str, object], list[str], list[dict[str, str]]]:
    """Attach ``capital_gain_517`` from formal+nonstd PnL facts to each bond row; re-bucket by class.

    MoM uses the period-end report date only. YTD/TTM sum ``capital_gain_517`` over every union
    (formal FI + nonstd bridge) ``report_date`` in ``[period_start, period_end]``. If none exist,
    trading stays at 0 with structured ``warnings_detail`` (no fabricated 517).
    """
    extra_warnings: list[str] = []
    details: list[dict[str, str]] = []
    pnl_repo = PnlRepository(duckdb_path)
    dates, _ = _pnl_report_dates_for_action_attribution(
        pnl_repo,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
    )
    if not dates:
        extra_warnings.append(
            "No formal/nonstd PnL report dates fall within period_start–period_end; "
            "capital_gain_517 trading overlay skipped."
        )
        details.extend(
            [
                dict(RETURN_TRADING_PNL517_NO_PERIOD_DATES_DETAIL),
                dict(RETURN_TRADING_GAP_WARNING_DETAIL),
            ]
        )
        return summary, extra_warnings, details

    multi_month = len(dates) > 1
    pnl_map = pnl_repo.merged_capital_gain_517_by_position_for_dates(dates)
    bond_rows = list(summary.get("bond_details") or [])
    matched_mv = ZERO
    total_mv = ZERO
    for row in bond_rows:
        if not isinstance(row, dict):
            continue
        key = _pnl_position_key_from_bond_row(row)
        econ = safe_decimal(row.get("total"))
        tv = pnl_map.get(key, ZERO)
        mv = safe_decimal(row.get("market_value"))
        total_mv += mv
        if tv != ZERO:
            matched_mv += mv
        row["trading"] = tv
        row["total"] = econ + tv

    summary["bond_details"] = bond_rows
    summary["trading_total"] = sum((safe_decimal(r.get("trading")) for r in bond_rows if isinstance(r, dict)), ZERO)
    matched_coverage_pct = float(matched_mv / total_mv * 100) if total_mv > ZERO else 0.0
    summary["matched_coverage_pct"] = round(matched_coverage_pct, 2)
    try:
        by_ac, by_acc = rebucket_return_decomposition(bond_rows)
        summary["by_asset_class"] = by_ac
        summary["by_accounting_class"] = by_acc
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        logger.exception(
            "rebucket_return_decomposition failed after trading overlay; "
            "by_asset_class / by_accounting_class unchanged: %s",
            exc,
        )

    if not pnl_map:
        extra_warnings.append(
            "No capital_gain_517 rows in formal/nonstd PnL tables for the selected report date(s); trading remains 0."
        )
        details.append(dict(RETURN_TRADING_GAP_WARNING_DETAIL))
        if multi_month:
            details.append({k: str(v) for k, v in RETURN_TRADING_PNL517_PERIOD_DETAIL.items()})
        return summary, extra_warnings, details

    details.append({k: str(v) for k, v in RETURN_TRADING_PNL517_FROM_FORMAL_DETAIL.items()})
    if multi_month:
        details.append({k: str(v) for k, v in RETURN_TRADING_PNL517_PERIOD_DETAIL.items()})
    if total_mv > ZERO and matched_mv < total_mv - Q8:
        extra_warnings.append(
            "capital_gain_517 matched for a subset of positions (instrument+book); others show trading 0."
        )
        details.append({k: str(v) for k, v in RETURN_TRADING_PNL517_PARTIAL_DETAIL.items()})
        if matched_coverage_pct < 80.0:
            details.append({
                "code": "return_decomposition_trading_pnl517_low_coverage",
                "level": "warning",
                "message": f"matched_coverage_pct={matched_coverage_pct:.1f}%_below_80pct_threshold",
            })
    return summary, extra_warnings, details


def _lineage(report_date: str, rows: list[dict[str, object]]) -> dict[str, str]:
    return resolve_formal_facts_lineage(
        governance_dir=str(get_settings().governance_path),
        cache_key=CACHE_KEY,
        job_name=JOB_NAME,
        report_date=report_date,
        has_rows=bool(rows),
        row_source_versions=[
            str(row.get("source_version") or "").strip()
            for row in rows
        ],
        default_source_version=EMPTY_SOURCE_VERSION,
        default_rule_version=RULE_VERSION,
        default_cache_version=CACHE_VERSION,
    )


def _first_lineage_value(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def _latest_governance_row(
    rows: list[dict[str, object]],
    *,
    cache_key: str,
    job_name: str | None = None,
    report_date: str | None = None,
    completed_only: bool = False,
) -> dict[str, object]:
    for row in reversed(rows):
        if str(row.get("cache_key") or "").strip() != cache_key:
            continue
        if job_name is not None and str(row.get("job_name") or "").strip() != job_name:
            continue
        if report_date is not None and str(row.get("report_date") or "").strip() != report_date:
            continue
        if completed_only and str(row.get("status") or "").strip() != "completed":
            continue
        return row
    return {}


def _lineage_from_governance_rows(
    *,
    report_date: str,
    rows: list[dict[str, object]],
    build_rows: list[dict[str, object]],
    manifest_rows: list[dict[str, object]],
) -> dict[str, str]:
    latest_build = _latest_governance_row(
        build_rows,
        cache_key=CACHE_KEY,
        job_name=JOB_NAME,
        report_date=report_date,
        completed_only=True,
    )
    row_sources = sorted(
        {
            str(row.get("source_version") or "").strip()
            for row in rows
            if str(row.get("source_version") or "").strip()
        }
    )
    if not rows and not latest_build:
        return {
            "source_version": EMPTY_SOURCE_VERSION,
            "rule_version": RULE_VERSION,
            "cache_version": CACHE_VERSION,
            "vendor_version": "vv_none",
        }
    latest_manifest = _latest_governance_row(manifest_rows, cache_key=CACHE_KEY)
    return {
        "source_version": _first_lineage_value(
            str(latest_build.get("source_version") or "").strip(),
            "__".join(row_sources),
            EMPTY_SOURCE_VERSION,
        ),
        "rule_version": _first_lineage_value(
            str(latest_build.get("rule_version") or "").strip(),
            str(latest_manifest.get("rule_version") or "").strip(),
            RULE_VERSION,
        ),
        "cache_version": _first_lineage_value(
            str(latest_build.get("cache_version") or "").strip(),
            str(latest_manifest.get("cache_version") or "").strip(),
            CACHE_VERSION,
        ),
        "vendor_version": _first_lineage_value(
            str(latest_build.get("vendor_version") or "").strip(),
            str(latest_manifest.get("vendor_version") or "").strip(),
            "vv_none",
        ),
    }


def _meta_from_lineage(result_kind: str, lineage: dict[str, str]):
    return build_formal_result_meta_from_lineage(
        trace_id=_trace_id(),
        result_kind=result_kind,
        lineage=lineage,
        default_cache_version=CACHE_VERSION,
        source_surface="bond_analytics",
    )


def _meta(result_kind: str, report_date: date, rows: list[dict[str, object]]):
    lineage = _lineage(report_date.isoformat(), rows)
    return _meta_from_lineage(result_kind, lineage)


def _is_cny_currency(currency_code: object) -> bool:
    return str(currency_code or "").strip().upper() in {"", "CNY", "CNX", "RMB"}


def _foreign_currency_codes(rows: list[dict[str, object]]) -> list[str]:
    return sorted(
        {
            str(row.get("currency_code") or "").strip().upper()
            for row in rows
            if not _is_cny_currency(row.get("currency_code"))
        }
    )


def _with_bond_amount_disclosure(
    envelope: dict[str, object],
    *,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    result_meta = envelope.get("result_meta")
    if isinstance(result_meta, dict):
        result_meta["amount_currency_basis"] = BOND_ANALYTICS_AMOUNT_CURRENCY_BASIS
        result_meta["amount_currency_basis_note"] = BOND_ANALYTICS_AMOUNT_CURRENCY_BASIS_NOTE

    result_payload = envelope.get("result")
    if not isinstance(result_payload, dict):
        return envelope

    warnings = result_payload.get("warnings")
    if not isinstance(warnings, list):
        return envelope

    foreign_codes = _foreign_currency_codes(rows)
    if not foreign_codes:
        return envelope

    warning = (
        f"{BOND_ANALYTICS_FOREIGN_CURRENCY_FALLBACK_WARNING} "
        f"Detected foreign currencies: {', '.join(foreign_codes)}."
    )
    result_payload["warnings"] = _ordered_unique_warnings([*warnings, warning])
    return envelope


def _build_fact_envelope(
    *,
    result_kind: str,
    report_date: date,
    rows: list[dict[str, object]],
    result_payload: dict[str, object],
) -> dict[str, object]:
    return _with_bond_amount_disclosure(
        build_formal_result_envelope_from_lineage(
            trace_id=_trace_id(),
            result_kind=result_kind,
            lineage=_lineage(report_date.isoformat(), rows),
            default_cache_version=CACHE_VERSION,
            source_surface="bond_analytics",
            result_payload=_bond_analytics_api_payload(result_payload),
        ),
        rows=rows,
    )


def _build_numeric_fact_envelope(
    *,
    result_kind: str,
    report_date: date,
    rows: list[dict[str, object]],
    result_payload: dict[str, object],
) -> dict[str, object]:
    return _with_bond_amount_disclosure(
        build_formal_result_envelope_from_lineage(
            trace_id=_trace_id(),
            result_kind=result_kind,
            lineage=_lineage(report_date.isoformat(), rows),
            default_cache_version=CACHE_VERSION,
            source_surface="bond_analytics",
            result_payload=result_payload,
        ),
        rows=rows,
    )


def _action_attribution_candidate_meta(*, formal_meta, report_date: date, quality_flag: str | None = None):
    report_date_text = report_date.isoformat()
    return build_analytical_result_meta(
        trace_id=formal_meta.trace_id,
        result_kind=formal_meta.result_kind,
        cache_version=formal_meta.cache_version,
        source_version=formal_meta.source_version,
        rule_version=formal_meta.rule_version,
        quality_flag=quality_flag or formal_meta.quality_flag or "warning",
        vendor_version=formal_meta.vendor_version,
        vendor_status=formal_meta.vendor_status,
        fallback_mode=formal_meta.fallback_mode,
        requested_report_date=report_date_text,
        resolved_report_date=report_date_text,
        as_of_date=report_date_text,
        date_basis=BOND_ANALYTICS_DATE_BASIS,
        filters_applied={"report_date": report_date_text},
        tables_used=[BOND_ANALYTICS_FACT_TABLE],
        evidence_rows=formal_meta.evidence_rows,
        source_surface="bond_analytics",
        generated_at=formal_meta.generated_at,
    )


def _credit_spread_candidate_meta(
    *,
    formal_meta,
    report_date: date,
    spread_scenarios: str,
    rows: list[dict[str, object]],
):
    report_date_text = report_date.isoformat()
    return build_analytical_result_meta(
        trace_id=formal_meta.trace_id,
        result_kind=formal_meta.result_kind,
        cache_version=formal_meta.cache_version,
        source_version=formal_meta.source_version,
        rule_version=formal_meta.rule_version,
        quality_flag=formal_meta.quality_flag if formal_meta.quality_flag in {"error", "stale"} else "warning",
        vendor_version=formal_meta.vendor_version,
        vendor_status=formal_meta.vendor_status,
        fallback_mode=formal_meta.fallback_mode,
        requested_report_date=report_date_text,
        resolved_report_date=report_date_text,
        as_of_date=report_date_text,
        date_basis=BOND_ANALYTICS_DATE_BASIS,
        filters_applied={"report_date": report_date_text, "spread_scenarios": spread_scenarios},
        tables_used=[BOND_ANALYTICS_FACT_TABLE],
        evidence_rows=len(rows),
        source_surface="bond_analytics",
    )


def bond_analytics_dates_envelope() -> dict[str, object]:
    report_dates = _repo().list_report_dates()
    lineage = resolve_formal_dates_lineage(
        governance_dir=str(get_settings().governance_path),
        cache_key=CACHE_KEY,
        report_dates=report_dates,
        default_source_version=EMPTY_SOURCE_VERSION,
        default_rule_version=RULE_VERSION,
        default_cache_version=CACHE_VERSION,
        fallback_lineage_loader=lambda report_date: _lineage(
            report_date,
            _repo().fetch_bond_analytics_rows(report_date=report_date),
        ),
    )
    return build_formal_result_envelope_from_lineage(
        trace_id=_trace_id(),
        result_kind="bond_analytics.dates",
        lineage=lineage,
        default_cache_version=CACHE_VERSION,
        source_surface="bond_analytics",
        result_payload={"report_dates": report_dates},
    )


def _merge_lineage_values(*values: str) -> str:
    merged = sorted({value.strip() for value in values if value and value.strip()})
    return "__".join(merged)


def refresh_bond_analytics(
    settings: Settings,
    *,
    report_date: str,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    try:
        with acquire_lock(
            _refresh_trigger_lock(report_date=report_date),
            base_dir=settings.governance_path,
            timeout_seconds=0.1,
        ):
            if normalized_idempotency_key is not None:
                existing_idempotent_run = _latest_refresh_for_idempotency_key(
                    settings,
                    report_date=report_date,
                    idempotency_key=normalized_idempotency_key,
                )
                if existing_idempotent_run is not None:
                    return _idempotent_refresh_response(existing_idempotent_run)

            existing = _latest_inflight_refresh(settings, report_date=report_date)
            if existing is not None:
                raise BondAnalyticsRefreshConflictError(
                    f"Bond analytics refresh already in progress for report_date={report_date}."
                )

            try:
                _prepare_yield_curve_inputs_for_refresh(settings=settings, report_date=report_date)
            except Exception as exc:
                raise BondAnalyticsRefreshServiceError(
                    f"Bond analytics refresh could not prepare yield curve inputs for report_date={report_date}."
                ) from exc

            run_id = _build_run_id()
            queued_at = datetime.now(UTC).isoformat()
            GovernanceRepository(base_dir=settings.governance_path).append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **CacheBuildRunRecord(
                        run_id=run_id,
                        job_name=JOB_NAME,
                        status="queued",
                        cache_key=CACHE_KEY,
                        cache_version=CACHE_VERSION,
                        lock=BOND_ANALYTICS_LOCK.key,
                        source_version=PENDING_SOURCE_VERSION,
                        vendor_version="vv_none",
                    ).model_dump(),
                    "report_date": report_date,
                    "queued_at": queued_at,
                    "idempotency_key": normalized_idempotency_key,
                },
            )
            try:
                materialize_bond_analytics_facts.send(
                    report_date=report_date,
                    duckdb_path=str(settings.duckdb_path),
                    governance_dir=str(settings.governance_path),
                    run_id=run_id,
                )
            except Exception as exc:
                _record_dispatch_failure(
                    settings=settings,
                    run_id=run_id,
                    report_date=report_date,
                    error_message="Bond analytics refresh queue dispatch failed.",
                )
                raise BondAnalyticsRefreshServiceError(
                    "Bond analytics refresh queue dispatch failed."
                ) from exc

            return {
                "status": "queued",
                "run_id": run_id,
                "job_name": JOB_NAME,
                "trigger_mode": "async",
                "cache_key": CACHE_KEY,
                "report_date": report_date,
                "idempotency_key": normalized_idempotency_key,
                "idempotency_replay": False,
            }
    except TimeoutError as exc:
        raise BondAnalyticsRefreshConflictError(
            f"Bond analytics refresh already in progress for report_date={report_date}."
        ) from exc


def _prepare_yield_curve_inputs_for_refresh(*, settings: Settings, report_date: str) -> None:
    ensure_yield_curve_inputs_on_or_before(
        anchor_dates=_yield_curve_anchor_dates_for_refresh(
            duckdb_path=str(settings.duckdb_path),
            report_date=report_date,
        ),
        duckdb_path=str(settings.duckdb_path),
    )


def _yield_curve_anchor_dates_for_refresh(*, duckdb_path: str, report_date: str) -> tuple[str, ...]:
    report_dt = date.fromisoformat(report_date)
    anchors = {
        report_dt.isoformat(),
        report_dt.replace(day=1).isoformat(),
    }
    prior_balance_date = BondAnalyticsRepository(duckdb_path).resolve_prior_curve_anchor_report_date(
        report_date=report_date,
    )
    if prior_balance_date:
        anchors.add(prior_balance_date)
    return tuple(sorted(anchors))


def bond_analytics_refresh_status(settings: Settings, *, run_id: str) -> dict[str, object]:
    records = [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key")) == CACHE_KEY
        and str(record.get("job_name")) == JOB_NAME
        and str(record.get("run_id")) == run_id
    ]
    if not records:
        raise ValueError(f"Unknown bond analytics refresh run_id={run_id}")
    latest = records[-1]
    status = str(latest.get("status", "unknown"))
    if status == "completed":
        _invalidate_bond_analytics_caches_for_report_date(latest.get("report_date"))
    return {
        **latest,
        "trigger_mode": "async" if status in IN_FLIGHT_STATUSES else "terminal",
    }


def _empty_return_response(meta, report_date: date, period_type: str, period_start: date, period_end: date) -> dict:
    payload = ReturnDecompositionResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "period_type": period_type,
                "period_start": period_start,
                "period_end": period_end,
                "carry": ZERO,
                "roll_down": ZERO,
                "rate_effect": ZERO,
                "spread_effect": ZERO,
                "trading": ZERO,
                "explained_pnl": ZERO,
                "actual_pnl": ZERO,
                "recon_error": ZERO,
                "recon_error_pct": ZERO,
                "computed_at": meta.generated_at.isoformat(),
                "warnings": [EMPTY_WARNING],
                "warnings_detail": [],
            },
            ReturnDecompositionResponse,
        )
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope(
            result_meta=meta, result_payload=_bond_analytics_api_payload(payload.model_dump(mode="json"))
        ),
        rows=[],
    )


def _fetch_fx_rates(
    curve_repo: YieldCurveRepository,
    *,
    current_date: str,
    prior_date: str,
) -> tuple[
    dict[str, Decimal] | None,
    str | None,
    dict[str, Decimal] | None,
    str | None,
]:
    """Fetch FX rates for both period dates in one place. Returns (current, current_warning, prior, prior_warning)."""
    fx_current, fx_current_warning = curve_repo.fetch_fx_rates_with_fallback_warning(current_date)
    fx_prior, fx_prior_warning = curve_repo.fetch_fx_rates_with_fallback_warning(prior_date)
    return fx_current or None, fx_current_warning, fx_prior or None, fx_prior_warning


def _fetch_all_curve_pairs(
    rows: list[dict[str, object]],
    *,
    curve_repo: YieldCurveRepository,
    report_date: str,
    prior_date: str,
    extra_curve_types: set[str] | None = None,
) -> dict[str, object]:
    """Resolve treasury/cdb/aaa_credit current+prior snapshots for the given rows.

    Returns a dict with keys:
      treasury_current, treasury_prior, treasury_current_warning, treasury_prior_warning,
      cdb_current, cdb_prior, cdb_current_warning, cdb_prior_warning,
      aaa_current, aaa_prior, aaa_current_warning, aaa_prior_warning,
      curve_snapshots, curve_latest_fallback, curve_unavailable
    """
    required = _required_curve_types_for_return_rows(rows)
    if extra_curve_types:
        required = required | extra_curve_types

    treasury_current, treasury_current_warning = _resolve_curve_pair_if_needed(
        curve_type="treasury", required_curve_types=required, repo=curve_repo,
        report_date=report_date, prior_date=prior_date,
    )
    cdb_current, cdb_current_warning = _resolve_curve_pair_if_needed(
        curve_type="cdb", required_curve_types=required, repo=curve_repo,
        report_date=report_date, prior_date=prior_date,
    )
    aaa_current, aaa_current_warning = _resolve_curve_pair_if_needed(
        curve_type="aaa_credit", required_curve_types=required, repo=curve_repo,
        report_date=report_date, prior_date=prior_date,
    )

    treasury_prior = treasury_current.get("_prior_snapshot") if treasury_current else None
    cdb_prior = cdb_current.get("_prior_snapshot") if cdb_current else None
    aaa_prior = aaa_current.get("_prior_snapshot") if aaa_current else None
    treasury_prior_warning = treasury_current.get("_prior_warning") if treasury_current else None
    cdb_prior_warning = cdb_current.get("_prior_warning") if cdb_current else None
    aaa_prior_warning = aaa_current.get("_prior_warning") if aaa_current else None

    curve_snapshots = [
        s for s in (treasury_current, treasury_prior, cdb_current, cdb_prior, aaa_current, aaa_prior)
        if s is not None
    ]
    relevant_warnings = _curve_warnings_for_return_rows(
        rows,
        treasury_current_warning=treasury_current_warning,
        treasury_prior_warning=treasury_prior_warning,
        cdb_current_warning=cdb_current_warning,
        cdb_prior_warning=cdb_prior_warning,
        aaa_current_warning=aaa_current_warning,
        aaa_prior_warning=aaa_prior_warning,
    )
    return {
        "treasury_current": treasury_current,
        "treasury_prior": treasury_prior,
        "treasury_current_warning": treasury_current_warning,
        "treasury_prior_warning": treasury_prior_warning,
        "cdb_current": cdb_current,
        "cdb_prior": cdb_prior,
        "cdb_current_warning": cdb_current_warning,
        "cdb_prior_warning": cdb_prior_warning,
        "aaa_current": aaa_current,
        "aaa_prior": aaa_prior,
        "aaa_current_warning": aaa_current_warning,
        "aaa_prior_warning": aaa_prior_warning,
        "curve_snapshots": curve_snapshots,
        "relevant_curve_warnings": relevant_warnings,
        "curve_latest_fallback": any(
            w and YIELD_CURVE_LATEST_FALLBACK_PREFIX in w for w in relevant_warnings
        ),
        "curve_unavailable": any(w and w.startswith("No ") for w in relevant_warnings),
    }


def _build_asset_class_breakdown(row: dict[str, object]) -> AssetClassBreakdown:
    return AssetClassBreakdown.model_validate(
        promote_flat_payload(
            {
                "asset_class": row["key"],
                "carry": row["carry"],
                "roll_down": row["roll_down"],
                "rate_effect": row["rate_effect"],
                "spread_effect": row["spread_effect"],
                "convexity_effect": row.get("convexity_effect", ZERO),
                "trading": row.get("trading", ZERO),
                "total": row["total"],
                "bond_count": int(row["bond_count"]),
                "market_value": row["market_value"],
            },
            AssetClassBreakdown,
        )
    )


def _build_bond_level_decomposition(row: dict[str, object]) -> BondLevelDecomposition:
    trading = row.get("trading", ZERO)
    return BondLevelDecomposition.model_validate(
        promote_flat_payload(
            {
                "bond_code": str(row["instrument_code"]),
                "bond_name": str(row.get("instrument_name") or ""),
                "asset_class": str(row["asset_class_std"]),
                "accounting_class": str(row["accounting_class"]),
                "market_value": row["market_value"],
                "carry": row["carry"],
                "roll_down": row["roll_down"],
                "rate_effect": row["rate_effect"],
                "spread_effect": row["spread_effect"],
                "convexity_effect": row.get("convexity_effect", ZERO),
                "trading": trading,
                "total": row["total"],
                "explained_for_recon": row["total"],
                "economic_only_effects": (
                    row["roll_down"]
                    + row["rate_effect"]
                    + row["spread_effect"]
                    + row.get("convexity_effect", ZERO)
                    + row.get("fx_effect", ZERO)
                ),
            },
            BondLevelDecomposition,
        )
    )


def _build_return_decomposition_payload(
    *,
    report_date: date,
    period_type: str,
    period_start: date,
    period_end: date,
    summary: dict[str, object],
    meta,
    relevant_curve_warnings: list,
    fx_current_warning: str | None,
    fx_prior_warning: str | None,
    fx_missing_warnings: list[str],
    trading_extra_warnings: list[str] | None = None,
    warnings_detail: list[dict[str, str]] | None = None,
) -> ReturnDecompositionResponse:
    trading_total = safe_decimal(summary.get("trading_total", ZERO))
    explained_total = (
        summary["carry_total"]
        + summary["roll_down_total"]
        + summary["rate_effect_total"]
        + summary["spread_effect_total"]
        + summary["convexity_effect_total"]
        + summary.get("fx_effect_total", ZERO)
        + trading_total
    )
    trading_warn_head: list[str | None] = []
    if trading_total == ZERO:
        trading_warn_head.append(RETURN_TRADING_GAP_WARNING)
    detail_payload = (
        warnings_detail if warnings_detail is not None else [dict(RETURN_TRADING_GAP_WARNING_DETAIL)]
    )
    return ReturnDecompositionResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "period_type": period_type,
                "period_start": period_start,
                "period_end": period_end,
                "carry": summary["carry_total"],
                "roll_down": summary["roll_down_total"],
                "rate_effect": summary["rate_effect_total"],
                "spread_effect": summary["spread_effect_total"],
                "trading": trading_total,
                "fx_effect": summary.get("fx_effect_total", ZERO),
                "convexity_effect": summary.get("convexity_effect_total", ZERO),
                "explained_pnl": explained_total,
                "explained_pnl_accounting": explained_total,
                "explained_pnl_economic": explained_total,
                "oci_reserve_impact": ZERO,
                "actual_pnl": explained_total,
                "recon_error": ZERO,
                "recon_error_pct": ZERO,
                "by_asset_class": [_build_asset_class_breakdown(row) for row in summary["by_asset_class"]],
                "by_accounting_class": [_build_asset_class_breakdown(row) for row in summary["by_accounting_class"]],
                "bond_details": [_build_bond_level_decomposition(row) for row in summary["bond_details"]],
                "bond_count": int(summary["bond_count"]),
                "total_market_value": summary["total_market_value"],
                "computed_at": meta.generated_at.isoformat(),
                "warnings": _ordered_unique_warnings(
                    [
                        *(trading_extra_warnings or []),
                        *trading_warn_head,
                        *relevant_curve_warnings,
                        fx_current_warning,
                        fx_prior_warning,
                        *fx_missing_warnings,
                    ]
                ),
                "warnings_detail": detail_payload,
            },
            ReturnDecompositionResponse,
        )
    )


def _fetch_return_decomposition_inputs(
    *,
    rows: list[dict[str, object]],
    curve_repo: YieldCurveRepository,
    report_date: str,
    period_start: str,
) -> dict[str, object]:
    """Fetch FX rates and curves for return decomposition."""
    fx_rates_current, fx_current_warning, fx_rates_prior, fx_prior_warning = _fetch_fx_rates(
        curve_repo, current_date=report_date, prior_date=period_start
    )
    curves = _fetch_all_curve_pairs(
        rows, curve_repo=curve_repo, report_date=report_date, prior_date=period_start,
    )
    fx_unavailable = _fx_unavailable_for_return_rows(rows, fx_rates_current=fx_rates_current, fx_rates_prior=fx_rates_prior)
    fx_latest_fallback = any(
        w and FX_LATEST_FALLBACK_PREFIX in w for w in (fx_current_warning, fx_prior_warning)
    )
    fx_missing_warnings = _fx_missing_warnings_for_return_rows(
        rows, report_date=report_date, prior_date=period_start,
        fx_rates_current=fx_rates_current, fx_rates_prior=fx_rates_prior,
    )
    return {
        "fx_rates_current": fx_rates_current,
        "fx_current_warning": fx_current_warning,
        "fx_rates_prior": fx_rates_prior,
        "fx_prior_warning": fx_prior_warning,
        "fx_unavailable": fx_unavailable,
        "fx_latest_fallback": fx_latest_fallback,
        "fx_missing_warnings": fx_missing_warnings,
        **curves,
    }


def _compute_return_decomposition_summary(
    *,
    rows: list[dict[str, object]],
    period_start: date,
    period_end: date,
    period_type: str,
    inputs: dict[str, object],
    duckdb_path: str,
) -> tuple[dict[str, object], list[str], list[dict[str, str]]]:
    """Compute return decomposition summary with trading overlay."""
    treasury_current = inputs["treasury_current"]
    treasury_prior = inputs["treasury_prior"]
    cdb_current = inputs["cdb_current"]
    cdb_prior = inputs["cdb_prior"]
    aaa_current = inputs["aaa_current"]
    aaa_prior = inputs["aaa_prior"]

    summary = summarize_return_decomposition(
        rows,
        period_start=period_start,
        period_end=period_end,
        treasury_curve_current=treasury_current["curve"] if treasury_current else None,
        treasury_curve_prior=treasury_prior["curve"] if treasury_prior else None,
        cdb_curve_current=cdb_current["curve"] if cdb_current else None,
        cdb_curve_prior=cdb_prior["curve"] if cdb_prior else None,
        aaa_credit_curve_current=aaa_current["curve"] if aaa_current else None,
        aaa_credit_curve_prior=aaa_prior["curve"] if aaa_prior else None,
        fx_rates_current=inputs["fx_rates_current"],
        fx_rates_prior=inputs["fx_rates_prior"],
    )
    return _overlay_return_decomposition_trading_pnl517(
        summary,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        duckdb_path=duckdb_path,
    )


def get_return_decomposition(report_date: date, period_type: str = "MoM", asset_class: str = "all", accounting_class: str = "all") -> dict:
    _cache_key = (report_date.isoformat(), period_type, asset_class, accounting_class)
    hit, cached = _return_decomposition_cache.get(_cache_key)
    if hit:
        return cached

    period_start, period_end = resolve_period(report_date, period_type)
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat(), asset_class=asset_class, accounting_class=accounting_class)
    if not rows:
        meta = _meta("bond_analytics.return_decomposition", report_date, rows)
        result = _empty_return_response(meta, report_date, period_type, period_start, period_end)
        _return_decomposition_cache.set(_cache_key, result)
        return result

    curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
    inputs = _fetch_return_decomposition_inputs(
        rows=rows, curve_repo=curve_repo,
        report_date=report_date.isoformat(), period_start=period_start.isoformat(),
    )

    meta = _meta("bond_analytics.return_decomposition", report_date, rows)
    meta = _apply_vendor_meta_update(
        meta,
        curve_snapshots=inputs["curve_snapshots"],
        cache_version_suffix=YIELD_CURVE_CACHE_VERSION,
        curve_unavailable=inputs["curve_unavailable"],
        curve_latest_fallback=inputs["curve_latest_fallback"],
        fx_unavailable=inputs["fx_unavailable"],
        fx_latest_fallback=inputs["fx_latest_fallback"],
    )

    summary, trading_extra_warnings, trading_wd = _compute_return_decomposition_summary(
        rows=rows,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        inputs=inputs,
        duckdb_path=str(get_settings().duckdb_path),
    )
    payload = _build_return_decomposition_payload(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        meta=meta,
        relevant_curve_warnings=inputs["relevant_curve_warnings"],
        fx_current_warning=inputs["fx_current_warning"],
        fx_prior_warning=inputs["fx_prior_warning"],
        fx_missing_warnings=inputs["fx_missing_warnings"],
        trading_extra_warnings=trading_extra_warnings,
        warnings_detail=trading_wd,
    )
    result = _with_bond_amount_disclosure(
        build_formal_result_envelope(
            result_meta=meta, result_payload=_bond_analytics_api_payload(payload.model_dump(mode="json"))
        ),
        rows=rows,
    )
    _return_decomposition_cache.set(_cache_key, result)
    return result


def _resolve_curve_for_service(
    *,
    repo: YieldCurveRepository,
    requested_trade_date: str,
    curve_type: str,
) -> tuple[dict[str, object] | None, str | None]:
    snapshot, warning = repo.resolve_curve_snapshot(requested_trade_date, curve_type)
    if snapshot is not None or warning is None:
        return snapshot, warning
    if str(warning).startswith("No ") and "affected components remain 0" not in warning:
        return snapshot, f"{warning}; affected components remain 0."
    return snapshot, warning


def _ordered_unique_warnings(values: list[str | None]) -> list[str]:
    """Drop empties, preserve order, remove exact duplicates (stable contract surface)."""
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


def _required_fx_currencies(rows: list[dict[str, object]]) -> set[str]:
    return {
        str(row.get("currency_code") or "").upper().strip()
        for row in rows
        if str(row.get("currency_code") or "").upper().strip() not in {"", "CNY", "CNX", "RMB"}
    }


def _fx_unavailable_for_return_rows(
    rows: list[dict[str, object]],
    *,
    fx_rates_current: dict[str, Decimal] | None,
    fx_rates_prior: dict[str, Decimal] | None,
) -> bool:
    required = _required_fx_currencies(rows)
    if not required:
        return False
    current = fx_rates_current or {}
    prior = fx_rates_prior or {}
    return any(currency not in current for currency in required) or any(
        currency not in prior for currency in required
    )


def _fx_missing_warnings_for_return_rows(
    rows: list[dict[str, object]],
    *,
    report_date: str,
    prior_date: str,
    fx_rates_current: dict[str, Decimal] | None,
    fx_rates_prior: dict[str, Decimal] | None,
) -> list[str]:
    required = _required_fx_currencies(rows)
    if not required:
        return []
    warnings: list[str] = []
    current = fx_rates_current or {}
    prior = fx_rates_prior or {}
    missing_current = sorted(currency for currency in required if currency not in current)
    missing_prior = sorted(currency for currency in required if currency not in prior)
    if missing_current:
        warnings.append(
            f"Missing FX rates for {', '.join(missing_current)} on requested trade_date={report_date}; fx_effect remains 0 for affected rows."
        )
    if missing_prior:
        warnings.append(
            f"Missing FX rates for {', '.join(missing_prior)} on requested trade_date={prior_date}; fx_effect remains 0 for affected rows."
        )
    return warnings


def _merge_vendor_state(
    *,
    curve_unavailable: bool,
    curve_latest_fallback: bool,
    fx_unavailable: bool,
    fx_latest_fallback: bool,
) -> dict[str, str]:
    if curve_unavailable or fx_unavailable:
        return {"fallback_mode": "none", "vendor_status": "vendor_unavailable"}
    if curve_latest_fallback or fx_latest_fallback:
        return {"fallback_mode": "latest_snapshot", "vendor_status": "vendor_stale"}
    return {}


def _apply_vendor_meta_update(
    meta,
    *,
    curve_snapshots: list[dict[str, object]],
    cache_version_suffix: str | None = None,
    curve_unavailable: bool,
    curve_latest_fallback: bool,
    fx_unavailable: bool = False,
    fx_latest_fallback: bool = False,
):
    status_update = _merge_vendor_state(
        curve_unavailable=curve_unavailable,
        curve_latest_fallback=curve_latest_fallback,
        fx_unavailable=fx_unavailable,
        fx_latest_fallback=fx_latest_fallback,
    )
    if not curve_snapshots and not status_update:
        return meta

    update: dict[str, object] = {}
    if curve_snapshots:
        update.update(
            {
                "source_version": _merge_lineage_values(
                    meta.source_version,
                    *[str(snapshot.get("source_version") or "") for snapshot in curve_snapshots],
                    *[str(snapshot.get("vendor_name") or "").strip() for snapshot in curve_snapshots],
                ),
                "rule_version": _merge_lineage_values(
                    meta.rule_version,
                    *[str(snapshot.get("rule_version") or "") for snapshot in curve_snapshots],
                ),
                "vendor_version": _merge_lineage_values(
                    meta.vendor_version,
                    *[str(snapshot.get("vendor_version") or "") for snapshot in curve_snapshots],
                )
                or "vv_none",
            }
        )
        if cache_version_suffix:
            update["cache_version"] = f"{meta.cache_version}__{cache_version_suffix}"
    update.update(status_update)
    return meta.model_copy(update=update)


def _required_curve_types_for_return_rows(rows: list[dict[str, object]]) -> set[str]:
    needs_treasury = False
    needs_cdb = False
    needs_aaa = False
    for row in rows:
        if str(row.get("asset_class_std")) == "credit":
            needs_treasury = True
            needs_aaa = True
            continue
        curve_type = infer_curve_type(
            row.get("instrument_name"),
            row.get("bond_type"),
            row.get("asset_class_raw"),
        )
        if curve_type == "cdb":
            needs_cdb = True
        else:
            needs_treasury = True
    required: set[str] = set()
    if needs_treasury:
        required.add("treasury")
    if needs_cdb:
        required.add("cdb")
    if needs_aaa:
        required.add("aaa_credit")
    return required


def _resolve_curve_pair_if_needed(
    *,
    curve_type: str,
    required_curve_types: set[str],
    repo: YieldCurveRepository,
    report_date: str,
    prior_date: str,
) -> tuple[dict[str, object] | None, str | None]:
    if curve_type not in required_curve_types:
        return None, None
    current_snapshot, current_warning = _resolve_curve_for_service(
        repo=repo,
        requested_trade_date=report_date,
        curve_type=curve_type,
    )
    prior_snapshot, prior_warning = _resolve_curve_for_service(
        repo=repo,
        requested_trade_date=prior_date,
        curve_type=curve_type,
    )
    if current_snapshot is not None:
        current_snapshot = {
            **current_snapshot,
            "_prior_snapshot": prior_snapshot,
            "_prior_warning": prior_warning,
        }
    return current_snapshot, current_warning


def _curve_warnings_for_return_rows(
    rows: list[dict[str, object]],
    *,
    treasury_current_warning: str | None,
    treasury_prior_warning: str | None,
    cdb_current_warning: str | None,
    cdb_prior_warning: str | None,
    aaa_current_warning: str | None,
    aaa_prior_warning: str | None,
) -> list[str | None]:
    needs_treasury = False
    needs_cdb = False
    needs_aaa = False
    for row in rows:
        if str(row.get("asset_class_std")) == "credit":
            needs_treasury = True
            needs_aaa = True
            continue
        curve_type = infer_curve_type(
            row.get("instrument_name"),
            row.get("bond_type"),
            row.get("asset_class_raw"),
        )
        if curve_type == "cdb":
            needs_cdb = True
        else:
            needs_treasury = True
    selected: list[str | None] = []
    if needs_treasury:
        selected.extend([treasury_current_warning, treasury_prior_warning])
    if needs_cdb:
        selected.extend([cdb_current_warning, cdb_prior_warning])
    if needs_aaa:
        selected.extend([aaa_current_warning, aaa_prior_warning])
    return selected


def _select_benchmark_curve(curves: dict[str, object], curve_type: str) -> tuple:
    """Pick the (current, prior, current_warning, prior_warning) for the benchmark curve_type."""
    if curve_type == "treasury":
        return (curves["treasury_current"], curves["treasury_prior"],
                curves["treasury_current_warning"], curves["treasury_prior_warning"])
    if curve_type == "cdb":
        return (curves["cdb_current"], curves["cdb_prior"],
                curves["cdb_current_warning"], curves["cdb_prior_warning"])
    return (curves["aaa_current"], curves["aaa_prior"],
            curves["aaa_current_warning"], curves["aaa_prior_warning"])


def _fetch_benchmark_curves(
    rows: list[dict[str, object]],
    *,
    curve_repo: YieldCurveRepository,
    report_date: str,
    prior_date: str,
    benchmark_id: str,
) -> dict[str, object]:
    """Fetch all curves needed for benchmark excess, including the benchmark curve itself."""
    curve_type = BENCHMARK_CURVE_TYPES.get(benchmark_id, "cdb")
    curves = _fetch_all_curve_pairs(
        rows, curve_repo=curve_repo, report_date=report_date, prior_date=prior_date,
        extra_curve_types={curve_type},
    )
    current_curve, prior_curve, current_warning, prior_warning = _select_benchmark_curve(curves, curve_type)

    relevant_curve_warnings = _ordered_unique_warnings(
        [
            *_curve_warnings_for_return_rows(
                rows,
                treasury_current_warning=curves["treasury_current_warning"],
                treasury_prior_warning=curves["treasury_prior_warning"],
                cdb_current_warning=curves["cdb_current_warning"],
                cdb_prior_warning=curves["cdb_prior_warning"],
                aaa_current_warning=curves["aaa_current_warning"],
                aaa_prior_warning=curves["aaa_prior_warning"],
            ),
            current_warning if current_warning not in {
                curves["treasury_current_warning"], curves["cdb_current_warning"], curves["aaa_current_warning"]
            } else None,
            prior_warning if prior_warning not in {
                curves["treasury_prior_warning"], curves["cdb_prior_warning"], curves["aaa_prior_warning"]
            } else None,
        ]
    )

    return {
        **curves,
        "current_curve": current_curve,
        "prior_curve": prior_curve,
        "current_warning": current_warning,
        "prior_warning": prior_warning,
        "curve_latest_fallback": any(
            w and YIELD_CURVE_LATEST_FALLBACK_PREFIX in w for w in relevant_curve_warnings
        ),
        "curve_unavailable": any(w and w.startswith("No ") for w in relevant_curve_warnings),
        "relevant_curve_warnings": relevant_curve_warnings,
    }


def _resolve_curve_pair_from_batch(
    *,
    curve_type: str,
    required_curve_types: set[str],
    resolved_curves: dict[tuple[str, str], tuple[dict[str, object] | None, str | None]],
    report_date: str,
    prior_date: str,
) -> tuple[dict[str, object] | None, str | None]:
    if curve_type not in required_curve_types:
        return None, None
    current_snapshot, current_warning = resolved_curves.get(
        (report_date, curve_type),
        (None, f"No {curve_type} curve available for requested trade_date={report_date}; affected components remain 0."),
    )
    prior_snapshot, prior_warning = resolved_curves.get(
        (prior_date, curve_type),
        (None, f"No {curve_type} curve available for requested trade_date={prior_date}; affected components remain 0."),
    )
    if current_snapshot is not None:
        current_snapshot = {
            **current_snapshot,
            "_prior_snapshot": prior_snapshot,
            "_prior_warning": prior_warning,
        }
    return current_snapshot, current_warning


def _fetch_benchmark_curves_from_batch(
    rows: list[dict[str, object]],
    *,
    resolved_curves: dict[tuple[str, str], tuple[dict[str, object] | None, str | None]],
    report_date: str,
    prior_date: str,
    benchmark_id: str,
) -> dict[str, object]:
    curve_type = BENCHMARK_CURVE_TYPES.get(benchmark_id, "cdb")
    required = _required_curve_types_for_return_rows(rows) | {curve_type}

    treasury_current, treasury_current_warning = _resolve_curve_pair_from_batch(
        curve_type="treasury", required_curve_types=required, resolved_curves=resolved_curves,
        report_date=report_date, prior_date=prior_date,
    )
    cdb_current, cdb_current_warning = _resolve_curve_pair_from_batch(
        curve_type="cdb", required_curve_types=required, resolved_curves=resolved_curves,
        report_date=report_date, prior_date=prior_date,
    )
    aaa_current, aaa_current_warning = _resolve_curve_pair_from_batch(
        curve_type="aaa_credit", required_curve_types=required, resolved_curves=resolved_curves,
        report_date=report_date, prior_date=prior_date,
    )

    treasury_prior = treasury_current.get("_prior_snapshot") if treasury_current else None
    cdb_prior = cdb_current.get("_prior_snapshot") if cdb_current else None
    aaa_prior = aaa_current.get("_prior_snapshot") if aaa_current else None
    treasury_prior_warning = treasury_current.get("_prior_warning") if treasury_current else None
    cdb_prior_warning = cdb_current.get("_prior_warning") if cdb_current else None
    aaa_prior_warning = aaa_current.get("_prior_warning") if aaa_current else None
    curves = {
        "treasury_current": treasury_current,
        "treasury_prior": treasury_prior,
        "treasury_current_warning": treasury_current_warning,
        "treasury_prior_warning": treasury_prior_warning,
        "cdb_current": cdb_current,
        "cdb_prior": cdb_prior,
        "cdb_current_warning": cdb_current_warning,
        "cdb_prior_warning": cdb_prior_warning,
        "aaa_current": aaa_current,
        "aaa_prior": aaa_prior,
        "aaa_current_warning": aaa_current_warning,
        "aaa_prior_warning": aaa_prior_warning,
    }
    current_curve, prior_curve, current_warning, prior_warning = _select_benchmark_curve(curves, curve_type)
    relevant_curve_warnings = _ordered_unique_warnings(
        [
            *_curve_warnings_for_return_rows(
                rows,
                treasury_current_warning=treasury_current_warning,
                treasury_prior_warning=treasury_prior_warning,
                cdb_current_warning=cdb_current_warning,
                cdb_prior_warning=cdb_prior_warning,
                aaa_current_warning=aaa_current_warning,
                aaa_prior_warning=aaa_prior_warning,
            ),
            current_warning if current_warning not in {
                treasury_current_warning, cdb_current_warning, aaa_current_warning
            } else None,
            prior_warning if prior_warning not in {
                treasury_prior_warning, cdb_prior_warning, aaa_prior_warning
            } else None,
        ]
    )
    curve_snapshots = [
        s for s in (treasury_current, treasury_prior, cdb_current, cdb_prior, aaa_current, aaa_prior)
        if s is not None
    ]
    return {
        **curves,
        "current_curve": current_curve,
        "prior_curve": prior_curve,
        "current_warning": current_warning,
        "prior_warning": prior_warning,
        "curve_snapshots": curve_snapshots,
        "curve_latest_fallback": any(
            w and YIELD_CURVE_LATEST_FALLBACK_PREFIX in w for w in relevant_curve_warnings
        ),
        "curve_unavailable": any(w and w.startswith("No ") for w in relevant_curve_warnings),
        "relevant_curve_warnings": relevant_curve_warnings,
    }


def _build_benchmark_excess_payload(
    *,
    report_date: date,
    period_type: str,
    period_start: date,
    period_end: date,
    benchmark_id: str,
    summary: dict[str, object],
    meta,
    warnings: list[str],
) -> BenchmarkExcessResponse:
    return BenchmarkExcessResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "period_type": period_type,
                "period_start": period_start,
                "period_end": period_end,
                "benchmark_id": benchmark_id,
                "benchmark_name": BENCHMARK_NAMES.get(benchmark_id, benchmark_id),
                "portfolio_return": summary["portfolio_return"],
                "benchmark_return": summary["benchmark_return"],
                "excess_return": summary["excess_return"],
                "duration_effect": summary["duration_effect"],
                "curve_effect": summary["curve_effect"],
                "spread_effect": summary["spread_effect"],
                "selection_effect": summary["selection_effect"],
                "allocation_effect": summary["allocation_effect"],
                "explained_excess": summary["explained_excess"],
                "recon_error": summary["recon_error"],
                "portfolio_duration": summary["portfolio_duration"],
                "benchmark_duration": summary["benchmark_duration"],
                "duration_diff": summary["duration_diff"],
                "excess_sources": [
                    {
                        **row,
                        "contribution": numeric_json(Decimal(str(row["contribution"])), "bp", True),
                    }
                    for row in summary["excess_sources"]
                ],
                "computed_at": meta.generated_at.isoformat(),
                "warnings": warnings,
            },
            BenchmarkExcessResponse,
        )
    )


def _build_benchmark_excess_warnings(
    *,
    rows: list[dict[str, object]],
    summary: dict[str, object],
    curves: dict[str, object],
    current_curve,
    prior_curve,
    treasury_current,
    treasury_prior,
    aaa_current,
    aaa_prior,
) -> list[str]:
    credit_rows = [row for row in rows if str(row.get("asset_class_std")) == "credit"]
    spread_excess_incomplete = (
        bool(current_curve and prior_curve)
        and bool(credit_rows)
        and summary["spread_effect"] == ZERO
        and (treasury_current is None or treasury_prior is None or aaa_current is None or aaa_prior is None)
    )
    recon_large = abs(safe_decimal(summary["recon_error"])) > Decimal("0.02")
    return _ordered_unique_warnings(
        [
            BENCHMARK_WARNING if not current_curve or not prior_curve else None,
            BENCHMARK_EXCESS_SPREAD_GAP_WARNING if spread_excess_incomplete else None,
            BENCHMARK_EXCESS_RECON_GAP if recon_large else None,
            curves["current_warning"],
            curves["prior_warning"],
            *_curve_warnings_for_return_rows(
                rows,
                treasury_current_warning=curves["treasury_current_warning"],
                treasury_prior_warning=curves["treasury_prior_warning"],
                cdb_current_warning=curves["cdb_current_warning"],
                cdb_prior_warning=curves["cdb_prior_warning"],
                aaa_current_warning=curves["aaa_current_warning"],
                aaa_prior_warning=curves["aaa_prior_warning"],
            ),
        ]
    )


def _empty_benchmark_excess_envelope(
    *,
    report_date: date,
    period_type: str,
    period_start: date,
    period_end: date,
    benchmark_id: str,
    rows: list[dict[str, object]],
    meta,
) -> dict[str, object]:
    summary = compute_benchmark_excess(
        rows, period_start=period_start, period_end=period_end, benchmark_id=benchmark_id,
        benchmark_curve_current=None, benchmark_curve_prior=None,
        treasury_curve_current=None, treasury_curve_prior=None,
        cdb_curve_current=None, cdb_curve_prior=None,
        aaa_credit_curve_current=None, aaa_credit_curve_prior=None,
    )
    bench_warns = [EMPTY_WARNING]
    if not _benchmark_excess_brinson_sum_matches_explained(summary):
        bench_warns.append(BENCHMARK_EXCESS_EXPLAINED_MISMATCH)
    payload = _build_benchmark_excess_payload(
        report_date=report_date, period_type=period_type,
        period_start=period_start, period_end=period_end,
        benchmark_id=benchmark_id, summary=summary, meta=meta,
        warnings=_ordered_unique_warnings(bench_warns),
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope(
            result_meta=meta, result_payload=_bond_analytics_api_payload(payload.model_dump(mode="json"))
        ),
        rows=rows,
    )


def _compute_benchmark_excess_summary(
    *,
    rows: list[dict[str, object]],
    period_start: date,
    period_end: date,
    benchmark_id: str,
    curves: dict[str, object],
) -> dict[str, object]:
    """Compute benchmark excess summary from pre-fetched curve data."""
    current_curve = curves["current_curve"]
    prior_curve = curves["prior_curve"]
    treasury_current = curves["treasury_current"]
    treasury_prior = curves["treasury_prior"]
    cdb_current = curves["cdb_current"]
    cdb_prior = curves["cdb_prior"]
    aaa_current = curves["aaa_current"]
    aaa_prior = curves["aaa_prior"]
    return compute_benchmark_excess(
        rows,
        period_start=period_start,
        period_end=period_end,
        benchmark_id=benchmark_id,
        benchmark_curve_current=current_curve["curve"] if current_curve and prior_curve else None,
        benchmark_curve_prior=prior_curve["curve"] if current_curve and prior_curve else None,
        treasury_curve_current=treasury_current["curve"] if treasury_current and treasury_prior else None,
        treasury_curve_prior=treasury_prior["curve"] if treasury_current and treasury_prior else None,
        cdb_curve_current=cdb_current["curve"] if cdb_current and cdb_prior else None,
        cdb_curve_prior=cdb_prior["curve"] if cdb_current and cdb_prior else None,
        aaa_credit_curve_current=aaa_current["curve"] if aaa_current and aaa_prior else None,
        aaa_credit_curve_prior=aaa_prior["curve"] if aaa_current and aaa_prior else None,
    )


def _build_benchmark_excess_envelope_from_inputs(
    *,
    report_date: date,
    period_type: str,
    period_start: date,
    period_end: date,
    benchmark_id: str,
    rows: list[dict[str, object]],
    meta,
    curves: dict[str, object],
) -> dict[str, object]:
    meta = _apply_vendor_meta_update(
        meta,
        curve_snapshots=curves["curve_snapshots"],
        cache_version_suffix=YIELD_CURVE_CACHE_VERSION,
        curve_unavailable=curves["curve_unavailable"],
        curve_latest_fallback=curves["curve_latest_fallback"],
    )

    summary = _compute_benchmark_excess_summary(
        rows=rows, period_start=period_start, period_end=period_end,
        benchmark_id=benchmark_id, curves=curves,
    )
    warnings = _build_benchmark_excess_warnings(
        rows=rows, summary=summary, curves=curves,
        current_curve=curves["current_curve"], prior_curve=curves["prior_curve"],
        treasury_current=curves["treasury_current"], treasury_prior=curves["treasury_prior"],
        aaa_current=curves["aaa_current"], aaa_prior=curves["aaa_prior"],
    )
    if not _benchmark_excess_brinson_sum_matches_explained(summary):
        warnings = _ordered_unique_warnings([*warnings, BENCHMARK_EXCESS_EXPLAINED_MISMATCH])
    payload = _build_benchmark_excess_payload(
        report_date=report_date, period_type=period_type,
        period_start=period_start, period_end=period_end,
        benchmark_id=benchmark_id, summary=summary, meta=meta,
        warnings=warnings,
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope(
            result_meta=meta, result_payload=_bond_analytics_api_payload(payload.model_dump(mode="json"))
        ),
        rows=rows,
    )


def get_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict:
    _cache_key = (
        report_date.isoformat(),
        period_type,
        benchmark_id,
        *_duckdb_cache_version_token(),
    )
    hit, cached = _benchmark_excess_cache.get(_cache_key)
    if hit:
        return cached

    period_start, period_end = resolve_period(report_date, period_type)
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    meta = _meta("bond_analytics.benchmark_excess", report_date, rows)

    if not rows:
        result = _empty_benchmark_excess_envelope(
            report_date=report_date,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            benchmark_id=benchmark_id,
            rows=rows,
            meta=meta,
        )
        _benchmark_excess_cache.set(_cache_key, result)
        return result

    curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
    curves = _fetch_benchmark_curves(
        rows, curve_repo=curve_repo,
        report_date=report_date.isoformat(), prior_date=period_start.isoformat(),
        benchmark_id=benchmark_id,
    )
    result = _build_benchmark_excess_envelope_from_inputs(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        benchmark_id=benchmark_id,
        rows=rows,
        meta=meta,
        curves=curves,
    )
    _benchmark_excess_cache.set(_cache_key, result)
    return result


def get_benchmark_excess_many(
    report_dates: list[date],
    period_type: str = "MoM",
    benchmark_id: str = "CDB_INDEX",
) -> dict[str, dict]:
    requested_dates = [
        value for value in dict.fromkeys(report_dates)
        if isinstance(value, date)
    ]
    if not requested_dates:
        return {}
    cache_token = _duckdb_cache_version_token()
    out: dict[str, dict] = {}
    missing_dates: list[date] = []
    for report_date in requested_dates:
        cache_key = (
            report_date.isoformat(),
            period_type,
            benchmark_id,
            *cache_token,
        )
        hit, cached = _benchmark_excess_cache.get(cache_key)
        if hit:
            out[report_date.isoformat()] = cached
        else:
            missing_dates.append(report_date)
    if not missing_dates:
        return out

    repo = _repo()
    rows_by_date = repo.fetch_bond_analytics_rows_for_dates(
        report_dates=[value.isoformat() for value in missing_dates]
    )
    settings = get_settings()
    governance_repo = GovernanceRepository(base_dir=settings.governance_path)
    build_rows = governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
    manifest_rows = governance_repo.read_all(CACHE_MANIFEST_STREAM)

    period_by_date = {
        report_date: resolve_period(report_date, period_type)
        for report_date in missing_dates
    }
    curve_requests: list[tuple[str, str]] = []
    for report_date in missing_dates:
        rows = rows_by_date.get(report_date.isoformat(), [])
        if not rows:
            continue
        period_start, _period_end = period_by_date[report_date]
        required = _required_curve_types_for_return_rows(rows) | {
            BENCHMARK_CURVE_TYPES.get(benchmark_id, "cdb")
        }
        for curve_type in sorted(required):
            curve_requests.append((report_date.isoformat(), curve_type))
            curve_requests.append((period_start.isoformat(), curve_type))
    curve_repo = YieldCurveRepository(str(settings.duckdb_path))
    resolved_curves = curve_repo.resolve_curve_snapshots_many(curve_requests)
    resolved_curves = {
        key: (
            snapshot,
            (
                f"{warning}; affected components remain 0."
                if isinstance(warning, str)
                and warning.startswith("No ")
                and "affected components remain 0" not in warning
                else warning
            ),
        )
        for key, (snapshot, warning) in resolved_curves.items()
    }

    for report_date in missing_dates:
        report_date_text = report_date.isoformat()
        period_start, period_end = period_by_date[report_date]
        rows = rows_by_date.get(report_date_text, [])
        lineage = _lineage_from_governance_rows(
            report_date=report_date_text,
            rows=rows,
            build_rows=build_rows,
            manifest_rows=manifest_rows,
        )
        meta = _meta_from_lineage("bond_analytics.benchmark_excess", lineage)
        if not rows:
            result = _empty_benchmark_excess_envelope(
                report_date=report_date,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                benchmark_id=benchmark_id,
                rows=rows,
                meta=meta,
            )
        else:
            curves = _fetch_benchmark_curves_from_batch(
                rows,
                resolved_curves=resolved_curves,
                report_date=report_date_text,
                prior_date=period_start.isoformat(),
                benchmark_id=benchmark_id,
            )
            result = _build_benchmark_excess_envelope_from_inputs(
                report_date=report_date,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                benchmark_id=benchmark_id,
                rows=rows,
                meta=meta,
                curves=curves,
            )
        cache_key = (
            report_date_text,
            period_type,
            benchmark_id,
            *cache_token,
        )
        _benchmark_excess_cache.set(cache_key, result)
        out[report_date_text] = result
    return {report_date.isoformat(): out[report_date.isoformat()] for report_date in requested_dates if report_date.isoformat() in out}


def get_krd_curve_risk(report_date: date, scenario_set: str = "standard") -> dict:
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    meta = _meta("bond_analytics.krd_curve_risk", report_date, rows)
    risk = summarize_portfolio_risk(rows)
    payload = KRDCurveRiskResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "portfolio_duration": risk["portfolio_duration"],
                "portfolio_modified_duration": risk["portfolio_modified_duration"],
                "portfolio_dv01": risk["portfolio_dv01"],
                "portfolio_convexity": risk["portfolio_convexity"],
                "krd_buckets": [
                    KRDBucket.model_validate(
                        promote_flat_payload(
                            {
                                "tenor": row["tenor_bucket"],
                                "krd": row["krd"],
                                "dv01": row["dv01"],
                                "market_value_weight": row["market_value"] / risk["total_market_value"] if risk["total_market_value"] else ZERO,
                            },
                            KRDBucket,
                        )
                    )
                    for row in build_krd_distribution(rows)
                ],
                "scenarios": [
                    ScenarioResult.model_validate(
                        promote_flat_payload(
                            {
                                "scenario_name": row["scenario_name"],
                                "scenario_description": row["scenario_description"],
                                "shocks": row["shocks"],
                                "pnl_economic": row["pnl_economic"],
                                "pnl_oci": row["pnl_oci"],
                                "pnl_tpl": row["pnl_tpl"],
                                "rate_contribution": row["rate_contribution"],
                                "convexity_contribution": row["convexity_contribution"],
                                "by_asset_class": {
                                    key: {
                                        metric: numeric_json(value, "yuan", True)
                                        for metric, value in values.items()
                                    }
                                    for key, values in row["by_asset_class"].items()
                                },
                            },
                            ScenarioResult,
                        )
                    )
                    for row in build_curve_scenarios(rows)
                ],
                "by_asset_class": [
                    AssetClassRiskSummary.model_validate(
                        promote_flat_payload(
                            {
                                "asset_class": row["asset_class"],
                                "market_value": row["market_value"],
                                "duration": row["duration"],
                                "dv01": row["dv01"],
                                "weight": row["weight"],
                            },
                            AssetClassRiskSummary,
                        )
                    )
                    for row in build_asset_class_risk_summary(rows)
                ],
                "computed_at": meta.generated_at.isoformat(),
                "warnings": [EMPTY_WARNING] if not rows else [],
            },
            KRDCurveRiskResponse,
        )
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope(
            result_meta=meta, result_payload=_bond_analytics_api_payload(payload.model_dump(mode="json"))
        ),
        rows=rows,
    )


def _fetch_credit_curves(
    *,
    curve_repo: YieldCurveRepository,
    trade_date: str,
) -> dict[str, object]:
    """Fetch treasury + aaa_credit snapshots for credit spread analysis (single date, no prior needed).

    Returns dict with keys:
      treasury_current, treasury_warning, aaa_current, aaa_warning,
      curve_snapshots, curve_latest_fallback, curve_unavailable
    """
    treasury_current, treasury_warning = _resolve_curve_for_service(
        repo=curve_repo, requested_trade_date=trade_date, curve_type="treasury",
    )
    aaa_current, aaa_warning = _resolve_curve_for_service(
        repo=curve_repo, requested_trade_date=trade_date, curve_type="aaa_credit",
    )
    curve_snapshots = [s for s in (treasury_current, aaa_current) if s is not None]
    return {
        "treasury_current": treasury_current,
        "treasury_warning": treasury_warning,
        "aaa_current": aaa_current,
        "aaa_warning": aaa_warning,
        "curve_snapshots": curve_snapshots,
        "curve_latest_fallback": any(
            w and YIELD_CURVE_LATEST_FALLBACK_PREFIX in w for w in (aaa_warning, treasury_warning)
        ),
        "curve_unavailable": any(
            w and w.startswith("No ") for w in (aaa_warning, treasury_warning)
        ),
    }


def _build_credit_spread_payload(
    *,
    report_date: date,
    credit_rows: list[dict[str, object]],
    summary: dict[str, object],
    spread_scenarios: str,
    meta,
    warnings: list[str],
) -> CreditSpreadMigrationResponse:
    return CreditSpreadMigrationResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "credit_bond_count": int(summary["credit_bond_count"]),
                "credit_market_value": summary["credit_market_value"],
                "credit_weight": summary["credit_weight"],
                "rating_aa_and_below_weight": rating_aa_and_below_portfolio_weight(
                    credit_rows,
                    total_portfolio_market_value=summary["total_market_value"],
                ),
                "spread_dv01": summary["spread_dv01"],
                "weighted_avg_spread": summary["weighted_avg_spread"],
                "weighted_avg_spread_duration": summary["weighted_avg_spread_duration"],
                "spread_scenarios": [
                    SpreadScenarioResult.model_validate(
                        promote_flat_payload(
                            {
                                "scenario_name": f"利差{'走阔' if change_bp > 0 else '收窄'} {abs(change_bp)}bp",
                                "spread_change_bp": float(change_bp),
                                "pnl_impact": -(summary["spread_dv01"] * Decimal(str(change_bp))),
                                "oci_impact": -(summary["oci_spread_dv01"] * Decimal(str(change_bp))),
                                "tpl_impact": -(summary["tpl_spread_dv01"] * Decimal(str(change_bp))),
                            },
                            SpreadScenarioResult,
                        )
                    )
                    for bp in [int(v.strip()) for v in spread_scenarios.split(",") if v.strip()]
                    for change_bp in (bp, -bp)
                ],
                "migration_scenarios": [],
                "concentration_by_issuer": _to_concentration_model(build_concentration(credit_rows, field_name="issuer_name", dimension="issuer")),
                "concentration_by_industry": _to_concentration_model(build_concentration(credit_rows, field_name="industry_name", dimension="industry")),
                "concentration_by_rating": _to_concentration_model(build_concentration(credit_rows, field_name="rating", dimension="rating")),
                "concentration_by_tenor": _to_concentration_model(build_concentration(credit_rows, field_name="tenor_bucket", dimension="tenor")),
                "oci_credit_exposure": summary["oci_credit_exposure"],
                "oci_spread_dv01": summary["oci_spread_dv01"],
                "oci_sensitivity_25bp": -(summary["oci_spread_dv01"] * Decimal("25")),
                "computed_at": meta.generated_at.isoformat(),
                "warnings": warnings,
            },
            CreditSpreadMigrationResponse,
        )
    )


def get_credit_spread_migration(report_date: date, spread_scenarios: str = "10,25,50") -> dict:
    all_rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    credit_rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat(), asset_class="credit")
    meta = _meta("bond_analytics.credit_spread_migration", report_date, all_rows)

    treasury_current = None
    aaa_current = None
    if credit_rows:
        curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
        curves = _fetch_credit_curves(curve_repo=curve_repo, trade_date=report_date.isoformat())
        treasury_current = curves["treasury_current"]
        aaa_current = curves["aaa_current"]
        meta = _apply_vendor_meta_update(
            meta,
            curve_snapshots=curves["curve_snapshots"],
            cache_version_suffix=YIELD_CURVE_CACHE_VERSION,
            curve_unavailable=curves["curve_unavailable"],
            curve_latest_fallback=curves["curve_latest_fallback"],
        )
        curve_warnings = _ordered_unique_warnings([curves["aaa_warning"], curves["treasury_warning"]])
    else:
        curve_warnings = []

    summary = summarize_credit(
        credit_rows,
        total_rows=all_rows,
        aaa_credit_curve_current=aaa_current["curve"] if aaa_current else None,
        treasury_curve_current=treasury_current["curve"] if treasury_current else None,
    )
    spread_level_incomplete = (
        bool(credit_rows)
        and summary["weighted_avg_spread"] == ZERO
        and (aaa_current is None or treasury_current is None)
    )
    migration_warnings = (
        [EMPTY_WARNING]
        if not all_rows
        else _ordered_unique_warnings([SPREAD_WARNING if spread_level_incomplete else None, *curve_warnings])
    )
    meta = _credit_spread_candidate_meta(
        formal_meta=meta,
        report_date=report_date,
        spread_scenarios=spread_scenarios,
        rows=all_rows,
    )
    payload = _build_credit_spread_payload(
        report_date=report_date,
        credit_rows=credit_rows,
        summary=summary,
        spread_scenarios=spread_scenarios,
        meta=meta,
        warnings=migration_warnings,
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope(
            result_meta=meta, result_payload=_bond_analytics_api_payload(payload.model_dump(mode="json"))
        ),
        rows=all_rows,
    )


def _to_concentration_model(payload: dict[str, object] | None) -> ConcentrationMetrics | None:
    if payload is None:
        return None
    return ConcentrationMetrics.model_validate(
        promote_flat_payload(
            {
                "dimension": str(payload["dimension"]),
                "hhi": payload["hhi"],
                "top5_concentration": payload["top5_concentration"],
                "top_items": [
                    ConcentrationItem.model_validate(
                        promote_flat_payload(
                            {
                                "name": str(row["name"]),
                                "weight": row["weight"],
                                "market_value": row["market_value"],
                            },
                            ConcentrationItem,
                        )
                    )
                    for row in payload["top_items"]
                ],
            },
            ConcentrationMetrics,
        )
    )


def _build_portfolio_headlines_empty_response(report_date: date) -> dict:
    """Build empty portfolio headlines response when no data."""
    payload = PortfolioHeadlinesResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "total_market_value": ZERO,
                "weighted_ytm": ZERO,
                "weighted_duration": ZERO,
                "weighted_coupon": ZERO,
                "total_dv01": ZERO,
                "bond_count": 0,
                "credit_weight": ZERO,
                "issuer_hhi": ZERO,
                "issuer_top5_weight": ZERO,
                "by_asset_class": [],
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": [EMPTY_WARNING],
            },
            PortfolioHeadlinesResponse,
        )
    )
    return _build_fact_envelope(
        result_kind="bond_analytics.portfolio_headlines",
        report_date=report_date,
        rows=[],
        result_payload=payload.model_dump(mode="json"),
    )


def _compute_portfolio_headlines_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    """Compute all metrics for portfolio headlines."""
    risk = summarize_portfolio_risk(rows)
    rate_duration_rows = _rate_duration_rows(rows)
    rate_duration_risk = summarize_portfolio_risk(rate_duration_rows)
    credit_rows = [row for row in rows if str(row.get("asset_class_std")) == "credit"]
    credit_summary = summarize_credit(
        credit_rows,
        total_rows=rows,
        aaa_credit_curve_current=None,
        treasury_curve_current=None,
    )
    conc = build_concentration(rows, field_name="issuer_name", dimension="issuer")
    ytm_dec = weighted_average_by_market_value(rate_duration_rows, "ytm")
    cpn_dec = weighted_average_by_market_value(rows, "coupon_rate")
    by_ac = build_asset_class_risk_summary(rows)
    return {
        "risk": risk,
        "rate_duration_risk": rate_duration_risk,
        "credit_summary": credit_summary,
        "conc": conc,
        "ytm_dec": ytm_dec,
        "cpn_dec": cpn_dec,
        "by_ac": by_ac,
    }


def _rate_duration_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        row
        for row in rows
        if str(row.get("asset_class_std")) in {"rate", "credit"}
        and row.get("maturity_date") is not None
        and safe_decimal(row.get("modified_duration")) > ZERO
        and safe_decimal(row.get("market_value")) != ZERO
    ]


def get_portfolio_headlines(report_date: date) -> dict:
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    if not rows:
        return _build_portfolio_headlines_empty_response(report_date)

    metrics = _compute_portfolio_headlines_metrics(rows)
    pct = Decimal("100")
    payload = PortfolioHeadlinesResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "total_market_value": metrics["risk"]["total_market_value"],
                "weighted_ytm": metrics["ytm_dec"] * pct,
                "weighted_duration": metrics["rate_duration_risk"]["portfolio_modified_duration"],
                "weighted_coupon": metrics["cpn_dec"] * pct,
                "total_dv01": metrics["risk"]["portfolio_dv01"],
                "bond_count": int(metrics["risk"]["bond_count"]),
                "credit_weight": metrics["credit_summary"]["credit_weight"],
                "issuer_hhi": metrics["conc"]["hhi"] if metrics["conc"] else ZERO,
                "issuer_top5_weight": metrics["conc"]["top5_concentration"] if metrics["conc"] else ZERO,
                "by_asset_class": [
                    AssetClassRiskSummary.model_validate(
                        promote_flat_payload(
                            {
                                "asset_class": row["asset_class"],
                                "market_value": row["market_value"],
                                "duration": row["duration"],
                                "dv01": row["dv01"],
                                "weight": row["weight"],
                            },
                            AssetClassRiskSummary,
                        )
                    )
                    for row in metrics["by_ac"]
                ],
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": [],
            },
            PortfolioHeadlinesResponse,
        )
    )
    return _build_fact_envelope(
        result_kind="bond_analytics.portfolio_headlines",
        report_date=report_date,
        rows=rows,
        result_payload=payload.model_dump(mode="json"),
    )


def get_dv01_risk(
    report_date: date,
    accounting_class: str = "OCI",
    top_n: int = 20,
    shock_bps: str = "1,10,25,50",
) -> dict:
    normalized_class = _normalize_dv01_accounting_class(accounting_class)
    rows = _repo().fetch_bond_analytics_rows(
        report_date=report_date.isoformat(),
        accounting_class=normalized_class,
    )
    top_n = max(1, min(int(top_n), 100))
    shocks = dv01_core.parse_dv01_shocks(shock_bps)
    summary = dv01_core.dv01_scope_summary(rows)
    total_dv01 = summary["total_dv01"]
    total_abs_dv01 = dv01_core.total_abs_dv01(rows)
    warnings = _dv01_scope_warnings(rows, normalized_class)

    payload = DV01RiskResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "accounting_class": normalized_class,
                "total_face_value": summary["total_face_value"],
                "total_market_value": summary["total_market_value"],
                "face_weighted_modified_duration": summary["face_weighted_modified_duration"],
                "total_dv01": total_dv01,
                "position_count": len(rows),
                "shock_scenarios": _model_payloads(
                    dv01_core.build_dv01_shock_scenario_payloads(total_dv01=total_dv01, shocks=shocks)
                    if rows
                    else [],
                    DV01ShockScenario,
                ),
                "tenor_buckets": _model_payloads(
                    dv01_core.build_dv01_tenor_bucket_payloads(rows, total_abs_dv01=total_abs_dv01),
                    DV01TenorBucket,
                ),
                "top_bonds": _model_payloads(
                    dv01_core.build_dv01_top_bond_payloads(rows, total_abs_dv01=total_abs_dv01, top_n=top_n),
                    DV01TopBondItem,
                ),
                "top_issuers": _model_payloads(
                    dv01_core.build_dv01_top_issuer_payloads(rows, total_abs_dv01=total_abs_dv01, top_n=top_n),
                    DV01TopIssuerItem,
                ),
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": warnings,
            },
            DV01RiskResponse,
        )
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope_from_lineage(
            trace_id=_trace_id(),
            result_kind="bond_analytics.dv01_risk",
            lineage=_lineage(report_date.isoformat(), rows),
            default_cache_version=CACHE_VERSION,
            source_surface="bond_analytics",
            result_payload=payload.model_dump(mode="json"),
        ),
        rows=rows,
    )


def get_dv01_reconciliation(report_date: date, accounting_class: str = "OCI") -> dict:
    normalized_class = _normalize_dv01_accounting_class(accounting_class)
    rows = _repo().fetch_bond_analytics_rows(
        report_date=report_date.isoformat(),
        accounting_class=normalized_class,
    )
    summary = dv01_core.dv01_scope_summary(rows)
    total_abs_dv01 = dv01_core.total_abs_dv01(rows)
    warnings = _dv01_scope_warnings(rows, normalized_class)

    payload = DV01ReconciliationResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "accounting_class": normalized_class,
                "total_face_value": summary["total_face_value"],
                "total_market_value": summary["total_market_value"],
                "face_weighted_modified_duration": summary["face_weighted_modified_duration"],
                "total_dv01": summary["total_dv01"],
                "position_count": len(rows),
                "rows": _model_payloads(
                    dv01_core.build_dv01_reconciliation_payloads(rows, total_abs_dv01=total_abs_dv01),
                    DV01ReconciliationRow,
                ),
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": warnings,
            },
            DV01ReconciliationResponse,
        )
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope_from_lineage(
            trace_id=_trace_id(),
            result_kind="bond_analytics.dv01_reconciliation",
            lineage=_lineage(report_date.isoformat(), rows),
            default_cache_version=CACHE_VERSION,
            source_surface="bond_analytics",
            result_payload=payload.model_dump(mode="json"),
        ),
        rows=rows,
    )


def get_dv01_movement(report_date: date, accounting_class: str = "OCI", top_n: int = 20) -> dict:
    normalized_class = _normalize_dv01_accounting_class(accounting_class)
    top_n = max(1, min(int(top_n), 100))
    repo = _repo()
    current_date = report_date.isoformat()
    previous_date = _resolve_prior_bond_snapshot_date(repo, current_date)
    current_rows = repo.fetch_bond_analytics_rows(
        report_date=current_date,
        accounting_class=normalized_class,
    )
    previous_rows = (
        repo.fetch_bond_analytics_rows(
            report_date=previous_date,
            accounting_class=normalized_class,
        )
        if previous_date
        else []
    )
    current_all_rows = repo.fetch_bond_analytics_rows(report_date=current_date, accounting_class="all")
    previous_all_rows = repo.fetch_bond_analytics_rows(report_date=previous_date, accounting_class="all") if previous_date else []

    current_summary = dv01_core.dv01_scope_summary(current_rows)
    previous_summary = dv01_core.dv01_scope_summary(previous_rows)
    delta_dv01 = current_summary["total_dv01"] - previous_summary["total_dv01"]
    warnings: list[str] = []
    if not current_rows:
        warnings.append(EMPTY_WARNING)
    if not previous_date:
        warnings.append("No prior bond analytics report date available; DV01 movement cannot be computed.")
    elif not previous_rows:
        warnings.append("Prior bond analytics snapshot is empty for this accounting class; DV01 movement is current-only.")

    if not current_rows or not previous_rows:
        payload = DV01MovementResponse.model_validate(
            promote_flat_payload(
                {
                    "report_date": report_date,
                    "previous_report_date": date.fromisoformat(previous_date) if previous_date else None,
                    "accounting_class": normalized_class,
                    "source_status": "empty",
                    "current_total_face_value": current_summary["total_face_value"],
                    "previous_total_face_value": previous_summary["total_face_value"],
                    "current_total_market_value": current_summary["total_market_value"],
                    "previous_total_market_value": previous_summary["total_market_value"],
                    "current_face_weighted_modified_duration": current_summary["face_weighted_modified_duration"],
                    "previous_face_weighted_modified_duration": previous_summary["face_weighted_modified_duration"],
                    "current_total_dv01": current_summary["total_dv01"],
                    "previous_total_dv01": previous_summary["total_dv01"],
                    "delta_dv01": delta_dv01,
                    "current_position_count": len(current_rows),
                    "previous_position_count": len(previous_rows),
                    "attribution": [],
                    "anomaly_bonds": [],
                    "methodology_checks": [],
                    "computed_at": datetime.now(UTC).isoformat(),
                    "warnings": warnings,
                },
                DV01MovementResponse,
            )
        )
        return _with_bond_amount_disclosure(
            build_formal_result_envelope_from_lineage(
                trace_id=_trace_id(),
                result_kind="bond_analytics.dv01_movement",
                lineage=_lineage(current_date, [*current_rows, *previous_rows]),
                default_cache_version=CACHE_VERSION,
                source_surface="bond_analytics",
                result_payload=payload.model_dump(mode="json"),
            ),
            rows=[*current_rows, *previous_rows],
        )

    movement_payloads = dv01_core.build_dv01_movement_bond_payloads(
        current_rows=current_rows,
        previous_rows=previous_rows,
        current_all_rows=current_all_rows,
        previous_all_rows=previous_all_rows,
    )
    movement_rows = _model_payloads(movement_payloads, DV01MovementBondItem)
    attribution = _model_payloads(
        dv01_core.build_dv01_movement_attribution_payloads(
            movement_payloads,
            total_delta_dv01=delta_dv01,
        ),
        DV01MovementAttributionItem,
    )
    anomaly_bonds = sorted(
        movement_rows,
        key=lambda row: (
            safe_decimal(row.dv01_delta.raw).copy_abs(),
            safe_decimal(row.current_dv01.raw).copy_abs(),
            row.instrument_code,
        ),
        reverse=True,
    )[:top_n]
    methodology_checks = sorted(
        [row for row in movement_rows if safe_decimal(row.current_dv01.raw) != ZERO],
        key=lambda row: (
            safe_decimal(row.dv01_estimate_gap.raw).copy_abs(),
            safe_decimal(row.current_dv01.raw).copy_abs(),
            row.instrument_code,
        ),
        reverse=True,
    )[:top_n]
    payload = DV01MovementResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "previous_report_date": date.fromisoformat(previous_date),
                "accounting_class": normalized_class,
                "source_status": "ready",
                "current_total_face_value": current_summary["total_face_value"],
                "previous_total_face_value": previous_summary["total_face_value"],
                "current_total_market_value": current_summary["total_market_value"],
                "previous_total_market_value": previous_summary["total_market_value"],
                "current_face_weighted_modified_duration": current_summary["face_weighted_modified_duration"],
                "previous_face_weighted_modified_duration": previous_summary["face_weighted_modified_duration"],
                "current_total_dv01": current_summary["total_dv01"],
                "previous_total_dv01": previous_summary["total_dv01"],
                "delta_dv01": delta_dv01,
                "current_position_count": len(current_rows),
                "previous_position_count": len(previous_rows),
                "attribution": attribution,
                "anomaly_bonds": anomaly_bonds,
                "methodology_checks": methodology_checks,
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": warnings,
            },
            DV01MovementResponse,
        )
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope_from_lineage(
            trace_id=_trace_id(),
            result_kind="bond_analytics.dv01_movement",
            lineage=_lineage(current_date, [*current_rows, *previous_rows]),
            default_cache_version=CACHE_VERSION,
            source_surface="bond_analytics",
            result_payload=payload.model_dump(mode="json"),
        ),
        rows=[*current_rows, *previous_rows],
    )


DEFAULT_DV01_LIMIT = Decimal("5000000")
DEFAULT_DV01_WARNING = Decimal("4000000")
DEFAULT_DV01_HEDGE_UNIT = Decimal("100000")
DEFAULT_DV01_HEDGE_TARGET = Decimal("4000000")
DV01_ACTION_SHOCKS = (Decimal("10"), Decimal("25"))
DV01_LIMIT_CONFIG_STREAM = "bond_dv01_limit_config"
DV01_LIMIT_CONFIG_REQUIRED_FIELDS = (
    "accounting_class",
    "limit_dv01",
    "warning_dv01",
    "hedge_target_dv01",
    "limit_source",
    "limit_source_version",
    "limit_rule_version",
    "limit_effective_date",
)
DV01_ACTION_FORMAL_LIMIT_NOTE = "已接入正式 DV01 限额；按限额配置计算使用率、剩余额度和动作建议。"
DV01_ACTION_THRESHOLD_NOTE = "页面预警阈值，不代表正式限额；未接入正式限额源时仅作参考。"
DV01_PAGE_THRESHOLD_RULE_VERSION = "rv_dv01_page_threshold_v3"


def get_dv01_action_plan(
    report_date: date,
    accounting_class: str = "OCI",
    top_n: int = 20,
    limit_dv01: str | int | float | Decimal | None = None,
    warning_dv01: str | int | float | Decimal | None = None,
    hedge_instrument_dv01: str | int | float | Decimal | None = None,
    hedge_target_dv01: str | int | float | Decimal | None = None,
) -> dict:
    normalized_class = _normalize_dv01_accounting_class(accounting_class)
    top_n = max(1, min(int(top_n), 100))
    rows = _repo().fetch_bond_analytics_rows(
        report_date=report_date.isoformat(),
        accounting_class=normalized_class,
    )
    hedge_unit = _positive_decimal_or_default(hedge_instrument_dv01, DEFAULT_DV01_HEDGE_UNIT)
    limit_config = _resolve_dv01_limit_config(
        report_date=report_date,
        accounting_class=normalized_class,
    )
    if limit_config is not None:
        limit = limit_config.limit_dv01
        warning = limit_config.warning_dv01
        hedge_target = limit_config.hedge_target_dv01
        policy_basis = "formal_limit"
        threshold_note = DV01_ACTION_FORMAL_LIMIT_NOTE
        limit_source = limit_config.limit_source
        limit_source_version = limit_config.limit_source_version
        limit_rule_version = limit_config.limit_rule_version
        limit_effective_date = limit_config.limit_effective_date
    else:
        limit = _positive_decimal_or_default(limit_dv01, DEFAULT_DV01_LIMIT)
        warning = _positive_decimal_or_default(warning_dv01, DEFAULT_DV01_WARNING)
        hedge_target = _positive_decimal_or_default(hedge_target_dv01, min(warning, limit))
        policy_basis = "page_threshold_fallback"
        threshold_note = DV01_ACTION_THRESHOLD_NOTE
        limit_source = "page_threshold"
        limit_source_version = "unconfigured"
        limit_rule_version = DV01_PAGE_THRESHOLD_RULE_VERSION
        limit_effective_date = None
    total_dv01 = sum((safe_decimal(row.get("dv01")) for row in rows), ZERO)
    total_abs_dv01 = dv01_core.total_abs_dv01(rows)
    dv01_to_reduce = max(total_dv01 - hedge_target, ZERO)
    limit_usage = (total_dv01 / limit) if limit > ZERO else ZERO
    remaining_limit_dv01 = limit - total_dv01
    suggested_hedge_units = (dv01_to_reduce / hedge_unit) if hedge_unit > ZERO else ZERO
    risk_level = dv01_core.dv01_action_risk_level(
        total_dv01=total_dv01,
        warning_dv01=warning,
        limit_dv01=limit,
        has_rows=bool(rows),
    )
    warnings = [] if limit_config is not None else [DV01_ACTION_THRESHOLD_NOTE]
    if not rows:
        warnings.append(EMPTY_WARNING)

    scenario_breaches = _model_payloads(
        dv01_core.build_dv01_action_scenario_payloads(
            total_dv01=total_dv01,
            warning_dv01=warning,
            limit_dv01=limit,
            has_rows=bool(rows),
            shocks=DV01_ACTION_SHOCKS,
        ),
        DV01ActionScenarioBreach,
    )
    tenor_actions = _model_payloads(
        dv01_core.build_dv01_action_tenor_payloads(
            rows,
            total_abs_dv01=total_abs_dv01,
            dv01_to_reduce=dv01_to_reduce,
            top_n=top_n,
        ),
        DV01ActionTenorItem,
    )
    issuer_actions = _model_payloads(
        dv01_core.build_dv01_action_issuer_payloads(
            rows,
            total_abs_dv01=total_abs_dv01,
            dv01_to_reduce=dv01_to_reduce,
            top_n=top_n,
        ),
        DV01ActionIssuerItem,
    )
    bond_actions = _model_payloads(
        dv01_core.build_dv01_action_bond_payloads(
            rows,
            total_abs_dv01=total_abs_dv01,
            dv01_to_reduce=dv01_to_reduce,
            top_n=top_n,
        ),
        DV01ActionBondItem,
    )
    breach_count = int(risk_level == "breach") + sum(
        1 for row in scenario_breaches if row.risk_level in {"watch", "breach"}
    )
    payload = DV01ActionPlanResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "accounting_class": normalized_class,
                "risk_level": risk_level,
                "policy_basis": policy_basis,
                "threshold_note": threshold_note,
                "limit_source": limit_source,
                "limit_source_version": limit_source_version,
                "limit_rule_version": limit_rule_version,
                "limit_effective_date": limit_effective_date,
                "total_dv01": total_dv01,
                "limit_dv01": limit,
                "warning_dv01": warning,
                "limit_usage": limit_usage,
                "remaining_limit_dv01": remaining_limit_dv01,
                "dv01_to_reduce": dv01_to_reduce,
                "hedge_instrument_label": "DV01 hedge unit",
                "hedge_instrument_dv01": hedge_unit,
                "suggested_hedge_units": suggested_hedge_units,
                "position_count": len(rows),
                "breach_count": breach_count,
                "scenario_breaches": scenario_breaches,
                "tenor_actions": tenor_actions,
                "issuer_actions": issuer_actions,
                "bond_actions": bond_actions,
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": warnings,
            },
            DV01ActionPlanResponse,
        )
    )
    lineage = _lineage(report_date.isoformat(), rows)
    result_payload = payload.model_dump(mode="json")
    result_kind = "bond_analytics.dv01_action_plan"
    return _with_bond_amount_disclosure(
        build_result_envelope(
            basis="analytical",
            trace_id=_trace_id(),
            result_kind=result_kind,
            cache_version=str(lineage.get("cache_version") or CACHE_VERSION),
            source_version=str(lineage.get("source_version") or "sv_unknown"),
            rule_version=str(lineage.get("rule_version") or "rv_unknown"),
            vendor_version=str(lineage.get("vendor_version") or "vv_none"),
            source_surface="bond_analytics",
            requested_report_date=report_date.isoformat(),
            resolved_report_date=report_date.isoformat(),
            as_of_date=report_date.isoformat(),
            date_basis=BOND_ANALYTICS_DATE_BASIS,
            filters_applied={
                "report_date": report_date.isoformat(),
                "accounting_class": normalized_class,
                "policy_basis": policy_basis,
            },
            tables_used=[BOND_ANALYTICS_FACT_TABLE],
            evidence_rows=len(rows),
            result_payload=result_payload,
        ),
        rows=rows,
    )


def _positive_decimal_or_default(value: str | int | float | Decimal | None, default: Decimal) -> Decimal:
    parsed = safe_decimal(value)
    if parsed <= ZERO:
        return default
    return parsed


class _DV01LimitConfig:
    def __init__(
        self,
        *,
        limit_dv01: Decimal,
        warning_dv01: Decimal,
        hedge_target_dv01: Decimal,
        limit_source: str,
        limit_source_version: str,
        limit_rule_version: str,
        limit_effective_date: date,
    ) -> None:
        self.limit_dv01 = limit_dv01
        self.warning_dv01 = warning_dv01
        self.hedge_target_dv01 = hedge_target_dv01
        self.limit_source = limit_source
        self.limit_source_version = limit_source_version
        self.limit_rule_version = limit_rule_version
        self.limit_effective_date = limit_effective_date


DV01_LIMIT_CONFIG_CLASSES = ("AC", "OCI", "TPL", "all")
DV01_LIMIT_CONFIG_BUSINESS_FIELDS = tuple(
    field for field in DV01_LIMIT_CONFIG_REQUIRED_FIELDS if field != "accounting_class"
)


def get_dv01_limit_config_status(report_date: date) -> dict:
    rows = [_build_dv01_limit_config_status_row(report_date, accounting_class) for accounting_class in DV01_LIMIT_CONFIG_CLASSES]
    configured_count = sum(1 for row in rows if row.status == "ready")
    missing_count = sum(1 for row in rows if row.status == "missing")
    invalid_count = sum(1 for row in rows if row.status == "invalid")
    configured_accounting_classes = [row.accounting_class for row in rows if row.status == "ready"]
    missing_accounting_classes = [row.accounting_class for row in rows if row.status == "missing"]
    invalid_accounting_classes = [row.accounting_class for row in rows if row.status == "invalid"]
    needs_business_followup = bool(missing_accounting_classes or invalid_accounting_classes)
    acceptance_message, next_action = _dv01_limit_config_acceptance_guidance(
        missing_accounting_classes=missing_accounting_classes,
        invalid_accounting_classes=invalid_accounting_classes,
    )
    warnings: list[str] = []
    if missing_count:
        warnings.append("部分会计分类未配置正式 DV01 限额。")
    if invalid_count:
        warnings.append("部分会计分类的正式 DV01 限额配置无效，动作计划将回退页面阈值。")
    payload = DV01LimitConfigStatusResponse.model_validate(
        {
            "report_date": report_date,
            "overall_status": "ready" if configured_count == len(DV01_LIMIT_CONFIG_CLASSES) else "incomplete",
            "acceptance_status": "ready" if configured_count == len(DV01_LIMIT_CONFIG_CLASSES) else "blocked",
            "acceptance_message": acceptance_message,
            "next_action": next_action,
            "config_stream": DV01_LIMIT_CONFIG_STREAM,
            "required_accounting_classes": list(DV01_LIMIT_CONFIG_CLASSES),
            "required_fields": list(DV01_LIMIT_CONFIG_REQUIRED_FIELDS),
            "configured_accounting_classes": configured_accounting_classes,
            "missing_accounting_classes": missing_accounting_classes,
            "invalid_accounting_classes": invalid_accounting_classes,
            "missing_business_fields_by_class": _dv01_limit_config_missing_business_fields_by_class(
                missing_accounting_classes
            ),
            "review_package_command": _dv01_limit_config_review_package_command(report_date)
            if needs_business_followup
            else "",
            "dry_run_command": _dv01_limit_config_dry_run_command(report_date)
            if needs_business_followup
            else "",
            "configured_count": configured_count,
            "missing_count": missing_count,
            "invalid_count": invalid_count,
            "rows": [row.model_dump(mode="json") for row in rows],
            "computed_at": datetime.now(UTC).isoformat(),
            "warnings": warnings,
        }
    )
    return build_formal_result_envelope_from_lineage(
        trace_id=_trace_id(),
        result_kind="bond_analytics.dv01_limit_config_status",
        lineage=_lineage(report_date.isoformat(), []),
        default_cache_version=CACHE_VERSION,
        source_surface="bond_analytics",
        result_payload=payload.model_dump(mode="json"),
    )


def _dv01_limit_config_missing_business_fields_by_class(
    accounting_classes: list[str],
) -> dict[str, list[str]]:
    return {accounting_class: list(DV01_LIMIT_CONFIG_BUSINESS_FIELDS) for accounting_class in accounting_classes}


def _dv01_limit_config_review_package_command(report_date: date) -> str:
    report_date_text = report_date.isoformat()
    return (
        "python -m backend.app.tasks.bond_dv01_limit_config_import "
        f"--review-package-dir .tmp\\bond_dv01_limit_config_review_package --report-date {report_date_text}"
    )


def _dv01_limit_config_dry_run_command(report_date: date) -> str:
    report_date_text = report_date.isoformat()
    return (
        "python -m backend.app.tasks.bond_dv01_limit_config_import "
        f"--config-path .tmp\\bond_dv01_limit_config_review_package\\bond_dv01_limit_config_review_{report_date_text}.csv "
        f"--report-date {report_date_text} --dry-run"
    )


def _dv01_limit_config_acceptance_guidance(
    *,
    missing_accounting_classes: list[str],
    invalid_accounting_classes: list[str],
) -> tuple[str, str]:
    if not missing_accounting_classes and not invalid_accounting_classes:
        return (
            "正式 DV01 限额配置验收通过。",
            "无需补充配置；动作计划将按正式限额口径计算。",
        )
    details: list[str] = []
    if missing_accounting_classes:
        details.append(f"待补分类：{', '.join(missing_accounting_classes)}")
    if invalid_accounting_classes:
        details.append(f"无效分类：{', '.join(invalid_accounting_classes)}")
    fields = "、".join(DV01_LIMIT_CONFIG_REQUIRED_FIELDS)
    classes = ", ".join(missing_accounting_classes + invalid_accounting_classes)
    return (
        f"正式 DV01 限额配置验收未通过；{'；'.join(details)}。",
        f"请在 {DV01_LIMIT_CONFIG_STREAM} 治理流补齐 {classes} 的 {fields}。",
    )


def _build_dv01_limit_config_status_row(
    report_date: date,
    accounting_class: str,
) -> DV01LimitConfigStatusRow:
    candidate = _resolve_dv01_limit_config_candidate(
        report_date=report_date,
        accounting_class=accounting_class,
        allow_all_fallback=False,
    )
    if candidate is None:
        return _dv01_limit_config_status_row(
            accounting_class=accounting_class,
            status="missing",
            message="未找到正式 DV01 限额配置。",
        )
    config, message = candidate
    if config is None:
        return _dv01_limit_config_status_row(
            accounting_class=accounting_class,
            status="invalid",
            message=message,
        )
    return _dv01_limit_config_status_row(
        accounting_class=accounting_class,
        status="ready",
        limit_dv01=config.limit_dv01,
        warning_dv01=config.warning_dv01,
        hedge_target_dv01=config.hedge_target_dv01,
        limit_source=config.limit_source,
        limit_source_version=config.limit_source_version,
        limit_rule_version=config.limit_rule_version,
        limit_effective_date=config.limit_effective_date,
        message="已接入正式 DV01 限额。",
    )


def _dv01_limit_config_status_row(
    *,
    accounting_class: str,
    status: Literal["ready", "missing", "invalid"],
    message: str,
    limit_dv01: Decimal = ZERO,
    warning_dv01: Decimal = ZERO,
    hedge_target_dv01: Decimal = ZERO,
    limit_source: str = "unconfigured",
    limit_source_version: str = "unconfigured",
    limit_rule_version: str = "unconfigured",
    limit_effective_date: date | None = None,
) -> DV01LimitConfigStatusRow:
    return DV01LimitConfigStatusRow.model_validate(
        promote_flat_payload(
            {
                "accounting_class": accounting_class,
                "status": status,
                "limit_dv01": limit_dv01,
                "warning_dv01": warning_dv01,
                "hedge_target_dv01": hedge_target_dv01,
                "limit_source": limit_source,
                "limit_source_version": limit_source_version,
                "limit_rule_version": limit_rule_version,
                "limit_effective_date": limit_effective_date,
                "message": message,
            },
            DV01LimitConfigStatusRow,
        )
    )


def _resolve_dv01_limit_config(
    *,
    report_date: date,
    accounting_class: str,
) -> _DV01LimitConfig | None:
    candidate = _resolve_dv01_limit_config_candidate(
        report_date=report_date,
        accounting_class=accounting_class,
    )
    if candidate is None:
        return None
    return candidate[0]


def _resolve_dv01_limit_config_candidate(
    *,
    report_date: date,
    accounting_class: str,
    allow_all_fallback: bool = True,
) -> tuple[_DV01LimitConfig | None, str] | None:
    try:
        records = GovernanceRepository(base_dir=get_settings().governance_path).read_all(
            DV01_LIMIT_CONFIG_STREAM
        )
    except (OSError, ValueError):
        logger.exception("Failed to read DV01 limit config governance stream")
        return None

    scoped: list[tuple[int, date, int, _DV01LimitConfig | None, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        record_class = _normalize_limit_config_accounting_class(record.get("accounting_class"))
        allowed_classes = {accounting_class, "all"} if allow_all_fallback else {accounting_class}
        if record_class not in allowed_classes:
            continue
        effective_date = _parse_limit_effective_date(record)
        if effective_date is None or effective_date > report_date:
            continue
        limit = safe_decimal(record.get("limit_dv01"))
        if limit <= ZERO:
            scoped.append((1 if record_class == accounting_class else 0, effective_date, index, None, "limit_dv01 必须大于 0。"))
            continue
        warning = _positive_decimal_or_default(record.get("warning_dv01"), limit)
        if warning > limit:
            warning = limit
        hedge_target = _positive_decimal_or_default(record.get("hedge_target_dv01"), warning)
        if hedge_target > limit:
            hedge_target = warning
        source_version = str(record.get("limit_source_version") or record.get("source_version") or "").strip()
        rule_version = str(record.get("limit_rule_version") or record.get("rule_version") or "").strip()
        limit_source = str(record.get("limit_source") or "governance_config").strip()
        if not source_version or not rule_version:
            scoped.append((1 if record_class == accounting_class else 0, effective_date, index, None, "limit_source_version 和 limit_rule_version 必须配置。"))
            continue
        specificity = 1 if record_class == accounting_class else 0
        scoped.append(
            (
                specificity,
                effective_date,
                index,
                _DV01LimitConfig(
                    limit_dv01=limit,
                    warning_dv01=warning,
                    hedge_target_dv01=hedge_target,
                    limit_source=limit_source,
                    limit_source_version=source_version,
                    limit_rule_version=rule_version,
                    limit_effective_date=effective_date,
                ),
                "已接入正式 DV01 限额。",
            )
        )
    if not scoped:
        return None
    selected = max(scoped, key=lambda item: (item[0], item[1], item[2]))
    return selected[3], selected[4]


def _normalize_limit_config_accounting_class(value: object) -> str:
    try:
        return _normalize_dv01_accounting_class(str(value or "all"))
    except ValueError:
        return ""


def _parse_limit_effective_date(record: dict[str, object]) -> date | None:
    raw = record.get("limit_effective_date") or record.get("effective_date") or record.get("report_date")
    try:
        return date.fromisoformat(str(raw or "").strip())
    except ValueError:
        return None


def _normalize_dv01_accounting_class(value: str) -> str:
    normalized = str(value or "OCI").strip().upper()
    if normalized in {"", "ALL"}:
        return "all"
    if normalized not in {"AC", "OCI", "TPL"}:
        raise ValueError("accounting_class must be one of AC, OCI, TPL, all")
    return normalized


def _dv01_scope_warnings(rows: list[dict[str, object]], accounting_class: str) -> list[str]:
    warnings: list[str] = [] if rows else [EMPTY_WARNING]
    if accounting_class != "all":
        return warnings
    unmapped_classes = sorted(
        {
            str(row.get("accounting_class") or "blank").strip() or "blank"
            for row in rows
            if str(row.get("accounting_class") or "").strip().upper() not in {"AC", "OCI", "TPL"}
        }
    )
    if unmapped_classes:
        warnings.append(
            f"{DV01_UNMAPPED_ACCOUNTING_CLASS_WARNING_PREFIX}：{', '.join(unmapped_classes)}；"
            "AC/OCI/TPL 正式分类验收不能用 all 行替代。"
        )
    return warnings


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def get_top_holdings(report_date: date, top_n: int = 20) -> dict:
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    if not rows:
        payload = BondTopHoldingsResponse.model_validate(
            promote_flat_payload(
                {
                    "report_date": report_date,
                    "top_n": top_n,
                    "items": [],
                    "total_market_value": ZERO,
                    "computed_at": datetime.now(UTC).isoformat(),
                    "warnings": [EMPTY_WARNING],
                },
                BondTopHoldingsResponse,
            )
        )
        return _build_fact_envelope(
            result_kind="bond_analytics.top_holdings",
            report_date=report_date,
            rows=rows,
            result_payload=payload.model_dump(mode="json"),
        )

    total_mv_dec = sum((safe_decimal(row.get("market_value")) for row in rows), ZERO)
    ordered = sorted(rows, key=lambda row: safe_decimal(row.get("market_value")), reverse=True)
    picked = ordered[:top_n]
    items = [
        BondTopHoldingItem.model_validate(
            promote_flat_payload(
                {
                    "instrument_code": str(row.get("instrument_code") or ""),
                    "instrument_name": (str(row["instrument_name"]).strip() or None) if row.get("instrument_name") else None,
                    "issuer_name": (str(row["issuer_name"]).strip() or None) if row.get("issuer_name") else None,
                    "rating": (str(row["rating"]).strip() or None) if row.get("rating") else None,
                    "asset_class": str(row.get("asset_class_std") or ""),
                    "market_value": safe_decimal(row.get("market_value")),
                    "face_value": safe_decimal(row.get("face_value")),
                    "ytm": safe_decimal(row.get("ytm")),
                    "modified_duration": safe_decimal(row.get("modified_duration")),
                    "weight": ZERO if total_mv_dec == ZERO else safe_decimal(row.get("market_value")) / total_mv_dec,
                },
                BondTopHoldingItem,
            )
        )
        for row in picked
    ]
    payload = BondTopHoldingsResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "top_n": top_n,
                "items": items,
                "total_market_value": total_mv_dec,
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": [],
            },
            BondTopHoldingsResponse,
        )
    )
    return _build_fact_envelope(
        result_kind="bond_analytics.top_holdings",
        report_date=report_date,
        rows=rows,
        result_payload=payload.model_dump(mode="json"),
    )


def _position_change_direction(change_market_value: Decimal) -> Literal["increase", "decrease", "flat"]:
    if change_market_value > ZERO:
        return "increase"
    if change_market_value < ZERO:
        return "decrease"
    return "flat"


def _position_change_reason(
    *,
    previous_market_value: Decimal,
    current_market_value: Decimal,
    change_market_value: Decimal,
) -> str:
    if previous_market_value == ZERO and current_market_value > ZERO:
        return "新增"
    if previous_market_value > ZERO and current_market_value == ZERO:
        return "清仓"
    if change_market_value > ZERO:
        return "增持"
    if change_market_value < ZERO:
        return "减持"
    return "持平"


def _position_change_item(
    *,
    instrument_code: str,
    current_row: dict[str, object] | None,
    previous_row: dict[str, object] | None,
    total_market_value: Decimal,
    prev_total_market_value: Decimal,
) -> BondPositionChangeItem:
    row = current_row or previous_row or {}
    current_market_value = safe_decimal((current_row or {}).get("market_value"))
    previous_market_value = safe_decimal((previous_row or {}).get("market_value"))
    change_market_value = current_market_value - previous_market_value
    current_weight = ZERO if total_market_value == ZERO else current_market_value / total_market_value
    previous_weight = ZERO if prev_total_market_value == ZERO else previous_market_value / prev_total_market_value
    return BondPositionChangeItem.model_validate(
        promote_flat_payload(
            {
                "instrument_code": instrument_code,
                "instrument_name": _optional_text(row.get("instrument_name")),
                "issuer_name": _optional_text(row.get("issuer_name")),
                "rating": _optional_text(row.get("rating")),
                "asset_class": str(row.get("asset_class_std") or row.get("asset_class") or ""),
                "previous_market_value": previous_market_value,
                "current_market_value": current_market_value,
                "change_market_value": change_market_value,
                "previous_weight": previous_weight,
                "current_weight": current_weight,
                "change_weight": current_weight - previous_weight,
                "direction": _position_change_direction(change_market_value),
                "reason_label": _position_change_reason(
                    previous_market_value=previous_market_value,
                    current_market_value=current_market_value,
                    change_market_value=change_market_value,
                ),
                "source_status": "ready",
            },
            BondPositionChangeItem,
        )
    )


def get_position_changes(report_date: date, top_n: int = 5) -> dict:
    repo = _repo()
    current_rows = repo.fetch_bond_analytics_rows(report_date=report_date.isoformat())
    prev_report_date = _resolve_prior_bond_snapshot_date(repo, report_date.isoformat())
    previous_rows = repo.fetch_bond_analytics_rows(report_date=prev_report_date) if prev_report_date else []
    total_market_value = sum((safe_decimal(row.get("market_value")) for row in current_rows), ZERO)
    prev_total_market_value = sum((safe_decimal(row.get("market_value")) for row in previous_rows), ZERO)

    warnings: list[str] = []
    if not current_rows:
        warnings.append(EMPTY_WARNING)
    if not prev_report_date:
        warnings.append("No prior bond analytics report date available; position changes cannot be computed.")
    elif not previous_rows:
        warnings.append("Prior bond analytics snapshot is empty; position changes cannot be computed.")

    if not current_rows or not previous_rows:
        payload = BondPositionChangesResponse.model_validate(
            promote_flat_payload(
                {
                    "report_date": report_date,
                    "prev_report_date": date.fromisoformat(prev_report_date) if prev_report_date else None,
                    "top_n": top_n,
                    "source_status": "empty",
                    "items": [],
                    "total_market_value": total_market_value,
                    "prev_total_market_value": prev_total_market_value,
                    "computed_at": datetime.now(UTC).isoformat(),
                    "warnings": warnings,
                },
                BondPositionChangesResponse,
            )
        )
        return _build_numeric_fact_envelope(
            result_kind="bond_analytics.position_changes",
            report_date=report_date,
            rows=[*current_rows, *previous_rows],
            result_payload=payload.model_dump(mode="json"),
        )

    by_current = {str(row.get("instrument_code") or "").strip(): row for row in current_rows}
    by_previous = {str(row.get("instrument_code") or "").strip(): row for row in previous_rows}
    instrument_codes = sorted((set(by_current) | set(by_previous)) - {""})
    all_items = [
        _position_change_item(
            instrument_code=instrument_code,
            current_row=by_current.get(instrument_code),
            previous_row=by_previous.get(instrument_code),
            total_market_value=total_market_value,
            prev_total_market_value=prev_total_market_value,
        )
        for instrument_code in instrument_codes
    ]
    changed_items = [
        item
        for item in all_items
        if safe_decimal(item.change_market_value.raw) != ZERO
    ]
    ordered = sorted(
        changed_items,
        key=lambda item: (
            safe_decimal(item.change_market_value.raw).copy_abs(),
            safe_decimal(item.change_market_value.raw),
            item.instrument_code,
        ),
        reverse=True,
    )
    payload = BondPositionChangesResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "prev_report_date": date.fromisoformat(prev_report_date),
                "top_n": top_n,
                "source_status": "ready",
                "items": ordered[:top_n],
                "total_market_value": total_market_value,
                "prev_total_market_value": prev_total_market_value,
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": [],
            },
            BondPositionChangesResponse,
        )
    )
    return _build_numeric_fact_envelope(
        result_kind="bond_analytics.position_changes",
        report_date=report_date,
        rows=[*current_rows, *previous_rows],
        result_payload=payload.model_dump(mode="json"),
    )


def get_accounting_class_audit(report_date: date) -> dict:
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    audit = summarize_accounting_audit(rows)
    payload = AccountingClassAuditResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "total_positions": int(audit["total_positions"]),
                "total_market_value": audit["total_market_value"],
                "distinct_asset_classes": int(audit["distinct_asset_classes"]),
                "divergent_asset_classes": int(audit["divergent_asset_classes"]),
                "divergent_position_count": int(audit["divergent_position_count"]),
                "divergent_market_value": audit["divergent_market_value"],
                "map_unclassified_asset_classes": int(audit["map_unclassified_asset_classes"]),
                "map_unclassified_position_count": int(audit["map_unclassified_position_count"]),
                "map_unclassified_market_value": audit["map_unclassified_market_value"],
                "rows": [
                    AccountingClassAuditItem.model_validate(
                        promote_flat_payload(
                            {
                                "asset_class": str(row["asset_class_raw"]),
                                "position_count": int(row["position_count"]),
                                "market_value": row["market_value"],
                                "market_value_weight": row["market_value_weight"],
                                "infer_accounting_class": str(row["infer_accounting_class"]),
                                "map_accounting_class": str(row["map_accounting_class"]),
                                "infer_rule_id": str(row["infer_rule_id"]),
                                "infer_match": row["infer_match"],
                                "map_rule_id": str(row["map_rule_id"]),
                                "map_match": row["map_match"],
                                "is_divergent": bool(row["is_divergent"]),
                                "is_map_unclassified": bool(row["is_map_unclassified"]),
                            },
                            AccountingClassAuditItem,
                        )
                    )
                    for row in audit["rows"]
                ],
                "computed_at": datetime.now(UTC).isoformat(),
                "warnings": [EMPTY_WARNING] if not rows else [],
            },
            AccountingClassAuditResponse,
        )
    )
    return _build_fact_envelope(
        result_kind="bond_analytics.accounting_class_audit",
        report_date=report_date,
        rows=rows,
        result_payload=payload.model_dump(mode="json"),
    )


def _build_action_attribution_placeholder_response(
    *,
    report_date: date,
    period_type: str,
) -> dict:
    """Build placeholder response when no data or computation fails."""
    analysis_envelope = build_bond_action_attribution_placeholder_envelope(
        AnalysisQuery(
            consumer="bond_analytics.action_attribution",
            analysis_key="bond_action_attribution",
            report_date=report_date.isoformat(),
            basis="formal",
            view=period_type,
        )
    )
    summary = analysis_envelope.result.summary
    payload = build_action_attribution_placeholder_payload(
        report_date=report_date,
        summary=summary,
        facets=analysis_envelope.result.facets,
        warnings=[warning.model_dump(mode="python") for warning in analysis_envelope.result.warnings],
        generated_at=analysis_envelope.result_meta.generated_at.isoformat(),
        default_status=str(ActionAttributionResponse.model_fields["status"].default),
    )
    response = ActionAttributionResponse.model_validate(
        promote_flat_payload(
            payload,
            ActionAttributionResponse,
        )
    )
    formal_meta = analysis_envelope.result_meta.model_copy(update={"source_surface": "bond_analytics"})
    candidate_meta = _action_attribution_candidate_meta(
        formal_meta=formal_meta,
        report_date=report_date,
        quality_flag="warning",
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope(
            result_meta=candidate_meta,
            result_payload=_bond_analytics_api_payload(response.model_dump(mode="json")),
        ),
        rows=[],
    )


def _fetch_action_attribution_snapshots(
    *,
    repo: BondAnalyticsRepository,
    period_end: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]], str | None]:
    """Fetch current and prior bond snapshots for action attribution."""
    rows_end = repo.fetch_bond_analytics_rows(report_date=period_end)
    prior_rd = _resolve_prior_bond_snapshot_date(repo, period_end)
    rows_start = repo.fetch_bond_analytics_rows(report_date=prior_rd) if prior_rd else []
    return rows_end, rows_start, prior_rd


def _build_action_attribution_success_response(
    *,
    report_date: date,
    period_type: str,
    raw: dict[str, object],
    rows_end: list[dict[str, object]],
    prior_rd: str | None,
    pnl_by_key: dict[str, Decimal],
    pnl_warn_codes: list[str],
) -> dict:
    """Build success response from computed action attribution."""
    meta = _meta("bond_analytics.action_attribution", report_date, rows_end)
    payload = build_action_attribution_success_payload(
        report_date=report_date,
        period_type=period_type,
        raw=raw,
        prior_snapshot_date=prior_rd,
        pnl_by_key=pnl_by_key,
        pnl_warning_codes=pnl_warn_codes,
        computed_at=meta.generated_at.isoformat(),
    )
    response = ActionAttributionResponse.model_validate(
        promote_flat_payload(
            payload,
            ActionAttributionResponse,
        )
    )
    meta_adj = meta.model_copy(update={"quality_flag": "warning" if payload["warnings"] else "ok"})
    candidate_meta = _action_attribution_candidate_meta(
        formal_meta=meta_adj,
        report_date=report_date,
        quality_flag=meta_adj.quality_flag,
    )
    return _with_bond_amount_disclosure(
        build_formal_result_envelope(
            result_meta=candidate_meta,
            result_payload=_bond_analytics_api_payload(response.model_dump(mode="json")),
        ),
        rows=rows_end,
    )


def get_action_attribution(report_date: date, period_type: str = "MoM") -> dict:
    _cache_key = (report_date.isoformat(), period_type)
    hit, cached = _action_attribution_cache.get(_cache_key)
    if hit:
        return cached

    period_start, period_end = resolve_period(report_date, period_type)
    repo = _repo()
    rows_end, rows_start, prior_rd = _fetch_action_attribution_snapshots(
        repo=repo, period_end=period_end.isoformat()
    )
    if not rows_end:
        return _build_action_attribution_placeholder_response(
            report_date=report_date, period_type=period_type
        )

    pnl_repo = PnlRepository(str(get_settings().duckdb_path))
    pnl_by_key, pnl_warn_codes = _build_action_attribution_pnl_by_key(
        pnl_repo,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
    )

    try:
        raw = compute_action_attribution_bonds(
            period_start=period_start,
            period_end=period_end,
            positions_start=[bond_analytics_action_line_payload(r) for r in rows_start],
            positions_end=[bond_analytics_action_line_payload(r) for r in rows_end],
            pnl_by_key=pnl_by_key,
        )
    except Exception:
        logger.exception(
            "Action attribution computation failed for report_date=%s period_type=%s, returning placeholder",
            report_date, period_type,
        )
        return _build_action_attribution_placeholder_response(
            report_date=report_date, period_type=period_type
        )

    result = _build_action_attribution_success_response(
        report_date=report_date,
        period_type=period_type,
        raw=raw,
        rows_end=rows_end,
        prior_rd=prior_rd,
        pnl_by_key=pnl_by_key,
        pnl_warn_codes=pnl_warn_codes,
    )
    _action_attribution_cache.set(_cache_key, result)
    return result


def _refresh_trigger_lock(*, report_date: str) -> LockDefinition:
    return LockDefinition(
        key=f"{BOND_ANALYTICS_LOCK.key}:{report_date}:trigger",
        ttl_seconds=30,
    )


def _load_refresh_run_records(settings: Settings) -> list[dict[str, object]]:
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key")) == CACHE_KEY
        and str(record.get("job_name")) == JOB_NAME
    ]


def _normalize_idempotency_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _latest_refresh_for_idempotency_key(
    settings: Settings,
    *,
    report_date: str,
    idempotency_key: str,
) -> dict[str, object] | None:
    for record in reversed(_load_refresh_run_records(settings)):
        if str(record.get("report_date")) != report_date:
            continue
        if str(record.get("idempotency_key") or "").strip() != idempotency_key:
            continue
        if str(record.get("status")) in IN_FLIGHT_STATUSES and _is_stale_inflight_record(record):
            _mark_stale_inflight_run(
                settings=settings,
                run_id=str(record.get("run_id")),
                report_date=report_date,
                error_message="Marked stale bond analytics idempotent refresh run as failed.",
            )
            refreshed_records = _load_refresh_run_records(settings)
            return next(
                (
                    refreshed
                    for refreshed in reversed(refreshed_records)
                    if str(refreshed.get("run_id")) == str(record.get("run_id"))
                ),
                record,
            )
        return record
    return None


def _idempotent_refresh_response(record: dict[str, object]) -> dict[str, object]:
    status = str(record.get("status") or "queued")
    return {
        **record,
        "status": status,
        "run_id": str(record.get("run_id") or ""),
        "job_name": JOB_NAME,
        "trigger_mode": "async" if status in IN_FLIGHT_STATUSES else "terminal",
        "cache_key": CACHE_KEY,
        "idempotency_replay": True,
    }


def _latest_inflight_refresh(settings: Settings, *, report_date: str) -> dict[str, object] | None:
    by_run_id: dict[str, dict[str, object]] = {}
    for record in _load_refresh_run_records(settings):
        if str(record.get("report_date")) != report_date:
            continue
        by_run_id[str(record.get("run_id"))] = record
    stale_records: list[dict[str, object]] = []
    for record in reversed(list(by_run_id.values())):
        if str(record.get("status")) in IN_FLIGHT_STATUSES:
            if _is_stale_inflight_record(record):
                stale_records.append(record)
                continue
            return record
    for record in stale_records:
        _mark_stale_inflight_run(
            settings=settings,
            run_id=str(record.get("run_id")),
            report_date=report_date,
            error_message="Marked stale bond analytics refresh run as failed.",
        )
    return None


def _is_stale_inflight_record(record: dict[str, object]) -> bool:
    for field_name in ("started_at", "queued_at", "created_at"):
        raw_value = str(record.get(field_name) or "").strip()
        if not raw_value:
            continue
        timestamp = _parse_timestamp(raw_value)
        return datetime.now(UTC) - timestamp > STALE_IN_FLIGHT_AFTER
    return True


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _record_dispatch_failure(
    *,
    settings: Settings,
    run_id: str,
    report_date: str,
    error_message: str,
) -> None:
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": JOB_NAME,
            "status": "failed",
            "cache_key": CACHE_KEY,
            "lock": BOND_ANALYTICS_LOCK.key,
            "source_version": "sv_bond_analytics_failed",
            "vendor_version": "vv_none",
            "report_date": report_date,
            "error_message": error_message,
        },
    )


def _mark_stale_inflight_run(
    *,
    settings: Settings,
    run_id: str,
    report_date: str,
    error_message: str,
) -> None:
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": JOB_NAME,
            "status": "failed",
            "cache_key": CACHE_KEY,
            "lock": BOND_ANALYTICS_LOCK.key,
            "source_version": "sv_bond_analytics_stale",
            "vendor_version": "vv_none",
            "report_date": report_date,
            "error_message": error_message,
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )


def _build_run_id() -> str:
    return f"{JOB_NAME}:{datetime.now(UTC).isoformat()}"
