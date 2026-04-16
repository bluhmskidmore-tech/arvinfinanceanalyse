from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.core_finance import liability_analytics_compat as compat
from backend.app.core_finance.liability_analytics_compat import (
    classify_counterparty,
    classify_monthly_counterparty,
    coerce_date,
    is_self_counterparty,
    maturity_bucket,
    monthly_v1_bucket_name,
    normalize_bond_rate_decimal,
    normalize_interbank_rate_decimal,
    weighted_rate,
)


def test_coerce_date_accepts_date_datetime_and_iso_text() -> None:
    assert coerce_date(date(2026, 2, 26)) == date(2026, 2, 26)
    assert coerce_date(datetime(2026, 2, 26, 9, 30)) == date(2026, 2, 26)
    assert coerce_date("2026-02-26") == date(2026, 2, 26)
    assert coerce_date("2026-02-26T09:30:00") == date(2026, 2, 26)
    assert coerce_date("") is None
    assert coerce_date(None) is None


def test_normalize_bond_rate_decimal_matches_liability_v1_behavior() -> None:
    assert normalize_bond_rate_decimal(None) is None
    assert normalize_bond_rate_decimal("") is None
    assert normalize_bond_rate_decimal("2.5") == Decimal("0.025")
    assert normalize_bond_rate_decimal("0.03") == Decimal("0.03")
    assert normalize_bond_rate_decimal("100") == Decimal("1")


def test_normalize_interbank_rate_decimal_always_treats_input_as_percent() -> None:
    assert normalize_interbank_rate_decimal(None) is None
    assert normalize_interbank_rate_decimal("2.5") == Decimal("0.025")
    assert normalize_interbank_rate_decimal("0.8") == Decimal("0.008")


def test_normalize_interbank_rate_decimal_consumes_rate_units_pct_to_decimal(monkeypatch) -> None:
    calls: list[float] = []

    def fake_pct_to_decimal(value: float) -> float:
        calls.append(value)
        return 0.1234

    monkeypatch.setattr(compat, "pct_to_decimal", fake_pct_to_decimal)

    assert compat.normalize_interbank_rate_decimal("2.5") == Decimal("0.1234")
    assert calls == [2.5]


def test_weighted_rate_ignores_zero_amount_and_missing_rate() -> None:
    pairs = [
        (Decimal("100"), Decimal("0.02")),
        (Decimal("0"), Decimal("0.03")),
        (Decimal("50"), None),
    ]
    assert weighted_rate(pairs) == Decimal("0.02")
    assert weighted_rate([(Decimal("0"), Decimal("0.01"))]) is None


def test_maturity_bucket_uses_v1_day_boundaries_and_missing_default() -> None:
    report_date = date(2026, 2, 26)
    assert maturity_bucket(report_date, None) == "\u0033\u4e2a\u6708\u4ee5\u5185"
    assert maturity_bucket(report_date, "2026-02-25") == "\u5df2\u5230\u671f/\u903e\u671f"
    assert maturity_bucket(report_date, "2026-05-27") == "\u0033\u4e2a\u6708\u4ee5\u5185"
    assert maturity_bucket(report_date, "2026-05-28") == "\u0033\u002d\u0036\u4e2a\u6708"
    assert maturity_bucket(report_date, "2026-08-25") == "\u0033\u002d\u0036\u4e2a\u6708"
    assert maturity_bucket(report_date, "2026-08-26") == "\u0036\u002d\u0031\u0032\u4e2a\u6708"
    assert maturity_bucket(report_date, "2027-02-26") == "\u0036\u002d\u0031\u0032\u4e2a\u6708"
    assert maturity_bucket(report_date, "2027-02-27") == "\u0031\u002d\u0032\u5e74"


def test_monthly_v1_bucket_name_uses_v1_bucket_scheme() -> None:
    report_date = date(2026, 2, 26)
    assert monthly_v1_bucket_name(report_date, None) == "0-3M"
    assert monthly_v1_bucket_name(report_date, "2026-02-25") == "Matured"
    assert monthly_v1_bucket_name(report_date, "2026-05-27") == "0-3M"
    assert monthly_v1_bucket_name(report_date, "2026-05-28") == "3-6M"
    assert monthly_v1_bucket_name(report_date, "2027-02-26") == "6-12M"
    assert monthly_v1_bucket_name(report_date, "2029-02-25") == "1-3Y"


def test_counterparty_classifiers_match_v1_labels() -> None:
    assert classify_counterparty("ABC Bank") == "Bank"
    assert classify_counterparty("某某银行股份有限公司") == "Bank"
    assert classify_counterparty("某某基金管理公司") == "Non-Bank FI"
    assert classify_counterparty("某某财务公司") == "Corporate/Other"

    assert classify_monthly_counterparty("") == "Other"
    assert classify_monthly_counterparty("某某银行股份有限公司") == "Bank"
    assert classify_monthly_counterparty("某某财务公司") == "NonBank"


def test_is_self_counterparty_uses_contains_rule() -> None:
    assert is_self_counterparty("中国银行股份有限公司青岛银行合作部") is True
    assert is_self_counterparty("青岛银行股份有限公司") is True
    assert is_self_counterparty("ALPHA BANK") is False
