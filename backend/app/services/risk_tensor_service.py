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
from backend.app.schemas.common_numeric import Numeric, NumericUnit, null_numeric, numeric_from_raw
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
    repo = RiskTensorRepository(str(duckdb_path))
    row = repo.fetch_risk_tensor_row(report_date_text)

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

    prior_row = _fetch_previous_comparable_risk_tensor_row(
        repo=repo,
        duckdb_path=str(duckdb_path),
        governance_dir=governance_dir,
        report_date_text=report_date_text,
    )
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
                "prior_period_change": _build_prior_period_change(row, prior_row),
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
        requested_report_date=report_date_text,
        resolved_report_date=report_date_text,
        as_of_date=report_date_text,
        date_basis="formal_snapshot",
        fallback_date=None,
        result_payload=payload.model_dump(mode="json"),
    )


def _fetch_previous_comparable_risk_tensor_row(
    *,
    repo: RiskTensorRepository,
    duckdb_path: str,
    governance_dir: str,
    report_date_text: str,
) -> dict[str, object] | None:
    candidate_rows = repo.list_report_date_lineage_rows()
    try:
        bond_lineage_by_report_date = load_latest_bond_analytics_lineage_by_report_date(
            governance_dir=governance_dir,
        )
    except TimeoutError:
        return None
    tyw_liability_lineage_by_report_date = load_current_tyw_liability_lineage_by_report_date(
        duckdb_path=duckdb_path,
    )
    for candidate in candidate_rows:
        candidate_report_date = str(candidate["report_date"])
        if candidate_report_date >= report_date_text:
            continue
        tyw_liability_lineage = tyw_liability_lineage_by_report_date.get(candidate_report_date, {})
        stale_reason = _risk_tensor_freshness_error_from_values(
            report_date_text=candidate_report_date,
            row=candidate,
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
            continue
        return repo.fetch_risk_tensor_row(candidate_report_date)
    return None


def _build_prior_period_change(
    row: dict[str, object],
    prior_row: dict[str, object] | None,
) -> dict[str, object]:
    dominant_bucket, _ = _dominant_krd_bucket(row)
    if prior_row is None:
        return {
            "status": "no_prior",
            "comparison_report_date": None,
            "summary": "暂无可比较的上一报告日；当前仅展示截面风险。",
            "dominant_krd_bucket": dominant_bucket,
            "previous_dominant_krd_bucket": None,
            "dominant_krd_shifted": False,
            "metrics": [],
        }

    previous_bucket, _ = _dominant_krd_bucket(prior_row)
    metrics = [
        _build_prior_change_metric(
            row=row,
            prior_row=prior_row,
            key="regulatory_dv01",
            label="监管口径 DV01",
            unit="dv01",
            precision=2,
            improvement_direction="down",
            up_interpretation="监管口径 DV01 扩大",
            down_interpretation="监管口径 DV01 收敛",
            flat_interpretation="监管口径 DV01 基本持平",
        ),
        _build_prior_change_metric(
            row=row,
            prior_row=prior_row,
            key="portfolio_modified_duration",
            label="修正久期",
            unit="ratio",
            precision=2,
            improvement_direction="down",
            up_interpretation="组合久期拉长",
            down_interpretation="组合久期缩短",
            flat_interpretation="组合久期基本持平",
        ),
        _build_prior_change_metric(
            row=row,
            prior_row=prior_row,
            key="cs01",
            label="CS01",
            unit="dv01",
            precision=2,
            improvement_direction="down",
            up_interpretation="信用利差敏感度扩大",
            down_interpretation="信用利差敏感度收敛",
            flat_interpretation="信用利差敏感度基本持平",
        ),
        _build_prior_change_metric(
            row=row,
            prior_row=prior_row,
            key="liquidity_gap_30d_ratio",
            label="30 日流动性缺口比例",
            unit="ratio",
            precision=4,
            improvement_direction="up",
            up_interpretation="30 日流动性缓冲改善",
            down_interpretation="30 日流动性缓冲收窄",
            flat_interpretation="30 日流动性缓冲基本持平",
        ),
    ]
    metric_by_key = {metric["key"]: metric for metric in metrics}
    regulatory_delta = _delta_phrase(metric_by_key["regulatory_dv01"])
    duration_delta = _delta_phrase(metric_by_key["portfolio_modified_duration"])
    bucket_phrase = (
        f"主风险桶由 {previous_bucket} 切至 {dominant_bucket}"
        if previous_bucket != dominant_bucket
        else f"主风险桶仍为 {dominant_bucket}"
    )
    return {
        "status": "available",
        "comparison_report_date": str(prior_row["report_date"]),
        "summary": (
            f"较上一报告日 {prior_row['report_date']}：监管口径 DV01 {regulatory_delta}；"
            f"修正久期 {duration_delta}；{bucket_phrase}。"
        ),
        "dominant_krd_bucket": dominant_bucket,
        "previous_dominant_krd_bucket": previous_bucket,
        "dominant_krd_shifted": previous_bucket != dominant_bucket,
        "metrics": metrics,
    }


def _build_prior_change_metric(
    *,
    row: dict[str, object],
    prior_row: dict[str, object],
    key: str,
    label: str,
    unit: NumericUnit,
    precision: int,
    improvement_direction: str,
    up_interpretation: str,
    down_interpretation: str,
    flat_interpretation: str,
) -> dict[str, object]:
    current = _float_or_none(row.get(key))
    previous = _float_or_none(prior_row.get(key))
    delta = None if current is None or previous is None else current - previous
    direction = _delta_direction(delta)
    current_numeric = numeric_from_raw(
        raw=current,
        unit=unit,
        precision=precision,
        sign_aware=False,
    ).model_dump(mode="json")
    previous_numeric = numeric_from_raw(
        raw=previous,
        unit=unit,
        precision=precision,
        sign_aware=False,
    ).model_dump(mode="json")
    delta_numeric = numeric_from_raw(
        raw=delta,
        unit=unit,
        precision=precision,
        sign_aware=True,
    ).model_dump(mode="json")
    if direction == "up":
        interpretation = up_interpretation
    elif direction == "down":
        interpretation = down_interpretation
    elif direction == "flat":
        interpretation = flat_interpretation
    else:
        interpretation = f"{label} 缺少可比数据"
    return {
        "key": key,
        "label": label,
        "current": current_numeric,
        "previous": previous_numeric,
        "delta": delta_numeric,
        "current_display": _prior_change_display(key=key, numeric=current_numeric, is_delta=False),
        "previous_display": _prior_change_display(key=key, numeric=previous_numeric, is_delta=False),
        "delta_display": _prior_change_display(key=key, numeric=delta_numeric, is_delta=True),
        "direction": direction,
        "tone": _prior_change_tone(direction, improvement_direction),
        "interpretation": interpretation,
    }


def _prior_change_display(
    *,
    key: str,
    numeric: dict[str, object],
    is_delta: bool,
) -> str:
    raw = _float_or_none(numeric.get("raw"))
    if raw is None:
        return _numeric_display(numeric)
    precision = int(numeric.get("precision") or 2)
    if key == "portfolio_modified_duration":
        return _format_signed_decimal(raw, precision=precision, sign_aware=is_delta)
    if key.endswith("_ratio"):
        return _format_ratio_percent(raw, sign_aware=is_delta)
    if is_delta:
        return _format_signed_decimal(raw, precision=precision, sign_aware=True)
    return _numeric_display(numeric)


def _format_signed_decimal(raw: float, *, precision: int, sign_aware: bool) -> str:
    sign = "+" if sign_aware and raw > 0 else ""
    return f"{sign}{raw:,.{precision}f}"


def _format_ratio_percent(raw: float, *, sign_aware: bool) -> str:
    if abs(raw) < 0.0005:
        return "0.0%"
    sign = "+" if sign_aware and raw > 0 else ""
    if abs(raw) <= 1:
        return f"{sign}{raw * 100:.1f}%"
    return f"{sign}{raw:.1f}%"


def _delta_direction(delta: float | None) -> str:
    if delta is None:
        return "unavailable"
    if abs(delta) < 1e-12:
        return "flat"
    return "up" if delta > 0 else "down"


def _prior_change_tone(direction: str, improvement_direction: str) -> str:
    if direction in {"flat", "unavailable"}:
        return "neutral"
    return "good" if direction == improvement_direction else "warning"


def _delta_phrase(metric: dict[str, object]) -> str:
    direction = str(metric["direction"])
    delta = metric["delta"]
    delta_display = _unsigned_numeric_display(delta)
    if direction == "up":
        return f"增加 {delta_display}"
    if direction == "down":
        return f"下降 {delta_display}"
    if direction == "flat":
        return "基本持平"
    return "缺少可比数据"


def _unsigned_numeric_display(value: dict[str, object] | Numeric) -> str:
    display = _numeric_display(value)
    if display.startswith(("+", "-")):
        return display[1:]
    return display


def _build_dv01_controls(row: dict[str, object]) -> dict[str, object]:
    regulatory_dv01 = _float_or_none(row.get("regulatory_dv01"))
    regulatory_dv01_numeric = numeric_from_raw(
        raw=regulatory_dv01,
        unit="dv01",
        precision=2,
        sign_aware=False,
    ).model_dump(mode="json")
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
    operating_judgement = _build_dv01_operating_judgement(
        regulatory_dv01=regulatory_dv01_numeric,
        dominant_bucket=dominant_bucket,
        ten_bp_impact=stress_scenarios[0]["estimated_pnl_impact"],
    )
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
        "operating_judgement": operating_judgement,
        "control_actions": _build_dv01_control_actions(
            dominant_bucket=dominant_bucket,
            ten_bp_impact=stress_scenarios[0]["estimated_pnl_impact"],
            twenty_five_bp_impact=stress_scenarios[1]["estimated_pnl_impact"],
        ),
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


def _build_dv01_operating_judgement(
    *,
    regulatory_dv01: dict[str, object],
    dominant_bucket: str,
    ten_bp_impact: dict[str, object],
) -> str:
    dv01_display = _numeric_display(regulatory_dv01)
    ten_bp_display = _numeric_display(ten_bp_impact)
    return (
        f"当前监管口径 DV01 {dv01_display}；+10bp 平行上行估算影响 {ten_bp_display}；"
        f"主风险桶 {dominant_bucket}。审批限额与利率波动源未接入前，暂不判定超限。"
    )


def _build_dv01_control_actions(
    *,
    dominant_bucket: str,
    ten_bp_impact: dict[str, object],
    twenty_five_bp_impact: dict[str, object],
) -> list[dict[str, str]]:
    return [
        {
            "key": "approved_dv01_limit",
            "title": "配置审批限额",
            "status": "required",
            "evidence": "审批 DV01 限额未接入。",
            "action": "接入投委会或风控审批后的总 DV01 限额，再计算使用率与预警带。",
        },
        {
            "key": "rate_volatility_input",
            "title": "接入利率波动",
            "status": "required",
            "evidence": "日度利率波动率未接入。",
            "action": "接入曲线波动率后，把 DV01 敞口转换成日度波动损益观察。",
        },
        {
            "key": "bucket_sub_limits",
            "title": "拆分期限桶限额",
            "status": "required",
            "evidence": f"当前主风险桶为 {dominant_bucket}。",
            "action": "为 1Y/3Y/5Y/7Y/10Y/30Y 设置桶位限额，避免总 DV01 合规但期限错配。",
        },
        {
            "key": "stress_escalation",
            "title": "固化冲击升级",
            "status": "required",
            "evidence": (
                f"+10bp 估算影响 {_numeric_display(ten_bp_impact)}；"
                f"+25bp 估算影响 {_numeric_display(twenty_five_bp_impact)}。"
            ),
            "action": "将标准冲击纳入日例会；超过授权阈值时进入减久期、套保或审批升级流程。",
        },
    ]


def _numeric_display(value: dict[str, object] | Numeric) -> str:
    if isinstance(value, Numeric):
        return value.display
    display = value.get("display")
    return str(display) if display not in (None, "") else "—"


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
