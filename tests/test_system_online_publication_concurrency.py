"""Synthetic lifecycle proof; this is not a real financial-update acceptance run."""

from __future__ import annotations

import asyncio
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import duckdb
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.main import SystemReadPublicationMiddleware
from backend.app.repositories import system_read_publication_repo
from backend.app.repositories.duckdb_read_context import current_duckdb_read_selection
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.financial_result_publication_repo import read_publication_pointer
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_API_VERSION,
    SYSTEM_READ_GENERATION_HEADER,
    SYSTEM_READ_SCHEMA_VERSION,
    current_system_read_context,
    resolve_system_read_publication,
    system_read_publication_root,
)
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationPlan,
    FinancialTablePublicationSpec,
    publish_financial_result,
)
from tests.test_system_online_read_boundary import (
    _bundle,
    _publish_fixture,
    _seal_generation,
    _settings,
    _write_pointer,
)


def _hold_synthetic_writer(active: str, ready, release) -> None:
    source = Path(active)
    lock = resolve_duckdb_writer_lock(source, ttl_seconds=60)
    with acquire_lock(lock, base_dir=source.parent):
        conn = duckdb.connect(active)
        try:
            conn.execute("UPDATE sentinel SET value = 'NEW'")
            ready.set()
            if not release.wait(30):
                raise TimeoutError("Parent did not finish bounded concurrent read proof.")
        finally:
            conn.close()


def _plan(settings, generation: str) -> FinancialPublicationPlan:
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-r0", "PNL")
    _write_pointer(pnl_root, "pnl-r0", [("pnl-r0", pnl_digest)])
    bundle = _bundle(settings, "pnl-r0", pnl_digest)
    bundle["workflow"] = "core_financial"
    return FinancialPublicationPlan(
        generation=generation,
        expected_previous_generation=None,
        tables=(
            FinancialTablePublicationSpec(
                name="sentinel", date_column="report_date", required_dates=("2026-09-15",)
            ),
        ),
        required_steps=("verify",),
        step_receipts=(
            {"name": "verify", "status": "completed", "result": {"status": "completed"}},
        ),
        required_dependency_keys=("synthetic-source",),
        dependency_versions={"synthetic-source": "fixture-v1"},
        coverage_dates={"sentinel": ("2026-09-15",)},
        supported_api_versions=(SYSTEM_READ_API_VERSION,),
        supported_schema_versions=(SYSTEM_READ_SCHEMA_VERSION,),
        quality={"status": "passed", "checks": ({"name": "fixture", "status": "passed"},)},
        source_dependency_validator=lambda _conn: {"synthetic-source": "fixture-v1"},
        full_database=True,
        system_read_bundle=bundle,
    )


@pytest.mark.parametrize("failure_stage", ["before_pointer_commit", "pointer_committed"])
def test_full_publication_keeps_http_reads_stable_through_writer_and_commit_recovery(
    tmp_path: Path, failure_stage: str
) -> None:
    settings = _settings(tmp_path)
    conn = duckdb.connect(settings.duckdb_path)
    try:
        conn.execute("ALTER TABLE sentinel ADD COLUMN report_date DATE DEFAULT '2026-09-15'")
    finally:
        conn.close()
    root = system_read_publication_root(settings)
    generation_r0 = "system-read-2026-09-15-00000000000000000000"
    generation_r1 = "system-read-2026-09-15-11111111111111111111"
    plan_r0 = _plan(settings, generation_r0)
    publish_financial_result(
        source_duckdb_path=settings.duckdb_path, publication_root=root, plan=plan_r0
    )

    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)

    @app.get("/probe")
    def read_probe():
        with read_only_connection(settings.duckdb_path) as conn:
            return {"value": conn.execute("SELECT value FROM sentinel").fetchone()[0]}

    with TestClient(app) as client:
        assert client.get("/probe").json() == {"value": "ACTIVE"}
        context = multiprocessing.get_context("spawn")
        ready, release = context.Event(), context.Event()
        writer = context.Process(
            target=_hold_synthetic_writer,
            args=(settings.duckdb_path, ready, release),
        )
        writer.start()
        try:
            assert ready.wait(20), "Governed writer could not acquire/open the active database."
            for clients in (5, 10):
                with ThreadPoolExecutor(max_workers=clients) as pool:
                    responses = list(pool.map(lambda _: client.get("/probe"), range(clients * 2)))
                assert writer.is_alive(), "Reads did not overlap the real open writer."
                assert all(response.status_code == 200 for response in responses)
                assert all(response.json() == {"value": "ACTIVE"} for response in responses)
                assert all(
                    response.headers[SYSTEM_READ_GENERATION_HEADER] == generation_r0
                    for response in responses
                )
        finally:
            release.set()
            writer.join(30)
            if writer.is_alive():
                writer.terminate()
                writer.join(5)
        assert writer.exitcode == 0

        plan_r1 = replace(
            plan_r0,
            generation=generation_r1,
            expected_previous_generation=generation_r0,
        )
        observed_stages: list[str] = []

        def fail_at_boundary(stage: str) -> None:
            observed_stages.append(stage)
            response = client.get("/probe", headers={SYSTEM_READ_GENERATION_HEADER: generation_r0})
            assert response.status_code == 200
            assert response.json() == {"value": "ACTIVE"}
            if stage == failure_stage:
                raise RuntimeError("Injected metadata/commit-boundary interruption")

        with pytest.raises(RuntimeError, match="Injected metadata/commit-boundary"):
            publish_financial_result(
                source_duckdb_path=settings.duckdb_path,
                publication_root=root,
                plan=plan_r1,
                on_stage=fail_at_boundary,
            )
        assert failure_stage in observed_stages
        expected_current = generation_r0 if failure_stage == "before_pointer_commit" else generation_r1
        assert read_publication_pointer(root)["generation"] == expected_current
        receipt = publish_financial_result(
            source_duckdb_path=settings.duckdb_path,
            publication_root=root,
            plan=plan_r1,
        )
        assert receipt.generation == generation_r1
        new_response = client.get("/probe")
        assert new_response.status_code == 200
        assert new_response.headers[SYSTEM_READ_GENERATION_HEADER] == generation_r1
        assert new_response.json() == {"value": "NEW"}
        old_response = client.get("/probe", headers={SYSTEM_READ_GENERATION_HEADER: generation_r0})
        assert old_response.status_code == 200
        assert old_response.json() == {"value": "ACTIVE"}


@pytest.mark.parametrize("warm_previous", [False, True], ids=["cold", "generation_switch"])
def test_slow_publication_resolution_keeps_event_loop_and_liveness_available(
    tmp_path: Path, monkeypatch, warm_previous: bool
) -> None:
    settings = _settings(tmp_path)
    previous_generation, current_generation = _publish_fixture(settings)
    if warm_previous:
        root = system_read_publication_root(settings)
        pointer = read_publication_pointer(root)
        retained = [
            (item["generation"], item["manifest_sha256"])
            for item in pointer["retained_generations"]
        ]
        previous_entry = next(item for item in retained if item[0] == previous_generation)
        _write_pointer(root, previous_generation, [previous_entry])
        assert resolve_system_read_publication(settings).generation == previous_generation
        _write_pointer(root, current_generation, retained)

    resolution_started = threading.Event()
    release_resolution = threading.Event()
    resolution_finished = threading.Event()
    original_resolver = system_read_publication_repo._resolve_system_read_context

    def slow_resolver(*args, **kwargs):
        resolution_started.set()
        # A bounded fallback lets the old blocking implementation fail without hanging pytest.
        release_resolution.wait(3)
        try:
            return original_resolver(*args, **kwargs)
        finally:
            resolution_finished.set()

    monkeypatch.setattr(system_read_publication_repo, "_resolve_system_read_context", slow_resolver)
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)

    @app.get("/probe")
    async def probe() -> dict[str, str]:
        context = current_system_read_context()
        selection = current_duckdb_read_selection()
        assert context is not None and selection is not None
        await asyncio.sleep(0)
        with read_only_connection(settings.duckdb_path) as conn:
            value = conn.execute("SELECT value FROM sentinel").fetchone()[0]
        return {"generation": context.generation, "selection": selection.generation, "value": value}

    @app.get("/health/live")
    async def health_live() -> dict[str, bool]:
        return {
            "resolution_pending": not resolution_finished.is_set(),
            "unpinned": current_system_read_context() is None
            and current_duckdb_read_selection() is None,
        }

    async def run_requests() -> None:
        ticker_progressed = asyncio.Event()

        async def ticker() -> None:
            while not resolution_finished.is_set():
                if resolution_started.is_set():
                    ticker_progressed.set()
                await asyncio.sleep(0)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            ticking = asyncio.create_task(ticker())
            request = asyncio.create_task(client.get("/probe"))
            try:
                assert await asyncio.to_thread(resolution_started.wait, 3)
                await asyncio.sleep(0)
                live = await client.get("/health/live")
                assert live.status_code == 200
                assert SYSTEM_READ_GENERATION_HEADER not in live.headers
                assert live.json() == {"resolution_pending": True, "unpinned": True}
                assert ticker_progressed.is_set(), "The event loop stalled during publication resolution."
            finally:
                release_resolution.set()
                response = await request
                await ticking
            assert response.status_code == 200
            assert response.headers[SYSTEM_READ_GENERATION_HEADER] == current_generation
            assert response.json() == {
                "generation": current_generation, "selection": current_generation, "value": "R1"
            }
            assert current_system_read_context() is None
            assert current_duckdb_read_selection() is None

    asyncio.run(run_requests())
