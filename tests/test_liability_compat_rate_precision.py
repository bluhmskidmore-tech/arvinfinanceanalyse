# 回归：liability_analytics_compat.normalize_interbank_rate_decimal 全 Decimal 路径、无 float 损精度。
from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.liability_analytics_compat import normalize_interbank_rate_decimal


def test_percent_inputs_to_decimal_share() -> None:
    assert normalize_interbank_rate_decimal(Decimal("2.55")) == Decimal("0.0255")
    assert normalize_interbank_rate_decimal("3.65") == Decimal("0.0365")


def test_none_and_empty() -> None:
    assert normalize_interbank_rate_decimal(None) is None
    assert normalize_interbank_rate_decimal("") is None


def test_high_precision_no_float_roundtrip() -> None:
    v = Decimal("2.123456789")
    got = normalize_interbank_rate_decimal(v)
    assert got == v / Decimal("100")
    assert got == Decimal("0.02123456789")
