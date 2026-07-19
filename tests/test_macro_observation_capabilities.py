"""CTA / DCC-GARCH / Risk Parity observation capability cards."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro.cta_trend import compute_cta_trend_payload, compute_composite
from backend.app.core_finance.macro.dcc_garch import classify_warning, compute_dcc_garch_payload
from backend.app.core_finance.macro.risk_parity import compute_risk_parity_payload, solve_risk_parity
from backend.app.core_finance.macro.toolkit.scripts import cta_trend_cn as cta_script


def _correlated_prices(n: int = 260, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2025-01-02", periods=n)
    shocks = rng.normal(0, 0.01, size=(n, 4))
    common = rng.normal(0, 0.008, size=n)
    rets = shocks * 0.6 + common.reshape(-1, 1) * 0.4
    levels = 100 * np.exp(np.cumsum(rets, axis=0))
    return pd.DataFrame(
        levels,
        index=idx,
        columns=["hs300", "csi500", "copper", "nanhua"],
    )


def test_cta_composite_matches_script_helper() -> None:
    price = _correlated_prices()["hs300"]
    left = compute_composite(price)
    right = cta_script.compute_composite(price)
    pd.testing.assert_frame_equal(left, right, check_names=False)


def test_cta_payload_complete_on_synthetic_prices() -> None:
    frame = _correlated_prices()
    payload = compute_cta_trend_payload(frame, report_date=frame.index[-1].date())
    assert payload["data_status"] == "complete"
    assert payload["formal_use_allowed"] is False
    assert payload["avg_composite"] is not None
    assert payload["asset_signals"]


def test_dcc_warning_thresholds() -> None:
    assert classify_warning(0.9) == "红色预警"
    assert classify_warning(0.75) == "黄色预警"
    assert classify_warning(0.2) == "正常"


def test_dcc_payload_surfaces_avg_correlation() -> None:
    frame = _correlated_prices(n=300)
    payload = compute_dcc_garch_payload(frame, report_date=frame.index[-1].date(), window=40)
    assert payload["data_status"] == "complete"
    assert payload["avg_correlation"] is not None
    assert payload["warning_level"] in {"正常", "黄色预警", "红色预警"}
    assert payload["pair_correlations"]


def test_risk_parity_weights_sum_to_one() -> None:
    frame = _correlated_prices(n=220)
    cov = np.log(frame / frame.shift(1)).dropna().cov().values * 252
    weights = solve_risk_parity(cov)
    assert abs(float(weights.sum()) - 1.0) < 1e-6


def test_risk_parity_payload_is_shadow_observation() -> None:
    frame = _correlated_prices(n=220)
    payload = compute_risk_parity_payload(
        frame,
        report_date=frame.index[-1].date(),
        clock_phase="复苏",
    )
    assert payload["data_status"] == "complete"
    assert payload["shadow"] is True
    assert payload["formal_use_allowed"] is False
    assert payload["clock_phase"] == "复苏"
    assert abs(sum(item["rp_weight_pct"] for item in payload["weights"]) - 100) < 0.5


def test_risk_parity_missing_clock_phase_defaults_to_recession_degraded() -> None:
    frame = _correlated_prices(n=220)
    payload = compute_risk_parity_payload(
        frame,
        report_date=frame.index[-1].date(),
        clock_phase=None,
    )
    assert payload["clock_phase"] == "衰退"
    assert payload["data_status"] == "degraded"
    assert "CLOCK_PHASE_MISSING_DEFAULT_RECESSION" in payload["warnings"]
    assert payload["shadow"] is True
    assert payload["formal_use_allowed"] is False


def test_capability_definitions_wired_for_observation_models() -> None:
    keys = {"cta_trend_cn", "dcc_garch_cn", "risk_parity_cn"}
    defs = {
        item["key"]: item
        for item in macro_toolkit_route._CAPABILITY_DEFINITIONS
        if item["key"] in keys
    }
    assert set(defs) == keys
    for item in defs.values():
        assert item["route_status"] == "wired"
        assert item["frontend_status"] == "visible"


def test_observation_capability_cards_render_metrics() -> None:
    frame = _correlated_prices(n=260)
    report_date = frame.index[-1].date()
    payloads = {
        "cta_trend_cn": compute_cta_trend_payload(frame, report_date=report_date),
        "dcc_garch_cn": compute_dcc_garch_payload(frame, report_date=report_date, window=40),
        "risk_parity_cn": compute_risk_parity_payload(
            frame,
            report_date=report_date,
            clock_phase="过热",
        ),
    }
    for key, raw in payloads.items():
        definition = next(item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS if item["key"] == key)
        card = macro_toolkit_route._capability_result_card(definition, raw)
        assert card["status"] in {"complete", "degraded"}
        assert card["primary_metric"] is not None
        assert card["evidence"]


def test_unavailable_when_prices_missing() -> None:
    report_date = date.today() - timedelta(days=1)
    assert compute_cta_trend_payload({}, report_date=report_date)["data_status"] == "unavailable"
    assert compute_dcc_garch_payload({}, report_date=report_date)["data_status"] == "unavailable"
    assert compute_risk_parity_payload({}, report_date=report_date)["data_status"] == "unavailable"


def test_macro_capability_results_wires_multi_asset_observation_cards(monkeypatch) -> None:
    frame = _correlated_prices(n=260)
    report_date = frame.index[-1].date()

    def fake_multi_asset_series(*_args, **_kwargs):
        return {
            column: [(ts.date(), float(value)) for ts, value in frame[column].items()]
            for column in frame.columns
        }

    monkeypatch.setattr(macro_toolkit_route, "_parse_report_date", lambda value: report_date)
    monkeypatch.setattr(
        macro_toolkit_route,
        "_load_macro_capability_context",
        lambda *_args, **_kwargs: ([], None, []),
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "load_series_by_aliases",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(macro_toolkit_route, "_load_macro_wide_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        macro_toolkit_route,
        "_risk_tensor_to_liquidity_inputs",
        lambda *_args, **_kwargs: ([], [], None),
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "build_bond_portfolio_profile",
        lambda *_args, **_kwargs: {"total_mv": 0.0, "weighted_duration": 0.0, "positions": []},
    )
    monkeypatch.setattr(macro_toolkit_route, "_current_gov_curve", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        macro_toolkit_route,
        "_with_capability_input_evidence",
        lambda key, result, **_kwargs: result,
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "_source_checks_for_aliases",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "_load_multi_asset_price_series",
        fake_multi_asset_series,
    )

    observation_keys = {"cta_trend_cn", "dcc_garch_cn", "risk_parity_cn"}
    monkeypatch.setattr(
        macro_toolkit_route,
        "_run_capability",
        lambda key, fn: fn() if key in observation_keys else {"data_status": "unavailable", "warnings": ["skipped"]},
    )

    cards = macro_toolkit_route._macro_capability_results(
        "unused.duckdb",
        report_date=report_date.isoformat(),
    )
    by_key = {item["key"]: item for item in cards}
    for key in observation_keys:
        card = by_key[key]
        assert card["status"] in {"complete", "degraded"}
        assert card["result"]["formal_use_allowed"] is False
    assert by_key["risk_parity_cn"]["result"]["shadow"] is True
