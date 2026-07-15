from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

from backend.app.schemas.pnl import (
    PnlByBusinessYtdUnallocatedBreakdownRow,
    PnlByBusinessYtdUnallocatedItem,
)

TWOPLACES = Decimal("0.01")


class _UnallocatedBreakdownBucket(TypedDict):
    pnl_row_count: int
    total_pnl: Decimal
    abs_pnl: Decimal
    instrument_codes: set[str]


def pnl_by_business_unallocated_reason(matched_rows: list[dict[str, object]]) -> str:
    return "detail_only_business_rule_match" if matched_rows else "no_business_rule_match"


def pnl_by_business_unallocated_item(
    *,
    record: dict[str, object],
    classification: dict[str, object],
    reason_code: str,
    default_source_kind: str,
) -> PnlByBusinessYtdUnallocatedItem:
    total_pnl = _decimal_value(record.get("total_pnl"))
    return PnlByBusinessYtdUnallocatedItem(
        report_date=_norm_text(record.get("report_date") or classification.get("report_date")),
        reason_code=reason_code,
        source_kind=_norm_text(record.get("source_kind")) or default_source_kind,
        instrument_code=_norm_text(
            record.get("instrument_code")
            or record.get("bond_code")
            or classification.get("instrument_code")
        ),
        portfolio_name=_norm_text(record.get("portfolio_name") or classification.get("portfolio_name")),
        cost_center=_norm_text(record.get("cost_center") or classification.get("cost_center")),
        invest_type_std=_norm_text(record.get("invest_type_std") or classification.get("invest_type_std")),
        accounting_basis=_norm_text(record.get("accounting_basis") or classification.get("accounting_basis")),
        currency_basis=(
            _norm_text(
                record.get("currency_basis")
                or classification.get("currency_basis")
                or classification.get("currency_code")
            )
            or "CNY"
        ),
        interest_income_514=_decimal_value(record.get("interest_income_514") or record.get("interest_income")),
        fair_value_change_516=_decimal_value(record.get("fair_value_change_516") or record.get("fair_value_change")),
        capital_gain_517=_decimal_value(record.get("capital_gain_517") or record.get("capital_gain")),
        manual_adjustment=_decimal_value(record.get("manual_adjustment")),
        total_pnl=total_pnl,
        abs_pnl=abs(total_pnl),
    )


def normalize_pnl_by_business_unallocated_item(
    item: PnlByBusinessYtdUnallocatedItem,
) -> PnlByBusinessYtdUnallocatedItem:
    total_pnl = _quantize_decimal(item.total_pnl)
    return item.model_copy(
        update={
            "interest_income_514": _quantize_decimal(item.interest_income_514),
            "fair_value_change_516": _quantize_decimal(item.fair_value_change_516),
            "capital_gain_517": _quantize_decimal(item.capital_gain_517),
            "manual_adjustment": _quantize_decimal(item.manual_adjustment),
            "total_pnl": total_pnl,
            "abs_pnl": abs(total_pnl),
        }
    )


def pnl_by_business_unallocated_breakdown(
    items: list[PnlByBusinessYtdUnallocatedItem],
) -> list[PnlByBusinessYtdUnallocatedBreakdownRow]:
    grouped: dict[tuple[str, str, str, str, str, str], _UnallocatedBreakdownBucket] = {}
    for item in items:
        key = (
            item.reason_code,
            item.source_kind,
            item.invest_type_std,
            item.accounting_basis,
            item.portfolio_name,
            item.cost_center,
        )
        bucket = grouped.setdefault(
            key,
            {
                "pnl_row_count": 0,
                "total_pnl": Decimal("0"),
                "abs_pnl": Decimal("0"),
                "instrument_codes": set(),
            },
        )
        bucket["pnl_row_count"] = int(bucket["pnl_row_count"]) + 1
        bucket["total_pnl"] = Decimal(str(bucket["total_pnl"])) + item.total_pnl
        bucket["abs_pnl"] = Decimal(str(bucket["abs_pnl"])) + item.abs_pnl
        if item.instrument_code:
            bucket["instrument_codes"].add(item.instrument_code)

    rows = [
        PnlByBusinessYtdUnallocatedBreakdownRow(
            reason_code=key[0],
            source_kind=key[1],
            invest_type_std=key[2],
            accounting_basis=key[3],
            portfolio_name=key[4],
            cost_center=key[5],
            pnl_row_count=int(bucket["pnl_row_count"]),
            total_pnl=_quantize_decimal(Decimal(str(bucket["total_pnl"]))),
            abs_pnl=_quantize_decimal(Decimal(str(bucket["abs_pnl"]))),
            sample_instrument_codes=sorted(str(code) for code in bucket["instrument_codes"])[:5],
        )
        for key, bucket in grouped.items()
    ]
    return sorted(
        rows,
        key=lambda row: (
            -row.abs_pnl,
            row.reason_code,
            row.source_kind,
            row.invest_type_std,
            row.accounting_basis,
            row.portfolio_name,
            row.cost_center,
        ),
    )


def _decimal_value(value: object) -> Decimal:
    return Decimal(str(value or "0"))


def _norm_text(value: object) -> str:
    return str(value or "").strip()


def _quantize_decimal(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
