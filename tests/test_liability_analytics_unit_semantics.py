from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.liability_analytics_compat import (
    build_v1_bucket_amount_payload,
    build_v1_name_amount_payload,
)
from backend.app.schemas.liability_analytics import LiabilityYieldKpi


def test_liability_yield_kpi_formats_ratio_input_as_percent_display() -> None:
    kpi = LiabilityYieldKpi(
        asset_yield=0.024842762957435982,
        liability_cost=0.01747551450275207,
        market_liability_cost=0.015898081549606872,
        nim=0.00894468140782911,
    )

    assert kpi.asset_yield is not None
    assert kpi.asset_yield.display == "+2.48%"
    assert kpi.nim is not None
    assert kpi.nim.raw == pytest.approx(0.00894468140782911)
    assert kpi.nim.display == "+0.89%"


def test_v1_name_amount_payload_emits_ratio_pct_raw() -> None:
    payload = build_v1_name_amount_payload(
        {
            "Interbank": Decimal("670"),
            "Issued": Decimal("200"),
        }
    )

    assert payload == [
        {"name": "Interbank", "amount": 670.0, "pct": pytest.approx(0.7701, abs=1e-10)},
        {"name": "Issued", "amount": 200.0, "pct": pytest.approx(0.2299, abs=1e-10)},
    ]


def test_v1_bucket_amount_payload_emits_ratio_pct_raw() -> None:
    payload = build_v1_bucket_amount_payload(
        {
            "0-3M": Decimal("520"),
            "3-6M": Decimal("100"),
            "1-3Y": Decimal("200"),
            "3-5Y": Decimal("50"),
        }
    )

    assert payload[0] == {"bucket": "0-3M", "amount": 520.0, "pct": pytest.approx(0.5977, abs=1e-10)}
    assert payload[1] == {"bucket": "3-6M", "amount": 100.0, "pct": pytest.approx(0.1149, abs=1e-10)}
    assert payload[3] == {"bucket": "1-3Y", "amount": 200.0, "pct": pytest.approx(0.2299, abs=1e-10)}
    assert payload[4] == {"bucket": "3-5Y", "amount": 50.0, "pct": pytest.approx(0.0575, abs=1e-10)}
