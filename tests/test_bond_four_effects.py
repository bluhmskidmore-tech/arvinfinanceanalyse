from __future__ import annotations

from tests.helpers import load_module


def test_get_bond_field_skips_nan_like_values_without_pandas() -> None:
    module = load_module(
        "backend.app.core_finance.bond_four_effects",
        "backend/app/core_finance/bond_four_effects.py",
    )

    bond = {
        "coupon_rate_start": float("nan"),
        "coupon_rate": "3.25",
    }

    assert module._get_bond_field(bond, "coupon_rate_start", "coupon_rate") == "3.25"
