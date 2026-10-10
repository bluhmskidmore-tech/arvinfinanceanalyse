"""Regression tests for ADB rate weighting balance validity."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest

from backend.app.core_finance.adb_analytics import build_rate_map
from backend.app.services import adb_analysis_service


def _bond_row(
    *,
    balance: float,
    balance_valid: bool,
    rate_percent: float,
    issued: bool = False,
) -> dict[str, object]:
    return {
        "report_date": pd.Timestamp("2026-03-01"),
        "bond_category": "发行债券" if issued else "国债",
        "asset_class": "发行" if issued else "债券类",
        "is_issuance_like": issued,
        "market_value": balance,
        "market_value_is_valid": balance_valid,
        "yield_to_maturity": rate_percent,
        "coupon_rate": rate_percent,
    }


def _interbank_row(
    *,
    balance: float,
    balance_valid: bool,
    rate_percent: float,
    direction: str,
) -> dict[str, object]:
    return {
        "report_date": pd.Timestamp("2026-03-01"),
        "product_type": "拆放同业" if direction == "ASSET" else "卖出回购证券",
        "direction": direction,
        "amount": balance,
        "amount_is_valid": balance_valid,
        "interest_rate": rate_percent,
    }


def test_build_rate_map_excludes_invalid_balance_and_keeps_valid_zero() -> None:
    frame = pd.DataFrame(
        {
            "category": ["asset", "asset", "asset"],
            "balance": [100.0, 900.0, 0.0],
            "balance_valid": [True, False, True],
            "rate_decimal": [0.02, 0.10, 0.10],
        }
    )

    rate_map, total_rate, coverage_map = build_rate_map([frame])

    assert rate_map == {"asset": 2.0}
    assert total_rate == 2.0
    assert coverage_map == {"asset": 1.0, "__total__": 1.0}


@pytest.mark.parametrize(
    "non_finite_balance",
    [float("inf"), float("-inf")],
    ids=["positive-infinity", "negative-infinity"],
)
def test_build_rate_map_ignores_non_finite_balance_and_is_strict_json_safe(
    non_finite_balance: float,
) -> None:
    frame = pd.DataFrame(
        {
            "category": ["asset", "asset"],
            "balance": [100.0, non_finite_balance],
            "balance_valid": [True, True],
            "rate_decimal": [0.02, 0.10],
        }
    )

    rate_map, total_rate, coverage_map = build_rate_map([frame])
    payload = {
        "rate_map": rate_map,
        "total_rate": total_rate,
        "coverage_map": coverage_map,
    }

    json.dumps(payload, allow_nan=False)
    assert rate_map == {"asset": 2.0}
    assert total_rate == 2.0
    assert coverage_map == {"asset": 1.0, "__total__": 1.0}


def test_split_rate_frames_preserves_balance_valid_for_all_four_branches() -> None:
    bonds_df = pd.DataFrame(
        [
            _bond_row(balance=100.0, balance_valid=False, rate_percent=2.0),
            _bond_row(balance=200.0, balance_valid=True, rate_percent=1.0, issued=True),
        ]
    )
    interbank_df = pd.DataFrame(
        [
            _interbank_row(
                balance=300.0,
                balance_valid=False,
                rate_percent=2.5,
                direction="ASSET",
            ),
            _interbank_row(
                balance=400.0,
                balance_valid=True,
                rate_percent=1.5,
                direction="LIABILITY",
            ),
        ]
    )

    asset_frames, liability_frames, *_ = adb_analysis_service._split_rate_frames(
        bonds_df,
        interbank_df,
    )

    assert [frame["balance_valid"].tolist() for frame in asset_frames] == [
        [False],
        [False],
    ]
    assert [frame["balance_valid"].tolist() for frame in liability_frames] == [
        [True],
        [True],
    ]


@pytest.mark.parametrize(
    "non_finite_balance",
    [float("inf"), float("-inf")],
    ids=["positive-infinity", "negative-infinity"],
)
def test_adb_insights_rate_payload_ignores_invalid_and_non_finite_balances(
    non_finite_balance: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bonds_df = pd.DataFrame(
        [
            _bond_row(balance=100.0, balance_valid=True, rate_percent=2.0),
            _bond_row(balance=900.0, balance_valid=False, rate_percent=10.0),
            _bond_row(
                balance=non_finite_balance,
                balance_valid=True,
                rate_percent=10.0,
            ),
            _bond_row(balance=0.0, balance_valid=True, rate_percent=10.0),
        ]
    )
    interbank_df = pd.DataFrame(
        [
            _interbank_row(
                balance=100.0,
                balance_valid=True,
                rate_percent=1.0,
                direction="LIABILITY",
            )
        ]
    )

    monkeypatch.setattr(
        adb_analysis_service,
        "_load_adb_raw_data",
        lambda *_args, **_kwargs: (
            bonds_df,
            interbank_df,
            ["sv-rate-validity"],
            ["rv-rate-validity"],
            "formal_calendar",
            ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
            {
                "converted_rows": 0,
                "dropped_rows": 0,
                "converted_by_currency": {},
                "dropped_by_currency": {},
            },
        ),
    )

    window, *_ = adb_analysis_service._load_adb_insights_window(
        "unused.duckdb",
        date(2026, 3, 1),
        date(2026, 3, 2),
    )
    payload = adb_analysis_service.build_adb_insights_payload(
        current=window,
        qoq=window,
        yoy=window,
    )

    assert window.assets.total_rate == 2.0
    assert window.liabilities.total_rate == 1.0
    assert payload["nim_attribution"] is not None
    json.dumps(payload, allow_nan=False)
