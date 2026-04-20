"""W3.2 verification: pnl_attribution_service envelopes construct
explicit Numeric-dicts at the service layer; the schema coerce
validator is defense-in-depth, not the live code path."""
from __future__ import annotations

import importlib
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
