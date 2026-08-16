"""Tests for ADB calculation helpers."""

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from backend.app.core_finance.adb_analytics import (
    build_comparison_rows,
    build_rate_map,
    enrich_bonds_asset_frame,
    enrich_bonds_liability_frame,
    enrich_interbank_frame,
)


def test_build_comparison_rows_sorts_by_avg_balance_desc() -> None:
    spot_map = {"A": Decimal("100"), "B": Decimal("500")}
    sum_map = {"A": Decimal("600"), "B": Decimal("300")}  # 3 calendar days in range
    rows = build_comparison_rows(
        "Asset",
        spot_map,
        sum_map,
        Decimal("3"),
        None,
        False,
        date(2025, 1, 1),
        lambda *_: Decimal("1"),
    )
    assert [r["category"] for r in rows] == ["A", "B"]


def test_build_comparison_rows_top_n_truncates_after_sort() -> None:
    spot_map = {"big": Decimal("10"), "small": Decimal("10")}
    sum_map = {"big": Decimal("300"), "small": Decimal("30")}  # avg 100 vs 10 over 3 days
    rows = build_comparison_rows(
        "Asset",
        spot_map,
        sum_map,
        Decimal("3"),
        1,
        False,
        date(2025, 1, 1),
        lambda *_: Decimal("1"),
    )
    assert len(rows) == 1
    assert rows[0]["category"] == "big"


def test_build_comparison_rows_insufficient_window_yields_null_avg() -> None:
    """A1 治理：窗口不足且未显式仿真时，avg/deviation 为 None，spot 保留真实值。"""
    spot_map = {"A": Decimal("100"), "B": Decimal("500")}
    sum_map = {"A": Decimal("100"), "B": Decimal("500")}

    def _factor_must_not_be_called(*_args):
        raise AssertionError("stable factor must not run when simulation is off")

    rows = build_comparison_rows(
        "Asset",
        spot_map,
        sum_map,
        Decimal("1"),
        None,
        False,
        date(2025, 1, 1),
        _factor_must_not_be_called,
        insufficient_window=True,
    )
    assert [r["category"] for r in rows] == ["B", "A"]  # falls back to spot ordering
    for row in rows:
        assert row["avg"] is None
        assert row["deviation"] is None
        assert row["spot"] > 0


def test_enrich_frames_warn_when_balance_input_is_coerced_to_nan(caplog) -> None:
    caplog.set_level("WARNING", logger="backend.app.core_finance.adb_analytics")

    enrich_bonds_asset_frame(
        pd.DataFrame(
            {
                "bond_category": ["asset"],
                "market_value": ["not-a-number"],
                "yield_to_maturity": [Decimal("0.02")],
            }
        )
    )
    enrich_bonds_liability_frame(
        pd.DataFrame(
            {
                "bond_category": ["liability"],
                "market_value": ["dirty"],
                "coupon_rate": [Decimal("0.03")],
            }
        )
    )
    enrich_interbank_frame(
        pd.DataFrame(
            {
                "product_type": ["ib"],
                "amount": ["bad-amount"],
                "interest_rate": [Decimal("0.015")],
            }
        )
    )

    messages = [record.getMessage() for record in caplog.records]
    assert any("bonds_asset.market_value" in message and "not-a-number" in message for message in messages)
    assert any("bonds_liability.market_value" in message and "dirty" in message for message in messages)
    assert any("interbank.amount" in message and "bad-amount" in message for message in messages)


def test_enrich_frames_do_not_warn_for_valid_balance_inputs(caplog) -> None:
    caplog.set_level("WARNING", logger="backend.app.core_finance.adb_analytics")

    enrich_bonds_asset_frame(
        pd.DataFrame(
            {
                "bond_category": ["asset"],
                "market_value": [Decimal("100")],
                "yield_to_maturity": [Decimal("0.02")],
            }
        )
    )
    enrich_bonds_liability_frame(
        pd.DataFrame(
            {
                "bond_category": ["liability"],
                "market_value": [Decimal("200")],
                "coupon_rate": [Decimal("0.03")],
            }
        )
    )
    enrich_interbank_frame(
        pd.DataFrame(
            {
                "product_type": ["ib"],
                "amount": [Decimal("300")],
                "interest_rate": [Decimal("0.015")],
            }
        )
    )

    assert caplog.records == []


def test_liability_missing_coupon_is_excluded_from_rate_coverage() -> None:
    frame = enrich_bonds_liability_frame(
        pd.DataFrame(
            {
                "bond_category": ["liability", "liability", "zero-coupon"],
                "market_value": [Decimal("100"), Decimal("100"), Decimal("50")],
                "coupon_rate": [None, Decimal("2.0"), Decimal("0")],
            }
        )
    )

    rate_map, total_rate, coverage_map = build_rate_map([frame])

    assert frame["rate_decimal"].tolist() == [None, 0.02, 0.0]
    assert rate_map["liability"] == 2.0
    assert coverage_map["liability"] == 0.5
    assert rate_map["zero-coupon"] == 0.0
    assert coverage_map["zero-coupon"] == 1.0
    assert total_rate == pytest.approx(1.3333)
    assert coverage_map["__total__"] == 0.6
