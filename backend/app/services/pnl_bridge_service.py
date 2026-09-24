from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from backend.app.core_finance.bond_analytics.common import (
    TENOR_YEARS,
    classify_asset_class,
    infer_curve_type,
)
from backend.app.core_finance.pnl_bridge import (
    CurveEffectAvailabilitySummary,
    PnlBridgeRow,
    build_pnl_bridge_rows,
    required_curve_types_for_pnl_bridge,
    summarize_curve_effect_availability,
)
from backend.app.governance.formal_compute_lineage import (
    resolve_completed_formal_build_lineage,
    resolve_formal_manifest_lineage_with_completed_build,
)
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.fact_load_gates import ZQTZ_BALANCE_NATURAL_KEY
from backend.app.repositories.pnl_repo import PnlRepository

try:
    from backend.app.repositories.yield_curve_repo import (
        YIELD_CURVE_LATEST_FALLBACK_PREFIX,
        YieldCurveRepository,
        format_yield_curve_latest_fallback_warning,
    )
except ImportError:
    from backend.app.repositories import yield_curve_repo as _yield_curve_repo

    # Runtime fallback rebinding of the class name; mypy cannot model
    # conditional re-assignment of an imported type.
    YieldCurveRepository = _yield_curve_repo.YieldCurveRepository  # type: ignore[misc]
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
from backend.app.schemas.pnl_bridge import (
    PnlBridgePayload,
    PnlBridgeRowSchema,
    PnlBridgeSummarySchema,
)
from backend.app.services.explicit_numeric import promote_flat_payload
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_formal_result_envelope,
    build_formal_result_meta,
)

# Aligned with task-module identity constants; avoid import-time broker/actor registration.
BALANCE_ANALYSIS_CACHE_KEY = "balance_analysis:materialize:formal"
BALANCE_ANALYSIS_CACHE_VERSION = (
    "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1"
)
BALANCE_ANALYSIS_RULE_VERSION = "rv_balance_analysis_formal_materialize_v1"
PNL_CACHE_KEY = "pnl:phase2:materialize:formal"
PNL_RESULT_CACHE_VERSION = "cv_pnl_formal__rv_pnl_phase2_materialize_v3"
YIELD_CURVE_CACHE_VERSION = "cv_yield_curve_formal__rv_yield_curve_formal_materialize_v1"

PHASE3_WARNING = (
    "Phase 3 partial delivery: roll_down / treasury_curve / credit_spread use governed curves when available."
)
BRIDGE_CACHE_VERSION = (
    f"cv_pnl_bridge_formal_v1__{PNL_RESULT_CACHE_VERSION}__{BALANCE_ANALYSIS_CACHE_VERSION}__{YIELD_CURVE_CACHE_VERSION}"
)
ZERO = Decimal("0")


def pnl_bridge_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    pnl_repo = PnlRepository(duckdb_path)
    balance_repo = BalanceAnalysisRepository(duckdb_path)
    curve_repo = YieldCurveRepository(duckdb_path)
    if report_date not in pnl_repo.list_formal_fi_report_dates():
        raise ValueError(f"No pnl bridge data found for report_date={report_date} in fact_formal_pnl_fi.")

    pnl_fi_rows = pnl_repo.fetch_formal_fi_rows(report_date)
    current_balance_rows = _attach_native_exposure_fields(
        balance_repo=balance_repo,
        report_date=report_date,
        balance_rows=balance_repo.fetch_pnl_bridge_zqtz_balance_rows(report_date=report_date),
    )
    prior_date = balance_repo.resolve_prior_pnl_bridge_balance_report_date(report_date=report_date)
    prior_balance_rows = (
        _attach_native_exposure_fields(
            balance_repo=balance_repo,
            report_date=prior_date,
            balance_rows=balance_repo.fetch_pnl_bridge_zqtz_balance_rows(report_date=prior_date),
        )
        if prior_date
        else []
    )
    fx_current = balance_repo.resolve_formal_fx_mid_rates_map(
        report_date=report_date,
        base_currencies=_bridge_fx_base_currencies(pnl_fi_rows, current_balance_rows),
    )
    fx_prior = (
        balance_repo.resolve_formal_fx_mid_rates_map(
            report_date=prior_date,
            base_currencies=_bridge_fx_base_currencies(pnl_fi_rows, prior_balance_rows),
        )
        if prior_date
        else None
    )
    required_curve_types = required_curve_types_for_pnl_bridge(
        pnl_fi_rows=pnl_fi_rows,
        balance_rows_current=current_balance_rows,
        balance_rows_prior=prior_balance_rows,
    )
    treasury_current, treasury_current_warning = _resolve_curve_pair_if_needed(
        curve_type="treasury",
        required_curve_types=required_curve_types,
        repo=curve_repo,
        report_date=report_date,
        prior_date=prior_date,
    )
    cdb_current, cdb_current_warning = _resolve_curve_pair_if_needed(
        curve_type="cdb",
        required_curve_types=required_curve_types,
        repo=curve_repo,
        report_date=report_date,
        prior_date=prior_date,
    )
    aaa_current, aaa_current_warning = _resolve_curve_pair_if_needed(
        curve_type="aaa_credit",
        required_curve_types=required_curve_types,
        repo=curve_repo,
        report_date=report_date,
        prior_date=prior_date,
    )
    treasury_prior = _optional_snapshot(treasury_current.get("_prior_snapshot")) if treasury_current else None
    cdb_prior = _optional_snapshot(cdb_current.get("_prior_snapshot")) if cdb_current else None
    aaa_prior = _optional_snapshot(aaa_current.get("_prior_snapshot")) if aaa_current else None
    treasury_prior_warning = _optional_warning(treasury_current, "_prior_warning")
    cdb_prior_warning = _optional_warning(cdb_current, "_prior_warning")
    aaa_prior_warning = _optional_warning(aaa_current, "_prior_warning")
    treasury_current_points, treasury_current_curve_error = _curve_points_with_reason(treasury_current)
    treasury_prior_points, treasury_prior_curve_error = _curve_points_with_reason(_snapshot_dict(treasury_prior))
    cdb_current_points, cdb_current_curve_error = _curve_points_with_reason(cdb_current)
    cdb_prior_points, cdb_prior_curve_error = _curve_points_with_reason(_snapshot_dict(cdb_prior))
    aaa_current_points, aaa_current_curve_error = _curve_points_with_reason(aaa_current)
    aaa_prior_points, aaa_prior_curve_error = _curve_points_with_reason(_snapshot_dict(aaa_prior))
    curve_conversion_slots = (
        ("treasury", report_date, treasury_current, treasury_current_points, treasury_current_curve_error),
        ("treasury", prior_date, treasury_prior, treasury_prior_points, treasury_prior_curve_error),
        ("cdb", report_date, cdb_current, cdb_current_points, cdb_current_curve_error),
        ("cdb", prior_date, cdb_prior, cdb_prior_points, cdb_prior_curve_error),
        ("aaa_credit", report_date, aaa_current, aaa_current_points, aaa_current_curve_error),
        ("aaa_credit", prior_date, aaa_prior, aaa_prior_points, aaa_prior_curve_error),
    )
    curve_conversion_warnings = [
        (
            f"Required {curve_type} curve snapshot for trade_date="
            f"{snapshot.get('trade_date') or requested_trade_date} could not be converted "
            "to validated curve points; curve effect remains 0."
        )
        for curve_type, requested_trade_date, snapshot, points, _reason in curve_conversion_slots
        if snapshot is not None and points is None
    ]
    # Disclosure companion to the generic conversion warning above (kept verbatim for
    # exact-string consumers): each failed slot also reports its validation reason.
    curve_snapshot_error_warnings = [
        (
            f"curve_snapshot_error: {curve_type} curve snapshot for trade_date="
            f"{snapshot.get('trade_date') or requested_trade_date} rejected: {reason}; "
            "curve effect remains 0."
        )
        for curve_type, requested_trade_date, snapshot, _points, reason in curve_conversion_slots
        if snapshot is not None and reason is not None
    ]
    relevant_curve_warnings = [
        *_curve_warnings_for_bridge_rows(
            current_balance_rows=current_balance_rows,
            prior_balance_rows=prior_balance_rows,
            treasury_current_warning=treasury_current_warning,
            treasury_prior_warning=treasury_prior_warning,
            cdb_current_warning=cdb_current_warning,
            cdb_prior_warning=cdb_prior_warning,
            aaa_current_warning=aaa_current_warning,
            aaa_prior_warning=aaa_prior_warning,
        ),
        *curve_conversion_warnings,
        *curve_snapshot_error_warnings,
    ]
    curve_conversion_failed = bool(curve_conversion_warnings)
    curve_latest_fallback = any(
        w and YIELD_CURVE_LATEST_FALLBACK_PREFIX in w
        for w in relevant_curve_warnings
    )
    curve_unavailable = any(
        w and w.startswith("No ")
        for w in relevant_curve_warnings
    ) or curve_conversion_failed

    rows = build_pnl_bridge_rows(
        pnl_fi_rows=pnl_fi_rows,
        balance_rows_current=current_balance_rows,
        balance_rows_prior=prior_balance_rows,
        treasury_curve_current=treasury_current_points,
        treasury_curve_prior=treasury_prior_points,
        cdb_curve_current=cdb_current_points,
        cdb_curve_prior=cdb_prior_points,
        aaa_credit_curve_current=aaa_current_points,
        aaa_credit_curve_prior=aaa_prior_points,
        fx_rates_current=fx_current,
        fx_rates_prior=fx_prior,
    )
    summary = _build_summary(rows)
    row_diagnostic_warnings = _row_diagnostic_warnings(rows)
    lineage, lineage_warnings = _resolve_bridge_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
        prior_report_date=prior_date,
        current_balance_rows=current_balance_rows,
        prior_balance_rows=prior_balance_rows,
        curve_snapshots=[
            _snapshot_dict(snapshot)
            for snapshot in (treasury_current, treasury_prior, cdb_current, cdb_prior, aaa_current, aaa_prior)
            if snapshot is not None
        ],
    )
    payload = PnlBridgePayload(
        report_date=report_date,
        rows=[PnlBridgeRowSchema.model_validate(promote_flat_payload(row, PnlBridgeRowSchema)) for row in rows],
        summary=PnlBridgeSummarySchema.model_validate(promote_flat_payload(summary, PnlBridgeSummarySchema)),
        warnings=_bridge_warnings(
            balance_warnings=[
                *_build_warnings(
                    current_balance_rows=current_balance_rows,
                    prior_balance_rows=prior_balance_rows,
                    prior_report_date=prior_date,
                ),
                *row_diagnostic_warnings,
            ],
            curve_warnings=_compact_warnings([*relevant_curve_warnings]),
            lineage_warnings=lineage_warnings,
        ),
    )
    # PAGE-BRIDGE-001: business report_date is exact (no report-date fallback).
    # Curve trade dates are never promoted to fallback_date.
    resolved_report_date = str(payload.report_date)
    pnl_lineage_fallback = lineage.get("_lineage_fallback_mode") == "latest_snapshot"
    fallback_mode: FallbackMode
    vendor_status: VendorStatus
    if curve_unavailable:
        # Mixed vendor_unavailable + latest_snapshot: vendor_status reports unavailable,
        # while quality_flag still merges stale from curve_latest_fallback (intentional).
        fallback_mode = "latest_snapshot" if pnl_lineage_fallback else "none"
        vendor_status = "vendor_unavailable"
    elif curve_latest_fallback or pnl_lineage_fallback:
        fallback_mode = "latest_snapshot"
        vendor_status = "vendor_stale" if curve_latest_fallback else "ok"
    else:
        fallback_mode = "none"
        vendor_status = "ok"
    quality_flag = _merge_bridge_quality_flag(
        summary_quality=(
            "warning"
            if curve_conversion_failed and summary.quality_flag == "ok"
            else summary.quality_flag
        ),
        curve_latest_fallback=curve_latest_fallback,
    )
    if pnl_lineage_fallback and quality_flag != "error":
        quality_flag = "stale"
    result_meta = build_formal_result_meta(
        trace_id=f"tr_pnl_bridge_{report_date}",
        result_kind="pnl.bridge",
        cache_version=BRIDGE_CACHE_VERSION,
        source_version=str(lineage["source_version"]),
        rule_version=str(lineage["rule_version"]),
        vendor_version=str(lineage["vendor_version"]),
        source_surface="pnl_bridge",
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        requested_report_date=report_date,
        resolved_report_date=resolved_report_date,
        as_of_date=resolved_report_date,
        # The business report_date remains exact; this date identifies lineage fallback only.
        fallback_date=(
            str(lineage.get("_lineage_fallback_date") or "").strip() or None
            if pnl_lineage_fallback
            else None
        ),
    )
    return build_formal_result_envelope(
        result_meta=result_meta,
        result_payload=payload.model_dump(mode="json"),
    )


def _merge_bridge_quality_flag(*, summary_quality: str, curve_latest_fallback: bool) -> QualityFlag:
    # error > stale > warning > ok; latest_snapshot adds stale; vendor_unavailable does not.
    flags = {summary_quality}
    if curve_latest_fallback:
        flags.add("stale")
    for flag in ("error", "stale", "warning"):
        if flag in flags:
            return flag
    return "ok"


def _build_summary(rows: list[PnlBridgeRow]) -> PnlBridgeSummarySchema:
    ok_count = sum(1 for row in rows if row.quality_flag == "ok")
    warning_count = sum(1 for row in rows if row.quality_flag == "warning")
    error_count = sum(1 for row in rows if row.quality_flag == "error")
    worst_quality = "ok"
    if any(row.quality_flag == "error" for row in rows):
        worst_quality = "error"
    elif any(row.quality_flag == "warning" for row in rows):
        worst_quality = "warning"

    # model_validate shares the same validation pipeline as __init__ but accepts
    # the Decimal inputs that the mode="before" coercion validator is designed for.
    return PnlBridgeSummarySchema.model_validate(
        {
            "row_count": len(rows),
            "ok_count": ok_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "total_beginning_dirty_mv": sum((row.beginning_dirty_mv for row in rows), ZERO),
            "total_ending_dirty_mv": sum((row.ending_dirty_mv for row in rows), ZERO),
            "total_carry": sum((row.carry for row in rows), ZERO),
            "total_roll_down": sum((row.roll_down for row in rows), ZERO),
            "total_treasury_curve": sum((row.treasury_curve for row in rows), ZERO),
            "total_credit_spread": sum((row.credit_spread for row in rows), ZERO),
            "total_fx_translation": sum((row.fx_translation for row in rows), ZERO),
            "total_realized_trading": sum((row.realized_trading for row in rows), ZERO),
            "total_unrealized_fv": sum((row.unrealized_fv for row in rows), ZERO),
            "total_manual_adjustment": sum((row.manual_adjustment for row in rows), ZERO),
            "total_explained_pnl": sum((row.explained_pnl for row in rows), ZERO),
            "total_actual_pnl": sum((row.actual_pnl for row in rows), ZERO),
            "total_residual": sum((row.residual for row in rows), ZERO),
            "quality_flag": worst_quality,
            # 汇总合计的金额不变；这三块只回答"合计里的 0 有多少行是没有可比输入"。
            "roll_down_availability": _availability_block(
                summarize_curve_effect_availability(
                    (row.roll_down_availability, row.roll_down_availability_reason)
                    for row in rows
                )
            ),
            "treasury_curve_availability": _availability_block(
                summarize_curve_effect_availability(
                    (row.treasury_curve_availability, row.treasury_curve_availability_reason)
                    for row in rows
                )
            ),
            "credit_spread_availability": _availability_block(
                summarize_curve_effect_availability(
                    (row.credit_spread_availability, row.credit_spread_availability_reason)
                    for row in rows
                )
            ),
        }
    )


def _availability_block(summary: CurveEffectAvailabilitySummary) -> dict[str, object]:
    return {
        "status": summary.status,
        "unavailable_rows": summary.unavailable_rows,
        "applicable_rows": summary.applicable_rows,
        "reasons": list(summary.reasons),
    }


def _row_diagnostic_warnings(rows: list[PnlBridgeRow]) -> list[str]:
    fallback_currency_mismatch_count = sum(
        1
        for row in rows
        if any("currency_basis mismatch" in diagnostic for diagnostic in row.balance_diagnostics)
    )
    actual_pnl_missing_count = sum(
        1
        for row in rows
        if any("actual_pnl missing" in diagnostic for diagnostic in row.balance_diagnostics)
    )
    warnings: list[str] = []
    if fallback_currency_mismatch_count:
        warnings.append(
            f"{fallback_currency_mismatch_count} bridge row(s) used fallback balance rows with "
            "currency_basis mismatch; review row balance_diagnostics."
        )
    if actual_pnl_missing_count:
        warnings.append(
            f"{actual_pnl_missing_count} bridge row(s) missing actual_pnl; "
            "residual_ratio unavailable and quality_flag set to warning."
        )
    return warnings


def _bridge_fx_base_currencies(
    pnl_fi_rows: list[dict[str, object]],
    balance_rows: list[dict[str, object]],
) -> set[str]:
    """Foreign currencies the bridge must load FX rates for.

    The PnL fact carries no maturity leg, so (instrument, portfolio, cost center,
    accounting_basis) is the finest key the two sides share — and one PnL row can
    therefore face several balance rows. Collect every currency they carry rather
    than letting the last row of the group decide: a PnL row whose currency is
    dropped here loses its rate and silently publishes ``fx_translation = 0`` with
    only a row-level FX_RATE_MISSING diagnostic to show for it.
    """
    balance_currencies: dict[tuple[str, str, str, str], set[str]] = {}
    for row in balance_rows:
        key = (
            str(row.get("instrument_code") or ""),
            str(row.get("portfolio_name") or ""),
            str(row.get("cost_center") or ""),
            str(row.get("accounting_basis") or ""),
        )
        currency = str(row.get("currency_code") or row.get("currency_basis") or "").upper().strip()
        if currency:
            balance_currencies.setdefault(key, set()).add(currency)
    required: set[str] = set()
    for row in pnl_fi_rows:
        key = (
            str(row.get("instrument_code") or ""),
            str(row.get("portfolio_name") or ""),
            str(row.get("cost_center") or ""),
            str(row.get("accounting_basis") or ""),
        )
        bases = balance_currencies.get(key) or {
            str(row.get("currency_basis") or "").upper().strip()
        }
        required.update(base for base in bases if base and base not in {"CNY", "CNX", "RMB"})
    return required


def _build_warnings(
    *,
    current_balance_rows: list[dict[str, object]],
    prior_balance_rows: list[dict[str, object]],
    prior_report_date: str | None,
) -> list[str]:
    warnings: list[str] = []
    if not current_balance_rows:
        warnings.append(
            "Current balance rows unavailable; ending_dirty_mv defaults to 0 where balance data is missing."
        )
    if prior_report_date is None:
        warnings.append(
            "No prior balance report date found; beginning_dirty_mv defaults to 0 where prior balance data is missing."
        )
    elif not prior_balance_rows:
        warnings.append(
            f"Prior balance rows unavailable for report_date={prior_report_date}; beginning_dirty_mv defaults to 0 where prior balance data is missing."
        )
    return warnings


def _bridge_warnings(
    *,
    balance_warnings: list[str],
    curve_warnings: list[str],
    lineage_warnings: list[str],
) -> list[str]:
    warnings = [*balance_warnings, *curve_warnings, *lineage_warnings]
    if warnings:
        return [PHASE3_WARNING, *warnings]
    return []


def _resolve_bridge_lineage(
    *,
    governance_dir: str,
    report_date: str,
    prior_report_date: str | None,
    current_balance_rows: list[dict[str, object]],
    prior_balance_rows: list[dict[str, object]],
    curve_snapshots: list[dict[str, object]],
) -> tuple[dict[str, object], list[str]]:
    pnl_lineage = _resolve_pnl_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
    )
    current_build = _resolve_balance_build_lineage(governance_dir, report_date=report_date)
    prior_build = (
        _resolve_balance_build_lineage(governance_dir, report_date=prior_report_date)
        if prior_report_date is not None
        else None
    )

    warnings: list[str] = []
    pnl_lineage_fallback = pnl_lineage.get("_lineage_fallback_mode") == "latest_snapshot"
    pnl_lineage_fallback_date = (
        str(pnl_lineage.get("_lineage_fallback_date") or "").strip() or None
    )
    if pnl_lineage_fallback:
        warnings.append(
            f"PnL lineage fallback used for report_date={report_date}; "
            f"lineage_report_date={pnl_lineage_fallback_date or 'unknown'}; "
            "exact completed build and exact-date manifest unavailable."
        )
    current_balance_lineage, used_current_fallback = _resolve_balance_lineage_component(
        build_lineage=current_build,
        balance_rows=current_balance_rows,
    )
    prior_balance_lineage, used_prior_fallback = _resolve_balance_lineage_component(
        build_lineage=prior_build,
        balance_rows=prior_balance_rows,
    )

    if used_current_fallback:
        warnings.append(
            f"Balance lineage fallback used for report_date={report_date}; completed balance-analysis build record unavailable."
        )
    if used_prior_fallback and prior_report_date is not None:
        warnings.append(
            f"Balance lineage fallback used for prior_report_date={prior_report_date}; completed balance-analysis build record unavailable."
        )

    curve_source = _merge_lineage_values(
        *[str(snapshot.get("source_version") or "").strip() for snapshot in curve_snapshots]
    )
    curve_vendor_names = _merge_lineage_values(
        *[str(snapshot.get("vendor_name") or "").strip() for snapshot in curve_snapshots]
    )
    curve_rule = _merge_lineage_values(
        *[str(snapshot.get("rule_version") or "").strip() for snapshot in curve_snapshots]
    )
    curve_vendor = _merge_lineage_values(
        *[str(snapshot.get("vendor_version") or "").strip() for snapshot in curve_snapshots]
    )

    combined_lineage: dict[str, object] = {
        "source_version": _merge_lineage_values(
            str(pnl_lineage["source_version"]),
            current_balance_lineage["source_version"],
            prior_balance_lineage["source_version"],
            curve_source,
            curve_vendor_names,
        ),
        "rule_version": _merge_lineage_values(
            str(pnl_lineage["rule_version"]),
            current_balance_lineage["rule_version"],
            prior_balance_lineage["rule_version"],
            curve_rule,
        ),
        "vendor_version": _merge_lineage_values(
            str(pnl_lineage["vendor_version"]),
            current_balance_lineage["vendor_version"],
            prior_balance_lineage["vendor_version"],
            curve_vendor,
        )
        or "vv_none",
    }
    if pnl_lineage_fallback:
        combined_lineage["_lineage_fallback_mode"] = "latest_snapshot"
        combined_lineage["_lineage_fallback_date"] = pnl_lineage_fallback_date
    return combined_lineage, warnings


def _resolve_balance_build_lineage(
    governance_dir: str,
    *,
    report_date: str,
) -> dict[str, object] | None:
    return resolve_completed_formal_build_lineage(
        governance_dir=governance_dir,
        cache_key=BALANCE_ANALYSIS_CACHE_KEY,
        job_name="balance_analysis_materialize",
        report_date=report_date,
    )


def _resolve_balance_lineage_component(
    *,
    build_lineage: dict[str, object] | None,
    balance_rows: list[dict[str, object]],
) -> tuple[dict[str, str], bool]:
    if build_lineage is not None:
        return (
            {
                "source_version": str(build_lineage.get("source_version") or ""),
                "rule_version": str(build_lineage.get("rule_version") or BALANCE_ANALYSIS_RULE_VERSION),
                "vendor_version": str(build_lineage.get("vendor_version") or "vv_none"),
            },
            False,
        )

    source_version = _merge_lineage_values(
        *[
            str(row.get("source_version") or "").strip()
            for row in balance_rows
            if str(row.get("source_version") or "").strip()
        ]
    )
    rule_version = _merge_lineage_values(
        *[
            str(row.get("rule_version") or "").strip()
            for row in balance_rows
            if str(row.get("rule_version") or "").strip()
        ]
    ) or BALANCE_ANALYSIS_RULE_VERSION
    if not balance_rows:
        return {"source_version": "", "rule_version": "", "vendor_version": ""}, False
    return (
        {
            "source_version": source_version,
            "rule_version": rule_version,
            "vendor_version": "vv_none",
        },
        True,
    )


def _merge_lineage_values(*values: str) -> str:
    merged = sorted({value.strip() for value in values if value and value.strip()})
    return "__".join(merged)


def _resolve_curve_for_service(
    *,
    repo: YieldCurveRepository,
    requested_trade_date: str | None,
    curve_type: str,
) -> tuple[dict[str, object] | None, str | None]:
    if requested_trade_date is None:
        return None, None
    exact_snapshot = repo.fetch_curve_snapshot(requested_trade_date, curve_type)
    if exact_snapshot is not None:
        return exact_snapshot, None
    if repo.fetch_curve(requested_trade_date, curve_type):
        raise RuntimeError(
            f"Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date={requested_trade_date}."
        )
    latest_trade_date = repo.fetch_latest_trade_date_on_or_before(curve_type, requested_trade_date)
    if latest_trade_date is None:
        return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}; curve effect remains 0."
    latest_snapshot = repo.fetch_curve_snapshot(latest_trade_date, curve_type)
    if latest_snapshot is None:
        if repo.fetch_curve(latest_trade_date, curve_type):
            raise RuntimeError(
                f"Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date={latest_trade_date}."
            )
        return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}; curve effect remains 0."
    return (
        latest_snapshot,
        format_yield_curve_latest_fallback_warning(
            curve_type=curve_type,
            resolved_trade_date=latest_trade_date,
            requested_trade_date=requested_trade_date,
        ),
    )


def _compact_warnings(values: list[str | None]) -> list[str]:
    return [value for value in values if value]


def _curve_warnings_for_bridge_rows(
    *,
    current_balance_rows: list[dict[str, object]],
    prior_balance_rows: list[dict[str, object]],
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
    for row in [*current_balance_rows, *prior_balance_rows]:
        curve_type = infer_curve_type(
            row.get("instrument_name"),
            row.get("bond_type"),
            row.get("asset_class"),
        )
        if classify_asset_class(" ".join(str(row.get(field) or "") for field in ("asset_class", "bond_type", "instrument_name"))) == "credit":
            needs_aaa = True
            needs_treasury = True
        elif curve_type == "cdb":
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


def _resolve_curve_pair_if_needed(
    *,
    curve_type: str,
    required_curve_types: set[str],
    repo: YieldCurveRepository,
    report_date: str,
    prior_date: str | None,
) -> tuple[dict[str, object] | None, str | None]:
    if curve_type not in required_curve_types:
        return None, None
    current_snapshot, current_warning = _resolve_curve_for_service(
        repo=repo,
        requested_trade_date=report_date,
        curve_type=curve_type,
    )
    if prior_date is None:
        prior_snapshot, prior_warning = None, None
    else:
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


def _optional_warning(snapshot: dict[str, object] | None, key: str) -> str | None:
    if snapshot is None:
        return None
    value = snapshot.get(key)
    return str(value) if isinstance(value, str) else None


def _snapshot_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _optional_snapshot(value: object) -> dict[str, object] | None:
    # "_prior_snapshot" is stored as dict | None by _resolve_curve_pair_if_needed.
    return value if isinstance(value, dict) else None


def _curve_points(snapshot: dict[str, object] | None) -> dict[str, Decimal] | None:
    points, _reason = _curve_points_with_reason(snapshot)
    return points


def _curve_points_with_reason(
    snapshot: dict[str, object] | None,
) -> tuple[dict[str, Decimal] | None, str | None]:
    """Strictly convert a snapshot curve; on failure return ``(None, reason)``.

    The reason feeds the warnings channel only (disclosure). Callers keep the
    designed zeroed-curve fallback for the numeric path.
    """
    if snapshot is None:
        return None, None
    value = snapshot.get("curve")
    if not isinstance(value, Mapping):
        return None, f"curve payload is not a mapping (got {type(value).__name__})"
    curve_points: dict[str, Decimal] = {}
    for tenor, rate in value.items():
        if not isinstance(tenor, str) or tenor not in TENOR_YEARS:
            return None, f"unknown tenor label {tenor!r}"
        try:
            decimal_rate = Decimal(str(rate))
        except (InvalidOperation, TypeError, ValueError):
            return None, f"invalid rate {rate!r} for tenor {tenor!r}"
        if not decimal_rate.is_finite():
            return None, f"non-finite rate {rate!r} for tenor {tenor!r}"
        curve_points[tenor] = decimal_rate
    return curve_points, None


def _resolve_pnl_lineage(*, governance_dir: str, report_date: str) -> dict[str, object]:
    return resolve_formal_manifest_lineage_with_completed_build(
        governance_dir=governance_dir,
        cache_key=PNL_CACHE_KEY,
        job_name="pnl_materialize",
        report_date=report_date,
    )


def normalize_natural_key_date(value: object) -> str:
    """Canonical string form of a date-typed key column.

    ``fact_formal_zqtz_balance_daily.maturity_date`` is stored as VARCHAR while
    ``zqtz_bond_daily_snapshot.maturity_date`` is a DATE, so the same position
    yields ``'2026-09-21'`` on one side and ``date(2026, 9, 21)`` on the other.
    Both sides of every natural-key join must normalize through here or the join
    silently degenerates into a miss.
    """
    if value in (None, ""):
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def natural_key_component(row: Mapping[str, object], column: str) -> str:
    if column == "currency_code":
        return str(row.get(column) or "").upper()
    if column.endswith("_date"):
        return normalize_natural_key_date(row.get(column))
    return str(row.get(column) or "")


# ``fetch_formal_zqtz_rows`` is already sliced by report_date / position_scope /
# currency_basis, so what remains of the fact's natural key is the intra-slice
# identity. Derived from ``ZQTZ_BALANCE_NATURAL_KEY`` rather than restated, so the
# read path and the load gate cannot drift apart. ``currency_code`` is appended as
# the pre-existing currency guard: it is redundant given the rest of the key, and
# keeping it means a CNY row can never pick up a foreign leg's amounts.
_ZQTZ_SLICE_COLUMNS = frozenset({"report_date", "position_scope", "currency_basis"})
_NATIVE_AMOUNT_KEY_COLUMNS: tuple[str, ...] = (
    *(column for column in ZQTZ_BALANCE_NATURAL_KEY if column not in _ZQTZ_SLICE_COLUMNS),
    "currency_code",
)

# ``zqtz_bond_daily_snapshot`` has no ``accounting_basis`` column; the formal
# pipeline derives it from ``asset_class`` (持有至到期类资产/应收投资款项→AC,
# 可供出售类资产→FVOCI, 交易性资产→FVTPL), and the fact table carries that raw
# ``asset_class`` verbatim. It is the snapshot-side discriminator and is at least
# as fine as ``accounting_basis``.
_SNAPSHOT_FACE_VALUE_KEY_COLUMNS: tuple[str, ...] = tuple(
    "asset_class" if column == "accounting_basis" else column
    for column in _NATIVE_AMOUNT_KEY_COLUMNS
)


def _native_amount_key(row: Mapping[str, object]) -> tuple[str, ...]:
    """Natural key of ``fact_formal_zqtz_balance_daily`` inside one fetched slice.

    ``accounting_basis`` and ``maturity_date`` are load-bearing, not decoration: a
    single bond is routinely booked into two accounting books at once (from
    2025-09-30 onwards) and the same instrument_code can carry two maturity legs
    during a reclass. Without them the key covers 1,555 duplicate groups per
    currency_basis and the enrichment attaches another leg's native market value.
    """
    return tuple(natural_key_component(row, column) for column in _NATIVE_AMOUNT_KEY_COLUMNS)


def _snapshot_face_value_key(row: Mapping[str, object]) -> tuple[str, ...]:
    """The same position identity expressed in the raw snapshot's vocabulary."""
    return tuple(
        natural_key_component(row, column) for column in _SNAPSHOT_FACE_VALUE_KEY_COLUMNS
    )


def format_duplicate_natural_key_error(
    *,
    source: str,
    report_date: str,
    key_columns: tuple[str, ...],
    duplicate_keys: list[tuple[str, ...]],
) -> str:
    sample = "; ".join("/".join(key) for key in sorted(duplicate_keys)[:5])
    return (
        f"Duplicate natural key in {source} for report_date={report_date}: "
        f"{len(duplicate_keys)} key(s) on ({', '.join(key_columns)}) resolve to more than one row, "
        f"so the native exposure base is ambiguous. Sample: {sample}."
    )


def _index_rows_by_natural_key(
    rows: list[dict[str, object]],
    *,
    key_of,
    key_columns: tuple[str, ...],
    source: str,
    report_date: str,
) -> dict[tuple[str, ...], dict[str, object]]:
    """Index enrichment rows by their natural key, refusing ambiguity.

    The previous ``setdefault`` (and, on the snapshot side, a dict comprehension)
    on a non-unique key let row order decide the winner and handed every other row
    of the group another leg's amounts. A second row under a key that is supposed
    to be unique is a fact integrity failure, not a tie to break: picking either
    one silently is exactly the cross-assignment these joins have to stop
    producing, so the caller is told instead.
    """
    indexed: dict[tuple[str, ...], dict[str, object]] = {}
    duplicate_keys: list[tuple[str, ...]] = []
    for row in rows:
        key = key_of(row)
        if key in indexed:
            duplicate_keys.append(key)
            continue
        indexed[key] = row
    if duplicate_keys:
        raise RuntimeError(
            format_duplicate_natural_key_error(
                source=source,
                report_date=report_date,
                key_columns=key_columns,
                duplicate_keys=duplicate_keys,
            )
        )
    return indexed


def _attach_native_exposure_fields(
    *,
    balance_repo: BalanceAnalysisRepository,
    report_date: str,
    balance_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Attach native-currency exposure fields to the CNY-basis bridge balance rows.

    The bridge balance rows are the CNY projection, so their ``market_value_amount`` /
    ``accrued_interest_amount`` are already FX-converted. ``fx_translation`` needs the
    native dirty market value, so enrich each row with ``market_value_native`` /
    ``accrued_interest_native`` from the native-basis formal fact rows (same fact table,
    ``currency_basis='native'``), plus ``face_value_native`` from the raw snapshot as
    the legacy fallback base.

    Both joins key on the position's natural key, which needs the accounting book and
    the maturity leg on top of (instrument_code, portfolio_name, cost_center,
    currency_code) — see ``_native_amount_key`` / ``_snapshot_face_value_key``.
    """
    if not balance_rows:
        return balance_rows
    native_face_values = _index_rows_by_natural_key(
        balance_repo.fetch_zqtz_snapshot_native_face_value_rows(report_date=report_date),
        key_of=_snapshot_face_value_key,
        key_columns=_SNAPSHOT_FACE_VALUE_KEY_COLUMNS,
        source="zqtz_bond_daily_snapshot",
        report_date=report_date,
    )
    native_amounts = _index_rows_by_natural_key(
        balance_repo.fetch_formal_zqtz_rows(
            report_date=report_date,
            position_scope="asset",
            currency_basis="native",
        ),
        key_of=_native_amount_key,
        key_columns=_NATIVE_AMOUNT_KEY_COLUMNS,
        source="fact_formal_zqtz_balance_daily (position_scope=asset, currency_basis=native)",
        report_date=report_date,
    )
    if not native_face_values and not native_amounts:
        return balance_rows
    enriched_rows: list[dict[str, object]] = []
    for row in balance_rows:
        enriched = row
        face_value_row = native_face_values.get(_snapshot_face_value_key(row))
        if face_value_row is not None and face_value_row.get("face_value_native") is not None:
            enriched = {**enriched, "face_value_native": face_value_row["face_value_native"]}
        native_row = native_amounts.get(_native_amount_key(row))
        if native_row is not None:
            market_value_native = native_row.get("market_value_amount")
            accrued_interest_native = native_row.get("accrued_interest_amount")
            if market_value_native is not None:
                enriched = {**enriched, "market_value_native": market_value_native}
            if accrued_interest_native is not None:
                enriched = {**enriched, "accrued_interest_native": accrued_interest_native}
        enriched_rows.append(enriched)
    return enriched_rows
