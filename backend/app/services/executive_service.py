from __future__ import annotations

from datetime import date, datetime

from backend.app.core_finance.alert_engine import evaluate_alerts
from backend.app.core_finance.risk_tensor import compute_portfolio_risk_tensor
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.formal_zqtz_balance_metrics_repo import FormalZqtzBalanceMetricsRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.product_category_pnl_repo import ProductCategoryPnlRepository
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


def _fmt_yi_amount(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        v = 0.0
    else:
        v = float(value)
    yi = v / 1e8
    if signed:
        sign = "+" if yi >= 0 else ""
        return f"{sign}{yi:,.2f} 亿"
    return f"{yi:,.2f} 亿"


def _fmt_signed_segment_yi(yi: float) -> str:
    sign = "+" if yi >= 0 else ""
    return f"{sign}{yi:.2f} 亿"


def _tone_for_signed(yi: float) -> str:
    if yi > 0:
        return "positive"
    if yi < 0:
        return "negative"
    return "neutral"


_CATEGORY_ID_TO_ATTRIBUTION_SEGMENT: dict[str, str] = {
    "bond_tpl": "trading",
    "bond_ac": "carry",
    "bond_fvoci": "carry",
    "bond_ac_other": "credit",
    "bond_valuation_spread": "roll",
}


def _level1_monthly_rows(repo: ProductCategoryPnlRepository) -> tuple[str, list[dict[str, object]]] | None:
    dates = repo.list_report_dates()
    if not dates:
        return None
    report_date = dates[0]
    rows = repo.fetch_rows(report_date, "monthly")
    level1 = [
        r
        for r in rows
        if int(r.get("level") or -1) == 1 and not bool(r.get("is_total"))
    ]
    if not level1:
        return None
    return report_date, level1


def _aggregate_attribution_segments(rows: list[dict[str, object]]) -> dict[str, float]:
    totals = {"carry": 0.0, "roll": 0.0, "credit": 0.0, "trading": 0.0, "other": 0.0}
    for r in rows:
        cid = str(r.get("category_id") or "")
        raw = r.get("business_net_income")
        try:
            val = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            val = 0.0
        seg = _CATEGORY_ID_TO_ATTRIBUTION_SEGMENT.get(cid, "other")
        totals[seg] += val / 1e8
    return totals


def _build_pnl_attribution_from_repo(repo: ProductCategoryPnlRepository) -> PnlAttributionPayload | None:
    packed = _level1_monthly_rows(repo)
    if packed is None:
        return None
    _report_date, rows = packed
    seg = _aggregate_attribution_segments(rows)
    total_yi = sum(seg.values())
    order = [
        ("carry", "Carry", seg["carry"]),
        ("roll", "Roll-down", seg["roll"]),
        ("credit", "信用利差", seg["credit"]),
        ("trading", "交易损益", seg["trading"]),
        ("other", "其他", seg["other"]),
    ]
    segments = [
        AttributionSegment(
            id=key,
            label=label,
            amount=round(val, 4),
            display_amount=_fmt_signed_segment_yi(val),
            tone=_tone_for_signed(val),
        )
        for key, label, val in order
    ]
    return PnlAttributionPayload(
        title="收益归因",
        total=_fmt_yi_amount(total_yi * 1e8, signed=True),
        segments=segments,
    )


def _build_contribution_from_repo(repo: ProductCategoryPnlRepository) -> ContributionPayload | None:
    packed = _level1_monthly_rows(repo)
    if packed is None:
        return None
    report_date, rows = packed
    seg = _aggregate_attribution_segments(rows)
    rates_yi = seg["carry"] + seg["roll"]
    credit_yi = seg["credit"]
    trading_yi = seg["trading"]
    groups: list[tuple[str, str, float]] = [
        ("rates", "利率组", rates_yi),
        ("credit", "信用组", credit_yi),
        ("trading", "交易组", trading_yi),
    ]
    max_abs = max((abs(g[2]) for g in groups), default=0.0)

    def _completion(yi: float) -> int:
        if max_abs <= 0:
            return 0
        return int(min(100, max(0, round(abs(yi) / max_abs * 100))))

    def _status(yi: float) -> str:
        if max_abs <= 0:
            return "待观察"
        if abs(yi) >= max_abs * 0.95:
            return "核心拉动"
        if abs(yi) >= max_abs * 0.35:
            return "稳定贡献"
        return "波动偏大"

    contribution_rows = [
        ContributionRow(
            id=gid,
            name=gname,
            owner="按团队",
            contribution=_fmt_signed_segment_yi(val),
            completion=_completion(val),
            status=_status(val),
        )
        for gid, gname, val in groups
    ]
    return ContributionPayload(
        title="团队 / 账户 / 策略贡献",
        rows=contribution_rows,
    )


def executive_overview() -> dict[str, object]:
    settings = get_settings()
    aum_raw: float | None = None
    ytd_raw: float | None = None

    try:
        row = FormalZqtzBalanceMetricsRepository(
            str(settings.duckdb_path)
        ).fetch_latest_zqtz_asset_market_value(currency_basis="CNY")
        if row is not None:
            aum_raw = float(row["total_market_value_amount"])
    except (RuntimeError, OSError, TypeError, ValueError):
        aum_raw = None

    try:
        ytd_raw = float(
            PnlRepository(str(settings.duckdb_path)).sum_formal_total_pnl_for_year(
                date.today().year
            )
        )
    except (RuntimeError, OSError, TypeError, ValueError):
        ytd_raw = None

    aum_value = (
        _fmt_yi_amount(aum_raw, signed=False)
        if aum_raw is not None
        else "1,023.47 亿"
    )
    aum_detail = (
        "来自 fact_formal_zqtz_balance_daily 最新日期的 CNY 资产口径市值合计。"
        if aum_raw is not None
        else "较上月保持温和扩张，当前仅提供受控展示值。"
    )
    ytd_value = (
        _fmt_yi_amount(ytd_raw, signed=True)
        if ytd_raw is not None
        else "+12.63 亿"
    )
    ytd_detail = (
        f"来自 fact_formal_pnl_fi 当年（{date.today().year}）total_pnl 合计。"
        if ytd_raw is not None
        else "收益口径后续由正式服务替换，当前为受控演示值。"
    )

    payload = OverviewPayload(
        title="经营总览",
        metrics=[
            ExecutiveMetric(
                id="aum",
                label="资产规模",
                value=aum_value,
                delta="+2.35%",
                tone="positive",
                detail=aum_detail,
            ),
            ExecutiveMetric(
                id="yield",
                label="年内收益",
                value=ytd_value,
                delta="+8.72%",
                tone="positive",
                detail=ytd_detail,
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
    settings = get_settings()
    try:
        repo = ProductCategoryPnlRepository(str(settings.duckdb_path))
        built = _build_pnl_attribution_from_repo(repo)
        if built is not None:
            return _envelope("executive.pnl-attribution", built)
    except (RuntimeError, OSError, TypeError, ValueError, KeyError):
        pass

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
    settings = get_settings()
    try:
        snapshot = BondAnalyticsRepository(
            str(settings.duckdb_path)
        ).fetch_latest_risk_overview_snapshot()
        if snapshot is not None and snapshot["report_date"] is not None:
            wdur = snapshot["portfolio_modified_duration"]
            sum_dv01 = snapshot["portfolio_dv01"]
            cred_pct = snapshot["credit_market_value_ratio_pct"]
            w_ytm = snapshot["weighted_years_to_maturity"]
            if wdur is not None and sum_dv01 is not None:
                wdur_f = float(wdur)
                dv01_f = float(sum_dv01)
                cred_f = float(cred_pct) if cred_pct is not None else 0.0
                ytm_f = float(w_ytm) if w_ytm is not None else 0.0
                asof_date = str(snapshot["report_date"])
                payload = RiskOverviewPayload(
                    title="风险全景",
                    signals=[
                        RiskSignal(
                            id="duration",
                            label="久期风险",
                            value=f"{wdur_f:.2f} 年",
                            status="stable",
                            detail=f"最新日期 {asof_date}，组合市值加权修正久期（modified_duration）。",
                        ),
                        RiskSignal(
                            id="leverage",
                            label="杠杆风险",
                            value=f"{dv01_f:,.0f}",
                            status="watch",
                            detail=f"最新日期 {asof_date}，DV01 合计（元口径聚合）。",
                        ),
                        RiskSignal(
                            id="credit",
                            label="信用集中度",
                            value=f"{cred_f:.1f}%",
                            status="warning",
                            detail=f"最新日期 {asof_date}，信用类债券市值占组合市值比重。",
                        ),
                        RiskSignal(
                            id="liquidity",
                            label="流动性风险",
                            value=f"{ytm_f:.2f} 年",
                            status="stable",
                            detail=f"最新日期 {asof_date}，市值加权平均剩余期限（years_to_maturity）。",
                        ),
                    ],
                )
                return _envelope("executive.risk-overview", payload)
    except (RuntimeError, OSError, TypeError, ValueError):
        pass

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
    settings = get_settings()
    try:
        repo = ProductCategoryPnlRepository(str(settings.duckdb_path))
        built = _build_contribution_from_repo(repo)
        if built is not None:
            return _envelope("executive.contribution", built)
    except (RuntimeError, OSError, TypeError, ValueError, KeyError):
        pass

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


def _fallback_executive_alerts() -> dict[str, object]:
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


def executive_alerts() -> dict[str, object]:
    settings = get_settings()
    try:
        repo = BondAnalyticsRepository(str(settings.duckdb_path))
        dates = repo.list_report_dates()
        if not dates:
            return _fallback_executive_alerts()
        report_date = date.fromisoformat(dates[0])
        rows = repo.fetch_bond_analytics_rows(report_date=report_date.isoformat())
        tensor = compute_portfolio_risk_tensor(rows, report_date=report_date)
        raw = evaluate_alerts(tensor)
        occurred_at = datetime.now().strftime("%H:%M")
        items = [
            AlertItem(
                id=entry["rule_id"],
                severity=entry["severity"],
                title=entry["title"],
                occurred_at=occurred_at,
                detail=entry["detail"],
            )
            for entry in raw
        ]
        payload = AlertsPayload(title="预警与事件", items=items)
        return _envelope("executive.alerts", payload)
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError, KeyError):
        return _fallback_executive_alerts()
