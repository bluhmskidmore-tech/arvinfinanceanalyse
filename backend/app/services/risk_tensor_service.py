from __future__ import annotations

import uuid
from datetime import date

from backend.app.governance.formal_compute_lineage import resolve_formal_manifest_lineage
from backend.app.repositories.risk_tensor_repo import (
    load_current_tyw_liability_rule_version,
    RiskTensorRepository,
    load_current_tyw_liability_source_version,
    load_latest_bond_analytics_lineage,
)
from backend.app.schemas.risk_tensor import RiskTensorPayload
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope_from_lineage,
)
from backend.app.tasks.risk_tensor_materialize import CACHE_KEY, CACHE_VERSION, RULE_VERSION


def risk_tensor_dates_envelope(
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, object]:
    report_dates = RiskTensorRepository(str(duckdb_path)).list_report_dates()
    manifest_lineage: dict[str, object] | None = None
    source_version_value = "sv_risk_tensor_empty"
    rule_version_value = RULE_VERSION
    vendor_version_value = "vv_none"
    if report_dates:
        try:
            manifest_lineage = resolve_formal_manifest_lineage(
                governance_dir=governance_dir,
                cache_key=CACHE_KEY,
            )
        except RuntimeError:
            try:
                latest_lineage = load_latest_bond_analytics_lineage(
                    governance_dir=governance_dir,
                    report_date=report_dates[0],
                )
            except RuntimeError:
                latest_lineage = None
            if latest_lineage is not None:
                source_version_value = (
                    str(latest_lineage.get("source_version") or "").strip()
                    or source_version_value
                )

    return build_formal_result_envelope_from_lineage(
        trace_id=_trace_id(),
        result_kind="risk.tensor.dates",
        lineage=manifest_lineage,
        default_cache_version=CACHE_VERSION,
        source_version=source_version_value,
        rule_version=rule_version_value,
        vendor_version=vendor_version_value,
        source_surface="risk_tensor",
        result_payload={"report_dates": report_dates},
    )


def risk_tensor_envelope(
    duckdb_path: str,
    governance_dir: str,
    report_date: str | date,
) -> dict[str, object]:
    report_date_value = _coerce_report_date(report_date)
    report_date_text = report_date_value.isoformat()
    row = RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(report_date_text)
    upstream_lineage = load_latest_bond_analytics_lineage(
        governance_dir=governance_dir,
        report_date=report_date_text,
    )

    if row is None:
        if upstream_lineage is None:
            raise ValueError(f"No risk tensor data found for report_date={report_date_text}.")
        raise RuntimeError(
            f"Risk tensor fact missing for report_date={report_date_text} while bond analytics lineage exists."
        )

    if upstream_lineage is None or not upstream_lineage["source_version"]:
        raise RuntimeError(
            f"Bond analytics lineage missing for report_date={report_date_text}; cannot validate risk tensor freshness."
        )

    if str(row.get("upstream_source_version") or "").strip() != upstream_lineage["source_version"]:
        raise RuntimeError(
            f"Risk tensor stale against bond analytics lineage for report_date={report_date_text}."
        )

    current_tyw_liability_source_version = load_current_tyw_liability_source_version(
        duckdb_path=str(duckdb_path),
        report_date=report_date_text,
    )
    stored_tyw_liability_source_version = str(row.get("liability_source_version") or "").strip()
    if current_tyw_liability_source_version and (
        stored_tyw_liability_source_version != current_tyw_liability_source_version
    ):
        raise RuntimeError(
            f"Risk tensor stale against TYW liability lineage for report_date={report_date_text}."
        )
    current_tyw_liability_rule_version = load_current_tyw_liability_rule_version(
        duckdb_path=str(duckdb_path),
        report_date=report_date_text,
    )
    stored_tyw_liability_rule_version = str(row.get("liability_rule_version") or "").strip()
    if current_tyw_liability_rule_version and (
        stored_tyw_liability_rule_version != current_tyw_liability_rule_version
    ):
        raise RuntimeError(
            f"Risk tensor stale against TYW liability lineage for report_date={report_date_text}."
        )

    payload = RiskTensorPayload(
        report_date=report_date_value,
        portfolio_dv01=row["portfolio_dv01"],
        krd_1y=row["krd_1y"],
        krd_3y=row["krd_3y"],
        krd_5y=row["krd_5y"],
        krd_7y=row["krd_7y"],
        krd_10y=row["krd_10y"],
        krd_30y=row["krd_30y"],
        cs01=row["cs01"],
        portfolio_convexity=row["portfolio_convexity"],
        portfolio_modified_duration=row["portfolio_modified_duration"],
        issuer_concentration_hhi=row["issuer_concentration_hhi"],
        issuer_top5_weight=row["issuer_top5_weight"],
        asset_cashflow_30d=row["asset_cashflow_30d"],
        asset_cashflow_90d=row["asset_cashflow_90d"],
        liability_cashflow_30d=row["liability_cashflow_30d"],
        liability_cashflow_90d=row["liability_cashflow_90d"],
        liquidity_gap_30d=row["liquidity_gap_30d"],
        liquidity_gap_90d=row["liquidity_gap_90d"],
        liquidity_gap_30d_ratio=row["liquidity_gap_30d_ratio"],
        total_market_value=row["total_market_value"],
        bond_count=int(row["bond_count"]),
        quality_flag=str(row["quality_flag"]),
        warnings=list(row["warnings"]),
    )
    return build_formal_result_envelope_from_lineage(
        trace_id=_trace_id(),
        result_kind="risk.tensor",
        lineage=row,
        default_cache_version=CACHE_VERSION,
        source_version=str(row["source_version"]),
        rule_version=str(row.get("rule_version") or RULE_VERSION),
        vendor_version="vv_none",
        quality_flag=payload.quality_flag,
        source_surface="risk_tensor",
        result_payload=payload.model_dump(mode="json"),
    )


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _coerce_report_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
