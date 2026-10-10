from __future__ import annotations

import os
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from decimal import Decimal
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace

import pytest

from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    duckdb_read_scope,
    resolve_effective_read_path,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
)
from backend.app.repositories import system_read_publication_repo as publication_repo
from backend.app.services import bond_analytics_service as service


REPORT_DATE = "2026-08-31"
OTHER_REPORT_DATE = "2026-07-31"


def _same_stat_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    active = tmp_path / "active.duckdb"
    snapshot_a = tmp_path / "snapshot-a.duckdb"
    snapshot_b = tmp_path / "snapshot-b.duckdb"
    for path in (active, snapshot_a, snapshot_b):
        path.write_bytes(b"sealed-bond-fixture")
    shared_ns = 1_750_000_000_000_000_000
    for path in (active, snapshot_a, snapshot_b):
        os.utime(path, ns=(shared_ns, shared_ns))
    return active, snapshot_a, snapshot_b


def _selection(active: Path, snapshot: Path, generation: str) -> DuckDBReadSelection:
    return DuckDBReadSelection(
        active_path=active,
        snapshot_path=snapshot,
        generation=generation,
    )


def _install_row_probe(
    monkeypatch: pytest.MonkeyPatch,
    *,
    active: Path,
) -> list[str]:
    calls: list[str] = []
    settings = SimpleNamespace(duckdb_path=str(active))
    monkeypatch.setattr(service, "get_settings", lambda: settings)

    class _ProbeRepository:
        def fetch_bond_analytics_rows(
            self,
            *,
            report_date: str,
            asset_class: str = "all",
            accounting_class: str = "all",
        ) -> list[dict[str, object]]:
            effective_path = resolve_effective_read_path(active)
            calls.append(effective_path)
            return [
                {
                    "report_date": report_date,
                    "asset_class": asset_class,
                    "accounting_class": accounting_class,
                    "snapshot_name": Path(effective_path).name,
                }
            ]

    monkeypatch.setattr(service, "_repo", lambda: _ProbeRepository())
    service._bond_analytics_rows_cache.clear()
    return calls


def _headline_rows() -> list[dict[str, object]]:
    return [
        {
            "report_date": REPORT_DATE,
            "instrument_code": "BOND-001",
            "instrument_name": "Fixture Bond",
            "asset_class_std": "rate",
            "issuer_name": "Fixture Issuer",
            "market_value": Decimal("1000000"),
            "market_value_native": Decimal("1000000"),
            "currency_code": "CNY",
            "ytm": Decimal("0.021"),
            "coupon_rate": Decimal("0.025"),
            "macaulay_duration": Decimal("3.6"),
            "modified_duration": Decimal("3.5"),
            "dv01": Decimal("350"),
            "spread_dv01": Decimal("0"),
            "convexity": Decimal("12"),
            "maturity_date": "2031-08-31",
            "source_version": "sv_fixture_bond",
            "rule_version": service.RULE_VERSION,
        }
    ]


def _install_pinned_system_contexts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    generations: tuple[str, ...] = ("generation-a",),
) -> tuple[SimpleNamespace, dict[str, SimpleNamespace], Path]:
    active, snapshot_a, snapshot_b = _same_stat_files(tmp_path)
    snapshots = (snapshot_a, snapshot_b)
    governance_path = tmp_path / "governance"
    governance_path.mkdir()
    settings = SimpleNamespace(
        system_read_publication_enabled=True,
        duckdb_path=str(active),
        governance_path=str(governance_path),
    )
    build_rows = tuple(
        {
            "run_id": f"run-fixture-bond-{report_date}",
            "job_name": service.JOB_NAME,
            "status": "completed",
            "cache_key": service.CACHE_KEY,
            "report_date": report_date,
            "source_version": "sv_fixture_bond",
            "rule_version": service.RULE_VERSION,
            "cache_version": service.CACHE_VERSION,
            "vendor_version": "vv_none",
            "finished_at": "2026-09-01T00:00:00+00:00",
        }
        for report_date in (OTHER_REPORT_DATE, REPORT_DATE)
    )
    manifest_rows = tuple(
        {
            "run_id": f"run-fixture-bond-{report_date}",
            "cache_key": service.CACHE_KEY,
            "report_date": report_date,
            "source_version": "sv_fixture_bond",
            "rule_version": service.RULE_VERSION,
            "cache_version": service.CACHE_VERSION,
        }
        for report_date in (OTHER_REPORT_DATE, REPORT_DATE)
    )
    contexts: dict[str, SimpleNamespace] = {}
    governance_identity = os.path.normcase(str(governance_path.resolve()))
    for index, generation in enumerate(generations):
        snapshot = snapshots[index]
        publication = SimpleNamespace(
            database_path=snapshot.resolve(),
            generation=generation,
            manifest_sha256=f"sha256-{generation}",
        )
        contexts[generation] = SimpleNamespace(
            generation=generation,
            publication=publication,
            governance_base_identity=governance_identity,
            governance_streams={
                CACHE_BUILD_RUN_STREAM: deepcopy(build_rows),
                CACHE_MANIFEST_STREAM: deepcopy(manifest_rows),
            },
        )

    def _resolve(_settings: object, generation: str | None = None) -> SimpleNamespace:
        selected = generation or generations[-1]
        return contexts[selected]

    monkeypatch.setattr(publication_repo, "_resolve_system_read_context", _resolve)
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    return settings, contexts, active


def test_rows_cache_does_not_cross_contaminate_same_stat_snapshots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active, snapshot_a, snapshot_b = _same_stat_files(tmp_path)
    calls = _install_row_probe(monkeypatch, active=active)

    with duckdb_read_scope(_selection(active, snapshot_a, "generation-a"), required_online=True):
        rows_a = service._fetch_bond_analytics_rows_cached(report_date=REPORT_DATE)
    with duckdb_read_scope(_selection(active, snapshot_b, "generation-b"), required_online=True):
        rows_b = service._fetch_bond_analytics_rows_cached(report_date=REPORT_DATE)

    assert rows_a[0]["snapshot_name"] == snapshot_a.name
    assert rows_b[0]["snapshot_name"] == snapshot_b.name
    assert calls == [str(snapshot_a.resolve()), str(snapshot_b.resolve())]


def test_rows_cache_warm_hit_still_fails_closed_without_required_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active, snapshot_a, _ = _same_stat_files(tmp_path)
    _install_row_probe(monkeypatch, active=active)

    with duckdb_read_scope(_selection(active, snapshot_a, "generation-a"), required_online=True):
        service._fetch_bond_analytics_rows_cached(report_date=REPORT_DATE)

    with duckdb_read_scope(None, required_online=True, active_path=active):
        with pytest.raises(DuckDBOnlineReadRequiredError):
            service._fetch_bond_analytics_rows_cached(report_date=REPORT_DATE)


def test_rows_cache_warm_hit_still_fails_closed_after_snapshot_deletion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active, snapshot_a, _ = _same_stat_files(tmp_path)
    _install_row_probe(monkeypatch, active=active)
    selection = _selection(active, snapshot_a, "generation-a")

    with duckdb_read_scope(selection, required_online=True):
        service._fetch_bond_analytics_rows_cached(report_date=REPORT_DATE)
        snapshot_a.unlink()
        with pytest.raises(DuckDBReadSelectionError, match="unavailable"):
            service._fetch_bond_analytics_rows_cached(report_date=REPORT_DATE)


def test_pinned_headlines_cache_reuses_real_compute_and_lineage_with_fresh_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = _install_pinned_system_contexts(tmp_path, monkeypatch)
    rows = _headline_rows()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: rows)
    real_compute = service._compute_portfolio_headlines_metrics
    real_lineage = service._lineage
    calls = {"compute": 0, "lineage": 0}

    def _count_compute(values: list[dict[str, object]]) -> dict[str, object]:
        calls["compute"] += 1
        return real_compute(values)

    def _count_lineage(report_date: str, values: list[dict[str, object]]) -> dict[str, str]:
        calls["lineage"] += 1
        return real_lineage(report_date, values)

    monkeypatch.setattr(service, "_compute_portfolio_headlines_metrics", _count_compute)
    monkeypatch.setattr(service, "_lineage", _count_lineage)

    with publication_repo.system_read_scope(settings, generation="generation-a"):
        first = service.get_portfolio_headlines(service.date.fromisoformat(REPORT_DATE))
        second = service.get_portfolio_headlines(service.date.fromisoformat(REPORT_DATE))
        first["result"]["warnings"].append("caller mutation")
        third = service.get_portfolio_headlines(service.date.fromisoformat(REPORT_DATE))

    assert calls == {"compute": 1, "lineage": 1}
    assert "caller mutation" not in second["result"]["warnings"]
    assert "caller mutation" not in third["result"]["warnings"]
    assert first["result_meta"]["trace_id"] != second["result_meta"]["trace_id"]
    assert second["result_meta"]["trace_id"] != third["result_meta"]["trace_id"]
    assert second["result"] == third["result"]
    second_meta = {key: value for key, value in second["result_meta"].items() if key != "trace_id"}
    third_meta = {key: value for key, value in third["result_meta"].items() if key != "trace_id"}
    assert second_meta == third_meta


def test_unscoped_headlines_calls_keep_legacy_recompute_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active, _, _ = _same_stat_files(tmp_path)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(duckdb_path=str(active)))
    rows = _headline_rows()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: rows)
    monkeypatch.setattr(service, "_build_fact_envelope", lambda **kwargs: kwargs["result_payload"])
    real_compute = service._compute_portfolio_headlines_metrics
    calls = {"compute": 0}

    def _count_compute(values: list[dict[str, object]]) -> dict[str, object]:
        calls["compute"] += 1
        return real_compute(values)

    monkeypatch.setattr(service, "_compute_portfolio_headlines_metrics", _count_compute)
    service.get_portfolio_headlines(service.date.fromisoformat(REPORT_DATE))
    service.get_portfolio_headlines(service.date.fromisoformat(REPORT_DATE))

    assert calls == {"compute": 2}


def test_pinned_headlines_cache_isolated_by_full_system_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = _install_pinned_system_contexts(
        tmp_path,
        monkeypatch,
        generations=("generation-a", "generation-b"),
    )
    service._portfolio_headlines_cache.clear()
    rows = _headline_rows()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: rows)
    real_compute = service._compute_portfolio_headlines_metrics
    calls = {"compute": 0}

    def _count_compute(values: list[dict[str, object]]) -> dict[str, object]:
        calls["compute"] += 1
        return real_compute(values)

    monkeypatch.setattr(service, "_compute_portfolio_headlines_metrics", _count_compute)
    report_date = service.date.fromisoformat(REPORT_DATE)
    with publication_repo.system_read_scope(settings, generation="generation-a"):
        first_a = service.get_portfolio_headlines(report_date)
        second_a = service.get_portfolio_headlines(report_date)
    with publication_repo.system_read_scope(settings, generation="generation-b"):
        first_b = service.get_portfolio_headlines(report_date)

    assert calls == {"compute": 2}
    assert first_a["result"] == second_a["result"]
    payload_a = {key: value for key, value in first_a["result"].items() if key != "computed_at"}
    payload_b = {key: value for key, value in first_b["result"].items() if key != "computed_at"}
    assert payload_a == payload_b
    assert first_a["result_meta"]["trace_id"] != second_a["result_meta"]["trace_id"]


def test_pinned_headlines_cache_singleflights_concurrent_builds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = _install_pinned_system_contexts(tmp_path, monkeypatch)
    service._portfolio_headlines_cache.clear()
    rows = _headline_rows()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: rows)
    real_compute = service._compute_portfolio_headlines_metrics
    started = Event()
    release = Event()
    counter_lock = Lock()
    calls = {"compute": 0}

    def _blocking_compute(values: list[dict[str, object]]) -> dict[str, object]:
        with counter_lock:
            calls["compute"] += 1
        started.set()
        assert release.wait(timeout=5)
        return real_compute(values)

    monkeypatch.setattr(service, "_compute_portfolio_headlines_metrics", _blocking_compute)
    report_date = service.date.fromisoformat(REPORT_DATE)
    with publication_repo.system_read_scope(settings, generation="generation-a"):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(copy_context().run, service.get_portfolio_headlines, report_date)
                for _ in range(4)
            ]
            assert started.wait(timeout=5)
            release.set()
            results = [future.result(timeout=5) for future in futures]

    assert calls == {"compute": 1}
    assert all(result["result"] == results[0]["result"] for result in results[1:])
    assert len({result["result_meta"]["trace_id"] for result in results}) == 4


def test_pinned_headlines_cache_retries_after_failed_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = _install_pinned_system_contexts(tmp_path, monkeypatch)
    service._portfolio_headlines_cache.clear()
    rows = _headline_rows()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: rows)
    real_compute = service._compute_portfolio_headlines_metrics
    calls = {"compute": 0}

    def _fail_once(values: list[dict[str, object]]) -> dict[str, object]:
        calls["compute"] += 1
        if calls["compute"] == 1:
            raise RuntimeError("fixture compute failure")
        return real_compute(values)

    monkeypatch.setattr(service, "_compute_portfolio_headlines_metrics", _fail_once)
    report_date = service.date.fromisoformat(REPORT_DATE)
    with publication_repo.system_read_scope(settings, generation="generation-a"):
        with pytest.raises(RuntimeError, match="fixture compute failure"):
            service.get_portfolio_headlines(report_date)
        recovered = service.get_portfolio_headlines(report_date)
        cached = service.get_portfolio_headlines(report_date)

    assert calls == {"compute": 2}
    assert recovered["result"] == cached["result"]
    assert recovered["result_meta"]["trace_id"] != cached["result_meta"]["trace_id"]


def test_report_date_invalidation_isolated_across_headlines_cache_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = _install_pinned_system_contexts(tmp_path, monkeypatch)
    service._portfolio_headlines_cache.clear()
    rows = _headline_rows()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: rows)
    real_lineage = service._lineage
    lineage_calls = {REPORT_DATE: 0, OTHER_REPORT_DATE: 0}

    def _count_lineage(report_date: str, values: list[dict[str, object]]) -> dict[str, str]:
        lineage_calls[report_date] += 1
        return real_lineage(report_date, values)

    monkeypatch.setattr(service, "_lineage", _count_lineage)
    current = service.date.fromisoformat(REPORT_DATE)
    other = service.date.fromisoformat(OTHER_REPORT_DATE)
    with publication_repo.system_read_scope(settings, generation="generation-a"):
        service.get_portfolio_headlines(current)
        service.get_portfolio_headlines(other)
        service._invalidate_bond_analytics_caches_for_report_date(REPORT_DATE)
        service.get_portfolio_headlines(current)
        service.get_portfolio_headlines(other)

    assert lineage_calls == {REPORT_DATE: 2, OTHER_REPORT_DATE: 1}


def test_inflight_headlines_build_cannot_restore_invalidated_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = _install_pinned_system_contexts(tmp_path, monkeypatch)
    service._portfolio_headlines_cache.clear()
    rows = _headline_rows()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: rows)
    real_compute = service._compute_portfolio_headlines_metrics
    started = Event()
    release = Event()
    calls = {"compute": 0}

    def _blocking_compute(values: list[dict[str, object]]) -> dict[str, object]:
        calls["compute"] += 1
        if calls["compute"] == 1:
            started.set()
            assert release.wait(timeout=5)
        return real_compute(values)

    monkeypatch.setattr(service, "_compute_portfolio_headlines_metrics", _blocking_compute)
    report_date = service.date.fromisoformat(REPORT_DATE)
    with publication_repo.system_read_scope(settings, generation="generation-a"):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(copy_context().run, service.get_portfolio_headlines, report_date)
            assert started.wait(timeout=5)
            service._invalidate_bond_analytics_caches_for_report_date(REPORT_DATE)
            release.set()
            future.result(timeout=5)
        service.get_portfolio_headlines(report_date)

    assert calls == {"compute": 2}


def test_inflight_rows_build_cannot_restore_invalidated_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active, snapshot_a, _ = _same_stat_files(tmp_path)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(duckdb_path=str(active)))
    service._bond_analytics_rows_cache.clear()
    started = Event()
    release = Event()
    calls = {"repo": 0}

    class _BlockingRepository:
        def fetch_bond_analytics_rows(self, **_: object) -> list[dict[str, object]]:
            calls["repo"] += 1
            if calls["repo"] == 1:
                started.set()
                assert release.wait(timeout=5)
            return [{"call": calls["repo"]}]

    monkeypatch.setattr(service, "_repo", lambda: _BlockingRepository())
    selection = _selection(active, snapshot_a, "generation-a")
    with duckdb_read_scope(selection, required_online=True):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                copy_context().run,
                service._fetch_bond_analytics_rows_cached,
                report_date=REPORT_DATE,
            )
            assert started.wait(timeout=5)
            service._invalidate_bond_analytics_caches_for_report_date(REPORT_DATE)
            release.set()
            future.result(timeout=5)
        service._fetch_bond_analytics_rows_cached(report_date=REPORT_DATE)

    assert calls == {"repo": 2}


def test_warm_headlines_cache_rechecks_required_selection_and_snapshot_existence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, contexts, active = _install_pinned_system_contexts(tmp_path, monkeypatch)
    service._portfolio_headlines_cache.clear()
    rows = _headline_rows()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: rows)
    report_date = service.date.fromisoformat(REPORT_DATE)

    with publication_repo.system_read_scope(settings, generation="generation-a"):
        service.get_portfolio_headlines(report_date)
        with duckdb_read_scope(None, required_online=True, active_path=active):
            with pytest.raises(DuckDBOnlineReadRequiredError):
                service.get_portfolio_headlines(report_date)
        Path(contexts["generation-a"].publication.database_path).unlink()
        with pytest.raises(DuckDBReadSelectionError, match="unavailable"):
            service.get_portfolio_headlines(report_date)


def test_empty_headlines_payload_and_provenance_are_cached_without_timestamp_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, _ = _install_pinned_system_contexts(tmp_path, monkeypatch)
    service._portfolio_headlines_cache.clear()
    monkeypatch.setattr(service, "_fetch_bond_analytics_rows_cached", lambda **_: [])
    report_date = service.date.fromisoformat(REPORT_DATE)
    with publication_repo.system_read_scope(settings, generation="generation-a"):
        first = service.get_portfolio_headlines(report_date)
        second = service.get_portfolio_headlines(report_date)

    assert first["result"] == second["result"]
    assert first["result"]["warnings"] == [service.EMPTY_WARNING]
    assert first["result"]["computed_at"] == second["result"]["computed_at"]
    first_meta = {key: value for key, value in first["result_meta"].items() if key != "trace_id"}
    second_meta = {key: value for key, value in second["result_meta"].items() if key != "trace_id"}
    assert first_meta == second_meta
    assert first["result_meta"]["trace_id"] != second["result_meta"]["trace_id"]
