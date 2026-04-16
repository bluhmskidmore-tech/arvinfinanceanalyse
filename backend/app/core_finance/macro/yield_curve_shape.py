from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Mapping

from app.core_finance.safe_decimal import safe_decimal

_TENOR_YEARS: dict[str, Decimal] = {
    "1Y": Decimal("1"),
    "3Y": Decimal("3"),
    "5Y": Decimal("5"),
    "7Y": Decimal("7"),
    "10Y": Decimal("10"),
    "30Y": Decimal("30"),
}


def _get_value(record: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(record, Mapping) and key in record:
            value = record[key]
        else:
            value = getattr(record, key, None)
        if value is not None:
            return value
    return default


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    return None


def _build_curves(
    curve_rows: Iterable[Any],
    *,
    curve_id: str,
    report_date: date,
) -> dict[date, dict[str, Decimal]]:
    curves: dict[date, dict[str, Decimal]] = defaultdict(dict)
    for row in curve_rows:
        row_date = _coerce_date(_get_value(row, "biz_date", "report_date"))
        if row_date is None or row_date > report_date:
            continue
        if str(_get_value(row, "curve_id", default="")) != curve_id:
            continue
        tenor = str(_get_value(row, "tenor", default=""))
        if tenor not in _TENOR_YEARS:
            continue
        rate = _get_value(row, "rate_value")
        if rate is None:
            continue
        curves[row_date][tenor] = safe_decimal(rate)
    return curves


def _spread_bp(curve: Mapping[str, Decimal], left: str, right: str) -> Decimal | None:
    left_value = curve.get(left)
    right_value = curve.get(right)
    if left_value is None or right_value is None:
        return None
    return (left_value - right_value) * Decimal("100")


def _linear_slope(curve: Mapping[str, Decimal]) -> Decimal:
    points = [
        (_TENOR_YEARS[tenor], safe_decimal(rate))
        for tenor, rate in curve.items()
        if tenor in _TENOR_YEARS and rate is not None
    ]
    points.sort(key=lambda item: item[0])
    if len(points) < 2:
        return Decimal("0")

    count = Decimal(len(points))
    sum_x = sum(x for x, _ in points)
    sum_y = sum(y for _, y in points)
    sum_xy = sum(x * y for x, y in points)
    sum_xx = sum(x * x for x, _ in points)
    denom = count * sum_xx - sum_x * sum_x
    if denom == 0:
        return Decimal("0")
    return (count * sum_xy - sum_x * sum_y) / denom


def _butterfly_spread(curve: Mapping[str, Decimal]) -> Decimal | None:
    one_year = curve.get("1Y")
    five_year = curve.get("5Y")
    ten_year = curve.get("10Y")
    if one_year is None or five_year is None or ten_year is None:
        return None
    return Decimal("2") * five_year - one_year - ten_year


def _classify_shape(curve: Mapping[str, Decimal], spread_10y_1y_bp: Decimal) -> tuple[str, str]:
    one_year = curve.get("1Y")
    five_year = curve.get("5Y")
    ten_year = curve.get("10Y")

    if spread_10y_1y_bp < Decimal("0"):
        return "Inverted", "收益率曲线倒挂，宏观上偏防御信号。"
    if spread_10y_1y_bp < Decimal("20"):
        return "Flat", "收益率曲线平坦，久期上宜保持谨慎。"
    if (
        one_year is not None
        and five_year is not None
        and ten_year is not None
        and five_year >= max(one_year, ten_year)
        and five_year > one_year + Decimal("0.10")
        and five_year > ten_year + Decimal("0.05")
    ):
        return "Hump", "中段收益率偏高，曲线中段承压。"
    if spread_10y_1y_bp < Decimal("60"):
        return "ModerateSteep", "收益率曲线中度陡峭，久期不必极端化。"
    return "NormalSteep", "收益率曲线偏陡，久期上需保持纪律。"


def compute_yield_curve_shape(
    curve_rows: Iterable[Any],
    *,
    report_date: date,
    curve_id: str = "CN_GOVT",
) -> dict[str, Any]:
    curves = _build_curves(curve_rows, curve_id=curve_id, report_date=report_date)
    available_dates = sorted(curves.keys(), reverse=True)
    if not available_dates:
        return {
            "report_date": report_date.isoformat(),
            "shape": "Unavailable",
            "slope": 0.0,
            "butterfly_spread": None,
            "curvature": "neutral",
            "spreads": {},
            "percentile_1y": None,
            "interpretation": "暂无国债收益率曲线数据。",
            "curve": {},
            "warnings": ["NO_GOV_CURVE"],
        }

    current_curve = curves[available_dates[0]]
    spread_10y_1y_bp = _spread_bp(current_curve, "10Y", "1Y")
    if spread_10y_1y_bp is None:
        return {
            "report_date": report_date.isoformat(),
            "shape": "Unavailable",
            "slope": float(_linear_slope(current_curve)),
            "butterfly_spread": None,
            "curvature": "neutral",
            "spreads": {},
            "percentile_1y": None,
            "interpretation": "国债曲线缺少必要的 1Y/10Y 节点。",
            "curve": {tenor: float(rate) for tenor, rate in current_curve.items()},
            "warnings": ["GOV_CURVE_MISSING_REQUIRED_TENORS"],
        }

    spread_history: list[Decimal] = []
    for history_date in available_dates[1:]:
        history_spread = _spread_bp(curves[history_date], "10Y", "1Y")
        if history_spread is not None:
            spread_history.append(history_spread)

    percentile_1y: float | None = None
    if spread_history:
        below = sum(1 for spread in spread_history if spread < spread_10y_1y_bp)
        percentile_1y = round((below / len(spread_history)) * 100, 2)

    slope = _linear_slope(current_curve)
    butterfly_spread = _butterfly_spread(current_curve)
    curvature = "neutral"
    if butterfly_spread is not None:
        if butterfly_spread > Decimal("0.05"):
            curvature = "convex"
        elif butterfly_spread < Decimal("-0.05"):
            curvature = "concave"

    shape, interpretation = _classify_shape(current_curve, spread_10y_1y_bp)
    spreads = {
        "10Y-1Y": float(spread_10y_1y_bp),
        "10Y-5Y": float(_spread_bp(current_curve, "10Y", "5Y") or Decimal("0")),
        "30Y-10Y": float(_spread_bp(current_curve, "30Y", "10Y") or Decimal("0")),
    }

    return {
        "report_date": report_date.isoformat(),
        "shape": shape,
        "slope": float(slope),
        "butterfly_spread": float(butterfly_spread) if butterfly_spread is not None else None,
        "curvature": curvature,
        "spreads": spreads,
        "percentile_1y": percentile_1y,
        "interpretation": interpretation,
        "curve": {tenor: float(rate) for tenor, rate in current_curve.items()},
        "warnings": [],
    }
