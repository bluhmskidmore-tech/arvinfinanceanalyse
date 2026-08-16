"""Contract tests for `backend.app.config.product_category_mapping`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.config import product_category_mapping as legacy_mapping
from backend.app.config.product_category_mapping import (
    DEFAULT_FTP_RATE_PCT,
    DERIVATIVE_PNL_ACCOUNTS,
    FTP_RATE_PCT_BY_REPORT_YEAR,
    INTERMEDIATE_BUSINESS_PNL_ACCOUNTS,
    build_default_product_category_config,
    build_product_category_config_for_report_date,
    resolve_product_category_ftp_rate_pct,
)
from backend.app.core_finance.config import (
    product_category_mapping as authority_mapping,
)

_REQUIRED_KEYS = frozenset(
    {"id", "name", "side", "level", "scale_accounts", "pnl_accounts", "ftp_rate_pct", "children"}
)
EXPECTED_DERIVATIVE_PNL_ACCOUNTS = [
    "51203010001",
    "51203010003",
    "51203020001",
    "51203050001",
    "51203070001",
    "51203070002",
    "51203070003",
    "51204000001",
    "51206010003",
    "51206040003",
]
EXPECTED_INTERMEDIATE_BUSINESS_PNL_ACCOUNTS = [
    "51102000004",
    "51102000005",
    "51104000001",
    "51110000018",
]


def test_default_ftp_rate_pct_is_one_point_seven_five() -> None:
    assert DEFAULT_FTP_RATE_PCT == Decimal("1.75")


def test_report_year_ftp_policy_pins_2024_2025_and_2026_rates() -> None:
    assert FTP_RATE_PCT_BY_REPORT_YEAR == {
        2024: Decimal("2.00"),
        2025: Decimal("1.75"),
        2026: Decimal("1.60"),
    }
    assert resolve_product_category_ftp_rate_pct(
        date(2024, 12, 31), Decimal("2.25")
    ) == Decimal("2.00")
    assert resolve_product_category_ftp_rate_pct(
        date(2025, 12, 31), Decimal("2.25")
    ) == Decimal("1.75")
    assert resolve_product_category_ftp_rate_pct(
        date(2026, 2, 28), Decimal("2.25")
    ) == Decimal("1.60")
    # 未登记年份不再静默套用 fallback，改为沿用最近已登记年份（见下方专项用例）。
    assert resolve_product_category_ftp_rate_pct(
        date(2027, 12, 31), Decimal("2.25")
    ) == Decimal("1.60")


def test_unregistered_future_year_carries_forward_nearest_year_with_warning(caplog) -> None:
    """未登记的未来年份沿用最后一个已登记年份，并显式告警（不静默用 fallback）。"""
    import logging

    with caplog.at_level(logging.WARNING):
        resolved = resolve_product_category_ftp_rate_pct(date(2030, 6, 30), Decimal("2.25"))

    assert resolved == FTP_RATE_PCT_BY_REPORT_YEAR[max(FTP_RATE_PCT_BY_REPORT_YEAR)]
    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and "not registered" in record.getMessage()
    ]
    assert len(warnings) == 1
    assert "2030" in warnings[0].getMessage()


def test_unregistered_year_before_table_start_uses_earliest_registered_year(caplog) -> None:
    """早于年表起点的年份沿用最早已登记年份，同样告警。"""
    import logging

    with caplog.at_level(logging.WARNING):
        resolved = resolve_product_category_ftp_rate_pct(date(2019, 12, 31), Decimal("2.25"))

    assert resolved == FTP_RATE_PCT_BY_REPORT_YEAR[min(FTP_RATE_PCT_BY_REPORT_YEAR)]
    assert [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and "not registered" in record.getMessage()
    ]


def test_registered_year_resolves_without_fallback_warning(caplog) -> None:
    """已登记年份必须命中年表且不产生回退告警。"""
    import logging

    with caplog.at_level(logging.WARNING):
        resolved = resolve_product_category_ftp_rate_pct(date(2026, 2, 28), Decimal("2.25"))

    assert resolved == Decimal("1.60")
    assert not [
        record for record in caplog.records if "not registered" in record.getMessage()
    ]


def test_report_date_config_applies_year_policy_to_all_items() -> None:
    cfg = build_product_category_config_for_report_date(date(2026, 2, 28))
    assert {item["ftp_rate_pct"] for item in cfg} == {"1.60"}


def test_build_default_product_category_config_nonempty_unique_ids() -> None:
    cfg = build_default_product_category_config()
    assert isinstance(cfg, list)
    assert len(cfg) > 0
    ids = [item["id"] for item in cfg]
    assert len(ids) == len(set(ids))


def test_bond_investment_level_zero_children() -> None:
    cfg = build_default_product_category_config()
    bond = next(item for item in cfg if item["id"] == "bond_investment")
    assert bond["level"] == 0
    assert set(bond["children"]) == {
        "bond_tpl",
        "bond_ac",
        "bond_ac_other",
        "bond_fvoci",
        "bond_valuation_spread",
    }


def test_children_references_resolve_to_config_ids() -> None:
    cfg = build_default_product_category_config()
    by_id = {item["id"]: item for item in cfg}
    for item in cfg:
        for child_id in item["children"]:
            assert child_id in by_id, f"missing child id {child_id!r} referenced from {item['id']!r}"


def test_every_item_has_required_keys_and_ftp_as_string() -> None:
    cfg = build_default_product_category_config()
    for item in cfg:
        assert set(item.keys()) >= _REQUIRED_KEYS
        ftp = item["ftp_rate_pct"]
        assert isinstance(ftp, str)
        assert ftp == str(Decimal(ftp))


def test_custom_ftp_rate_propagates_to_all_items() -> None:
    custom = Decimal("2.25")
    cfg = build_default_product_category_config(ftp_rate_pct=custom)
    expected = str(custom)
    for item in cfg:
        assert item["ftp_rate_pct"] == expected


def test_derivative_and_intermediate_account_lists_have_no_duplicates() -> None:
    assert len(DERIVATIVE_PNL_ACCOUNTS) == len(set(DERIVATIVE_PNL_ACCOUNTS))
    assert len(INTERMEDIATE_BUSINESS_PNL_ACCOUNTS) == len(set(INTERMEDIATE_BUSINESS_PNL_ACCOUNTS))
    assert not set(DERIVATIVE_PNL_ACCOUNTS).intersection(INTERMEDIATE_BUSINESS_PNL_ACCOUNTS)


def test_derivative_accounts_match_confirmed_fx_and_derivative_scope() -> None:
    assert DERIVATIVE_PNL_ACCOUNTS == EXPECTED_DERIVATIVE_PNL_ACCOUNTS


def test_intermediate_business_accounts_match_confirmed_fee_scope() -> None:
    assert INTERMEDIATE_BUSINESS_PNL_ACCOUNTS == EXPECTED_INTERMEDIATE_BUSINESS_PNL_ACCOUNTS


def test_derivatives_category_keeps_id_and_uses_fx_derivative_display_name() -> None:
    cfg = build_default_product_category_config()
    derivatives = next(item for item in cfg if item["id"] == "derivatives")
    intermediate = next(item for item in cfg if item["id"] == "intermediate_business_income")

    assert derivatives["name"] == "汇兑损益及衍生"
    assert derivatives["pnl_accounts"] == EXPECTED_DERIVATIVE_PNL_ACCOUNTS
    assert intermediate["pnl_accounts"] == EXPECTED_INTERMEDIATE_BUSINESS_PNL_ACCOUNTS


def test_fx_and_derivative_account_list_matches_confirmed_full_scope() -> None:
    assert DERIVATIVE_PNL_ACCOUNTS == [
        "51203010001",
        "51203010003",
        "51203020001",
        "51203050001",
        "51203070001",
        "51203070002",
        "51203070003",
        "51204000001",
        "51206010003",
        "51206040003",
    ]


def test_intermediate_business_income_keeps_only_fee_income_accounts() -> None:
    assert INTERMEDIATE_BUSINESS_PNL_ACCOUNTS == [
        "51102000004",
        "51102000005",
        "51104000001",
        "51110000018",
    ]


def test_fx_derivative_and_intermediate_income_accounts_do_not_overlap() -> None:
    assert set(DERIVATIVE_PNL_ACCOUNTS).isdisjoint(INTERMEDIATE_BUSINESS_PNL_ACCOUNTS)


@pytest.mark.parametrize("accounts", [DERIVATIVE_PNL_ACCOUNTS, INTERMEDIATE_BUSINESS_PNL_ACCOUNTS])
def test_account_lists_are_nonempty(accounts: list[str]) -> None:
    assert len(accounts) > 0


def test_legacy_import_reexports_core_finance_authority() -> None:
    assert legacy_mapping.build_default_product_category_config is (
        authority_mapping.build_default_product_category_config
    )
    assert legacy_mapping.PRODUCT_CATEGORY_CONFIG is authority_mapping.PRODUCT_CATEGORY_CONFIG


def test_legacy_product_category_config_view_is_derived_from_authority() -> None:
    cfg = build_default_product_category_config()
    legacy_names = {
        row["name"]
        for side_rows in authority_mapping.PRODUCT_CATEGORY_CONFIG.values()
        for row in side_rows
    }

    for item in cfg:
        if item["level"] == 0:
            assert item["name"] in legacy_names
