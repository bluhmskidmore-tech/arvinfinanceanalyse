from __future__ import annotations

import uuid
from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Any

import duckdb
from backend.app.core_finance.bond_analytics.engine import (
    DURATION_QUALITY_MATURITY_UNAVAILABLE,
    DURATION_QUALITY_NO_REMAINING_TERM,
    DURATION_QUALITY_OBSERVED,
    DURATION_QUALITY_YTM_PAR_FALLBACK,
    RATE_INPUT_STATUS_DIRTY,
    RATE_INPUT_STATUS_MISSING,
    RATE_INPUT_STATUS_OBSERVED,
)
from backend.app.core_finance.risk_tensor import ASSUMPTION_BASED_DURATION_QUALITY_FLAGS
from backend.app.core_finance.risk_tensor_regulatory_scope import (
    DEFAULT_REGULATORY_DV01_SCOPE_RULES,
    row_in_regulatory_dv01_scope,
)
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.risk_tensor_repo import RiskTensorRepository
from backend.app.schemas.common_numeric import numeric_from_raw
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.risk_tensor_service import risk_tensor_envelope

RULE_VERSION = "rv_risk_tensor_scenario_stress_v2"
CACHE_VERSION = "cv_risk_tensor_scenario_stress_v2"
SUMMARY_COMPARISON_MEASURE = "estimated_pnl_impact"


def risk_scenario_stress_envelope(
    duckdb_path: str,
    governance_dir: str,
    report_date: str | date,
) -> dict[str, object]:
    report_date_text = _coerce_report_date(report_date).isoformat()
    tensor_envelope = risk_tensor_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date_text,
    )
    tensor_result_raw = tensor_envelope["result"]
    tensor_meta_raw = tensor_envelope["result_meta"]
    # build_formal_result_envelope always stores dict payloads under these keys.
    assert isinstance(tensor_result_raw, dict)
    assert isinstance(tensor_meta_raw, dict)
    tensor_result = dict(tensor_result_raw)
    tensor_meta = dict(tensor_meta_raw)
    scenarios = _scenario_rows(tensor_result)
    source_warnings = [str(item) for item in tensor_result.get("warnings") or []]
    evidence = _scenario_evidence(duckdb_path, report_date_text, tensor_result, tensor_meta)
    if evidence["fallback_status"] == "unknown":
        source_warnings.append("来源回退状态未核验，情景金额暂不可展示。")

    return build_result_envelope(
        basis="scenario",
        trace_id=_trace_id(),
        result_kind="risk.tensor.scenario_stress",
        cache_version=CACHE_VERSION,
        source_version=str(tensor_meta.get("source_version") or "sv_risk_tensor_scenario_stress"),
        rule_version=RULE_VERSION,
        quality_flag="warning",
        vendor_version=str(tensor_meta.get("vendor_version") or "vv_none"),
        # Values come from a validated ResultMeta dump; an out-of-set value would
        # still fail inside ResultMeta construction downstream (behavior preserved).
        vendor_status=str(tensor_meta.get("vendor_status") or "ok"),  # type: ignore[arg-type]
        fallback_mode=("latest_snapshot" if evidence["fallback_status"] == "fallback" else "none"),
        filters_applied={"report_date": report_date_text},
        tables_used=["fact_formal_risk_tensor_daily"],
        evidence_rows=1,
        source_surface="risk_tensor",
        requested_report_date=report_date_text,
        resolved_report_date=evidence["actual_risk_date"],
        as_of_date=evidence["actual_risk_date"],
        fallback_date=evidence["fallback_date"],
        date_basis="formal_snapshot_scenario_overlay",
        result_payload={
            "basis": "scenario",
            "report_date": report_date_text,
            "scenario_set_id": "standard_risk_tensor_scenario_v1",
            "rule_version": RULE_VERSION,
            "source": {
                "result_kind": str(tensor_meta.get("result_kind") or "risk.tensor"),
                "trace_id": tensor_meta.get("trace_id"),
                "source_version": tensor_meta.get("source_version"),
                "rule_version": tensor_meta.get("rule_version"),
                "cache_version": tensor_meta.get("cache_version"),
                "quality_flag": tensor_meta.get("quality_flag"),
            },
            "summary": _scenario_summary(
                scenarios,
                amount_display_allowed=evidence["amount_display_allowed"],
            ),
            "scenarios": scenarios,
            "warnings": [
                "Scenario stress is a review-only overlay on the materialized formal Risk Tensor; "
                "it is not a formal PnL, limit decision, or trading instruction."
            ],
            "source_warnings": source_warnings,
            "evidence": evidence,
        },
    )


def _scenario_evidence(
    duckdb_path: str,
    requested_date: str,
    tensor_result: dict[str, Any],
    tensor_meta: dict[str, Any],
) -> dict[str, Any]:
    """Validate the existing formal scope; never recompute the scenario amount."""
    payload_date = _evidence_date(tensor_result.get("report_date"))
    resolved_date = _evidence_date(tensor_meta.get("resolved_report_date"))
    as_of_date = _evidence_date(tensor_meta.get("as_of_date"))
    dates = {value for value in (payload_date, resolved_date, as_of_date) if value}
    date_status = "conflict" if len(dates) > 1 else "unknown"
    if payload_date and resolved_date and as_of_date and len(dates) == 1:
        date_status = "verified"
    actual_date = payload_date if date_status == "verified" else None
    fallback_date = _evidence_date(tensor_meta.get("fallback_date"))
    fallback_mode = tensor_meta.get("fallback_mode")
    fallback_status = "unknown"
    if fallback_mode == "latest_snapshot" or fallback_date or (actual_date and actual_date != requested_date):
        fallback_status = "fallback"
    elif fallback_mode == "none" and actual_date:
        fallback_status = "none"
    if fallback_status == "fallback" and fallback_date is None:
        fallback_date = actual_date
    coverage: dict[str, Any] = {
        "status": "unknown",
        "total_position_count": None,
        "included_position_count": None,
        "excluded_position_count": None,
        "missing_risk_position_count": None,
        "reasons": [],
    }
    reasons = coverage["reasons"]
    if actual_date:
        try:
            fact = RiskTensorRepository(duckdb_path).fetch_risk_tensor_row(actual_date)
            rows = BondAnalyticsRepository(duckdb_path).fetch_bond_analytics_rows(report_date=actual_date)
        except (OSError, duckdb.Error):
            fact, rows = None, []
            reasons.append("正式风险范围证据读取失败。")
        if fact is None or not rows:
            reasons.append("缺少可核对的正式风险事实或债券分析明细。")
        else:
            included = [row for row in rows if row_in_regulatory_dv01_scope(row)]
            input_problems = Counter(
                problem for row in included if (problem := _risk_input_evidence_problem(row))
            )
            missing = sum(count for (is_missing, _), count in input_problems.items() if is_missing)
            coverage.update(
                total_position_count=len(rows),
                included_position_count=len(included),
                excluded_position_count=len(rows) - len(included),
                missing_risk_position_count=missing,
            )
            reasons.extend(f"适用范围内有 {count} 项{problem}。" for (_, problem), count in input_problems.items())
            if len(rows) != tensor_result.get("bond_count") or len(rows) != fact.get("bond_count"):
                reasons.append("正式债券分析行数与风险张量范围不一致。")
            if _evidence_date(fact.get("report_date")) != actual_date or any(
                _evidence_date(row.get("report_date")) != actual_date for row in rows
            ):
                reasons.append("风险事实与明细日期不一致。")
            if not tensor_meta.get("source_version") or fact.get("source_version") != tensor_meta.get("source_version"):
                reasons.append("风险事实版本与返回结果不一致。")
            upstream_version = fact.get("upstream_source_version")
            # Bond facts retain input snapshot rule_version, whereas the tensor's
            # upstream_rule_version identifies the analytics materializer. The
            # formal tensor service already checks that materializer lineage.
            # Its source version is the sorted union of input source versions.
            row_versions = {str(row.get("source_version") or "").strip() for row in rows}
            if not upstream_version or "" in row_versions or "__".join(sorted(row_versions)) != upstream_version:
                reasons.append("正式债券明细版本与风险张量上游版本不一致。")
            coverage["status"] = "incomplete" if missing else "unknown" if reasons else "complete"
            par_fallback_count = sum(
                row.get("duration_quality_flag") == DURATION_QUALITY_YTM_PAR_FALLBACK
                and _risk_input_evidence_problem(row) is None
                for row in included
            )
            if par_fallback_count:
                reasons.append(
                    f"适用范围内有 {par_fallback_count} 项采用既有平价收益率假设（YTM=票息）；"
                    "该假设按现行正式口径保留，情景仍需人工复核。"
                )
    else:
        reasons.append("实际风险日期缺失或来源日期冲突。")
    regulatory_value = tensor_result.get("regulatory_dv01")
    has_risk_value = isinstance(regulatory_value, dict) and _finite_risk_input(regulatory_value.get("raw"))
    if not has_risk_value:
        reasons.append("监管口径 DV01 不可用。")
    return {
        "requested_report_date": requested_date,
        "actual_risk_date": actual_date,
        "date_status": date_status,
        "fallback_status": fallback_status,
        "fallback_date": fallback_date,
        "metric_id": "MTR-RSK-001R",
        "scope_label": "正式债券分析持仓，按监管 DV01 纳入规则；不代表全行所有资产",
        "scope_rule_ids": [rule.rule_id for rule in DEFAULT_REGULATORY_DV01_SCOPE_RULES],
        "coverage": coverage,
        "amount_display_allowed": bool(
            date_status == "verified" and fallback_status == "none"
            and coverage["status"] == "complete" and has_risk_value
        ),
        "human_review_required": True,
    }


def _evidence_date(value: object) -> str | None:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        return None


def _finite_risk_input(value: object) -> bool:
    try:
        return value is not None and Decimal(str(value)).is_finite()
    except (ValueError, TypeError, ArithmeticError):
        return False


def _risk_input_evidence_problem(row: dict[str, Any]) -> tuple[bool, str] | None:
    """Return whether risk is missing plus its evidence gap; preserve formal values."""
    if not _finite_risk_input(row.get("dv01")):
        return True, "缺少有限数值 DV01"
    quality = row.get("duration_quality_flag")
    if quality == DURATION_QUALITY_MATURITY_UNAVAILABLE:
        return True, "缺少到期日，DV01 零占位不能证明零风险"
    if quality == DURATION_QUALITY_YTM_PAR_FALLBACK:
        # calc_rules.md retains par fallback for missing/dirty/zero YTM. It is
        # an approved formal assumption, not missing risk; disclose it separately.
        if row.get("coupon_rate_input_status") == RATE_INPUT_STATUS_OBSERVED and row.get("ytm_input_status") in {
            RATE_INPUT_STATUS_OBSERVED, RATE_INPUT_STATUS_MISSING, RATE_INPUT_STATUS_DIRTY,
        }:
            return None
        return False, "平价收益率假设与票息或收益率输入状态不一致"
    if quality in ASSUMPTION_BASED_DURATION_QUALITY_FLAGS:
        # The formal engine retains and discloses these values. They are not
        # missing DV01; their applicability to this scenario remains unverified.
        return False, "DV01 使用近似或代理输入，其情景适用性待复核"
    if quality == DURATION_QUALITY_NO_REMAINING_TERM:
        # Matured positions have genuine zero rate sensitivity; coupon/yield
        # inputs are not needed for that persisted no-remaining-term result.
        return None if Decimal(str(row["dv01"])) == 0 else (False, "已到期标记与非零 DV01 冲突")
    if quality != DURATION_QUALITY_OBSERVED:
        return False, "DV01 输入质量未核验"
    if any(
        row.get(field) != RATE_INPUT_STATUS_OBSERVED
        for field in ("coupon_rate_input_status", "ytm_input_status")
    ):
        return False, "DV01 观测标记与票息或收益率输入状态不一致"
    return None


def _scenario_rows(tensor_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _rate_scenario(tensor_result),
        _credit_scenario(tensor_result),
        _liquidity_scenario(tensor_result),
        _fx_scenario(),
    ]


def _rate_scenario(tensor_result: dict[str, Any]) -> dict[str, Any]:
    shock_bp = Decimal("10")
    regulatory_dv01 = _numeric_raw(tensor_result.get("regulatory_dv01"))
    impact = None if regulatory_dv01 is None else -regulatory_dv01 * shock_bp
    return {
        "category": "rate",
        "scenario_key": "parallel_rate_up_10bp",
        "label": "利率平行上行 10bp",
        "source_field": "regulatory_dv01",
        "shock": numeric_from_raw(
            raw=float(shock_bp),
            unit="bp",
            precision=0,
            sign_aware=True,
        ).model_dump(mode="json"),
        "estimated_impact": numeric_from_raw(
            raw=_as_float(impact),
            unit="yuan",
            precision=2,
            sign_aware=True,
        ).model_dump(mode="json"),
        "measure": "estimated_pnl_impact",
        "calculation": "-regulatory_dv01 * shock_bp",
        "interpretation": "利率上行时，按已物化监管口径 DV01 估算组合价格影响。",
        "data_status": "available" if regulatory_dv01 is not None else "source_missing",
        "human_review_required": True,
    }


def _credit_scenario(tensor_result: dict[str, Any]) -> dict[str, Any]:
    shock_bp = Decimal("10")
    cs01 = _numeric_raw(tensor_result.get("cs01"))
    impact = None if cs01 is None else -cs01 * shock_bp
    return {
        "category": "credit",
        "scenario_key": "credit_spread_up_10bp",
        "label": "信用利差走阔 10bp",
        "source_field": "cs01",
        "shock": numeric_from_raw(raw=float(shock_bp), unit="bp", precision=0, sign_aware=True).model_dump(mode="json"),
        "estimated_impact": numeric_from_raw(
            raw=_as_float(impact),
            unit="yuan",
            precision=2,
            sign_aware=True,
        ).model_dump(mode="json"),
        "measure": "estimated_pnl_impact",
        "calculation": "-cs01 * shock_bp",
        "interpretation": "信用利差走阔时，按已物化 CS01 估算信用敏感度影响。",
        "data_status": "available" if cs01 is not None else "source_missing",
        "human_review_required": True,
    }


def _liquidity_scenario(tensor_result: dict[str, Any]) -> dict[str, Any]:
    shock_pct = Decimal("0.10")
    asset_cashflow = _numeric_raw(tensor_result.get("asset_cashflow_30d"))
    liability_cashflow = _numeric_raw(tensor_result.get("liability_cashflow_30d"))
    baseline_gap = _numeric_raw(tensor_result.get("liquidity_gap_30d"))
    total_market_value = _numeric_raw(tensor_result.get("total_market_value"))
    available = (
        asset_cashflow is not None
        and liability_cashflow is not None
        and baseline_gap is not None
    )
    if asset_cashflow is None or liability_cashflow is None:
        stressed_gap = None
    else:
        stressed_gap = (
            asset_cashflow * (Decimal("1") - shock_pct)
            - liability_cashflow * (Decimal("1") + shock_pct)
        )
    impact = stressed_gap - baseline_gap if stressed_gap is not None and baseline_gap is not None else None
    baseline_ratio = (
        baseline_gap / total_market_value
        if baseline_gap is not None
        and total_market_value is not None
        and total_market_value != 0
        else None
    )
    stressed_ratio = (
        stressed_gap / total_market_value
        if stressed_gap is not None
        and total_market_value is not None
        and total_market_value != 0
        else None
    )
    return {
        "category": "liquidity",
        "scenario_key": "liquidity_30d_cashflow_10pct",
        "label": "30 天现金流压力 10%",
        "source_field": "asset_cashflow_30d/liability_cashflow_30d/liquidity_gap_30d",
        # shock_pct / gap ratios are decimal ratios (0.10 == 10%); ratios can
        # legitimately exceed 1, so bypass the legacy "auto" rescale heuristic.
        "shock": numeric_from_raw(raw=float(shock_pct), unit="pct", precision=1, sign_aware=True, raw_scale="ratio").model_dump(mode="json"),
        "estimated_impact": numeric_from_raw(raw=_as_float(impact), unit="yuan", precision=2, sign_aware=True).model_dump(mode="json"),
        "measure": "stressed_30d_liquidity_gap_delta",
        "calculation": (
            "asset_cashflow_30d * (1 - shock_pct) - "
            "liability_cashflow_30d * (1 + shock_pct) - liquidity_gap_30d"
        ),
        "interpretation": "现金流压力下的 30 天流动性缺口变化；负值表示缓冲收窄。",
        "data_status": "available" if available else "source_missing",
        "human_review_required": True,
        "baseline_value": numeric_from_raw(raw=_as_float(baseline_gap), unit="yuan", precision=2, sign_aware=True).model_dump(mode="json"),
        "stressed_value": numeric_from_raw(raw=_as_float(stressed_gap), unit="yuan", precision=2, sign_aware=True).model_dump(mode="json"),
        "baseline_ratio": numeric_from_raw(raw=_as_float(baseline_ratio), unit="pct", precision=1, sign_aware=True, raw_scale="ratio").model_dump(mode="json"),
        "stressed_ratio": numeric_from_raw(raw=_as_float(stressed_ratio), unit="pct", precision=1, sign_aware=True, raw_scale="ratio").model_dump(mode="json"),
    }


def _fx_scenario() -> dict[str, Any]:
    return {
        "category": "fx",
        "scenario_key": "fx_parallel_move_review",
        "label": "汇率波动情景",
        "source_field": "fx_exposure",
        "shock": numeric_from_raw(raw=None, unit="pct", precision=1, sign_aware=True, raw_scale="ratio").model_dump(mode="json"),
        "estimated_impact": numeric_from_raw(raw=None, unit="yuan", precision=2, sign_aware=True).model_dump(mode="json"),
        "measure": "estimated_pnl_impact",
        "calculation": "fx_exposure * fx_shock",
        "interpretation": "当前风险张量未提供汇率敞口，接入 FX exposure 后方可估算。",
        "data_status": "source_missing",
        "human_review_required": True,
    }


def _scenario_summary(
    scenarios: list[dict[str, Any]],
    *,
    amount_display_allowed: bool = True,
) -> dict[str, Any]:
    available = [row for row in scenarios if row.get("data_status") == "available"]
    impacts = [
        (raw, str(row["scenario_key"]))
        for row in available
        if row.get("measure") == SUMMARY_COMPARISON_MEASURE
        if (raw := _numeric_raw(row.get("estimated_impact"))) is not None
    ]
    worst_impact, worst_key = (
        min(impacts, key=lambda item: item[0])
        if amount_display_allowed and impacts
        else (None, None)
    )
    return {
        "scenario_count": len(scenarios),
        "available_count": len(available),
        "review_required_count": sum(bool(row.get("human_review_required")) for row in scenarios),
        "comparison_measure": SUMMARY_COMPARISON_MEASURE,
        "worst_estimated_impact": numeric_from_raw(
            raw=_as_float(worst_impact),
            unit="yuan",
            precision=2,
            sign_aware=True,
        ).model_dump(mode="json"),
        "worst_scenario_key": worst_key,
        "message": (
            "利率与信用价格影响仅在同一估值损益口径内比较；"
            "流动性缺口变化单独披露，所有结果均需人工复核。"
            if amount_display_allowed
            else "来源证据未通过金额显示门禁，摘要金额已隐藏；所有结果均需人工复核。"
        ),
    }


def _as_float(value: Decimal | None) -> float | None:
    # numeric_from_raw immediately applies float(raw); converting at the call
    # boundary is bit-for-bit identical.
    return None if value is None else float(value)


def _numeric_raw(value: object) -> Decimal | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("raw")
    if raw is None:
        return None
    try:
        # 先经 float 保持与历史实现一致的解析接受域（上游 raw 本就是 JSON float），
        # 再以最短精确 repr 转 Decimal；后续冲击损益运算全程 Decimal，
        # 仅在 numeric_from_raw 输出边界回到 float。
        return Decimal(str(float(raw)))
    except (TypeError, ValueError, ArithmeticError):
        return None


def _coerce_report_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"
