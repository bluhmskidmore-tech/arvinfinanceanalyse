"""DV01 portfolio calculations for bond analytics read models."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.app.core_finance.bond_analytics.common import safe_decimal

ZERO = Decimal("0")


def parse_dv01_shocks(value: object) -> list[Decimal]:
    shocks: list[Decimal] = []
    for raw in str(value or "1,10,25,50").split(","):
        text = raw.strip()
        if not text:
            continue
        shock = safe_decimal(text).copy_abs()
        if shock == ZERO:
            continue
        if shock not in shocks:
            shocks.append(shock)
    return shocks or [Decimal("1"), Decimal("10"), Decimal("25"), Decimal("50")]


def expand_parallel_shocks(shocks: list[Decimal]) -> list[Decimal]:
    expanded: list[Decimal] = []
    for shock in shocks:
        expanded.extend([shock, -shock])
    return expanded


def build_dv01_shock_scenario_payloads(
    *,
    total_dv01: Decimal,
    shocks: list[Decimal],
) -> list[dict[str, object]]:
    return [
        {
            "scenario_name": f"rate_{'up' if shock > ZERO else 'down'}_{abs(shock)}bp",
            "shock_bp": shock,
            "estimated_pnl": -(total_dv01 * shock),
        }
        for shock in expand_parallel_shocks(shocks)
    ]


def face_weighted_modified_duration(rows: list[dict[str, object]]) -> Decimal:
    total_face_value = sum((safe_decimal(row.get("face_value")) for row in rows), ZERO)
    if total_face_value == ZERO:
        return ZERO
    return (
        sum(
            (
                safe_decimal(row.get("face_value")) * safe_decimal(row.get("modified_duration"))
                for row in rows
            ),
            ZERO,
        )
        / total_face_value
    )


def total_abs_dv01(rows: list[dict[str, object]]) -> Decimal:
    return sum((safe_decimal(row.get("dv01")).copy_abs() for row in rows), ZERO)


def dv01_share(dv01: Decimal, total_abs_dv01: Decimal) -> Decimal:
    denominator = total_abs_dv01.copy_abs()
    if denominator == ZERO:
        return ZERO
    return abs(dv01) / denominator


def build_dv01_tenor_bucket_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        tenor = str(row.get("tenor_bucket") or "UNKNOWN").strip() or "UNKNOWN"
        grouped.setdefault(tenor, []).append(row)

    result: list[dict[str, object]] = []
    for tenor, bucket_rows in grouped.items():
        face_value = sum((safe_decimal(row.get("face_value")) for row in bucket_rows), ZERO)
        market_value = sum((safe_decimal(row.get("market_value")) for row in bucket_rows), ZERO)
        dv01 = sum((safe_decimal(row.get("dv01")) for row in bucket_rows), ZERO)
        result.append(
            {
                "tenor_bucket": tenor,
                "face_value": face_value,
                "market_value": market_value,
                "face_weighted_modified_duration": face_weighted_modified_duration(bucket_rows),
                "dv01": dv01,
                "dv01_share": dv01_share(dv01, total_abs_dv01),
                "position_count": len(bucket_rows),
            }
        )
    return sorted(result, key=lambda row: (safe_decimal(row["dv01"]).copy_abs(), str(row["tenor_bucket"])), reverse=True)


def build_dv01_top_bond_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
    top_n: int,
) -> list[dict[str, object]]:
    ordered = sorted(
        rows,
        key=lambda row: (safe_decimal(row.get("dv01")).copy_abs(), str(row.get("instrument_code") or "")),
        reverse=True,
    )
    return [
        {
            "instrument_code": str(row.get("instrument_code") or ""),
            "instrument_name": _optional_text(row.get("instrument_name")),
            "issuer_name": _optional_text(row.get("issuer_name")),
            "rating": _optional_text(row.get("rating")),
            "tenor_bucket": str(row.get("tenor_bucket") or ""),
            "accounting_class": str(row.get("accounting_class") or ""),
            "face_value": safe_decimal(row.get("face_value")),
            "market_value": safe_decimal(row.get("market_value")),
            "modified_duration": safe_decimal(row.get("modified_duration")),
            "dv01": safe_decimal(row.get("dv01")),
            "dv01_share": dv01_share(safe_decimal(row.get("dv01")), total_abs_dv01),
        }
        for row in ordered[:top_n]
    ]


def build_dv01_top_issuer_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
    top_n: int,
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        issuer = str(row.get("issuer_name") or "UNKNOWN").strip() or "UNKNOWN"
        grouped.setdefault(issuer, []).append(row)

    items: list[dict[str, object]] = []
    for issuer, issuer_rows in grouped.items():
        face_value = sum((safe_decimal(row.get("face_value")) for row in issuer_rows), ZERO)
        market_value = sum((safe_decimal(row.get("market_value")) for row in issuer_rows), ZERO)
        dv01 = sum((safe_decimal(row.get("dv01")) for row in issuer_rows), ZERO)
        items.append(
            {
                "issuer_name": issuer,
                "face_value": face_value,
                "market_value": market_value,
                "face_weighted_modified_duration": face_weighted_modified_duration(issuer_rows),
                "dv01": dv01,
                "dv01_share": dv01_share(dv01, total_abs_dv01),
                "position_count": len(issuer_rows),
            }
        )
    return sorted(items, key=lambda row: (safe_decimal(row["dv01"]).copy_abs(), str(row["issuer_name"])), reverse=True)[:top_n]


def build_dv01_reconciliation_payloads(
    rows: list[dict[str, object]],
    *,
    total_abs_dv01: Decimal,
) -> list[dict[str, object]]:
    ordered = sorted(
        rows,
        key=lambda row: (safe_decimal(row.get("dv01")).copy_abs(), str(row.get("instrument_code") or "")),
        reverse=True,
    )
    return [
        {
            "report_date": row.get("report_date"),
            "instrument_code": str(row.get("instrument_code") or ""),
            "instrument_name": _optional_text(row.get("instrument_name")),
            "accounting_class": str(row.get("accounting_class") or ""),
            "issuer_name": _optional_text(row.get("issuer_name")),
            "rating": _optional_text(row.get("rating")),
            "tenor_bucket": str(row.get("tenor_bucket") or ""),
            "face_value": safe_decimal(row.get("face_value")),
            "market_value": safe_decimal(row.get("market_value")),
            "modified_duration": safe_decimal(row.get("modified_duration")),
            "dv01": safe_decimal(row.get("dv01")),
            "dv01_share": dv01_share(safe_decimal(row.get("dv01")), total_abs_dv01),
            "source_version": str(row.get("source_version") or ""),
            "rule_version": str(row.get("rule_version") or ""),
            "trace_id": str(row.get("trace_id") or ""),
        }
        for row in ordered
    ]


def dv01_scope_summary(rows: list[dict[str, object]]) -> dict[str, Decimal]:
    return {
        "total_face_value": sum((safe_decimal(row.get("face_value")) for row in rows), ZERO),
        "total_market_value": sum((safe_decimal(row.get("market_value")) for row in rows), ZERO),
        "face_weighted_modified_duration": face_weighted_modified_duration(rows),
        "total_dv01": sum((safe_decimal(row.get("dv01")) for row in rows), ZERO),
    }


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
