from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import duckdb
from backend.app.core_finance.alert_engine import evaluate_alerts
from backend.app.core_finance.liability_analytics_compat import compute_liability_yield_metrics
from backend.app.core_finance.risk_tensor import compute_portfolio_risk_tensor
from backend.app.governance.formal_compute_lineage import resolve_completed_formal_build_lineage
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
    AlertItem,
    AlertsPayload,
    AttributionSegment,
    ContributionPayload,
    ContributionRow,
    ExecutiveMetric,
    HomeSnapshotPayload,
    OverviewPayload,
    PnlAttributionPayload,
    ProductCategoryMonthlyHeadlinePayload,
    ProductCategoryYtdHeadlinePayload,
    RiskOverviewPayload,
    RiskSignal,
    SummaryPayload,
    SummaryPoint,
    VerdictPayload,
    VerdictReason,
    VerdictSuggestion,
    VerdictTone,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.kpi_service import (
    resolve_executive_kpi_metrics,
    resolve_kpi_authority_gate,
)
from backend.app.services.product_category_pnl_service import (
    product_category_pnl_envelope,
    resolve_product_category_ytd_payload_for_home_snapshot,
)
from backend.app.services.runtime_cache import InMemoryTTLCache, get_runtime_cache
from backend.app.tasks.pnl_materialize import CACHE_KEY as PNL_CACHE_KEY

PNL_JOB_NAME = "pnl_materialize"

_MISS_SOURCE = "sv_exec_dashboard_explicit_miss_v1"
_DEFAULT_SOURCE = "sv_exec_dashboard_v1"
_DEFAULT_RULE = "rv_exec_dashboard_v1"
_CACHE_VERSION = "cv_exec_dashboard_v1"
logger = logging.getLogger(__name__)
_logger = logging.getLogger(__name__)

# Yuan → 亿 conversion factor; a single named constant avoids magic-number scatter.
_YUAN_PER_YI: float = 1e8


def _normalize_report_date(report_date: str | None) -> str | None:
    if report_date is None:
        return None
    return date.fromisoformat(str(report_date).strip()).isoformat()


def _safe_report_year(report_date: str | None) -> int | None:
    if not report_date:
        return None
    try:
        return date.fromisoformat(str(report_date).strip()).year
    except ValueError:
        return None


def _single_effective_report_date(*report_dates: str | None) -> str | None:
    resolved = [str(value or "").strip() for value in report_dates]
    if not resolved or any(not value for value in resolved):
        return None
    first = resolved[0]
    return first if all(value == first for value in resolved) else None


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
    requested_report_date: str | None = None,
    resolved_report_date: str | None = None,
    as_of_date: str | None = None,
    date_basis: str | None = None,
    fallback_date: str | None = None,
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
        requested_report_date=requested_report_date,
        resolved_report_date=resolved_report_date,
        as_of_date=as_of_date,
        date_basis=date_basis,
        fallback_date=fallback_date,
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
    yi = v / _YUAN_PER_YI
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
        raw=float(yi) * _YUAN_PER_YI,
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


def _normalize_ratio_percent_input(value: float | None) -> float:
    """Treat input as decimal-ratio (e.g. 0.035 = 3.5%).

    Upstream callers (compute_liability_yield_metrics → weighted_rate) all
    return decimal ratios.  The previous heuristic threshold ``abs(v) >= 0.1``
    caused a 100× error for NIM values at or above 10 bp decimal (0.001).
    """
    if value is None:
        return 0.0
    return float(value)


def _fmt_signed_ratio_percent(value: float | None) -> Numeric:
    if value is None:
        return Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True)
    ratio = _normalize_ratio_percent_input(value)
    sign = "+" if ratio >= 0 else ""
    return Numeric(
        raw=ratio,
        unit="pct",
        display=f"{sign}{ratio * 100.0:.2f}%",
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
        try:
            row = fetch_formal_overview(
                report_date=report_date,
                position_scope="asset",
                currency_basis=currency_basis,
            )
        except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
            row = None
        if row is None:
            pass
        else:
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


def _list_executive_aum_report_dates(
    balance_repo: object,
    *,
    currency_basis: str = "CNY",
) -> list[str]:
    list_formal_overview_report_dates = getattr(balance_repo, "list_formal_overview_report_dates", None)
    if callable(list_formal_overview_report_dates):
        try:
            dates = list(
                list_formal_overview_report_dates(
                    position_scope="asset",
                    currency_basis=currency_basis,
                )
            )
            if dates:
                return dates
        except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
            pass
    list_report_dates = getattr(balance_repo, "list_report_dates", None)
    if not callable(list_report_dates):
        return []
    try:
        return list(list_report_dates(currency_basis=currency_basis))
    except TypeError:
        return list(list_report_dates())


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


def _format_ratio_point_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous is None:
        return Numeric(raw=None, unit="bp", display="N/A", precision=2, sign_aware=True)
    current_ratio = _normalize_ratio_percent_input(current)
    previous_ratio = _normalize_ratio_percent_input(previous)
    change_ratio = current_ratio - previous_ratio
    sign = "+" if change_ratio >= 0 else ""
    return Numeric(
        raw=change_ratio * 10000.0,
        unit="bp",
        display=f"{sign}{change_ratio * 100.0:.2f}pp",
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


def _history_date_slice(
    report_dates: list[str],
    current_report_date: str | None,
    n: int,
) -> list[str] | None:
    if not report_dates:
        return None
    if current_report_date is None:
        return report_dates[:n]
    try:
        idx = report_dates.index(current_report_date)
    except ValueError:
        return None
    return report_dates[idx : idx + n]


def _fetch_aum_history(
    balance_repo: FormalZqtzBalanceMetricsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> list[float] | None:
    """逐日取 _fetch_executive_aum_row(...)['total_market_value_amount']，按时间正序返回最近 n 个。
    单日异常跳过；整体异常返回 None。"""
    try:
        slice_dates = _history_date_slice(report_dates, current_report_date, n)
        if not slice_dates:
            return None
        fetch_history = getattr(balance_repo, "fetch_formal_overview_history", None)
        if callable(fetch_history):
            try:
                rows_by_date = fetch_history(
                    report_dates=slice_dates,
                    position_scope="asset",
                    currency_basis="CNY",
                )
                values = [
                    float(row["total_market_value_amount"])
                    for d in slice_dates
                    if (row := rows_by_date.get(d)) is not None
                    and row.get("total_market_value_amount") is not None
                ]
                if values:
                    values.reverse()
                    return values
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                pass
        values: list[float] = []
        for d in slice_dates:
            try:
                row = _fetch_executive_aum_row(
                    balance_repo,
                    report_date=d,
                    currency_basis="CNY",
                )
                if row is None:
                    continue
                v = row.get("total_market_value_amount")
                if v is not None:
                    values.append(float(v))
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                continue
        if not values:
            return None
        values.reverse()
        return values
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        return None


def _fetch_aum_context(
    balance_repo: FormalZqtzBalanceMetricsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> tuple[dict[str, dict[str, object]], list[float] | None]:
    slice_dates = _history_date_slice(report_dates, current_report_date, n) or []
    fetch_dates = list(slice_dates)
    previous_report_date = _previous_report_date(report_dates, current_report_date)
    for d in (current_report_date, previous_report_date):
        if d is not None and d not in fetch_dates:
            fetch_dates.append(d)
    if not fetch_dates:
        return {}, None

    fetch_history = getattr(balance_repo, "fetch_formal_overview_history", None)
    if callable(fetch_history):
        try:
            rows_by_date = fetch_history(
                report_dates=fetch_dates,
                position_scope="asset",
                currency_basis="CNY",
            )
            if rows_by_date:
                values = [
                    float(row["total_market_value_amount"])
                    for d in slice_dates
                    if (row := rows_by_date.get(d)) is not None
                    and row.get("total_market_value_amount") is not None
                ]
                if values:
                    values.reverse()
                return rows_by_date, values or None
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    rows_by_date: dict[str, dict[str, object]] = {}
    for d in fetch_dates:
        try:
            row = _fetch_executive_aum_row(
                balance_repo,
                report_date=d,
                currency_basis="CNY",
            )
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            row = None
        if row is not None:
            rows_by_date[d] = row
    values = [
        float(row["total_market_value_amount"])
        for d in slice_dates
        if (row := rows_by_date.get(d)) is not None
        and row.get("total_market_value_amount") is not None
    ]
    if values:
        values.reverse()
    return rows_by_date, values or None


def _fetch_ytd_history(
    pnl_repo: PnlRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> list[float] | None:
    """逐日取 FI + nonstd bridge 年度累计损益。"""
    try:
        slice_dates = _history_date_slice(report_dates, current_report_date, n)
        if not slice_dates:
            return None
        sum_formal_history = getattr(pnl_repo, "sum_formal_total_pnl_through_report_dates", None)
        if callable(sum_formal_history):
            try:
                formal_by_date = sum_formal_history(slice_dates)
                sum_nonstd_history = getattr(
                    pnl_repo,
                    "sum_nonstd_bridge_total_pnl_through_report_dates",
                    None,
                )
                nonstd_by_date = (
                    sum_nonstd_history(slice_dates) if callable(sum_nonstd_history) else {}
                )
                values = [
                    float(formal_by_date[d] + nonstd_by_date.get(d, 0))
                    for d in slice_dates
                    if d in formal_by_date
                ]
                if values:
                    values.reverse()
                    return values
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                pass
        values: list[float] = []
        for d in slice_dates:
            try:
                v = _sum_business_ytd_pnl(pnl_repo, d)
                if v is not None:
                    values.append(float(v))
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                continue
        if not values:
            return None
        values.reverse()
        return values
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        return None


def _sum_business_ytd_pnl(pnl_repo: PnlRepository, report_date: str):
    formal = pnl_repo.sum_formal_total_pnl_through_report_date(report_date)
    nonstd_sum = getattr(pnl_repo, "sum_nonstd_bridge_total_pnl_through_report_date", None)
    if not callable(nonstd_sum):
        return formal
    return formal + nonstd_sum(report_date)


def _fetch_ytd_context(
    pnl_repo: PnlRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> tuple[dict[str, object], list[float] | None]:
    slice_dates = _history_date_slice(report_dates, current_report_date, n) or []
    fetch_dates = list(slice_dates)
    previous_report_date = _previous_report_date(report_dates, current_report_date)
    for d in (current_report_date, previous_report_date):
        if d is not None and d not in fetch_dates:
            fetch_dates.append(d)
    if not fetch_dates:
        return {}, None

    sum_formal_history = getattr(pnl_repo, "sum_formal_total_pnl_through_report_dates", None)
    if callable(sum_formal_history):
        try:
            formal_by_date = sum_formal_history(fetch_dates)
            sum_nonstd_history = getattr(
                pnl_repo,
                "sum_nonstd_bridge_total_pnl_through_report_dates",
                None,
            )
            nonstd_by_date = (
                sum_nonstd_history(fetch_dates) if callable(sum_nonstd_history) else {}
            )
            values_by_date = {
                d: formal_by_date[d] + nonstd_by_date.get(d, 0)
                for d in fetch_dates
                if d in formal_by_date
            }
            values = [float(values_by_date[d]) for d in slice_dates if d in values_by_date]
            if values:
                values.reverse()
            return values_by_date, values or None
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    values_by_date: dict[str, object] = {}
    for d in fetch_dates:
        try:
            values_by_date[d] = _sum_business_ytd_pnl(pnl_repo, d)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            continue
    values = [float(values_by_date[d]) for d in slice_dates if d in values_by_date]
    if values:
        values.reverse()
    return values_by_date, values or None


def _fetch_nim_history(
    liability_repo: LiabilityAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> list[float] | None:
    """逐日 fetch_zqtz_rows + fetch_tyw_rows → compute_liability_yield_metrics → kpi.nim。"""
    try:
        slice_dates = _history_date_slice(report_dates, current_report_date, n)
        if not slice_dates:
            return None
        fetch_zqtz_history = getattr(liability_repo, "fetch_zqtz_rows_for_dates", None)
        fetch_tyw_history = getattr(liability_repo, "fetch_tyw_rows_for_dates", None)
        if callable(fetch_zqtz_history) and callable(fetch_tyw_history):
            try:
                zqtz_rows_by_date = fetch_zqtz_history(slice_dates)
                tyw_rows_by_date = fetch_tyw_history(slice_dates)
                values: list[float] = []
                for d in slice_dates:
                    payload = compute_liability_yield_metrics(
                        d,
                        zqtz_rows_by_date.get(d, []),
                        tyw_rows_by_date.get(d, []),
                    )
                    kpi = payload.get("kpi") if isinstance(payload, dict) else None
                    v = kpi.get("nim") if isinstance(kpi, dict) else None
                    if v is not None:
                        values.append(float(v))
                if values:
                    values.reverse()
                    return values
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                pass
        values: list[float] = []
        for d in slice_dates:
            try:
                zqtz_rows = liability_repo.fetch_zqtz_rows(d)
                tyw_rows = liability_repo.fetch_tyw_rows(d)
                payload = compute_liability_yield_metrics(d, zqtz_rows, tyw_rows)
                kpi = payload.get("kpi") if isinstance(payload, dict) else None
                v = kpi.get("nim") if isinstance(kpi, dict) else None
                if v is not None:
                    values.append(float(v))
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                continue
        if not values:
            return None
        values.reverse()
        return values
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        return None


def _fetch_liability_rows_by_dates(
    liability_repo: LiabilityAnalyticsRepository,
    *,
    report_dates: list[str],
    batch_method_name: str,
    single_method_name: str,
) -> dict[str, list[dict[str, object]]]:
    if not report_dates:
        return {}
    fetch_many = getattr(liability_repo, batch_method_name, None)
    if callable(fetch_many):
        try:
            rows_by_date = fetch_many(report_dates)
            return {
                d: list(rows_by_date.get(d, []))
                for d in report_dates
                if isinstance(rows_by_date, dict)
            }
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    fetch_one = getattr(liability_repo, single_method_name)
    rows_by_date: dict[str, list[dict[str, object]]] = {}
    for d in report_dates:
        try:
            rows_by_date[d] = list(fetch_one(d))
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            rows_by_date[d] = []
    return rows_by_date


def _fetch_nim_context(
    liability_repo: LiabilityAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, list[dict[str, object]]],
    dict[str, list[dict[str, object]]],
    list[float] | None,
]:
    slice_dates = _history_date_slice(report_dates, current_report_date, n) or []
    fetch_dates = list(slice_dates)
    if current_report_date is not None and current_report_date not in fetch_dates:
        fetch_dates.insert(0, current_report_date)
    previous_report_date = _previous_report_date(report_dates, current_report_date)
    if previous_report_date is not None and previous_report_date not in fetch_dates:
        fetch_dates.append(previous_report_date)
    if not fetch_dates:
        return {}, {}, {}, None

    fetch_yield_rows = getattr(liability_repo, "fetch_yield_rows_for_dates", None)
    if callable(fetch_yield_rows):
        try:
            zqtz_rows_by_date, tyw_rows_by_date = fetch_yield_rows(fetch_dates)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            zqtz_rows_by_date, tyw_rows_by_date = {}, {}
    else:
        zqtz_rows_by_date, tyw_rows_by_date = {}, {}

    if not zqtz_rows_by_date and not tyw_rows_by_date:
        zqtz_rows_by_date = _fetch_liability_rows_by_dates(
            liability_repo,
            report_dates=fetch_dates,
            batch_method_name="fetch_zqtz_yield_rows_for_dates",
            single_method_name="fetch_zqtz_rows",
        )
        tyw_rows_by_date = _fetch_liability_rows_by_dates(
            liability_repo,
            report_dates=fetch_dates,
            batch_method_name="fetch_tyw_yield_rows_for_dates",
            single_method_name="fetch_tyw_rows",
        )

    payloads_by_date: dict[str, dict[str, object]] = {}
    for d in fetch_dates:
        try:
            payloads_by_date[d] = compute_liability_yield_metrics(
                d,
                zqtz_rows_by_date.get(d, []),
                tyw_rows_by_date.get(d, []),
            )
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            continue

    history_values: list[float] = []
    for d in slice_dates:
        payload = payloads_by_date.get(d)
        kpi = payload.get("kpi") if isinstance(payload, dict) else None
        v = kpi.get("nim") if isinstance(kpi, dict) else None
        if v is not None:
            history_values.append(float(v))
    history = history_values if history_values else None
    if history is not None:
        history.reverse()

    return payloads_by_date, zqtz_rows_by_date, tyw_rows_by_date, history


def _fetch_dv01_history(
    bond_repo: BondAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> list[float] | None:
    """逐日 fetch_risk_overview_snapshot(date)['portfolio_dv01']。"""
    try:
        slice_dates = _history_date_slice(report_dates, current_report_date, n)
        if not slice_dates:
            return None
        fetch_snapshots = getattr(bond_repo, "fetch_risk_overview_snapshots", None)
        if callable(fetch_snapshots):
            try:
                snapshots_by_date = fetch_snapshots(report_dates=slice_dates)
                values = [
                    float(snapshot["portfolio_dv01"])
                    for d in slice_dates
                    if (snapshot := snapshots_by_date.get(d)) is not None
                    and snapshot.get("portfolio_dv01") is not None
                ]
                if values:
                    values.reverse()
                    return values
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                pass
        values: list[float] = []
        for d in slice_dates:
            try:
                snapshot = bond_repo.fetch_risk_overview_snapshot(report_date=d)
                if snapshot is None:
                    continue
                v = snapshot.get("portfolio_dv01")
                if v is not None:
                    values.append(float(v))
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                continue
        if not values:
            return None
        values.reverse()
        return values
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        return None


def _fetch_dv01_context(
    bond_repo: BondAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> tuple[dict[str, dict[str, object]], list[float] | None]:
    slice_dates = _history_date_slice(report_dates, current_report_date, n) or []
    fetch_dates = list(slice_dates)
    previous_report_date = _previous_report_date(report_dates, current_report_date)
    for d in (current_report_date, previous_report_date):
        if d is not None and d not in fetch_dates:
            fetch_dates.append(d)
    if not fetch_dates:
        return {}, None

    fetch_snapshots = getattr(bond_repo, "fetch_risk_overview_snapshots", None)
    if callable(fetch_snapshots):
        try:
            snapshots_by_date = fetch_snapshots(report_dates=fetch_dates)
            if snapshots_by_date:
                values = [
                    float(snapshot["portfolio_dv01"])
                    for d in slice_dates
                    if (snapshot := snapshots_by_date.get(d)) is not None
                    and snapshot.get("portfolio_dv01") is not None
                ]
                if values:
                    values.reverse()
                return snapshots_by_date, values or None
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    snapshots_by_date: dict[str, dict[str, object]] = {}
    for d in fetch_dates:
        try:
            snapshot = bond_repo.fetch_risk_overview_snapshot(report_date=d)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            snapshot = None
        if snapshot is not None:
            snapshots_by_date[d] = snapshot
    values = [
        float(snapshot["portfolio_dv01"])
        for d in slice_dates
        if (snapshot := snapshots_by_date.get(d)) is not None
        and snapshot.get("portfolio_dv01") is not None
    ]
    if values:
        values.reverse()
    return snapshots_by_date, values or None


def executive_overview(
    report_date: str | None = None,
    *,
    date_context: dict[str, list[str]] | None = None,
) -> dict[str, object]:
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
    aum_history: list[float] | None = None
    ytd_history: list[float] | None = None
    nim_history: list[float] | None = None
    dv01_history: list[float] | None = None
    row: dict[str, object] | None = None

    def load_aum_state() -> dict[str, object]:
        state: dict[str, object] = {
            "current_report_date": None,
            "raw": None,
            "delta": Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True),
            "history": None,
            "row": None,
            "source_versions": [],
            "rule_versions": [],
        }
        try:
            balance_repo = FormalZqtzBalanceMetricsRepository(str(settings.duckdb_path))
            balance_report_dates = (
                _list_executive_aum_report_dates(balance_repo, currency_basis="CNY")
                if date_context is None
                else list(date_context.get("balance", []))
            )
            current_report_date = normalized_report_date or (
                balance_report_dates[0] if balance_report_dates else None
            )
            state["current_report_date"] = current_report_date
            aum_rows_by_date, history = _fetch_aum_context(
                balance_repo,
                report_dates=balance_report_dates,
                current_report_date=current_report_date,
            )
            state["history"] = history
            current_row = aum_rows_by_date.get(current_report_date) if current_report_date else None
            state["row"] = current_row
            if current_row is not None:
                raw = float(current_row["total_market_value_amount"])
                state["raw"] = raw
                state["source_versions"] = [current_row.get("source_version")]
                state["rule_versions"] = [current_row.get("rule_version")]
                previous_report_date = _previous_report_date(
                    balance_report_dates,
                    current_report_date,
                )
                if previous_report_date is not None:
                    previous_row = aum_rows_by_date.get(previous_report_date)
                    if previous_row is not None:
                        state["source_versions"] = [
                            *list(state["source_versions"]),
                            previous_row.get("source_version"),
                        ]
                        state["rule_versions"] = [
                            *list(state["rule_versions"]),
                            previous_row.get("rule_version"),
                        ]
                        state["delta"] = _format_percent_change(
                            raw,
                            float(previous_row["total_market_value_amount"]),
                        )
        except (RuntimeError, OSError, TypeError, ValueError):
            state["raw"] = None
        return state

    def load_ytd_state() -> dict[str, object]:
        state: dict[str, object] = {
            "current_report_date": None,
            "raw": None,
            "delta": Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True),
            "history": None,
            "source_versions": [],
            "rule_versions": [],
        }
        try:
            pnl_repo = PnlRepository(str(settings.duckdb_path))
            pnl_report_dates = (
                list(
                    getattr(
                        pnl_repo,
                        "list_formal_fi_report_dates",
                        getattr(pnl_repo, "list_union_report_dates", lambda: []),
                    )()
                )
                if date_context is None
                else list(date_context.get("pnl", []))
            )
            current_report_date = normalized_report_date or (
                pnl_report_dates[0] if pnl_report_dates else None
            )
            state["current_report_date"] = current_report_date
            ytd_values_by_date, history = _fetch_ytd_context(
                pnl_repo,
                report_dates=pnl_report_dates,
                current_report_date=current_report_date,
            )
            state["history"] = history
            source_versions: list[object] = []
            rule_versions: list[object] = []
            raw: float | None = None
            if current_report_date is not None:
                if current_report_date in ytd_values_by_date:
                    raw = float(ytd_values_by_date[current_report_date])
                    state["raw"] = raw
                if governance_dir:
                    current_lineage = resolve_completed_formal_build_lineage(
                        governance_dir=governance_dir,
                        cache_key=PNL_CACHE_KEY,
                        job_name=PNL_JOB_NAME,
                        report_date=current_report_date,
                    )
                    if current_lineage is not None:
                        source_versions.append(current_lineage.get("source_version"))
                        rule_versions.append(current_lineage.get("rule_version"))
            previous_report_date = _previous_report_date(
                pnl_report_dates,
                current_report_date,
            )
            if previous_report_date is not None:
                if governance_dir:
                    previous_lineage = resolve_completed_formal_build_lineage(
                        governance_dir=governance_dir,
                        cache_key=PNL_CACHE_KEY,
                        job_name=PNL_JOB_NAME,
                        report_date=previous_report_date,
                    )
                    if previous_lineage is not None:
                        source_versions.append(previous_lineage.get("source_version"))
                        rule_versions.append(previous_lineage.get("rule_version"))
                if previous_report_date in ytd_values_by_date:
                    state["delta"] = _format_percent_change(
                        raw,
                        float(ytd_values_by_date[previous_report_date]),
                    )
            state["source_versions"] = source_versions
            state["rule_versions"] = rule_versions
        except (RuntimeError, OSError, TypeError, ValueError):
            state["raw"] = None
        return state

    def load_nim_state() -> dict[str, object]:
        state: dict[str, object] = {
            "current_report_date": None,
            "raw": None,
            "delta": Numeric(raw=None, unit="bp", display="N/A", precision=2, sign_aware=True),
            "history": None,
            "source_versions": [],
            "rule_versions": [],
        }
        try:
            liability_repo = LiabilityAnalyticsRepository(str(settings.duckdb_path))
            liability_report_dates = (
                list(getattr(liability_repo, "list_report_dates", lambda: [])())
                if date_context is None
                else list(date_context.get("liability", []))
            )
            current_report_date = normalized_report_date or (
                liability_report_dates[0]
                if liability_report_dates
                else liability_repo.resolve_latest_report_date()
            )
            state["current_report_date"] = current_report_date
            if current_report_date:
                nim_payloads_by_date, zqtz_rows_by_date, tyw_rows_by_date, history = _fetch_nim_context(
                    liability_repo,
                    report_dates=liability_report_dates,
                    current_report_date=current_report_date,
                )
                state["history"] = history
                zqtz_rows = zqtz_rows_by_date.get(current_report_date, [])
                tyw_rows = tyw_rows_by_date.get(current_report_date, [])
                source_versions: list[object] = [
                    *_lineage_tokens_from_rows(zqtz_rows, "source_version"),
                    *_lineage_tokens_from_rows(tyw_rows, "source_version"),
                ]
                rule_versions: list[object] = [
                    *_lineage_tokens_from_rows(zqtz_rows, "rule_version"),
                    *_lineage_tokens_from_rows(tyw_rows, "rule_version"),
                ]
                payload = nim_payloads_by_date.get(current_report_date, {})
                nim_value = payload.get("kpi", {}).get("nim")
                if nim_value is not None:
                    raw = float(nim_value)
                    state["raw"] = raw
                    previous_report_date = _previous_report_date(
                        liability_report_dates,
                        current_report_date,
                    )
                    if previous_report_date is not None:
                        previous_zqtz_rows = zqtz_rows_by_date.get(previous_report_date, [])
                        previous_tyw_rows = tyw_rows_by_date.get(previous_report_date, [])
                        source_versions.extend(_lineage_tokens_from_rows(previous_zqtz_rows, "source_version"))
                        source_versions.extend(_lineage_tokens_from_rows(previous_tyw_rows, "source_version"))
                        rule_versions.extend(_lineage_tokens_from_rows(previous_zqtz_rows, "rule_version"))
                        rule_versions.extend(_lineage_tokens_from_rows(previous_tyw_rows, "rule_version"))
                        previous_payload = nim_payloads_by_date.get(previous_report_date, {})
                        state["delta"] = _format_ratio_point_change(
                            raw,
                            previous_payload.get("kpi", {}).get("nim"),
                        )
                state["source_versions"] = source_versions
                state["rule_versions"] = rule_versions
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            state["raw"] = None
        return state

    def load_dv01_state() -> dict[str, object]:
        state: dict[str, object] = {
            "current_report_date": None,
            "raw": None,
            "delta": Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True),
            "history": None,
            "source_versions": [],
            "rule_versions": [],
        }
        try:
            bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
            bond_report_dates = (
                list(getattr(bond_repo, "list_report_dates", lambda: [])())
                if date_context is None
                else list(date_context.get("bond", []))
            )
            current_report_date = normalized_report_date or (
                bond_report_dates[0] if bond_report_dates else None
            )
            state["current_report_date"] = current_report_date
            snapshots_by_date, history = _fetch_dv01_context(
                bond_repo,
                report_dates=bond_report_dates,
                current_report_date=current_report_date,
            )
            state["history"] = history
            snapshot = snapshots_by_date.get(current_report_date) if current_report_date else None
            source_versions: list[object] = []
            rule_versions: list[object] = []
            if snapshot is not None and snapshot.get("portfolio_dv01") is not None:
                raw = float(snapshot["portfolio_dv01"])
                state["raw"] = raw
                if governance_dir:
                    current_lineage = load_latest_bond_analytics_lineage(
                        governance_dir=governance_dir,
                        report_date=current_report_date,
                    )
                    if current_lineage is not None:
                        source_versions.append(current_lineage.get("source_version"))
                        rule_versions.append(current_lineage.get("rule_version"))
                previous_report_date = _previous_report_date(
                    bond_report_dates,
                    current_report_date,
                )
                if previous_report_date is not None:
                    previous_snapshot = snapshots_by_date.get(previous_report_date)
                    if previous_snapshot is not None and previous_snapshot.get("portfolio_dv01") is not None:
                        if governance_dir:
                            previous_lineage = load_latest_bond_analytics_lineage(
                                governance_dir=governance_dir,
                                report_date=previous_report_date,
                            )
                            if previous_lineage is not None:
                                source_versions.append(previous_lineage.get("source_version"))
                                rule_versions.append(previous_lineage.get("rule_version"))
                        state["delta"] = _format_percent_change(
                            raw,
                            float(previous_snapshot["portfolio_dv01"]),
                        )
            state["source_versions"] = source_versions
            state["rule_versions"] = rule_versions
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            state["raw"] = None
        return state

    domain_loaders = {
        "aum": load_aum_state,
        "ytd": load_ytd_state,
        "nim": load_nim_state,
        "dv01": load_dv01_state,
    }
    if date_context is None:
        domain_states = {name: loader() for name, loader in domain_loaders.items()}
    else:
        with ThreadPoolExecutor(max_workers=len(domain_loaders)) as executor:
            futures = {name: executor.submit(loader) for name, loader in domain_loaders.items()}
            domain_states = {name: future.result() for name, future in futures.items()}

    aum_state = domain_states["aum"]
    current_balance_report_date = aum_state.get("current_report_date")  # type: ignore[assignment]
    aum_raw = aum_state.get("raw")  # type: ignore[assignment]
    aum_delta = aum_state.get("delta")  # type: ignore[assignment]
    aum_history = aum_state.get("history")  # type: ignore[assignment]
    row = aum_state.get("row") if isinstance(aum_state.get("row"), dict) else None
    overview_source_versions.extend(list(aum_state.get("source_versions", [])))  # type: ignore[arg-type]
    overview_rule_versions.extend(list(aum_state.get("rule_versions", [])))  # type: ignore[arg-type]

    ytd_state = domain_states["ytd"]
    current_pnl_report_date = ytd_state.get("current_report_date")  # type: ignore[assignment]
    ytd_raw = ytd_state.get("raw")  # type: ignore[assignment]
    ytd_delta = ytd_state.get("delta")  # type: ignore[assignment]
    ytd_history = ytd_state.get("history")  # type: ignore[assignment]
    overview_source_versions.extend(list(ytd_state.get("source_versions", [])))  # type: ignore[arg-type]
    overview_rule_versions.extend(list(ytd_state.get("rule_versions", [])))  # type: ignore[arg-type]

    nim_state = domain_states["nim"]
    liability_report_date = nim_state.get("current_report_date")  # type: ignore[assignment]
    nim_raw = nim_state.get("raw")  # type: ignore[assignment]
    nim_delta = nim_state.get("delta")  # type: ignore[assignment]
    nim_history = nim_state.get("history")  # type: ignore[assignment]
    overview_source_versions.extend(list(nim_state.get("source_versions", [])))  # type: ignore[arg-type]
    overview_rule_versions.extend(list(nim_state.get("rule_versions", [])))  # type: ignore[arg-type]

    dv01_state = domain_states["dv01"]
    current_bond_report_date = dv01_state.get("current_report_date")  # type: ignore[assignment]
    dv01_raw = dv01_state.get("raw")  # type: ignore[assignment]
    dv01_delta = dv01_state.get("delta")  # type: ignore[assignment]
    dv01_history = dv01_state.get("history")  # type: ignore[assignment]
    overview_source_versions.extend(list(dv01_state.get("source_versions", [])))  # type: ignore[arg-type]
    overview_rule_versions.extend(list(dv01_state.get("rule_versions", [])))  # type: ignore[arg-type]

    metrics: list[ExecutiveMetric] = []
    if aum_raw is not None:
        aum_scope = str(row.get("_metric_scope") or "") if row is not None else ""
        aum_label = "总资产规模" if aum_scope == "combined_formal_balance" else "债券资产规模（zqtz）"
        aum_caliber_label = "本币资产口径" if aum_scope == "combined_formal_balance" else "债券资产口径"
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
                caliber_label=aum_caliber_label,
                value=_fmt_yi_amount(aum_raw, signed=False),
                delta=aum_delta,
                tone="positive",
                detail=aum_detail,
                history=aum_history,
            )
        )
    if ytd_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="yield",
                label="年度损益（不扣FTP）",
                caliber_label="FI + 非标桥接",
                value=_fmt_yi_amount(ytd_raw, signed=True),
                delta=ytd_delta,
                tone="positive",
                detail=(
                    "来自 fact_formal_pnl_fi + fact_nonstd_pnl_bridge "
                    f"截至 {normalized_report_date} 的年度累计 total_pnl，不扣减 FTP。"
                    if normalized_report_date is not None
                    else (
                        "来自 fact_formal_pnl_fi + fact_nonstd_pnl_bridge "
                        f"截至 {current_pnl_report_date} 的年度累计 total_pnl，不扣减 FTP。"
                    )
                ),
                history=ytd_history,
            )
        )
    if nim_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="nim",
                label="净息差",
                value=_fmt_signed_ratio_percent(nim_raw),
                delta=nim_delta,
                tone="positive" if nim_raw >= 0 else "negative",
                detail=(
                    f"来自受治理负债分析收益指标，在 {normalized_report_date} 的 NIM 读面。"
                    if normalized_report_date is not None
                    else f"来自受治理负债分析收益指标，在 {liability_report_date} 的 NIM 读面。"
                ),
                history=nim_history,
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
                    f"来自 bond analytics 风险快照，在 {normalized_report_date} 的全量组合 DV01；含 AC/OCI/TPL，拆分见风险全景。"
                    if normalized_report_date is not None
                    else f"来自 bond analytics 风险快照，在 {current_bond_report_date} 的全量组合 DV01；含 AC/OCI/TPL，拆分见风险全景。"
                ),
                history=dv01_history,
            )
        )
    kpi_dsn = str(
        getattr(settings, "governance_sql_dsn", "")
        or getattr(settings, "postgres_dsn", "")
    )
    kpi_gate = resolve_kpi_authority_gate(
        dsn=kpi_dsn,
        year=(
            _safe_report_year(current_pnl_report_date)
            if current_pnl_report_date
            else (
                _safe_report_year(normalized_report_date)
                if normalized_report_date is not None
                else None
            )
        ),
    )
    if kpi_gate["status"] == "available":
        try:
            metrics.extend(
                ExecutiveMetric.model_validate(item)
                for item in resolve_executive_kpi_metrics(
                    dsn=kpi_dsn,
                    report_date=current_pnl_report_date or normalized_report_date,
                )
            )
        except (RuntimeError, ValueError, TypeError, KeyError):
            kpi_gate = {
                "status": "blocked",
                "reason": "metrics-resolution-error",
                "owner_count": 0,
                "year": kpi_gate.get("year"),
            }

    payload = OverviewPayload(title="经营总览", metrics=metrics)
    has_missing_governed_metrics = (
        aum_raw is None
        or ytd_raw is None
        or nim_raw is None
        or dv01_raw is None
    )
    effective_balance_report_date = current_balance_report_date if aum_raw is not None else None
    effective_pnl_report_date = current_pnl_report_date if ytd_raw is not None else None
    effective_liability_report_date = liability_report_date if nim_raw is not None else None
    effective_risk_report_date = current_bond_report_date if dv01_raw is not None else None
    overview_report_date = _single_effective_report_date(
        effective_balance_report_date,
        effective_pnl_report_date,
        effective_liability_report_date,
        effective_risk_report_date,
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
                "balance": effective_balance_report_date,
                "pnl": effective_pnl_report_date,
                "liability": effective_liability_report_date,
                "risk": effective_risk_report_date,
            },
            "kpi_gate": kpi_gate,
        },
        requested_report_date=normalized_report_date,
        resolved_report_date=overview_report_date,
        as_of_date=overview_report_date,
        date_basis="multi_domain_snapshot",
        fallback_date=None,
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
                for split_field, split_id, split_label in (
                    ("ac_dv01", "dv01_ac", "AC DV01"),
                    ("oci_dv01", "dv01_oci", "OCI DV01"),
                    ("tpl_dv01", "dv01_tpl", "TPL DV01"),
                    ("other_dv01", "dv01_other", "未分类 DV01"),
                ):
                    split_value = snapshot.get(split_field)
                    if split_value is None:
                        continue
                    split_raw = float(split_value)
                    if split_field == "other_dv01" and split_raw == 0:
                        continue
                    split_status = "warning" if split_field == "other_dv01" else "stable"
                    payload.signals.append(
                        RiskSignal(
                            id=split_id,
                            label=split_label,
                            value=Numeric(
                                raw=split_raw,
                                unit="dv01",
                                display=f"{split_raw:,.0f}",
                                precision=0,
                                sign_aware=False,
                            ),
                            status=split_status,
                            detail=f"{asof_label}; management DV01 accounting split included in total portfolio DV01.",
                        )
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


_HOME_SNAPSHOT_CALIBERS = ("balance_sheet", "pnl")
"""Business calibers for the home snapshot.

- ``balance_sheet``: AUM + NIM + DV01 — all from the same T+1 daily pipeline.
  Available dates = intersection(balance, liability, bond).
- ``pnl``: YTD P&L — independent formal build cycle.
- Market/macro data is excluded; it is real-time and not bound to report date.
"""


def _list_domain_dates() -> dict[str, set[str]]:
    """Return the set of available report_dates per caliber.

    ``balance_sheet`` = intersection of balance, liability, bond dates.
    ``pnl`` = formal fixed-income P&L dates.
    """
    settings = get_settings()

    balance_dates: set[str] = set()
    liability_dates: set[str] = set()
    bond_dates: set[str] = set()
    pnl_dates: set[str] = set()

    try:
        balance_repo = FormalZqtzBalanceMetricsRepository(str(settings.duckdb_path))
        balance_dates = set(_list_executive_aum_report_dates(balance_repo, currency_basis="CNY"))
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        pass

    try:
        pnl_repo = PnlRepository(str(settings.duckdb_path))
        pnl_dates = set(pnl_repo.list_formal_fi_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        pass

    try:
        liability_repo = LiabilityAnalyticsRepository(str(settings.duckdb_path))
        liability_dates = set(liability_repo.list_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        pass

    try:
        bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
        bond_dates = set(bond_repo.list_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        pass

    # balance_sheet caliber: a date is available only when ALL THREE
    # sub-sources (balance, liability, bond) have data for that date.
    bs_components = [balance_dates, liability_dates, bond_dates]
    balance_sheet_dates = (
        set.intersection(*bs_components) if all(bs_components) else set()
    )

    return {
        "balance_sheet": balance_sheet_dates,
        "pnl": pnl_dates,
    }


def _list_domain_date_context() -> dict[str, list[str]]:
    settings = get_settings()
    empty_context: dict[str, list[str]] = {
        "balance": [],
        "pnl": [],
        "liability": [],
        "bond": [],
    }
    try:
        conn = duckdb.connect(str(settings.duckdb_path), read_only=True)
    except (RuntimeError, OSError, TypeError, ValueError, duckdb.Error):
        return empty_context
    try:
        def table_exists(table_name: str) -> bool:
            row = conn.execute(
                """
                select 1
                from information_schema.tables
                where table_name = ?
                limit 1
                """,
                [table_name],
            ).fetchone()
            return row is not None

        context = {key: list(value) for key, value in empty_context.items()}
        if table_exists("fact_formal_zqtz_balance_daily"):
            balance_parts = [
                """
                select distinct cast(report_date as varchar) as d
                from fact_formal_zqtz_balance_daily
                where position_scope = 'asset'
                  and currency_basis = 'CNY'
                """
            ]
            if table_exists("fact_formal_tyw_balance_daily"):
                balance_parts.append(
                    """
                    select distinct cast(report_date as varchar) as d
                    from fact_formal_tyw_balance_daily
                    where position_scope = 'asset'
                      and currency_basis = 'CNY'
                    """
                )
            rows = conn.execute(
                f"""
                select distinct d
                from ({" union ".join(balance_parts)}) t
                order by d desc
                """
            ).fetchall()
            context["balance"] = [str(row[0]) for row in rows if row[0] is not None]

        if table_exists("fact_formal_pnl_fi"):
            rows = conn.execute(
                """
                select distinct cast(report_date as varchar) as d
                from fact_formal_pnl_fi
                order by d desc
                """
            ).fetchall()
            context["pnl"] = [str(row[0]) for row in rows if row[0] is not None]

        liability_parts: list[str] = []
        if table_exists("zqtz_bond_daily_snapshot"):
            liability_parts.append(
                "select distinct cast(report_date as varchar) as d from zqtz_bond_daily_snapshot"
            )
        if table_exists("tyw_interbank_daily_snapshot"):
            liability_parts.append(
                "select distinct cast(report_date as varchar) as d from tyw_interbank_daily_snapshot"
            )
        if liability_parts:
            rows = conn.execute(
                f"""
                select distinct d
                from ({" union ".join(liability_parts)}) t
                order by d desc
                """
            ).fetchall()
            context["liability"] = [str(row[0]) for row in rows if row[0] is not None]

        if table_exists("fact_formal_bond_analytics_daily"):
            rows = conn.execute(
                """
                select distinct cast(report_date as varchar) as d
                from fact_formal_bond_analytics_daily
                order by d desc
                """
            ).fetchall()
            context["bond"] = [str(row[0]) for row in rows if row[0] is not None]
        return context
    except (RuntimeError, OSError, TypeError, ValueError, duckdb.Error):
        return empty_context
    finally:
        conn.close()


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


def _build_product_category_ytd_headline(report_date: str) -> ProductCategoryYtdHeadlinePayload | None:
    """与 /product-category-pnl「汇总视图」（ytd）一致：grand_total + intermediate_business_income。"""
    settings = get_settings()
    duck_path = str(getattr(settings, "duckdb_path", "") or "").strip()
    if not duck_path:
        return None
    try:
        pc_payload = resolve_product_category_ytd_payload_for_home_snapshot(
            duck_path,
            str(settings.governance_path),
            report_date,
            float(settings.ftp_rate_pct),
        )
    except Exception:
        return None

    if pc_payload is None:
        return None

    summary_val = float(pc_payload.grand_total.business_net_income)
    summary_pnl = _fmt_yi_amount(summary_val, signed=True)
    summary_detail = (
        "与产品分类损益「汇总视图」（view=ytd）页脚「全部市场科目 + 投资收益合计」口径一致："
        f"grand_total.business_net_income；report_date={report_date}；"
        "优先读 product_category_pnl_formal_read_model（view=ytd）；"
        "若缺行则自 product_category_pnl_canonical_fact 重算（与刷数任务同口径）。"
    )
    operating = summary_pnl
    operating_detail = summary_detail

    intermediate_row = next(
        (r for r in pc_payload.rows if r.category_id == "intermediate_business_income"),
        None,
    )
    if intermediate_row is None:
        int_numeric = _fmt_yi_amount(None, signed=True)
        int_detail = (
            "未找到 intermediate_business_income 分类行（product_category ytd, "
            f"report_date={report_date}）。"
        )
    else:
        int_numeric = _fmt_yi_amount(float(intermediate_row.business_net_income), signed=True)
        int_detail = (
            "与产品分类损益「中间业务收入」（intermediate_business_income）ytd 行一致；"
            f"report_date={report_date}。"
        )

    return ProductCategoryYtdHeadlinePayload(
        view="ytd",
        summary_pnl=summary_pnl,
        summary_pnl_detail=summary_detail,
        operating_income=operating,
        operating_income_detail=operating_detail,
        intermediate_business_income=int_numeric,
        intermediate_business_income_detail=int_detail,
    )


def _build_product_category_monthly_headline(report_date: str) -> ProductCategoryMonthlyHeadlinePayload | None:
    """与 /product-category-pnl 月度视图页脚 grand_total.business_net_income 对齐。"""
    settings = get_settings()
    duck_path = str(getattr(settings, "duckdb_path", "") or "").strip()
    if not duck_path:
        return None
    try:
        envelope = product_category_pnl_envelope(
            duck_path,
            report_date=report_date,
            view="monthly",
        )
        result_dict = envelope.get("result")
        if not isinstance(result_dict, dict):
            return None
        from backend.app.schemas.product_category_pnl import ProductCategoryPnlPayload

        pc_payload = ProductCategoryPnlPayload.model_validate(result_dict)
    except Exception:
        return None

    monthly_value = float(pc_payload.grand_total.business_net_income)
    monthly_detail = (
        "与产品分类损益「月度视图」（view=monthly）页脚"
        f"「全部市场科目 + 投资收益合计」一致：grand_total.business_net_income；report_date={report_date}。"
    )
    return ProductCategoryMonthlyHeadlinePayload(
        view="monthly",
        monthly_income=_fmt_yi_amount(monthly_value, signed=True),
        monthly_income_detail=monthly_detail,
    )


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


# ---------------------------------------------------------------------------
# Home snapshot 内存 TTL 缓存
# ---------------------------------------------------------------------------
# 单进程进程内缓存，按 (report_date, allow_partial) 维度独立存储；
# TTL 过期或显式 invalidate 才会重新构造（一次约 80+ 次 DuckDB 查询 + 派生）。
# 设计权衡：
#   - 驾驶舱用户量小（管理层），日常 TTL 5 分钟足够；
#   - 不引入 Redis/外部存储，零依赖增加；
#   - 写场景（治理刷库、补数任务）应显式调用 invalidate_home_snapshot_cache();
#   - 多 worker 部署下每个 worker 独立缓存，可接受（TTL 短）。

_HOME_SNAPSHOT_CACHE_TTL_SECONDS: float = 300.0
_HomeSnapshotCacheKey = tuple[str | None, bool, str, int | None]
_HOME_SNAPSHOT_CACHE: InMemoryTTLCache[_HomeSnapshotCacheKey, dict[str, object]] = get_runtime_cache(
    "executive.home_snapshot",
    ttl_seconds=_HOME_SNAPSHOT_CACHE_TTL_SECONDS,
    clock=lambda: time.monotonic(),
)


def _duckdb_version_token() -> tuple[str, int | None]:
    duckdb_path = str(get_settings().duckdb_path)
    try:
        return duckdb_path, Path(duckdb_path).stat().st_mtime_ns
    except OSError:
        return duckdb_path, None


def _home_snapshot_cache_key(
    *,
    report_date: str | None,
    allow_partial: bool,
) -> _HomeSnapshotCacheKey:
    duckdb_path, duckdb_mtime_ns = _duckdb_version_token()
    return (report_date, allow_partial, duckdb_path, duckdb_mtime_ns)


def invalidate_home_snapshot_cache() -> None:
    """显式清空 home_snapshot 缓存。

    适用场景：
      - 治理流程完成补数 / 刷库后；
      - 后台任务希望强制下次请求拿到新数据；
      - 测试隔离。
    """
    _HOME_SNAPSHOT_CACHE.clear()


def home_snapshot_envelope(
    *,
    report_date: str | None = None,
    allow_partial: bool = False,
) -> dict[str, object]:
    """home snapshot envelope 入口（带 TTL 缓存）。

    缓存命中：返回上次构造 envelope 的防御副本，避免调用方 mutation 污染缓存。
    缓存未命中或过期：执行 ``_compute_home_snapshot_envelope`` 并写回缓存。
    """
    total_t0 = time.perf_counter()
    normalized_report_date = _normalize_report_date(report_date)
    cache_key = _home_snapshot_cache_key(
        report_date=normalized_report_date,
        allow_partial=allow_partial,
    )
    t0 = time.perf_counter()
    cache_state = "hit" if _HOME_SNAPSHOT_CACHE.get(cache_key)[0] else "miss"
    logger.info(
        "home_snapshot perf: step=cache_lookup ms=%d extra=cache=%s report_date=%s allow_partial=%s",
        int((time.perf_counter() - t0) * 1000),
        cache_state,
        normalized_report_date,
        allow_partial,
    )

    envelope = _HOME_SNAPSHOT_CACHE.get_or_set(
        cache_key,
        lambda: _compute_home_snapshot_envelope(
            report_date=normalized_report_date,
            allow_partial=allow_partial,
        ),
    )

    logger.info(
        "home_snapshot perf: step=total ms=%d extra=cache=%s report_date=%s allow_partial=%s",
        int((time.perf_counter() - total_t0) * 1000),
        cache_state,
        normalized_report_date,
        allow_partial,
    )
    return deepcopy(envelope)


def warm_home_snapshot_cache_if_configured(settings: object) -> bool:
    if not bool(getattr(settings, "home_snapshot_prewarm_enabled", False)):
        return False
    thread = threading.Thread(
        target=_warm_home_snapshot_cache_quietly,
        kwargs={"report_date": None, "allow_partial": False},
        daemon=True,
        name="moss-home-snapshot-warmup",
    )
    thread.start()
    return True


def _warm_home_snapshot_cache_quietly(
    *,
    report_date: str | None,
    allow_partial: bool,
) -> None:
    try:
        home_snapshot_envelope(report_date=report_date, allow_partial=allow_partial)
    except Exception:
        _logger.exception("home_snapshot_prewarm_failed")


def _compute_home_snapshot_envelope(
    *,
    report_date: str | None = None,
    allow_partial: bool = False,
) -> dict[str, object]:
    """Build the authoritative home snapshot envelope.

    See ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 4.
    """
    normalized = _normalize_report_date(report_date)
    date_context = _list_domain_date_context()
    domain_dates = _domain_dates_from_context(date_context)

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
                "domains_missing": list(_HOME_SNAPSHOT_CALIBERS),
            },
        )

    overview_env = executive_overview(report_date=target_date, date_context=date_context)
    attribution_env = executive_pnl_attribution(report_date=target_date)
    overview_result = OverviewPayload.model_validate(overview_env["result"])
    attribution_result = PnlAttributionPayload.model_validate(attribution_env["result"])
    attention_count = len(domains_missing)
    partial_note = (
        "部分业务域不可用: " + ", ".join(domains_missing) if domains_missing else None
    )
    verdict = executive_verdict(
        overview=overview_result,
        attention_count=attention_count,
        partial_note=partial_note,
        client_mode="real",
    )
    product_category_ytd = _build_product_category_ytd_headline(target_date)
    product_category_monthly = _build_product_category_monthly_headline(target_date)
    payload = HomeSnapshotPayload(
        report_date=target_date,
        mode="partial" if allow_partial else "strict",
        source_surface="executive_analytical",
        overview=overview_result,
        attribution=attribution_result,
        domains_missing=domains_missing,
        domains_effective_date=effective,
        verdict=verdict,
        product_category_ytd=product_category_ytd,
        product_category_monthly=product_category_monthly,
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
