from __future__ import annotations

import os
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.repositories import system_read_publication_repo as publication_repo
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.duckdb_read_context import duckdb_read_scope
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.services import bond_analytics_service as headlines_service
from backend.app.services import bond_dashboard_service as dashboard_service
from tests.test_bond_dashboard_api_contract import (
    _make_bond_analytics_row,
    _replace_bond_dashboard_rows,
)


REPORT_DATE = "2026-08-31"


def _seed_bond_database(path: Path, *, instrument_code: str, market_value: str) -> None:
    repository = BondAnalyticsRepository(str(path))
    _replace_bond_dashboard_rows(
        repository,
        report_date=REPORT_DATE,
        rows=[
            _make_bond_analytics_row(
                report_date=REPORT_DATE,
                instrument_code=instrument_code,
                portfolio_name="P1",
                asset_class_std="rate",
                market_value=headlines_service.Decimal(market_value),
                ytm=headlines_service.Decimal("0.02"),
                modified_duration=headlines_service.Decimal("2"),
                bond_type_label="Rate",
            )
        ],
    )


def _completed_build_row() -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return CacheBuildRunRecord(
        run_id="bundle-read-context",
        job_name=headlines_service.JOB_NAME,
        status="completed",
        cache_key=headlines_service.CACHE_KEY,
        cache_version=headlines_service.CACHE_VERSION,
        lock=headlines_service.BOND_ANALYTICS_LOCK.key,
        source_version="sv",
        vendor_version="vv_none",
        rule_version=headlines_service.RULE_VERSION,
        report_date=REPORT_DATE,
        queued_at=now,
        started_at=now,
        finished_at=now,
        created_at=now,
    ).model_dump()


def _install_system_contexts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    snapshots: dict[str, Path],
    active: Path,
) -> SimpleNamespace:
    governance_path = tmp_path / "governance"
    governance_path.mkdir(exist_ok=True)
    build_row = _completed_build_row()
    GovernanceRepository(base_dir=governance_path).append(CACHE_BUILD_RUN_STREAM, build_row)
    manifest_row = {
        "run_id": build_row["run_id"],
        "cache_key": headlines_service.CACHE_KEY,
        "report_date": REPORT_DATE,
        "source_version": "sv",
        "rule_version": headlines_service.RULE_VERSION,
        "cache_version": headlines_service.CACHE_VERSION,
    }
    settings = SimpleNamespace(
        system_read_publication_enabled=True,
        duckdb_path=str(active),
        governance_path=str(governance_path),
    )
    governance_identity = os.path.normcase(str(governance_path.resolve()))
    contexts: dict[str, SimpleNamespace] = {}
    for generation, snapshot in snapshots.items():
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
                CACHE_BUILD_RUN_STREAM: (deepcopy(build_row),),
                CACHE_MANIFEST_STREAM: (deepcopy(manifest_row),),
            },
        )

    def _resolve(_settings: object, generation: str | None = None) -> SimpleNamespace:
        assert generation is not None
        return contexts[generation]

    monkeypatch.setattr(publication_repo, "_resolve_system_read_context", _resolve)
    monkeypatch.setattr(headlines_service, "get_settings", lambda: settings)
    monkeypatch.setattr(dashboard_service, "get_settings", lambda: settings)
    return settings


def _observe_native_duckdb_opens(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    opened: list[str] = []
    original_connect = duckdb.connect

    def _connect(database: object = ":memory:", *args: object, **kwargs: object):
        database_text = os.fspath(database) if isinstance(database, (str, os.PathLike)) else str(database)
        if database_text != ":memory:":
            opened.append(str(Path(database_text).resolve()))
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", _connect)
    return opened


def test_bundle_headlines_uses_pinned_snapshot_and_reuses_final_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "active.duckdb"
    snapshot = tmp_path / "snapshot.duckdb"
    _seed_bond_database(active, instrument_code="ACTIVE", market_value="999")
    _seed_bond_database(snapshot, instrument_code="SNAPSHOT", market_value="111")
    settings = _install_system_contexts(
        tmp_path,
        monkeypatch,
        snapshots={"generation-a": snapshot},
        active=active,
    )
    dashboard_service.clear_bond_dashboard_runtime_cache()
    headlines_service._bond_analytics_rows_cache.clear()
    headlines_service._portfolio_headlines_cache.clear()
    opened = _observe_native_duckdb_opens(monkeypatch)
    real_compute = headlines_service._compute_portfolio_headlines_metrics
    real_lineage = headlines_service._lineage
    counter_lock = Lock()
    calls = {"compute": 0, "lineage": 0}

    def _count_compute(rows: list[dict[str, object]]) -> dict[str, object]:
        with counter_lock:
            calls["compute"] += 1
        return real_compute(rows)

    def _count_lineage(report_date: str, rows: list[dict[str, object]]) -> dict[str, str]:
        with counter_lock:
            calls["lineage"] += 1
        return real_lineage(report_date, rows)

    monkeypatch.setattr(headlines_service, "_compute_portfolio_headlines_metrics", _count_compute)
    monkeypatch.setattr(headlines_service, "_lineage", _count_lineage)
    report_date = date.fromisoformat(REPORT_DATE)
    with publication_repo.system_read_scope(settings, generation="generation-a"):
        first = dashboard_service.get_bond_dashboard_bundle(
            sections=["portfolio-headlines"],
            report_date=report_date,
        )
        second = dashboard_service.get_bond_dashboard_bundle(
            sections=["portfolio-headlines"],
            report_date=report_date,
        )

    first_section = first["result"]["sections"]["portfolio-headlines"]
    second_section = second["result"]["sections"]["portfolio-headlines"]
    assert first_section["result"]["total_market_value"] == "111.00000000"
    assert second_section["result"] == first_section["result"]
    assert first_section["result_meta"]["trace_id"] != second_section["result_meta"]["trace_id"]
    assert calls == {"compute": 1, "lineage": 1}
    active_resolved = str(active.resolve())
    snapshot_resolved = str(snapshot.resolve())
    assert opened.count(active_resolved) == 0
    assert opened.count(snapshot_resolved) > 0


def test_concurrent_bundles_keep_independent_pinned_generations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "active.duckdb"
    snapshot_a = tmp_path / "snapshot-a.duckdb"
    snapshot_b = tmp_path / "snapshot-b.duckdb"
    _seed_bond_database(active, instrument_code="ACTIVE", market_value="999")
    _seed_bond_database(snapshot_a, instrument_code="SNAPSHOT-A", market_value="111")
    _seed_bond_database(snapshot_b, instrument_code="SNAPSHOT-B", market_value="222")
    settings = _install_system_contexts(
        tmp_path,
        monkeypatch,
        snapshots={"generation-a": snapshot_a, "generation-b": snapshot_b},
        active=active,
    )
    dashboard_service.clear_bond_dashboard_runtime_cache()
    headlines_service._bond_analytics_rows_cache.clear()
    headlines_service._portfolio_headlines_cache.clear()
    opened = _observe_native_duckdb_opens(monkeypatch)
    report_date = date.fromisoformat(REPORT_DATE)

    def _load(generation: str) -> str:
        with publication_repo.system_read_scope(settings, generation=generation):
            bundle = dashboard_service.get_bond_dashboard_bundle(
                sections=["portfolio-headlines"],
                report_date=report_date,
            )
        return bundle["result"]["sections"]["portfolio-headlines"]["result"][
            "total_market_value"
        ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(_load, "generation-a")
        future_b = executor.submit(_load, "generation-b")
        value_a = future_a.result(timeout=10)
        value_b = future_b.result(timeout=10)

    assert value_a == "111.00000000"
    assert value_b == "222.00000000"
    assert opened.count(str(active.resolve())) == 0
    assert opened.count(str(snapshot_a.resolve())) > 0
    assert opened.count(str(snapshot_b.resolve())) > 0


def test_bundle_warm_headlines_fail_closed_without_snapshot_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "active.duckdb"
    snapshot = tmp_path / "snapshot.duckdb"
    _seed_bond_database(active, instrument_code="ACTIVE", market_value="999")
    _seed_bond_database(snapshot, instrument_code="SNAPSHOT", market_value="111")
    settings = _install_system_contexts(
        tmp_path,
        monkeypatch,
        snapshots={"generation-a": snapshot},
        active=active,
    )
    dashboard_service.clear_bond_dashboard_runtime_cache()
    headlines_service._bond_analytics_rows_cache.clear()
    headlines_service._portfolio_headlines_cache.clear()
    opened = _observe_native_duckdb_opens(monkeypatch)
    report_date = date.fromisoformat(REPORT_DATE)
    with publication_repo.system_read_scope(settings, generation="generation-a"):
        dashboard_service.get_bond_dashboard_bundle(
            sections=["portfolio-headlines"],
            report_date=report_date,
        )
        with duckdb_read_scope(None, required_online=True, active_path=active):
            missing_selection = dashboard_service.get_bond_dashboard_bundle(
                sections=["portfolio-headlines"],
                report_date=report_date,
            )
        snapshot.unlink()
        deleted_snapshot = dashboard_service.get_bond_dashboard_bundle(
            sections=["portfolio-headlines"],
            report_date=report_date,
        )

    assert opened.count(str(active.resolve())) == 0
    for failed in (missing_selection, deleted_snapshot):
        result = failed["result"]
        assert "portfolio-headlines" not in result["sections"]
        assert result["failed_sections"] == ["portfolio-headlines"]
        assert result["section_statuses"]["portfolio-headlines"]["status"] == "error"


def test_unscoped_bundle_remains_compatible_and_reports_headlines_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "active.duckdb"
    snapshot = tmp_path / "unused-snapshot.duckdb"
    _seed_bond_database(active, instrument_code="ACTIVE", market_value="999")
    _seed_bond_database(snapshot, instrument_code="SNAPSHOT", market_value="111")
    _install_system_contexts(
        tmp_path,
        monkeypatch,
        snapshots={"generation-a": snapshot},
        active=active,
    )
    dashboard_service.clear_bond_dashboard_runtime_cache()
    headlines_service._bond_analytics_rows_cache.clear()
    headlines_service._portfolio_headlines_cache.clear()
    report_date = date.fromisoformat(REPORT_DATE)
    compatible = dashboard_service.get_bond_dashboard_bundle(
        sections=["portfolio-headlines"],
        report_date=report_date,
    )
    assert compatible["result"]["sections"]["portfolio-headlines"]["result"][
        "total_market_value"
    ] == "999.00000000"

    monkeypatch.setattr(
        dashboard_service,
        "get_portfolio_headlines",
        lambda _report_date: (_ for _ in ()).throw(RuntimeError("headlines unavailable")),
    )
    failed = dashboard_service.get_bond_dashboard_bundle(
        sections=["portfolio-headlines"],
        report_date=report_date,
    )
    result = failed["result"]
    assert "portfolio-headlines" not in result["sections"]
    assert result["failed_sections"] == ["portfolio-headlines"]
    assert result["section_statuses"]["portfolio-headlines"]["status"] == "error"
    assert result["section_statuses"]["portfolio-headlines"]["message"] == "headlines unavailable"
