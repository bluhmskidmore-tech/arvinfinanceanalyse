from __future__ import annotations

import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tests.helpers import ROOT


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def test_livermore_route_support_cache_invalidation_does_not_import_api() -> None:
    script = """
import importlib
import sys

route_support = importlib.import_module("backend.app.services.market_data_livermore_route_support")
assert "backend.app.api" not in sys.modules
route_support._invalidate_livermore_response_cache()
assert "backend.app.api" not in sys.modules
"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_livermore_route_support_invalidates_market_home_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.observability import response_cache
    from backend.app.services import market_data_livermore_route_support

    invalidated = False

    def invalidate() -> None:
        nonlocal invalidated
        invalidated = True

    monkeypatch.setattr(response_cache.market_home_response_cache, "invalidate", invalidate)

    market_data_livermore_route_support._invalidate_livermore_response_cache()

    assert invalidated is True


def test_workbench_revalidates_pretrade_authority_before_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from backend.app.services import market_data_livermore_route_support as support
    from backend.app.services import stock_analysis_workbench_service

    checks = 0
    cached: dict[str, dict[str, object]] = {}

    def selected_read(**_kwargs: object):
        nonlocal checks
        checks += 1
        return (
            {"status": "unavailable", "reason": "test_boundary"},
            None,
            "2026-09-14",
            "pretrade=test",
        )

    def get_or_build(key: str, builder, *, ttl_seconds: float):
        del ttl_seconds
        if key in cached:
            return cached[key], "hit"
        cached[key] = builder()
        return cached[key], "produce"

    monkeypatch.setattr(support, "_selected_pretrade_external_read", selected_read)
    monkeypatch.setattr(support, "_theme_overlay_reader_from_settings", lambda _settings: None)
    monkeypatch.setattr(support, "_theme_overlay_fingerprint", lambda _reader: "none")
    monkeypatch.setattr(
        support.market_home_response_cache,
        "get_or_build_with_status",
        get_or_build,
    )
    monkeypatch.setattr(
        stock_analysis_workbench_service,
        "stock_analysis_workbench_envelope",
        lambda **_kwargs: {"result": {"pretrade_qualification": {"status": "unavailable"}}},
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock.json",
    )

    first = support._cached_stock_analysis_workbench(
        settings=settings,
        as_of_date="2026-09-14",
        include=None,
        sector_window_days=20,
        top_k=10,
    )
    second = support._cached_stock_analysis_workbench(
        settings=settings,
        as_of_date="2026-09-14",
        include=None,
        sector_window_days=20,
        top_k=10,
    )

    assert first[1] == "produce"
    assert second[1] == "hit"
    assert checks == 2


def test_selected_legacy_generation_preserves_qualification_unavailable_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from backend.app.services import market_data_livermore_route_support as support

    monkeypatch.setattr(
        support,
        "current_system_read_context",
        lambda: SimpleNamespace(
            generation="legacy-generation",
            pretrade_availability={
                "schema": "pretrade_qualification/v1",
                "status": "unavailable",
                "reason": "legacy_system_read_bundle_has_no_pretrade_qualification",
            },
        ),
    )
    monkeypatch.setattr(
        support,
        "capture_livermore_external_inputs",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("unavailable evidence must not capture mutable inputs")
        ),
    )

    qualification, captured, target_date, fingerprint = (
        support._selected_pretrade_external_read(
            catalog_file=tmp_path / "missing-choice-stock.json",
            as_of_date=None,
        )
    )

    assert qualification == {
        "schema": "pretrade_qualification/v1",
        "status": "unavailable",
        "reason": "legacy_system_read_bundle_has_no_pretrade_qualification",
    }
    assert captured is None
    assert target_date is None
    assert "legacy_system_read_bundle_has_no_pretrade_qualification" in fingerprint
