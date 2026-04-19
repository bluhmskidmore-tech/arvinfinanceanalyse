"""Bond analytics service — orchestrates fact reads and delegates finance logic to core_finance."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from backend.app.governance.formal_compute_lineage import (
    resolve_formal_dates_lineage,
    resolve_formal_facts_lineage,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings, get_settings
from backend.app.core_finance.action_attribution import compute_action_attribution_bonds
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
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
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
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM, GovernanceRepository
from backend.app.schemas.analysis_service import AnalysisQuery
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.schemas.bond_analytics import (
    AccountingClassAuditItem,
    AccountingClassAuditResponse,
    ActionAttributionResponse,
    ActionDetail,
    ActionTypeSummary,
    AssetClassBreakdown,
    AssetClassRiskSummary,
    BenchmarkExcessResponse,
    BondLevelDecomposition,
    BondTopHoldingItem,
    BondTopHoldingsResponse,
    ConcentrationItem,
    ConcentrationMetrics,
    CreditSpreadMigrationResponse,
    KRDBucket,
    KRDCurveRiskResponse,
    PortfolioHeadlinesResponse,
    ReturnDecompositionResponse,
    ScenarioResult,
    SpreadScenarioResult,
)
from backend.app.services.analysis_adapters import build_bond_action_attribution_placeholder_envelope
from backend.app.services.explicit_numeric import numeric_json, promote_flat_payload
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_envelope_from_lineage,
    build_formal_result_meta,
    build_formal_result_meta_from_lineage,
)
from backend.app.tasks.bond_analytics_materialize import (
    BOND_ANALYTICS_LOCK,
    CACHE_KEY,
    CACHE_VERSION,
    RULE_VERSION,
    materialize_bond_analytics_facts,
)
from backend.app.tasks.yield_curve_materialize import ensure_yield_curve_inputs_on_or_before
from backend.app.tasks.yield_curve_materialize import CACHE_VERSION as YIELD_CURVE_CACHE_VERSION

JOB_NAME = "bond_analytics_materialize"
EMPTY_SOURCE_VERSION = "sv_bond_analytics_empty"
EMPTY_WARNING = "DuckDB bond analytics fact table not yet populated — returning empty result"
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


def _repo() -> BondAnalyticsRepository:
    return BondAnalyticsRepository(str(get_settings().duckdb_path))


def _pnl_position_key_from_bond_row(row: dict[str, object]) -> str:
    inst = str(row.get("instrument_code") or "").strip()
    pn = str(row.get("portfolio_name") or "").strip()
    cc = str(row.get("cost_center") or "").strip()
    return f"{inst}::{pn}::{cc}"


def _action_attribution_bond_line(row: dict[str, object]) -> dict[str, object]:
    pn = str(row.get("portfolio_name") or "").strip()
    cc = str(row.get("cost_center") or "").strip()
    return {
        "bond_code": str(row.get("instrument_code") or "").strip(),
        "book_id": f"{pn}::{cc}",
        "market_value": row.get("market_value"),
        "modified_duration": row.get("modified_duration"),
        "asset_class": str(row.get("asset_class_std") or row.get("accounting_class") or ""),
    }


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
    codes: list[str] = []
    if period_type == "MoM":
        return [period_end.isoformat()], codes
    selected: list[str] = []
    for raw in pnl_repo.list_union_report_dates():
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
    by_ac, by_acc = rebucket_return_decomposition(bond_rows)
    summary["by_asset_class"] = by_ac
    summary["by_accounting_class"] = by_acc

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


def _meta(result_kind: str, report_date: date, rows: list[dict[str, object]]):
    lineage = _lineage(report_date.isoformat(), rows)
    return build_formal_result_meta_from_lineage(
        trace_id=_trace_id(),
        result_kind=result_kind,
        lineage=lineage,
        default_cache_version=CACHE_VERSION,
        source_surface="bond_analytics",
    )


def _build_fact_envelope(
    *,
    result_kind: str,
    report_date: date,
    rows: list[dict[str, object]],
    result_payload: dict[str, object],
) -> dict[str, object]:
    return build_formal_result_envelope_from_lineage(
        trace_id=_trace_id(),
        result_kind=result_kind,
        lineage=_lineage(report_date.isoformat(), rows),
        default_cache_version=CACHE_VERSION,
        source_surface="bond_analytics",
        result_payload=result_payload,
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


def refresh_bond_analytics(settings: Settings, *, report_date: str) -> dict[str, object]:
    try:
        with acquire_lock(
            _refresh_trigger_lock(report_date=report_date),
            base_dir=settings.governance_path,
            timeout_seconds=0.1,
        ):
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
            queued_at = datetime.now(timezone.utc).isoformat()
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
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


def _fetch_fx_rates(
    curve_repo: "YieldCurveRepository",
    *,
    current_date: str,
    prior_date: str,
) -> tuple[
    "dict[str, Decimal] | None",
    "str | None",
    "dict[str, Decimal] | None",
    "str | None",
]:
    """Fetch FX rates for both period dates in one place. Returns (current, current_warning, prior, prior_warning)."""
    fx_current, fx_current_warning = curve_repo.fetch_fx_rates_with_fallback_warning(current_date)
    fx_prior, fx_prior_warning = curve_repo.fetch_fx_rates_with_fallback_warning(prior_date)
    return fx_current or None, fx_current_warning, fx_prior or None, fx_prior_warning


def _fetch_all_curve_pairs(
    rows: list[dict[str, object]],
    *,
    curve_repo: "YieldCurveRepository",
    report_date: str,
    prior_date: str,
    extra_curve_types: "set[str] | None" = None,
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


def _build_asset_class_breakdown(row: dict[str, object]) -> "AssetClassBreakdown":
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


def _build_bond_level_decomposition(row: dict[str, object]) -> "BondLevelDecomposition":
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
    fx_current_warning: "str | None",
    fx_prior_warning: "str | None",
    fx_missing_warnings: list[str],
    trading_extra_warnings: list[str] | None = None,
    warnings_detail: list[dict[str, str]] | None = None,
) -> "ReturnDecompositionResponse":
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


def get_return_decomposition(report_date: date, period_type: str = "MoM", asset_class: str = "all", accounting_class: str = "all") -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat(), asset_class=asset_class, accounting_class=accounting_class)
    if not rows:
        meta = _meta("bond_analytics.return_decomposition", report_date, rows)
        return _empty_return_response(meta, report_date, period_type, period_start, period_end)

    curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
    fx_rates_current, fx_current_warning, fx_rates_prior, fx_prior_warning = _fetch_fx_rates(
        curve_repo, current_date=report_date.isoformat(), prior_date=period_start.isoformat()
    )
    curves = _fetch_all_curve_pairs(
        rows, curve_repo=curve_repo,
        report_date=report_date.isoformat(), prior_date=period_start.isoformat(),
    )
    fx_unavailable = _fx_unavailable_for_return_rows(rows, fx_rates_current=fx_rates_current, fx_rates_prior=fx_rates_prior)
    fx_latest_fallback = any(
        w and FX_LATEST_FALLBACK_PREFIX in w for w in (fx_current_warning, fx_prior_warning)
    )
    fx_missing_warnings = _fx_missing_warnings_for_return_rows(
        rows, report_date=report_date.isoformat(), prior_date=period_start.isoformat(),
        fx_rates_current=fx_rates_current, fx_rates_prior=fx_rates_prior,
    )

    meta = _meta("bond_analytics.return_decomposition", report_date, rows)
    meta = _apply_vendor_meta_update(
        meta,
        curve_snapshots=curves["curve_snapshots"],
        cache_version_suffix=YIELD_CURVE_CACHE_VERSION,
        curve_unavailable=curves["curve_unavailable"],
        curve_latest_fallback=curves["curve_latest_fallback"],
        fx_unavailable=fx_unavailable,
        fx_latest_fallback=fx_latest_fallback,
    )

    treasury_current = curves["treasury_current"]
    treasury_prior = curves["treasury_prior"]
    cdb_current = curves["cdb_current"]
    cdb_prior = curves["cdb_prior"]
    aaa_current = curves["aaa_current"]
    aaa_prior = curves["aaa_prior"]

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
        fx_rates_current=fx_rates_current,
        fx_rates_prior=fx_rates_prior,
    )
    summary, trading_extra_warnings, trading_wd = _overlay_return_decomposition_trading_pnl517(
        summary,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        duckdb_path=str(get_settings().duckdb_path),
    )
    payload = _build_return_decomposition_payload(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        meta=meta,
        relevant_curve_warnings=curves["relevant_curve_warnings"],
        fx_current_warning=fx_current_warning,
        fx_prior_warning=fx_prior_warning,
        fx_missing_warnings=fx_missing_warnings,
        trading_extra_warnings=trading_extra_warnings,
        warnings_detail=trading_wd,
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


def _resolve_curve_for_service(
    *,
    repo: YieldCurveRepository,
    requested_trade_date: str,
    curve_type: str,
) -> tuple[dict[str, object] | None, str | None]:
    exact_snapshot = repo.fetch_curve_snapshot(requested_trade_date, curve_type)
    if exact_snapshot is not None:
        return exact_snapshot, None
    if repo.fetch_curve(requested_trade_date, curve_type):
        raise RuntimeError(
            f"Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date={requested_trade_date}."
        )
    latest_trade_date = repo.fetch_latest_trade_date_on_or_before(curve_type, requested_trade_date)
    if latest_trade_date is None:
        return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}; affected components remain 0."
    latest_snapshot = repo.fetch_curve_snapshot(latest_trade_date, curve_type)
    if latest_snapshot is None:
        if repo.fetch_curve(latest_trade_date, curve_type):
            raise RuntimeError(
                f"Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date={latest_trade_date}."
            )
        return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}; affected components remain 0."
    return (
        latest_snapshot,
        format_yield_curve_latest_fallback_warning(
            curve_type=curve_type,
            resolved_trade_date=latest_trade_date,
            requested_trade_date=requested_trade_date,
        ),
    )


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
    curve_repo: "YieldCurveRepository",
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
) -> "BenchmarkExcessResponse":
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


def get_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    meta = _meta("bond_analytics.benchmark_excess", report_date, rows)

    if not rows:
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
        return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))

    curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
    curves = _fetch_benchmark_curves(
        rows, curve_repo=curve_repo,
        report_date=report_date.isoformat(), prior_date=period_start.isoformat(),
        benchmark_id=benchmark_id,
    )

    meta = _apply_vendor_meta_update(
        meta,
        curve_snapshots=curves["curve_snapshots"],
        cache_version_suffix=YIELD_CURVE_CACHE_VERSION,
        curve_unavailable=curves["curve_unavailable"],
        curve_latest_fallback=curves["curve_latest_fallback"],
    )

    treasury_current = curves["treasury_current"]
    treasury_prior = curves["treasury_prior"]
    cdb_current = curves["cdb_current"]
    cdb_prior = curves["cdb_prior"]
    aaa_current = curves["aaa_current"]
    aaa_prior = curves["aaa_prior"]
    current_curve = curves["current_curve"]
    prior_curve = curves["prior_curve"]

    summary = compute_benchmark_excess(
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

    warnings = _build_benchmark_excess_warnings(
        rows=rows, summary=summary, curves=curves,
        current_curve=current_curve, prior_curve=prior_curve,
        treasury_current=treasury_current, treasury_prior=treasury_prior,
        aaa_current=aaa_current, aaa_prior=aaa_prior,
    )
    if not _benchmark_excess_brinson_sum_matches_explained(summary):
        warnings = _ordered_unique_warnings([*warnings, BENCHMARK_EXCESS_EXPLAINED_MISMATCH])
    payload = _build_benchmark_excess_payload(
        report_date=report_date, period_type=period_type,
        period_start=period_start, period_end=period_end,
        benchmark_id=benchmark_id, summary=summary, meta=meta,
        warnings=warnings,
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


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
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


def _fetch_credit_curves(
    *,
    curve_repo: "YieldCurveRepository",
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
) -> "CreditSpreadMigrationResponse":
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
    payload = _build_credit_spread_payload(
        report_date=report_date,
        credit_rows=credit_rows,
        summary=summary,
        spread_scenarios=spread_scenarios,
        meta=meta,
        warnings=migration_warnings,
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


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


def get_portfolio_headlines(report_date: date) -> dict:
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    if not rows:
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
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                    "warnings": [EMPTY_WARNING],
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

    risk = summarize_portfolio_risk(rows)
    credit_rows = [row for row in rows if str(row.get("asset_class_std")) == "credit"]
    credit_summary = summarize_credit(
        credit_rows,
        total_rows=rows,
        aaa_credit_curve_current=None,
        treasury_curve_current=None,
    )
    conc = build_concentration(rows, field_name="issuer_name", dimension="issuer")
    ytm_dec = weighted_average_by_market_value(rows, "ytm")
    cpn_dec = weighted_average_by_market_value(rows, "coupon_rate")
    pct = Decimal("100")
    by_ac = build_asset_class_risk_summary(rows)
    payload = PortfolioHeadlinesResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "total_market_value": risk["total_market_value"],
                "weighted_ytm": ytm_dec * pct,
                "weighted_duration": risk["portfolio_modified_duration"],
                "weighted_coupon": cpn_dec * pct,
                "total_dv01": risk["portfolio_dv01"],
                "bond_count": int(risk["bond_count"]),
                "credit_weight": credit_summary["credit_weight"],
                "issuer_hhi": conc["hhi"] if conc else ZERO,
                "issuer_top5_weight": conc["top5_concentration"] if conc else ZERO,
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
                    for row in by_ac
                ],
                "computed_at": datetime.now(timezone.utc).isoformat(),
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
                    "computed_at": datetime.now(timezone.utc).isoformat(),
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
                "computed_at": datetime.now(timezone.utc).isoformat(),
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
                "computed_at": datetime.now(timezone.utc).isoformat(),
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


def get_action_attribution(report_date: date, period_type: str = "MoM") -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    repo = _repo()
    rows_end = repo.fetch_bond_analytics_rows(report_date=period_end.isoformat())
    if not rows_end:
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
        warnings = _ordered_unique_warnings([warning.message for warning in analysis_envelope.result.warnings])
        response = ActionAttributionResponse.model_validate(
            promote_flat_payload(
                {
                    "report_date": report_date,
                    "period_type": str(summary["period_type"]),
                    "period_start": date.fromisoformat(str(summary["period_start"])),
                    "period_end": date.fromisoformat(str(summary["period_end"])),
                    "total_actions": int(summary["total_actions"]),
                    "total_pnl_from_actions": summary["total_pnl_from_actions"],
                    "by_action_type": [
                        ActionTypeSummary.model_validate(promote_flat_payload(item, ActionTypeSummary))
                        for item in analysis_envelope.result.facets.get("by_action_type", [])
                    ],
                    "action_details": [
                        ActionDetail.model_validate(promote_flat_payload(item, ActionDetail))
                        for item in analysis_envelope.result.facets.get("action_details", [])
                    ],
                    "period_start_duration": summary["period_start_duration"],
                    "period_end_duration": summary["period_end_duration"],
                    "duration_change_from_actions": summary["duration_change_from_actions"],
                    "period_start_dv01": summary["period_start_dv01"],
                    "period_end_dv01": summary["period_end_dv01"],
                    "status": str(summary.get("status") or ActionAttributionResponse.model_fields["status"].default),
                    "available_components": [str(item) for item in list(summary.get("available_components") or [])],
                    "missing_inputs": [str(item) for item in list(summary.get("missing_inputs") or [])],
                    "blocked_components": [str(item) for item in list(summary.get("blocked_components") or [])],
                    "computed_at": str(summary.get("computed_at") or analysis_envelope.result_meta.generated_at.isoformat()),
                    "warnings": warnings,
                    "warnings_detail": [
                        {"code": w.code, "level": w.level, "message": w.message}
                        for w in analysis_envelope.result.warnings
                    ],
                },
                ActionAttributionResponse,
            )
        )
        return build_formal_result_envelope(
            result_meta=analysis_envelope.result_meta.model_copy(update={"source_surface": "bond_analytics"}),
            result_payload=response.model_dump(mode="json"),
        )

    prior_rd = _resolve_prior_bond_snapshot_date(repo, period_end.isoformat())
    rows_start = repo.fetch_bond_analytics_rows(report_date=prior_rd) if prior_rd else []

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
            positions_start=[_action_attribution_bond_line(r) for r in rows_start],
            positions_end=[_action_attribution_bond_line(r) for r in rows_end],
            pnl_by_key=pnl_by_key,
        )
    except Exception:
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
        warnings = _ordered_unique_warnings([warning.message for warning in analysis_envelope.result.warnings])
        response = ActionAttributionResponse.model_validate(
            promote_flat_payload(
                {
                    "report_date": report_date,
                    "period_type": str(summary["period_type"]),
                    "period_start": date.fromisoformat(str(summary["period_start"])),
                    "period_end": date.fromisoformat(str(summary["period_end"])),
                    "total_actions": int(summary["total_actions"]),
                    "total_pnl_from_actions": summary["total_pnl_from_actions"],
                    "by_action_type": [
                        ActionTypeSummary.model_validate(promote_flat_payload(item, ActionTypeSummary))
                        for item in analysis_envelope.result.facets.get("by_action_type", [])
                    ],
                    "action_details": [
                        ActionDetail.model_validate(promote_flat_payload(item, ActionDetail))
                        for item in analysis_envelope.result.facets.get("action_details", [])
                    ],
                    "period_start_duration": summary["period_start_duration"],
                    "period_end_duration": summary["period_end_duration"],
                    "duration_change_from_actions": summary["duration_change_from_actions"],
                    "period_start_dv01": summary["period_start_dv01"],
                    "period_end_dv01": summary["period_end_dv01"],
                    "status": str(summary.get("status") or ActionAttributionResponse.model_fields["status"].default),
                    "available_components": [str(item) for item in list(summary.get("available_components") or [])],
                    "missing_inputs": [str(item) for item in list(summary.get("missing_inputs") or [])],
                    "blocked_components": [str(item) for item in list(summary.get("blocked_components") or [])],
                    "computed_at": str(summary.get("computed_at") or analysis_envelope.result_meta.generated_at.isoformat()),
                    "warnings": warnings,
                    "warnings_detail": [
                        {"code": w.code, "level": w.level, "message": w.message}
                        for w in analysis_envelope.result.warnings
                    ],
                },
                ActionAttributionResponse,
            )
        )
        return build_formal_result_envelope(
            result_meta=analysis_envelope.result_meta.model_copy(update={"source_surface": "bond_analytics"}),
            result_payload=response.model_dump(mode="json"),
        )

    meta = _meta("bond_analytics.action_attribution", report_date, rows_end)
    warn_parts: list[str] = [str(w) for w in (raw.get("warnings") or [])]
    if not prior_rd:
        warn_parts.append("ACTION_ATTRIBUTION_NO_PRIOR_SNAPSHOT")
    warn_parts.extend(pnl_warn_codes)
    warn_strings = _ordered_unique_warnings(warn_parts)
    warnings_detail = [{"code": w, "level": "warning", "message": w} for w in warn_strings]

    missing_inputs: list[str] = []
    if not pnl_by_key:
        missing_inputs.append("fact_formal_pnl_fi_capital_gain_517")

    response = ActionAttributionResponse.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date,
                "period_type": period_type,
                "period_start": date.fromisoformat(str(raw["period_start"])),
                "period_end": date.fromisoformat(str(raw["period_end"])),
                "total_actions": int(raw["total_actions"]),
                "total_pnl_from_actions": raw["total_pnl_from_actions"],
                "by_action_type": [
                    ActionTypeSummary.model_validate(promote_flat_payload(item, ActionTypeSummary))
                    for item in raw.get("by_action_type", [])
                ],
                "action_details": [
                    ActionDetail.model_validate(promote_flat_payload(item, ActionDetail))
                    for item in raw.get("action_details", [])
                ],
                "period_start_duration": raw["period_start_duration"],
                "period_end_duration": raw["period_end_duration"],
                "duration_change_from_actions": raw["duration_change_from_actions"],
                "period_start_dv01": raw["period_start_dv01"],
                "period_end_dv01": raw["period_end_dv01"],
                "status": "ready",
                "available_components": ["snapshot_diff", "capital_gain_517_allocation"],
                "missing_inputs": missing_inputs,
                "blocked_components": [],
                "computed_at": meta.generated_at.isoformat(),
                "warnings": _ordered_unique_warnings(warn_strings),
                "warnings_detail": warnings_detail,
            },
            ActionAttributionResponse,
        )
    )
    meta_adj = meta.model_copy(update={"quality_flag": "warning" if warn_strings else "ok"})
    return build_formal_result_envelope(
        result_meta=meta_adj,
        result_payload=response.model_dump(mode="json"),
    )


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
        return datetime.now(timezone.utc) - timestamp > STALE_IN_FLIGHT_AFTER
    return True


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _build_run_id() -> str:
    return f"{JOB_NAME}:{datetime.now(timezone.utc).isoformat()}"
