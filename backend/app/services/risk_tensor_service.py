from __future__ import annotations

import uuid
from datetime import date

from backend.app.governance.formal_compute_lineage import resolve_formal_manifest_lineage
from backend.app.repositories.risk_tensor_repo import (
    RiskTensorRepository,
    load_current_tyw_liability_lineage_by_report_date,
    load_current_tyw_liability_rule_version,
    load_current_tyw_liability_source_version,
    load_latest_bond_analytics_lineage,
    load_latest_bond_analytics_lineage_by_report_date,
)
from backend.app.schemas.risk_tensor import RiskTensorPayload
from backend.app.schemas.common_numeric import Numeric, null_numeric, numeric_from_raw
from backend.app.services.explicit_numeric import promote_flat_payload
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope_from_lineage,
)
from backend.app.tasks.risk_tensor_materialize import CACHE_KEY, CACHE_VERSION, RULE_VERSION


def risk_tensor_dates_envelope(
    duckdb_path: str,
    governance_dir: str,
) -> dict[str, object]:
    repo = RiskTensorRepository(str(duckdb_path))
    candidate_rows = repo.list_report_date_lineage_rows()
    candidate_report_dates = [str(row["report_date"]) for row in candidate_rows]
    report_dates: list[str] = []
    blocked_report_dates: list[dict[str, str]] = []
    try:
        bond_lineage_by_report_date = load_latest_bond_analytics_lineage_by_report_date(
            governance_dir=governance_dir,
        )
    except TimeoutError as exc:
        raise RuntimeError("Risk tensor lineage store is temporarily unavailable.") from exc
    tyw_liability_lineage_by_report_date = load_current_tyw_liability_lineage_by_report_date(
        duckdb_path=str(duckdb_path),
    )
    for row in candidate_rows:
        candidate_report_date = str(row["report_date"])
        tyw_liability_lineage = tyw_liability_lineage_by_report_date.get(candidate_report_date, {})
        stale_reason = _risk_tensor_freshness_error_from_values(
            report_date_text=candidate_report_date,
            row=row,
            upstream_source_version=str(
                bond_lineage_by_report_date.get(candidate_report_date, {}).get("source_version") or ""
            ),
            current_tyw_liability_source_version=str(
                tyw_liability_lineage.get("source_version") or ""
            ),
            current_tyw_liability_rule_version=str(
                tyw_liability_lineage.get("rule_version") or ""
            ),
        )
        if stale_reason is not None:
            blocked_report_dates.append(
                {
                    "report_date": candidate_report_date,
                    "reason": stale_reason,
                }
            )
            continue
        report_dates.append(candidate_report_date)

    manifest_lineage: dict[str, object] | None = None
    source_version_value = "sv_risk_tensor_empty"
    rule_version_value = RULE_VERSION
    vendor_version_value = "vv_none"
    if candidate_report_dates:
        try:
            manifest_lineage = resolve_formal_manifest_lineage(
                governance_dir=governance_dir,
                cache_key=CACHE_KEY,
            )
        except RuntimeError:
            try:
                latest_lineage = bond_lineage_by_report_date.get(candidate_report_dates[0])
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
        result_payload={
            "report_dates": report_dates,
            "blocked_report_dates": blocked_report_dates,
        },
    )


def risk_tensor_envelope(
    duckdb_path: str,
    governance_dir: str,
    report_date: str | date,
) -> dict[str, object]:
    report_date_value = _coerce_report_date(report_date)
    report_date_text = report_date_value.isoformat()
    row = RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(report_date_text)

    if row is None:
        upstream_lineage = load_latest_bond_analytics_lineage(
            governance_dir=governance_dir,
            report_date=report_date_text,
        )
        if upstream_lineage is None:
            raise ValueError(f"No risk tensor data found for report_date={report_date_text}.")
        raise RuntimeError(
            f"Risk tensor fact missing for report_date={report_date_text} while bond analytics lineage exists."
        )

    stale_reason = _risk_tensor_freshness_error(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date_text=report_date_text,
        row=row,
    )
    if stale_reason is not None:
        raise RuntimeError(stale_reason)

    payload = RiskTensorPayload.model_validate(
        promote_flat_payload(
            {
                "report_date": report_date_value,
                "portfolio_dv01": row["portfolio_dv01"],
                "regulatory_dv01": row["regulatory_dv01"],
                "krd_1y": row["krd_1y"],
                "krd_3y": row["krd_3y"],
                "krd_5y": row["krd_5y"],
                "krd_7y": row["krd_7y"],
                "krd_10y": row["krd_10y"],
                "krd_30y": row["krd_30y"],
                "cs01": row["cs01"],
                "portfolio_convexity": row["portfolio_convexity"],
                "portfolio_modified_duration": row["portfolio_modified_duration"],
                "issuer_concentration_hhi": row["issuer_concentration_hhi"],
                "issuer_top5_weight": row["issuer_top5_weight"],
                "asset_cashflow_30d": row["asset_cashflow_30d"],
                "asset_cashflow_90d": row["asset_cashflow_90d"],
                "liability_cashflow_30d": row["liability_cashflow_30d"],
                "liability_cashflow_90d": row["liability_cashflow_90d"],
                "liquidity_gap_30d": row["liquidity_gap_30d"],
                "liquidity_gap_90d": row["liquidity_gap_90d"],
                "liquidity_gap_30d_ratio": row["liquidity_gap_30d_ratio"],
                "total_market_value": row["total_market_value"],
                "bond_count": int(row["bond_count"]),
                "quality_flag": str(row["quality_flag"]),
                "warnings": list(row["warnings"]),
                "dv01_controls": _build_dv01_controls(row),
            },
            RiskTensorPayload,
        )
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


def _build_dv01_controls(row: dict[str, object]) -> dict[str, object]:
    regulatory_dv01 = _float_or_none(row.get("regulatory_dv01"))
    stress_scenarios = [
        _build_dv01_stress_scenario(
            scenario_key="parallel_up_10bp",
            label="+10bp",
            shock_bp=10.0,
            regulatory_dv01=regulatory_dv01,
        ),
        _build_dv01_stress_scenario(
            scenario_key="parallel_up_25bp",
            label="+25bp",
            shock_bp=25.0,
            regulatory_dv01=regulatory_dv01,
        ),
    ]
    dominant_bucket, dominant_krd = _dominant_krd_bucket(row)
    return {
        "basis": "regulatory_dv01",
        "limit_status": "pending_configuration",
        "approved_limit_dv01": None,
        "limit_usage_ratio": None,
        "volatility_status": "pending_market_volatility",
        "daily_rate_volatility_bp": None,
        "dominant_krd_bucket": dominant_bucket,
        "dominant_krd": dominant_krd,
        "stress_scenarios": stress_scenarios,
        "control_message": "未接入正式限额源前，只展示当前监管口径敞口和标准平行冲击，不判定是否超限。",
        "action_hint": "经营落地需要先配置审批 DV01 限额、利率波动率输入与预警阈值，再计算使用率和波动预警。",
    }


def _build_dv01_stress_scenario(
    *,
    scenario_key: str,
    label: str,
    shock_bp: float,
    regulatory_dv01: float | None,
) -> dict[str, object]:
    estimated_pnl_impact = None if regulatory_dv01 is None else -regulatory_dv01 * shock_bp
    return {
        "scenario_key": scenario_key,
        "label": label,
        "shock_bp": numeric_from_raw(raw=shock_bp, unit="bp", precision=0, sign_aware=True).model_dump(mode="json"),
        "estimated_pnl_impact": numeric_from_raw(
            raw=estimated_pnl_impact,
            unit="yuan",
            precision=2,
            sign_aware=True,
        ).model_dump(mode="json"),
    }


def _dominant_krd_bucket(row: dict[str, object]) -> tuple[str, Numeric]:
    bucket_fields = (
        ("1Y", "krd_1y"),
        ("3Y", "krd_3y"),
        ("5Y", "krd_5y"),
        ("7Y", "krd_7y"),
        ("10Y", "krd_10y"),
        ("30Y", "krd_30y"),
    )
    values = [
        (bucket, _float_or_none(row.get(field)))
        for bucket, field in bucket_fields
    ]
    numeric_values = [(bucket, value) for bucket, value in values if value is not None]
    if not numeric_values:
        return "n/a", null_numeric(unit="ratio", sign_aware=True)
    bucket, value = max(numeric_values, key=lambda item: abs(item[1]))
    return bucket, numeric_from_raw(raw=value, unit="ratio", precision=2, sign_aware=True)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, ArithmeticError):
        return None


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _risk_tensor_freshness_error(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_date_text: str,
    row: dict[str, object] | None,
) -> str | None:
    if row is None:
        return f"Risk tensor fact missing for report_date={report_date_text}."

    upstream_lineage = load_latest_bond_analytics_lineage(
        governance_dir=governance_dir,
        report_date=report_date_text,
    )
    if upstream_lineage is None or not upstream_lineage["source_version"]:
        upstream_source_version = ""
    else:
        upstream_source_version = upstream_lineage["source_version"]

    current_tyw_liability_source_version = load_current_tyw_liability_source_version(
        duckdb_path=str(duckdb_path),
        report_date=report_date_text,
    )
    current_tyw_liability_rule_version = load_current_tyw_liability_rule_version(
        duckdb_path=str(duckdb_path),
        report_date=report_date_text,
    )

    return _risk_tensor_freshness_error_from_values(
        report_date_text=report_date_text,
        row=row,
        upstream_source_version=upstream_source_version,
        current_tyw_liability_source_version=current_tyw_liability_source_version,
        current_tyw_liability_rule_version=current_tyw_liability_rule_version,
    )


def _risk_tensor_freshness_error_from_values(
    *,
    report_date_text: str,
    row: dict[str, object] | None,
    upstream_source_version: str,
    current_tyw_liability_source_version: str,
    current_tyw_liability_rule_version: str,
) -> str | None:
    if row is None:
        return f"Risk tensor fact missing for report_date={report_date_text}."

    if not upstream_source_version:
        return (
            f"Bond analytics lineage missing for report_date={report_date_text}; "
            "cannot validate risk tensor freshness."
        )

    if str(row.get("upstream_source_version") or "").strip() != upstream_source_version:
        return f"Risk tensor stale against bond analytics lineage for report_date={report_date_text}."

    stored_tyw_liability_source_version = str(row.get("liability_source_version") or "").strip()
    if current_tyw_liability_source_version and (
        stored_tyw_liability_source_version != current_tyw_liability_source_version
    ):
        return f"Risk tensor stale against TYW liability lineage for report_date={report_date_text}."

    stored_tyw_liability_rule_version = str(row.get("liability_rule_version") or "").strip()
    if current_tyw_liability_rule_version and (
        stored_tyw_liability_rule_version != current_tyw_liability_rule_version
    ):
        return f"Risk tensor stale against TYW liability lineage for report_date={report_date_text}."
    return None


def _coerce_report_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
