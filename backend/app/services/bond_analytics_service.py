"""Bond analytics service — orchestrates fact reads and delegates finance logic to core_finance."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings, get_settings
from backend.app.core_finance.bond_analytics.common import STANDARD_SCENARIOS, resolve_period
from backend.app.core_finance.bond_analytics.read_models import (
    build_asset_class_risk_summary,
    build_concentration,
    build_curve_scenarios,
    build_krd_distribution,
    summarize_accounting_audit,
    summarize_credit,
    summarize_portfolio_risk,
    summarize_return_decomposition,
)
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
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
from backend.app.tasks.yield_curve_materialize import CACHE_VERSION as YIELD_CURVE_CACHE_VERSION

JOB_NAME = "bond_analytics_materialize"
EMPTY_SOURCE_VERSION = "sv_bond_analytics_empty"
EMPTY_WARNING = "DuckDB bond analytics fact table not yet populated — returning empty result"
PHASE3_WARNING = "Phase 3 partial delivery: spread_effect / trading still require additional curve and trade inputs."
BENCHMARK_WARNING = "Benchmark index data not yet available; benchmark-side fields remain zero"
SPREAD_WARNING = "Spread level input unavailable; weighted_avg_spread set to 0"
ACTION_WARNING = "Trade-level action data not yet available; returning placeholder attribution until trade records are integrated"
Q8 = Decimal("0.00000001")
ZERO = Decimal("0")
BENCHMARK_NAMES = {
    "TREASURY_INDEX": "中债国债总指数",
    "CDB_INDEX": "中债国开债总指数",
    "AAA_CREDIT_INDEX": "中债AAA信用债指数",
}
PENDING_SOURCE_VERSION = "sv_bond_analytics_pending"
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
    curve_repo = YieldCurveRepository(str(get_settings().duckdb_path))
    treasury_current, treasury_current_warning = _resolve_curve_for_service(
        repo=curve_repo,
        requested_trade_date=report_date.isoformat(),
        curve_type="treasury",
    )
    treasury_prior, treasury_prior_warning = _resolve_curve_for_service(
        repo=curve_repo,
        requested_trade_date=period_start.isoformat(),
        curve_type="treasury",
    )
    cdb_current, cdb_current_warning = _resolve_curve_for_service(
        repo=curve_repo,
        requested_trade_date=report_date.isoformat(),
        curve_type="cdb",
    )
    cdb_prior, cdb_prior_warning = _resolve_curve_for_service(
        repo=curve_repo,
        requested_trade_date=period_start.isoformat(),
        curve_type="cdb",
    )
    curve_snapshots = [
        snapshot
        for snapshot in (treasury_current, treasury_prior, cdb_current, cdb_prior)
        if snapshot is not None
    ]
    curve_latest_fallback = any(
        w and "Using latest available" in w
        for w in (
            treasury_current_warning,
            treasury_prior_warning,
            cdb_current_warning,
            cdb_prior_warning,
        )
    )
    meta = _meta("bond_analytics.return_decomposition", report_date, rows)
    if curve_snapshots:
        meta = meta.model_copy(
            update={
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
                "cache_version": f"{CACHE_VERSION}__{YIELD_CURVE_CACHE_VERSION}",
                **(
                    {"fallback_mode": "latest_snapshot", "vendor_status": "vendor_stale"}
                    if curve_latest_fallback
                    else {}
                ),
            }
        )
    if not rows:
        return _empty_return_response(meta, report_date, period_type, period_start, period_end)

    summary = summarize_return_decomposition(
        rows,
        period_start=period_start,
        period_end=period_end,
        treasury_curve_current=treasury_current["curve"] if treasury_current else None,
        treasury_curve_prior=treasury_prior["curve"] if treasury_prior else None,
        cdb_curve_current=cdb_current["curve"] if cdb_current else None,
        cdb_curve_prior=cdb_prior["curve"] if cdb_prior else None,
    )
    explained_total = summary["carry_total"] + summary["roll_down_total"] + summary["rate_effect_total"]
    payload = ReturnDecompositionResponse(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        carry=_text(summary["carry_total"]),
        roll_down=_text(summary["roll_down_total"]),
        rate_effect=_text(summary["rate_effect_total"]),
        spread_effect=_text(ZERO),
        trading=_text(ZERO),
        fx_effect=_text(ZERO),
        convexity_effect=_text(ZERO),
        explained_pnl=_text(explained_total),
        explained_pnl_accounting=_text(explained_total),
        explained_pnl_economic=_text(explained_total),
        oci_reserve_impact=_text(ZERO),
        actual_pnl=_text(explained_total),
        recon_error=_text(ZERO),
        recon_error_pct=_text(ZERO),
        by_asset_class=[AssetClassBreakdown(asset_class=row["key"], carry=_text(row["carry"]), roll_down=_text(row["roll_down"]), rate_effect=_text(row["rate_effect"]), spread_effect=_text(ZERO), trading=_text(ZERO), total=_text(row["total"]), bond_count=int(row["bond_count"]), market_value=_text(row["market_value"])) for row in summary["by_asset_class"]],
        by_accounting_class=[AssetClassBreakdown(asset_class=row["key"], carry=_text(row["carry"]), roll_down=_text(row["roll_down"]), rate_effect=_text(row["rate_effect"]), spread_effect=_text(ZERO), trading=_text(ZERO), total=_text(row["total"]), bond_count=int(row["bond_count"]), market_value=_text(row["market_value"])) for row in summary["by_accounting_class"]],
        bond_details=[BondLevelDecomposition(bond_code=str(row["instrument_code"]), bond_name=str(row.get("instrument_name") or ""), asset_class=str(row["asset_class_std"]), accounting_class=str(row["accounting_class"]), market_value=_text(row["market_value"]), carry=_text(row["carry"]), roll_down=_text(row["roll_down"]), rate_effect=_text(row["rate_effect"]), spread_effect=_text(ZERO), trading=_text(ZERO), total=_text(row["total"]), explained_for_recon=_text(row["total"]), economic_only_effects=_text(row["roll_down"] + row["rate_effect"])) for row in summary["bond_details"]],
        bond_count=int(summary["bond_count"]),
        total_market_value=_text(summary["total_market_value"]),
        computed_at=meta.generated_at.isoformat(),
        warnings=[
            PHASE3_WARNING,
            *_compact_warnings(
                [
                    treasury_current_warning,
                    treasury_prior_warning,
                    cdb_current_warning,
                    cdb_prior_warning,
                ]
            ),
        ],
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
    latest_trade_date = repo.fetch_latest_trade_date_on_or_before(curve_type, requested_trade_date)
    if latest_trade_date is None:
        return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}; affected components remain 0."
    latest_snapshot = repo.fetch_curve_snapshot(latest_trade_date, curve_type)
    if latest_snapshot is None:
        return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}; affected components remain 0."
    return (
        latest_snapshot,
        f"Using latest available {curve_type} curve from trade_date={latest_trade_date} for requested trade_date={requested_trade_date}.",
    )


def _compact_warnings(values: list[str | None]) -> list[str]:
    return [value for value in values if value]


def get_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date.isoformat())
    meta = _meta("bond_analytics.benchmark_excess", report_date, rows)
    risk = summarize_portfolio_risk(rows)
    payload = BenchmarkExcessResponse(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        benchmark_id=benchmark_id,
        benchmark_name=BENCHMARK_NAMES.get(benchmark_id, benchmark_id),
        portfolio_return=_text(ZERO),
        benchmark_return=_text(ZERO),
        excess_return=_text(ZERO),
        duration_effect=_text(ZERO),
        curve_effect=_text(ZERO),
        spread_effect=_text(ZERO),
        selection_effect=_text(ZERO),
        allocation_effect=_text(ZERO),
        explained_excess=_text(ZERO),
        recon_error=_text(ZERO),
        portfolio_duration=_text(risk["portfolio_duration"]),
        benchmark_duration=_text(ZERO),
        duration_diff=_text(risk["portfolio_duration"]),
        computed_at=meta.generated_at.isoformat(),
        warnings=[EMPTY_WARNING if not rows else BENCHMARK_WARNING],
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
    summary = summarize_credit(credit_rows, total_rows=all_rows)
    payload = CreditSpreadMigrationResponse(
        report_date=report_date,
        credit_bond_count=int(summary["credit_bond_count"]),
        credit_market_value=_text(summary["credit_market_value"]),
        credit_weight=_text(summary["credit_weight"]),
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
        warnings=[EMPTY_WARNING] if not all_rows else [SPREAD_WARNING],
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
    warnings = [warning.message for warning in analysis_envelope.result.warnings]
    if int(summary["total_actions"]) == 0 and not analysis_envelope.result.facets.get("action_details") and ACTION_WARNING not in warnings:
        warnings.append(ACTION_WARNING)
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
