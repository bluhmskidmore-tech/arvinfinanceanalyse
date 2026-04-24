from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.core_finance import liability_analytics_compat as compat
from backend.app.core_finance.liability_analytics_compat import (
    classify_counterparty,
    classify_monthly_counterparty,
    coerce_date,
    compute_liabilities_monthly,
    compute_liability_risk_buckets,
    compute_liability_yield_metrics,
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


def test_compute_liability_risk_buckets_matches_v1_bucket_shape_and_order() -> None:
    payload = compute_liability_risk_buckets(
        "2026-02-26",
        zqtz_rows=[
            {
                "is_issuance_like": True,
                "bond_type": "商业银行债",
                "market_value_native": "200",
                "face_value_native": "180",
                "maturity_date": "2027-03-15",
            }
        ],
        tyw_rows=[
            {
                "is_asset_side": False,
                "principal_native": "500",
                "product_type": "同业存放",
                "maturity_date": "2026-03-15",
            },
            {
                "is_asset_side": False,
                "principal_native": "100",
                "product_type": "卖出回购证券",
                "maturity_date": "2026-07-01",
            },
            {
                "is_asset_side": False,
                "principal_native": "20",
                "product_type": "卖出回购票据",
                "maturity_date": None,
            },
            {
                "is_asset_side": False,
                "principal_native": "50",
                "product_type": "同业拆入",
                "maturity_date": "2029-02-26",
            },
        ],
    )

    assert payload["liabilities_structure"] == [
        {"name": "同业负债", "amount": 670.0, "pct": 0.7701},
        {"name": "发行负债", "amount": 200.0, "pct": 0.2299},
    ]
    assert payload["interbank_liabilities_structure"] == [
        {"name": "卖出回购票据", "amount": 20.0, "pct": 0.0299},
        {"name": "卖出回购证券", "amount": 100.0, "pct": 0.1493},
        {"name": "同业存放", "amount": 500.0, "pct": 0.7463},
        {"name": "同业拆入", "amount": 50.0, "pct": 0.0746},
    ]
    assert [item["bucket"] for item in payload["liabilities_term_buckets"]] == [
        "0-3M",
        "3-6M",
        "6-12M",
        "1-3Y",
        "3-5Y",
        "5-10Y",
        "10Y+",
        "Matured",
    ]
    assert payload["liabilities_term_buckets"][0] == {
        "bucket": "0-3M",
        "amount": 520.0,
        "pct": 0.5977,
    }
    assert payload["liabilities_term_buckets"][1] == {
        "bucket": "3-6M",
        "amount": 100.0,
        "pct": 0.1149,
    }
    assert payload["liabilities_term_buckets"][3] == {
        "bucket": "1-3Y",
        "amount": 200.0,
        "pct": 0.2299,
    }
    assert payload["liabilities_term_buckets"][4:] == [
        {"bucket": "3-5Y", "amount": 50.0, "pct": 0.0575},
        {"bucket": "5-10Y", "amount": 0.0, "pct": 0.0},
        {"bucket": "10Y+", "amount": 0.0, "pct": 0.0},
        {"bucket": "Matured", "amount": 0.0, "pct": 0.0},
    ]
    assert all("amount_yi" not in item for item in payload["liabilities_structure"])
    assert all("amount_yi" not in item for item in payload["liabilities_term_buckets"])


def test_compute_liability_yield_metrics_uses_v1_face_value_for_market_ncd_weight() -> None:
    payload = compute_liability_yield_metrics(
        "2026-02-26",
        zqtz_rows=[
            {
                "is_issuance_like": True,
                "bond_type": "同业存单",
                "instrument_name": "NCD-1",
                "market_value_native": "200",
                "face_value_native": "100",
                "coupon_rate": "4.0",
            }
        ],
        tyw_rows=[
            {
                "is_asset_side": False,
                "principal_native": "100",
                "funding_cost_rate": "0",
            }
        ],
    )

    assert payload["kpi"] == {
        "asset_yield": None,
        "liability_cost": 0.02666666666666667,
        "market_liability_cost": 0.02,
        "nim": None,
    }


def test_compute_liability_yield_metrics_falls_back_to_interest_rate_for_bond_assets() -> None:
    payload = compute_liability_yield_metrics(
        "2026-02-26",
        zqtz_rows=[
            {
                "is_issuance_like": False,
                "asset_class": "可供出售类资产",
                "market_value_native": "100",
                "coupon_rate": None,
                "ytm_value": None,
                "interest_rate": "2.5",
            }
        ],
        tyw_rows=[],
    )

    assert payload["kpi"] == {
        "asset_yield": 0.025,
        "liability_cost": None,
        "market_liability_cost": None,
        "nim": None,
    }


def test_compute_liability_yield_metrics_uses_amortized_cost_for_htm_asset_weight() -> None:
    payload = compute_liability_yield_metrics(
        "2026-02-26",
        zqtz_rows=[
            {
                "is_issuance_like": False,
                "asset_class": "持有至到期类资产",
                "market_value_native": "200",
                "amortized_cost_native": "100",
                "coupon_rate": "4.0",
                "ytm_value": None,
            }
        ],
        tyw_rows=[
            {
                "is_asset_side": True,
                "principal_native": "100",
                "funding_cost_rate": "0",
            }
        ],
    )

    assert payload["kpi"] == {
        "asset_yield": 0.02,
        "liability_cost": None,
        "market_liability_cost": None,
        "nim": None,
    }


def test_compute_liabilities_monthly_keeps_v1_mom_fields_null() -> None:
    payload = compute_liabilities_monthly(
        2026,
        zqtz_rows=[
            {
                "report_date": "2026-01-31",
                "bond_type": "同业存单",
                "is_issuance_like": True,
                "amortized_cost_native": "100",
                "coupon_rate": "4.0",
                "maturity_date": "2026-04-01",
            },
            {
                "report_date": "2026-02-28",
                "bond_type": "同业存单",
                "is_issuance_like": True,
                "amortized_cost_native": "120",
                "coupon_rate": "4.0",
                "maturity_date": "2026-05-01",
            },
        ],
        tyw_rows=[],
    )

    assert [item["month"] for item in payload["months"]] == ["2026-01", "2026-02"]
    assert payload["months"][0]["mom_change"] is None
    assert payload["months"][0]["mom_change_pct"] is None
    assert payload["months"][1]["mom_change"] is None
    assert payload["months"][1]["mom_change_pct"] is None
