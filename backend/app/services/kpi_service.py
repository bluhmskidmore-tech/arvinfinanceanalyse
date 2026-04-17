from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.repositories.kpi_repo import KpiRepository
from backend.app.schemas.kpi import KpiOwnerListPayload, KpiOwnerPayload, KpiPeriodMetricSummaryPayload, KpiPeriodSummaryPayload


def kpi_owners_payload(
    *,
    dsn: str,
    year: int | None = None,
    is_active: bool | None = None,
) -> dict[str, object]:
    repo = KpiRepository(dsn)
    owners = repo.list_owners(year=year, is_active=is_active)
    return KpiOwnerListPayload(
        owners=[KpiOwnerPayload.model_validate(item) for item in owners],
        total=len(owners),
    ).model_dump(mode="json")


def kpi_period_summary_payload(
    *,
    dsn: str,
    owner_id: int,
    year: int,
    period_type: str,
    period_value: int | None = None,
) -> dict[str, object]:
    repo = KpiRepository(dsn)
    payload = repo.fetch_period_summary(
        owner_id=owner_id,
        year=year,
        period_type=period_type,
        period_value=period_value,
    )
    return KpiPeriodSummaryPayload(
        owner_id=payload["owner_id"],
        owner_name=payload["owner_name"],
        year=payload["year"],
        period_type=payload["period_type"],
        period_value=payload["period_value"],
        period_label=payload["period_label"],
        period_start_date=payload["period_start_date"],
        period_end_date=payload["period_end_date"],
        metrics=[
            KpiPeriodMetricSummaryPayload.model_validate(item)
            for item in payload["metrics"]
        ],
        total=payload["total"],
        total_weight=payload["total_weight"],
        total_score=payload["total_score"],
    ).model_dump(mode="json")


def resolve_executive_kpi_metrics(
    *,
    dsn: str,
    report_date: str | None,
) -> list[dict[str, object]]:
    if not str(dsn or "").strip():
        return []
    try:
        repo = KpiRepository(dsn)
        target_year = date.fromisoformat(report_date).year if report_date else None
        if target_year is not None:
            owners = repo.list_owners(year=target_year, is_active=True)
            if not owners:
                return []
            selected_year = target_year
        else:
            owners = repo.list_owners(is_active=True)
            if not owners:
                return []
            selected_year = max(int(owner["year"]) for owner in owners)
            owners = [
                owner
                for owner in owners
                if int(owner["year"]) == selected_year
            ]
    except Exception:
        return []
    total_weight = Decimal("0")
    total_score = Decimal("0")
    owner_count = len(owners)
    summaries: list[dict[str, object]] = []
    try:
        for owner in owners:
            summary = repo.fetch_period_summary(
                owner_id=int(owner["owner_id"]),
                year=int(owner["year"]),
                period_type="YEAR",
            )
            summaries.append(summary)
            total_weight += Decimal(str(summary["total_weight"] or "0"))
            total_score += Decimal(str(summary["total_score"] or "0"))
    except Exception:
        return []
    goal_completion = None
    if total_weight > 0:
        goal_completion = (total_score / total_weight) * Decimal("100")

    risk_weight = Decimal("0")
    risk_progress = Decimal("0")
    for summary in summaries:
        for metric in summary["metrics"]:
            haystacks = [
                str(metric.get("metric_code") or ""),
                str(metric.get("metric_name") or ""),
                str(metric.get("major_category") or ""),
                str(metric.get("indicator_category") or ""),
            ]
            normalized = " ".join(haystacks).lower()
            if not any(token in normalized for token in ("risk", "风险", "budget", "预算")):
                continue
            weight = Decimal(str(metric.get("score_weight") or "0"))
            value = metric.get("period_progress_pct") or metric.get("period_completion_ratio")
            if weight <= 0 or value in (None, ""):
                continue
            risk_weight += weight
            risk_progress += weight * Decimal(str(value))

    risk_budget_usage = None
    if risk_weight > 0:
        risk_budget_usage = risk_progress / risk_weight

    result: list[dict[str, object]] = []
    if goal_completion is not None:
        result.append(
            {
                "id": "goal",
                "label": "目标完成率",
                "value": f"{float(goal_completion):.2f}%",
                "delta": "governed",
                "tone": "positive" if goal_completion >= 0 else "negative",
                "detail": (
                    f"来自 KPI 年度汇总读面：{selected_year} 年 {owner_count} 个 active owners 的 "
                    "total_score / total_weight 加权汇总。"
                ),
            }
        )
    if risk_budget_usage is not None:
        result.append(
            {
                "id": "risk-budget",
                "label": "风险预算使用率",
                "value": f"{float(risk_budget_usage):.2f}%",
                "delta": "governed",
                "tone": "warning",
                "detail": (
                    f"来自 KPI 年度汇总读面：{selected_year} 年 {owner_count} 个 active owners 的 "
                    "风险类指标加权进度。"
                ),
            }
        )
    return result
