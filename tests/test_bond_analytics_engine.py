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
            "coupon_rate": Decimal("3.0"),
            "ytm_value": Decimal("3.5"),
            "value_date": date(2024, 3, 31),
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
            "coupon_rate": Decimal("2.0"),
            "ytm_value": Decimal("2.1"),
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
        coupon_frequency=2,
    )
    expected_modified = common.estimate_modified_duration(
        expected_macaulay,
        Decimal("0.035"),
        coupon_frequency=2,
    )
    expected_convexity = common.estimate_convexity(
        expected_macaulay,
        Decimal("0.035"),
        coupon_frequency=2,
    )

    assert row.instrument_code == "BOND-001"
    assert row.asset_class_raw == "债券资产"
    assert row.asset_class_std == "credit"
    assert row.accounting_class == "OCI"
    assert row.accounting_rule_id == "R010"
    assert row.interest_mode == "半年付息"
    assert row.interest_payment_frequency == "semi-annual"
    assert row.interest_payment_frequency_fallback_used is False
    assert row.interest_rate_style == "unknown"
    assert row.value_date == date(2024, 3, 31)
    assert row.years_to_maturity == expected_years
    assert row.tenor_bucket == "5Y"
    assert row.macaulay_duration == expected_macaulay
    assert row.modified_duration == expected_modified
    assert row.convexity == expected_convexity
    assert row.dv01 == Decimal("100") * expected_modified / Decimal("10000")
    assert row.is_credit is True
    assert row.spread_dv01 == row.dv01
    assert row.source_version == "sv_snapshot_1"
    assert row.rule_version == "rv_snapshot_1"
    assert row.ingest_batch_id == "ib_1"
    assert row.trace_id == "trace_1"


def test_compute_bond_analytics_rows_preserves_annual_frequency_fallback_provenance() -> None:
    module = _module()
    report_date = date(2026, 3, 31)

    rows = module.compute_bond_analytics_rows(
        [
            {
                "report_date": report_date,
                "instrument_code": "BOND-FIXED-FALLBACK",
                "currency_code": "CNY",
                "face_value_native": Decimal("100"),
                "market_value_native": Decimal("90"),
                "coupon_rate": Decimal("3"),
                "ytm_value": Decimal("3.5"),
                "maturity_date": date(2027, 3, 31),
                "interest_mode": "fixed",
                "is_issuance_like": False,
            }
        ],
        report_date,
    )

    assert rows[0].interest_payment_frequency == "annual"
    assert rows[0].interest_payment_frequency_fallback_used is True


def test_compute_bond_analytics_rows_uses_formal_cny_values_and_accounting_basis() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "USD-OCI-001",
            "instrument_name": "USD credit bond",
            "portfolio_name": "Portfolio",
            "cost_center": "CC-USD",
            "account_category": "bank book",
            "accounting_basis": "FVOCI",
            "asset_class": "credit bond",
            "bond_type": "corporate bond",
            "issuer_name": "Issuer",
            "industry_name": "Industry",
            "rating": "A",
            "currency_code": "USD",
            "face_value_native": Decimal("100"),
            "face_value_cny": Decimal("700"),
            "market_value_native": Decimal("100"),
            "market_value_cny": Decimal("720"),
            "amortized_cost_native": Decimal("98"),
            "accrued_interest_native": Decimal("1"),
            "coupon_rate": Decimal("3.0"),
            "ytm_value": Decimal("4.0"),
            "maturity_date": date(2031, 3, 31),
            "interest_mode": "annual",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_usd",
            "rule_version": "rv_snapshot_usd",
            "ingest_batch_id": "ib_usd",
            "trace_id": "trace_usd",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    assert len(rows) == 1
    row = rows[0]
    assert row.accounting_class == "OCI"
    assert row.accounting_rule_id == "R010"
    assert row.face_value == Decimal("700")
    assert row.market_value_native == Decimal("100")
    assert row.market_value == Decimal("720")
    assert row.dv01 == Decimal("700") * row.modified_duration / Decimal("10000")


def test_compute_bond_analytics_rows_falls_back_to_native_face_value_when_cny_face_missing() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "USD-NATIVE-FACE-001",
            "instrument_name": "USD bond without formal CNY face",
            "portfolio_name": "Portfolio",
            "cost_center": "CC-USD",
            "account_category": "bank book",
            "accounting_basis": "FVOCI",
            "asset_class": "credit bond",
            "bond_type": "corporate bond",
            "issuer_name": "Issuer",
            "industry_name": "Industry",
            "rating": "A",
            "currency_code": "USD",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("98"),
            "market_value_cny": Decimal("686"),
            "amortized_cost_native": Decimal("97"),
            "amortized_cost_cny": Decimal("679"),
            "accrued_interest_native": Decimal("1"),
            "accrued_interest_cny": Decimal("7"),
            "coupon_rate": Decimal("3.0"),
            "ytm_value": Decimal("4.0"),
            "maturity_date": date(2031, 3, 31),
            "interest_mode": "annual",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_usd",
            "rule_version": "rv_snapshot_usd",
            "ingest_batch_id": "ib_usd",
            "trace_id": "trace_usd",
        }
    ]

    row = module.compute_bond_analytics_rows(snapshot_rows, report_date)[0]

    assert row.face_value == Decimal("100")
    assert row.market_value == Decimal("686")
    assert row.accrued_interest == Decimal("7")
    assert row.dv01 == Decimal("100") * row.modified_duration / Decimal("10000")
    assert row.dv01 != row.market_value * row.modified_duration / Decimal("10000")


def test_compute_bond_analytics_rows_uses_formal_cny_cost_and_accrued_for_foreign_bond() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "USD-CNY-AMORT-001",
            "instrument_name": "USD formal CNY amount bond",
            "portfolio_name": "Portfolio",
            "cost_center": "CC-USD",
            "account_category": "bank book",
            "accounting_basis": "FVOCI",
            "asset_class": "credit bond",
            "bond_type": "corporate bond",
            "issuer_name": "Issuer",
            "industry_name": "Industry",
            "rating": "A",
            "currency_code": "USD",
            "face_value_native": Decimal("100"),
            "face_value_cny": Decimal("700"),
            "market_value_native": Decimal("100"),
            "market_value_cny": Decimal("720"),
            "amortized_cost_native": Decimal("98"),
            "amortized_cost_cny": Decimal("686"),
            "accrued_interest_native": Decimal("1"),
            "accrued_interest_cny": Decimal("7"),
            "coupon_rate": Decimal("3.0"),
            "ytm_value": Decimal("4.0"),
            "maturity_date": date(2031, 3, 31),
            "interest_mode": "annual",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_usd",
            "rule_version": "rv_snapshot_usd",
            "ingest_batch_id": "ib_usd",
            "trace_id": "trace_usd",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    row = rows[0]
    assert row.face_value == Decimal("700")
    assert row.market_value == Decimal("720")
    assert row.amortized_cost == Decimal("686")
    assert row.accrued_interest == Decimal("7")


def test_compute_bond_analytics_rows_uses_payment_frequency_for_duration_and_convexity() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    maturity_date = date(2031, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "SEMI-DURATION-001",
            "instrument_name": "Semi annual credit bond",
            "portfolio_name": "Portfolio",
            "cost_center": "CC-SEMI",
            "account_category": "bank book",
            "accounting_basis": "FVOCI",
            "asset_class": "credit bond",
            "bond_type": "corporate bond",
            "issuer_name": "Issuer",
            "industry_name": "Industry",
            "rating": "A",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("100"),
            "amortized_cost_native": Decimal("98"),
            "accrued_interest_native": Decimal("1"),
            "coupon_rate": Decimal("3.0"),
            "ytm_value": Decimal("4.0"),
            "maturity_date": maturity_date,
            "interest_mode": "semi-annual",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_semi",
            "rule_version": "rv_snapshot_semi",
            "ingest_batch_id": "ib_semi",
            "trace_id": "trace_semi",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    row = rows[0]
    years_to_maturity = Decimal(str((maturity_date - report_date).days)) / Decimal("365")
    expected_macaulay = common.compute_macaulay_duration(
        Decimal("0.03"),
        Decimal("0.04"),
        years_to_maturity,
        coupon_frequency=2,
    )
    expected_modified = common.estimate_modified_duration(
        expected_macaulay,
        Decimal("0.04"),
        coupon_frequency=2,
    )
    expected_convexity = common.estimate_convexity(
        expected_macaulay,
        Decimal("0.04"),
        coupon_frequency=2,
    )

    assert row.interest_payment_frequency == "semi-annual"
    assert row.macaulay_duration == expected_macaulay
    assert row.modified_duration == expected_modified
    assert row.convexity == expected_convexity


@pytest.mark.parametrize(
    ("interest_mode", "expected_payment_frequency", "expected_coupon_frequency"),
    [
        ("unknown-mode", "annual", 1),
        ("bullet", "bullet", 1),
    ],
)
def test_compute_bond_analytics_rows_uses_annual_frequency_for_unknown_and_bullet_modes(
    interest_mode: str,
    expected_payment_frequency: str,
    expected_coupon_frequency: int,
) -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    maturity_date = date(2029, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": f"FREQ-{interest_mode}",
            "instrument_name": "Frequency convention bond",
            "portfolio_name": "Portfolio",
            "cost_center": "CC-FREQ",
            "account_category": "bank book",
            "accounting_basis": "FVOCI",
            "asset_class": "credit bond",
            "bond_type": "corporate bond",
            "issuer_name": "Issuer",
            "industry_name": "Industry",
            "rating": "A",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("100"),
            "amortized_cost_native": Decimal("98"),
            "accrued_interest_native": Decimal("1"),
            "coupon_rate": Decimal("3.0"),
            "ytm_value": Decimal("4.0"),
            "maturity_date": maturity_date,
            "interest_mode": interest_mode,
            "is_issuance_like": False,
            "source_version": "sv_snapshot_freq",
            "rule_version": "rv_snapshot_freq",
            "ingest_batch_id": "ib_freq",
            "trace_id": "trace_freq",
        }
    ]

    row = module.compute_bond_analytics_rows(snapshot_rows, report_date)[0]
    years_to_maturity = Decimal(str((maturity_date - report_date).days)) / Decimal("365")
    expected_macaulay = common.compute_macaulay_duration(
        Decimal("0.03"),
        Decimal("0.04"),
        years_to_maturity,
        coupon_frequency=expected_coupon_frequency,
    )

    assert row.interest_payment_frequency == expected_payment_frequency
    assert row.macaulay_duration == expected_macaulay


def test_compute_bond_analytics_rows_uses_face_value_basis_for_dv01() -> None:
    module = _module()
    report_date = date(2026, 4, 30)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "FACE-DV01-001",
            "instrument_name": "Face value DV01 bond",
            "portfolio_name": "Portfolio",
            "cost_center": "CC-FACE",
            "account_category": "bank book",
            "accounting_basis": "FVOCI",
            "asset_class": "credit bond",
            "bond_type": "corporate bond",
            "issuer_name": "Issuer",
            "industry_name": "Industry",
            "rating": "A",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("500"),
            "amortized_cost_native": Decimal("98"),
            "accrued_interest_native": Decimal("1"),
            "coupon_rate": Decimal("1.47"),
            "ytm_value": Decimal("1.6359"),
            "maturity_date": date(2028, 2, 14),
            "interest_mode": "annual",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_face",
            "rule_version": "rv_snapshot_face",
            "ingest_batch_id": "ib_face",
            "trace_id": "trace_face",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    row = rows[0]
    assert row.modified_duration.quantize(Decimal("0.0001")) == Decimal("1.7514")
    assert row.dv01 == row.face_value * row.modified_duration / Decimal("10000")
    assert row.dv01 != row.market_value * row.modified_duration / Decimal("10000")


def test_compute_bond_analytics_rows_keeps_cny_market_value_native_when_cny_backfill_is_stale() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "CNY-OCI-001",
            "instrument_name": "CNY credit bond",
            "portfolio_name": "Portfolio",
            "cost_center": "CC-CNY",
            "account_category": "bank book",
            "accounting_basis": "FVOCI",
            "asset_class": "credit bond",
            "bond_type": "corporate bond",
            "issuer_name": "Issuer",
            "industry_name": "Industry",
            "rating": "A",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("100"),
            "market_value_cny": Decimal("-100"),
            "amortized_cost_native": Decimal("98"),
            "accrued_interest_native": Decimal("1"),
            "coupon_rate": Decimal("3.0"),
            "ytm_value": Decimal("4.0"),
            "maturity_date": date(2031, 3, 31),
            "interest_mode": "annual",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_cny",
            "rule_version": "rv_snapshot_cny",
            "ingest_batch_id": "ib_cny",
            "trace_id": "trace_cny",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    assert len(rows) == 1
    row = rows[0]
    assert row.accounting_class == "OCI"
    assert row.market_value_native == Decimal("100")
    assert row.market_value == Decimal("100")
    assert row.dv01 == Decimal("100") * row.modified_duration / Decimal("10000")


@pytest.mark.parametrize(
    ("basis", "expected"),
    [
        ("AC", "AC"),
        ("FVOCI", "OCI"),
        ("OCI", "OCI"),
        ("FVTPL", "TPL"),
        ("TPL", "TPL"),
        ("unknown", None),
        ("", None),
    ],
)
def test_map_accounting_basis_to_risk_class(basis: str, expected: str | None) -> None:
    assert common.map_accounting_basis_to_risk_class(basis) == expected


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
            "coupon_rate": Decimal("2.0"),
            "ytm_value": Decimal("1.8"),
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


def test_compute_bond_analytics_rows_normalizes_gray_zone_percent_rates() -> None:
    """灰区回归锁定：票息 1.82（=1.82%）必须 ÷100，不得当作小数 182%。

    2026-07-19 取证：zqtz 快照利率为百分数口径，[0.2, 2) 灰区每天约 550 只券。
    旧的 >2 启发式会放行 1.82 → 久期被 182% 的 ytm 压扁、DV01 全错。
    """
    module = _module()
    report_date = date(2026, 6, 30)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "SCP-GRAY-001",
            "instrument_name": "低票息超短融",
            "portfolio_name": "组合灰区",
            "cost_center": "CC-GRAY",
            "account_category": "交易性金融资产",
            "asset_class": "债券资产",
            "bond_type": "短期融资券",
            "issuer_name": "发行人G",
            "industry_name": "城投",
            "rating": "AAA",
            "currency_code": "CNY",
            "face_value_native": Decimal("1000000"),
            "market_value_native": Decimal("1000000"),
            "amortized_cost_native": Decimal("1000000"),
            "accrued_interest_native": Decimal("0"),
            "coupon_rate": Decimal("1.82"),
            "ytm_value": Decimal("1.82"),
            "maturity_date": date(2027, 6, 30),
            "interest_mode": "年付",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_gray",
            "rule_version": "rv_snapshot_gray",
            "ingest_batch_id": "ib_gray",
            "trace_id": "trace_gray",
        }
    ]

    row = module.compute_bond_analytics_rows(snapshot_rows, report_date)[0]

    assert row.coupon_rate == Decimal("0.0182")
    assert row.ytm == Decimal("0.0182")
    expected_macaulay = common.estimate_duration(
        date(2027, 6, 30),
        report_date,
        coupon_rate=Decimal("0.0182"),
        ytm=Decimal("0.0182"),
        bond_code="SCP-GRAY-001",
    )
    expected_modified = common.estimate_modified_duration(expected_macaulay, Decimal("0.0182"))
    assert row.macaulay_duration == expected_macaulay
    assert row.modified_duration == expected_modified
    # 1 年期券修正久期应接近 1，远不是被 182% ytm 压扁的 ~0.35
    assert row.modified_duration > Decimal("0.9")


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
            "coupon_rate": Decimal("2.0"),
            "ytm_value": Decimal("2.0"),
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


def test_normalize_rate_decimal_uses_percent_caliber() -> None:
    """Engine rate normalization must follow rate_units.normalize_percent_rate_to_decimal.

    Snapshot rates are stored in percent form (1.82 = 1.82%; evidenced
    2026-07-19), so every value is divided by 100 and > 20 (rates above 20%)
    is rejected as dirty data. No gray-zone heuristic is allowed.
    """
    module = _module()

    # Percent-form values are always divided by 100.
    assert module._normalize_rate_decimal(Decimal("3.5")) == Decimal("0.035")
    # Gray-zone low coupons (the old > 2 heuristic wrongly kept these as decimals).
    assert module._normalize_rate_decimal(Decimal("1.82")) == Decimal("0.0182")
    assert module._normalize_rate_decimal(Decimal("0.85")) == Decimal("0.0085")
    # Sub-percent yields are still percent-form (0.09 = 0.09%).
    assert module._normalize_rate_decimal(Decimal("0.09")) == Decimal("0.0009")
    # > 20 is dirty data -> None.
    assert module._normalize_rate_decimal(Decimal("25")) is None
    # Negative rates are rejected as dirty data.
    assert module._normalize_rate_decimal(Decimal("-0.5")) is None
    assert module._normalize_rate_decimal(None) is None
    assert module._normalize_rate_decimal("") is None


def test_compute_bond_analytics_rows_treats_dirty_rates_as_missing() -> None:
    module = _module()
    report_date = date(2026, 3, 31)
    snapshot_rows = [
        {
            "report_date": report_date,
            "instrument_code": "TB-DIRTY-001",
            "instrument_name": "脏利率债",
            "portfolio_name": "组合脏数据",
            "cost_center": "CC-DIRTY",
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
            "coupon_rate": Decimal("25"),
            "ytm_value": Decimal("25"),
            "maturity_date": date(2031, 3, 31),
            "interest_mode": "年付",
            "is_issuance_like": False,
            "source_version": "sv_snapshot_dirty",
            "rule_version": "rv_snapshot_dirty",
            "ingest_batch_id": "ib_dirty",
            "trace_id": "trace_dirty",
        }
    ]

    rows = module.compute_bond_analytics_rows(snapshot_rows, report_date)

    assert len(rows) == 1
    row = rows[0]
    # Dirty rates (> 20) are treated as missing rather than silently divided by 100.
    assert row.coupon_rate is None
    assert row.ytm is None
    expected_macaulay = common.estimate_duration(
        date(2031, 3, 31),
        report_date,
        coupon_rate=Decimal("0"),
        ytm=Decimal("0"),
        bond_code="TB-DIRTY-001",
    )
    assert row.macaulay_duration == expected_macaulay
