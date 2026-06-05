from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

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


def compute_credit_impulse_signal(*, current_yoy: float, prior_yoy: float) -> float:
    """Credit impulse proxy: month-over-month change in social-financing YoY (ppt); pending product sign-off."""
    impulse_ppt = current_yoy - prior_yoy
    return _clamp((impulse_ppt + 2.0) / 4.0), impulse_ppt


def compute_price_spread_signal(*, pe: float, cn10y: float) -> float:
    """Earnings yield minus 10Y yield (ppt), normalized to [0, 1]."""
    if pe <= 0:
        return 0.0
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
    pe: float | None,
    cn10y: float | None,
    as_of_date: str,
) -> CycleMacroSnapshot:
    pmi_signal: float | None = None
    pmi_value: float | None = None
    pmi_ready = False
    pmi_lineage: dict[str, object] = {}

    ordered_pmi = _ordered_points(pmi_points)
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
    ordered_sf = _ordered_points(social_financing_yoy_points)
    if len(ordered_sf) >= 2:
        prior_date, prior_yoy = ordered_sf[-2]
        current_date, current_yoy = ordered_sf[-1]
        credit_signal, credit_value = compute_credit_impulse_signal(
            current_yoy=current_yoy,
            prior_yoy=prior_yoy,
        )
        credit_ready = True
        credit_lineage = {
            "series_id": SOCIAL_FINANCING_YOY_SERIES_ID,
            "current_trade_date": current_date,
            "prior_trade_date": prior_date,
            "current_yoy": current_yoy,
            "prior_yoy": prior_yoy,
            "impulse_ppt": credit_value,
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
        evidence_parts.append(f"credit_impulse {credit_value:+.2f}ppt ({SOCIAL_FINANCING_YOY_SERIES_ID})")
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


def _ordered_points(points: Iterable[tuple[str, float]] | None) -> list[tuple[str, float]]:
    if not points:
        return []
    return sorted(((str(trade_date), float(value)) for trade_date, value in points), key=lambda row: row[0])


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))
