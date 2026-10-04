from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]



def _service_module():
    return load_module(
        "backend.app.services.livermore_signal_confluence_service",
        "backend/app/services/livermore_signal_confluence_service.py",
    )


def _route_confluence_envelope() -> dict[str, object]:
    return {
        "result_meta": {
            "basis": "analytical",
            "result_kind": "market_data.livermore.signal_confluence",
            "cache_version": "cv_test",
            "source_version": "sv_test",
            "rule_version": "rv_test",
            "quality_flag": "ok",
            "vendor_version": "vv_test",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "filters_applied": {"as_of_date": "2026-09-14"},
            "tables_used": ["fact_test"],
            "evidence_rows": 1,
        },
        "result": {
            "as_of_date": "2026-09-14",
            "strategy_context": {
                "allows_new_entry_observations": True,
                "new_entry_observation_allowed": True,
                "position_size_hint": {"max_position_pct": 5.0},
            },
            "closed_loop_state": {"status": "ready"},
            "position_size_hint": {"max_position_pct": 5.0},
            "entry_observations": [{"stock_code": "000001.SZ"}],
            "exit_observations": [{"stock_code": "000002.SZ"}],
        },
    }


@pytest.mark.parametrize(
    ("status", "digest_matches", "expected_status", "keeps_hints"),
    [
        ("ready", True, "ready", True),
        ("ready", False, "unavailable", False),
        ("ready_empty", True, "ready_empty", False),
    ],
)
def test_route_confluence_requires_exact_attested_projection(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    digest_matches: bool,
    expected_status: str,
    keeps_hints: bool,
) -> None:
    from backend.app.api.routes import market_data_livermore as route

    envelope = _route_confluence_envelope()
    digest = route.canonical_pretrade_confluence_projection_sha256(envelope)
    qualification = {
        "status": status,
        "target_date": "2026-09-14",
        "evidence_sha256": "a" * 64,
        "rule_identity": {"strategy_calculation_mode": route.STRATEGY_CALCULATION_MODE},
        "outputs": {
            "signal_confluence_sha256": digest if digest_matches else "0" * 64,
        },
    }
    monkeypatch.setattr(
        route,
        "livermore_signal_confluence_envelope",
        lambda **_kwargs: envelope,
    )

    payload = route._qualified_livermore_signal_confluence(
        duckdb_path="unused.duckdb",
        as_of_date="2026-09-14",
        catalog_file="unused.json",
        theme_overlay_reader=None,
        pretrade_qualification=qualification,
        captured_external_inputs={"identity_profiles": []},
        target_date="2026-09-14",
    )
    result = cast(dict[str, Any], payload["result"])

    assert result["pretrade_qualification"]["status"] == expected_status
    assert bool(result["entry_observations"]) is keeps_hints
    assert (result["position_size_hint"] is not None) is keeps_hints


def test_route_confluence_revalidates_authority_before_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from backend.app.api.routes import market_data_livermore as route

    checks = 0
    cache: dict[str, dict[str, object]] = {}
    envelope = _route_confluence_envelope()

    def selected_read(**_kwargs: object):
        nonlocal checks
        checks += 1
        return (
            {"status": "unavailable", "reason": "test_boundary"},
            None,
            "2026-09-14",
            "pretrade=test",
        )

    def get_or_build(key: str, builder):
        if key not in cache:
            cache[key] = builder()
        return cache[key]

    monkeypatch.setattr(route, "_selected_pretrade_external_read", selected_read)
    monkeypatch.setattr(route, "_ensure_livermore_read_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(route, "_theme_overlay_reader_from_settings", lambda _settings: None)
    monkeypatch.setattr(route, "_theme_overlay_fingerprint", lambda _reader: "none")
    monkeypatch.setattr(
        route,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=tmp_path / "moss.duckdb",
            choice_stock_catalog_file=tmp_path / "choice-stock.json",
        ),
    )
    monkeypatch.setattr(
        route,
        "livermore_signal_confluence_envelope",
        lambda **_kwargs: envelope,
    )
    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", get_or_build)
    auth = route.AuthContext(user_id="test", role="viewer", identity_source="test")

    route.livermore_signal_confluence(auth=auth, as_of_date="2026-09-14")
    route.livermore_signal_confluence(auth=auth, as_of_date="2026-09-14")

    assert checks == 2
    assert len(cache) == 1


def test_signal_confluence_warmup_and_api_share_qualified_unavailable_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from backend.app.api.routes import market_data_livermore as route
    from backend.app.services import (
        livermore_signal_confluence_service,
        market_data_livermore_service,
    )
    from backend.app.services import (
        market_data_livermore_route_support as support,
    )
    from backend.app.services import (
        market_home_warmup_service as warmup,
    )

    cache: dict[str, dict[str, object]] = {}
    signal_calls: list[dict[str, object]] = []
    envelope = _route_confluence_envelope()
    envelope["result"] = {
        **cast(dict[str, object], envelope["result"]),
        "as_of_date": "2026-09-02",
    }
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock.json",
    )

    def get_or_build(key: str, builder):
        if key not in cache:
            cache[key] = builder()
        return cache[key]

    def signal_envelope(**kwargs: object) -> dict[str, object]:
        signal_calls.append(kwargs)
        return envelope

    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", get_or_build)
    monkeypatch.setattr(support, "current_system_read_context", lambda: None)
    monkeypatch.setattr(warmup, "resolve_effective_read_path", lambda path: path)
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    monkeypatch.setattr(route, "_ensure_livermore_read_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(route, "_theme_overlay_reader_from_settings", lambda _settings: None)
    monkeypatch.setattr(route, "_theme_overlay_fingerprint", lambda _reader: "overlay-test")
    monkeypatch.setattr(support, "_theme_overlay_reader_from_settings", lambda _settings: None)
    monkeypatch.setattr(support, "_theme_overlay_fingerprint", lambda _reader: "overlay-test")
    monkeypatch.setattr(market_data_livermore_service, "livermore_data_version", lambda _path: "db-test")
    monkeypatch.setattr(market_data_livermore_service, "livermore_business_inputs_version", lambda: "inputs-test")
    for name, value in (
        ("livermore_data_version", lambda _path: "db-test"),
        ("livermore_business_inputs_version", lambda: "inputs-test"),
    ):
        if hasattr(route, name):
            monkeypatch.setattr(route, name, value)
    def strategy_envelope(**_kwargs: object) -> dict[str, object]:
        return {"result": {"as_of_date": "2026-09-02"}}
    monkeypatch.setattr(route, "livermore_strategy_envelope_from_catalog", strategy_envelope)
    monkeypatch.setattr(
        market_data_livermore_service,
        "livermore_strategy_envelope_from_catalog",
        strategy_envelope,
    )
    monkeypatch.setattr(route, "livermore_signal_confluence_envelope", signal_envelope)
    monkeypatch.setattr(
        livermore_signal_confluence_service,
        "livermore_signal_confluence_envelope",
        signal_envelope,
    )

    warmup._warm_livermore_signal_confluence(
        settings=settings,
        requested_as_of_date="2026-09-03",
        force_refresh=False,
    )
    auth = route.AuthContext(user_id="test", role="viewer", identity_source="test")
    api_payload = route.livermore_signal_confluence(auth=auth, as_of_date="2026-09-02")

    assert len(signal_calls) == 1
    assert len(cache) == 2  # strategy and qualified confluence
    qualified_key = next(key for key in cache if key.startswith("livermore/signal-confluence::"))
    assert "pretrade=none:unavailable:system_read_generation_missing" in qualified_key
    assert cache[qualified_key] is api_payload
    result = cast(dict[str, object], api_payload["result"])
    assert result["pretrade_qualification"]["status"] == "unavailable"
    assert result["entry_observations"] == []
    assert result["exit_observations"] == []
    assert result["position_size_hint"] is None

    other_date = route.livermore_signal_confluence(auth=auth, as_of_date="2026-09-03")
    assert len(signal_calls) == 2
    assert other_date["result"]["entry_observations"] == []

    monkeypatch.setattr(
        support,
        "current_system_read_context",
        lambda: SimpleNamespace(generation="gen-next", pretrade_availability=None),
    )
    other_generation = route.livermore_signal_confluence(
        auth=auth, as_of_date="2026-09-02"
    )
    assert len(signal_calls) == 3
    assert len(cache) == 4  # strategy plus three separately qualified contexts
    assert other_generation["result"]["entry_observations"] == []


def test_signal_confluence_warmup_and_api_share_selected_snapshot_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from importlib import import_module

    from backend.app.repositories.duckdb_read_context import (
        DuckDBReadSelection,
        duckdb_read_scope,
    )

    route = import_module("backend.app.api.routes.market_data_livermore")
    support = import_module("backend.app.services.market_data_livermore_route_support")
    strategy_service = import_module("backend.app.services.market_data_livermore_service")
    signal_service = import_module("backend.app.services.livermore_signal_confluence_service")
    warmup = import_module("backend.app.services.market_home_warmup_service")
    active_path = tmp_path / "active.duckdb"
    first_snapshot = tmp_path / "snapshot-one.duckdb"
    second_snapshot = tmp_path / "snapshot-two.duckdb"
    for path in (active_path, first_snapshot, second_snapshot):
        path.write_bytes(b"")  # Scope selection checks existence; no database is opened.
    settings = SimpleNamespace(
        duckdb_path=active_path,
        choice_stock_catalog_file=tmp_path / "choice-stock.json",
    )
    cache: dict[str, dict[str, object]] = {}
    signal_paths: list[str] = []

    def get_or_build(key: str, builder):
        if key not in cache:
            cache[key] = builder()
        return cache[key]

    def signal_envelope(**kwargs: object) -> dict[str, object]:
        signal_paths.append(str(kwargs["duckdb_path"]))
        return _route_confluence_envelope()

    def strategy_envelope(**_kwargs: object) -> dict[str, object]:
        return {"result": {"as_of_date": "2026-09-14"}}

    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", get_or_build)
    monkeypatch.setattr(support, "current_system_read_context", lambda: None)
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    monkeypatch.setattr(route, "_ensure_livermore_read_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(route, "_theme_overlay_reader_from_settings", lambda _settings: None)
    monkeypatch.setattr(route, "_theme_overlay_fingerprint", lambda _reader: "overlay-test")
    monkeypatch.setattr(support, "_theme_overlay_reader_from_settings", lambda _settings: None)
    monkeypatch.setattr(support, "_theme_overlay_fingerprint", lambda _reader: "overlay-test")
    monkeypatch.setattr(strategy_service, "livermore_data_version", lambda _path: "db-test")
    monkeypatch.setattr(strategy_service, "livermore_business_inputs_version", lambda: "inputs-test")
    for name, value in (
        ("livermore_data_version", lambda _path: "db-test"),
        ("livermore_business_inputs_version", lambda: "inputs-test"),
    ):
        if hasattr(route, name):
            monkeypatch.setattr(route, name, value)
    monkeypatch.setattr(route, "livermore_strategy_envelope_from_catalog", strategy_envelope)
    monkeypatch.setattr(strategy_service, "livermore_strategy_envelope_from_catalog", strategy_envelope)
    monkeypatch.setattr(route, "livermore_signal_confluence_envelope", signal_envelope)
    monkeypatch.setattr(signal_service, "livermore_signal_confluence_envelope", signal_envelope)
    auth = route.AuthContext(user_id="test", role="viewer", identity_source="test")

    first_selection = DuckDBReadSelection(active_path, first_snapshot, "generation-one")
    with duckdb_read_scope(first_selection, required_online=True, active_path=active_path):
        warmup._warm_livermore_signal_confluence(
            settings=settings,
            requested_as_of_date="2026-09-14",
            force_refresh=False,
        )
        route.livermore_signal_confluence(auth=auth, as_of_date="2026-09-14")
    assert signal_paths == [str(first_snapshot.resolve())]
    assert len([key for key in cache if key.startswith("livermore/signal-confluence::")]) == 1

    second_selection = DuckDBReadSelection(active_path, second_snapshot, "generation-two")
    with duckdb_read_scope(second_selection, required_online=True, active_path=active_path):
        route.livermore_signal_confluence(auth=auth, as_of_date="2026-09-14")
    assert signal_paths == [str(first_snapshot.resolve()), str(second_snapshot.resolve())]
    assert len([key for key in cache if key.startswith("livermore/signal-confluence::")]) == 2


@pytest.mark.parametrize("status", ["ready", "ready_empty"])
def test_signal_confluence_warmup_keeps_attested_status_and_rechecks_hot_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    status: str,
) -> None:
    from backend.app.api.routes import market_data_livermore as route
    from backend.app.services import (
        livermore_signal_confluence_service,
        market_data_livermore_service,
    )
    from backend.app.services import (
        market_data_livermore_route_support as support,
    )
    from backend.app.services import (
        market_home_warmup_service as warmup,
    )

    cache: dict[str, dict[str, object]] = {}
    signal_calls: list[dict[str, object]] = []
    envelope = _route_confluence_envelope()
    digest = route.canonical_pretrade_confluence_projection_sha256(envelope)
    evidence = {
        "status": status,
        "target_date": "2026-09-14",
        "evidence_sha256": ("a" if status == "ready" else "b") * 64,
        "rule_identity": {
            "strategy_calculation_mode": route.STRATEGY_CALCULATION_MODE,
        },
        "input_snapshot": {"external_sources": []},
        "outputs": {"signal_confluence_sha256": digest},
    }
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock.json",
    )

    def get_or_build(key: str, builder):
        if key not in cache:
            cache[key] = builder()
        return cache[key]

    def signal_envelope(**kwargs: object) -> dict[str, object]:
        signal_calls.append(kwargs)
        return envelope

    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", get_or_build)
    monkeypatch.setattr(warmup, "resolve_effective_read_path", lambda path: path)
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    monkeypatch.setattr(route, "_ensure_livermore_read_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(route, "_theme_overlay_reader_from_settings", lambda _settings: None)
    monkeypatch.setattr(route, "_theme_overlay_fingerprint", lambda _reader: "overlay-test")
    monkeypatch.setattr(support, "_theme_overlay_reader_from_settings", lambda _settings: None)
    monkeypatch.setattr(support, "_theme_overlay_fingerprint", lambda _reader: "overlay-test")
    monkeypatch.setattr(support, "current_system_read_context", lambda: SimpleNamespace(
        generation="gen-ready", pretrade_availability=evidence
    ))
    monkeypatch.setattr(support, "normalize_pretrade_qualification", lambda _value: evidence)
    monkeypatch.setattr(support, "qualify_sealed_pretrade_read", lambda **_kwargs: evidence)
    monkeypatch.setattr(
        support,
        "capture_livermore_external_inputs",
        lambda _catalog: {"identity_profiles": []},
    )
    monkeypatch.setattr(market_data_livermore_service, "livermore_data_version", lambda _path: "db-test")
    monkeypatch.setattr(market_data_livermore_service, "livermore_business_inputs_version", lambda: "inputs-test")
    for name, value in (
        ("livermore_data_version", lambda _path: "db-test"),
        ("livermore_business_inputs_version", lambda: "inputs-test"),
    ):
        if hasattr(route, name):
            monkeypatch.setattr(route, name, value)
    def strategy_envelope(**_kwargs: object) -> dict[str, object]:
        return {"result": {"as_of_date": "2026-09-14"}}
    monkeypatch.setattr(route, "livermore_strategy_envelope_from_catalog", strategy_envelope)
    monkeypatch.setattr(
        market_data_livermore_service,
        "livermore_strategy_envelope_from_catalog",
        strategy_envelope,
    )
    monkeypatch.setattr(route, "livermore_signal_confluence_envelope", signal_envelope)
    monkeypatch.setattr(
        livermore_signal_confluence_service,
        "livermore_signal_confluence_envelope",
        signal_envelope,
    )

    warmup._warm_livermore_signal_confluence(
        settings=settings,
        requested_as_of_date="2026-09-14",
        force_refresh=False,
    )
    auth = route.AuthContext(user_id="test", role="viewer", identity_source="test")
    ready_payload = route.livermore_signal_confluence(auth=auth, as_of_date="2026-09-14")
    ready_result = cast(dict[str, object], ready_payload["result"])
    assert len(signal_calls) == 1
    assert len(cache) == 2
    assert ready_result["pretrade_qualification"]["status"] == status
    assert bool(ready_result["entry_observations"]) is (status == "ready")
    assert any(f"pretrade=gen-ready:{status}:" in key for key in cache)

    monkeypatch.setattr(support, "current_system_read_context", lambda: None)
    unavailable_payload = route.livermore_signal_confluence(
        auth=auth, as_of_date="2026-09-14"
    )
    unavailable_result = cast(dict[str, object], unavailable_payload["result"])
    assert len(signal_calls) == 2
    assert len(cache) == 3
    assert unavailable_result["pretrade_qualification"]["status"] == "unavailable"
    assert unavailable_result["entry_observations"] == []
    assert unavailable_result["exit_observations"] == []
    assert unavailable_result["position_size_hint"] is None


def test_signal_confluence_force_refresh_keeps_cache_generation_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from backend.app.services import (
        livermore_signal_confluence_service,
        market_data_livermore_service,
    )
    from backend.app.services import (
        market_data_livermore_route_support as support,
    )

    writes: list[tuple[str, dict[str, object], int]] = []
    monkeypatch.setattr(
        support.market_home_response_cache,
        "get_or_build",
        lambda *_args: pytest.fail("force refresh must rebuild before guarded set"),
    )
    monkeypatch.setattr(support.market_home_response_cache, "generation", lambda: 17)
    monkeypatch.setattr(
        support.market_home_response_cache,
        "set",
        lambda key, payload, *, generation: writes.append((key, payload, generation)),
    )
    monkeypatch.setattr(market_data_livermore_service, "livermore_data_version", lambda _path: "db-test")
    monkeypatch.setattr(market_data_livermore_service, "livermore_business_inputs_version", lambda: "inputs-test")
    monkeypatch.setattr(
        livermore_signal_confluence_service,
        "livermore_signal_confluence_envelope",
        lambda **_kwargs: _route_confluence_envelope(),
    )

    payload = support._cached_livermore_signal_confluence(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        as_of_date="2026-09-14",
        catalog_file=tmp_path / "choice-stock.json",
        theme_overlay_reader=None,
        theme_overlay_fingerprint="overlay-test",
        selected_pretrade_read=(
            {"status": "unavailable", "reason": "synthetic_unavailable"},
            None,
            "2026-09-14",
            "pretrade=synthetic-unavailable",
        ),
        force_refresh=True,
    )

    assert len(writes) == 1
    assert writes[0][1] is payload
    assert writes[0][2] == 17
    assert "pretrade=synthetic-unavailable" in writes[0][0]
    assert payload["result"]["entry_observations"] == []


def _build_livermore_signal_confluence(
    *,
    as_of_date: str,
    livermore_payload: dict[str, object],
    macro_payload: dict[str, object],
    adversarial_payload: dict[str, object] | None = None,
    backtest_window_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    module = _service_module()
    normalized_livermore_payload = dict(livermore_payload)
    market_gate = normalized_livermore_payload.get("market_gate")
    if isinstance(market_gate, dict):
        normalized_market_gate = dict(market_gate)
        if "macro_context" not in normalized_market_gate:
            legacy_score = None
            for container_name in ("environment_score", "macro_environment"):
                container = macro_payload.get(container_name)
                if isinstance(container, dict) and isinstance(container.get("composite_score"), (int, float)):
                    legacy_score = float(container["composite_score"])
                    break
            if legacy_score is None or legacy_score != legacy_score or legacy_score in {
                float("inf"),
                float("-inf"),
            }:
                normalized_market_gate["macro_context"] = {
                    "status": "missing",
                    "cycle_state": None,
                    "macro_score": None,
                    "gate_as_of_date": as_of_date[:10],
                    "data_date": None,
                    "lag_days": None,
                    "max_component_lag_days": None,
                    "components": [],
                    "evidence": "",
                    "formula_version": "rv_gate_macro_overlay_test",
                }
            else:
                cycle_state = (
                    "expansion"
                    if legacy_score < -0.3
                    else "contraction"
                    if legacy_score > 0.3
                    else "neutral"
                )
                normalized_market_gate["macro_context"] = {
                    "status": "ready",
                    "cycle_state": cycle_state,
                    "macro_score": legacy_score,
                    "gate_as_of_date": as_of_date[:10],
                    "data_date": as_of_date[:10],
                    "lag_days": 0,
                    "max_component_lag_days": 0,
                    "components": [
                        {
                            "input_family": "PMI",
                            "input": "M0017126",
                            "cadence": "monthly",
                            "business_date": as_of_date[:10],
                            "age_days": 0,
                            "tier": "fresh",
                        },
                        {
                            "input_family": "credit_impulse",
                            "input": "M5525763",
                            "cadence": "monthly",
                            "business_date": as_of_date[:10],
                            "age_days": 0,
                            "tier": "fresh",
                        },
                        {
                            "input_family": "price_spread",
                            "input": "CA.CSI300_PE",
                            "cadence": "daily",
                            "business_date": as_of_date[:10],
                            "age_days": 0,
                            "tier": "fresh",
                        },
                    ],
                    "evidence": "unit-test authoritative market-gate macro evidence",
                    "formula_version": "rv_gate_macro_overlay_test",
                }
        normalized_livermore_payload["market_gate"] = normalized_market_gate
    return cast(
        dict[str, object],
        module.build_livermore_signal_confluence(
            as_of_date=as_of_date,
            livermore_payload=normalized_livermore_payload,
            macro_payload=macro_payload,
            strategy_meta={
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
            adversarial_payload=adversarial_payload,
            backtest_window_summary=backtest_window_summary,
        ),
    )


def test_build_livermore_signal_confluence_allows_observation_entries_when_gate_is_hot_and_macro_supportive() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "HOT",
                "exposure": 0.75,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000001.SZ",
                        "stock_name": "Alpha",
                        "breakout_level": 21.8,
                        "close": 21.9,
                        "ema10": 20.6,
                    }
                ]
            },
            "risk_exit": {
                "watch_items": [
                    {
                        "stock_code": "000777.SZ",
                        "stock_name": "Watch Alpha",
                        "latest_close": 19.8,
                        "latest_ema10": 20.1,
                    }
                ]
            },
        },
        macro_payload={
            "environment_score": {
                "composite_score": -0.45,
            }
        },
    )

    assert result["as_of_date"] == "2026-05-02"
    assert result["position_size_hint"] == pytest.approx(0.75)
    assert result["disclaimer"] == (
        "Observation-only output. This service does not generate trading instructions."
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "supportive"
    assert macro_context["composite_score"] == pytest.approx(-0.45)
    assert macro_context["multiplier"] == pytest.approx(1.0)

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["market_gate_state"] == "HOT"
    assert strategy_context["market_gate_exposure"] == pytest.approx(0.75)
    assert strategy_context["allows_new_entry_observations"] is True

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert len(entry_observations) == 1
    assert entry_observations[0] == {
        "stock_code": "000001.SZ",
        "stock_name": "Alpha",
        "action": "observe_entry_setup",
        "trigger_price": 21.8,
        "current_price": 21.9,
        "invalidation_reference_price": 20.6,
        "evidence": [
            "候选触发价来自 Livermore breakout_level。",
            "失效参考价来自候选股 EMA10。",
        ],
    }

    exit_observations = cast(list[dict[str, Any]], result["exit_observations"])
    assert exit_observations == [
        {
            "stock_code": "000777.SZ",
            "stock_name": "Watch Alpha",
            "action": "observe_exit_watch",
            "current_price": 19.8,
            "exit_watch_price": 20.1,
            "triggered": False,
            "evidence": ["退出观察价来自 Livermore EMA10。"],
        }
    ]
    closed_loop_state = cast(dict[str, Any], result["closed_loop_state"])
    assert closed_loop_state["exit_gate"] == "watch"

    diagnostics = cast(list[str], result["diagnostics"])
    assert diagnostics[-1] == (
        "Observation-only output. This service does not generate trading instructions."
    )


@pytest.mark.parametrize("composite_score", [-0.45, 0.0, 0.4])
def test_build_livermore_signal_confluence_discloses_cross_asset_macro_score_reuse(
    composite_score: float,
) -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "stock_candidates": {"items": []},
            "risk_exit": {"watch_items": []},
        },
        macro_payload={
            "environment_score": {
                "composite_score": composite_score,
            }
        },
    )

    diagnostics = cast(list[str], result["diagnostics"])
    assert (
        "Legacy bond-side macro_bond_linkage composite score is retained for degraded disclosure only; "
        "it never authorizes equity entry observations."
    ) in diagnostics
    assert (
        "Legacy bond macro thresholds of +/-0.3 are empirical and have no independent equity-side contract source."
    ) in diagnostics
    assert cast(dict[str, Any], result["macro_context"])["legacy_bond_context"] == {
        "authority_status": "legacy_degraded_only",
        "status": "supportive" if composite_score < -0.3 else "restrictive" if composite_score > 0.3 else "neutral",
        "composite_score": composite_score,
        "lineage": {},
    }
    assert diagnostics[-1] == (
        "Observation-only output. This service does not generate trading instructions."
    )


def test_build_livermore_signal_confluence_omits_cross_asset_reuse_disclosure_when_macro_score_is_missing() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={},
        macro_payload={},
    )

    diagnostics = cast(list[str], result["diagnostics"])
    assert "Legacy bond macro composite score is missing; it cannot authorize entry observations." in diagnostics
    assert not any("macro_bond_linkage" in item for item in diagnostics)


def test_build_livermore_signal_confluence_keeps_candidate_price_facts_visible_but_observe_only_when_macro_is_restrictive() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "OVERHEAT",
                "exposure": 1.0,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000002.SZ",
                        "stock_name": "Beta",
                        "breakout_level": 12.4,
                        "close": 12.1,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": 0.4,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "restrictive"
    assert result["position_size_hint"] == pytest.approx(0.0)

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["allows_new_entry_observations"] is False

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations == [
        {
            "stock_code": "000002.SZ",
            "stock_name": "Beta",
            "action": "observe_only",
            "trigger_price": 12.4,
            "current_price": 12.1,
            "invalidation_reference_price": None,
            "evidence": ["候选触发价来自 Livermore breakout_level。"],
        }
    ]
    assert "buy" not in str(entry_observations[0]).lower()
    diagnostics = cast(list[str], result["diagnostics"])
    assert "Stock 000002.SZ is missing EMA10; invalidation reference price is unavailable." in diagnostics


def test_build_livermore_signal_confluence_overheat_stays_observe_only_even_when_macro_is_supportive() -> None:
    """OVERHEAT 历史回测 win_5d=41.1% / avg=-0.09%，任何 macro 下都不放行新观察入场。"""
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "OVERHEAT",
                "exposure": 1.0,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000003.SZ",
                        "stock_name": "Gamma",
                        "breakout_level": 33.0,
                        "close": 33.4,
                        "ema10": 31.2,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": -0.5,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "supportive"

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["market_gate_state"] == "OVERHEAT"
    assert strategy_context["allows_new_entry_observations"] is False

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations[0]["action"] == "observe_only"


def test_build_livermore_signal_confluence_uses_observe_only_when_adversarial_gate_blocks() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "HOT",
                "exposure": 0.6,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000006.SZ",
                        "stock_name": "Zeta",
                        "breakout_level": 18.2,
                        "close": 18.5,
                        "ema10": 17.8,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": -0.4,
            }
        },
        adversarial_payload={
            "status": "ok",
            "risk_gate": "block",
            "diagnostics": ["Crowding reversal risk is elevated."],
        },
    )

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["allows_new_entry_observations"] is True

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations[0]["action"] == "observe_only"

    adversarial_context = cast(dict[str, Any], result["adversarial_context"])
    assert adversarial_context["status"] == "ok"
    assert adversarial_context["risk_gate"] == "block"
    assert adversarial_context["mode"] == "macro_adversarial_crowding"
    assert adversarial_context["position_scale"] is None
    assert adversarial_context["blocks_new_entry_observations"] is True

    closed_loop_state = cast(dict[str, Any], result["closed_loop_state"])
    assert closed_loop_state["status"] == "blocked_by_adversarial"
    assert closed_loop_state["entry_gate"] == "blocked"
    assert closed_loop_state["lineage_status"] == "complete"
    assert closed_loop_state["entry_observation_action"] == "observe_only"

    diagnostics = cast(list[str], result["diagnostics"])
    assert "Adversarial risk gate is blocking new entry observations; candidate entries stay observe_only." in diagnostics


def test_build_livermore_signal_confluence_keeps_entries_visible_when_adversarial_signal_is_missing() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000007.SZ",
                        "stock_name": "Eta",
                        "breakout_level": 16.2,
                        "close": 16.4,
                        "ema10": 15.7,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": -0.1,
            }
        },
    )

    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations[0]["action"] == "observe_entry_setup"

    adversarial_context = cast(dict[str, Any], result["adversarial_context"])
    assert adversarial_context["status"] == "missing"
    assert adversarial_context["risk_gate"] == "missing"
    assert adversarial_context["blocks_new_entry_observations"] is False

    closed_loop_state = cast(dict[str, Any], result["closed_loop_state"])
    assert closed_loop_state["status"] == "degraded_missing_adversarial"
    assert closed_loop_state["entry_gate"] == "open"
    replay_status = cast(dict[str, Any], closed_loop_state["replay_status"])
    assert replay_status["window_status"] == "unsupported"
    assert replay_status["maturity_status"] == "missing"
    assert replay_status["has_decision_usable_completed_stats"] is False
    assert replay_status["matched_entry_count"] == 0
    assert closed_loop_state["lineage_status"] == "missing"
    assert closed_loop_state["entry_observation_action"] == "observe_entry_setup"

    diagnostics = cast(list[str], result["diagnostics"])
    assert "Macro adversarial signal is missing; no adversarial gate is applied." in diagnostics


def test_build_livermore_signal_confluence_reports_missing_inputs_and_stays_observation_only() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={},
        macro_payload={},
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "unknown"
    assert macro_context["composite_score"] is None
    assert macro_context["multiplier"] == pytest.approx(0.0)

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["market_gate_state"] == "UNKNOWN"
    assert strategy_context["market_gate_exposure"] is None
    assert strategy_context["allows_new_entry_observations"] is False

    assert result["position_size_hint"] is None
    assert result["entry_observations"] == []
    assert result["exit_observations"] == []

    diagnostics = cast(list[str], result["diagnostics"])
    assert "Legacy bond macro composite score is missing; it cannot authorize entry observations." in diagnostics
    assert "Missing Livermore market gate; entry observations are blocked." in diagnostics
    assert "Missing Livermore market gate exposure; position size hint is unavailable." in diagnostics
    assert "No stock candidates available for observation." in diagnostics
    assert "No risk exit watch items or triggered exit items available." in diagnostics
    assert diagnostics[-1] == (
        "Observation-only output. This service does not generate trading instructions."
    )


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), float("-inf"), "nan"])
def test_build_livermore_signal_confluence_rejects_non_finite_legacy_macro_scores(
    bad_score: object,
) -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000005.SZ",
                        "stock_name": "Epsilon",
                        "breakout_level": 15.2,
                        "close": 15.0,
                        "ema10": 14.7,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": bad_score,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "unknown"
    assert macro_context["authority_status"] == "blocked"
    assert macro_context["legacy_bond_context"]["composite_score"] is None
    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["allows_new_entry_observations"] is False
    entry_observations = cast(list[dict[str, Any]], result["entry_observations"])
    assert entry_observations[0]["action"] == "observe_only"
    diagnostics = cast(list[str], result["diagnostics"])
    assert "Legacy bond macro composite score is missing; it cannot authorize entry observations." in diagnostics
    assert (
        "Authoritative PMI/credit-expansion-proxy (social-financing-stock YoY delta proxy) "
        "market-gate context is not ready; entry observations fail closed."
    ) in diagnostics


def test_build_livermore_signal_confluence_falls_back_to_triggered_exit_items_when_watch_items_are_absent() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "risk_exit": {
                "items": [
                    {
                        "stock_code": "000003.SZ",
                        "stock_name": "Gamma",
                        "latest_close": 9.1,
                        "latest_ema10": 9.8,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": 0.0,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "neutral"
    assert result["position_size_hint"] == pytest.approx(0.25)

    exit_observations = cast(list[dict[str, Any]], result["exit_observations"])
    assert exit_observations == [
        {
            "stock_code": "000003.SZ",
            "stock_name": "Gamma",
            "action": "exit_triggered",
            "current_price": 9.1,
            "exit_watch_price": 9.8,
            "triggered": True,
            "evidence": ["退出观察价来自 Livermore EMA10。"],
        }
    ]
    closed_loop_state = cast(dict[str, Any], result["closed_loop_state"])
    assert closed_loop_state["exit_gate"] == "triggered"


def test_build_livermore_signal_confluence_keeps_position_size_hint_unavailable_when_exposure_is_null() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": None,
            },
            "stock_candidates": {"items": []},
            "risk_exit": {"watch_items": []},
        },
        macro_payload={
            "environment_score": {
                "composite_score": 0.0,
            }
        },
    )

    strategy_context = cast(dict[str, Any], result["strategy_context"])
    assert strategy_context["market_gate_state"] == "WARM"
    assert strategy_context["market_gate_exposure"] is None
    assert result["position_size_hint"] is None

    diagnostics = cast(list[str], result["diagnostics"])
    assert "Missing Livermore market gate exposure; position size hint is unavailable." in diagnostics
    assert "Missing Livermore market gate; entry observations are blocked." not in diagnostics


@pytest.mark.parametrize("composite_score", [-0.3, 0.3])
def test_build_livermore_signal_confluence_treats_macro_boundary_as_neutral(
    composite_score: float,
) -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "stock_candidates": {"items": []},
            "risk_exit": {"watch_items": []},
        },
        macro_payload={
            "environment_score": {
                "composite_score": composite_score,
            }
        },
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["status"] == "neutral"
    assert macro_context["composite_score"] == pytest.approx(composite_score)


def test_build_livermore_signal_confluence_does_not_invent_exit_watch_evidence_when_ema10_is_missing() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
            },
            "risk_exit": {
                "watch_items": [
                    {
                        "stock_code": "000004.SZ",
                        "stock_name": "Delta",
                        "latest_close": 10.1,
                        "triggered": False,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": 0.0,
            }
        },
    )

    exit_observations = cast(list[dict[str, Any]], result["exit_observations"])
    assert exit_observations == [
        {
            "stock_code": "000004.SZ",
            "stock_name": "Delta",
            "action": "observe_exit_watch",
            "current_price": 10.1,
            "exit_watch_price": None,
            "triggered": False,
            "evidence": [],
        }
    ]
    diagnostics = cast(list[str], result["diagnostics"])
    assert "Stock 000004.SZ is missing EMA10; exit watch price is unavailable." in diagnostics


def test_build_livermore_signal_confluence_projects_backtest_window_summary_into_closed_loop_replay_status() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-08",
        livermore_payload={
            "market_gate": {
                "state": "HOT",
                "exposure": 0.6,
            },
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000006.SZ",
                        "stock_name": "Zeta",
                        "breakout_level": 18.2,
                        "close": 18.5,
                        "ema10": 17.8,
                    }
                ]
            },
        },
        macro_payload={
            "macro_environment": {
                "composite_score": -0.4,
            }
        },
        backtest_window_summary={
            "status": "partial",
            "snapshot_from": "2026-04-30",
            "snapshot_to": "2026-05-08",
            "replay_dates_total": 4,
            "replay_dates_completed": 1,
            "replay_dates_pending": 1,
            "replay_dates_unsupported": 1,
            "replay_dates_proxy_only": 1,
            "completed_rows": 0,
            "pending_rows": 1,
            "unsupported_rows": 0,
            "proxy_only_rows": 1,
            "excluded_from_completed_stats_dates": ["2026-04-30", "2026-05-07", "2026-05-08"],
            "included_completed_stats_dates": ["2026-05-06"],
            "date_reasons": [
                {
                    "trade_date": "2026-04-30",
                    "status": "unsupported",
                    "reason_code": "missing_daily_limit_flags",
                    "message": "daily_limit_flags absent; Livermore strategy replay unsupported for 2026-04-30.",
                    "affects_completed_stats": False,
                    "signal_kinds": ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
                },
                {
                    "trade_date": "2026-05-06",
                    "status": "completed",
                    "reason_code": "no_strategy_signals",
                    "message": "Full replay coverage produced no Livermore strategy signal rows for 2026-05-06.",
                    "affects_completed_stats": True,
                    "signal_kinds": ["stock_candidate", "theme_breakout", "factor_screen", "mean_reversion"],
                },
                {
                    "trade_date": "2026-05-07",
                    "status": "proxy_only",
                    "reason_code": "proxy_theme_only",
                    "message": "Theme breakout replay for 2026-05-07 relies on proxy-only theme evidence.",
                    "affects_completed_stats": False,
                    "signal_kinds": ["theme_breakout"],
                },
                {
                    "trade_date": "2026-05-08",
                    "status": "pending",
                    "reason_code": "forward_returns_pending",
                    "message": "Forward return bars are not available yet; exclude 2026-05-08 from completed forward-return statistics.",
                    "affects_completed_stats": False,
                    "signal_kinds": ["stock_candidate"],
                },
            ],
        },
    )

    replay_status = cast(
        dict[str, Any], cast(dict[str, Any], result["closed_loop_state"])["replay_status"]
    )
    assert replay_status["window_status"] == "partial"
    assert replay_status["snapshot_from"] == "2026-04-30"
    assert replay_status["snapshot_to"] == "2026-05-08"
    assert replay_status["maturity_status"] == "insufficient"
    assert replay_status["completed_dates"] == 1
    assert replay_status["pending_dates"] == 1
    assert replay_status["blocking_pending_date_count"] == 1
    assert replay_status["unsupported_dates"] == 1
    assert replay_status["proxy_only_dates"] == 1
    assert replay_status["included_completed_stats_dates"] == ["2026-05-06"]
    assert [row["status"] for row in replay_status["blocked_dates"]] == [
        "unsupported",
        "proxy_only",
        "pending",
    ]


def test_build_livermore_replay_status_accepts_private_included_completed_dates_key() -> None:
    module = _service_module()

    replay_status = module.build_livermore_replay_status(
        {
            "status": "valid",
            "replay_dates_completed": 1,
            "replay_dates_pending": 0,
            "replay_dates_unsupported": 0,
            "replay_dates_proxy_only": 0,
            "completed_rows": 1,
            "pending_rows": 0,
            "unsupported_rows": 0,
            "proxy_only_rows": 0,
            "_included_completed_stats_dates": ["2026-05-06"],
            "date_reasons": [],
        }
    )

    assert replay_status["included_completed_stats_dates"] == ["2026-05-06"]
    assert replay_status["has_decision_usable_completed_stats"] is False
    assert replay_status["maturity_status"] == "insufficient"


def test_build_livermore_replay_status_marks_only_mature_complete_windows_decision_usable() -> None:
    module = _service_module()

    replay_status = module.build_livermore_replay_status(
        {
            "status": "valid",
            "replay_dates_completed": 20,
            "replay_dates_pending": 3,
            "pending_tail_dates": ["2026-06-01", "2026-06-02", "2026-06-03"],
            "blocking_pending_dates": [],
            "replay_dates_unsupported": 0,
            "replay_dates_proxy_only": 0,
            "completed_rows": 120,
            "pending_rows": 0,
            "unsupported_rows": 0,
            "proxy_only_rows": 0,
            "included_completed_stats_dates": [f"2026-05-{day:02d}" for day in range(1, 21)],
            "decision_metric_basis": "net_next_open_adj",
            "research_metric_basis": "adjusted_close_return",
            "execution_usable_stats": {
                "metric_basis": "net_next_open_adj",
                "by_signal_kind_horizon_usable_stats": {
                    "stock_candidate": {
                        "return_5d": {"available_count": 100},
                        "return_20d": {"available_count": 100},
                    }
                },
            },
            "date_reasons": [],
        }
    )

    assert replay_status["maturity_status"] == "ready"
    assert replay_status["matched_entry_count"] == 100
    assert replay_status["has_required_horizon_stats"] is True
    assert replay_status["has_decision_usable_completed_stats"] is True
    assert replay_status["metric_basis"] == "net_next_open_adj"
    assert replay_status["pending_tail_date_count"] == 3
    assert replay_status["blocking_pending_date_count"] == 0


@pytest.mark.parametrize(
    ("completed_dates", "matched_entries"),
    [(20, 99), (19, 100)],
)
def test_build_livermore_replay_status_requires_both_readiness_thresholds(
    completed_dates: int,
    matched_entries: int,
) -> None:
    module = _service_module()
    replay_status = module.build_livermore_replay_status(
        {
            "status": "valid",
            "replay_dates_completed": completed_dates,
            "replay_dates_pending": 0,
            "blocking_pending_dates": [],
            "replay_dates_unsupported": 0,
            "replay_dates_proxy_only": 0,
            "decision_metric_basis": "net_next_open_adj",
            "execution_usable_stats": {
                "metric_basis": "net_next_open_adj",
                "by_signal_kind_horizon_usable_stats": {
                    "stock_candidate": {
                        "return_5d": {"available_count": matched_entries},
                        "return_20d": {"available_count": matched_entries},
                    }
                },
            },
            "date_reasons": [],
        }
    )

    assert replay_status["maturity_status"] != "ready"
    assert replay_status["has_decision_usable_completed_stats"] is False


def test_build_livermore_signal_confluence_never_authorizes_from_legacy_bond_macro_alone() -> None:
    module = _service_module()
    result = module.build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {"state": "WARM", "exposure": 0.5},
            "stock_candidates": {
                "items": [{"stock_code": "000001.SZ", "breakout_level": 10.0}]
            },
        },
        macro_payload={"environment_score": {"composite_score": -0.8}},
        strategy_meta={"quality_flag": "ok", "vendor_status": "ok", "fallback_mode": "none"},
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["authority_status"] == "blocked"
    assert macro_context["status"] == "unknown"
    assert macro_context["legacy_bond_context"]["status"] == "supportive"
    assert cast(dict[str, Any], result["strategy_context"])["allows_new_entry_observations"] is False


def test_authoritative_macro_score_is_not_mislabeled_with_legacy_bond_value() -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
                "macro_context": {
                    "status": "ready",
                    "cycle_state": "expansion",
                    "macro_score": 0.8,
                    "gate_as_of_date": "2026-05-02",
                    "components": [
                        {
                            "input_family": "PMI",
                            "input": "M0017126",
                            "business_date": "2026-05-01",
                            "age_days": 1,
                            "tier": "fresh",
                        },
                        {
                            "input_family": "credit_impulse",
                            "input": "M5525763",
                            "business_date": "2026-05-01",
                            "age_days": 1,
                            "tier": "fresh",
                        },
                    ],
                },
            }
        },
        macro_payload={"environment_score": {"composite_score": -0.4}},
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["source_metric"] == "market_gate.macro_context.macro_score"
    assert macro_context["composite_score"] == pytest.approx(0.8)
    assert macro_context["legacy_bond_context"]["composite_score"] == pytest.approx(-0.4)


@pytest.mark.parametrize(
    ("pmi_tier", "credit_business_date", "expected_reason"),
    [
        ("stale", "2026-05-01", "PMI_tier_not_fresh"),
        ("fresh", "2026-05-03", "credit_impulse_business_date_look_ahead"),
    ],
)
def test_build_livermore_signal_confluence_fails_closed_on_stale_or_lookahead_macro(
    pmi_tier: str,
    credit_business_date: str,
    expected_reason: str,
) -> None:
    result = _build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {
                "state": "WARM",
                "exposure": 0.5,
                "macro_context": {
                    "status": "ready",
                    "cycle_state": "expansion",
                    "macro_score": 0.8,
                    "gate_as_of_date": "2026-05-02",
                    "data_date": "2026-05-01",
                    "lag_days": 1,
                    "max_component_lag_days": 1,
                    "components": [
                        {
                            "input_family": "PMI",
                            "input": "M0017126",
                            "business_date": "2026-05-01",
                            "age_days": 1,
                            "tier": pmi_tier,
                        },
                        {
                            "input_family": "credit_impulse",
                            "input": "M5525763",
                            "business_date": credit_business_date,
                            "age_days": 1,
                            "tier": "fresh",
                        },
                    ],
                    "formula_version": "rv_gate_macro_overlay_test",
                    "evidence": "test",
                },
            },
            "stock_candidates": {
                "items": [{"stock_code": "000001.SZ", "breakout_level": 10.0}]
            },
        },
        macro_payload={},
    )

    macro_context = cast(dict[str, Any], result["macro_context"])
    assert macro_context["authority_status"] == "blocked"
    assert expected_reason in macro_context["authority_reasons"]
    assert cast(dict[str, Any], result["strategy_context"])["allows_new_entry_observations"] is False


def test_build_livermore_signal_confluence_fails_closed_when_strategy_fallback_is_active() -> None:
    module = _service_module()
    macro_context = {
        "status": "ready",
        "cycle_state": "neutral",
        "macro_score": 0.5,
        "gate_as_of_date": "2026-05-02",
        "components": [
            {
                "input_family": "PMI",
                "input": "M0017126",
                "business_date": "2026-05-01",
                "age_days": 1,
                "tier": "fresh",
            },
            {
                "input_family": "credit_impulse",
                "input": "M0001385",
                "business_date": "2026-05-01",
                "age_days": 1,
                "tier": "fresh",
            },
        ],
    }
    result = module.build_livermore_signal_confluence(
        as_of_date="2026-05-02",
        livermore_payload={
            "market_gate": {"state": "WARM", "exposure": 0.5, "macro_context": macro_context},
            "stock_candidates": {
                "items": [{"stock_code": "000001.SZ", "breakout_level": 10.0}]
            },
        },
        macro_payload={},
        strategy_meta={
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "latest_snapshot",
        },
    )

    authoritative = cast(dict[str, Any], result["macro_context"])
    assert authoritative["authority_status"] == "blocked"
    assert "strategy_fallback_active" in authoritative["authority_reasons"]
    assert cast(dict[str, Any], result["strategy_context"])["allows_new_entry_observations"] is False
