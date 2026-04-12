from __future__ import annotations

from decimal import Decimal

import pytest

from tests.helpers import load_module


class _ChoiceResult:
    Codes = [
        "EMM00166492",
        "EMM00166494",
        "EMM00166495",
        "EMM00166496",
        "EMM00166498",
        "EMM00166502",
        "EMM00166504",
    ]
    Dates = ["2026-04-10"]
    Data = {
        "EMM00166492": [[Decimal("1.10")]],
        "EMM00166494": [[Decimal("1.20")]],
        "EMM00166495": [[Decimal("1.30")]],
        "EMM00166496": [[Decimal("1.40")]],
        "EMM00166498": [[Decimal("1.50")]],
        "EMM00166502": [[Decimal("1.80")]],
        "EMM00166504": [[Decimal("2.10")]],
    }


class _TreasuryChoiceResult:
    Codes = [
        "EMM00166455",
        "EMM00166456",
        "EMM00166458",
        "EMM00588704",
        "EMM00166460",
        "EMM00166462",
        "EMM00166464",
        "EMM00166466",
        "EMM00166468",
        "EMM00166469",
    ]
    Dates = ["2026-04-10"]
    Data = {
        "EMM00166455": [[Decimal("1.01")]],
        "EMM00166456": [[Decimal("1.02")]],
        "EMM00166458": [[Decimal("1.10")]],
        "EMM00588704": [[Decimal("1.20")]],
        "EMM00166460": [[Decimal("1.30")]],
        "EMM00166462": [[Decimal("1.40")]],
        "EMM00166464": [[Decimal("1.50")]],
        "EMM00166466": [[Decimal("1.60")]],
        "EMM00166468": [[Decimal("1.80")]],
        "EMM00166469": [[Decimal("1.90")]],
    }


def test_treasury_choice_fallback_returns_normalized_snapshot(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(module.VendorAdapter, "_fetch_akshare_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.ChoiceClient, "edb", lambda *args, **kwargs: _TreasuryChoiceResult())

    snapshot = module.VendorAdapter().fetch_yield_curve("treasury", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "choice"
    assert tenor_map["3M"] == Decimal("1.01")
    assert tenor_map["30Y"] == Decimal("1.90")


def test_treasury_akshare_primary_returns_normalized_snapshot(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_curve",
        lambda *args, **kwargs: module._snapshot_from_points(
            curve_type="treasury",
            trade_date="2026-04-10",
            vendor_name="akshare",
            points=[
                module.YieldCurvePoint("3M", Decimal("1.01")),
                module.YieldCurvePoint("6M", Decimal("1.02")),
                module.YieldCurvePoint("1Y", Decimal("1.10")),
                module.YieldCurvePoint("2Y", Decimal("1.20")),
                module.YieldCurvePoint("3Y", Decimal("1.30")),
                module.YieldCurvePoint("5Y", Decimal("1.40")),
                module.YieldCurvePoint("7Y", Decimal("1.50")),
                module.YieldCurvePoint("10Y", Decimal("1.60")),
                module.YieldCurvePoint("20Y", Decimal("1.80")),
                module.YieldCurvePoint("30Y", Decimal("1.90")),
            ],
        ),
    )

    snapshot = module.VendorAdapter().fetch_yield_curve("treasury", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "akshare"
    assert tenor_map["3M"] == Decimal("1.01")
    assert tenor_map["30Y"] == Decimal("1.90")


def test_cdb_choice_fallback_synthesizes_30y_point(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(module.VendorAdapter, "_fetch_akshare_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.ChoiceClient, "edb", lambda *args, **kwargs: _ChoiceResult())

    snapshot = module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "choice"
    assert tenor_map["20Y"] == Decimal("2.10")
    assert tenor_map["30Y"] == Decimal("2.40")


def test_cdb_akshare_primary_synthesizes_30y_point(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )
    monkeypatch.setattr(
        module.VendorAdapter,
        "_fetch_akshare_records_locally",
        lambda *args, **kwargs: [
            {
                "曲线名称": "中债政策性金融债收益率曲线(国开行)",
                "日期": "2026-04-10",
                "6月": Decimal("1.10"),
                "1年": Decimal("1.20"),
                "2年": Decimal("1.30"),
                "3年": Decimal("1.40"),
                "5年": Decimal("1.50"),
                "10年": Decimal("1.80"),
                "20年": Decimal("2.10"),
            }
        ],
    )

    snapshot = module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")

    tenor_map = {point.tenor: point.rate_pct for point in snapshot.points}
    assert snapshot.vendor_name == "akshare"
    assert tenor_map["20Y"] == Decimal("2.10")
    assert tenor_map["30Y"] == Decimal("2.40")


def test_partial_choice_curve_is_rejected(monkeypatch):
    module = load_module(
        "backend.app.repositories.akshare_adapter",
        "backend/app/repositories/akshare_adapter.py",
    )

    class _PartialChoiceResult:
        Codes = ["EMM00166494"]
        Dates = ["2026-04-10"]
        Data = {"EMM00166494": [[Decimal("1.20")]]}

    monkeypatch.setattr(module.VendorAdapter, "_fetch_akshare_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.ChoiceClient, "edb", lambda *args, **kwargs: _PartialChoiceResult())

    with pytest.raises(RuntimeError):
        module.VendorAdapter().fetch_yield_curve("cdb", "2026-04-10")
