from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from app.core_finance.safe_decimal import safe_decimal
from app.core_finance.macro.helpers import get_value as _get_value


def _round(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_liquidity_stress_test(
    proxy_rows: Iterable[Any],
    bucket_rows: Iterable[Any],
    *,
    report_date: date,
    total_assets: Any = None,
) -> dict[str, Any]:
    proxy_items = list(proxy_rows)
    buckets = list(bucket_rows)
    if not proxy_items and not buckets:
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "stress_score": 0,
            "stress_level": "UNAVAILABLE",
            "headline": "暂无流动性代理或期限阶梯数据。",
            "top_book_share_of_abs_dv01": None,
            "short_term_gap": None,
            "short_term_gap_ratio": None,
            "cumulative_gap_3m": None,
            "negative_bucket_count": 0,
            "alerts": [],
            "recommendation": "无法评估流动性压力。",
            "top_books": [],
            "buckets": [],
            "notes": [],
            "warnings": ["NO_LIQUIDITY_INPUTS"],
        }

    top_book_share = None
    if proxy_items:
        share = _get_value(proxy_items[0], "share_of_abs_dv01")
        top_book_share = safe_decimal(share) if share is not None else None

    short_term_gap = Decimal("0")
    cumulative_gap_3m = None
    negative_bucket_count = 0
    bucket_payload: list[dict[str, Any]] = []
    for bucket in buckets:
        bucket_name = str(_get_value(bucket, "bucket_name", default=""))
        net_gap = safe_decimal(_get_value(bucket, "net_gap", default=0))
        cumulative_gap = safe_decimal(_get_value(bucket, "cumulative_gap", default=0))
        gap_ratio_raw = _get_value(bucket, "gap_ratio")
        if net_gap < 0:
            negative_bucket_count += 1
        if bucket_name in {"<=1M", "1-3M"}:
            short_term_gap += net_gap
            cumulative_gap_3m = cumulative_gap
        bucket_payload.append(
            {
                "bucket_name": bucket_name,
                "asset_amount": float(safe_decimal(_get_value(bucket, "asset_amount", default=0))),
                "liability_amount": float(safe_decimal(_get_value(bucket, "liability_amount", default=0))),
                "net_gap": float(net_gap),
                "cumulative_gap": float(cumulative_gap),
                "gap_ratio": float(safe_decimal(gap_ratio_raw)) if gap_ratio_raw is not None else None,
                "asset_row_count": int(_get_value(bucket, "asset_row_count", default=0) or 0),
                "liability_row_count": int(_get_value(bucket, "liability_row_count", default=0) or 0),
            }
        )

    total_assets_decimal = safe_decimal(total_assets) if total_assets is not None else None
    short_term_gap_ratio = None
    if total_assets_decimal is not None and total_assets_decimal > 0:
        short_term_gap_ratio = short_term_gap / total_assets_decimal

    stress_score = 0
    alerts: list[dict[str, str]] = []

    if top_book_share is not None:
        if top_book_share >= Decimal("0.60"):
            stress_score += 40
            alerts.append({"level": "CRITICAL", "message": "单账簿 DV01 集中度极高。"})
        elif top_book_share >= Decimal("0.45"):
            stress_score += 25
            alerts.append({"level": "WARNING", "message": "首位账簿 DV01 集中度偏高。"})
        elif top_book_share >= Decimal("0.35"):
            stress_score += 10

    if short_term_gap_ratio is not None and short_term_gap < 0:
        ratio_abs = abs(short_term_gap_ratio)
        if ratio_abs >= Decimal("0.40"):
            stress_score += 35
            alerts.append({"level": "CRITICAL", "message": "短期期限阶梯缺口深度为负。"})
        elif ratio_abs >= Decimal("0.20"):
            stress_score += 20
            alerts.append({"level": "WARNING", "message": "短期期限阶梯缺口为负。"})
        elif ratio_abs >= Decimal("0.10"):
            stress_score += 10

    if negative_bucket_count >= 4:
        stress_score += 20
        alerts.append({"level": "WARNING", "message": "多个期限桶出现净缺口为负。"})
    elif negative_bucket_count >= 2:
        stress_score += 10

    stress_score = max(0, min(100, stress_score))
    if stress_score >= 70:
        stress_level = "CRITICAL"
        recommendation = "提高流动性缓冲，并降低主导账簿的 DV01 集中度。"
    elif stress_score >= 45:
        stress_level = "HIGH"
        recommendation = "保持额外流动性，并压缩承压期限桶内的敞口。"
    elif stress_score >= 20:
        stress_level = "MEDIUM"
        recommendation = "密切监控近端期限桶与集中度变化。"
    else:
        stress_level = "LOW"
        recommendation = "流动性代理信号整体可控。"

    warnings: list[str] = []
    if not proxy_items:
        warnings.append("DV01_PROXY_MISSING")
    if not buckets:
        warnings.append("MATURITY_BUCKETS_MISSING")
    if total_assets_decimal is None or total_assets_decimal <= 0:
        warnings.append("TOTAL_ASSETS_UNAVAILABLE")

    data_status = "complete"
    if warnings:
        data_status = "degraded"
    if not proxy_items and not buckets:
        data_status = "unavailable"

    top_books = [
        {
            "book_id": str(_get_value(item, "book_id", default="")),
            "dv01_sum": float(safe_decimal(_get_value(item, "dv01_sum", default=0))),
            "row_count": int(_get_value(item, "row_count", default=0) or 0),
            "share_of_abs_dv01": (
                float(safe_decimal(_get_value(item, "share_of_abs_dv01")))
                if _get_value(item, "share_of_abs_dv01") is not None
                else None
            ),
        }
        for item in proxy_items[:5]
    ]

    return {
        "report_date": report_date.isoformat(),
        "data_status": data_status,
        "stress_score": stress_score,
        "stress_level": stress_level,
        "headline": "流动性压力测试基于 V2 期限阶梯与 DV01 集中度代理构建。",
        "top_book_share_of_abs_dv01": _round(top_book_share),
        "short_term_gap": _round(short_term_gap),
        "short_term_gap_ratio": _round(short_term_gap_ratio),
        "cumulative_gap_3m": _round(cumulative_gap_3m),
        "negative_bucket_count": negative_bucket_count,
        "alerts": alerts,
        "recommendation": recommendation,
        "top_books": top_books,
        "buckets": bucket_payload,
        "notes": [
            "短期缺口汇总 <=1M 与 1-3M 期限阶梯桶。",
            "压力分数综合 DV01 集中度与期限缺口压力。",
        ],
        "warnings": warnings,
    }
