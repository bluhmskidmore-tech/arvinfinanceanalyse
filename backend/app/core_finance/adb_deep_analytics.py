"""
Pure calculation logic for ADB deep insights（规模归因 / NIM 量价 / 波动异常 / 结构集中度 / 结论）。

No DB access and no service imports — inputs are already-loaded enriched rate frames (the same
frames `adb_analysis_service._split_rate_frames` feeds to `build_rate_map`) or plain mappings.

Formulas are frozen by `docs/plans/2026-08-13-average-balance-deep-analysis-prd.md` §4; the emitted
structure is frozen by §5. Amounts stay in 元 and unrounded so the closure identities
(Σ 分类 delta = 总 delta、rate+mix+residual = 总效应、nim_delta = 资产 − 负债) survive serialization.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any

import pandas as pd

# --- 冻结阈值（PRD §4.4 / §4.6）------------------------------------------------------------
ANOMALY_ZSCORE_THRESHOLD = 2.5
ANOMALY_SEVERE_ZSCORE = 4.0
ANOMALY_MAX_ITEMS = 10
ANOMALY_MIN_OBSERVATIONS = 5
MONTH_END_MIN_OBSERVATIONS = 5
MONTH_END_UPLIFT_THRESHOLD_PCT = 1.0
CONCENTRATION_MOVER_LIMIT = 8
CONCENTRATION_HHI_RISE_THRESHOLD = 0.02
SCALE_MOVE_TRIGGER_PCT = 3.0
SCALE_MOVE_NOTICE_PCT = 5.0
NIM_COMPRESSION_BP = -10.0
NIM_COMPRESSION_WARNING_BP = -20.0
NIM_EXPANSION_BP = 10.0
RATE_COVERAGE_LOW = 0.9

_YI = 100_000_000.0
_OTHER_CATEGORY = "其它"


def _clean_category(value: object) -> str:
    if value is None:
        return _OTHER_CATEGORY
    text = str(value).strip()
    return text or _OTHER_CATEGORY


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdbSideInput:
    """One side (asset / liability) of one window, already aggregated from enriched frames."""

    balance_by_category: Mapping[str, float] = field(default_factory=dict)
    rate_balance_by_category: Mapping[str, float] = field(default_factory=dict)
    rate_by_category: Mapping[str, float | None] = field(default_factory=dict)
    total_rate: float | None = None
    rate_coverage: float | None = None
    daily_totals: Mapping[str, float] = field(default_factory=dict)
    daily_category_balances: Mapping[str, Mapping[str, float]] = field(default_factory=dict)

    @property
    def total_rate_balance(self) -> float:
        return float(sum(self.rate_balance_by_category.values()))


@dataclass(frozen=True)
class AdbWindowInput:
    """One comparison window (current / qoq / yoy)."""

    start_date: str
    end_date: str
    calendar_days: int
    coverage_days: int = 0
    has_data: bool = False
    assets: AdbSideInput = field(default_factory=AdbSideInput)
    liabilities: AdbSideInput = field(default_factory=AdbSideInput)


# ---------------------------------------------------------------------------
# Window arithmetic (PRD §4.1)
# ---------------------------------------------------------------------------


def shift_date_by_years(value: date, years: int) -> date:
    """ISO 年位移；2/29 在非闰年回退 2/28（与前端 `shiftIsoDateByYears` 一致）。"""
    target_year = value.year + years
    try:
        return value.replace(year=target_year)
    except ValueError:
        return value.replace(year=target_year, day=28)


def compute_comparison_windows(start_date: date, end_date: date) -> dict[str, tuple[date, date]]:
    """本期 / 环比期（紧邻前一段等长区间）/ 同比期（减 1 年）。"""
    calendar_days = (end_date - start_date).days + 1
    return {
        "current": (start_date, end_date),
        "qoq": (start_date - timedelta(days=calendar_days), start_date - timedelta(days=1)),
        "yoy": (shift_date_by_years(start_date, -1), shift_date_by_years(end_date, -1)),
    }


# ---------------------------------------------------------------------------
# Frame aggregation (same enriched frames as build_rate_map)
# ---------------------------------------------------------------------------


def _finite_rate_mask(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.notna() & numeric.abs().ne(float("inf"))


def _is_usable_frame(frame: pd.DataFrame | None) -> bool:
    if frame is None or frame.empty:
        return False
    return "category" in frame.columns and "balance" in frame.columns


def build_side_input(
    frames: Sequence[pd.DataFrame],
    *,
    rate_by_category: Mapping[str, float | None] | None = None,
    total_rate: float | None = None,
    rate_coverage: float | None = None,
) -> AdbSideInput:
    """Aggregate enriched side frames into per-category totals and per-day observation series."""
    balance_by_category: dict[str, float] = {}
    rate_balance_by_category: dict[str, float] = {}
    daily_totals: dict[str, float] = {}
    daily_category_balances: dict[str, dict[str, float]] = {}

    for frame in frames:
        if not _is_usable_frame(frame):
            continue
        numeric_balances = pd.to_numeric(frame["balance"], errors="coerce")
        valid_balance = numeric_balances.notna() & numeric_balances.abs().ne(float("inf"))
        if "balance_valid" in frame.columns:
            valid_balance &= frame["balance_valid"].fillna(False).astype(bool)
        if not bool(valid_balance.any()):
            continue
        valid_frame = frame.loc[valid_balance]
        balances = numeric_balances.loc[valid_balance]
        if "rate_decimal" in frame.columns:
            has_rate = _finite_rate_mask(frame["rate_decimal"]).loc[valid_balance]
        else:
            has_rate = pd.Series(False, index=valid_frame.index)
        if "report_date" in frame.columns:
            days = pd.to_datetime(valid_frame["report_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        else:
            days = pd.Series(pd.NA, index=valid_frame.index, dtype=object)
        work = pd.DataFrame(
            {
                "category": valid_frame["category"].map(_clean_category).to_numpy(),
                "balance": balances.to_numpy(dtype=float),
                "rate_balance": balances.where(has_rate, 0.0).to_numpy(dtype=float),
                "day": days.to_numpy(),
            }
        )
        grouped = work.groupby("category", sort=False)[["balance", "rate_balance"]].sum()
        for category, row in grouped.iterrows():
            key = str(category)
            balance_by_category[key] = balance_by_category.get(key, 0.0) + float(row["balance"])
            rate_balance_by_category[key] = rate_balance_by_category.get(key, 0.0) + float(row["rate_balance"])

        dated = work.loc[work["day"].notna()]
        if dated.empty:
            continue
        for (day, category), amount in dated.groupby(["day", "category"], sort=False)["balance"].sum().items():
            iso_day = str(day)
            bucket = daily_category_balances.setdefault(iso_day, {})
            bucket[str(category)] = bucket.get(str(category), 0.0) + float(amount)
            daily_totals[iso_day] = daily_totals.get(iso_day, 0.0) + float(amount)

    return AdbSideInput(
        balance_by_category=balance_by_category,
        rate_balance_by_category=rate_balance_by_category,
        rate_by_category=dict(rate_by_category or {}),
        total_rate=total_rate,
        rate_coverage=rate_coverage,
        daily_totals=daily_totals,
        daily_category_balances=daily_category_balances,
    )


def sample_fill_side_balances(
    side: AdbSideInput,
    *,
    calendar_days: int,
    coverage_days: int,
) -> AdbSideInput:
    """Match comparison's sparse-snapshot completion without altering observed daily series."""
    if coverage_days <= 0 or coverage_days >= calendar_days:
        return side
    factor = float(calendar_days) / float(coverage_days)
    return replace(
        side,
        balance_by_category={
            category: float(value) * factor
            for category, value in side.balance_by_category.items()
        },
    )


# ---------------------------------------------------------------------------
# 4.2 规模变动归因
# ---------------------------------------------------------------------------


def _side_scale_attribution(
    current: AdbSideInput,
    current_days: int,
    prior: AdbSideInput,
    prior_days: int,
    side_label: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current_denominator = max(int(current_days), 1)
    prior_denominator = max(int(prior_days), 1)
    current_avg = {cat: value / current_denominator for cat, value in current.balance_by_category.items()}
    prior_avg = {cat: value / prior_denominator for cat, value in prior.balance_by_category.items()}

    total_current = float(sum(current_avg.values()))
    total_prior = float(sum(prior_avg.values()))
    delta_total = total_current - total_prior

    rows: list[dict[str, Any]] = []
    for category in sorted(set(current_avg) | set(prior_avg)):
        current_value = current_avg.get(category)
        prior_value = prior_avg.get(category)
        delta = (current_value or 0.0) - (prior_value or 0.0)
        rows.append(
            {
                "category": category,
                "side": side_label,
                "current_avg": current_value,
                "prior_avg": prior_value,
                "delta": delta,
                "contribution_pct": (
                    round(delta / abs(delta_total) * 100, 4) if delta_total != 0 else None
                ),
            }
        )
    rows.sort(key=lambda row: (-abs(row["delta"]), row["category"]))

    totals = {
        "current_avg": total_current,
        "prior_avg": total_prior,
        "delta": delta_total,
        "delta_pct": round(delta_total / total_prior * 100, 4) if total_prior != 0 else None,
    }
    return totals, rows


def build_scale_attribution(current: AdbWindowInput, prior: AdbWindowInput) -> dict[str, Any]:
    asset_totals, asset_rows = _side_scale_attribution(
        current.assets, current.calendar_days, prior.assets, prior.calendar_days, "asset"
    )
    liability_totals, liability_rows = _side_scale_attribution(
        current.liabilities, current.calendar_days, prior.liabilities, prior.calendar_days, "liability"
    )
    return {
        "side_totals": {"assets": asset_totals, "liabilities": liability_totals},
        "asset_contributions": asset_rows,
        "liability_contributions": liability_rows,
    }


# ---------------------------------------------------------------------------
# 4.3 NIM 量价归因
# ---------------------------------------------------------------------------


def _category_shares(side: AdbSideInput) -> dict[str, float | None]:
    total = side.total_rate_balance
    if total <= 0:
        return {}
    return {cat: value / total for cat, value in side.rate_balance_by_category.items()}


def _side_rate_attribution(current: AdbSideInput, prior: AdbSideInput) -> dict[str, Any]:
    rate_current = float(current.total_rate or 0.0)
    rate_prior = float(prior.total_rate or 0.0)
    total_effect_bp = round((rate_current - rate_prior) * 100, 4)

    shares_current = _category_shares(current)
    shares_prior = _category_shares(prior)
    categories = sorted(
        set(current.rate_by_category)
        | set(prior.rate_by_category)
        | set(current.rate_balance_by_category)
        | set(prior.rate_balance_by_category)
    )

    rows: list[dict[str, Any]] = []
    for category in categories:
        share_current = shares_current.get(category)
        share_prior = shares_prior.get(category)
        weight_current = share_current or 0.0
        weight_prior = share_prior or 0.0
        category_rate_current = current.rate_by_category.get(category)
        category_rate_prior = prior.rate_by_category.get(category)

        if category_rate_current is not None and category_rate_prior is not None:
            rate_effect = weight_prior * (category_rate_current - category_rate_prior) * 100
            mix_effect = (weight_current - weight_prior) * (category_rate_prior - rate_prior) * 100
        elif category_rate_current is not None:
            # 新增（对比期无利率）：整体贡献按结构效应披露，避免虚构 rate_prior。
            rate_effect = 0.0
            mix_effect = weight_current * (category_rate_current - rate_prior) * 100
        elif category_rate_prior is not None:
            rate_effect = 0.0
            mix_effect = (weight_current - weight_prior) * (category_rate_prior - rate_prior) * 100
        else:
            rate_effect = 0.0
            mix_effect = 0.0

        rows.append(
            {
                "category": category,
                "share_current": round(share_current, 6) if share_current is not None else None,
                "share_prior": round(share_prior, 6) if share_prior is not None else None,
                "rate_current": category_rate_current,
                "rate_prior": category_rate_prior,
                "rate_effect_bp": round(rate_effect, 4),
                "mix_effect_bp": round(mix_effect, 4),
            }
        )
    rows.sort(key=lambda row: (-abs(row["rate_effect_bp"] + row["mix_effect_bp"]), row["category"]))

    rate_effect_total = round(sum(row["rate_effect_bp"] for row in rows), 4)
    mix_effect_total = round(sum(row["mix_effect_bp"] for row in rows), 4)
    return {
        "total_effect_bp": total_effect_bp,
        "rate_effect_bp": rate_effect_total,
        "mix_effect_bp": mix_effect_total,
        "residual_bp": round(total_effect_bp - rate_effect_total - mix_effect_total, 4),
        "by_category": rows,
    }


def build_nim_attribution(
    current: AdbWindowInput,
    prior: AdbWindowInput,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (attribution, unavailable_reason); reason is "rate_unavailable" when any side R is null."""
    rates = (
        current.assets.total_rate,
        prior.assets.total_rate,
        current.liabilities.total_rate,
        prior.liabilities.total_rate,
    )
    if any(rate is None for rate in rates):
        return None, "rate_unavailable"

    asset_side = _side_rate_attribution(current.assets, prior.assets)
    liability_side = _side_rate_attribution(current.liabilities, prior.liabilities)
    asset_yield_current, asset_yield_prior, liability_cost_current, liability_cost_prior = (
        float(rate) for rate in rates
    )
    return (
        {
            "basis": "qoq",
            "nim_current": round(asset_yield_current - liability_cost_current, 4),
            "nim_prior": round(asset_yield_prior - liability_cost_prior, 4),
            "nim_delta_bp": round(
                asset_side["total_effect_bp"] - liability_side["total_effect_bp"], 4
            ),
            "asset_side": asset_side,
            "liability_side": liability_side,
        },
        None,
    )


# ---------------------------------------------------------------------------
# 4.4 波动与异常
# ---------------------------------------------------------------------------


def _sorted_points(daily_totals: Mapping[str, float]) -> list[tuple[str, float]]:
    return sorted((str(day), float(value)) for day, value in daily_totals.items())


def _sample_std(values: Sequence[float]) -> float:
    count = len(values)
    if count < 2:
        return 0.0
    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / (count - 1)
    return math.sqrt(max(variance, 0.0))


def _series_stats(points: Sequence[tuple[str, float]]) -> dict[str, Any] | None:
    if len(points) < 2:
        return None
    values = [value for _day, value in points]
    mean = sum(values) / len(values)
    std = _sample_std(values)
    minimum = min(points, key=lambda item: (item[1], item[0]))
    maximum = max(points, key=lambda item: (item[1], item[0]))

    max_change: dict[str, Any] | None = None
    best_magnitude = -1.0
    for index in range(1, len(points)):
        previous_value = points[index - 1][1]
        delta = points[index][1] - previous_value
        if abs(delta) > best_magnitude:
            best_magnitude = abs(delta)
            max_change = {
                "date": points[index][0],
                "delta": delta,
                "pct": round(delta / previous_value * 100, 4) if previous_value != 0 else None,
            }

    return {
        "mean": mean,
        "std": std,
        "cv": round(std / mean, 6) if mean != 0 else None,
        "min": {"date": minimum[0], "value": minimum[1]},
        "max": {"date": maximum[0], "value": maximum[1]},
        "max_daily_change": max_change,
    }


def _detect_anomalies(
    points: Sequence[tuple[str, float]],
    side_label: str,
) -> tuple[list[dict[str, Any]], bool]:
    if len(points) < ANOMALY_MIN_OBSERVATIONS:
        return [], False
    changes = [
        (points[index][0], points[index][1], points[index][1] - points[index - 1][1])
        for index in range(1, len(points))
    ]
    deltas = [delta for _day, _value, delta in changes]
    mean = sum(deltas) / len(deltas)
    std = _sample_std(deltas)
    if std <= 0:
        return [], False

    anomalies: list[dict[str, Any]] = []
    for day, value, delta in changes:
        zscore = (delta - mean) / std
        if abs(zscore) < ANOMALY_ZSCORE_THRESHOLD:
            continue
        anomalies.append(
            {
                "date": day,
                "side": side_label,
                "value": value,
                "delta": delta,
                "zscore": round(zscore, 4),
                "direction": "up" if delta >= 0 else "down",
            }
        )
    return anomalies, True


def _month_end_effect(points: Sequence[tuple[str, float]]) -> dict[str, Any]:
    by_month: dict[str, list[tuple[str, float]]] = {}
    for day, value in points:
        by_month.setdefault(day[:7], []).append((day, value))

    uplifts: list[float] = []
    for _month, entries in sorted(by_month.items()):
        if len(entries) < MONTH_END_MIN_OBSERVATIONS:
            continue
        ordered = sorted(entries)
        month_end_value = ordered[-1][1]
        mid_values = [value for _day, value in ordered[:-1]]
        mid = sum(mid_values) / len(mid_values)
        if mid == 0:
            continue
        uplifts.append((month_end_value - mid) / mid * 100)

    if not uplifts:
        return {"uplift_pct": None, "months_observed": 0, "flagged": False}
    average_uplift = sum(uplifts) / len(uplifts)
    return {
        "uplift_pct": round(average_uplift, 4),
        "months_observed": len(uplifts),
        "flagged": average_uplift > MONTH_END_UPLIFT_THRESHOLD_PCT,
    }


def build_volatility_block(window: AdbWindowInput) -> dict[str, Any] | None:
    asset_points = _sorted_points(window.assets.daily_totals)
    liability_points = _sorted_points(window.liabilities.daily_totals)
    if not asset_points and not liability_points:
        return None

    asset_anomalies, asset_detectable = _detect_anomalies(asset_points, "asset")
    liability_anomalies, liability_detectable = _detect_anomalies(liability_points, "liability")
    anomalies = sorted(
        asset_anomalies + liability_anomalies,
        key=lambda item: (-abs(item["zscore"]), item["date"], item["side"]),
    )[:ANOMALY_MAX_ITEMS]

    return {
        "assets": _series_stats(asset_points),
        "liabilities": _series_stats(liability_points),
        "anomaly_detection_available": bool(asset_detectable or liability_detectable),
        "anomalies": anomalies,
        "month_end_effect": {
            "assets": _month_end_effect(asset_points),
            "liabilities": _month_end_effect(liability_points),
        },
    }


# ---------------------------------------------------------------------------
# 4.5 结构集中度
# ---------------------------------------------------------------------------


def _distribution_shares(distribution: Mapping[str, float]) -> dict[str, float]:
    total = float(sum(distribution.values()))
    if total <= 0:
        return {}
    return {category: float(value) / total for category, value in distribution.items()}


def _top_n_share(shares: Mapping[str, float], count: int) -> float:
    return float(sum(sorted(shares.values(), reverse=True)[:count]))


def _side_concentration(side: AdbSideInput) -> dict[str, Any] | None:
    days = sorted(side.daily_category_balances)
    if len(days) < 2:
        return None
    start_day, end_day = days[0], days[-1]
    start_shares = _distribution_shares(side.daily_category_balances[start_day])
    end_shares = _distribution_shares(side.daily_category_balances[end_day])

    movers: list[dict[str, Any]] = []
    for category in sorted(set(start_shares) | set(end_shares)):
        share_start = start_shares.get(category, 0.0)
        share_end = end_shares.get(category, 0.0)
        movers.append(
            {
                "category": category,
                "share_start_pct": round(share_start * 100, 4),
                "share_end_pct": round(share_end * 100, 4),
                "delta_pp": round((share_end - share_start) * 100, 4),
            }
        )
    movers.sort(key=lambda row: (-abs(row["delta_pp"]), row["category"]))

    return {
        "start_observation_date": start_day,
        "end_observation_date": end_day,
        "hhi_start": round(sum(share * share for share in start_shares.values()), 4),
        "hhi_end": round(sum(share * share for share in end_shares.values()), 4),
        "top3_share_start": round(_top_n_share(start_shares, 3), 4),
        "top3_share_end": round(_top_n_share(end_shares, 3), 4),
        "top5_share_start": round(_top_n_share(start_shares, 5), 4),
        "top5_share_end": round(_top_n_share(end_shares, 5), 4),
        "movers": movers[:CONCENTRATION_MOVER_LIMIT],
    }


def build_concentration_block(window: AdbWindowInput) -> dict[str, Any] | None:
    if not window.assets.daily_category_balances and not window.liabilities.daily_category_balances:
        return None
    assets = _side_concentration(window.assets)
    liabilities = _side_concentration(window.liabilities)
    return {
        "assets": assets,
        "liabilities": liabilities,
        "reason": "single_observation" if assets is None and liabilities is None else None,
    }


# ---------------------------------------------------------------------------
# 4.6 结论规则引擎
# ---------------------------------------------------------------------------


def _format_yi(value: float) -> str:
    return f"{value / _YI:.2f}亿元"


def _format_bp(value: float) -> str:
    return f"{value:.1f}bp"


def _format_pct(value: float) -> str:
    return f"{value:.2f}%"


def _insight(
    insight_id: str,
    severity: str,
    dimension: str,
    title: str,
    detail: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": insight_id,
        "severity": severity,
        "dimension": dimension,
        "title": title,
        "detail": detail,
        "evidence": evidence,
    }


_SIDE_LABELS = {"assets": "资产", "liabilities": "负债"}


def _scale_move_insight(scale_qoq: Mapping[str, Any]) -> dict[str, Any] | None:
    triggered: list[tuple[str, Mapping[str, Any], Sequence[Mapping[str, Any]]]] = []
    for side_key, rows_key in (("assets", "asset_contributions"), ("liabilities", "liability_contributions")):
        totals = scale_qoq["side_totals"][side_key]
        delta_pct = totals.get("delta_pct")
        if delta_pct is None or abs(delta_pct) <= SCALE_MOVE_TRIGGER_PCT:
            continue
        triggered.append((side_key, totals, scale_qoq[rows_key]))
    if not triggered:
        return None

    severity = (
        "notice"
        if any(abs(totals["delta_pct"]) >= SCALE_MOVE_NOTICE_PCT for _key, totals, _rows in triggered)
        else "info"
    )
    fragments: list[str] = []
    evidence_sides: list[dict[str, Any]] = []
    for side_key, totals, rows in triggered:
        label = _SIDE_LABELS[side_key]
        direction = "上升" if totals["delta"] >= 0 else "下降"
        top_rows = list(rows[:2])
        top_text = "、".join(f"{row['category']}（{_format_yi(row['delta'])}）" for row in top_rows) or "无明细"
        fragments.append(
            f"{label}日均{direction}{_format_yi(abs(totals['delta']))}"
            f"（{_format_pct(totals['delta_pct'])}），主要贡献为{top_text}"
        )
        evidence_sides.append(
            {
                "side": side_key,
                "delta": totals["delta"],
                "delta_pct": totals["delta_pct"],
                "top_contributions": [
                    {"category": row["category"], "delta": row["delta"], "contribution_pct": row["contribution_pct"]}
                    for row in top_rows
                ],
            }
        )
    return _insight(
        "scale_qoq_move",
        severity,
        "scale",
        "规模环比变动显著",
        "环比区间内" + "；".join(fragments) + "。",
        {"sides": evidence_sides},
    )


def _dominant_nim_driver(nim: Mapping[str, Any]) -> tuple[str, float]:
    candidates = [
        ("资产利率", float(nim["asset_side"]["rate_effect_bp"])),
        ("资产结构", float(nim["asset_side"]["mix_effect_bp"])),
        ("负债利率", float(nim["liability_side"]["rate_effect_bp"])),
        ("负债结构", float(nim["liability_side"]["mix_effect_bp"])),
    ]
    return max(candidates, key=lambda item: abs(item[1]))


def _nim_insight(nim: Mapping[str, Any]) -> dict[str, Any] | None:
    delta_bp = nim.get("nim_delta_bp")
    if delta_bp is None:
        return None
    nim_current = nim.get("nim_current")
    nim_prior = nim.get("nim_prior")
    if delta_bp < NIM_COMPRESSION_BP:
        driver_label, driver_bp = _dominant_nim_driver(nim)
        severity = "warning" if delta_bp <= NIM_COMPRESSION_WARNING_BP else "notice"
        detail = (
            f"净息差环比收窄{_format_bp(abs(delta_bp))}"
            f"（{_format_pct(float(nim_prior))} → {_format_pct(float(nim_current))}），"
            f"主导项为{driver_label}效应（{_format_bp(driver_bp)}）。"
        )
        return _insight(
            "nim_compression",
            severity,
            "nim",
            "净息差环比收窄",
            detail,
            {
                "nim_delta_bp": delta_bp,
                "nim_current": nim_current,
                "nim_prior": nim_prior,
                "dominant_driver": driver_label,
                "dominant_driver_bp": driver_bp,
            },
        )
    if delta_bp > NIM_EXPANSION_BP:
        detail = (
            f"净息差环比走阔{_format_bp(delta_bp)}"
            f"（{_format_pct(float(nim_prior))} → {_format_pct(float(nim_current))}）。"
        )
        return _insight(
            "nim_expansion",
            "info",
            "nim",
            "净息差环比走阔",
            detail,
            {"nim_delta_bp": delta_bp, "nim_current": nim_current, "nim_prior": nim_prior},
        )
    return None


def _anomaly_insight(volatility: Mapping[str, Any]) -> dict[str, Any] | None:
    anomalies = list(volatility.get("anomalies") or [])
    if not anomalies:
        return None
    top = anomalies[0]
    severity = "warning" if any(abs(item["zscore"]) >= ANOMALY_SEVERE_ZSCORE for item in anomalies) else "notice"
    side_label = "资产" if top["side"] == "asset" else "负债"
    direction = "上升" if top["direction"] == "up" else "下降"
    detail = (
        f"区间内检测到{len(anomalies)}个异常波动日，最显著为 {top['date']} "
        f"{side_label}单日{direction}{_format_yi(abs(top['delta']))}（z={top['zscore']:.2f}）。"
    )
    return _insight(
        "anomaly_days",
        severity,
        "volatility",
        "日度余额出现异常跳变",
        detail,
        {"anomaly_count": len(anomalies), "top_anomaly": top},
    )


def _month_end_insight(volatility: Mapping[str, Any]) -> dict[str, Any] | None:
    month_end = volatility.get("month_end_effect")
    if not month_end:
        return None
    flagged = [(key, month_end[key]) for key in ("assets", "liabilities") if month_end[key]["flagged"]]
    if not flagged:
        return None
    fragments = [
        f"{_SIDE_LABELS[key]}月末余额较月中均值高{_format_pct(effect['uplift_pct'])}"
        f"（覆盖{effect['months_observed']}个月）"
        for key, effect in flagged
    ]
    return _insight(
        "month_end_effect",
        "warning",
        "volatility",
        "存在月末冲高（窗口粉饰）迹象",
        "；".join(fragments) + "。",
        {"sides": [{"side": key, **effect} for key, effect in flagged]},
    )


def _concentration_insight(concentration: Mapping[str, Any]) -> dict[str, Any] | None:
    fragments: list[str] = []
    evidence_sides: list[dict[str, Any]] = []
    for side_key in ("assets", "liabilities"):
        side = concentration.get(side_key)
        if not side:
            continue
        rise = float(side["hhi_end"]) - float(side["hhi_start"])
        if rise <= CONCENTRATION_HHI_RISE_THRESHOLD:
            continue
        fragments.append(
            f"{_SIDE_LABELS[side_key]} HHI 由 {side['hhi_start']:.4f} 升至 {side['hhi_end']:.4f}"
            f"（+{rise:.4f}）"
        )
        evidence_sides.append(
            {
                "side": side_key,
                "hhi_start": side["hhi_start"],
                "hhi_end": side["hhi_end"],
                "hhi_delta": round(rise, 4),
                "movers": list(side["movers"][:3]),
            }
        )
    if not fragments:
        return None
    return _insight(
        "concentration_up",
        "notice",
        "concentration",
        "结构集中度上升",
        "区间首末观测日对比：" + "；".join(fragments) + "。",
        {"sides": evidence_sides},
    )


def _comparison_unavailable_insight(windows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    labels = {"qoq": "环比期", "yoy": "同比期"}
    missing = [key for key in ("qoq", "yoy") if not windows[key]["available"]]
    if not missing:
        return None
    fragments = [
        f"{labels[key]}（{windows[key]['start_date']}～{windows[key]['end_date']}）无数据"
        for key in missing
    ]
    return _insight(
        "comparison_unavailable",
        "info",
        "quality",
        "对比期数据缺失",
        "；".join(fragments) + "，相关归因不可用。",
        {"missing_windows": [{"basis": key, **dict(windows[key])} for key in missing]},
    )


def _current_unavailable_insight(
    windows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    current = windows["current"]
    if current["available"]:
        return None
    return _insight(
        "current_unavailable",
        "info",
        "quality",
        "本期有效余额缺失",
        f"本期（{current['start_date']}～{current['end_date']}）无有效余额，深度分析不可用。",
        {"window": dict(current)},
    )


def _rate_coverage_insight(
    asset_coverage: float | None,
    liability_coverage: float | None,
) -> dict[str, Any] | None:
    fragments: list[str] = []
    evidence: dict[str, Any] = {}
    for side_key, coverage in (("assets", asset_coverage), ("liabilities", liability_coverage)):
        if coverage is None or coverage >= RATE_COVERAGE_LOW:
            continue
        fragments.append(f"{_SIDE_LABELS[side_key]}利率覆盖率{_format_pct(float(coverage) * 100)}")
        evidence[side_key] = coverage
    if not fragments:
        return None
    return _insight(
        "rate_coverage_low",
        "info",
        "quality",
        "利率覆盖不足",
        "本期" + "、".join(fragments) + f"，低于{_format_pct(RATE_COVERAGE_LOW * 100)}，量价归因残差可能偏大。",
        {"coverage": evidence},
    )


def build_insights(
    *,
    windows: Mapping[str, Mapping[str, Any]],
    scale_qoq: Mapping[str, Any] | None,
    nim: Mapping[str, Any] | None,
    volatility: Mapping[str, Any] | None,
    concentration: Mapping[str, Any] | None,
    asset_rate_coverage: float | None,
    liability_rate_coverage: float | None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any] | None] = [_current_unavailable_insight(windows)]
    if scale_qoq is not None:
        candidates.append(_scale_move_insight(scale_qoq))
    if nim is not None:
        candidates.append(_nim_insight(nim))
    if volatility is not None:
        candidates.append(_anomaly_insight(volatility))
        candidates.append(_month_end_insight(volatility))
    if concentration is not None:
        candidates.append(_concentration_insight(concentration))
    candidates.append(_comparison_unavailable_insight(windows))
    candidates.append(_rate_coverage_insight(asset_rate_coverage, liability_rate_coverage))
    return [item for item in candidates if item is not None]


# ---------------------------------------------------------------------------
# Payload assembly (PRD §5)
# ---------------------------------------------------------------------------


def _window_descriptor(window: AdbWindowInput) -> dict[str, Any]:
    return {
        "start_date": window.start_date,
        "end_date": window.end_date,
        "calendar_days_inclusive": window.calendar_days,
        "coverage_days": window.coverage_days,
        "available": bool(window.has_data),
        "reason": "ok" if window.has_data else "no_data",
    }


def build_adb_insights_payload(
    *,
    current: AdbWindowInput,
    qoq: AdbWindowInput,
    yoy: AdbWindowInput,
) -> dict[str, Any]:
    windows = {
        "current": _window_descriptor(current),
        "qoq": _window_descriptor(qoq),
        "yoy": _window_descriptor(yoy),
    }
    insufficient_window = current.calendar_days <= 1

    if insufficient_window:
        scale_attribution: dict[str, Any] = {"qoq": None, "yoy": None}
        nim_attribution: dict[str, Any] | None = None
        nim_unavailable_reason: str | None = "insufficient_window"
        volatility: dict[str, Any] | None = None
        concentration: dict[str, Any] | None = None
    elif not current.has_data:
        scale_attribution = {"qoq": None, "yoy": None}
        nim_attribution = None
        nim_unavailable_reason = "current_unavailable"
        volatility = None
        concentration = None
    else:
        scale_attribution = {
            "qoq": build_scale_attribution(current, qoq) if qoq.has_data else None,
            "yoy": build_scale_attribution(current, yoy) if yoy.has_data else None,
        }
        if qoq.has_data:
            nim_attribution, nim_unavailable_reason = build_nim_attribution(current, qoq)
        else:
            nim_attribution, nim_unavailable_reason = None, "comparison_unavailable"
        volatility = build_volatility_block(current)
        concentration = build_concentration_block(current)

    return {
        "start_date": current.start_date,
        "end_date": current.end_date,
        "calendar_days_inclusive": current.calendar_days,
        "insufficient_window": insufficient_window,
        "windows": windows,
        "scale_attribution": scale_attribution,
        "nim_attribution": nim_attribution,
        "nim_attribution_unavailable_reason": nim_unavailable_reason,
        "volatility": volatility,
        "concentration": concentration,
        "insights": build_insights(
            windows=windows,
            scale_qoq=scale_attribution["qoq"],
            nim=nim_attribution,
            volatility=volatility,
            concentration=concentration,
            asset_rate_coverage=current.assets.rate_coverage,
            liability_rate_coverage=current.liabilities.rate_coverage,
        ),
    }


__all__ = [
    "AdbSideInput",
    "AdbWindowInput",
    "build_adb_insights_payload",
    "build_concentration_block",
    "build_insights",
    "build_nim_attribution",
    "build_scale_attribution",
    "build_side_input",
    "build_volatility_block",
    "compute_comparison_windows",
    "sample_fill_side_balances",
    "shift_date_by_years",
]
