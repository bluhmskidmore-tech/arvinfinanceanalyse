from __future__ import annotations

from datetime import date

from backend.app.core_finance.macro.economic_cycle import compute_economic_cycle


def _row(
    trade_date: date,
    *,
    pmi: float | None,
    cpi_yoy: float = 1.5,
    ppi_yoy: float = 0.5,
    m2_yoy: float = 8.0,
    social_financing_yoy: float = 9.0,
    term_spread_10y_1y: float = 60.0,
) -> dict[str, object]:
    return {
        "trade_date": trade_date,
        "pmi": pmi,
        "cpi_yoy": cpi_yoy,
        "ppi_yoy": ppi_yoy,
        "m2_yoy": m2_yoy,
        "social_financing_yoy": social_financing_yoy,
        "term_spread_10y_1y": term_spread_10y_1y,
    }


def test_economic_cycle_warns_missing_and_differs_from_zero_fill() -> None:
    rows_with_missing = [
        _row(date(2026, 6, 30), pmi=52.0),
        _row(date(2026, 5, 31), pmi=None),
        _row(date(2026, 4, 30), pmi=51.0),
        _row(date(2026, 3, 31), pmi=50.0),
        _row(date(2026, 2, 28), pmi=49.0),
        _row(date(2026, 1, 31), pmi=48.0),
    ]
    rows_with_zero = [{**row, "pmi": 0.0 if row.get("pmi") is None else row.get("pmi")} for row in rows_with_missing]

    missing_payload = compute_economic_cycle(rows_with_missing, report_date=date(2026, 6, 30))
    zero_payload = compute_economic_cycle(rows_with_zero, report_date=date(2026, 6, 30))

    assert missing_payload["data_status"] == "degraded"
    assert "PMI_MISSING" in missing_payload["warnings"]
    assert missing_payload["growth_score"] != zero_payload["growth_score"]
