from __future__ import annotations

from backend.app.schemas.executive_dashboard import (
    AlertsPayload,
    AlertItem,
    AttributionSegment,
    ContributionPayload,
    ContributionRow,
    ExecutiveMetric,
    OverviewPayload,
    PnlAttributionPayload,
    RiskOverviewPayload,
    RiskSignal,
    SummaryPayload,
    SummaryPoint,
)
from backend.app.schemas.result_meta import ResultMeta


def _envelope(result_kind: str, result: object) -> dict[str, object]:
    meta = ResultMeta(
        trace_id=f"tr_{result_kind.replace('.', '_')}",
        basis="analytical",
        result_kind=result_kind,
        formal_use_allowed=False,
        source_version="sv_exec_dashboard_v1",
        vendor_version="vv_none",
        rule_version="rv_exec_dashboard_v1",
        cache_version="cv_exec_dashboard_v1",
        quality_flag="ok",
        scenario_flag=False,
    )
    return {
        "result_meta": meta.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
    }


def executive_overview() -> dict[str, object]:
    payload = OverviewPayload(
        title="经营总览",
        metrics=[
            ExecutiveMetric(
                id="aum",
                label="资产规模",
                value="1,023.47 亿",
                delta="+2.35%",
                tone="positive",
                detail="较上月保持温和扩张，当前仅提供受控展示值。",
            ),
            ExecutiveMetric(
                id="yield",
                label="年内收益",
                value="+12.63 亿",
                delta="+8.72%",
                tone="positive",
                detail="收益口径后续由正式服务替换，当前为受控演示值。",
            ),
            ExecutiveMetric(
                id="goal",
                label="目标完成率",
                value="63.1%",
                delta="目标 20.00 亿",
                tone="neutral",
                detail="用于壳层阶段的完成进度展示。",
            ),
            ExecutiveMetric(
                id="risk-budget",
                label="风险预算使用率",
                value="68.7%",
                delta="+3.6pp",
                tone="warning",
                detail="保持对风险预算接近上限的提示能力。",
            ),
        ],
    )
    return _envelope("executive.overview", payload)


def executive_summary() -> dict[str, object]:
    payload = SummaryPayload(
        title="本周管理摘要",
        narrative=(
            "本周组合收益延续修复，收益主要来自久期与票息贡献。"
            "风险端仍需关注信用集中度与流动性预留，当前页面仅展示受控摘要，不生成正式分析口径。"
        ),
        points=[
            SummaryPoint(
                id="income",
                label="收益",
                tone="positive",
                text="利率下行仍是收益主驱动，票息表现稳定。",
            ),
            SummaryPoint(
                id="risk",
                label="风险",
                tone="warning",
                text="信用集中度上行，需持续关注暴露边界。",
            ),
            SummaryPoint(
                id="action",
                label="建议",
                tone="neutral",
                text="保持流动性缓冲，避免在高波动窗口放大仓位。",
            ),
        ],
    )
    return _envelope("executive.summary", payload)


def executive_pnl_attribution() -> dict[str, object]:
    payload = PnlAttributionPayload(
        title="收益归因",
        total="12.63 亿",
        segments=[
            AttributionSegment(
                id="carry",
                label="Carry",
                amount=5.21,
                display_amount="+5.21 亿",
                tone="positive",
            ),
            AttributionSegment(
                id="roll",
                label="Roll-down",
                amount=2.18,
                display_amount="+2.18 亿",
                tone="positive",
            ),
            AttributionSegment(
                id="credit",
                label="信用利差",
                amount=1.42,
                display_amount="+1.42 亿",
                tone="positive",
            ),
            AttributionSegment(
                id="trading",
                label="交易损益",
                amount=-0.85,
                display_amount="-0.85 亿",
                tone="negative",
            ),
            AttributionSegment(
                id="other",
                label="其他",
                amount=0.67,
                display_amount="+0.67 亿",
                tone="neutral",
            ),
        ],
    )
    return _envelope("executive.pnl-attribution", payload)


def executive_risk_overview() -> dict[str, object]:
    payload = RiskOverviewPayload(
        title="风险全景",
        signals=[
            RiskSignal(
                id="duration",
                label="久期风险",
                value="32.1%",
                status="stable",
                detail="久期暴露仍处于本周可接受区间。",
            ),
            RiskSignal(
                id="leverage",
                label="杠杆风险",
                value="54.3%",
                status="watch",
                detail="杠杆使用率上行，需结合资金窗口观察。",
            ),
            RiskSignal(
                id="credit",
                label="信用集中度",
                value="78.9%",
                status="warning",
                detail="集中度已逼近预警阈值。",
            ),
            RiskSignal(
                id="liquidity",
                label="流动性风险",
                value="41.2%",
                status="stable",
                detail="流动性缓冲仍具备调节空间。",
            ),
        ],
    )
    return _envelope("executive.risk-overview", payload)


def executive_contribution() -> dict[str, object]:
    payload = ContributionPayload(
        title="团队 / 账户 / 策略贡献",
        rows=[
            ContributionRow(
                id="rates",
                name="利率组",
                owner="按团队",
                contribution="+4.21 亿",
                completion=65,
                status="核心拉动",
            ),
            ContributionRow(
                id="credit",
                name="信用组",
                owner="按团队",
                contribution="+2.18 亿",
                completion=58,
                status="稳定贡献",
            ),
            ContributionRow(
                id="trading",
                name="交易组",
                owner="按团队",
                contribution="+0.32 亿",
                completion=31,
                status="波动偏大",
            ),
        ],
    )
    return _envelope("executive.contribution", payload)


def executive_alerts() -> dict[str, object]:
    payload = AlertsPayload(
        title="预警与事件",
        items=[
            AlertItem(
                id="a1",
                severity="high",
                title="久期敞口接近上限",
                occurred_at="10:15",
                detail="账户 B 久期 6.82，接近上限 7.00。",
            ),
            AlertItem(
                id="a2",
                severity="medium",
                title="信用集中度预警",
                occurred_at="09:48",
                detail="城投敞口 23.5%，接近阈值 25%。",
            ),
            AlertItem(
                id="a3",
                severity="medium",
                title="杠杆使用率上升",
                occurred_at="09:30",
                detail="当前 1.82x，较上周上升 0.06x。",
            ),
        ],
    )
    return _envelope("executive.alerts", payload)
