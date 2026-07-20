"""CTA / DCC-GARCH / Risk Parity observation capability cards."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro.cta_trend import compute_cta_trend_payload, compute_composite
from backend.app.core_finance.macro.dcc_garch import (
    classify_warning,
    compute_dcc_garch_payload,
    garch_standardize,
)
from backend.app.core_finance.macro.risk_parity import (
    compute_risk_parity_payload,
    risk_contributions,
    solve_risk_budget,
    solve_risk_parity,
)
from backend.app.core_finance.macro.toolkit.scripts import cta_trend_cn as cta_script
from backend.app.core_finance.macro.toolkit.scripts import dcc_garch_cn as dcc_script
from backend.app.core_finance.macro.toolkit.scripts import risk_parity_cn as rp_script


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


def test_risk_parity_degenerate_covariance_is_unavailable() -> None:
    # 常数价格（如被 ffill 拉平）协方差为零：不得输出"等权 + 0 波动"的 complete 假象。
    idx = pd.bdate_range("2025-01-02", periods=150)
    frame = pd.DataFrame(
        {"hs300": 100.0, "csi500": 200.0, "copper": 300.0, "nanhua": 400.0},
        index=idx,
    )
    payload = compute_risk_parity_payload(frame, report_date=idx[-1].date(), clock_phase="复苏")
    assert payload["data_status"] == "unavailable"
    assert "RISK_PARITY_COV_DEGENERATE" in payload["warnings"]


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


def test_missing_leg_degrades_with_leg_warning() -> None:
    frame = _correlated_prices(n=260)
    report_date = frame.index[-1].date()
    series_data = {
        column: [(ts.date(), float(value)) for ts, value in frame[column].items()]
        for column in ("hs300", "csi500", "copper")
    }
    # 接线层对缺数据的腿保留空列表（见 _load_multi_asset_price_series）
    series_data["nanhua"] = []

    cta = compute_cta_trend_payload(series_data, report_date=report_date)
    assert cta["data_status"] == "degraded"
    assert "NANHUA_MISSING" in cta["warnings"]

    dcc = compute_dcc_garch_payload(series_data, report_date=report_date, window=40)
    assert dcc["data_status"] == "degraded"
    assert "NANHUA_MISSING" in dcc["warnings"]

    rp = compute_risk_parity_payload(series_data, report_date=report_date, clock_phase="复苏")
    assert rp["data_status"] == "degraded"
    assert "NANHUA_MISSING" in rp["warnings"]


def test_multi_asset_loader_keeps_empty_legs(monkeypatch) -> None:
    frame = _correlated_prices(n=40)

    def fake_load_series_by_aliases(aliases, **_kwargs):
        empty = pd.DataFrame(columns=["date", "value", "series_id", "vendor_name"])
        frames = {}
        for alias in aliases:
            if alias == "NH0100.NHF":
                frames[alias] = empty
            else:
                frames[alias] = pd.DataFrame(
                    {
                        "date": [ts.date().isoformat() for ts in frame.index],
                        "value": frame["hs300"].to_numpy(),
                        "series_id": alias,
                        "vendor_name": "test",
                    }
                )
        return frames

    monkeypatch.setattr(macro_toolkit_route, "load_series_by_aliases", fake_load_series_by_aliases)
    series_data = macro_toolkit_route._load_multi_asset_price_series(
        "unused.duckdb",
        frame.index[-1].date(),
    )
    assert set(series_data) == {"hs300", "csi500", "copper", "nanhua"}
    assert series_data["nanhua"] == []
    assert series_data["hs300"]


def test_dcc_garch_standardize_matches_script_helper() -> None:
    price = _correlated_prices()["hs300"]
    log_ret = np.log(price / price.shift(1)).dropna() * 100
    left = garch_standardize(log_ret)
    right = dcc_script._garch_standardize(log_ret)
    pd.testing.assert_series_equal(left, right, check_names=False)


def test_dcc_warning_thresholds_match_script() -> None:
    for value in (0.95, 0.9, 0.85, 0.80, 0.75, 0.70, 0.5, 0.2, -0.4):
        assert classify_warning(value) == dcc_script.classify_warning(value)


def test_risk_parity_solvers_match_script() -> None:
    frame = _correlated_prices(n=220)
    cov = np.log(frame / frame.shift(1)).dropna().cov().values * 252

    w_lib = solve_risk_parity(cov)
    w_script = rp_script.solve_risk_parity(cov)
    np.testing.assert_allclose(w_lib, w_script, atol=1e-8)

    budget = [0.30, 0.25, 0.20, 0.25]
    np.testing.assert_allclose(
        solve_risk_budget(cov, budget),
        rp_script.solve_risk_budget(cov, budget),
        atol=1e-8,
    )

    rc_lib, sig_lib = risk_contributions(w_lib, cov)
    rc_script, sig_script = rp_script.risk_contributions(w_lib, cov)
    np.testing.assert_allclose(rc_lib, rc_script, atol=1e-12)
    np.testing.assert_allclose(sig_lib, sig_script, atol=1e-12)


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
