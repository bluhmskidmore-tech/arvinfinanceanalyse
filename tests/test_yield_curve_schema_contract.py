from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from backend.app.schemas.yield_curve import YieldCurvePoint, YieldCurveSnapshot


def test_yield_curve_point_equality_and_attributes():
    a = YieldCurvePoint(tenor="1Y", rate_pct=Decimal("2.5"))
    b = YieldCurvePoint(tenor="1Y", rate_pct=Decimal("2.5"))
    c = YieldCurvePoint(tenor="2Y", rate_pct=Decimal("2.5"))
    assert a == b
    assert a != c
    assert a.tenor == "1Y"
    assert a.rate_pct == Decimal("2.5")


def test_yield_curve_snapshot_holds_expected_fields():
    p1 = YieldCurvePoint(tenor="1Y", rate_pct=Decimal("2.0"))
    p2 = YieldCurvePoint(tenor="10Y", rate_pct=Decimal("2.8"))
    snap = YieldCurveSnapshot(
        curve_type="gov",
        trade_date="2026-04-11",
        points=[p1, p2],
        vendor_name="choice",
        vendor_version="vv1",
        source_version="sv1",
    )
    assert snap.curve_type == "gov"
    assert snap.trade_date == "2026-04-11"
    assert snap.points == [p1, p2]
    assert snap.vendor_name == "choice"
    assert snap.vendor_version == "vv1"
    assert snap.source_version == "sv1"


def test_yield_curve_frozen_point_rejects_mutation():
    p = YieldCurvePoint(tenor="1Y", rate_pct=Decimal("1"))
    with pytest.raises(FrozenInstanceError):
        p.tenor = "2Y"  # type: ignore[misc]
