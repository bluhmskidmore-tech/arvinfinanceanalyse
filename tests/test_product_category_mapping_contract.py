"""Contract tests for `backend.app.config.product_category_mapping`."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.config.product_category_mapping import (
    DEFAULT_FTP_RATE_PCT,
    DERIVATIVE_PNL_ACCOUNTS,
    INTERMEDIATE_BUSINESS_PNL_ACCOUNTS,
    build_default_product_category_config,
)

_REQUIRED_KEYS = frozenset(
    {"id", "name", "side", "level", "scale_accounts", "pnl_accounts", "ftp_rate_pct", "children"}
)


def test_default_ftp_rate_pct_is_one_point_seven_five() -> None:
    assert DEFAULT_FTP_RATE_PCT == Decimal("1.75")


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


@pytest.mark.parametrize("accounts", [DERIVATIVE_PNL_ACCOUNTS, INTERMEDIATE_BUSINESS_PNL_ACCOUNTS])
def test_account_lists_are_nonempty(accounts: list[str]) -> None:
    assert len(accounts) > 0
