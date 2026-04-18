from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from backend.app.core_finance.alert_engine import evaluate_alerts
from backend.app.governance.formal_compute_lineage import resolve_completed_formal_build_lineage
from backend.app.core_finance.liability_analytics_compat import compute_liability_yield_metrics
from backend.app.core_finance.risk_tensor import compute_portfolio_risk_tensor
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.formal_zqtz_balance_metrics_repo import (
    FormalZqtzBalanceMetricsRepository,
)
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.product_category_pnl_repo import ProductCategoryPnlRepository
from backend.app.repositories.risk_tensor_repo import load_latest_bond_analytics_lineage
from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.executive_dashboard import (
    AlertsPayload,
    AlertItem,
    AttributionSegment,
    ContributionPayload,
    ContributionRow,
    ExecutiveMetric,
    HomeSnapshotPayload,
    OverviewPayload,
    PnlAttributionPayload,
    RiskOverviewPayload,
    RiskSignal,
    SummaryPayload,
    SummaryPoint,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.kpi_service import resolve_executive_kpi_metrics
from backend.app.tasks.pnl_materialize import CACHE_KEY as PNL_CACHE_KEY

PNL_JOB_NAME = "pnl_materialize"

_MISS_SOURCE = "sv_exec_dashboard_explicit_miss_v1"
_DEFAULT_SOURCE = "sv_exec_dashboard_v1"
_DEFAULT_RULE = "rv_exec_dashboard_v1"
_CACHE_VERSION = "cv_exec_dashboard_v1"


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
    source_version: str = _DEFAULT_SOURCE,
    rule_version: str = _DEFAULT_RULE,
    filters_applied: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_{result_kind.replace('.', '_')}",
        result_kind=result_kind,
        cache_version=_CACHE_VERSION,
        source_version=source_version,
        rule_version=rule_version,
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        filters_applied=filters_applied,
        result_payload=result.model_dump(mode="json"),
        source_surface="executive_analytical",
    )


def _fmt_yi_amount(value: float | None, *, signed: bool = False) -> Numeric:
    """Format a yuan-denominated amount into a Numeric in yi display.

    Retains the original signature to minimize churn at call sites (they just
    receive a Numeric instead of str now; ExecutiveMetric etc. accept both
    thanks to W2.1 coercion, but callers building Numerics directly bypass
    the coerce path).
    """
    if value is None:
        return Numeric(
            raw=None,
            unit="yuan",
            display="—" if signed else "0.00 亿",
            precision=2,
            sign_aware=signed,
        )
    v = float(value)
    yi = v / 1e8
    if signed:
        sign = "+" if yi >= 0 else ""
        display = f"{sign}{yi:,.2f} 亿"
    else:
        display = f"{yi:,.2f} 亿"
    return Numeric(
        raw=v,
        unit="yuan",
        display=display,
        precision=2,
        sign_aware=signed,
    )


def _fmt_signed_segment_yi(yi: float) -> Numeric:
    sign = "+" if yi >= 0 else ""
    return Numeric(
        raw=float(yi) * 1e8,
        unit="yuan",
        display=f"{sign}{yi:.2f} 亿",
        precision=2,
        sign_aware=True,
    )


def _fmt_signed_percent(value: float | None) -> Numeric:
    if value is None:
        return Numeric(raw=None, unit="pct", display="—", precision=2, sign_aware=True)
    sign = "+" if float(value) >= 0 else ""
    return Numeric(
        raw=float(value) / 100.0,  # raw 是 decimal ratio
        unit="pct",
        display=f"{sign}{float(value):.2f}%",
        precision=2,
        sign_aware=True,
    )


def _previous_report_date(dates: list[str], current_report_date: str | None) -> str | None:
    if not current_report_date or not dates:
        return None
    if current_report_date in dates:
        idx = dates.index(current_report_date)
        if idx + 1 < len(dates):
            return dates[idx + 1]
    return None


def _fetch_executive_aum_row(
    balance_repo: object,
    *,
    report_date: str,
    currency_basis: str = "CNY",
) -> dict[str, object] | None:
    fetch_formal_overview = getattr(balance_repo, "fetch_formal_overview", None)
    if callable(fetch_formal_overview):
        row = fetch_formal_overview(
            report_date=report_date,
            position_scope="asset",
            currency_basis=currency_basis,
        )
        if row is None:
            return None
        return {
            **row,
            "_metric_scope": "combined_formal_balance",
        }

    row = balance_repo.fetch_zqtz_asset_market_value(
        report_date=report_date,
        currency_basis=currency_basis,
    )
    if row is None:
        return None
    return {
        **row,
        "_metric_scope": "zqtz_only",
    }


def _lineage_tokens(*values: object) -> list[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        for token in text.split("__"):
            for dirty_part in token.split(","):
                normalized = dirty_part.strip()
                if normalized:
                    tokens.add(normalized)
    return sorted(tokens)


def _lineage_tokens_from_rows(rows: list[dict[str, object]], field_name: str) -> list[str]:
    return _lineage_tokens(*(row.get(field_name) for row in rows))


def _join_lineage_tokens(*values: object) -> str:
    return "__".join(_lineage_tokens(*values))


def _format_percent_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous in (None, 0):
        return Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)
    change = ((float(current) - float(previous)) / float(previous)) * 100
    sign = "+" if change >= 0 else ""
    return Numeric(
        raw=change / 100.0,
        unit="pct",
        display=f"{sign}{change:.2f}%",
        precision=2,
        sign_aware=True,
    )


def _format_point_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous is None:
        return Numeric(raw=None, unit="bp", display="无环比", precision=2, sign_aware=True)
    change = float(current) - float(previous)
    sign = "+" if change >= 0 else ""
    return Numeric(
        raw=change * 100.0,  # bp = percent point * 100
        unit="bp",
        display=f"{sign}{change:.2f}pp",
        precision=2,
        sign_aware=True,
    )


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
        value=Numeric(raw=None, unit="yuan", display="—", precision=2, sign_aware=False),
        delta=Numeric(raw=None, unit="pct", display=delta, precision=2, sign_aware=True),
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


def _build_repo_payload_envelope(
    result_kind: str,
    repo_factory,
    build_fn,
    miss_payload_fn,
    unavailable_payload_fn,
    report_date: str | None,
    normalized: str | None,
) -> dict[str, object]:
    """共用模式：构建 ProductCategoryPnlRepository 类端点的 envelope。

    消除 executive_pnl_attribution / executive_contribution 的重复结构。
    """
    repo = None
    try:
        repo = repo_factory()
    except (RuntimeError, OSError, TypeError, ValueError):
        if normalized is not None:
            return _envelope(
                result_kind,
                miss_payload_fn(normalized),
                quality_flag="warning",
                vendor_status="vendor_unavailable",
                source_version=_MISS_SOURCE,
                filters_applied={"report_date": normalized},
            )

    built = None
    src = _DEFAULT_SOURCE
    rule = _DEFAULT_RULE
    if repo is not None:
        try:
            result = build_fn(repo, report_date)
            if result is not None:
                built, rows = result
                src = _join_lineage_tokens(src, *_lineage_tokens_from_rows(rows, "source_version"))
                rule = _join_lineage_tokens(rule, *_lineage_tokens_from_rows(rows, "rule_version"))
        except (RuntimeError, OSError, TypeError, ValueError, KeyError):
            if normalized is not None:
                return _envelope(
                    result_kind,
                    miss_payload_fn(normalized),
                    quality_flag="warning",
                    source_version=_MISS_SOURCE,
                    filters_applied={"report_date": normalized},
                )

    if built is not None:
        return _envelope(
            result_kind,
            built,
            source_version=src,
            rule_version=rule,
            filters_applied={
                "report_date": normalized
                or next(
                    (
                        str(row.get("report_date") or "").strip()
                        for row in rows
                        if str(row.get("report_date") or "").strip()
                    ),
                    None,
                ),
            },
        )

    if normalized is not None:
        return _envelope(
            result_kind,
            miss_payload_fn(normalized),
            quality_flag="warning",
            vendor_status="vendor_unavailable",
            source_version=_MISS_SOURCE,
            filters_applied={"report_date": normalized},
        )

    return _envelope(
        result_kind,
        unavailable_payload_fn(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version=_MISS_SOURCE,
        filters_applied={"report_date": None},
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


def executive_overview(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    governance_dir = str(getattr(settings, "governance_path", "") or "").strip()
    normalized_report_date = _normalize_report_date(report_date)
    current_balance_report_date: str | None = None
    current_pnl_report_date: str | None = None
    liability_report_date: str | None = None
    current_bond_report_date: str | None = None
    aum_raw: float | None = None
    ytd_raw: float | None = None
    nim_raw: float | None = None
    dv01_raw: float | None = None
    overview_source_versions: list[object] = [_DEFAULT_SOURCE]
    overview_rule_versions: list[object] = [_DEFAULT_RULE]
    aum_delta: Numeric = Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)
    ytd_delta: Numeric = Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)
    nim_delta: Numeric = Numeric(raw=None, unit="bp", display="无环比", precision=2, sign_aware=True)
    dv01_delta: Numeric = Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)

    try:
        balance_repo = FormalZqtzBalanceMetricsRepository(str(settings.duckdb_path))
        balance_report_dates = list(getattr(balance_repo, "list_report_dates", lambda: [])())
        current_balance_report_date = normalized_report_date or (balance_report_dates[0] if balance_report_dates else None)
        row = (
            _fetch_executive_aum_row(
                balance_repo,
                report_date=current_balance_report_date,
                currency_basis="CNY",
            )
            if current_balance_report_date is not None
            else None
        )
        if row is not None:
            aum_raw = float(row["total_market_value_amount"])
            overview_source_versions.append(row.get("source_version"))
            overview_rule_versions.append(row.get("rule_version"))
            previous_balance_report_date = _previous_report_date(
                balance_report_dates,
                current_balance_report_date,
            )
            if previous_balance_report_date is not None:
                previous_row = _fetch_executive_aum_row(
                    balance_repo,
                    report_date=previous_balance_report_date,
                    currency_basis="CNY",
                )
                if previous_row is not None:
                    overview_source_versions.append(previous_row.get("source_version"))
                    overview_rule_versions.append(previous_row.get("rule_version"))
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
            if governance_dir:
                current_pnl_lineage = resolve_completed_formal_build_lineage(
                    governance_dir=governance_dir,
                    cache_key=PNL_CACHE_KEY,
                    job_name=PNL_JOB_NAME,
                    report_date=current_pnl_report_date,
                )
                if current_pnl_lineage is not None:
                    overview_source_versions.append(current_pnl_lineage.get("source_version"))
                    overview_rule_versions.append(current_pnl_lineage.get("rule_version"))
        previous_pnl_report_date = _previous_report_date(
            pnl_report_dates,
            current_pnl_report_date,
        )
        if previous_pnl_report_date is not None:
            if governance_dir:
                previous_pnl_lineage = resolve_completed_formal_build_lineage(
                    governance_dir=governance_dir,
                    cache_key=PNL_CACHE_KEY,
                    job_name=PNL_JOB_NAME,
                    report_date=previous_pnl_report_date,
                )
                if previous_pnl_lineage is not None:
                    overview_source_versions.append(previous_pnl_lineage.get("source_version"))
                    overview_rule_versions.append(previous_pnl_lineage.get("rule_version"))
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
            overview_source_versions.extend(_lineage_tokens_from_rows(zqtz_rows, "source_version"))
            overview_source_versions.extend(_lineage_tokens_from_rows(tyw_rows, "source_version"))
            overview_rule_versions.extend(_lineage_tokens_from_rows(zqtz_rows, "rule_version"))
            overview_rule_versions.extend(_lineage_tokens_from_rows(tyw_rows, "rule_version"))
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
                    previous_zqtz_rows = liability_repo.fetch_zqtz_rows(previous_liability_report_date)
                    previous_tyw_rows = liability_repo.fetch_tyw_rows(previous_liability_report_date)
                    overview_source_versions.extend(_lineage_tokens_from_rows(previous_zqtz_rows, "source_version"))
                    overview_source_versions.extend(_lineage_tokens_from_rows(previous_tyw_rows, "source_version"))
                    overview_rule_versions.extend(_lineage_tokens_from_rows(previous_zqtz_rows, "rule_version"))
                    overview_rule_versions.extend(_lineage_tokens_from_rows(previous_tyw_rows, "rule_version"))
                    previous_payload = compute_liability_yield_metrics(
                        previous_liability_report_date,
                        previous_zqtz_rows,
                        previous_tyw_rows,
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
            if governance_dir:
                current_bond_lineage = load_latest_bond_analytics_lineage(
                    governance_dir=governance_dir,
                    report_date=current_bond_report_date,
                )
                if current_bond_lineage is not None:
                    overview_source_versions.append(current_bond_lineage.get("source_version"))
                    overview_rule_versions.append(current_bond_lineage.get("rule_version"))
            previous_bond_report_date = _previous_report_date(
                bond_report_dates,
                current_bond_report_date,
            )
            if previous_bond_report_date is not None:
                previous_snapshot = bond_repo.fetch_risk_overview_snapshot(
                    report_date=previous_bond_report_date,
                )
                if previous_snapshot is not None and previous_snapshot.get("portfolio_dv01") is not None:
                    if governance_dir:
                        previous_bond_lineage = load_latest_bond_analytics_lineage(
                            governance_dir=governance_dir,
                            report_date=previous_bond_report_date,
                        )
                        if previous_bond_lineage is not None:
                            overview_source_versions.append(previous_bond_lineage.get("source_version"))
                            overview_rule_versions.append(previous_bond_lineage.get("rule_version"))
                    dv01_delta = _format_percent_change(
                        dv01_raw,
                        float(previous_snapshot["portfolio_dv01"]),
                    )
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        dv01_raw = None

    metrics: list[ExecutiveMetric] = []
    if aum_raw is not None:
        aum_scope = str(row.get("_metric_scope") or "") if row is not None else ""
        aum_label = "资产规模" if aum_scope == "combined_formal_balance" else "债券资产规模（zqtz）"
        aum_detail = (
            (
                f"来自 governed formal balance overview，在 {normalized_report_date} 的 CNY 资产口径市值合计。"
                if normalized_report_date is not None
                else f"来自 governed formal balance overview，在 {current_balance_report_date} 的 CNY 资产口径市值合计。"
            )
            if aum_scope == "combined_formal_balance"
            else (
                f"来自 fact_formal_zqtz_balance_daily，在 {normalized_report_date} 的 CNY 资产口径市值合计。"
                if normalized_report_date is not None
                else f"来自 fact_formal_zqtz_balance_daily，在 {current_balance_report_date} 的 CNY 资产口径市值合计。"
            )
        )
        metrics.append(
            ExecutiveMetric(
                id="aum",
                label=aum_label,
                value=_fmt_yi_amount(aum_raw, signed=False),
                delta=aum_delta,
                tone="positive",
                detail=aum_detail,
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
                value=Numeric(
                    raw=dv01_raw,
                    unit="dv01",
                    display=f"{dv01_raw:,.0f}",
                    precision=0,
                    sign_aware=False,
                ),
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
        source_version=(
            _MISS_SOURCE
            if has_missing_governed_metrics
            else _join_lineage_tokens(*overview_source_versions)
        ),
        rule_version=(
            _DEFAULT_RULE
            if has_missing_governed_metrics
            else _join_lineage_tokens(*overview_rule_versions)
        ),
        filters_applied={
            "requested_report_date": normalized_report_date,
            "effective_report_dates": {
                "balance": current_balance_report_date,
                "pnl": current_pnl_report_date,
                "liability": liability_report_date,
                "risk": current_bond_report_date,
            },
        },
    )


def executive_summary(report_date: str | None = None) -> dict[str, object]:
    payload = SummaryPayload(
        title="本周管理摘要",
        report_date=report_date,
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
    overview_payload = executive_overview(report_date=report_date)
    overview_meta = overview_payload.get("result_meta") if isinstance(overview_payload, dict) else None
    source_version = _MISS_SOURCE
    rule_version = _DEFAULT_RULE
    if isinstance(overview_meta, dict) and overview_meta.get("vendor_status") == "ok":
        source_version = str(overview_meta.get("source_version") or "").strip() or source_version
        rule_version = str(overview_meta.get("rule_version") or "").strip() or rule_version
    return _envelope(
        "executive.summary",
        payload,
        source_version=source_version,
        rule_version=rule_version,
    )


def executive_pnl_attribution(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    normalized = _normalize_report_date(report_date)
    return _build_repo_payload_envelope(
        result_kind="executive.pnl-attribution",
        repo_factory=lambda: ProductCategoryPnlRepository(str(settings.duckdb_path)),
        build_fn=_build_pnl_attribution_from_repo,
        miss_payload_fn=_pnl_attribution_explicit_miss_payload,
        unavailable_payload_fn=_pnl_attribution_unavailable_payload,
        report_date=report_date,
        normalized=normalized,
    )


def executive_risk_overview(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    governance_dir = str(getattr(settings, "governance_path", "") or "").strip()
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
                    source_version=_MISS_SOURCE,
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
                            value=Numeric(raw=wdur_f, unit="ratio", display=f"{wdur_f:.2f} 年", precision=2, sign_aware=False),
                            status="stable",
                            detail=f"{asof_label}，组合市值加权修正久期（modified_duration）。",
                        ),
                        RiskSignal(
                            id="leverage",
                            label="杠杆风险",
                            value=Numeric(raw=dv01_f, unit="dv01", display=f"{dv01_f:,.0f}", precision=0, sign_aware=False),
                            status="watch",
                            detail=f"{asof_label}，DV01 合计（元口径聚合）。",
                        ),
                        RiskSignal(
                            id="credit",
                            label="信用集中度",
                            value=Numeric(raw=cred_f, unit="pct", display=f"{cred_f:.1f}%", precision=1, sign_aware=False),
                            status="warning",
                            detail=f"{asof_label}，信用类债券市值占组合市值比重。",
                        ),
                        RiskSignal(
                            id="liquidity",
                            label="流动性风险",
                            value=Numeric(raw=ytm_f, unit="ratio", display=f"{ytm_f:.2f} 年", precision=2, sign_aware=False),
                            status="stable",
                            detail=f"{asof_label}，市值加权平均剩余期限（years_to_maturity）。",
                        ),
                    ],
                )
                risk_source_version = _DEFAULT_SOURCE
                risk_rule_version = _DEFAULT_RULE
                if governance_dir:
                    lineage = load_latest_bond_analytics_lineage(
                        governance_dir=governance_dir,
                        report_date=asof_date,
                    )
                    if lineage is not None:
                        risk_source_version = _join_lineage_tokens(
                            risk_source_version,
                            lineage.get("source_version"),
                        )
                        risk_rule_version = _join_lineage_tokens(
                            risk_rule_version,
                            lineage.get("rule_version"),
                        )
                return _envelope(
                    "executive.risk-overview",
                    payload,
                    source_version=risk_source_version,
                    rule_version=risk_rule_version,
                )
        return _envelope(
            "executive.risk-overview",
            _empty_risk_overview_payload(),
            quality_flag="warning",
            vendor_status="vendor_unavailable",
            source_version=_MISS_SOURCE,
        )
    except (RuntimeError, OSError, TypeError, ValueError):
        pass

    return _envelope(
        "executive.risk-overview",
        _empty_risk_overview_payload(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version=_MISS_SOURCE,
    )


def executive_contribution(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    normalized = _normalize_report_date(report_date)
    return _build_repo_payload_envelope(
        result_kind="executive.contribution",
        repo_factory=lambda: ProductCategoryPnlRepository(str(settings.duckdb_path)),
        build_fn=_build_contribution_from_repo,
        miss_payload_fn=_contribution_explicit_miss_payload,
        unavailable_payload_fn=_contribution_unavailable_payload,
        report_date=report_date,
        normalized=normalized,
    )


def _fallback_executive_alerts() -> dict[str, object]:
    return _envelope(
        "executive.alerts",
        _empty_alerts_payload(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version=_MISS_SOURCE,
    )


def executive_alerts(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    governance_dir = str(getattr(settings, "governance_path", "") or "").strip()
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
                source_version=_MISS_SOURCE,
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
        alerts_source_version = _DEFAULT_SOURCE
        alerts_rule_version = _DEFAULT_RULE
        if governance_dir:
            lineage = load_latest_bond_analytics_lineage(
                governance_dir=governance_dir,
                report_date=normalized_report_date,
            )
            if lineage is not None:
                alerts_source_version = _join_lineage_tokens(
                    alerts_source_version,
                    lineage.get("source_version"),
                )
                alerts_rule_version = _join_lineage_tokens(
                    alerts_rule_version,
                    lineage.get("rule_version"),
                )
        return _envelope(
            "executive.alerts",
            payload,
            source_version=alerts_source_version,
            rule_version=alerts_rule_version,
        )
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError, KeyError):
        if explicit_requested is not None:
            return _envelope(
                "executive.alerts",
                _empty_alerts_payload(),
                quality_flag="warning",
                vendor_status="vendor_unavailable",
                source_version=_MISS_SOURCE,
            )
        return _fallback_executive_alerts()


_HOME_SNAPSHOT_DOMAINS = ("balance", "pnl", "liability", "bond")


def _list_domain_dates() -> dict[str, set[str]]:
    """Return the set of available report_dates per domain."""
    settings = get_settings()
    dates: dict[str, set[str]] = {d: set() for d in _HOME_SNAPSHOT_DOMAINS}
    try:
        balance_repo = FormalZqtzBalanceMetricsRepository(str(settings.duckdb_path))
        dates["balance"] = set(balance_repo.list_report_dates(currency_basis="CNY"))
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        dates["balance"] = set()

    try:
        pnl_repo = PnlRepository(str(settings.duckdb_path))
        dates["pnl"] = set(pnl_repo.list_formal_fi_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        dates["pnl"] = set()

    try:
        liability_repo = LiabilityAnalyticsRepository(str(settings.duckdb_path))
        dates["liability"] = set(liability_repo.list_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        dates["liability"] = set()

    try:
        bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
        dates["bond"] = set(bond_repo.list_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        dates["bond"] = set()

    return dates


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
                    {domain: requested for domain in _HOME_SNAPSHOT_DOMAINS},
                )
            return (None, list(_HOME_SNAPSHOT_DOMAINS), {})
        if not intersection:
            return (None, list(_HOME_SNAPSHOT_DOMAINS), {})
        top_date = max(intersection)
        return (
            top_date,
            [],
            {domain: top_date for domain in _HOME_SNAPSHOT_DOMAINS},
        )

    # partial: accept any requested or fall back to union max
    if requested:
        target = requested
    else:
        union = set.union(*domain_dates.values()) if domain_dates.values() else set()
        if not union:
            return (None, list(_HOME_SNAPSHOT_DOMAINS), {})
        target = max(union)

    missing = [
        domain for domain in _HOME_SNAPSHOT_DOMAINS if target not in domain_dates[domain]
    ]
    effective: dict[str, str] = {}
    for domain in _HOME_SNAPSHOT_DOMAINS:
        if target in domain_dates[domain]:
            effective[domain] = target
        elif domain_dates[domain]:
            # approximate latest available for that domain
            effective[domain] = max(domain_dates[domain])
    return (target, missing, effective)


def _empty_home_snapshot_payload() -> HomeSnapshotPayload:
    return HomeSnapshotPayload(
        report_date="",
        mode="strict",
        source_surface="executive_analytical",
        overview=OverviewPayload(title="经营总览", metrics=[]),
        attribution=_pnl_attribution_unavailable_payload(),
        domains_missing=list(_HOME_SNAPSHOT_DOMAINS),
        domains_effective_date={},
    )


def home_snapshot_envelope(
    *,
    report_date: str | None = None,
    allow_partial: bool = False,
) -> dict[str, object]:
    """Build the authoritative home snapshot envelope.

    See ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 4.
    """
    normalized = _normalize_report_date(report_date)
    domain_dates = _list_domain_dates()

    target_date, domains_missing, effective = _compute_unified_report_date(
        requested=normalized,
        allow_partial=allow_partial,
        domain_dates=domain_dates,
    )

    if target_date is None:
        return _envelope(
            "home.snapshot",
            _empty_home_snapshot_payload(),
            quality_flag="error",
            vendor_status="vendor_unavailable",
            source_version="sv_home_snapshot_empty_v1",
            filters_applied={
                "requested_report_date": normalized,
                "allow_partial": allow_partial,
                "effective_report_dates": {},
                "domains_missing": list(_HOME_SNAPSHOT_DOMAINS),
            },
        )

    overview_env = executive_overview(report_date=target_date)
    attribution_env = executive_pnl_attribution(report_date=target_date)
    overview_result = OverviewPayload.model_validate(overview_env["result"])
    attribution_result = PnlAttributionPayload.model_validate(attribution_env["result"])

    payload = HomeSnapshotPayload(
        report_date=target_date,
        mode="partial" if allow_partial else "strict",
        source_surface="executive_analytical",
        overview=overview_result,
        attribution=attribution_result,
        domains_missing=domains_missing,
        domains_effective_date=effective,
    )

    quality_flag: Literal["ok", "warning", "error", "stale"] = (
        "ok" if not domains_missing else "warning"
    )
    vendor_status: Literal["ok", "vendor_stale", "vendor_unavailable"] = (
        "ok" if not domains_missing else "vendor_stale"
    )

    return _envelope(
        "home.snapshot",
        payload,
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        source_version="sv_home_snapshot_v1",
        rule_version="rv_home_snapshot_v1",
        filters_applied={
            "requested_report_date": normalized,
            "allow_partial": allow_partial,
            "report_date": target_date,
            "effective_report_dates": effective,
            "domains_missing": domains_missing,
        },
    )
