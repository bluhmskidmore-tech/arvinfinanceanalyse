from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)

PMI_SERIES_ID = "M0017126"
SOCIAL_FINANCING_YOY_SERIES_ID = "M5525763"
M2_YOY_SERIES_ID = "M0001385"
CSI300_PE_SERIES_ID = "CA.CSI300_PE"
CN10Y_SERIES_ID = "EMM00166466"

MACRO_WEIGHT_PMI = 0.40
MACRO_WEIGHT_CREDIT_IMPULSE = 0.35
MACRO_WEIGHT_PRICE_SPREAD = 0.25


@dataclass(frozen=True)
class CycleMacroSnapshot:
    macro_score: float | None
    pmi_signal: float | None
    credit_impulse_signal: float | None
    price_spread_signal: float | None
    pmi_value: float | None
    credit_impulse_value: float | None
    price_spread_ppt: float | None
    pmi_ready: bool
    credit_impulse_ready: bool
    price_spread_ready: bool
    evidence: str
    missing_inputs: tuple[str, ...]
    available_inputs: tuple[str, ...]
    lineage: dict[str, object]


def compute_pmi_signal(pmi: float) -> float:
    """PMI 50 is the expansion/contraction boundary; map to [0, 1] without claiming official NBS calibration."""
    return _clamp((pmi - 47.0) / 6.0)


def compute_credit_impulse_signal(*, current_yoy: float, prior_yoy: float) -> tuple[float, float]:
    """Credit impulse proxy: month-over-month change in social-financing YoY (ppt); pending product sign-off.

    Returns ``(signal in [0, 1], impulse_ppt)``.
    """
    impulse_ppt = current_yoy - prior_yoy
    return _clamp((impulse_ppt + 2.0) / 4.0), impulse_ppt


def compute_price_spread_signal(*, pe: float, cn10y: float) -> tuple[float, float | None]:
    """Earnings yield minus 10Y yield (ppt), normalized to [0, 1]."""
    if pe <= 0:
        return 0.0, None
    spread_ppt = (100.0 / pe) - cn10y
    return _clamp((spread_ppt + 1.0) / 5.0), spread_ppt


def compute_macro_score(
    *,
    pmi_signal: float | None,
    credit_impulse_signal: float | None,
    price_spread_signal: float | None,
) -> float | None:
    components: list[tuple[float, float]] = []
    if pmi_signal is not None:
        components.append((MACRO_WEIGHT_PMI, pmi_signal))
    if credit_impulse_signal is not None:
        components.append((MACRO_WEIGHT_CREDIT_IMPULSE, credit_impulse_signal))
    if price_spread_signal is not None:
        components.append((MACRO_WEIGHT_PRICE_SPREAD, price_spread_signal))
    if not components:
        return None
    weight_total = sum(weight for weight, _ in components)
    if weight_total <= 0:
        return None
    return sum(weight * value for weight, value in components) / weight_total


def build_cycle_macro_snapshot(
    *,
    pmi_points: Iterable[tuple[str, float]] | None,
    social_financing_yoy_points: Iterable[tuple[str, float]] | None,
    credit_impulse_series_id: str = SOCIAL_FINANCING_YOY_SERIES_ID,
    pe: float | None,
    cn10y: float | None,
    as_of_date: str,
) -> CycleMacroSnapshot:
    pmi_signal: float | None = None
    pmi_value: float | None = None
    pmi_ready = False
    pmi_lineage: dict[str, object] = {}

    ordered_pmi = _ordered_points(pmi_points, as_of_date=as_of_date)
    if ordered_pmi:
        trade_date, value = ordered_pmi[-1]
        pmi_value = value
        pmi_signal = compute_pmi_signal(value)
        pmi_ready = True
        pmi_lineage = {
            "series_id": PMI_SERIES_ID,
            "trade_date": trade_date,
            "value": value,
        }

    credit_signal: float | None = None
    credit_value: float | None = None
    credit_ready = False
    credit_lineage: dict[str, object] = {}
    credit_pair = _latest_adjacent_month_pair(
        social_financing_yoy_points,
        as_of_date=as_of_date,
    )
    if credit_pair is not None and credit_impulse_series_id in {
        SOCIAL_FINANCING_YOY_SERIES_ID,
        M2_YOY_SERIES_ID,
    }:
        prior_date, prior_yoy, current_date, current_yoy = credit_pair
        credit_signal, credit_value = compute_credit_impulse_signal(
            current_yoy=current_yoy,
            prior_yoy=prior_yoy,
        )
        credit_ready = True
        credit_lineage = {
            "series_id": credit_impulse_series_id,
            "current_reference_date": current_date,
            "prior_reference_date": prior_date,
            "current_yoy": current_yoy,
            "prior_yoy": prior_yoy,
            "impulse_ppt": credit_value,
            "unit": "ppt",
        }

    price_signal: float | None = None
    spread_ppt: float | None = None
    price_ready = False
    price_lineage: dict[str, object] = {}
    if pe is not None and cn10y is not None and pe > 0:
        price_signal, spread_ppt = compute_price_spread_signal(pe=pe, cn10y=cn10y)
        price_ready = True
        price_lineage = {
            "pe_series_id": CSI300_PE_SERIES_ID,
            "cn10y_series_id": CN10Y_SERIES_ID,
            "pe": pe,
            "cn10y": cn10y,
            "spread_ppt": spread_ppt,
        }

    macro_score = compute_macro_score(
        pmi_signal=pmi_signal,
        credit_impulse_signal=credit_signal,
        price_spread_signal=price_signal,
    )
    available = tuple(
        name
        for name, ready in (
            ("PMI", pmi_ready),
            ("credit_impulse", credit_ready),
            ("price_spread", price_ready),
        )
        if ready
    )
    missing = tuple(
        name
        for name, ready in (
            ("PMI", pmi_ready),
            ("credit_impulse", credit_ready),
            ("price_spread", price_ready),
        )
        if not ready
    )
    evidence_parts: list[str] = []
    if pmi_ready and pmi_value is not None:
        evidence_parts.append(f"PMI {pmi_value:.1f} ({PMI_SERIES_ID})")
    if credit_ready and credit_value is not None:
        evidence_parts.append(f"credit_impulse {credit_value:+.2f}ppt ({credit_impulse_series_id})")
    if price_ready and spread_ppt is not None:
        evidence_parts.append(f"price_spread {spread_ppt:.2f}ppt")
    if macro_score is not None:
        evidence_parts.append(f"MacroScore {macro_score:.3f} as of {as_of_date}")
    evidence = "; ".join(evidence_parts) if evidence_parts else "Macro layer inputs are not all landed."

    return CycleMacroSnapshot(
        macro_score=macro_score,
        pmi_signal=pmi_signal,
        credit_impulse_signal=credit_signal,
        price_spread_signal=price_signal,
        pmi_value=pmi_value,
        credit_impulse_value=credit_value,
        price_spread_ppt=spread_ppt,
        pmi_ready=pmi_ready,
        credit_impulse_ready=credit_ready,
        price_spread_ready=price_ready,
        evidence=evidence,
        missing_inputs=missing,
        available_inputs=available,
        lineage={
            "pmi": pmi_lineage,
            "credit_impulse": credit_lineage,
            "price_spread": price_lineage,
            "formula": (
                f"MacroScore = {MACRO_WEIGHT_PMI:.2f}*PMI + "
                f"{MACRO_WEIGHT_CREDIT_IMPULSE:.2f}*CreditImpulse + "
                f"{MACRO_WEIGHT_PRICE_SPREAD:.2f}*PriceSpread"
            ),
        },
    )


def _ordered_points(
    points: Iterable[tuple[str, float]] | None,
    *,
    as_of_date: str | None = None,
) -> list[tuple[str, float]]:
    """Sort ascending by trade_date; drop any point after as_of_date to avoid look-ahead leakage."""
    if not points:
        return []
    rows = ((str(trade_date), float(value)) for trade_date, value in points)
    if as_of_date is not None:
        rows = (row for row in rows if row[0] <= as_of_date)
    return sorted(rows, key=lambda row: row[0])


def _latest_adjacent_month_pair(
    points: Iterable[tuple[str, float]] | None,
    *,
    as_of_date: str,
) -> tuple[str, float, str, float] | None:
    # Fail-closed by design: ANY malformed value, future-dated point, or
    # duplicated month in the input series returns None, which disables the
    # credit-impulse component entirely. compute_macro_score then silently
    # re-normalizes the remaining component weights, so one bad upstream row
    # degrades the macro score composition without an explicit warning.
    # This is intentionally conservative (never compute an impulse from
    # suspect data) but brittle; revisit if upstream data quality allows
    # per-point filtering instead of whole-series rejection.
    if not points:
        return None
    try:
        evaluation_date = date.fromisoformat(as_of_date)
    except ValueError:
        return None

    rows: list[tuple[date, float]] = []
    months: set[tuple[int, int]] = set()
    for raw_date, raw_value in points:
        try:
            reference_date = date.fromisoformat(str(raw_date)[:10])
            value = float(raw_value)
        except (TypeError, ValueError):
            return None
        if reference_date > evaluation_date:
            return None
        month = (reference_date.year, reference_date.month)
        if month in months:
            return None
        months.add(month)
        rows.append((reference_date, value))

    rows.sort(key=lambda row: row[0])
    if len(rows) < 2:
        return None
    prior, current = rows[-2:]
    prior_month = prior[0].year * 12 + prior[0].month
    current_month = current[0].year * 12 + current[0].month
    if current_month - prior_month != 1:
        return None
    return prior[0].isoformat(), prior[1], current[0].isoformat(), current[1]


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))
