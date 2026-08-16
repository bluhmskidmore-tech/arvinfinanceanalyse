"""Executive dashboard 纯 payload 构建器(自 executive_service.py 门面拆分,逐字迁移)。

本模块只包含"输入参数 → payload/值对象"的确定性构建逻辑:PnL 归因与贡献拆解、
风险张量转换、统一报告日推导、verdict 定调、产品分类头条与空 payload 家族。
仓库实例一律由调用方(门面)构造后作为参数传入;本模块不构造仓库、不读 settings、
不触缓存,保证门面侧 monkeypatch 语义不受拆分影响。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from backend.app.core_finance.risk_tensor import PortfolioRiskTensor
from backend.app.repositories.product_category_pnl_repo import ProductCategoryPnlRepository
from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.executive_dashboard import (
    AlertsPayload,
    AttributionSegment,
    ContributionPayload,
    ContributionRow,
    HomeSnapshotPayload,
    OverviewPayload,
    PnlAttributionPayload,
    ProductCategoryMonthlyHeadlinePayload,
    ProductCategoryYtdHeadlinePayload,
    RiskOverviewPayload,
    VerdictPayload,
    VerdictReason,
    VerdictSuggestion,
    VerdictTone,
)
from backend.app.services.executive_service_formatting import (
    _YUAN_PER_YI,
    _fmt_signed_segment_yi,
    _fmt_yi_amount,
    _normalize_report_date,
    _tone_for_signed,
)

_CATEGORY_ID_TO_ATTRIBUTION_SEGMENT: dict[str, str] = {
    # Only level-1 category_ids reach _aggregate_attribution_segments (via
    # _level1_monthly_rows L380-384).  Currently only ``bond_investment``
    # defines children at level 1 in product_category_mapping.py; other
    # product categories (interbank, repo, NCD, etc.) are all level 0 and
    # flow entirely into the ``other`` bucket by design.
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
    target_report_date = _normalize_report_date(report_date)
    if target_report_date is None:
        dates = repo.list_report_dates()
        if not dates:
            return None
        target_report_date = dates[0]
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
        totals[seg] += val / _YUAN_PER_YI
    return totals


def _build_pnl_attribution_from_repo(
    repo: ProductCategoryPnlRepository,
    report_date: str | None = None,
) -> tuple[PnlAttributionPayload, list[dict[str, object]]] | None:
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
            amount=_fmt_signed_segment_yi(val),
            tone=_tone_for_signed(val),
        )
        for key, label, val in order
    ]
    return (
        PnlAttributionPayload(
            title="经营贡献拆解",
            total=_fmt_yi_amount(total_yi * 1e8, signed=True),
            segments=segments,
        ),
        rows,
    )


_ZERO_ATTRIBUTION_SEGMENTS = [
    ("carry", "Carry"),
    ("roll", "Roll-down"),
    ("credit", "信用利差"),
    ("trading", "交易损益"),
    ("other", "其他"),
]


def _zero_pnl_attribution_payload(title: str) -> PnlAttributionPayload:
    segments = [
        AttributionSegment(
            id=key,
            label=label,
            amount=_fmt_signed_segment_yi(0.0),
            tone=_tone_for_signed(0.0),
        )
        for key, label in _ZERO_ATTRIBUTION_SEGMENTS
    ]
    return PnlAttributionPayload(
        title=title,
        total=Numeric(raw=0.0, unit="yuan", display="0 亿", precision=0, sign_aware=False),
        segments=segments,
    )


def _pnl_attribution_explicit_miss_payload(report_date: str) -> PnlAttributionPayload:
    return _zero_pnl_attribution_payload(f"经营贡献拆解（{report_date} 无受控产品分类月度数据）")


def _pnl_attribution_unavailable_payload() -> PnlAttributionPayload:
    return _zero_pnl_attribution_payload("经营贡献拆解（当前无受控产品分类月度数据）")


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
) -> tuple[ContributionPayload, list[dict[str, object]]] | None:
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
    return (
        ContributionPayload(
            title="团队 / 账户 / 策略贡献",
            rows=contribution_rows,
        ),
        rows,
    )


def _decimal_from_formal_numeric(
    value: object,
    *,
    field_name: str,
    allow_none: bool = False,
) -> Decimal:
    if isinstance(value, dict):
        if "raw" not in value:
            raise ValueError(f"Formal risk tensor numeric field {field_name!r} has no raw value.")
        value = value["raw"]
    if value is None:
        if allow_none:
            return Decimal("0")
        raise ValueError(f"Formal risk tensor numeric field {field_name!r} is null.")
    if isinstance(value, bool):
        raise ValueError(f"Formal risk tensor numeric field {field_name!r} is boolean.")
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError(
            f"Formal risk tensor numeric field {field_name!r} is invalid."
        ) from exc
    if not decimal_value.is_finite():
        raise ValueError(f"Formal risk tensor numeric field {field_name!r} is not finite.")
    return decimal_value


def _portfolio_risk_tensor_from_formal_result(
    result: dict[str, object],
    *,
    expected_report_date: date,
) -> PortfolioRiskTensor:
    result_report_date = date.fromisoformat(str(result["report_date"]))
    if result_report_date != expected_report_date:
        raise ValueError(
            "Formal risk tensor report_date does not match the requested executive alerts date."
        )
    warnings = result.get("warnings") or []
    if not isinstance(warnings, list):
        raise ValueError("Formal risk tensor warnings must be a list.")

    def _numeric(field_name: str, *, allow_none: bool = False) -> Decimal:
        return _decimal_from_formal_numeric(
            result.get(field_name),
            field_name=field_name,
            allow_none=allow_none,
        )

    return PortfolioRiskTensor(
        report_date=result_report_date,
        portfolio_dv01=_numeric("portfolio_dv01"),
        regulatory_dv01=_numeric("regulatory_dv01", allow_none=True),
        krd_1y=_numeric("krd_1y"),
        krd_3y=_numeric("krd_3y"),
        krd_5y=_numeric("krd_5y"),
        krd_7y=_numeric("krd_7y"),
        krd_10y=_numeric("krd_10y"),
        krd_30y=_numeric("krd_30y"),
        cs01=_numeric("cs01"),
        portfolio_convexity=_numeric("portfolio_convexity"),
        portfolio_modified_duration=_numeric("portfolio_modified_duration"),
        issuer_concentration_hhi=_numeric("issuer_concentration_hhi"),
        issuer_top5_weight=_numeric("issuer_top5_weight"),
        asset_cashflow_30d=_numeric("asset_cashflow_30d"),
        asset_cashflow_90d=_numeric("asset_cashflow_90d"),
        liability_cashflow_30d=_numeric("liability_cashflow_30d"),
        liability_cashflow_90d=_numeric("liability_cashflow_90d"),
        liquidity_gap_30d=_numeric("liquidity_gap_30d"),
        liquidity_gap_90d=_numeric("liquidity_gap_90d"),
        liquidity_gap_30d_ratio=_numeric("liquidity_gap_30d_ratio"),
        total_market_value=_numeric("total_market_value"),
        bond_count=int(result["bond_count"]),
        quality_flag=str(result["quality_flag"]),
        warnings=[str(warning) for warning in warnings],
    )


def _formal_risk_tensor_quality_flag(
    result_meta: dict[str, object],
    tensor: PortfolioRiskTensor,
) -> Literal["ok", "warning", "error", "stale"]:
    value = str(result_meta.get("quality_flag") or tensor.quality_flag).strip()
    if value == "ok":
        return "ok"
    if value == "warning":
        return "warning"
    if value == "error":
        return "error"
    if value == "stale":
        return "stale"
    raise ValueError(f"Formal risk tensor owner returned invalid quality_flag={value!r}.")


_HOME_SNAPSHOT_CALIBERS = ("balance_sheet", "pnl")
"""Business calibers for the home snapshot.

- ``balance_sheet``: AUM + NIM + DV01 — all from the same T+1 daily pipeline.
  Available dates = intersection(balance, liability, bond).
- ``pnl``: YTD P&L — independent formal build cycle.
- Market/macro data is excluded; it is real-time and not bound to report date.
"""


def _domain_dates_from_context(context: dict[str, list[str]]) -> dict[str, set[str]]:
    balance_dates = set(context.get("balance", []))
    liability_dates = set(context.get("liability", []))
    bond_dates = set(context.get("bond", []))
    bs_components = [balance_dates, liability_dates, bond_dates]
    balance_sheet_dates = (
        set.intersection(*bs_components) if all(bs_components) else set()
    )
    return {
        "balance_sheet": balance_sheet_dates,
        "pnl": set(context.get("pnl", [])),
    }


def _compute_unified_report_date(
    *,
    requested: str | None,
    allow_partial: bool,
    domain_dates: dict[str, set[str]],
) -> tuple[str | None, list[str], dict[str, str]]:
    """Pick the authoritative report_date given inputs.

    Returns ``(report_date, domains_missing, domains_effective_date)``.
    - strict mode: returns the most recent date in the intersection; if
      ``requested`` is set and in intersection, returns it; else (None, all_domains, {}).
    - partial mode: returns ``requested`` (or max across union if not requested)
      and labels domains that don't have that date as missing.
    """
    intersection: set[str] = (
        set.intersection(*domain_dates.values()) if all(domain_dates.values()) else set()
    )

    if not allow_partial:
        # strict: intersection-only
        if requested:
            if requested in intersection:
                return (
                    requested,
                    [],
                    {domain: requested for domain in _HOME_SNAPSHOT_CALIBERS},
                )
            return (None, list(_HOME_SNAPSHOT_CALIBERS), {})
        if not intersection:
            return (None, list(_HOME_SNAPSHOT_CALIBERS), {})
        top_date = max(intersection)
        return (
            top_date,
            [],
            {domain: top_date for domain in _HOME_SNAPSHOT_CALIBERS},
        )

    # partial: accept any requested or fall back to union max
    if requested:
        target = requested
    else:
        union = set.union(*domain_dates.values()) if domain_dates.values() else set()
        if not union:
            return (None, list(_HOME_SNAPSHOT_CALIBERS), {})
        target = max(union)

    missing = [
        domain for domain in _HOME_SNAPSHOT_CALIBERS if target not in domain_dates[domain]
    ]
    effective: dict[str, str] = {}
    for domain in _HOME_SNAPSHOT_CALIBERS:
        if target in domain_dates[domain]:
            effective[domain] = target
        elif domain_dates[domain]:
            # approximate latest available for that domain
            effective[domain] = max(domain_dates[domain])
    return (target, missing, effective)


_VERDICT_TONES: frozenset[str] = frozenset({"positive", "neutral", "warning", "negative"})


def _coerce_verdict_tone(raw: str) -> VerdictTone:
    if raw in _VERDICT_TONES:
        return raw  # type: ignore[return-value]
    return "neutral"


def executive_verdict(
    *,
    overview: OverviewPayload,
    attention_count: int,
    partial_note: str | None,
    client_mode: str = "real",
) -> VerdictPayload:
    """首屏 Pyramid 定调：结论、支撑事实与下钻建议（确定性、可测试）。"""

    metrics = overview.metrics
    reasons: list[VerdictReason] = []
    for m in metrics[:3]:
        reasons.append(
            VerdictReason(
                label=m.label,
                value=m.value.display,
                detail=m.detail,
                tone=_coerce_verdict_tone(m.tone),
            )
        )

    tones = [_coerce_verdict_tone(m.tone) for m in metrics]
    pos = sum(1 for t in tones if t == "positive")
    neg = sum(1 for t in tones if t == "negative")
    warn = sum(1 for t in tones if t == "warning")

    if client_mode != "real" or partial_note:
        conclusion = "数据状态需先复核，再做方向性判断"
        tone: VerdictTone = "warning"
    elif not metrics:
        conclusion = "当前指标平稳，等待下一组观测"
        tone = "neutral"
    elif len(tones) > 0 and all(t == "neutral" for t in tones):
        conclusion = "当前指标平稳，等待下一组观测"
        tone = "neutral"
    elif pos >= neg + warn:
        conclusion = "首屏整体偏多，可基于规模与收益做方向性判断"
        tone = "positive"
    elif neg + warn > pos:
        conclusion = "首屏存在压力点，需进入专题页确认原因"
        tone = "warning"
    else:
        conclusion = "当前指标平稳，等待下一组观测"
        tone = "neutral"

    suggestions: list[VerdictSuggestion] = [
        VerdictSuggestion(text="进入对应专题页继续下钻原因链条", link=None),
    ]
    if any(_coerce_verdict_tone(m.tone) in ("warning", "negative") for m in metrics):
        suggestions.append(
            VerdictSuggestion(text="关注信用利差与久期暴露", link="/bond-analysis"),
        )
    if attention_count > 0 or partial_note:
        suggestions.append(
            VerdictSuggestion(text="复核治理状态后再做正式结论", link="/governance"),
        )

    return VerdictPayload(
        conclusion=conclusion,
        tone=tone,
        reasons=reasons,
        suggestions=suggestions,
    )


def _product_category_ytd_headline_from_values(
    report_date: str,
    values: dict[str, object],
) -> ProductCategoryYtdHeadlinePayload | None:
    if values.get("grand_total") is None:
        return None
    summary_pnl = _fmt_yi_amount(float(values["grand_total"]), signed=True)
    summary_detail = (
        "Aligned with product-category view=ytd "
        f"grand_total.business_net_income; report_date={report_date}."
    )
    intermediate = values.get("intermediate_business_income")
    if intermediate is None:
        int_numeric = _fmt_yi_amount(None, signed=True)
        int_detail = (
            "intermediate_business_income row was not found for product-category "
            f"view=ytd; report_date={report_date}."
        )
    else:
        int_numeric = _fmt_yi_amount(float(intermediate), signed=True)
        int_detail = (
            "Aligned with product-category view=ytd "
            f"intermediate_business_income; report_date={report_date}."
        )
    return ProductCategoryYtdHeadlinePayload(
        view="ytd",
        summary_pnl=summary_pnl,
        summary_pnl_detail=summary_detail,
        operating_income=summary_pnl,
        operating_income_detail=summary_detail,
        intermediate_business_income=int_numeric,
        intermediate_business_income_detail=int_detail,
    )


def _product_category_monthly_headline_from_values(
    report_date: str,
    values: dict[str, object],
) -> ProductCategoryMonthlyHeadlinePayload | None:
    if values.get("grand_total") is None:
        return None
    monthly_detail = (
        "Aligned with product-category view=monthly "
        f"grand_total.business_net_income; report_date={report_date}."
    )
    return ProductCategoryMonthlyHeadlinePayload(
        view="monthly",
        monthly_income=_fmt_yi_amount(float(values["grand_total"]), signed=True),
        monthly_income_detail=monthly_detail,
    )


class _ProductCategoryHeadlineValues(dict[str, dict[str, object]]):
    """Home-headline fast-path values carrying explicit degradation metadata.

    Mirrors the `_HomeCacheBuildRunRows` pattern: shape-compatible with the
    plain dict consumers already `.get()` from, while exposing fail-visible
    `degraded` / `degraded_reason` attributes instead of a silent empty dict.
    """

    def __init__(
        self,
        values: dict[str, dict[str, object]] | None = None,
        *,
        degraded: bool = False,
        degraded_reason: str | None = None,
    ) -> None:
        super().__init__(values or {})
        self.degraded = degraded
        self.degraded_reason = degraded_reason


class _DegradedProductCategoryHeadline:
    """Explicit degraded marker returned instead of a silent ``None``.

    The headline payload schemas cannot carry warnings, so the failure reason
    rides on this marker; `_compute_home_snapshot_envelope` converts it back
    to ``None`` for the payload and surfaces the reason in
    ``filters_applied.degraded_reasons``.
    """

    degraded = True

    def __init__(self, component: str, reason: str) -> None:
        self.component = component
        self.reason = reason


def _empty_home_snapshot_payload() -> HomeSnapshotPayload:
    return HomeSnapshotPayload(
        report_date="",
        mode="strict",
        source_surface="executive_analytical",
        overview=OverviewPayload(title="经营总览", metrics=[]),
        attribution=_pnl_attribution_unavailable_payload(),
        domains_missing=list(_HOME_SNAPSHOT_CALIBERS),
        domains_effective_date={},
        verdict=None,
        product_category_ytd=None,
        product_category_monthly=None,
    )
