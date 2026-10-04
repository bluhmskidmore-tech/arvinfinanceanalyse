"""WP-A2: envelope-level runtime cache for `HomeMacroReleaseContextService.build_envelope`.

Uses the existing fake repository pattern from
`tests.test_home_macro_release_context_service`, extended with a `_duckdb_path`
attribute so the module-level runtime cache can compute a stable key.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from backend.app.repositories import system_read_publication_repo
from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    duckdb_read_scope,
)
from backend.app.repositories.home_macro_release_context_repo import (
    HomeMacroObservation,
    HomeMacroSeriesRead,
)
from backend.app.services import home_macro_release_context_service as macro_svc
from backend.app.services.home_macro_release_context_service import (
    HomeMacroReleaseContextService,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]

ROOT = Path(__file__).resolve().parents[1]
BINDINGS_PATH = ROOT / "config" / "home_macro_release_bindings.json"


class _CountingRepository:
    def __init__(
        self,
        reads: dict[str, HomeMacroSeriesRead],
        *,
        duckdb_path: Path,
    ) -> None:
        self._reads = reads
        self._duckdb_path = duckdb_path
        self.calls: list[tuple[str, str, date, int]] = []

    def read_recent_observations(
        self,
        *,
        table: str,
        series_id: str,
        cutoff_date: date,
        limit: int = 2,
    ) -> HomeMacroSeriesRead:
        self.calls.append((table, series_id, cutoff_date, limit))
        return self._reads.get(
            series_id,
            HomeMacroSeriesRead(
                table=table,
                series_id=series_id,
                observations=[],
                error="relation_missing",
            ),
        )


def _observation(
    *,
    table: str,
    series_id: str,
    observation_date: date,
    value: float | None,
    cadence: str,
    unit: str,
    version_suffix: str,
    vendor_name: str | None = None,
) -> HomeMacroObservation:
    return HomeMacroObservation(
        table=table,
        series_id=series_id,
        observation_date=observation_date,
        value=value,
        cadence=cadence,
        unit=unit,
        source_version=f"sv-{version_suffix}",
        vendor_version=f"vv-{version_suffix}",
        rule_version=f"rv-{version_suffix}",
        vendor_name=vendor_name,
    )


def _series_read(
    *,
    table: str,
    series_id: str,
    current_date: date,
    current_value: float | None,
    previous_date: date | None,
    previous_value: float | None,
    cadence: str,
    unit: str,
    vendor_name: str | None,
) -> HomeMacroSeriesRead:
    current = _observation(
        table=table,
        series_id=series_id,
        observation_date=current_date,
        value=current_value,
        cadence=cadence,
        unit=unit,
        version_suffix=f"{series_id}-current",
        vendor_name=vendor_name,
    )
    observations = [current]
    if previous_date is not None:
        observations.append(
            _observation(
                table=table,
                series_id=series_id,
                observation_date=previous_date,
                value=previous_value,
                cadence=cadence,
                unit=unit,
                version_suffix=f"{series_id}-previous",
                vendor_name=vendor_name,
            )
        )
    return HomeMacroSeriesRead(table=table, series_id=series_id, observations=observations)


def _ready_reads() -> dict[str, HomeMacroSeriesRead]:
    return {
        "M0017126": _series_read(
            table="fact_choice_macro_daily",
            series_id="M0017126",
            current_date=date(2026, 6, 1),
            current_value=51.0,
            previous_date=date(2026, 5, 1),
            previous_value=50.5,
            cadence="monthly",
            unit="index",
            vendor_name=None,
        ),
        "tushare.macro.cn_cpi.monthly": _series_read(
            table="std_external_macro_daily",
            series_id="tushare.macro.cn_cpi.monthly",
            current_date=date(2026, 6, 1),
            current_value=1.2,
            previous_date=date(2026, 5, 1),
            previous_value=1.0,
            cadence="monthly",
            unit="pct",
            vendor_name="tushare",
        ),
        "tushare.macro.cn_ppi.monthly": _series_read(
            table="std_external_macro_daily",
            series_id="tushare.macro.cn_ppi.monthly",
            current_date=date(2026, 6, 1),
            current_value=3.9,
            previous_date=date(2026, 5, 1),
            previous_value=2.8,
            cadence="monthly",
            unit="pct",
            vendor_name="tushare",
        ),
        "nbs.macro.cn_cpi.monthly": _series_read(
            table="std_external_macro_daily",
            series_id="nbs.macro.cn_cpi.monthly",
            current_date=date(2026, 6, 1),
            current_value=1.2,
            previous_date=date(2026, 5, 1),
            previous_value=1.0,
            cadence="monthly",
            unit="pct",
            vendor_name="nbs",
        ),
        "nbs.macro.cn_ppi.monthly": _series_read(
            table="std_external_macro_daily",
            series_id="nbs.macro.cn_ppi.monthly",
            current_date=date(2026, 6, 1),
            current_value=3.9,
            previous_date=date(2026, 5, 1),
            previous_value=2.8,
            cadence="monthly",
            unit="pct",
            vendor_name="nbs",
        ),
        "nbs.macro.cn_gdp.quarterly": _series_read(
            table="std_external_macro_daily",
            series_id="nbs.macro.cn_gdp.quarterly",
            current_date=date(2026, 6, 30),
            current_value=4.3,
            previous_date=date(2026, 3, 31),
            previous_value=5.0,
            cadence="quarterly",
            unit="pct",
            vendor_name="nbs",
        ),
        "tushare.macro.cn_gdp.quarterly": _series_read(
            table="std_external_macro_daily",
            series_id="tushare.macro.cn_gdp.quarterly",
            current_date=date(2026, 6, 30),
            current_value=5.0,
            previous_date=date(2026, 3, 31),
            previous_value=5.2,
            cadence="quarterly",
            unit="pct",
            vendor_name="tushare",
        ),
    }


def _bump_mtime(path: Path) -> None:
    original = path.stat().st_mtime_ns
    for delta_ns in (1_000_000, 2_000_000, 5_000_000, 10_000_000, 50_000_000):
        target_ns = original + delta_ns
        try:
            os.utime(path, ns=(target_ns, target_ns))
        except (OSError, NotImplementedError):
            time.sleep(0.02)
            path.write_bytes(path.read_bytes() + b"\n")
        if path.stat().st_mtime_ns != original:
            return
    raise RuntimeError(f"failed to bump mtime for {path}")


@pytest.fixture
def duckdb_path(tmp_path: Path) -> Path:
    path = tmp_path / "moss.duckdb"
    path.write_text("seed", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    macro_svc.clear_home_macro_release_context_runtime_cache()


def _build(
    repository: _CountingRepository,
    *,
    bindings_path: Path = BINDINGS_PATH,
    window_start_date: date = date(2026, 7, 16),
    window_end_date: date = date(2026, 8, 30),
    history_limit: int = 8,
    force_refresh: bool = False,
):
    service = HomeMacroReleaseContextService(
        repository=repository,
        bindings_path=bindings_path,
    )
    kwargs = {
        "window_start_date": window_start_date,
        "window_end_date": window_end_date,
        "history_limit": history_limit,
    }
    if force_refresh:
        kwargs["force_refresh"] = True
    return service.build_envelope(**kwargs)


def test_build_envelope_runtime_cache_skips_repository_reads_on_second_call(
    duckdb_path: Path,
) -> None:
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)

    first = _build(repository)
    baseline = len(repository.calls)
    assert baseline > 0

    second = _build(repository)
    assert len(repository.calls) == baseline
    assert first.model_dump() == second.model_dump()


def test_build_envelope_runtime_cache_isolates_by_window_and_history_limit(
    duckdb_path: Path,
) -> None:
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)

    _build(repository, window_start_date=date(2026, 7, 16))
    baseline = len(repository.calls)

    _build(repository, window_start_date=date(2026, 7, 17))
    assert len(repository.calls) > baseline
    baseline_after_second_window = len(repository.calls)

    _build(repository, window_start_date=date(2026, 7, 16), history_limit=4)
    assert len(repository.calls) > baseline_after_second_window


def test_build_envelope_runtime_cache_invalidates_on_bindings_mtime_change(
    duckdb_path: Path,
    tmp_path: Path,
) -> None:
    bindings_copy = tmp_path / "bindings.json"
    bindings_copy.write_bytes(BINDINGS_PATH.read_bytes())
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)

    _build(repository, bindings_path=bindings_copy)
    baseline = len(repository.calls)

    _bump_mtime(bindings_copy)
    _build(repository, bindings_path=bindings_copy)

    assert len(repository.calls) > baseline


def test_build_envelope_runtime_cache_invalidates_on_duckdb_mtime_change(
    duckdb_path: Path,
) -> None:
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)

    _build(repository)
    baseline = len(repository.calls)

    _bump_mtime(duckdb_path)
    _build(repository)

    assert len(repository.calls) > baseline


def test_force_refresh_rebuilds_and_renews_before_original_expiry(
    duckdb_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    cache = macro_svc.InMemoryTTLCache(
        ttl_seconds=900.0,
        clock=lambda: now[0],
    )
    monkeypatch.setattr(macro_svc, "_HOME_MACRO_ENVELOPE_CACHE", cache)
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)

    first = _build(repository)
    initial_calls = len(repository.calls)
    repository._reads["M0017126"] = _series_read(
        table="fact_choice_macro_daily",
        series_id="M0017126",
        current_date=date(2026, 6, 1),
        current_value=52.0,
        previous_date=date(2026, 5, 1),
        previous_value=50.5,
        cadence="monthly",
        unit="index",
        vendor_name=None,
    )
    now[0] = 600.0
    refreshed = _build(repository, force_refresh=True)
    assert len(repository.calls) > initial_calls
    after_refresh_calls = len(repository.calls)
    now[0] = 901.0
    cached = _build(repository)
    assert len(repository.calls) == after_refresh_calls
    assert cached.model_dump() == refreshed.model_dump()
    first_pmi = next(item for item in first.result.history_items if item.indicator_key == "cn_pmi")
    refreshed_pmi = next(item for item in refreshed.result.history_items if item.indicator_key == "cn_pmi")
    assert first_pmi.metrics[0].actual_value == 51.0
    assert refreshed_pmi.metrics[0].actual_value == 52.0


def test_force_refresh_keeps_valid_cached_envelope_readable_during_build(
    duckdb_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    cached = _build(repository)
    initial_calls = len(repository.calls)
    entered = Event()
    release = Event()
    original = macro_svc.HomeMacroReleaseContextService._build_envelope_uncached

    def delayed(self, **kwargs):
        entered.set()
        assert release.wait(timeout=5.0)
        return original(self, **kwargs)

    monkeypatch.setattr(
        macro_svc.HomeMacroReleaseContextService, "_build_envelope_uncached", delayed,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        refresh = pool.submit(_build, repository, force_refresh=True)
        try:
            assert entered.wait(timeout=5.0)
            during_refresh = _build(repository)
            assert during_refresh.model_dump() == cached.model_dump()
            assert len(repository.calls) == initial_calls
        finally:
            release.set()
        refreshed = refresh.result(timeout=5.0)
    assert len(repository.calls) > initial_calls
    assert refreshed.result.model_dump() == cached.result.model_dump()


def test_force_refresh_failure_preserves_valid_cached_envelope(
    duckdb_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    cached = _build(repository)
    initial_calls = len(repository.calls)

    def fail(self, **kwargs):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(
        macro_svc.HomeMacroReleaseContextService, "_build_envelope_uncached", fail,
    )
    with pytest.raises(RuntimeError, match="source unavailable"):
        _build(repository, force_refresh=True)
    assert _build(repository).model_dump() == cached.model_dump()
    assert len(repository.calls) == initial_calls


def test_clear_during_force_refresh_prevents_refill(
    duckdb_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    _build(repository)
    original = macro_svc.HomeMacroReleaseContextService._build_envelope_uncached

    def clearing(self, **kwargs):
        envelope = original(self, **kwargs)
        macro_svc.clear_home_macro_release_context_runtime_cache()
        return envelope

    with monkeypatch.context() as patch:
        patch.setattr(
            macro_svc.HomeMacroReleaseContextService, "_build_envelope_uncached", clearing,
        )
        _build(repository, force_refresh=True)
    after_force = len(repository.calls)
    _build(repository)
    assert len(repository.calls) > after_force


@pytest.mark.parametrize("changed_input", ["bindings", "duckdb"])
def test_input_change_during_force_refresh_does_not_replace_previous_cache(
    changed_input: str,
    duckdb_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bindings_copy = tmp_path / "bindings.json"
    bindings_copy.write_bytes(BINDINGS_PATH.read_bytes())
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    service = HomeMacroReleaseContextService(
        repository=repository, bindings_path=bindings_copy,
    )
    window = {
        "window_start_date": date(2026, 7, 16),
        "window_end_date": date(2026, 8, 30),
    }
    cached = service.build_envelope(**window)
    key = service._envelope_cache_key(*window.values(), 8)
    original = service._build_envelope_uncached

    def changing(**kwargs):
        envelope = original(**kwargs)
        _bump_mtime(bindings_copy if changed_input == "bindings" else duckdb_path)
        return envelope

    monkeypatch.setattr(service, "_build_envelope_uncached", changing)
    refreshed = service.build_envelope(**window, force_refresh=True)
    hit, retained = macro_svc._HOME_MACRO_ENVELOPE_CACHE.get(key)
    assert hit
    assert retained is cached
    assert refreshed is not cached
    after_force = len(repository.calls)
    _build(repository, bindings_path=bindings_copy)
    assert len(repository.calls) > after_force


def test_constructor_bindings_changed_before_force_refresh_are_not_cached(
    duckdb_path: Path,
    tmp_path: Path,
) -> None:
    bindings_copy = tmp_path / "bindings.json"
    bindings_copy.write_bytes(BINDINGS_PATH.read_bytes())
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    service = HomeMacroReleaseContextService(
        repository=repository, bindings_path=bindings_copy,
    )
    _bump_mtime(bindings_copy)
    service.build_envelope(
        window_start_date=date(2026, 7, 16),
        window_end_date=date(2026, 8, 30),
        force_refresh=True,
    )
    after_force = len(repository.calls)
    _build(repository, bindings_path=bindings_copy)
    assert len(repository.calls) > after_force


def test_runtime_cache_uses_effective_read_snapshot_identity(
    duckdb_path: Path,
    tmp_path: Path,
) -> None:
    first_snapshot = tmp_path / "first.duckdb"
    second_snapshot = tmp_path / "second.duckdb"
    first_snapshot.write_bytes(b"first")
    second_snapshot.write_bytes(b"second")
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    first_selection = DuckDBReadSelection(duckdb_path, first_snapshot, "first")
    second_selection = DuckDBReadSelection(duckdb_path, second_snapshot, "second")
    with duckdb_read_scope(first_selection):
        _build(repository)
        first_calls = len(repository.calls)
        _build(repository)
        assert len(repository.calls) == first_calls
    with duckdb_read_scope(second_selection):
        _build(repository)
        assert len(repository.calls) > first_calls


def test_effective_read_change_during_force_refresh_does_not_refill(
    duckdb_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_snapshot = tmp_path / "first.duckdb"
    second_snapshot = tmp_path / "second.duckdb"
    first_snapshot.write_bytes(b"first")
    second_snapshot.write_bytes(b"second")
    effective_path = [str(first_snapshot)]
    monkeypatch.setattr(
        macro_svc, "resolve_effective_read_path", lambda _: effective_path[0],
    )
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    cached = _build(repository)
    original = macro_svc.HomeMacroReleaseContextService._build_envelope_uncached

    def changing(self, **kwargs):
        envelope = original(self, **kwargs)
        effective_path[0] = str(second_snapshot)
        return envelope

    with monkeypatch.context() as patch:
        patch.setattr(
            macro_svc.HomeMacroReleaseContextService, "_build_envelope_uncached", changing,
        )
        _build(repository, force_refresh=True)
    after_force = len(repository.calls)
    _build(repository)
    assert len(repository.calls) > after_force
    effective_path[0] = str(first_snapshot)
    assert _build(repository) is cached


def test_system_read_namespace_change_during_force_refresh_does_not_refill(
    duckdb_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation = ["first"]
    monkeypatch.setattr(
        system_read_publication_repo,
        "current_system_read_context",
        lambda: SimpleNamespace(
            generation=generation[0],
            publication=SimpleNamespace(
                manifest_sha256=generation[0], database_path=duckdb_path,
            ),
        ),
    )
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    cached = _build(repository)
    original = macro_svc.HomeMacroReleaseContextService._build_envelope_uncached

    def changing(self, **kwargs):
        envelope = original(self, **kwargs)
        generation[0] = "second"
        return envelope

    with monkeypatch.context() as patch:
        patch.setattr(
            macro_svc.HomeMacroReleaseContextService, "_build_envelope_uncached", changing,
        )
        _build(repository, force_refresh=True)
    after_force = len(repository.calls)
    _build(repository)
    assert len(repository.calls) > after_force
    generation[0] = "first"
    assert _build(repository) is cached


def test_required_online_read_cannot_reuse_active_database_cached_envelope(
    duckdb_path: Path,
) -> None:
    repository = _CountingRepository(_ready_reads(), duckdb_path=duckdb_path)
    _build(repository)
    with duckdb_read_scope(None, required_online=True, active_path=duckdb_path):
        with pytest.raises(DuckDBReadSelectionError):
            _build(repository)
