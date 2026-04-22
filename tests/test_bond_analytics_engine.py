from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_analytics import common
from tests.helpers import load_module


def _module():
    return load_module(
        "backend.app.core_finance.bond_analytics.engine",
        "backend/app/core_finance/bond_analytics/engine.py",
    )


def test_compute_bond_analytics_rows_filters_issuance_like_and_derives_credit_metrics() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "BOND-001",
            "instrument_name": "企业债A",
            "portfolio_name": "组合A",
            "cost_center": "CC1",
            "account_category": "可供出售类资产",
            "asset_class": "债券资产",
            "bond_type": "企业债",
            "issuer_name": "发行人A",
            "industry_name": "工业",
            "rating": "AAA",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("95"),
            "amortized_cost_native": Decimal("93"),
            "accrued_interest_native": Decimal("1.2"),
            "coupon_rate": Decimal("0.03"),
            "ytm_value": Decimal("0.035"),
            "maturity_date": date(2031, 3, 31),
            "interest_mode": "半年付息",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_1",
            "rule_version": "rv_snapshot_1",
            "ingest_batch_id": "ib_1",
            "trace_id": "trace_1",
        },
        {
            "report_date": report_date,
            "instrument_code": "BOND-ISSUE",
            "instrument_name": "发行类债券",
            "portfolio_name": "组合A",
            "cost_center": "CC1",
            "account_category": "持有至到期类资产",
            "asset_class": "债券资产",
            "bond_type": "同业存单",
            "issuer_name": "本行",
            "industry_name": "金融",
            "rating": "AAA",
            "currency_code": "CNY",
            "face_value_native": Decimal("200"),
            "market_value_native": Decimal("200"),
            "amortized_cost_native": Decimal("200"),
            "accrued_interest_native": Decimal("0"),
            "coupon_rate": Decimal("0.02"),
            "ytm_value": Decimal("0.021"),
            "maturity_date": date(2027, 3, 31),
            "is_issuance_like": True,
            "source_version": "sv_snapshot_1",
            "rule_version": "rv_snapshot_1",
            "ingest_batch_id": "ib_1",
            "trace_id": "trace_2",
        },
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    assert len(rows) == 1
    row = rows[0]
    expected_years = Decimal("1826") / Decimal("365")
    expected_macaulay = common.estimate_duration(
        date(2031, 3, 31),
        report_date,
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
    )
    expected_modified = common.estimate_modified_duration(expected_macaulay, Decimal("0.035"))
    expected_convexity = common.estimate_convexity(expected_macaulay, Decimal("0.035"))

    assert row.instrument_code == "BOND-001"
    assert row.asset_class_raw == "债券资产"
    assert row.asset_class_std == "credit"
    assert row.accounting_class == "OCI"
    assert row.accounting_rule_id == "R010"
    assert row.interest_mode == "半年付息"
    assert row.interest_payment_frequency == "semi-annual"
    assert row.interest_rate_style == "unknown"
    assert row.years_to_maturity == expected_years
    assert row.tenor_bucket == "5Y"
    assert row.macaulay_duration == expected_macaulay
    assert row.modified_duration == expected_modified
    assert row.convexity == expected_convexity
    assert row.dv01 == Decimal("95") * expected_modified / Decimal("10000")
    assert row.is_credit is True
    assert row.spread_dv01 == row.dv01
    assert row.source_version == "sv_snapshot_1"
    assert row.rule_version == "rv_snapshot_1"
    assert row.ingest_batch_id == "ib_1"
    assert row.trace_id == "trace_1"


def test_compute_bond_analytics_rows_uses_rate_classification_and_zero_spread_dv01() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "TB-001",
            "instrument_name": "国债1号",
            "portfolio_name": "组合国债",
            "cost_center": "CC2",
            "account_category": "持有至到期投资",
            "asset_class": "债券资产",
            "bond_type": "国债",
            "issuer_name": "财政部",
            "industry_name": "政府",
            "rating": "AAA",
            "currency_code": "CNY",
            "face_value_native": Decimal("1000"),
            "market_value_native": Decimal("998"),
            "amortized_cost_native": Decimal("997"),
            "accrued_interest_native": Decimal("3"),
            "coupon_rate": Decimal("0.02"),
            "ytm_value": Decimal("0.018"),
            "maturity_date": date(2027, 1, 15),
            "is_issuance_like": False,
            "source_version": "sv_snapshot_2",
            "rule_version": "rv_snapshot_2",
            "ingest_batch_id": "ib_2",
            "trace_id": "trace_2",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    assert len(rows) == 1
    row = rows[0]
    assert row.asset_class_std == "rate"
    assert row.accounting_class == "AC"
    assert row.accounting_rule_id == "R001"
    assert row.is_credit is False
    assert row.interest_payment_frequency == "annual"
    assert row.interest_rate_style == "unknown"
    assert row.spread_dv01 == Decimal("0")


def test_compute_bond_analytics_rows_normalizes_percent_rates_before_duration_math() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "TB-PCT-001",
            "instrument_name": "百分数利率债",
            "portfolio_name": "组合百分数",
            "cost_center": "CC-PCT",
            "account_category": "持有至到期投资",
            "asset_class": "债券资产",
            "bond_type": "国债",
            "issuer_name": "财政部",
            "industry_name": "政府",
            "rating": "AAA",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("100"),
            "amortized_cost_native": Decimal("100"),
            "accrued_interest_native": Decimal("0"),
            "coupon_rate": Decimal("3.00"),
            "ytm_value": Decimal("3.50"),
            "maturity_date": date(2031, 3, 31),
            "interest_mode": "年付",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_pct",
            "rule_version": "rv_snapshot_pct",
            "ingest_batch_id": "ib_pct",
            "trace_id": "trace_pct",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    assert len(rows) == 1
    row = rows[0]
    expected_macaulay = common.estimate_duration(
        date(2031, 3, 31),
        report_date,
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
        bond_code="TB-PCT-001",
    )
    expected_modified = common.estimate_modified_duration(expected_macaulay, Decimal("0.035"))

    assert row.coupon_rate == Decimal("0.03")
    assert row.ytm == Decimal("0.035")
    assert row.macaulay_duration == expected_macaulay
    assert row.modified_duration == expected_modified


def test_compute_bond_analytics_rows_backfills_missing_lineage_with_deterministic_defaults() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "BOND-003",
            "instrument_name": "交易债",
            "portfolio_name": "组合C",
            "cost_center": "CC3",
            "account_category": "交易性金融资产",
            "asset_class": "债券资产",
            "bond_type": "公司债",
            "issuer_name": "发行人C",
            "industry_name": "地产",
            "rating": "AA+",
            "currency_code": "USD",
            "face_value_native": Decimal("50"),
            "market_value_native": Decimal("48"),
            "amortized_cost_native": Decimal("49"),
            "accrued_interest_native": Decimal("0.4"),
            "coupon_rate": None,
            "ytm_value": None,
            "maturity_date": None,
            "is_issuance_like": False,
            "source_version": "",
            "rule_version": "",
            "ingest_batch_id": "",
            "trace_id": "",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    assert len(rows) == 1
    row = rows[0]
    assert row.accounting_class == "TPL"
    assert row.accounting_rule_id == "R020"
    assert row.years_to_maturity == Decimal("0")
    assert row.macaulay_duration == Decimal("0")
    assert row.modified_duration == Decimal("0")
    assert row.convexity == Decimal("0")
    assert row.dv01 == Decimal("0")
    assert row.spread_dv01 == Decimal("0")
    assert row.source_version == "sv_bond_analytics_snapshot_missing"
    assert row.rule_version == "rv_bond_analytics_engine_v1"
    assert row.ingest_batch_id == "ib_bond_analytics_missing"
    assert row.trace_id == "trace_bond_analytics_BOND-003_0"


def test_compute_bond_analytics_rows_rejects_report_date_mismatch() -> None:
    module = _module()
    requested_report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": date(2026, 3, 30),
            "instrument_code": "BOND-004",
            "instrument_name": "错期债券",
            "portfolio_name": "组合D",
            "cost_center": "CC4",
            "account_category": "持有至到期投资",
            "asset_class": "债券资产",
            "bond_type": "国债",
            "issuer_name": "财政部",
            "industry_name": "政府",
            "rating": "AAA",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("100"),
            "amortized_cost_native": Decimal("100"),
            "accrued_interest_native": Decimal("0"),
            "coupon_rate": Decimal("0.02"),
            "ytm_value": Decimal("0.02"),
            "maturity_date": date(2027, 3, 31),
            "is_issuance_like": False,
            "source_version": "sv_snapshot_4",
            "rule_version": "rv_snapshot_4",
            "ingest_batch_id": "ib_4",
            "trace_id": "trace_4",
        }
    ]

    with pytest.raises(ValueError, match="report_date"):
        module.compute_bond_analytics_rows(snapshot_rows, requested_report_date)
