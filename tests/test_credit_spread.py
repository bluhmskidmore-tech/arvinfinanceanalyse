from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.credit_spread import compute_credit_spread_profile


def test_credit_spread_dv01_uses_face_value_when_available() -> None:
    report_date = date(2026, 1, 1)
    payload = compute_credit_spread_profile(
        [
            {
                "bond_code": "CB-FACE",
                "market_value": Decimal("500000"),
                "face_value": Decimal("1000000"),
                "coupon_rate": Decimal("0.0300"),
                "yield_to_maturity": Decimal("0.0300"),
                "maturity_date": date(2031, 1, 1),
                "report_date": report_date,
                "sub_type": "企业债",
                "agency_rating": "AAA",
            }
        ],
        report_date=report_date,
        wind_metrics={"CB-FACE": {"mod_duration": Decimal("2.5")}},
    )

    assert payload["spread_dv01"] == Decimal("250")
    assert payload["position_metrics"][0]["dv01"] == Decimal("250")
    assert payload["position_metrics"][0]["dv01"] != Decimal("125")
