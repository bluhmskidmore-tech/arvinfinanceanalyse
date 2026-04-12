from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.bond_analytics.common import classify_asset_class, infer_curve_type
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.core_finance.pnl_bridge import (
    PnlBridgeRow,
    build_pnl_bridge_rows,
    required_curve_types_for_pnl_bridge,
)
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
from backend.app.schemas.pnl_bridge import (
    PnlBridgePayload,
    PnlBridgeRowSchema,
    PnlBridgeSummarySchema,
)
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)
from backend.app.tasks.pnl_materialize import CACHE_KEY as PNL_CACHE_KEY
from backend.app.tasks.pnl_materialize import PNL_RESULT_CACHE_VERSION
from backend.app.tasks.balance_analysis_materialize import (
    CACHE_KEY as BALANCE_ANALYSIS_CACHE_KEY,
    CACHE_VERSION as BALANCE_ANALYSIS_CACHE_VERSION,
    RULE_VERSION as BALANCE_ANALYSIS_RULE_VERSION,
)
from backend.app.tasks.yield_curve_materialize import CACHE_VERSION as YIELD_CURVE_CACHE_VERSION


PHASE3_WARNING = (
    "Phase 3 partial delivery: fx_translation remains fixed at 0; roll_down / treasury_curve / credit_spread use governed curves when available."
)
BRIDGE_CACHE_VERSION = (
    f"cv_pnl_bridge_start_pack_v1__{PNL_RESULT_CACHE_VERSION}__{BALANCE_ANALYSIS_CACHE_VERSION}__{YIELD_CURVE_CACHE_VERSION}"
)
ZERO = Decimal("0")


def pnl_bridge_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, object]:
    pnl_repo = PnlRepository(duckdb_path)
    balance_repo = BalanceAnalysisRepository(duckdb_path)
    curve_repo = YieldCurveRepository(duckdb_path)
    if report_date not in pnl_repo.list_formal_fi_report_dates():
        raise ValueError(f"No pnl bridge data found for report_date={report_date} in fact_formal_pnl_fi.")

    pnl_fi_rows = pnl_repo.fetch_formal_fi_rows(report_date)
    current_balance_rows = balance_repo.fetch_pnl_bridge_zqtz_balance_rows(report_date=report_date)
    prior_date = balance_repo.resolve_prior_pnl_bridge_balance_report_date(report_date=report_date)
    prior_balance_rows = (
        balance_repo.fetch_pnl_bridge_zqtz_balance_rows(report_date=prior_date) if prior_date else []
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
    treasury_prior = treasury_current.get("_prior_snapshot") if treasury_current else None
    cdb_prior = cdb_current.get("_prior_snapshot") if cdb_current else None
    aaa_prior = aaa_current.get("_prior_snapshot") if aaa_current else None
    treasury_prior_warning = treasury_current.get("_prior_warning") if treasury_current else None
    cdb_prior_warning = cdb_current.get("_prior_warning") if cdb_current else None
    aaa_prior_warning = aaa_current.get("_prior_warning") if aaa_current else None
    relevant_curve_warnings = _curve_warnings_for_bridge_rows(
        current_balance_rows=current_balance_rows,
        prior_balance_rows=prior_balance_rows,
        treasury_current_warning=treasury_current_warning,
        treasury_prior_warning=treasury_prior_warning,
        cdb_current_warning=cdb_current_warning,
        cdb_prior_warning=cdb_prior_warning,
        aaa_current_warning=aaa_current_warning,
        aaa_prior_warning=aaa_prior_warning,
    )
    curve_latest_fallback = any(
        w and "Using latest available" in w
        for w in relevant_curve_warnings
    )
    curve_unavailable = any(
        w and w.startswith("No ")
        for w in relevant_curve_warnings
    )

    rows = build_pnl_bridge_rows(
        pnl_fi_rows=pnl_fi_rows,
        balance_rows_current=current_balance_rows,
        balance_rows_prior=prior_balance_rows,
        treasury_curve_current=treasury_current["curve"] if treasury_current else None,
        treasury_curve_prior=treasury_prior["curve"] if treasury_prior else None,
        cdb_curve_current=cdb_current["curve"] if cdb_current else None,
        cdb_curve_prior=cdb_prior["curve"] if cdb_prior else None,
        aaa_credit_curve_current=aaa_current["curve"] if aaa_current else None,
        aaa_credit_curve_prior=aaa_prior["curve"] if aaa_prior else None,
    )
    summary = _build_summary(rows)
    lineage, lineage_warnings = _resolve_bridge_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
        prior_report_date=prior_date,
        current_balance_rows=current_balance_rows,
        prior_balance_rows=prior_balance_rows,
        curve_snapshots=[
            snapshot
            for snapshot in (treasury_current, treasury_prior, cdb_current, cdb_prior, aaa_current, aaa_prior)
            if snapshot is not None
        ],
    )
    payload = PnlBridgePayload(
        report_date=report_date,
        rows=[PnlBridgeRowSchema.model_validate(row) for row in rows],
        summary=summary,
        warnings=_build_warnings(
            current_balance_rows=current_balance_rows,
            prior_balance_rows=prior_balance_rows,
            prior_report_date=prior_date,
        )
        + _compact_warnings(
            [
                *relevant_curve_warnings,
            ]
        )
        + lineage_warnings,
    )
    result_meta = build_formal_result_meta(
        trace_id=f"tr_pnl_bridge_{report_date}",
        result_kind="pnl.bridge",
        cache_version=BRIDGE_CACHE_VERSION,
        source_version=str(lineage["source_version"]),
        rule_version=str(lineage["rule_version"]),
        vendor_version=str(lineage["vendor_version"]),
    ).model_copy(
        update={
            "quality_flag": summary.quality_flag,
            **(
                {"fallback_mode": "none", "vendor_status": "vendor_unavailable"}
                if curve_unavailable
                else (
                    {"fallback_mode": "latest_snapshot", "vendor_status": "vendor_stale"}
                    if curve_latest_fallback
                    else {}
                )
            ),
        }
    )
    return build_formal_result_envelope(
        result_meta=result_meta,
        result_payload=payload.model_dump(mode="json"),
    )


def _build_summary(rows: list[PnlBridgeRow]) -> PnlBridgeSummarySchema:
    ok_count = sum(1 for row in rows if row.quality_flag == "ok")
    warning_count = sum(1 for row in rows if row.quality_flag == "warning")
    error_count = sum(1 for row in rows if row.quality_flag == "error")
    worst_quality = "ok"
    if any(row.quality_flag == "error" for row in rows):
        worst_quality = "error"
    elif any(row.quality_flag == "warning" for row in rows):
        worst_quality = "warning"

    return PnlBridgeSummarySchema(
        row_count=len(rows),
        ok_count=ok_count,
        warning_count=warning_count,
        error_count=error_count,
        total_beginning_dirty_mv=sum((row.beginning_dirty_mv for row in rows), ZERO),
        total_ending_dirty_mv=sum((row.ending_dirty_mv for row in rows), ZERO),
        total_carry=sum((row.carry for row in rows), ZERO),
        total_roll_down=sum((row.roll_down for row in rows), ZERO),
        total_treasury_curve=sum((row.treasury_curve for row in rows), ZERO),
        total_credit_spread=sum((row.credit_spread for row in rows), ZERO),
        total_fx_translation=sum((row.fx_translation for row in rows), ZERO),
        total_realized_trading=sum((row.realized_trading for row in rows), ZERO),
        total_unrealized_fv=sum((row.unrealized_fv for row in rows), ZERO),
        total_manual_adjustment=sum((row.manual_adjustment for row in rows), ZERO),
        total_explained_pnl=sum((row.explained_pnl for row in rows), ZERO),
        total_actual_pnl=sum((row.actual_pnl for row in rows), ZERO),
        total_residual=sum((row.residual for row in rows), ZERO),
        quality_flag=worst_quality,
    )


def _build_warnings(
    *,
    current_balance_rows: list[dict[str, object]],
    prior_balance_rows: list[dict[str, object]],
    prior_report_date: str | None,
) -> list[str]:
    warnings = [PHASE3_WARNING]
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


def _resolve_bridge_lineage(
    *,
    governance_dir: str,
    report_date: str,
    prior_report_date: str | None,
    current_balance_rows: list[dict[str, object]],
    prior_balance_rows: list[dict[str, object]],
    curve_snapshots: list[dict[str, object]],
) -> tuple[dict[str, str], list[str]]:
    pnl_lineage = _resolve_pnl_manifest_lineage(governance_dir)
    current_build = _resolve_balance_build_lineage(governance_dir, report_date=report_date)
    prior_build = (
        _resolve_balance_build_lineage(governance_dir, report_date=prior_report_date)
        if prior_report_date is not None
        else None
    )

    warnings: list[str] = []
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

    return (
        {
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
        },
        warnings,
    )


def _resolve_balance_build_lineage(
    governance_dir: str,
    *,
    report_date: str,
) -> dict[str, object] | None:
    rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    matches = [
        row
        for row in rows
        if str(row.get("cache_key")) == BALANCE_ANALYSIS_CACHE_KEY
        and str(row.get("job_name")) == "balance_analysis_materialize"
        and str(row.get("status")) == "completed"
        and str(row.get("report_date")) == report_date
    ]
    return matches[-1] if matches else None


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
        f"Using latest available {curve_type} curve from trade_date={latest_trade_date} for requested trade_date={requested_trade_date}.",
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


def _resolve_pnl_manifest_lineage(governance_dir: str) -> dict[str, object]:
    rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_MANIFEST_STREAM)
    matches = [row for row in rows if str(row.get("cache_key")) == PNL_CACHE_KEY]
    if not matches:
        raise RuntimeError(f"Canonical pnl lineage unavailable for cache_key={PNL_CACHE_KEY}.")
    latest = matches[-1]
    required = ("source_version", "vendor_version", "rule_version")
    missing = [key for key in required if key not in latest or latest.get(key) in (None, "")]
    if missing:
        raise RuntimeError(
            f"Canonical pnl lineage malformed for cache_key={PNL_CACHE_KEY}: missing {', '.join(missing)}."
        )
    return latest
