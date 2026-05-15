from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Any

import pytest

from backend.app.core_finance.campisi import CampisiResult
from backend.app.services import pnl_attribution_service as svc


START_DATE = "2026-01-01"
END_DATE = "2026-01-31"

TREASURY_FLAT = {
    "1Y": 2.0,
    "3Y": 2.5,
    "5Y": 3.0,
    "7Y": 3.2,
    "10Y": 3.5,
    "30Y": 4.0,
}
TREASURY_UP = {
    "1Y": 4.0,
    "3Y": 4.5,
    "5Y": 5.0,
    "7Y": 5.2,
    "10Y": 5.5,
    "30Y": 6.0,
}


@dataclass
class FakeBondRepo:
    dates: list[str]
    rows_by_date: dict[str, list[dict[str, Any]]]

    def list_report_dates(self) -> list[str]:
        return list(self.dates)

    def fetch_bond_analytics_rows(self, *, report_date: str, **_kwargs: Any) -> list[dict[str, Any]]:
        return list(self.rows_by_date.get(report_date, []))


@dataclass
class FakeCurveRepo:
    curves: dict[tuple[str, str], dict[str, Any]]
    path: str = "non-existent.duckdb"

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, Any]:
        return dict(self.curves.get((trade_date, curve_type), {}))

    def fetch_latest_trade_date_on_or_before(self, _curve_type: str, _trade_date: str) -> str | None:
        return None


def _install_repos(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rows_start: list[dict[str, Any]] | None = None,
    rows_end: list[dict[str, Any]] | None = None,
    curves: dict[tuple[str, str], dict[str, Any]] | None = None,
    dates: list[str] | None = None,
) -> None:
    row_dates = dates if dates is not None else [END_DATE, START_DATE]
    rows_by_date = {
        START_DATE: list(rows_start or []),
        END_DATE: list(rows_end or []),
    }
    monkeypatch.setattr(svc, "_bond_repo", lambda: FakeBondRepo(row_dates, rows_by_date))
    monkeypatch.setattr(svc, "_curve_repo", lambda: FakeCurveRepo(curves or _curves()))


def _curves(
    *,
    treasury_start: dict[str, Any] | None = None,
    treasury_end: dict[str, Any] | None = None,
    aaa_spread_start: float = 50.0,
    aaa_spread_end: float = 50.0,
) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (START_DATE, "treasury"): treasury_start or TREASURY_FLAT,
        (END_DATE, "treasury"): treasury_end or TREASURY_FLAT,
        (START_DATE, "credit_spread_aaa"): {"3Y": aaa_spread_start},
        (END_DATE, "credit_spread_aaa"): {"3Y": aaa_spread_end},
        (START_DATE, "credit_spread_aa_plus"): {"3Y": 80.0},
        (END_DATE, "credit_spread_aa_plus"): {"3Y": 80.0},
        (START_DATE, "credit_spread_aa"): {"3Y": 100.0},
        (END_DATE, "credit_spread_aa"): {"3Y": 100.0},
    }


def _bond_rows(
    *,
    code: str = "BOND1",
    market_value_start: float = 1_000.0,
    market_value_end: float = 1_000.0,
    face_value: float = 1_000.0,
    accrued_interest_start: float | None = 0.0,
    accrued_interest_end: float | None = 0.0,
    coupon_rate: float = 0.03,
    ytm: float = 0.03,
    asset_class: str = "credit",
    rating: str = "AAA",
    maturity_date: date = date(2030, 1, 1),
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = {
        "instrument_code": code,
        "portfolio_name": "Portfolio",
        "cost_center": "CostCenter",
        "accounting_class": "FVOCI",
        "currency_code": "CNY",
        "face_value": face_value,
        "coupon_rate": coupon_rate,
        "ytm": ytm,
        "maturity_date": maturity_date,
        "asset_class_std": asset_class,
        "rating": rating,
    }
    return (
        {
            **base,
            "market_value": market_value_start,
            "accrued_interest": accrued_interest_start,
        },
        {
            **base,
            "market_value": market_value_end,
            "accrued_interest": accrued_interest_end,
        },
    )


def _result(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> dict[str, Any]:
    _install_repos(monkeypatch, **kwargs)
    return svc.campisi_attribution_envelope(
        start_date=START_DATE,
        end_date=END_DATE,
    )["result"]


def _raw(payload: dict[str, Any], key: str) -> float:
    value = payload[key]
    assert isinstance(value, dict)
    assert "raw" in value
    return float(value["raw"])


def test_empty_data_returns_valid_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_repos(monkeypatch, dates=[])

    envelope = svc.campisi_attribution_envelope(start_date=None, end_date=None)
    result = envelope["result"]

    assert result["items"] == []
    assert result["primary_driver"] == "unknown"
    assert result["num_days"] == 0
    assert envelope["result_meta"]["quality_flag"] == "warning"


def test_primary_driver_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    start, end = _bond_rows(
        market_value_start=1_000.0,
        market_value_end=1_000.0,
        accrued_interest_start=0.0,
        accrued_interest_end=2.4657534,
        coupon_rate=0.03,
    )
    income_result = _result(monkeypatch, rows_start=[start], rows_end=[end])
    assert income_result["primary_driver"] == "income"

    start, end = _bond_rows(
        code="TREASURY_DRIVER",
        market_value_start=1_000.0,
        market_value_end=803.0,
        accrued_interest_start=0.0,
        accrued_interest_end=0.0,
        coupon_rate=0.0,
        maturity_date=date(2036, 1, 1),
    )
    treasury_result = _result(
        monkeypatch,
        rows_start=[start],
        rows_end=[end],
        curves=_curves(treasury_start=TREASURY_FLAT, treasury_end=TREASURY_UP),
    )
    assert treasury_result["primary_driver"] == "treasury"
    assert _raw(treasury_result, "total_treasury_effect") < 0

    start, end = _bond_rows()
    _install_repos(monkeypatch, rows_start=[start], rows_end=[end])

    def fake_core_campisi(**_kwargs: Any) -> CampisiResult:
        return CampisiResult(
            num_days=30,
            totals={
                "market_value_start": 1_000.0,
                "total_return": 50.0,
                "income_return": 100.0,
                "treasury_effect": -95.0,
                "spread_effect": 10.0,
                "selection_effect": 1.0,
            },
            by_asset_class=[
                {
                    "asset_class": "credit AAA",
                    "market_value_start": 1_000.0,
                    "weight_pct": 100.0,
                    "total_return": 50.0,
                    "total_return_pct": 5.0,
                    "income_return": 100.0,
                    "income_return_pct": 10.0,
                    "treasury_effect": -95.0,
                    "treasury_effect_pct": -9.5,
                    "spread_effect": 10.0,
                    "spread_effect_pct": 1.0,
                    "selection_effect": 1.0,
                    "selection_effect_pct": 0.1,
                }
            ],
            by_bond=[],
            diagnostics=[],
        )

    monkeypatch.setattr(svc, "_core_campisi", fake_core_campisi)
    mixed_result = svc.campisi_attribution_envelope(start_date=START_DATE, end_date=END_DATE)["result"]

    assert mixed_result["primary_driver"] == "mixed"


def test_ac_accounting_zero_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    start, end = _bond_rows(
        market_value_start=1_000.0,
        market_value_end=1_200.0,
        accrued_interest_start=0.0,
        accrued_interest_end=50.0,
        coupon_rate=0.05,
        asset_class="\u644a\u4f59\u6210\u672c",
        maturity_date=date(2036, 1, 1),
    )

    result = _result(
        monkeypatch,
        rows_start=[start],
        rows_end=[end],
        curves=_curves(treasury_start=TREASURY_FLAT, treasury_end=TREASURY_UP, aaa_spread_end=100.0),
    )
    item = result["items"][0]

    assert _raw(item, "treasury_effect") == pytest.approx(0.0)
    assert _raw(item, "spread_effect") == pytest.approx(0.0)
    assert _raw(item, "selection_effect") == pytest.approx(0.0)
    assert _raw(item, "total_return") == pytest.approx(_raw(item, "income_return"))


def test_contribution_pct_zero_total_return_protected(monkeypatch: pytest.MonkeyPatch) -> None:
    start, end = _bond_rows()
    _install_repos(monkeypatch, rows_start=[start], rows_end=[end])

    def fake_core_campisi(**_kwargs: Any) -> CampisiResult:
        return CampisiResult(
            num_days=30,
            totals={
                "market_value_start": 1_000.0,
                "total_return": 1e-10,
                "income_return": 12.0,
                "treasury_effect": -8.0,
                "spread_effect": 1.0,
                "selection_effect": -5.0,
            },
            by_asset_class=[],
            by_bond=[],
            diagnostics=[],
        )

    monkeypatch.setattr(svc, "_core_campisi", fake_core_campisi)

    result = svc.campisi_attribution_envelope(start_date=START_DATE, end_date=END_DATE)["result"]

    for key in (
        "income_contribution_pct",
        "treasury_contribution_pct",
        "spread_contribution_pct",
        "selection_contribution_pct",
    ):
        raw = _raw(result, key)
        assert raw == 0.0
        assert isfinite(raw)


def test_diagnostics_propagate_to_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    start, end = _bond_rows(
        code="MISSING_AI",
        accrued_interest_start=None,
        accrued_interest_end=None,
    )

    result = _result(monkeypatch, rows_start=[start], rows_end=[end])

    warnings = result.get("warnings") or []
    assert any("accrued_interest_missing" in warning for warning in warnings)
    assert any("MISSING_AI" in warning for warning in warnings)


def test_legacy_campisi_envelope_uses_formal_bridge_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start, end = _bond_rows(
        code="BOND_FORMAL",
        market_value_start=1_000.0,
        market_value_end=1_100.0,
        accrued_interest_start=0.0,
        accrued_interest_end=0.0,
        coupon_rate=0.0,
    )
    _install_repos(monkeypatch, rows_start=[start], rows_end=[end])

    bridge = {
        "result": {
            "summary": {
                "total_actual_pnl": {"raw": 35.0},
            },
            "rows": [
                {
                    "instrument_code": "BOND_FORMAL",
                    "portfolio_name": "Portfolio",
                    "cost_center": "CostCenter",
                    "accounting_basis": "FVTPL",
                    "beginning_dirty_mv": {"raw": 1_000.0},
                    "carry": {"raw": 5.0},
                    "roll_down": {"raw": 1.0},
                    "treasury_curve": {"raw": 2.0},
                    "credit_spread": {"raw": 3.0},
                    "actual_pnl": {"raw": 35.0},
                }
            ],
        },
    }
    monkeypatch.setattr(
        svc,
        "_try_fetch_formal_bridge",
        lambda **_kwargs: bridge,
        raising=False,
    )

    envelope = svc.campisi_attribution_envelope(
        start_date=START_DATE,
        end_date=END_DATE,
    )
    result = envelope["result"]

    assert _raw(result, "total_return") == pytest.approx(35.0)
    assert _raw(result, "total_income") == pytest.approx(5.0)
    assert _raw(result, "total_treasury_effect") == pytest.approx(3.0)
    assert _raw(result, "total_spread_effect") == pytest.approx(3.0)
    assert _raw(result, "total_selection_effect") == pytest.approx(24.0)
    assert envelope["result_meta"]["as_of_date"] == END_DATE
    assert "fact_formal_pnl_fi" in envelope["result_meta"]["tables_used"]
