from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from backend.app.core_finance.alert_engine import evaluate_alerts
from backend.app.core_finance.liability_analytics_compat import compute_liability_yield_metrics
from backend.app.core_finance.risk_tensor import compute_portfolio_risk_tensor
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.formal_zqtz_balance_metrics_repo import FormalZqtzBalanceMetricsRepository
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository
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
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.kpi_service import resolve_executive_kpi_metrics


def _normalize_report_date(report_date: str | None) -> str | None:
    if report_date is None:
        return None
    return date.fromisoformat(str(report_date).strip()).isoformat()


def _envelope(
    result_kind: str,
    result: object,
    *,
    quality_flag: Literal["ok", "warning", "error", "stale"] = "ok",
    vendor_status: Literal["ok", "vendor_stale", "vendor_unavailable"] = "ok",
    fallback_mode: Literal["none", "latest_snapshot"] = "none",
    source_version: str = "sv_exec_dashboard_v1",
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_{result_kind.replace('.', '_')}",
        result_kind=result_kind,
        cache_version="cv_exec_dashboard_v1",
        source_version=source_version,
        rule_version="rv_exec_dashboard_v1",
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        result_payload=result.model_dump(mode="json"),
    )


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


def _fmt_signed_percent(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if float(value) >= 0 else ""
    return f"{sign}{float(value):.2f}%"


def _previous_report_date(dates: list[str], current_report_date: str | None) -> str | None:
    if not current_report_date or not dates:
        return None
    if current_report_date in dates:
        idx = dates.index(current_report_date)
        if idx + 1 < len(dates):
            return dates[idx + 1]
    return None


def _format_percent_change(current: float | None, previous: float | None) -> str:
    if current is None or previous in (None, 0):
        return "无环比"
    change = ((float(current) - float(previous)) / float(previous)) * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.2f}%"


def _format_point_change(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return "无环比"
    change = float(current) - float(previous)
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.2f}pp"


def _unavailable_metric(
    *,
    metric_id: str,
    label: str,
    detail: str,
    delta: str = "未接入",
    tone: Literal["positive", "neutral", "warning", "negative"] = "warning",
) -> ExecutiveMetric:
    return ExecutiveMetric(
        id=metric_id,
        label=label,
        value="—",
        delta=delta,
        tone=tone,
        detail=detail,
    )


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


def _level1_monthly_rows(
    repo: ProductCategoryPnlRepository,
    report_date: str | None = None,
) -> tuple[str, list[dict[str, object]]] | None:
    dates = repo.list_report_dates()
    target_report_date = _normalize_report_date(report_date)
    if target_report_date is None:
        if not dates:
            return None
        target_report_date = dates[0]
    elif dates and target_report_date not in dates:
        return None
    rows = repo.fetch_rows(target_report_date, "monthly")
    level1 = [
        r
        for r in rows
        if int(r.get("level") or -1) == 1 and not bool(r.get("is_total"))
    ]
    if not level1:
        return None
    return target_report_date, level1


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


def _build_pnl_attribution_from_repo(
    repo: ProductCategoryPnlRepository,
    report_date: str | None = None,
) -> PnlAttributionPayload | None:
    packed = _level1_monthly_rows(repo, report_date)
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


def _pnl_attribution_explicit_miss_payload(report_date: str) -> PnlAttributionPayload:
    zero = [
        ("carry", "Carry", 0.0),
        ("roll", "Roll-down", 0.0),
        ("credit", "信用利差", 0.0),
        ("trading", "交易损益", 0.0),
        ("other", "其他", 0.0),
    ]
    segments = [
        AttributionSegment(
            id=key,
            label=label,
            amount=0.0,
            display_amount=_fmt_signed_segment_yi(val),
            tone=_tone_for_signed(val),
        )
        for key, label, val in zero
    ]
    return PnlAttributionPayload(
        title=f"收益归因（{report_date} 无受控产品分类月度数据）",
        total="0 亿",
        segments=segments,
    )


def _pnl_attribution_unavailable_payload() -> PnlAttributionPayload:
    zero = [
        ("carry", "Carry", 0.0),
        ("roll", "Roll-down", 0.0),
        ("credit", "信用利差", 0.0),
        ("trading", "交易损益", 0.0),
        ("other", "其他", 0.0),
    ]
    segments = [
        AttributionSegment(
            id=key,
            label=label,
            amount=0.0,
            display_amount=_fmt_signed_segment_yi(val),
            tone=_tone_for_signed(val),
        )
        for key, label, val in zero
    ]
    return PnlAttributionPayload(
        title="收益归因（当前无受控产品分类月度数据）",
        total="0 亿",
        segments=segments,
    )


def _contribution_explicit_miss_payload(report_date: str) -> ContributionPayload:
    return ContributionPayload(
        title="团队 / 账户 / 策略贡献",
        rows=[],
    )


def _contribution_unavailable_payload() -> ContributionPayload:
    return ContributionPayload(
        title="团队 / 账户 / 策略贡献",
        rows=[],
    )


def _empty_risk_overview_payload() -> RiskOverviewPayload:
    return RiskOverviewPayload(
        title="风险全景",
        signals=[],
    )


def _empty_alerts_payload() -> AlertsPayload:
    return AlertsPayload(
        title="预警与事件",
        items=[],
    )


def _build_contribution_from_repo(
    repo: ProductCategoryPnlRepository,
    report_date: str | None = None,
) -> ContributionPayload | None:
    packed = _level1_monthly_rows(repo, report_date)
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


def executive_overview(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    normalized_report_date = _normalize_report_date(report_date)
    aum_raw: float | None = None
    ytd_raw: float | None = None
    nim_raw: float | None = None
    dv01_raw: float | None = None
    aum_delta = "无环比"
    ytd_delta = "无环比"
    nim_delta = "无环比"
    dv01_delta = "无环比"

    try:
        balance_repo = FormalZqtzBalanceMetricsRepository(str(settings.duckdb_path))
        balance_report_dates = list(getattr(balance_repo, "list_report_dates", lambda: [])())
        current_balance_report_date = normalized_report_date or (balance_report_dates[0] if balance_report_dates else None)
        row = (
            balance_repo.fetch_zqtz_asset_market_value(
                report_date=current_balance_report_date,
                currency_basis="CNY",
            )
            if current_balance_report_date is not None
            else None
        )
        if row is not None:
            aum_raw = float(row["total_market_value_amount"])
            previous_balance_report_date = _previous_report_date(
                balance_report_dates,
                current_balance_report_date,
            )
            if previous_balance_report_date is not None:
                previous_row = balance_repo.fetch_zqtz_asset_market_value(
                    report_date=previous_balance_report_date,
                    currency_basis="CNY",
                )
                if previous_row is not None:
                    aum_delta = _format_percent_change(
                        aum_raw,
                        float(previous_row["total_market_value_amount"]),
                    )
    except (RuntimeError, OSError, TypeError, ValueError):
        aum_raw = None

    try:
        pnl_repo = PnlRepository(str(settings.duckdb_path))
        pnl_report_dates = list(
            getattr(
                pnl_repo,
                "list_formal_fi_report_dates",
                getattr(pnl_repo, "list_union_report_dates", lambda: []),
            )()
        )
        current_pnl_report_date = normalized_report_date or (pnl_report_dates[0] if pnl_report_dates else None)
        if current_pnl_report_date is not None:
            ytd_raw = float(
                pnl_repo.sum_formal_total_pnl_through_report_date(current_pnl_report_date)
            )
        previous_pnl_report_date = _previous_report_date(
            pnl_report_dates,
            current_pnl_report_date,
        )
        if previous_pnl_report_date is not None:
            ytd_delta = _format_percent_change(
                ytd_raw,
                float(pnl_repo.sum_formal_total_pnl_through_report_date(previous_pnl_report_date)),
            )
    except (RuntimeError, OSError, TypeError, ValueError):
        ytd_raw = None

    try:
        liability_repo = LiabilityAnalyticsRepository(str(settings.duckdb_path))
        liability_report_date = normalized_report_date or liability_repo.resolve_latest_report_date()
        liability_report_dates = list(getattr(liability_repo, "list_report_dates", lambda: [])())
        if liability_report_date:
            zqtz_rows = liability_repo.fetch_zqtz_rows(liability_report_date)
            tyw_rows = liability_repo.fetch_tyw_rows(liability_report_date)
            payload = compute_liability_yield_metrics(
                liability_report_date,
                zqtz_rows,
                tyw_rows,
            )
            nim_value = payload.get("kpi", {}).get("nim")
            if nim_value is not None:
                nim_raw = float(nim_value)
                previous_liability_report_date = _previous_report_date(
                    liability_report_dates,
                    liability_report_date,
                )
                if previous_liability_report_date is not None:
                    previous_payload = compute_liability_yield_metrics(
                        previous_liability_report_date,
                        liability_repo.fetch_zqtz_rows(previous_liability_report_date),
                        liability_repo.fetch_tyw_rows(previous_liability_report_date),
                    )
                    nim_delta = _format_point_change(
                        nim_raw,
                        previous_payload.get("kpi", {}).get("nim"),
                    )
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        nim_raw = None

    try:
        bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
        bond_report_dates = list(getattr(bond_repo, "list_report_dates", lambda: [])())
        current_bond_report_date = normalized_report_date or (bond_report_dates[0] if bond_report_dates else None)
        snapshot = (
            bond_repo.fetch_risk_overview_snapshot(report_date=current_bond_report_date)
            if current_bond_report_date is not None
            else None
        )
        if snapshot is not None and snapshot.get("portfolio_dv01") is not None:
            dv01_raw = float(snapshot["portfolio_dv01"])
            previous_bond_report_date = _previous_report_date(
                bond_report_dates,
                current_bond_report_date,
            )
            if previous_bond_report_date is not None:
                previous_snapshot = bond_repo.fetch_risk_overview_snapshot(
                    report_date=previous_bond_report_date,
                )
                if previous_snapshot is not None and previous_snapshot.get("portfolio_dv01") is not None:
                    dv01_delta = _format_percent_change(
                        dv01_raw,
                        float(previous_snapshot["portfolio_dv01"]),
                    )
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        dv01_raw = None

    metrics: list[ExecutiveMetric] = []
    if aum_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="aum",
                label="资产规模",
                value=_fmt_yi_amount(aum_raw, signed=False),
                delta=aum_delta,
                tone="positive",
                detail=(
                    f"来自 fact_formal_zqtz_balance_daily 在 {normalized_report_date} 的 CNY 资产口径市值合计。"
                    if normalized_report_date is not None
                    else f"来自 fact_formal_zqtz_balance_daily 在 {current_balance_report_date} 的 CNY 资产口径市值合计。"
                ),
            )
        )
    if ytd_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="yield",
                label="年内收益",
                value=_fmt_yi_amount(ytd_raw, signed=True),
                delta=ytd_delta,
                tone="positive",
                detail=(
                    f"来自 fact_formal_pnl_fi 截至 {normalized_report_date} 的年内 total_pnl 合计。"
                    if normalized_report_date is not None
                    else f"来自 fact_formal_pnl_fi 截至 {current_pnl_report_date} 的年内 total_pnl 合计。"
                ),
            )
        )
    if nim_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="nim",
                label="净息差",
                value=_fmt_signed_percent(nim_raw),
                delta=nim_delta,
                tone="positive" if nim_raw >= 0 else "negative",
                detail=(
                    f"来自受治理负债分析收益指标，在 {normalized_report_date} 的 NIM 读面。"
                    if normalized_report_date is not None
                    else f"来自受治理负债分析收益指标，在 {liability_report_date} 的 NIM 读面。"
                ),
            )
        )
    if dv01_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="dv01",
                label="组合DV01",
                value=f"{dv01_raw:,.0f}",
                delta=dv01_delta,
                tone="warning",
                detail=(
                    f"来自 bond analytics 风险快照，在 {normalized_report_date} 的组合 DV01。"
                    if normalized_report_date is not None
                    else f"来自 bond analytics 风险快照，在 {current_bond_report_date} 的组合 DV01。"
                ),
            )
        )
    try:
        metrics.extend(
            ExecutiveMetric.model_validate(item)
            for item in resolve_executive_kpi_metrics(
                dsn=str(
                    getattr(settings, "governance_sql_dsn", "")
                    or getattr(settings, "postgres_dsn", "")
                ),
                report_date=current_pnl_report_date or normalized_report_date,
            )
        )
    except (RuntimeError, ValueError, TypeError, KeyError):
        pass

    payload = OverviewPayload(title="经营总览", metrics=metrics)
    has_missing_governed_metrics = (
        aum_raw is None
        or ytd_raw is None
        or nim_raw is None
        or dv01_raw is None
    )
    return _envelope(
        "executive.overview",
        payload,
        quality_flag="warning" if has_missing_governed_metrics else "ok",
        vendor_status="vendor_unavailable" if has_missing_governed_metrics else "ok",
        source_version="sv_exec_dashboard_explicit_miss_v1" if has_missing_governed_metrics else "sv_exec_dashboard_v1",
    )


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


def executive_pnl_attribution(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    normalized = _normalize_report_date(report_date)
    repo: ProductCategoryPnlRepository | None = None
    try:
        repo = ProductCategoryPnlRepository(str(settings.duckdb_path))
    except (RuntimeError, OSError, TypeError, ValueError):
        if normalized is not None:
            return _envelope(
                "executive.pnl-attribution",
                _pnl_attribution_explicit_miss_payload(normalized),
                quality_flag="warning",
                vendor_status="vendor_unavailable",
                source_version="sv_exec_dashboard_explicit_miss_v1",
            )
        repo = None

    built: PnlAttributionPayload | None = None
    if repo is not None:
        try:
            built = _build_pnl_attribution_from_repo(repo, report_date)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError):
            if normalized is not None:
                return _envelope(
                    "executive.pnl-attribution",
                    _pnl_attribution_explicit_miss_payload(normalized),
                    quality_flag="warning",
                    source_version="sv_exec_dashboard_explicit_miss_v1",
                )
            built = None

    if built is not None:
        return _envelope("executive.pnl-attribution", built)

    if normalized is not None:
        return _envelope(
            "executive.pnl-attribution",
            _pnl_attribution_explicit_miss_payload(normalized),
            quality_flag="warning",
            vendor_status="vendor_unavailable",
            source_version="sv_exec_dashboard_explicit_miss_v1",
        )

    return _envelope(
        "executive.pnl-attribution",
        _pnl_attribution_unavailable_payload(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version="sv_exec_dashboard_explicit_miss_v1",
    )


def executive_risk_overview(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    normalized_report_date = _normalize_report_date(report_date)
    try:
        repo = BondAnalyticsRepository(str(settings.duckdb_path))
        if normalized_report_date is not None:
            available_bond_dates = repo.list_report_dates()
            if available_bond_dates and normalized_report_date not in available_bond_dates:
                return _envelope(
                    "executive.risk-overview",
                    _empty_risk_overview_payload(),
                    quality_flag="warning",
                    vendor_status="vendor_unavailable",
                    source_version="sv_exec_dashboard_explicit_miss_v1",
                )
        snapshot = (
            repo.fetch_risk_overview_snapshot(report_date=normalized_report_date)
            if normalized_report_date is not None
            else repo.fetch_latest_risk_overview_snapshot()
        )
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
                asof_label = (
                    f"指定日期 {asof_date}"
                    if normalized_report_date is not None
                    else f"最新日期 {asof_date}"
                )
                payload = RiskOverviewPayload(
                    title="风险全景",
                    signals=[
                        RiskSignal(
                            id="duration",
                            label="久期风险",
                            value=f"{wdur_f:.2f} 年",
                            status="stable",
                            detail=f"{asof_label}，组合市值加权修正久期（modified_duration）。",
                        ),
                        RiskSignal(
                            id="leverage",
                            label="杠杆风险",
                            value=f"{dv01_f:,.0f}",
                            status="watch",
                            detail=f"{asof_label}，DV01 合计（元口径聚合）。",
                        ),
                        RiskSignal(
                            id="credit",
                            label="信用集中度",
                            value=f"{cred_f:.1f}%",
                            status="warning",
                            detail=f"{asof_label}，信用类债券市值占组合市值比重。",
                        ),
                        RiskSignal(
                            id="liquidity",
                            label="流动性风险",
                            value=f"{ytm_f:.2f} 年",
                            status="stable",
                            detail=f"{asof_label}，市值加权平均剩余期限（years_to_maturity）。",
                        ),
                    ],
                )
                return _envelope("executive.risk-overview", payload)
        return _envelope(
            "executive.risk-overview",
            _empty_risk_overview_payload(),
            quality_flag="warning",
            vendor_status="vendor_unavailable",
            source_version="sv_exec_dashboard_explicit_miss_v1",
        )
    except (RuntimeError, OSError, TypeError, ValueError):
        pass

    return _envelope(
        "executive.risk-overview",
        _empty_risk_overview_payload(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version="sv_exec_dashboard_explicit_miss_v1",
    )


def executive_contribution(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    normalized = _normalize_report_date(report_date)
    repo: ProductCategoryPnlRepository | None = None
    try:
        repo = ProductCategoryPnlRepository(str(settings.duckdb_path))
    except (RuntimeError, OSError, TypeError, ValueError):
        if normalized is not None:
            return _envelope(
                "executive.contribution",
                _contribution_explicit_miss_payload(normalized),
                quality_flag="warning",
                vendor_status="vendor_unavailable",
                source_version="sv_exec_dashboard_explicit_miss_v1",
            )
        repo = None

    built: ContributionPayload | None = None
    if repo is not None:
        try:
            built = _build_contribution_from_repo(repo, report_date)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError):
            if normalized is not None:
                return _envelope(
                    "executive.contribution",
                    _contribution_explicit_miss_payload(normalized),
                    quality_flag="warning",
                    vendor_status="vendor_unavailable",
                    source_version="sv_exec_dashboard_explicit_miss_v1",
                )
            built = None

    if built is not None:
        return _envelope("executive.contribution", built)

    if normalized is not None:
        return _envelope(
            "executive.contribution",
            _contribution_explicit_miss_payload(normalized),
            quality_flag="warning",
            vendor_status="vendor_unavailable",
            source_version="sv_exec_dashboard_explicit_miss_v1",
        )

    return _envelope(
        "executive.contribution",
        _contribution_unavailable_payload(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version="sv_exec_dashboard_explicit_miss_v1",
    )


def _fallback_executive_alerts() -> dict[str, object]:
    return _envelope(
        "executive.alerts",
        _empty_alerts_payload(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version="sv_exec_dashboard_explicit_miss_v1",
    )


def executive_alerts(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    explicit_requested = _normalize_report_date(report_date)
    try:
        repo = BondAnalyticsRepository(str(settings.duckdb_path))
        normalized_report_date = explicit_requested
        if normalized_report_date is None:
            dates = repo.list_report_dates()
            if not dates:
                return _fallback_executive_alerts()
            normalized_report_date = dates[0]
        elif normalized_report_date not in repo.list_report_dates():
            return _envelope(
                "executive.alerts",
                _empty_alerts_payload(),
                quality_flag="warning",
                vendor_status="vendor_unavailable",
                source_version="sv_exec_dashboard_explicit_miss_v1",
            )
        report_date_value = date.fromisoformat(normalized_report_date)
        rows = repo.fetch_bond_analytics_rows(report_date=report_date_value.isoformat())
        tensor = compute_portfolio_risk_tensor(rows, report_date=report_date_value)
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
        if explicit_requested is not None:
            return _envelope(
                "executive.alerts",
                _empty_alerts_payload(),
                quality_flag="warning",
                vendor_status="vendor_unavailable",
                source_version="sv_exec_dashboard_explicit_miss_v1",
            )
        return _fallback_executive_alerts()
