from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance import krd


def test_krd_classification_helpers_cover_rate_credit_and_accounting_classes() -> None:
    assert krd.classify_asset_class("国债") == "rate"
    assert krd.classify_asset_class("企业债") == "credit"
    assert krd.classify_asset_class("其他") == "other"

    assert krd.map_accounting_class("交易性金融资产") == "TPL"
    assert krd.map_accounting_class("其他债权投资") == "OCI"
    assert krd.map_accounting_class("债权投资") == "AC"


def test_build_krd_position_metrics_computes_weight_dv01_and_tenor_bucket() -> None:
    metrics = krd.build_krd_position_metrics(
        [
            {
                "bond_code": "240001.IB",
                "market_value": Decimal("100"),
                "coupon_rate": Decimal("0.03"),
                "yield_to_maturity": Decimal("0.032"),
                "report_date": date(2026, 3, 31),
                "maturity_date": date(2031, 3, 31),
                "bond_type": "国债",
                "asset_class": "交易性金融资产",
            }
        ],
        report_date=date(2026, 3, 31),
    )

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric["bond_code"] == "240001.IB"
    assert metric["asset_class"] == "rate"
    assert metric["accounting_class"] == "TPL"
    assert metric["tenor_bucket"] == "5Y"
    assert metric["duration"] > Decimal("0")
    assert metric["modified_duration"] > Decimal("0")
    assert metric["dv01"] > Decimal("0")
    assert metric["weight"] == Decimal("1")


def test_compute_curve_scenario_routes_tpl_and_oci_pnl_separately() -> None:
    scenario = {
        "name": "parallel_up_25bp",
        "description": "Parallel +25bp",
        "shocks": {"5Y": 25, "10Y": 25},
    }
    payload = krd.compute_curve_scenario(
        [
            {
                "tenor_bucket": "5Y",
                "market_value": Decimal("100"),
                "modified_duration": Decimal("4"),
                "convexity": Decimal("2"),
                "accounting_class": "TPL",
                "asset_class": "rate",
            },
            {
                "tenor_bucket": "10Y",
                "market_value": Decimal("80"),
                "modified_duration": Decimal("5"),
                "convexity": Decimal("3"),
                "accounting_class": "OCI",
                "asset_class": "credit",
            },
        ],
        scenario=scenario,
    )

    assert payload["scenario_name"] == "parallel_up_25bp"
    assert payload["pnl_tpl"] != Decimal("0")
    assert payload["pnl_oci"] != Decimal("0")
    assert payload["pnl_economic"] == payload["pnl_tpl"] + payload["pnl_oci"]
    assert payload["by_asset_class"]["rate"] != Decimal("0")
    assert payload["by_asset_class"]["credit"] != Decimal("0")
