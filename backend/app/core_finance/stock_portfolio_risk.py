"""Descriptive risk metrics for a stock target-weight shadow portfolio.

This module deliberately stops before business-limit evaluation.  It accepts
long-only target weights, validates the complete input set, and returns
descriptive exposure and concentration metrics.  An approved risk policy is a
separate governed input, so the limit gate is always blocked here.

All ratios use the ``0..1`` scale and all arithmetic uses :class:`Decimal`.
Invalid or incomplete input fails closed: descriptive metrics are ``None`` and
the payload carries stable reason codes.  No bond-risk or VaR implementation is
reused because those formulas have different units and semantics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

ZERO = Decimal("0")
ONE = Decimal("1")
HHI_INDEX_SCALE = Decimal("10000")

LIMIT_GATE_STATUS = "blocked_missing_approved_policy"
LIMIT_GATE_REASON_CODE = "missing_approved_policy"

_METRIC_NULLS: dict[str, object] = {
    "target_weight_sum_ratio": None,
    "gross_exposure_ratio": None,
    "net_exposure_ratio": None,
    "cash_ratio": None,
    "closure_residual_ratio": None,
    "top1_weight_ratio": None,
    "top5_weight_ratio": None,
    "hhi_ratio": None,
    "hhi_index": None,
    "sector_exposures": None,
}


def compute_stock_portfolio_risk(
    target_lines: Sequence[Mapping[str, object]] | None,
) -> dict[str, object]:
    """Compute descriptive risk for stock target weights.

    Each target line must contain a non-empty ``stock_code`` and
    ``sector_name`` plus a finite ``target_weight`` in the inclusive range
    ``[0, 1]``.  Stock codes are unique after trimming and upper-casing.

    ``top1_weight_ratio`` and ``top5_weight_ratio`` are NAV-relative target
    weights.  HHI is calculated on the invested book, so each stock's HHI
    share is ``target_weight / gross_exposure``.  ``hhi_ratio`` is on the
    ``0..1`` scale and ``hhi_index`` is the same value multiplied by 10,000.
    Cash is excluded from HHI and sector exposures.
    """

    lines = list(target_lines or ())
    if not lines:
        return _unavailable_payload(
            input_line_count=0,
            reason_codes=["empty_target_lines"],
        )

    reason_codes: list[str] = []
    normalized: list[tuple[str, str, Decimal]] = []
    seen_codes: set[str] = set()

    for line in lines:
        if not isinstance(line, Mapping):
            _append_reason(reason_codes, "target_line_not_mapping")
            continue

        stock_code, stock_code_reason = _required_string(
            line.get("stock_code"),
            missing_reason="missing_stock_code",
            invalid_reason="invalid_stock_code",
        )
        sector_name, sector_name_reason = _required_string(
            line.get("sector_name"),
            missing_reason="missing_sector_name",
            invalid_reason="invalid_sector_name",
        )
        raw_weight = line.get("target_weight")

        if stock_code_reason is not None:
            _append_reason(reason_codes, stock_code_reason)
        if stock_code is not None:
            normalized_code = stock_code.upper()
            if normalized_code in seen_codes:
                _append_reason(reason_codes, "duplicate_stock_code")
            seen_codes.add(normalized_code)

        if sector_name_reason is not None:
            _append_reason(reason_codes, sector_name_reason)

        if _is_missing(raw_weight):
            weight = None
            _append_reason(reason_codes, "missing_target_weight")
        else:
            weight = _finite_decimal(raw_weight)
            if weight is None:
                _append_reason(reason_codes, "invalid_target_weight")
            elif weight < ZERO or weight > ONE:
                _append_reason(reason_codes, "target_weight_out_of_range")

        if (
            stock_code is not None
            and sector_name is not None
            and weight is not None
            and ZERO <= weight <= ONE
        ):
            normalized.append((stock_code.upper(), sector_name, weight))

    if reason_codes:
        return _unavailable_payload(
            input_line_count=len(lines),
            reason_codes=reason_codes,
        )

    target_weight_sum = sum((weight for _code, _sector, weight in normalized), ZERO)
    if target_weight_sum > ONE:
        return _unavailable_payload(
            input_line_count=len(lines),
            reason_codes=["total_target_weight_exceeds_one"],
        )

    # The minimum release is long-only, so gross and net exposure are equal.
    gross_exposure = sum((abs(weight) for _code, _sector, weight in normalized), ZERO)
    net_exposure = target_weight_sum
    cash_ratio = ONE - net_exposure
    # Identity self-check, not an independent reconciliation: cash_ratio is defined
    # as ONE - net_exposure, so the residual is zero by construction under exact
    # Decimal arithmetic. It only guards against a future refactor that derives
    # cash from another source; the range checks below are the real validation.
    closure_residual = ONE - (net_exposure + cash_ratio)
    if closure_residual != ZERO or cash_ratio < ZERO or cash_ratio > ONE:
        return _unavailable_payload(
            input_line_count=len(lines),
            reason_codes=["weight_and_cash_closure_failed"],
        )

    ranked_weights = sorted(
        (weight for _code, _sector, weight in normalized),
        reverse=True,
    )
    top1_weight = ranked_weights[0]
    top5_weight = sum(ranked_weights[:5], ZERO)

    sector_totals: dict[str, Decimal] = {}
    for _stock_code, sector_name, weight in normalized:
        sector_totals[sector_name] = sector_totals.get(sector_name, ZERO) + weight
    sector_exposures = [
        {
            "sector_name": sector_name,
            "exposure_ratio": sector_totals[sector_name],
        }
        for sector_name in sorted(sector_totals)
    ]
    if sum(sector_totals.values(), ZERO) != net_exposure:
        return _unavailable_payload(
            input_line_count=len(lines),
            reason_codes=["sector_exposure_reconciliation_failed"],
        )

    common = {
        "input_line_count": len(lines),
        "position_count": len(normalized),
        "observation_only": True,
        "formal_use_allowed": False,
        "limit_gate": _blocked_limit_gate(),
        "target_weight_sum_ratio": target_weight_sum,
        "gross_exposure_ratio": gross_exposure,
        "net_exposure_ratio": net_exposure,
        "cash_ratio": cash_ratio,
        "closure_residual_ratio": closure_residual,
        "top1_weight_ratio": top1_weight,
        "top5_weight_ratio": top5_weight,
        "sector_exposures": sector_exposures,
    }

    if gross_exposure == ZERO:
        return {
            "data_status": "partial",
            "reason_codes": ["zero_invested_weight"],
            **common,
            "hhi_ratio": None,
            "hhi_index": None,
        }

    hhi_ratio = sum(
        ((weight / gross_exposure) ** 2 for weight in ranked_weights),
        ZERO,
    )
    if hhi_ratio <= ZERO or hhi_ratio > ONE:
        return _unavailable_payload(
            input_line_count=len(lines),
            reason_codes=["hhi_scale_validation_failed"],
        )
    return {
        "data_status": "complete",
        "reason_codes": [],
        **common,
        "hhi_ratio": hhi_ratio,
        "hhi_index": hhi_ratio * HHI_INDEX_SCALE,
    }


def _unavailable_payload(
    *,
    input_line_count: int,
    reason_codes: list[str],
) -> dict[str, object]:
    return {
        "data_status": "unavailable",
        "reason_codes": reason_codes,
        "input_line_count": input_line_count,
        "position_count": None,
        "observation_only": True,
        "formal_use_allowed": False,
        **_METRIC_NULLS,
        "limit_gate": _blocked_limit_gate(),
    }


def _blocked_limit_gate() -> dict[str, object]:
    return {
        "status": LIMIT_GATE_STATUS,
        "reason_code": LIMIT_GATE_REASON_CODE,
        "approved_policy_present": False,
    }


def _required_string(
    value: object,
    *,
    missing_reason: str,
    invalid_reason: str,
) -> tuple[str | None, str | None]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, missing_reason
    if not isinstance(value, str):
        return None, invalid_reason
    return value.strip(), None


def _is_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _finite_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _append_reason(reason_codes: list[str], reason_code: str) -> None:
    if reason_code not in reason_codes:
        reason_codes.append(reason_code)
