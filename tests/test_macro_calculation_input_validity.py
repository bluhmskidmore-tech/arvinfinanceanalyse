"""Synthetic calculation counterexamples; no production data or execution."""

from __future__ import annotations

from backend.app.services import macro_toolkit_route_support as macro_toolkit_support

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

import backend.app.core_finance.macro.risk_parity as risk_parity
from backend.app.core_finance.macro.a_share_stampede_risk import compute_a_share_stampede_risk
from backend.app.core_finance.macro.macro_etf_strategy import (
    DEFAULT_CONFIG,
    DEFAULT_MACRO_STATE,
    build_macro_etf_strategy_snapshot,
    deep_merge,
)
from backend.app.core_finance.macro.risk_parity import compute_risk_parity_payload
from backend.app.services.macro_etf_strategy_service import macro_etf_strategy_envelope

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_macro_toolkit]


@pytest.mark.parametrize("field", ["scores", "weights"])
@pytest.mark.parametrize("invalid", ["NaN", "Infinity", "-Infinity", None, "not-a-number"])
def test_invalid_macro_input_does_not_produce_position_or_orders(field, invalid) -> None:
    state = deep_merge(DEFAULT_MACRO_STATE, {field: {"domestic_liquidity": invalid}})
    quotes = {code: {"price": 1.0, "volume": 1_000_000, "prev_close": 1.0} for code in DEFAULT_CONFIG["universe"]}
    result = build_macro_etf_strategy_snapshot(
        macro_state=state, as_of_date=date(2026, 7, 3), quotes=quotes
    )

    assert result["macro"]["score"] is None
    assert result["macro"][field]["domestic_liquidity"] is None
    assert result["position"]["target_total_weight"] is None
    assert result["position"]["cash_weight"] is None
    assert result["position"]["target_weights"] == {}
    assert result["data_status"]["status"] == "blocked"
    assert result["order_draft"]["orders"] == []
    assert result["execution_enabled"] is False
    assert any("MACRO_INPUT_INVALID" in warning for warning in result["warnings"])
    json.dumps(result, allow_nan=False)


def test_macro_service_preserves_invalid_score_as_unavailable(tmp_path) -> None:
    config_path, macro_path = tmp_path / "config.json", tmp_path / "macro.json"
    config_path.write_text(json.dumps(DEFAULT_CONFIG), encoding="utf-8")
    macro_path.write_text(
        json.dumps(deep_merge(DEFAULT_MACRO_STATE, {"scores": {"domestic_liquidity": "NaN"}})),
        encoding="utf-8",
    )
    envelope = macro_etf_strategy_envelope(
        as_of_date="2026-07-03", config_path=config_path, macro_state_path=macro_path
    )
    assert envelope["result"]["macro"]["score"] is None
    assert envelope["result"]["position"]["target_total_weight"] is None
    assert envelope["result"]["dual_frequency"]["final_target_total_weight"] is None
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["quality_flag"] != "ok"
    json.dumps(envelope, allow_nan=False)


def test_partial_zero_volatility_cannot_satisfy_equal_positive_risk_budget() -> None:
    dates = pd.bdate_range("2026-01-02", periods=120)
    frame = pd.DataFrame({"hs300": 100.0, "csi500": [100.0, 101.0] * 60}, index=dates)
    for result in (
        compute_risk_parity_payload(frame, report_date=dates[-1].date(), clock_phase="recovery"),
        macro_toolkit_support._compute_multi_asset_observation_capability(
            "risk_parity_cn", "unused.duckdb", dates[-1].date(), clock_phase="recovery",
            series_data={col: [(day.date(), float(v)) for day, v in frame[col].items()] for col in frame},
        ),
    ):
        assert result["data_status"] == "unavailable"
        assert result["rule_version"] == "rv_macro_risk_parity_cn_v2"
        assert "RISK_PARITY_COV_DEGENERATE" in result["warnings"]
        assert result["weights"] == []
        assert result["portfolio_vol_rp_pct"] is None
        assert result["formal_use_allowed"] is False
        json.dumps(result, allow_nan=False)


def _breadth_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "trade_date": ["2026-07-03"] * 2000,
        "stock_code": [f"{i:06d}.SZ" for i in range(2000)],
        "close_value": 100.0, "pctchange": 1.0, "amount": 1_000_000.0,
        "highlimit": 110.0, "lowlimit": 90.0,
    })


@pytest.mark.parametrize("missing_count", [1, 2000])
@pytest.mark.parametrize("invalid", [None, float("inf"), float("-inf")])
def test_missing_breadth_is_unknown_not_zero_up_stocks(missing_count, invalid, monkeypatch) -> None:
    frame = _breadth_frame()
    frame["pctchange"] = frame["pctchange"].astype(object)
    frame.loc[:missing_count - 1, "pctchange"] = invalid
    monkeypatch.setattr(macro_toolkit_support, "_load_a_share_stampede_risk_context", lambda _: {"observations": frame})
    result = macro_toolkit_support._a_share_stampede_risk(None)

    assert result["status"] == "unavailable"
    assert result["risk_score"] is None
    assert result["risk_level"] == "unknown"
    assert result["metrics"]["up_ratio"] is None
    assert result["metrics"]["up_count"] is None
    assert result["metrics"]["pctchange_observed_count"] == 2000 - missing_count
    assert result["metrics"]["pctchange_coverage"] == pytest.approx((2000 - missing_count) / 2000)
    assert not result["triggered_rules"]
    assert any("BREADTH_PCTCHANGE_INCOMPLETE" in warning for warning in result["warnings"])
    json.dumps(result, allow_nan=False)


def test_bse_inclusion_configuration_changes_core_universe_only_when_enabled() -> None:
    frame = _breadth_frame()
    frame["is_bse"] = False
    frame.loc[:9, "is_bse"] = True
    default = compute_a_share_stampede_risk(frame)
    enabled = compute_a_share_stampede_risk(frame, config={"universe": {"include_bse_in_core": True}})
    assert default["metrics"]["core_stock_count"] == 1990
    assert enabled["metrics"]["core_stock_count"] == 2000
    assert enabled["metrics"]["up_count"] == 2000
    assert enabled["metrics"]["up_ratio"] == 1.0
    assert any("北交所" in warning for warning in default["warnings"])
    assert not any("北交所" in warning for warning in enabled["warnings"])


def test_observed_zero_macro_scores_are_valid() -> None:
    state = deep_merge(DEFAULT_MACRO_STATE, {"scores": {key: 0.0 for key in DEFAULT_MACRO_STATE["scores"]}})
    result = build_macro_etf_strategy_snapshot(macro_state=state, as_of_date=date(2026, 7, 3))
    assert result["macro"]["score"] == 0.0
    assert result["position"]["target_total_weight"] == 0.65
    assert not any("MACRO_INPUT_INVALID" in warning for warning in result["warnings"])


def test_observed_flat_prices_are_known_zero_up_stocks() -> None:
    frame = _breadth_frame()
    frame["pctchange"] = 0.0
    result = compute_a_share_stampede_risk(frame)
    assert result["status"] != "unavailable"
    assert result["metrics"]["up_count"] == 0
    assert result["metrics"]["up_ratio"] == 0.0
    assert result["metrics"]["pctchange_coverage"] == 1.0
    assert result["risk_score"] is not None


@pytest.mark.parametrize("price_scale", [1e-6, 1.0, 1e6])
def test_risk_parity_rejects_zero_risk_hedge_despite_positive_asset_variances(price_scale) -> None:
    dates = pd.bdate_range("2026-01-02", periods=120)
    frame = pd.DataFrame({"hs300": [100.0, 101.0] * 60, "csi500": [101.0, 100.0] * 60}, index=dates) * price_scale
    covariance = np.log(frame / frame.shift(1)).dropna().cov().values
    assert np.all(np.diag(covariance) > 0)

    result = compute_risk_parity_payload(frame, report_date=dates[-1].date(), clock_phase="recovery")

    assert result["data_status"] == "unavailable"
    assert "RISK_PARITY_SOLUTION_INVALID" in result["warnings"]
    assert result["weights"] == []
    assert result["portfolio_vol_rp_pct"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("price_scale", [1e-6, 1.0, 1e6])
def test_risk_parity_allows_positive_correlated_singular_covariance(price_scale) -> None:
    dates = pd.bdate_range("2026-01-02", periods=120)
    # Both assets share the same return. Equal positive risk contributions are feasible.
    frame = pd.DataFrame({"hs300": [100.0, 101.0] * 60, "csi500": [200.0, 202.0] * 60}, index=dates) * price_scale
    result = compute_risk_parity_payload(frame, report_date=dates[-1].date(), clock_phase="recovery")
    assert result["data_status"] == "complete"
    assert result["portfolio_vol_rp_pct"] > 0
    assert [item["rp_weight_pct"] for item in result["weights"]] == pytest.approx([50, 50])
    assert [item["rp_risk_contrib_pct"] for item in result["weights"]] == pytest.approx([50, 50])
    assert [item["rb_weight_pct"] for item in result["weights"]] == pytest.approx([58.33, 41.67])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("solver", ["solve_risk_parity_with_status", "solve_risk_budget_with_status"])
@pytest.mark.parametrize("weights", [[float("nan"), 0.5], [0.9, 0.1]])
def test_risk_parity_checks_solver_result_even_when_optimizer_reports_success(monkeypatch, solver, weights) -> None:
    dates = pd.bdate_range("2026-01-02", periods=120)
    frame = pd.DataFrame({"hs300": [100.0, 101.0] * 60, "csi500": [100.0, 101.0] * 60}, index=dates)
    monkeypatch.setattr(risk_parity, solver, lambda *_args: (np.array(weights), True))
    result = compute_risk_parity_payload(frame, report_date=dates[-1].date(), clock_phase="recovery")
    assert result["data_status"] == "unavailable"
    assert result["weights"] == []
    assert any(warning.endswith("SOLUTION_INVALID") for warning in result["warnings"])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("covariance_scale", [1e-12, 1.0, 1e12])
def test_risk_parity_solution_validation_is_independent_of_covariance_units(covariance_scale) -> None:
    # Perfect positive correlation with a 1:2 volatility ratio has an exact
    # equal-risk solution at 2/3 : 1/3. Singularity alone cannot invalidate it.
    positive_cov = np.array([[1.0, 2.0], [2.0, 4.0]]) * covariance_scale
    assert risk_parity._valid_risk_allocation(np.array([2 / 3, 1 / 3]), positive_cov, [0.5, 0.5])
    assert not risk_parity._valid_risk_allocation(np.array([0.5, 0.5]), positive_cov, [0.5, 0.5])
    hedge_cov = np.array([[1.0, -1.0], [-1.0, 1.0]]) * covariance_scale
    assert not risk_parity._valid_risk_allocation(np.array([0.5, 0.5]), hedge_cov, [0.5, 0.5])
