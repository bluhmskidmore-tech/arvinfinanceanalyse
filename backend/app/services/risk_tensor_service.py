from __future__ import annotations

import uuid
from datetime import date

from backend.app.repositories.risk_tensor_repo import (
    RiskTensorRepository,
    load_latest_bond_analytics_lineage,
)
from backend.app.schemas.risk_tensor import RiskTensorPayload
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)
from backend.app.tasks.risk_tensor_materialize import CACHE_VERSION, RULE_VERSION


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
        liquidity_gap_30d=row["liquidity_gap_30d"],
        liquidity_gap_90d=row["liquidity_gap_90d"],
        liquidity_gap_30d_ratio=row["liquidity_gap_30d_ratio"],
        total_market_value=row["total_market_value"],
        bond_count=int(row["bond_count"]),
        quality_flag=str(row["quality_flag"]),
        warnings=list(row["warnings"]),
    )
    meta = build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind="risk.tensor",
        cache_version=str(row.get("cache_version") or CACHE_VERSION),
        source_version=str(row["source_version"]),
        rule_version=str(row.get("rule_version") or RULE_VERSION),
        vendor_version="vv_none",
    ).model_copy(update={"quality_flag": payload.quality_flag})
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _coerce_report_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
