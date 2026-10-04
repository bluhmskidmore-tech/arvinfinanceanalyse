from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest

from backend.app.api.routes import market_overview as route
from backend.app.observability.response_cache import TTLResponseCache
from backend.app.services import market_overview_service as service


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_market_data,
]


def _component_envelope(
    *,
    vendor_status: str = "ok",
    quality_flag: str = "ok",
    coverage: tuple[int, int] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {"value": 1}
    result_kind = "test.component"
    if coverage is not None:
        indicator_count, hit_count = coverage
        result["coverage"] = {
            "indicator_count": indicator_count,
            "hit_count": hit_count,
        }
        result_kind = "macro_toolkit.analysis"
    return {
        "result": result,
        "result_meta": {
            "result_kind": result_kind,
            "basis": "analytical",
            "quality_flag": quality_flag,
            "vendor_status": vendor_status,
            "fallback_mode": "none",
            "fallback_date": None,
            "formal_use_allowed": False,
        },
    }


def _snapshot(component: dict[str, object]) -> dict[str, object]:
    return {
        "result": {"components": {"macro_analysis_core": component}},
        "result_meta": {"quality_flag": "warning"},
    }


def _patch_route(
    monkeypatch: pytest.MonkeyPatch,
    cache: TTLResponseCache,
    builder: Callable[..., dict[str, object]],
) -> None:
    monkeypatch.setattr(route, "ensure_read_allowed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        route,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path="isolated.duckdb"),
    )
    monkeypatch.setattr(
        route,
        "load_macro_toolkit_refresh_receipt_health",
        lambda: SimpleNamespace(cache_fingerprint="ready:test"),
    )
    monkeypatch.setattr(route, "market_home_response_cache", cache)
    monkeypatch.setattr(route, "build_market_snapshot", builder)


def test_vendor_unavailable_component_expires_after_short_ttl_without_hit_renewal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])
    calls = 0

    def build() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _component_envelope(
            vendor_status="vendor_unavailable" if calls == 1 else "ok"
        )

    monkeypatch.setattr(service, "market_home_response_cache", cache)
    first = service._load_cached_component("choice_latest", cache_key="choice", builder=build)
    now[0] = 10
    second = service._load_cached_component("choice_latest", cache_key="choice", builder=build)
    now[0] = 16
    recovered = service._load_cached_component("choice_latest", cache_key="choice", builder=build)

    assert first.status == second.status == "degraded"
    assert recovered.status == "ok"
    assert calls == 2


def test_shared_vendor_unavailable_prefill_is_shortened_on_component_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])
    calls = 0
    cached_unavailable = _component_envelope(vendor_status="vendor_unavailable")
    cache.set("choice", cached_unavailable)

    def build() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _component_envelope()

    monkeypatch.setattr(service, "market_home_response_cache", cache)
    first = service._load_cached_component("choice_latest", cache_key="choice", builder=build)
    now[0] = 10
    second = service._load_cached_component("choice_latest", cache_key="choice", builder=build)
    now[0] = 16
    recovered = service._load_cached_component("choice_latest", cache_key="choice", builder=build)

    assert first.envelope is second.envelope is cached_unavailable
    assert calls == 1
    assert recovered.status == "ok"


def test_all_macro_inputs_unavailable_is_explicit_and_uses_short_component_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])
    calls = 0

    def build() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _component_envelope(
            coverage=(3, 0) if calls == 1 else (3, 3),
            quality_flag="warning",
        )

    monkeypatch.setattr(service, "market_home_response_cache", cache)
    unavailable = service._load_cached_component("macro_analysis_core", cache_key="core", builder=build)
    now[0] = 16
    recovered = service._load_cached_component("macro_analysis_core", cache_key="core", builder=build)

    assert unavailable.status == "unavailable"
    assert unavailable.reason == "macro analysis inputs unavailable: coverage hit_count=0"
    assert recovered.status == "degraded"
    assert recovered.reason == "quality_flag=warning"
    assert calls == 2


def test_complete_input_quality_warning_keeps_normal_component_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])
    calls = 0

    def build() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _component_envelope(coverage=(3, 3), quality_flag="warning")

    monkeypatch.setattr(service, "market_home_response_cache", cache)
    first = service._load_cached_component("macro_analysis_core", cache_key="core", builder=build)
    now[0] = 16
    second = service._load_cached_component("macro_analysis_core", cache_key="core", builder=build)

    assert first.status == second.status == "degraded"
    assert calls == 1


def test_component_short_ttl_write_respects_cache_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = TTLResponseCache(default_ttl_seconds=300)
    calls = 0

    def build() -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            cache.invalidate()
        return _component_envelope(vendor_status="vendor_unavailable")

    monkeypatch.setattr(service, "market_home_response_cache", cache)
    service._load_cached_component("choice_latest", cache_key="choice", builder=build)
    service._load_cached_component("choice_latest", cache_key="choice", builder=build)

    assert calls == 2


def test_snapshot_transient_unavailability_uses_short_ttl_without_hit_renewal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])
    calls = 0

    def build(**_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _snapshot(
            {
                "status": "degraded" if calls == 1 else "ok",
                "reason": "vendor_status=vendor_unavailable" if calls == 1 else None,
                "quality_flag": "warning" if calls == 1 else "ok",
                "vendor_status": "vendor_unavailable" if calls == 1 else "ok",
            }
        )

    _patch_route(monkeypatch, cache, build)
    route.market_overview_snapshot(auth=object(), include="gate")
    now[0] = 10
    route.market_overview_snapshot(auth=object(), include="gate")
    now[0] = 16
    recovered = route.market_overview_snapshot(auth=object(), include="gate")

    assert calls == 2
    assert recovered["result"]["components"]["macro_analysis_core"]["status"] == "ok"


def test_warmup_snapshot_prefill_is_shortened_on_route_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])
    calls = 0
    cached_unavailable = _snapshot(
        {
            "status": "degraded",
            "reason": "vendor_status=vendor_unavailable",
            "quality_flag": "warning",
            "vendor_status": "vendor_unavailable",
        }
    )
    cache_key = service.market_overview_snapshot_cache_key(
        include=frozenset({"gate"}),
        duckdb_path="isolated.duckdb",
        freshness_fingerprint="ready:test",
    )
    cache.set(cache_key, cached_unavailable)

    def build(**_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _snapshot(
            {
                "status": "ok",
                "reason": None,
                "quality_flag": "ok",
                "vendor_status": "ok",
            }
        )

    _patch_route(monkeypatch, cache, build)
    first = route.market_overview_snapshot(auth=object(), include="gate")
    now[0] = 10
    second = route.market_overview_snapshot(auth=object(), include="gate")
    now[0] = 16
    recovered = route.market_overview_snapshot(auth=object(), include="gate")

    assert first is second is cached_unavailable
    assert calls == 1
    assert recovered["result"]["components"]["macro_analysis_core"]["status"] == "ok"


def test_snapshot_complete_input_quality_warning_keeps_normal_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    cache = TTLResponseCache(default_ttl_seconds=300, clock=lambda: now[0])
    calls = 0

    def build(**_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _snapshot(
            {
                "status": "degraded",
                "reason": "quality_flag=warning",
                "quality_flag": "warning",
                "vendor_status": "ok",
            }
        )

    _patch_route(monkeypatch, cache, build)
    route.market_overview_snapshot(auth=object(), include="gate")
    now[0] = 16
    route.market_overview_snapshot(auth=object(), include="gate")

    assert calls == 1
