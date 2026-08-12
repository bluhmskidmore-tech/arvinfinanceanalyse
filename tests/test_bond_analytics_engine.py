from __future__ import annotations

import logging
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


def _foreign_bond_snapshot_row() -> dict[str, object]:
    return {
        "report_date": date(2026, 3, 31),
        "instrument_code": "USD-CLOSURE-001",
        "instrument_name": "USD formal CNY closure bond",
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


def _par_fallback_snapshot_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "report_date": date(2026, 1, 1),
        "instrument_code": "PAR-FB-001",
        "instrument_name": "有票息缺 ytm 债",
        "portfolio_name": "组合A",
        "cost_center": "CC1",
        "account_category": "可供出售类资产",
        "asset_class": "债券资产",
        "bond_type": "企业债",
        "currency_code": "CNY",
        "face_value_native": Decimal("100"),
        "market_value_native": Decimal("95"),
        "amortized_cost_native": Decimal("93"),
        "accrued_interest_native": Decimal("1"),
        "coupon_rate": Decimal("3.0"),  # percent 口径 → 0.03
        "ytm_value": None,  # ytm 缺失
        # 2026-01-01 → 2035-12-30 恰 3650 天 → years_to_maturity = 10（整）
        "maturity_date": date(2035, 12, 30),
        "interest_mode": "annual",
        "is_issuance_like": False,
    }
    row.update(overrides)
    return row


def test_compute_bond_analytics_rows_par_fallback_for_coupon_bond_missing_ytm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """有票息缺 ytm 的行：三项指标按 par 假设（ytm=coupon）计算，聚合告警可观测。

    黄金手算（10Y=3650 天、年付 3%、par ytm=3%；闭式独立推导，未经被测函数）：
      Macaulay  = (1.03/0.03)(1 - 1.03^-10)      = 8.786108921879104...
      修正久期  = Macaulay / 1.03                 = 8.530202836775829...
      凸性      = Macaulay(Macaulay+1) / 1.03^2   = 81.046110763505234...
      DV01      = 100 × 修正久期 / 10000          = 0.0853020283677582...
    旧缺陷下 Macaulay=修正久期=10（零息假设）、DV01=0.1，系统性高估。
    """
    module = _module()
    report_date = date(2026, 1, 1)
    with caplog.at_level(
        logging.WARNING, logger="backend.app.core_finance.bond_analytics.engine"
    ):
        rows = module.compute_bond_analytics_rows(
            [_par_fallback_snapshot_row()], report_date
        )

    assert len(rows) == 1
    row = rows[0]
    tol = Decimal("0.000001")
    assert row.years_to_maturity == Decimal("10")
    assert abs(row.macaulay_duration - Decimal("8.786108921879104")) < tol
    assert abs(row.modified_duration - Decimal("8.530202836775829")) < tol
    assert abs(row.convexity - Decimal("81.046110763505234")) < tol
    assert abs(row.dv01 - Decimal("0.085302028367758")) < tol
    # 不再等于剩余年限（旧回退值 10）。
    assert row.macaulay_duration < row.years_to_maturity

    fallback_warnings = [
        message
        for message in caplog.messages
        if "par-assumption duration" in message
    ]
    assert len(fallback_warnings) == 1
    assert common.YTM_PAR_FALLBACK_RULE_ID in fallback_warnings[0]
    assert "1 coupon-bond rows" in fallback_warnings[0]
    assert "market_value_cny=95" in fallback_warnings[0]
    # 日志级行清单：带具体回退债券代码；未超上限不出现“…共 N 只”截断尾。
    assert "instrument_codes=PAR-FB-001" in fallback_warnings[0]
    assert "…共" not in fallback_warnings[0]


def test_compute_bond_analytics_rows_par_fallback_code_list_truncates_beyond_20(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """超过 20 只回退券时：单条告警只列前 20 个代码，以“…共 N 只”收尾。"""
    module = _module()
    report_date = date(2026, 1, 1)
    codes = [f"PAR-FB-{i:03d}" for i in range(1, 26)]  # 25 只，超过生产上限 20
    with caplog.at_level(
        logging.WARNING, logger="backend.app.core_finance.bond_analytics.engine"
    ):
        rows = module.compute_bond_analytics_rows(
            [_par_fallback_snapshot_row(instrument_code=code) for code in codes],
            report_date,
        )

    assert len(rows) == 25
    fallback_warnings = [
        message
        for message in caplog.messages
        if "par-assumption duration" in message
    ]
    # 保持单条聚合 WARNING，不逐券告警。
    assert len(fallback_warnings) == 1
    message = fallback_warnings[0]
    assert "25 coupon-bond rows" in message
    for code in codes[:20]:
        assert code in message
    for code in codes[20:]:
        assert code not in message
    assert message.endswith("…共 25 只")


def test_compute_bond_analytics_rows_zero_coupon_missing_ytm_unchanged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """零票息 + ytm 缺失：仍回退剩余年限（正确口径），不触发 par 假设告警。"""
    module = _module()
    report_date = date(2026, 1, 1)
    with caplog.at_level(
        logging.WARNING, logger="backend.app.core_finance.bond_analytics.engine"
    ):
        rows = module.compute_bond_analytics_rows(
            [
                _par_fallback_snapshot_row(
                    instrument_code="ZERO-FB-001",
                    coupon_rate=None,
                )
            ],
            report_date,
        )

    row = rows[0]
    assert row.macaulay_duration == Decimal("10")
    assert row.modified_duration == Decimal("10")
    assert row.convexity == Decimal("100")
    assert row.dv01 == Decimal("100") * Decimal("10") / Decimal("10000")
    assert not [m for m in caplog.messages if "par-assumption duration" in m]


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

    assert len(rows) == 1
    row = rows[0]
    assert row.accounting_class == "OCI"
    assert row.accounting_rule_id == "R010"
    assert row.face_value == Decimal("700")
    assert row.market_value_native == Decimal("100")
    assert row.market_value == Decimal("720")
    assert row.amortized_cost == Decimal("686")
    assert row.accrued_interest == Decimal("7")
    assert row.dv01 == Decimal("700") * row.modified_duration / Decimal("10000")


@pytest.mark.parametrize("identity_currency", ["CNY", "RMB"])
def test_compute_bond_analytics_rows_keeps_cny_rmb_identity_on_native_amounts(
    identity_currency: str,
) -> None:
    module = _module()
    snapshot_row = _foreign_bond_snapshot_row()
    snapshot_row["currency_code"] = identity_currency
    for field_name in (
        "face_value_cny",
        "market_value_cny",
        "amortized_cost_cny",
        "accrued_interest_cny",
    ):
        snapshot_row.pop(field_name)

    row = module.compute_bond_analytics_rows(
        [snapshot_row],
        date(2026, 3, 31),
    )[0]

    assert row.currency_code == identity_currency
    assert row.face_value == Decimal("100")
    assert row.market_value == Decimal("100")
    assert row.amortized_cost == Decimal("98")
    assert row.accrued_interest == Decimal("1")


def test_compute_bond_analytics_rows_requires_formal_cny_closure_for_cnx() -> None:
    module = _module()
    snapshot_row = _foreign_bond_snapshot_row()
    snapshot_row["currency_code"] = "CNX"
    for field_name in (
        "face_value_cny",
        "market_value_cny",
        "amortized_cost_cny",
        "accrued_interest_cny",
    ):
        snapshot_row.pop(field_name)

    with pytest.raises(
        ValueError,
        match=r"formal CNY closure unavailable:.*instrument_code=USD-CLOSURE-001.*face_value_cny",
    ):
        module.compute_bond_analytics_rows(
            [snapshot_row],
            date(2026, 3, 31),
        )


@pytest.mark.parametrize(
    ("missing_field", "invalid_value"),
    [
        ("face_value_cny", None),
        ("market_value_cny", None),
        ("amortized_cost_cny", None),
        ("accrued_interest_cny", None),
        ("face_value_cny", ""),
        ("face_value_cny", Decimal("NaN")),
        ("market_value_cny", Decimal("Infinity")),
    ],
)
def test_compute_bond_analytics_rows_rejects_foreign_bond_without_formal_cny_closure(
    missing_field: str,
    invalid_value: object,
) -> None:
    module = _module()
    snapshot_row = _foreign_bond_snapshot_row()
    snapshot_row[missing_field] = invalid_value

    with pytest.raises(
        ValueError,
        match=rf"formal CNY closure unavailable:.*instrument_code=USD-CLOSURE-001.*{missing_field}",
    ):
        module.compute_bond_analytics_rows(
            [snapshot_row],
            date(2026, 3, 31),
        )


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
            "face_value_cny": Decimal("350"),
            "market_value_native": Decimal("48"),
            "market_value_cny": Decimal("336"),
            "amortized_cost_native": Decimal("49"),
            "amortized_cost_cny": Decimal("343"),
            "accrued_interest_native": Decimal("0.4"),
            "accrued_interest_cny": Decimal("2.8"),
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
