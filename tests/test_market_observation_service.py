"""Scoped acceptance of analytical market PRD, not Phase 2 formalization."""
import pytest

from backend.app.services.market_observation_service import build_market_observations

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_market_data]


def point(series_id, value, previous, **overrides):
    return {"series_id": series_id, "value_numeric": value, "unit": "%", "trade_date": "2026-09-04",
            "quality_flag": "ok", "vendor_name": "verified_curve_source",
            "recent_points": [{"trade_date": "2026-09-03", "value_numeric": previous, "quality_flag": "ok"}], **overrides}


def observations(extra=(), **kwargs):
    return build_market_observations({"series": [
        point("CA.DR007", 1.5, 1.6), point("NCD.SHIBOR.3M", 1.43, 1.42),
        point("EMM00588704", 1.25, 1.30), point("EMM00166462", 1.5, 1.52),
        point("EMM00166466", 1.68, 1.70), *extra]}, source_ok=True, receipt_ready=True, **kwargs)


def test_policy_verified_interval_and_bp():
    funding, rates = observations(policy_evidence={"value": 1.4, "unit": "%", "source": "policy publication",
        "effective_from": "2026-09-01", "validity_status": "verified"})
    assert funding["policy_deviation_bp"] == 10
    assert funding["rows"][0]["change_bp"] == -10
    assert rates["rows"][0]["change_bp"] == -5
    assert rates["spreads"][0]["previous_value_bp"] == 40
    assert rates["spreads"][0]["value_bp"] == 43
    assert rates["spreads"][0]["change_bp"] == 3
    assert rates["full_curve_comparison_allowed"]


def test_missing_policy_does_not_block_independent_rates():
    funding, rates = observations()
    assert funding["policy_deviation_bp"] is None
    assert funding["rows"][0]["value"] == 1.5
    assert rates["judgment_allowed"]


@pytest.mark.parametrize("override", [{"unit": "unknown"}, {"quality_flag": "stale"}, {"fallback_mode": "previous"},
    {"trade_date": "2026-09-02"}, {"value_numeric": None}, {"value_numeric": float("nan")}])
def test_invalid_leg_prevents_spread(override):
    _, rates = build_market_observations({"series": [point("EMM00588704", 1.25, 1.3, **override),
        point("EMM00166466", 1.68, 1.7)]}, source_ok=True, receipt_ready=True)
    assert rates["spreads"][0]["change_bp"] is None
    assert not rates["full_curve_comparison_allowed"]


def test_partial_curve_and_blocked_receipt():
    series = [point("EMM00588704", 1.25, 1.3), point("EMM00166466", 1.68, 1.7)]
    _, partial = build_market_observations({"series": series}, source_ok=True, receipt_ready=True)
    assert partial["spreads"][0]["change_bp"] == 3
    assert not partial["full_curve_comparison_allowed"]
    _, blocked = build_market_observations({"series": series}, source_ok=True, receipt_ready=False)
    assert not blocked["judgment_allowed"]
    assert blocked["rows"][0]["value"] == 1.25
    assert blocked["spreads"][0]["value_bp"] is None


def test_proxy_identity_zero_and_tiny_changes():
    funding, rates = build_market_observations({"series": [
        point("CA.DR007", 1.37, 1.37, policy_note="public FDR007; not the exact Choice series"),
        point("NCD.SHIBOR.3M", 1.43, 1.43), point("EMM00166466", 1.6804, 1.6798)]},
        source_ok=True, receipt_ready=True)
    assert funding["rows"][0]["label"] == "FDR007（DR007代理参考）"
    assert not funding["judgment_allowed"]
    assert funding["rows"][1]["change_bp"] == 0
    assert rates["rows"][2]["change_bp"] == 0.06


def test_comparison_dates_are_not_silently_mixed():
    _, rates = build_market_observations({"series": [
        point("EMM00588704", 1.25, 1.3, recent_points=[{"trade_date": "2026-09-02", "value_numeric": 1.3, "quality_flag": "ok"}]),
        point("EMM00166466", 1.68, 1.7)]}, source_ok=True, receipt_ready=True)
    assert rates["comparison_date"] == "2026-09-03"
    assert rates["spreads"][0]["change_bp"] is None


def test_selected_alias_uses_its_own_quality_and_blocked_receipt_cannot_restore_it():
    series = [point("CA.DR007", 1.5, 1.6, quality_flag="warning"), point("M002", 1.2, 1.3)]
    for receipt_ready in (True, False):
        funding, _ = build_market_observations(
            {"series": series}, source_ok=True, receipt_ready=receipt_ready,
        )
        assert funding["rows"][0]["series_id"] == "CA.DR007"
        assert funding["rows"][0]["value"] == 1.5
        assert funding["rows"][0]["change_bp"] is None
        assert not funding["judgment_allowed"]


def test_shibor_label_only_changes_proven_proxy():
    import pandas as pd
    from backend.app.services.macro_toolkit_route_support import _indicator_payload
    config = {"key": "ncd_3m", "alias": "M0041813", "label": "3M NCD", "group": "资金利率", "unit": "%"}
    row = {"date": "2026-09-04", "value": 1.43, "vendor_name": "tushare", "series_id": "NCD.SHIBOR.3M"}
    assert _indicator_payload(config, pd.DataFrame([row]))["label"] == "SHIBOR 3M（期限报价参考）"
    row["series_id"] = "actual_ncd_3m"
    assert _indicator_payload(config, pd.DataFrame([row]))["label"] == "3M NCD"


def test_receipt_preserves_run_evidence_and_signal_names_proxy():
    from backend.app.services.macro_toolkit_refresh_receipt_service import _summarize_step_statuses
    from backend.app.services.macro_toolkit_analysis_service import _liquidity_card
    result = {"run_id": "run1", "row_count": 2, "covered_required_series": ["EMM00588704"], "failed_sources": []}
    assert _summarize_step_statuses({"steps": [{"step": "public_cross_asset_headlines", "status": "success", "result": result}]})["public_cross_asset_headlines"] == {"status": "success", **result}
    card = _liquidity_card({"ncd_3m": {"series_id": "NCD.SHIBOR.3M", "latest_value": 1.43}})
    assert any("SHIBOR 3M" in str(value) for value in card.values())
    assert "3M NCD" not in str(card)
