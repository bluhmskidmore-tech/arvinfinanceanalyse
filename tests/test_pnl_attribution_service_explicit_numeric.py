"""W3.2 verification: pnl_attribution_service envelopes construct
explicit Numeric-dicts at the service layer; the schema coerce
validator is defense-in-depth, not the live code path."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest


NUMERIC_KEYS = {"raw", "unit", "display", "precision", "sign_aware"}


def _pnl_svc():
    """Resolve at call time so tests stay aligned if other suites reload the module."""
    return importlib.import_module("backend.app.services.pnl_attribution_service")


class _EmptyRepo:
    def list_formal_fi_report_dates(self) -> list[str]:
        return []

    def list_report_dates(self) -> list[str]:
        return []

    def fetch_formal_fi_rows(self, *_args, **_kwargs) -> list[dict[str, Any]]:
        return []

    def fetch_bond_analytics_rows(self, *_args, **_kwargs) -> list[dict[str, Any]]:
        return []

    def fetch_curve(self, *_args, **_kwargs) -> dict[str, Any] | None:
        return None


class _CampisiRepo:
    def list_report_dates(self) -> list[str]:
        return ["2026-01-31", "2026-01-01"]

    def fetch_bond_analytics_rows(self, *, report_date: str) -> list[dict[str, Any]]:
        return [{"instrument_code": f"BOND-{report_date}"}]

    def fetch_curve(self, *_args, **_kwargs) -> dict[str, Any] | None:
        return {"3Y": 2.5}


@dataclass
class _CampisiCoreResult:
    num_days: int
    totals: dict[str, float]
    by_asset_class: list[dict[str, Any]]
    by_bond: list[dict[str, Any]]
    diagnostics: list[str]


@pytest.fixture(autouse=True)
def _stub_repos(monkeypatch: pytest.MonkeyPatch):
    stub = _EmptyRepo()
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: stub)
    monkeypatch.setattr(mod, "_bond_repo", lambda: stub)
    monkeypatch.setattr(mod, "_curve_repo", lambda: stub)


def _assert_numeric_dict(value: Any) -> None:
    assert isinstance(value, dict), f"expected Numeric-dict, got {type(value).__name__}: {value!r}"
    assert NUMERIC_KEYS <= set(value.keys()), f"missing keys in {value!r}"
    assert isinstance(value["unit"], str)


def test_volume_rate_envelope_empty_produces_numeric_dicts():
    env = _pnl_svc().volume_rate_attribution_envelope(report_date=None, compare_type="mom")
    result = env["result"]
    for k in ("total_current_pnl",):
        _assert_numeric_dict(result[k])
    # Optional totals present as dict or None
    for k in ("total_previous_pnl", "total_pnl_change", "total_volume_effect"):
        v = result.get(k)
        assert v is None or (isinstance(v, dict) and NUMERIC_KEYS <= set(v.keys()))


def test_tpl_market_envelope_empty_produces_numeric_dicts():
    env = _pnl_svc().tpl_market_correlation_envelope(months=12)
    result = env["result"]
    _assert_numeric_dict(result["total_tpl_fv_change"])


def test_composition_envelope_empty_produces_numeric_dicts():
    env = _pnl_svc().pnl_composition_envelope(report_date=None)
    result = env["result"]
    for k in (
        "total_pnl",
        "total_interest_income",
        "total_fair_value_change",
        "total_capital_gain",
        "total_other_income",
        "interest_pct",
        "fair_value_pct",
        "capital_gain_pct",
        "other_pct",
    ):
        _assert_numeric_dict(result[k])


def test_attribution_analysis_summary_envelope_empty():
    env = _pnl_svc().attribution_analysis_summary_envelope(report_date=None)
    _assert_numeric_dict(env["result"]["primary_driver_pct"])


def test_carry_roll_down_envelope_empty():
    env = _pnl_svc().carry_roll_down_envelope(report_date=None)
    result = env["result"]
    for k in (
        "total_market_value",
        "portfolio_carry",
        "portfolio_rolldown",
        "portfolio_static_return",
        "total_carry_pnl",
        "total_rolldown_pnl",
        "total_static_pnl",
        "ftp_rate",
    ):
        _assert_numeric_dict(result[k])


def test_spread_envelope_empty():
    env = _pnl_svc().spread_attribution_envelope(report_date=None, lookback_days=30)
    result = env["result"]
    for k in ("total_market_value", "portfolio_duration", "total_treasury_effect", "total_spread_effect", "total_price_change"):
        _assert_numeric_dict(result[k])


def test_krd_envelope_empty():
    env = _pnl_svc().krd_attribution_envelope(report_date=None, lookback_days=30)
    result = env["result"]
    for k in ("total_market_value", "portfolio_duration", "portfolio_dv01", "total_duration_effect", "max_contribution_value"):
        _assert_numeric_dict(result[k])


def test_advanced_summary_envelope_empty():
    env = _pnl_svc().advanced_attribution_summary_envelope(report_date=None)
    result = env["result"]
    for k in ("portfolio_carry", "portfolio_rolldown", "static_return_annualized", "treasury_effect_total", "spread_effect_total"):
        _assert_numeric_dict(result[k])


def test_campisi_envelope_empty():
    env = _pnl_svc().campisi_attribution_envelope(start_date=None, end_date=None, lookback_days=30)
    result = env["result"]
    for k in (
        "total_market_value",
        "total_return",
        "total_return_pct",
        "total_income",
        "total_treasury_effect",
        "total_spread_effect",
        "total_selection_effect",
        "income_contribution_pct",
        "treasury_contribution_pct",
        "spread_contribution_pct",
        "selection_contribution_pct",
    ):
        _assert_numeric_dict(result[k])


def test_campisi_envelope_adapts_core_result(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    repo = _CampisiRepo()
    calls: dict[str, Any] = {}

    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)
    monkeypatch.setattr(
        mod,
        "merge_positions",
        lambda rows_start, rows_end: [{"bond_code": "BOND1", "market_value_start": 1000.0}],
    )
    monkeypatch.setattr(mod, "fetch_credit_spread_market", lambda _repo, _trade_date: {"credit_spread_aaa_3y": 50.0})

    def _fake_core(**kwargs: Any) -> _CampisiCoreResult:
        calls.update(kwargs)
        return _CampisiCoreResult(
            num_days=30,
            totals={
                "market_value_start": 1000.0,
                "total_return": 107.0,
                "income_return": 60.0,
                "treasury_effect": -10.0,
                "spread_effect": 57.0,
                "selection_effect": 0.0,
            },
            by_asset_class=[
                {
                    "asset_class": "credit AAA",
                    "market_value_start": 1000.0,
                    "weight_pct": 100.0,
                    "total_return": 107.0,
                    "total_return_pct": 10.7,
                    "income_return": 60.0,
                    "income_return_pct": 6.0,
                    "treasury_effect": -10.0,
                    "treasury_effect_pct": -1.0,
                    "spread_effect": 57.0,
                    "spread_effect_pct": 5.7,
                    "selection_effect": 0.0,
                    "selection_effect_pct": 0.0,
                }
            ],
            by_bond=[],
            diagnostics=["BOND1: accrued interest missing"],
        )

    monkeypatch.setattr(mod, "_core_campisi", _fake_core)

    env = mod.campisi_attribution_envelope(start_date="2026-01-01", end_date="2026-01-31", lookback_days=30)
    result = env["result"]

    assert calls["positions_merged"] == [{"bond_code": "BOND1", "market_value_start": 1000.0}]
    assert calls["market_start"]["treasury_3y"] == 2.5
    assert calls["market_end"]["credit_spread_aaa_3y"] == 50.0
    assert calls["start_date"] == date(2026, 1, 1)
    assert calls["end_date"] == date(2026, 1, 31)
    assert result["num_days"] == 30
    assert result["primary_driver"] == "mixed"
    assert result["warnings"] == ["BOND1: accrued interest missing", mod.WARN]
    assert result["total_income"]["raw"] == 60.0
    assert result["total_return_pct"]["raw"] == pytest.approx(0.107)
    assert result["total_return_pct"]["display"] == "+10.70%"
    assert result["income_contribution_pct"]["raw"] == pytest.approx(0.560748)
    assert result["items"][0]["category"] == "credit AAA"
    assert result["items"][0]["weight"]["raw"] == 1.0


def test_promote_helper_passthrough_already_promoted():
    # Idempotency: a promoted dict goes through unchanged.
    from backend.app.schemas.common_numeric import numeric_from_raw
    from backend.app.schemas.pnl_attribution import VolumeRateAttributionPayload

    already = numeric_from_raw(raw=1.0, unit="yuan", sign_aware=True).model_dump(mode="json")
    payload = {
        "current_period": "2025-04",
        "previous_period": "",
        "compare_type": "mom",
        "total_current_pnl": already,
        "items": [],
        "has_previous_data": False,
    }
    promoted = _pnl_svc()._promote_payload_numerics(payload, VolumeRateAttributionPayload)
    assert promoted["total_current_pnl"] == already


def test_promote_helper_handles_nested_item_list():
    from backend.app.schemas.pnl_attribution import VolumeRateAttributionPayload

    payload = {
        "current_period": "2025-04",
        "previous_period": "2025-03",
        "compare_type": "mom",
        "total_current_pnl": 1e9,
        "items": [
            {
                "category": "TPL",
                "category_type": "asset",
                "level": 0,
                "current_scale": 1e11,
                "current_pnl": 5e8,
            }
        ],
        "has_previous_data": True,
    }
    promoted = _pnl_svc()._promote_payload_numerics(payload, VolumeRateAttributionPayload)
    assert isinstance(promoted["total_current_pnl"], dict)
    assert NUMERIC_KEYS <= set(promoted["total_current_pnl"].keys())
    item = promoted["items"][0]
    assert isinstance(item["current_scale"], dict)
    assert item["current_scale"]["unit"] == "yuan"
    assert item["current_scale"]["sign_aware"] is False
    assert isinstance(item["current_pnl"], dict)
    assert item["current_pnl"]["sign_aware"] is True


def test_promote_helper_treats_small_pct_values_as_percent_points():
    from backend.app.schemas.pnl_attribution import VolumeRateAttributionPayload

    payload = {
        "current_period": "2026-04",
        "previous_period": "2026-03",
        "compare_type": "mom",
        "total_current_pnl": 110_000.0,
        "items": [
            {
                "category": "A",
                "category_type": "asset",
                "level": 0,
                "current_scale": 100_000_000.0,
                "current_pnl": 110_000.0,
                "current_yield_pct": 0.11,
                "previous_scale": 100_000_000.0,
                "previous_pnl": 100_000.0,
                "previous_yield_pct": 0.10,
                "pnl_change_pct": 10.0,
                "volume_contribution_pct": 0.5,
            }
        ],
        "has_previous_data": True,
    }

    promoted = _pnl_svc()._promote_payload_numerics(payload, VolumeRateAttributionPayload)
    row = promoted["items"][0]

    assert row["current_yield_pct"]["raw"] == pytest.approx(0.0011)
    assert row["current_yield_pct"]["display"] == "+0.11%"
    assert row["previous_yield_pct"]["raw"] == pytest.approx(0.001)
    assert row["previous_yield_pct"]["display"] == "+0.10%"
    assert row["pnl_change_pct"]["display"] == "+10.00%"
    assert row["volume_contribution_pct"]["display"] == "+0.50%"


def test_promote_helper_keeps_tpl_rate_changes_in_bp():
    from backend.app.schemas.pnl_attribution import TPLMarketCorrelationPayload

    payload = {
        "start_period": "2026-02",
        "end_period": "2026-03",
        "num_periods": 2,
        "correlation_coefficient": -0.62,
        "correlation_interpretation": "test",
        "total_tpl_fv_change": 42_000_000.0,
        "avg_treasury_10y_change": -7.5,
        "treasury_10y_total_change_bp": -15.0,
        "analysis_summary": "summary",
        "data_points": [
            {
                "period": "2026-03",
                "period_label": "2026-03",
                "tpl_fair_value_change": 32_000_000.0,
                "tpl_total_pnl": 32_000_000.0,
                "tpl_scale": 1_100_000_000.0,
                "treasury_10y": 2.2,
                "treasury_10y_change": -15.0,
                "dr007": None,
            }
        ],
    }

    promoted = _pnl_svc()._promote_payload_numerics(payload, TPLMarketCorrelationPayload)

    assert promoted["avg_treasury_10y_change"]["unit"] == "bp"
    assert promoted["avg_treasury_10y_change"]["raw"] == pytest.approx(-7.5)
    assert promoted["treasury_10y_total_change_bp"]["raw"] == pytest.approx(-15.0)
    point = promoted["data_points"][0]
    assert point["treasury_10y_change"]["unit"] == "bp"
    assert point["treasury_10y_change"]["raw"] == pytest.approx(-15.0)
    assert point["treasury_10y"]["unit"] == "pct"
    assert point["treasury_10y"]["display"] == "+2.20%"
