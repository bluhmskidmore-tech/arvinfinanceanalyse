from __future__ import annotations

from collections.abc import Callable

import pytest

from backend.app.services import market_overview_service as service


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_market_data,
]


class _UnexpectedComponentError(Exception):
    pass


@pytest.mark.parametrize("error", [RuntimeError("offline"), _UnexpectedComponentError("failed")])
def test_direct_component_failure_is_visible(error: Exception) -> None:
    def _raise() -> dict[str, object]:
        raise error

    component = service._load_direct_component("choice_news", _raise)

    assert component.status == "unavailable"
    assert component.envelope is None
    assert component.reason == f"component load failed: {type(error).__name__}"


def test_cached_component_timeout_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    class _TimeoutCache:
        def generation(self) -> int:
            return 0

        def get_or_build_with_status(self, _key: str, _builder: object) -> object:
            raise TimeoutError("cache wait timed out")

    monkeypatch.setattr(service, "market_home_response_cache", _TimeoutCache())

    component = service._load_cached_component("market_rates", cache_key="rates", builder=dict)

    assert component.status == "unavailable"
    assert component.envelope is None
    assert component.reason == "component load failed: TimeoutError"


def test_cached_component_unexpected_failure_is_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _CallingCache:
        def generation(self) -> int:
            return 0

        def get_or_build_with_status(
            self,
            _key: str,
            builder: Callable[[], object],
        ) -> tuple[object, str]:
            return builder(), "produce"

    def _raise() -> dict[str, object]:
        raise _UnexpectedComponentError("component implementation failed")

    monkeypatch.setattr(service, "market_home_response_cache", _CallingCache())
    component = service._load_cached_component(
        "market_rates",
        cache_key="rates",
        builder=_raise,
    )

    assert component.status == "unavailable"
    assert component.envelope is None
    assert component.reason == "component load failed: _UnexpectedComponentError"
