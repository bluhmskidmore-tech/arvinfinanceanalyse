from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.app.api.routes import market_overview as route
from backend.app.core_finance.macro.toolkit import system_sources
from backend.app.observability.response_cache import CacheBuildTimeoutError, TTLResponseCache
from backend.app.schemas.market_overview import MarketOverviewCrisis, MarketOverviewPulse
from backend.app.services import market_overview_service as service
from backend.app.services.macro_toolkit_refresh_receipt_service import MacroToolkitRefreshReceiptHealth

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]


def _component(result, **meta):
    return service._component_from_envelope(
        "test", cache_key=None,
        envelope={"result": result, "result_meta": {"quality_flag": "ok", "vendor_status": "ok", **meta}},
    )


def _health(category="scheduler_configuration_error"):
    return MacroToolkitRefreshReceiptHealth(
        status="blocked", ready=False, cache_fingerprint="blocked:test",
        generated_at="2026-09-05T01:00:00+00:00", run_status="failed",
        source_version="test", missing_fields=("receipt.status",), warnings=(),
        latest_observation_dates={}, failure_category=category,
        failure_message="ValueError: source_ip 192.0.2.1 is not assigned to this host (available IPv4: 192.0.2.2)",
    )


def test_component_fallback_and_vendor_status_are_visible_without_changing_values():
    component = _component(
        {"value": 2.1}, vendor_status="vendor_stale", fallback_mode="latest_snapshot",
        fallback_date="2026-08-31", formal_use_allowed=False,
    )
    assert component.status == "degraded"
    payload = service._component_payload({"market_rates": component})["market_rates"]
    assert payload["vendor_status"] == "vendor_stale"
    assert payload["fallback_mode"] == "latest_snapshot"
    assert payload["fallback_date"] == "2026-08-31"
    assert payload["formal_use_allowed"] is False
    assert component.envelope["result"]["value"] == 2.1


def test_missing_use_metadata_is_unknown_not_formal_permission():
    assert service._component_use_metadata(_component({})) == {
        "fallback_mode": None, "fallback_date": None, "formal_use_allowed": None,
    }


def test_pulse_uses_local_monthly_aliases_dates_units_and_preserves_single_point_null(monkeypatch):
    captured = {}

    def load(aliases, **kwargs):
        captured.update(aliases=aliases, **kwargs)
        return {
            "M0000612": pd.DataFrame([
                {"date": "2026-06-30", "value": 0.1, "series_id": "cn_cpi_yoy", "vendor_name": "test"},
                {"date": "2026-07-31", "value": 0.3, "series_id": "cn_cpi_yoy", "vendor_name": "test"},
            ]),
            "M0001227": pd.DataFrame([
                {"date": "2026-07-31", "value": -2.3, "series_id": "cn_ppi_yoy", "vendor_name": "test"},
            ]),
            "M0017126": pd.DataFrame([
                {"date": "2026-07-31", "value": 49.5, "series_id": "M0017126", "vendor_name": "test"},
                {"date": "2026-08-31", "value": 49.9, "series_id": "M0017126", "vendor_name": "test"},
            ]),
            "M5525763": pd.DataFrame(columns=["date", "value", "series_id", "vendor_name"]),
        }

    monkeypatch.setattr(system_sources, "load_series_by_aliases", load)
    envelope = service._load_macro_pulse_envelope("isolated.duckdb")
    pulse = service._build_pulse(service._component_from_envelope("macro_pulse", cache_key=None, envelope=envelope))
    MarketOverviewPulse.model_validate(pulse)
    by_key = {item["key"]: item for item in pulse["items"]}
    assert captured["aliases"] == ("M0000612", "M0001227", "M0017126", "M5525763")
    assert captured["duckdb_path"] == "isolated.duckdb"
    assert captured["end"]
    assert pulse["status"] == "degraded"
    assert by_key["cpi"]["latest_date"] == "2026-07-31"
    assert by_key["pmi"]["latest_date"] == "2026-08-31"
    assert by_key["cpi"]["unit"] == "%"
    assert by_key["cpi"]["change_unit"] == "百分点"
    assert by_key["cpi"]["change"] == pytest.approx(0.2)
    assert by_key["pmi"]["unit"] == "index"
    assert by_key["pmi"]["change_unit"] == "点"
    assert by_key["ppi"]["previous_value"] is None
    assert by_key["ppi"]["change"] is None
    assert by_key["social_financing"]["status"] == "unavailable"
    assert by_key["social_financing"]["label"] == "社融存量同比"
    assert all(by_key[key]["status"] == "ok" for key in ("cpi", "ppi", "pmi"))


def test_pulse_unknown_unit_is_explicit_and_does_not_guess_from_key():
    pulse = service._build_pulse(_component({"indicators": [
        {"key": "cpi", "latest_value": 0.3, "quality": "ok"},
    ]}))
    item = pulse["items"][0]
    assert item["unit"] is None and item["change_unit"] is None
    assert item["status"] == "degraded"
    assert item["reason"] == "单位未确认"


@pytest.mark.parametrize("vendor_version, source, mismatch", [
    ("vv_backfill_macro_nbs_pmi_release_20260905_exact", "国家统计局（官方发布）", None),
    ("vv_backfill_macro_tushare_cn_pmi_20260905_exact", "Tushare", None),
    ("vv_choice_edb_20260905", "Choice", None),
    ("vv_backfill_macro_nbs_pmi_release_20260905_exact", "来源待核验", "value"),
    ("vv_backfill_macro_nbs_pmi_release_20260905_exact", "来源待核验", "date"),
    ("vv_backfill_macro_nbs_pmi_release_20260905_exact", "来源待核验", "error"),
])
def test_pulse_source_uses_matching_observation_lineage(monkeypatch, vendor_version, source, mismatch):
    from datetime import date

    from backend.app.repositories.home_macro_release_context_repo import (
        HomeMacroObservation,
        HomeMacroSeriesRead,
    )

    frame = pd.DataFrame([{
        "date": "2026-08-01", "value": 49.8, "series_id": "M0017126", "vendor_name": "choice",
    }])
    monkeypatch.setattr(system_sources, "load_series_by_aliases", lambda aliases, **kwargs: {
        alias: frame if alias == "M0017126" else frame.iloc[:0] for alias in aliases
    })

    def read(_self, **kwargs):
        assert kwargs["cutoff_date"] == date(2026, 8, 1)
        assert kwargs["series_id"] == "M0017126"
        if mismatch == "error":
            raise OSError("lineage temporarily unavailable")
        return HomeMacroSeriesRead("fact_choice_macro_daily", "M0017126", [HomeMacroObservation(
            table="fact_choice_macro_daily", series_id="M0017126",
            observation_date=date(2026, 7, 1) if mismatch == "date" else date(2026, 8, 1),
            value=49.2 if mismatch == "value" else 49.8,
            cadence="monthly", unit="index", source_version="backfill_macro_v1",
            vendor_version=vendor_version, rule_version="test",
        )])

    monkeypatch.setattr(service.HomeMacroReleaseContextRepository, "read_recent_observations", read)
    item = service._load_macro_pulse_envelope("isolated.duckdb")["result"]["indicators"][2]
    assert item["source"] == source
    assert item["latest_value"] == 49.8 and item["latest_date"] == "2026-08-01"


def test_unavailable_crisis_keeps_history_without_current_score_or_regime():
    component = _component({"capability_results": [{
        "key": "crisis_score_cn", "score": 1.2,
        "result": {
            "data_status": "unavailable", "crisis_score": 1.2, "regime": "正常", "percentile": 60,
            "score_history": [{"date": "2026-08-31", "crisis_score": 1.2, "data_status": "complete"}],
        },
    }]})
    crisis = service._build_crisis(component)
    MarketOverviewCrisis.model_validate(crisis)
    assert crisis["current_available"] is False and crisis["history_only"] is True
    assert crisis["score"] is None and crisis["regime"] is None and crisis["percentile"] is None
    assert crisis["score_history"][0]["crisis_score"] == 1.2
    assert crisis["risk_gate"]["eligible"] is False


def test_explicit_null_current_score_closes_old_triggered_risk_gate():
    crisis = service._build_crisis(_component({"capability_results": [{
        "key": "crisis_score_cn", "score": 2.1,
        "result": {
            "data_status": "complete", "crisis_score": None,
            "risk_gate": {"eligible": True, "triggered": True, "threshold": 2.0, "reason_code": "crisis_score_at_or_above_threshold"},
            "score_history": [{"date": "2026-08-31", "crisis_score": 2.1, "data_status": "complete"}],
        },
    }]}))
    assert crisis["current_available"] is False
    assert crisis["history_only"] is True
    assert crisis["status"] != "ok"
    assert crisis["risk_gate"]["eligible"] is False
    assert crisis["risk_gate"]["triggered"] is False
    assert crisis["risk_gate"]["reason_code"] == "crisis_score_current_unavailable"


@pytest.mark.parametrize("category, expected", [
    ("scheduler_configuration_error", "出口地址或调度配置"),
    ("external_dependency_pending", "供应商权限"),
    ("upstream_unavailable", "上游数据服务恢复"),
])
def test_gate_redacts_technical_failure_including_cached_core_conclusion(category, expected):
    health = _health(category)
    gate = service._build_gate(health, _component({"conclusion": {"summary": health.failure_message}}))
    assert gate["level"] == "blocked"
    assert expected in gate["recovery_action"]
    assert "192.0.2" not in str(gate)
    assert "ValueError" not in str(gate)
    assert health.failure_message in str(health.as_payload())


def test_gate_recommendation_uses_business_words_without_mutating_core_payload():
    from dataclasses import replace

    health = replace(_health(), ready=True, status="ready")
    component = _component({"conclusion": {"recommended_action": "查看 signal_aggregator / risk_monitor"}})
    gate = service._build_gate(health, component)
    assert gate["conclusion"]["recommended_action"] == "复核宏观信号与风险监测结果，再形成今日判断。"
    assert "signal_aggregator" in component.envelope["result"]["conclusion"]["recommended_action"]


def _patch_route(monkeypatch, cache, builder):
    monkeypatch.setattr(route, "ensure_read_allowed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(route, "get_settings", lambda: SimpleNamespace(duckdb_path="isolated.duckdb"))
    monkeypatch.setattr(route, "load_macro_toolkit_refresh_receipt_health", _health)
    monkeypatch.setattr(route, "market_home_response_cache", cache)
    monkeypatch.setattr(route, "build_market_snapshot", builder)


def test_transient_component_failure_expires_quickly_and_hits_do_not_extend_it(monkeypatch):
    now = [0.0]
    calls = []
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])

    def build(**_kwargs):
        calls.append(1)
        failed = len(calls) == 1
        return {"result": {"components": {"choice_latest": {
            "status": "unavailable" if failed else "ok",
            "reason": "component load failed: TimeoutError" if failed else None,
        }}}}

    _patch_route(monkeypatch, cache, build)
    route.market_overview_snapshot(auth=object(), include="tape")
    now[0] = 10
    route.market_overview_snapshot(auth=object(), include="tape")
    assert len(calls) == 1
    now[0] = 16
    recovered = route.market_overview_snapshot(auth=object(), include="tape")
    assert len(calls) == 2
    assert recovered["result"]["components"]["choice_latest"]["status"] == "ok"


def test_macro_component_with_zero_hits_uses_short_cache_without_extending_hits(monkeypatch):
    now = [0.0]
    calls = []
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])

    def build():
        calls.append(1)
        hit_count = 0 if len(calls) == 1 else 1
        return {
            "result": {"coverage": {"indicator_count": 3, "hit_count": hit_count}},
            "result_meta": {
                "result_kind": "macro_toolkit.analysis",
                "quality_flag": "ok",
                "vendor_status": "ok",
            },
        }

    monkeypatch.setattr(service, "market_home_response_cache", cache)
    first = service._load_cached_component("macro_analysis_core", cache_key="macro", builder=build)
    assert first.status == "unavailable"
    now[0] = 10
    second = service._load_cached_component("macro_analysis_core", cache_key="macro", builder=build)
    assert second.status == "unavailable"
    assert len(calls) == 1
    now[0] = 16
    recovered = service._load_cached_component("macro_analysis_core", cache_key="macro", builder=build)
    assert recovered.status == "ok"
    assert len(calls) == 2


def test_snapshot_cache_wait_timeout_has_retryable_business_response(monkeypatch):
    class TimeoutCache:
        def generation(self):
            return 0

        def get_or_build_with_status(self, key, _builder):
            raise CacheBuildTimeoutError(key, 120)

    _patch_route(monkeypatch, TimeoutCache(), lambda **_kwargs: {})
    with pytest.raises(HTTPException) as exc:
        route.market_overview_snapshot(auth=object(), include="tape")
    assert exc.value.status_code == 503
    assert exc.value.headers == {"Retry-After": "15"}
    assert "isolated.duckdb" not in exc.value.detail
