from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests.helpers import load_module


def _module():
    return load_module(
        "backend.app.core_finance.balance_analysis",
        "backend/app/core_finance/balance_analysis.py",
    )


def test_balance_analysis_core_derives_invest_type_and_accounting_basis():
    module = _module()

    assert module.derive_invest_type_std("可供出售债券") == "A"
    assert module.derive_accounting_basis("A") == "FVOCI"
    assert module.derive_invest_type_std("交易性金融资产") == "T"
    assert module.derive_accounting_basis("T") == "FVTPL"
    assert module.derive_invest_type_std("持有至到期投资") == "H"
    assert module.derive_accounting_basis("H") == "AC"
    assert module.derive_invest_type_std("应收投资款项") == "H"

    with pytest.raises(ValueError):
        module.derive_invest_type_std("未知口径")


def test_balance_analysis_core_projects_zqtz_asset_scope_with_issuance_exclusion():
    module = _module()

    issuance_row = module.ZqtzSnapshotRow(
        report_date=date(2025, 12, 31),
        instrument_code="IB0001",
        instrument_name="发行类债券",
        portfolio_name="组合A",
        cost_center="CC1",
        account_category="发行类债劵",
        asset_class="债券类",
        bond_type="同业存单",
        issuer_name="发行人A",
        industry_name="金融业",
        rating="",
        currency_code="USD",
        face_value_native=Decimal("100"),
        market_value_native=Decimal("100"),
        amortized_cost_native=Decimal("90"),
        accrued_interest_native=Decimal("5"),
        coupon_rate=Decimal("2.5"),
        ytm_value=Decimal("2.4"),
        maturity_date=date(2026, 6, 30),
        is_issuance_like=True,
        interest_mode="固定",
        source_version="sv_1",
        rule_version="rv_1",
        ingest_batch_id="ib_1",
        trace_id="trace_1",
    )

    assert (
        module.project_zqtz_formal_balance_row(
            issuance_row,
            invest_type_raw="可供出售",
            position_scope="asset",
            currency_basis="CNY",
            fx_rate=Decimal("7.2"),
        )
        is None
    )

    included = module.project_zqtz_formal_balance_row(
        issuance_row,
        invest_type_raw="可供出售",
        position_scope="all",
        currency_basis="CNY",
        fx_rate=Decimal("7.2"),
    )

    assert included is not None
    assert included.invest_type_std == "A"
    assert included.accounting_basis == "FVOCI"
    assert included.face_value_amount == Decimal("720.0")
    assert included.market_value_amount == Decimal("720.0")
    assert included.amortized_cost_amount == Decimal("648.0")
    assert included.accrued_interest_amount == Decimal("36.0")


def test_balance_analysis_core_averages_daily_cny_amounts_after_fx_conversion():
    module = _module()

    result = module.average_daily_cny_amounts(
        [
            (Decimal("100"), Decimal("7.0")),
            (Decimal("200"), Decimal("8.0")),
        ]
    )

    assert result == Decimal("1150.0")


def test_balance_analysis_core_requires_explicit_fx_when_projecting_cny_rows():
    module = _module()

    row = module.TywSnapshotRow(
        report_date=date(2025, 12, 31),
        position_id="pos-1",
        product_type="同业存单",
        position_side="liability",
        counterparty_name="银行A",
        account_type="负债账户",
        special_account_type="一般",
        core_customer_type="股份制银行",
        currency_code="USD",
        principal_native=Decimal("10"),
        accrued_interest_native=Decimal("2"),
        funding_cost_rate=Decimal("1.5"),
        maturity_date=date(2026, 6, 30),
        source_version="sv_2",
        rule_version="rv_2",
        ingest_batch_id="ib_2",
        trace_id="trace_2",
    )

    with pytest.raises(ValueError):
        module.project_tyw_formal_balance_row(
            row,
            invest_type_raw="持有至到期",
            position_scope="liability",
            currency_basis="CNY",
        )

    converted = module.project_tyw_formal_balance_row(
        row,
        invest_type_raw="持有至到期",
        position_scope="liability",
        currency_basis="CNY",
        fx_rate=Decimal("7.1"),
    )

    assert converted.invest_type_std == "H"
    assert converted.accounting_basis == "AC"
    assert converted.principal_amount == Decimal("71.0")
    assert converted.accrued_interest_amount == Decimal("14.2")
