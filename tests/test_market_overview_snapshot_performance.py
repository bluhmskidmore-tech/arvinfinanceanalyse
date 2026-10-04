from __future__ import annotations

import threading
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from backend.app.services import market_overview_service as service


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_market_data,
]


class _InlineCache:
    def __init__(self) -> None:
        self.keys: list[str] = []
        self._lock = threading.Lock()

    def generation(self) -> int:
        return 0

    def get_or_build_with_status(
        self,
        key: str,
        builder: Callable[[], dict[str, object]],
    ) -> tuple[dict[str, object], str]:
        with self._lock:
            self.keys.append(key)
        return builder(), "produce"

    def set(self, *_args: object, **_kwargs: object) -> bool:
        return True

    def shorten_if_same(self, *_args: object, **_kwargs: object) -> bool:
        return True


def _envelope(name: str) -> dict[str, object]:
    return {
        "result": {"component": name},
        "result_meta": {
            "basis": "analytical",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "fallback_date": None,
            "formal_use_allowed": False,
        },
    }


def _health() -> SimpleNamespace:
    return SimpleNamespace(cache_fingerprint="ready:test")


def test_component_reads_overlap_with_bounded_workers_and_keep_contract_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    condition = threading.Condition()
    release = threading.Event()
    active = 0
    started = 0
    peak_active = 0

    def blocked_builder(name: str) -> dict[str, object]:
        nonlocal active, started, peak_active
        with condition:
            active += 1
            started += 1
            peak_active = max(peak_active, active)
            condition.notify_all()
        try:
            if not release.wait(timeout=5):
                raise TimeoutError("test did not release component builders")
            return _envelope(name)
        finally:
            with condition:
                active -= 1
                condition.notify_all()

    cache = _InlineCache()
    monkeypatch.setattr(service, "market_home_response_cache", cache)
    monkeypatch.setattr(
        service,
        "choice_macro_latest_envelope",
        lambda *_args, **_kwargs: blocked_builder("choice_latest"),
    )
    monkeypatch.setattr(
        service,
        "choice_macro_formal_envelope",
        lambda *_args, **_kwargs: blocked_builder("market_rates"),
    )
    monkeypatch.setattr(
        service,
        "build_macro_toolkit_analysis",
        lambda detail, **_kwargs: blocked_builder(f"macro_analysis_{detail}"),
    )
    monkeypatch.setattr(
        service,
        "_load_macro_pulse_envelope",
        lambda *_args, **_kwargs: blocked_builder("macro_pulse"),
    )
    monkeypatch.setattr(
        service,
        "build_macro_toolkit_strategy_summaries",
        lambda: blocked_builder("macro_strategy_summaries"),
    )
    monkeypatch.setattr(
        service,
        "choice_news_latest_envelope",
        lambda *_args, **_kwargs: blocked_builder("choice_news"),
    )

    outcome: dict[str, object] = {}

    def load() -> None:
        try:
            outcome["components"] = service._load_components(
                component_names=set(service._COMPONENT_ORDER),
                duckdb_path="test.duckdb",
                refresh_receipt_health=_health(),  # type: ignore[arg-type]
            )
        except BaseException as exc:  # surfaced on the asserting test thread
            outcome["error"] = exc

    loader_thread = threading.Thread(target=load)
    loader_thread.start()
    try:
        with condition:
            reached_worker_bound = condition.wait_for(
                lambda: started == service._MAX_COMPONENT_WORKERS,
                timeout=5,
            )
        assert reached_worker_bound
        assert peak_active == service._MAX_COMPONENT_WORKERS == 3
    finally:
        release.set()
        loader_thread.join(timeout=10)

    assert not loader_thread.is_alive()
    assert "error" not in outcome
    components = outcome["components"]
    assert isinstance(components, dict)
    assert tuple(components) == service._COMPONENT_ORDER
    assert all(component.status == "ok" for component in components.values())
    assert len(cache.keys) == 5


def test_component_failure_remains_local_and_other_results_are_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = _InlineCache()
    monkeypatch.setattr(service, "market_home_response_cache", cache)
    monkeypatch.setattr(
        service,
        "choice_macro_latest_envelope",
        lambda *_args, **_kwargs: _envelope("choice_latest"),
    )
    monkeypatch.setattr(
        service,
        "choice_macro_formal_envelope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad rates")),
    )
    monkeypatch.setattr(
        service,
        "choice_news_latest_envelope",
        lambda *_args, **_kwargs: _envelope("choice_news"),
    )

    components = service._load_components(
        component_names={"choice_latest", "market_rates", "choice_news"},
        duckdb_path="test.duckdb",
        refresh_receipt_health=_health(),  # type: ignore[arg-type]
    )

    assert tuple(components) == ("choice_latest", "market_rates", "choice_news")
    assert components["choice_latest"].status == "ok"
    assert components["choice_news"].status == "ok"
    assert components["market_rates"].status == "unavailable"
    assert components["market_rates"].reason == "component load failed: ValueError"
    assert components["market_rates"].cache_key == "market-data/rates::test.duckdb"
    assert components["market_rates"].envelope is None
