"""Bond analytics service — orchestrates fact reads and delegates finance logic to core_finance."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from backend.app.governance.formal_compute_lineage import resolve_formal_manifest_lineage
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings, get_settings
from backend.app.core_finance.bond_analytics.common import (
    STANDARD_SCENARIOS,
    infer_curve_type,
    resolve_period,
)
from backend.app.core_finance.bond_analytics.read_models import (
    build_asset_class_risk_summary,
    build_concentration,
    build_curve_scenarios,
    build_krd_distribution,
    compute_benchmark_excess,
    rating_aa_and_below_portfolio_weight,
    summarize_accounting_audit,
    summarize_credit,
    summarize_portfolio_risk,
    summarize_return_decomposition,
)
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
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
    ConcentrationItem,
    ConcentrationMetrics,
    CreditSpreadMigrationResponse,
    KRDBucket,
    KRDCurveRiskResponse,
    ReturnDecompositionResponse,
    ScenarioResult,
    SpreadScenarioResult,
)
from backend.app.services.analysis_adapters import build_bond_action_attribution_placeholder_envelope
from backend.app.services.formal_result_runtime import build_formal_result_envelope, build_formal_result_meta
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


def _lineage(report_date: str, rows: list[dict[str, object]]) -> dict[str, str]:
    governance = GovernanceRepository(base_dir=get_settings().governance_path)
    build_rows = [
        row
        for row in governance.read_all(CACHE_BUILD_RUN_STREAM)
        if str(row.get("cache_key")) == CACHE_KEY
        and str(row.get("job_name")) == JOB_NAME
        and str(row.get("status")) == "completed"
        and str(row.get("report_date")) == report_date
    ]
    if not rows and not build_rows:
        return {
            "source_version": EMPTY_SOURCE_VERSION,
            "rule_version": RULE_VERSION,
            "cache_version": CACHE_VERSION,
            "vendor_version": "vv_none",
        }
    manifest_rows = [row for row in governance.read_all(CACHE_MANIFEST_STREAM) if str(row.get("cache_key")) == CACHE_KEY]
    latest_build = build_rows[-1] if build_rows else {}
    latest_manifest = manifest_rows[-1] if manifest_rows else {}
    row_source_versions = sorted({str(row.get("source_version") or "").strip() for row in rows if str(row.get("source_version") or "").strip()})
    return {
        "source_version": next(
            (value for value in (str(latest_build.get("source_version") or "").strip(), "__".join(row_source_versions), EMPTY_SOURCE_VERSION) if value),
            EMPTY_SOURCE_VERSION,
        ),
        "rule_version": next(
            (value for value in (str(latest_build.get("rule_version") or "").strip(), str(latest_manifest.get("rule_version") or "").strip(), RULE_VERSION) if value),
            RULE_VERSION,
        ),
        "cache_version": next(
            (value for value in (str(latest_build.get("cache_version") or "").strip(), str(latest_manifest.get("cache_version") or "").strip(), CACHE_VERSION) if value),
            CACHE_VERSION,
        ),
        "vendor_version": next(
            (value for value in (str(latest_build.get("vendor_version") or "").strip(), str(latest_manifest.get("vendor_version") or "").strip(), "vv_none") if value),
            "vv_none",
        ),
    }


def _meta(result_kind: str, report_date: date, rows: list[dict[str, object]]):
    lineage = _lineage(report_date.isoformat(), rows)
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=lineage["cache_version"],
        source_version=lineage["source_version"],
        rule_version=lineage["rule_version"],
        vendor_version=lineage["vendor_version"],
    )


def bond_analytics_dates_envelope() -> dict[str, object]:
    report_dates = _repo().list_report_dates()
    if report_dates:
        try:
            manifest = resolve_formal_manifest_lineage(
                governance_dir=str(get_settings().governance_path),
                cache_key=CACHE_KEY,
            )
            lineage = {
                "source_version": str(manifest["source_version"]),
                "rule_version": str(manifest["rule_version"]),
                "cache_version": str(manifest.get("cache_version") or "").strip() or CACHE_VERSION,
                "vendor_version": str(manifest.get("vendor_version") or "").strip() or "vv_none",
            }
        except RuntimeError:
            rows = _repo().fetch_bond_analytics_rows(report_date=report_dates[0])
            lineage = _lineage(report_dates[0], rows)
    else:
        lineage = {
            "source_version": EMPTY_SOURCE_VERSION,
            "rule_version": RULE_VERSION,
            "cache_version": CACHE_VERSION,
            "vendor_version": "vv_none",
        }

    meta = build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind="bond_analytics.dates",
        cache_version=lineage["cache_version"],
        source_version=lineage["source_version"],
        rule_version=lineage["rule_version"],
        vendor_version=lineage["vendor_version"],
    )
    return build_formal_result_envelope(
        result_meta=meta,
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
    prior_balance_date = BalanceAnalysisRepository(duckdb_path).resolve_prior_pnl_bridge_balance_report_date(
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
    payload = ReturnDecompositionResponse(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        carry=_text(ZERO),
        roll_down=_text(ZERO),
        rate_effect=_text(ZERO),
        spread_effect=_text(ZERO),
        trading=_text(ZERO),
        explained_pnl=_text(ZERO),
        actual_pnl=_text(ZERO),
        recon_error=_text(ZERO),
        recon_error_pct=_text(ZERO),
        computed_at=meta.generated_at.isoformat(),
        warnings=[EMPTY_WARNING],
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


def get_return_decomposition(report_date: date, period_type: str = "MoM", asset_class: str = "all", accounting_class: str = "all") -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat(), asset_class=asset_class, accounting_class=accounting_class)
    if not rows:
        meta = _meta("bond_analytics.return_decomposition", report_date, rows)
        return _empty_return_response(meta, report_date, period_type, period_start, period_end)
    curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
    fx_rates_current, fx_current_warning = curve_repo.fetch_fx_rates_with_fallback_warning(
        report_date.isoformat()
    )
    fx_rates_prior, fx_prior_warning = curve_repo.fetch_fx_rates_with_fallback_warning(
        period_start.isoformat()
    )
    fx_rates_current = fx_rates_current or None
    fx_rates_prior = fx_rates_prior or None
    required_curve_types = _required_curve_types_for_return_rows(rows)
    treasury_current, treasury_current_warning = _resolve_curve_pair_if_needed(
        curve_type="treasury",
        required_curve_types=required_curve_types,
        repo=curve_repo,
        report_date=report_date.isoformat(),
        prior_date=period_start.isoformat(),
    )
    cdb_current, cdb_current_warning = _resolve_curve_pair_if_needed(
        curve_type="cdb",
        required_curve_types=required_curve_types,
        repo=curve_repo,
        report_date=report_date.isoformat(),
        prior_date=period_start.isoformat(),
    )
    aaa_current, aaa_current_warning = _resolve_curve_pair_if_needed(
        curve_type="aaa_credit",
        required_curve_types=required_curve_types,
        repo=curve_repo,
        report_date=report_date.isoformat(),
        prior_date=period_start.isoformat(),
    )
    treasury_prior = treasury_current.get("_prior_snapshot") if treasury_current else None
    cdb_prior = cdb_current.get("_prior_snapshot") if cdb_current else None
    aaa_prior = aaa_current.get("_prior_snapshot") if aaa_current else None
    treasury_prior_warning = treasury_current.get("_prior_warning") if treasury_current else None
    cdb_prior_warning = cdb_current.get("_prior_warning") if cdb_current else None
    aaa_prior_warning = aaa_current.get("_prior_warning") if aaa_current else None
    curve_snapshots = [
        snapshot
        for snapshot in (treasury_current, treasury_prior, cdb_current, cdb_prior, aaa_current, aaa_prior)
        if snapshot is not None
    ]
    relevant_curve_warnings = _curve_warnings_for_return_rows(
        rows,
        treasury_current_warning=treasury_current_warning,
        treasury_prior_warning=treasury_prior_warning,
        cdb_current_warning=cdb_current_warning,
        cdb_prior_warning=cdb_prior_warning,
        aaa_current_warning=aaa_current_warning,
        aaa_prior_warning=aaa_prior_warning,
    )
    curve_latest_fallback = any(
        w and YIELD_CURVE_LATEST_FALLBACK_PREFIX in w
        for w in relevant_curve_warnings
    )
    curve_unavailable = any(
        w and w.startswith("No ")
        for w in relevant_curve_warnings
    )
    fx_latest_fallback = any(
        warning and FX_LATEST_FALLBACK_PREFIX in warning
        for warning in (fx_current_warning, fx_prior_warning)
    )
    fx_unavailable = _fx_unavailable_for_return_rows(
        rows,
        fx_rates_current=fx_rates_current,
        fx_rates_prior=fx_rates_prior,
    )
    fx_missing_warnings = _fx_missing_warnings_for_return_rows(
        rows,
        report_date=report_date.isoformat(),
        prior_date=period_start.isoformat(),
        fx_rates_current=fx_rates_current,
        fx_rates_prior=fx_rates_prior,
    )
    meta = _meta("bond_analytics.return_decomposition", report_date, rows)
    meta = _apply_vendor_meta_update(
        meta,
        curve_snapshots=curve_snapshots,
        cache_version_suffix=YIELD_CURVE_CACHE_VERSION,
        curve_unavailable=curve_unavailable,
        curve_latest_fallback=curve_latest_fallback,
        fx_unavailable=fx_unavailable,
        fx_latest_fallback=fx_latest_fallback,
    )

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
    explained_total = (
        summary["carry_total"]
        + summary["roll_down_total"]
        + summary["rate_effect_total"]
        + summary["spread_effect_total"]
        + summary["convexity_effect_total"]
        + summary.get("fx_effect_total", ZERO)
    )
    payload = ReturnDecompositionResponse(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        carry=_text(summary["carry_total"]),
        roll_down=_text(summary["roll_down_total"]),
        rate_effect=_text(summary["rate_effect_total"]),
        spread_effect=_text(summary["spread_effect_total"]),
        trading=_text(ZERO),
        fx_effect=_text(summary.get("fx_effect_total", ZERO)),
        convexity_effect=_text(summary.get("convexity_effect_total", ZERO)),
        explained_pnl=_text(explained_total),
        explained_pnl_accounting=_text(explained_total),
        explained_pnl_economic=_text(explained_total),
        oci_reserve_impact=_text(ZERO),
        actual_pnl=_text(explained_total),
        recon_error=_text(ZERO),
        recon_error_pct=_text(ZERO),
        by_asset_class=[AssetClassBreakdown(asset_class=row["key"], carry=_text(row["carry"]), roll_down=_text(row["roll_down"]), rate_effect=_text(row["rate_effect"]), spread_effect=_text(row["spread_effect"]), convexity_effect=_text(row.get("convexity_effect", ZERO)), trading=_text(ZERO), total=_text(row["total"]), bond_count=int(row["bond_count"]), market_value=_text(row["market_value"])) for row in summary["by_asset_class"]],
        by_accounting_class=[AssetClassBreakdown(asset_class=row["key"], carry=_text(row["carry"]), roll_down=_text(row["roll_down"]), rate_effect=_text(row["rate_effect"]), spread_effect=_text(row["spread_effect"]), convexity_effect=_text(row.get("convexity_effect", ZERO)), trading=_text(ZERO), total=_text(row["total"]), bond_count=int(row["bond_count"]), market_value=_text(row["market_value"])) for row in summary["by_accounting_class"]],
        bond_details=[BondLevelDecomposition(bond_code=str(row["instrument_code"]), bond_name=str(row.get("instrument_name") or ""), asset_class=str(row["asset_class_std"]), accounting_class=str(row["accounting_class"]), market_value=_text(row["market_value"]), carry=_text(row["carry"]), roll_down=_text(row["roll_down"]), rate_effect=_text(row["rate_effect"]), spread_effect=_text(row["spread_effect"]), convexity_effect=_text(row.get("convexity_effect", ZERO)), trading=_text(ZERO), total=_text(row["total"]), explained_for_recon=_text(row["total"]), economic_only_effects=_text(row["roll_down"] + row["rate_effect"] + row["spread_effect"] + row.get("convexity_effect", ZERO) + row.get("fx_effect", ZERO))) for row in summary["bond_details"]],
        bond_count=int(summary["bond_count"]),
        total_market_value=_text(summary["total_market_value"]),
        computed_at=meta.generated_at.isoformat(),
        warnings=_ordered_unique_warnings(
            [
                RETURN_TRADING_GAP_WARNING,
                *relevant_curve_warnings,
                fx_current_warning,
                fx_prior_warning,
                *fx_missing_warnings,
            ]
        ),
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


def get_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    meta = _meta("bond_analytics.benchmark_excess", report_date, rows)
    curve_type = BENCHMARK_CURVE_TYPES.get(benchmark_id, "cdb")
    treasury_current = None
    treasury_prior = None
    treasury_current_warning = None
    treasury_prior_warning = None
    cdb_current = None
    cdb_prior = None
    cdb_current_warning = None
    cdb_prior_warning = None
    aaa_current = None
    aaa_prior = None
    aaa_current_warning = None
    aaa_prior_warning = None
    current_curve = None
    prior_curve = None
    current_warning = None
    prior_warning = None
    curve_snapshots: list[dict[str, object]] = []
    curve_latest_fallback = False
    curve_unavailable = False
    if rows:
        curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
        required_curve_types = _required_curve_types_for_return_rows(rows)
        required_curve_types.add(curve_type)
        treasury_current, treasury_current_warning = _resolve_curve_pair_if_needed(
            curve_type="treasury",
            required_curve_types=required_curve_types,
            repo=curve_repo,
            report_date=report_date.isoformat(),
            prior_date=period_start.isoformat(),
        )
        cdb_current, cdb_current_warning = _resolve_curve_pair_if_needed(
            curve_type="cdb",
            required_curve_types=required_curve_types,
            repo=curve_repo,
            report_date=report_date.isoformat(),
            prior_date=period_start.isoformat(),
        )
        aaa_current, aaa_current_warning = _resolve_curve_pair_if_needed(
            curve_type="aaa_credit",
            required_curve_types=required_curve_types,
            repo=curve_repo,
            report_date=report_date.isoformat(),
            prior_date=period_start.isoformat(),
        )
        treasury_prior = treasury_current.get("_prior_snapshot") if treasury_current else None
        cdb_prior = cdb_current.get("_prior_snapshot") if cdb_current else None
        aaa_prior = aaa_current.get("_prior_snapshot") if aaa_current else None
        treasury_prior_warning = treasury_current.get("_prior_warning") if treasury_current else None
        cdb_prior_warning = cdb_current.get("_prior_warning") if cdb_current else None
        aaa_prior_warning = aaa_current.get("_prior_warning") if aaa_current else None

        if curve_type == "treasury":
            current_curve, prior_curve = treasury_current, treasury_prior
            current_warning, prior_warning = treasury_current_warning, treasury_prior_warning
        elif curve_type == "cdb":
            current_curve, prior_curve = cdb_current, cdb_prior
            current_warning, prior_warning = cdb_current_warning, cdb_prior_warning
        else:
            current_curve, prior_curve = aaa_current, aaa_prior
            current_warning, prior_warning = aaa_current_warning, aaa_prior_warning
        curve_snapshots = [
            snapshot
            for snapshot in (
                treasury_current,
                treasury_prior,
                cdb_current,
                cdb_prior,
                aaa_current,
                aaa_prior,
            )
            if snapshot is not None
        ]
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
                current_warning if current_warning not in {treasury_current_warning, cdb_current_warning, aaa_current_warning} else None,
                prior_warning if prior_warning not in {treasury_prior_warning, cdb_prior_warning, aaa_prior_warning} else None,
            ]
        )
        curve_latest_fallback = any(
            warning and YIELD_CURVE_LATEST_FALLBACK_PREFIX in warning
            for warning in relevant_curve_warnings
        )
        curve_unavailable = any(
            warning and warning.startswith("No ")
            for warning in relevant_curve_warnings
        )
    meta = _apply_vendor_meta_update(
        meta,
        curve_snapshots=curve_snapshots,
        cache_version_suffix=YIELD_CURVE_CACHE_VERSION,
        curve_unavailable=curve_unavailable,
        curve_latest_fallback=curve_latest_fallback,
    )
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
    credit_rows_for_excess = [row for row in rows if str(row.get("asset_class_std")) == "credit"]
    benchmark_curves_ok = bool(current_curve and prior_curve)
    spread_excess_incomplete = (
        benchmark_curves_ok
        and bool(credit_rows_for_excess)
        and summary["spread_effect"] == ZERO
        and (
            treasury_current is None
            or treasury_prior is None
            or aaa_current is None
            or aaa_prior is None
        )
    )
    warnings = (
        [EMPTY_WARNING]
        if not rows
        else _ordered_unique_warnings(
            [
                BENCHMARK_WARNING if not current_curve or not prior_curve else None,
                BENCHMARK_EXCESS_SPREAD_GAP_WARNING if spread_excess_incomplete else None,
                current_warning,
                prior_warning,
                *_curve_warnings_for_return_rows(
                    rows,
                    treasury_current_warning=treasury_current_warning,
                    treasury_prior_warning=treasury_prior_warning,
                    cdb_current_warning=cdb_current_warning,
                    cdb_prior_warning=cdb_prior_warning,
                    aaa_current_warning=aaa_current_warning,
                    aaa_prior_warning=aaa_prior_warning,
                ),
            ]
        )
    )
    payload = BenchmarkExcessResponse(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        benchmark_id=benchmark_id,
        benchmark_name=BENCHMARK_NAMES.get(benchmark_id, benchmark_id),
        portfolio_return=_text(summary["portfolio_return"]),
        benchmark_return=_text(summary["benchmark_return"]),
        excess_return=_text(summary["excess_return"]),
        duration_effect=_text(summary["duration_effect"]),
        curve_effect=_text(summary["curve_effect"]),
        spread_effect=_text(summary["spread_effect"]),
        selection_effect=_text(summary["selection_effect"]),
        allocation_effect=_text(summary["allocation_effect"]),
        explained_excess=_text(summary["explained_excess"]),
        recon_error=_text(summary["recon_error"]),
        portfolio_duration=_text(summary["portfolio_duration"]),
        benchmark_duration=_text(summary["benchmark_duration"]),
        duration_diff=_text(summary["duration_diff"]),
        excess_sources=[
            {
                **row,
                "contribution": _text(Decimal(str(row["contribution"]))),
            }
            for row in summary["excess_sources"]
        ],
        computed_at=meta.generated_at.isoformat(),
        warnings=warnings,
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


def get_krd_curve_risk(report_date: date, scenario_set: str = "standard") -> dict:
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    meta = _meta("bond_analytics.krd_curve_risk", report_date, rows)
    risk = summarize_portfolio_risk(rows)
    payload = KRDCurveRiskResponse(
        report_date=report_date,
        portfolio_duration=_text(risk["portfolio_duration"]),
        portfolio_modified_duration=_text(risk["portfolio_modified_duration"]),
        portfolio_dv01=_text(risk["portfolio_dv01"]),
        portfolio_convexity=_text(risk["portfolio_convexity"]),
        krd_buckets=[KRDBucket(tenor=row["tenor_bucket"], krd=_text(row["krd"]), dv01=_text(row["dv01"]), market_value_weight=_text(row["market_value"] / risk["total_market_value"] if risk["total_market_value"] else ZERO)) for row in build_krd_distribution(rows)],
        scenarios=[ScenarioResult(scenario_name=row["scenario_name"], scenario_description=row["scenario_description"], shocks=row["shocks"], pnl_economic=_text(row["pnl_economic"]), pnl_oci=_text(row["pnl_oci"]), pnl_tpl=_text(row["pnl_tpl"]), rate_contribution=_text(row["rate_contribution"]), convexity_contribution=_text(row["convexity_contribution"]), by_asset_class={key: {metric: _text(value) for metric, value in values.items()} for key, values in row["by_asset_class"].items()}) for row in build_curve_scenarios(rows)],
        by_asset_class=[AssetClassRiskSummary(asset_class=row["asset_class"], market_value=_text(row["market_value"]), duration=_text(row["duration"]), dv01=_text(row["dv01"]), weight=_text(row["weight"])) for row in build_asset_class_risk_summary(rows)],
        computed_at=meta.generated_at.isoformat(),
        warnings=[EMPTY_WARNING] if not rows else [],
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


def get_credit_spread_migration(report_date: date, spread_scenarios: str = "10,25,50") -> dict:
    all_rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    credit_rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat(), asset_class="credit")
    meta = _meta("bond_analytics.credit_spread_migration", report_date, all_rows)
    treasury_current = None
    treasury_warning = None
    aaa_current = None
    aaa_warning = None
    curve_snapshots: list[dict[str, object]] = []
    curve_latest_fallback = False
    curve_unavailable = False
    if credit_rows:
        curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
        treasury_current, treasury_warning = _resolve_curve_for_service(
            repo=curve_repo,
            requested_trade_date=report_date.isoformat(),
            curve_type="treasury",
        )
        aaa_current, aaa_warning = _resolve_curve_for_service(
            repo=curve_repo,
            requested_trade_date=report_date.isoformat(),
            curve_type="aaa_credit",
        )
        curve_snapshots = [snapshot for snapshot in (treasury_current, aaa_current) if snapshot is not None]
        curve_latest_fallback = any(
            warning and YIELD_CURVE_LATEST_FALLBACK_PREFIX in warning
            for warning in (aaa_warning, treasury_warning)
        )
        curve_unavailable = any(
            warning and warning.startswith("No ")
            for warning in (aaa_warning, treasury_warning)
        )
    meta = _apply_vendor_meta_update(
        meta,
        curve_snapshots=curve_snapshots,
        cache_version_suffix=YIELD_CURVE_CACHE_VERSION,
        curve_unavailable=curve_unavailable,
        curve_latest_fallback=curve_latest_fallback,
    )
    summary = summarize_credit(
        credit_rows,
        total_rows=all_rows,
        aaa_credit_curve_current=aaa_current["curve"] if aaa_current else None,
        treasury_curve_current=treasury_current["curve"] if treasury_current else None,
    )
    curve_warnings = _ordered_unique_warnings([aaa_warning, treasury_warning])
    spread_level_incomplete = bool(credit_rows) and summary["weighted_avg_spread"] == ZERO and (
        aaa_current is None or treasury_current is None
    )
    migration_warnings = (
        [EMPTY_WARNING]
        if not all_rows
        else _ordered_unique_warnings(
            [SPREAD_WARNING if spread_level_incomplete else None, *curve_warnings]
        )
    )
    payload = CreditSpreadMigrationResponse(
        report_date=report_date,
        credit_bond_count=int(summary["credit_bond_count"]),
        credit_market_value=_text(summary["credit_market_value"]),
        credit_weight=_text(summary["credit_weight"]),
        rating_aa_and_below_weight=_text(
            rating_aa_and_below_portfolio_weight(
                credit_rows,
                total_portfolio_market_value=summary["total_market_value"],
            )
        ),
        spread_dv01=_text(summary["spread_dv01"]),
        weighted_avg_spread=_text(summary["weighted_avg_spread"]),
        weighted_avg_spread_duration=_text(summary["weighted_avg_spread_duration"]),
        spread_scenarios=[
            SpreadScenarioResult(
                scenario_name=f"利差{'走阔' if change_bp > 0 else '收窄'} {abs(change_bp)}bp",
                spread_change_bp=float(change_bp),
                pnl_impact=_text(-(summary["spread_dv01"] * Decimal(str(change_bp)))),
                oci_impact=_text(-(summary["oci_spread_dv01"] * Decimal(str(change_bp)))),
                tpl_impact=_text(-(summary["tpl_spread_dv01"] * Decimal(str(change_bp)))),
            )
            for bp in [int(value.strip()) for value in spread_scenarios.split(",") if value.strip()]
            for change_bp in (bp, -bp)
        ],
        migration_scenarios=[],
        concentration_by_issuer=_to_concentration_model(build_concentration(credit_rows, field_name="issuer_name", dimension="issuer")),
        concentration_by_industry=_to_concentration_model(build_concentration(credit_rows, field_name="industry_name", dimension="industry")),
        concentration_by_rating=_to_concentration_model(build_concentration(credit_rows, field_name="rating", dimension="rating")),
        concentration_by_tenor=_to_concentration_model(build_concentration(credit_rows, field_name="tenor_bucket", dimension="tenor")),
        oci_credit_exposure=_text(summary["oci_credit_exposure"]),
        oci_spread_dv01=_text(summary["oci_spread_dv01"]),
        oci_sensitivity_25bp=_text(-(summary["oci_spread_dv01"] * Decimal("25"))),
        computed_at=meta.generated_at.isoformat(),
        warnings=migration_warnings,
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


def _to_concentration_model(payload: dict[str, object] | None) -> ConcentrationMetrics | None:
    if payload is None:
        return None
    return ConcentrationMetrics(
        dimension=str(payload["dimension"]),
        hhi=_text(payload["hhi"]),
        top5_concentration=_text(payload["top5_concentration"]),
        top_items=[ConcentrationItem(name=str(row["name"]), weight=_text(row["weight"]), market_value=_text(row["market_value"])) for row in payload["top_items"]],
    )


def get_accounting_class_audit(report_date: date) -> dict:
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    meta = _meta("bond_analytics.accounting_class_audit", report_date, rows)
    audit = summarize_accounting_audit(rows)
    payload = AccountingClassAuditResponse(
        report_date=report_date,
        total_positions=int(audit["total_positions"]),
        total_market_value=_text(audit["total_market_value"]),
        distinct_asset_classes=int(audit["distinct_asset_classes"]),
        divergent_asset_classes=int(audit["divergent_asset_classes"]),
        divergent_position_count=int(audit["divergent_position_count"]),
        divergent_market_value=_text(audit["divergent_market_value"]),
        map_unclassified_asset_classes=int(audit["map_unclassified_asset_classes"]),
        map_unclassified_position_count=int(audit["map_unclassified_position_count"]),
        map_unclassified_market_value=_text(audit["map_unclassified_market_value"]),
        rows=[
            AccountingClassAuditItem(
                asset_class=str(row["asset_class_raw"]),
                position_count=int(row["position_count"]),
                market_value=_text(row["market_value"]),
                market_value_weight=_text(row["market_value_weight"]),
                infer_accounting_class=str(row["infer_accounting_class"]),
                map_accounting_class=str(row["map_accounting_class"]),
                infer_rule_id=str(row["infer_rule_id"]),
                infer_match=row["infer_match"],
                map_rule_id=str(row["map_rule_id"]),
                map_match=row["map_match"],
                is_divergent=bool(row["is_divergent"]),
                is_map_unclassified=bool(row["is_map_unclassified"]),
            )
            for row in audit["rows"]
        ],
        computed_at=meta.generated_at.isoformat(),
        warnings=[EMPTY_WARNING] if not rows else [],
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload.model_dump(mode="json"))


def get_action_attribution(report_date: date, period_type: str = "MoM") -> dict:
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
    response = ActionAttributionResponse(
        report_date=report_date,
        period_type=str(summary["period_type"]),
        period_start=date.fromisoformat(str(summary["period_start"])),
        period_end=date.fromisoformat(str(summary["period_end"])),
        total_actions=int(summary["total_actions"]),
        total_pnl_from_actions=str(summary["total_pnl_from_actions"]),
        by_action_type=[ActionTypeSummary.model_validate(item) for item in analysis_envelope.result.facets.get("by_action_type", [])],
        action_details=[ActionDetail.model_validate(item) for item in analysis_envelope.result.facets.get("action_details", [])],
        period_start_duration=str(summary["period_start_duration"]),
        period_end_duration=str(summary["period_end_duration"]),
        duration_change_from_actions=str(summary["duration_change_from_actions"]),
        period_start_dv01=str(summary["period_start_dv01"]),
        period_end_dv01=str(summary["period_end_dv01"]),
        computed_at=str(summary.get("computed_at") or analysis_envelope.result_meta.generated_at.isoformat()),
        warnings=warnings,
    )
    return {"result_meta": analysis_envelope.result_meta.model_dump(mode="json"), "result": response.model_dump(mode="json")}


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
