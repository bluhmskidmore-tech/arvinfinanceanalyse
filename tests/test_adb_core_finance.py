from __future__ import annotations

from datetime import date
from inspect import signature

import pandas as pd

from tests.helpers import load_module
from tests.test_adb_analysis_api import BOND_CERT, BOND_CORP, INTERBANK_PLACE


def test_adb_core_finance_exports_pure_payload_builders() -> None:
    core_mod = load_module(
        "backend.app.core_finance.adb_analysis",
        "backend/app/core_finance/adb_analysis.py",
    )

    assert callable(core_mod.build_adb_daily_payload)
    assert callable(core_mod.build_adb_comparison_payload)
    assert callable(core_mod.build_adb_monthly_payload)
    assert "duckdb_path" not in signature(core_mod.build_adb_daily_payload).parameters
    assert "duckdb_path" not in signature(core_mod.build_adb_comparison_payload).parameters
    assert "duckdb_path" not in signature(core_mod.build_adb_monthly_payload).parameters
    assert "as_of_date" in signature(core_mod.build_adb_monthly_payload).parameters


def test_build_adb_comparison_payload_returns_stable_contract() -> None:
    core_mod = load_module(
        "backend.app.core_finance.adb_analysis",
        "backend/app/core_finance/adb_analysis.py",
    )

    bonds_df = pd.DataFrame(
        [
            {
                "report_date": "2025-06-03",
                "market_value": 100.0,
                "yield_to_maturity": 2.4,
                "coupon_rate": 2.5,
                "interest_rate": 0.0,
                "asset_class": "\u503a\u5238\u7c7b",
                "sub_type": BOND_CORP,
                "is_issuance_like": False,
            }
        ]
    )
    bonds_df["report_date"] = pd.to_datetime(bonds_df["report_date"])

    interbank_df = pd.DataFrame(
        [
            {
                "report_date": "2025-06-03",
                "amount": 50.0,
                "interest_rate": 1.5,
                "product_type": "\u62c6\u653e\u540c\u4e1a",
                "direction": "ASSET",
            }
        ]
    )
    interbank_df["report_date"] = pd.to_datetime(interbank_df["report_date"])

    payload = core_mod.build_adb_comparison_payload(
        bonds_df=bonds_df,
        interbank_df=interbank_df,
        start_date=date(2025, 6, 3),
        end_date=date(2025, 6, 3),
        top_n=5,
        simulate_if_single_snapshot=True,
    )

    assert payload["report_date"] == "2025-06-03"
    assert payload["start_date"] == "2025-06-03"
    assert payload["end_date"] == "2025-06-03"
    assert payload["num_days"] == 1
    assert payload["simulated"] is True
    assert payload["asset_yield"] == 2.1
    assert payload["assets_breakdown"][0]["category"] == BOND_CORP
    assert payload["assets_breakdown"][0]["weighted_rate"] == 2.4


def test_build_adb_daily_payload_preserves_daily_classification_behavior() -> None:
    core_mod = load_module(
        "backend.app.core_finance.adb_analysis",
        "backend/app/core_finance/adb_analysis.py",
    )

    bonds_df = pd.DataFrame(
        [
            {
                "report_date": "2025-06-03",
                "market_value": 100.0,
                "yield_to_maturity": 2.4,
                "coupon_rate": 2.5,
                "asset_class": "\u503a\u5238\u7c7b",
                "sub_type": BOND_CORP,
                "is_issuance_like": False,
            },
            {
                "report_date": "2025-06-03",
                "market_value": 30.0,
                "yield_to_maturity": 0.0,
                "coupon_rate": 1.8,
                "asset_class": "\u53d1\u884c\u503a\u5238",
                "sub_type": BOND_CERT,
                "is_issuance_like": True,
            },
        ]
    )
    bonds_df["report_date"] = pd.to_datetime(bonds_df["report_date"])

    interbank_df = pd.DataFrame(
        [
            {
                "report_date": "2025-06-03",
                "amount": 50.0,
                "interest_rate": 1.5,
                "product_type": "\u62c6\u653e\u540c\u4e1a",
                "direction": "ASSET",
            },
            {
                "report_date": "2025-06-03",
                "amount": 20.0,
                "interest_rate": 1.2,
                "product_type": INTERBANK_PLACE,
                "direction": "LIABILITY",
            },
        ]
    )
    interbank_df["report_date"] = pd.to_datetime(interbank_df["report_date"])

    payload = core_mod.build_adb_daily_payload(
        bonds_df=bonds_df,
        interbank_df=interbank_df,
        start_date=date(2025, 6, 3),
        end_date=date(2025, 6, 3),
    )

    assert payload["summary"]["total_avg_assets"] == 150.0
    assert payload["summary"]["total_avg_liabilities"] == 50.0
    categories = {(row["category"], row["side"]): row["avg_balance"] for row in payload["breakdown"]}
    assert categories[(BOND_CORP, "Asset")] == 100.0
    assert categories[("Issuance-" + BOND_CERT, "Liability")] == 30.0


def test_build_adb_monthly_payload_requires_as_of_date_and_keeps_monthly_categories() -> None:
    core_mod = load_module(
        "backend.app.core_finance.adb_analysis",
        "backend/app/core_finance/adb_analysis.py",
    )

    bonds_df = pd.DataFrame(
        [
            {
                "report_date": "2025-01-15",
                "market_value": 100.0,
                "yield_to_maturity": 2.4,
                "coupon_rate": 2.5,
                "asset_class": "\u503a\u5238\u7c7b",
                "sub_type": BOND_CORP,
                "is_issuance_like": False,
            },
            {
                "report_date": "2025-01-15",
                "market_value": 30.0,
                "yield_to_maturity": 0.0,
                "coupon_rate": 1.8,
                "asset_class": "\u53d1\u884c\u503a\u5238",
                "sub_type": BOND_CERT,
                "is_issuance_like": True,
            },
        ]
    )
    bonds_df["report_date"] = pd.to_datetime(bonds_df["report_date"])

    interbank_df = pd.DataFrame(
        [
            {
                "report_date": "2025-01-15",
                "amount": 20.0,
                "interest_rate": 1.2,
                "product_type": INTERBANK_PLACE,
                "direction": "LIABILITY",
            }
        ]
    )
    interbank_df["report_date"] = pd.to_datetime(interbank_df["report_date"])

    payload = core_mod.build_adb_monthly_payload(
        bonds_df=bonds_df,
        interbank_df=interbank_df,
        as_of_date=date(2025, 1, 31),
    )

    month = payload["months"][0]
    asset_categories = {item["category"] for item in month["breakdown_assets"]}
    liability_categories = {item["category"] for item in month["breakdown_liabilities"]}

    assert month["month"] == "2025-01"
    assert month["month_label"] == "2025\u5e741\u6708"
    assert BOND_CORP in asset_categories
    assert "\u540c\u4e1a-" + INTERBANK_PLACE in liability_categories
    assert "\u53d1\u884c\u503a\u5238-" + BOND_CERT in liability_categories
