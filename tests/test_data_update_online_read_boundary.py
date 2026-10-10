from pathlib import Path

import duckdb
import pytest

from backend.app.repositories.data_update_repo import DATE_TABLES, financial_dates
from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    duckdb_read_scope,
)


def _snapshot(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        for _key, _label, table, column in DATE_TABLES:
            conn.execute(f'CREATE TABLE "{table}"("{column}" DATE)')
            conn.execute(f'INSERT INTO "{table}" VALUES (DATE \'2026-08-31\')')
    finally:
        conn.close()


def test_financial_dates_use_pinned_snapshot_even_without_active_file(tmp_path: Path) -> None:
    active, snapshot = tmp_path / "absent-active.duckdb", tmp_path / "snapshot.duckdb"
    _snapshot(snapshot)
    selection = DuckDBReadSelection(active, snapshot, "retained-fixture")
    with duckdb_read_scope(selection, required_online=True):
        rows = financial_dates(active)
    assert len(rows) == 5
    assert all(row["as_of_date"] == "2026-08-31" and row["status"] == "available" for row in rows)
    assert not active.exists()


def test_financial_dates_do_not_hide_missing_required_selection(tmp_path: Path) -> None:
    active = tmp_path / "active.duckdb"
    with duckdb_read_scope(None, required_online=True, active_path=active):
        with pytest.raises(DuckDBReadSelectionError):
            financial_dates(active)


def test_financial_dates_do_not_fall_back_after_snapshot_disappears(tmp_path: Path) -> None:
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "snapshot.duckdb"
    _snapshot(active)
    _snapshot(snapshot)
    selection = DuckDBReadSelection(active, snapshot, "retained-fixture")
    with duckdb_read_scope(selection, required_online=True):
        snapshot.unlink()
        with pytest.raises(DuckDBReadSelectionError):
            financial_dates(active)
@pytest.mark.parametrize("failed_step,change_source,interrupt_after_pnl", [
    ("publish", False, False), ("publish", True, False),
    ("system_read_publish", False, False), ("system_read_publish", True, False),
    ("publish", False, True),
])
def test_publication_recovery_uses_exact_sources_and_retains_old_online_generation(tmp_path, monkeypatch, change_source, failed_step, interrupt_after_pnl):
    """Real isolated publication proves source rejection and atomic old-read retention."""
    from importlib import import_module
    from types import SimpleNamespace

    from backend.app.repositories import data_update_repo
    from backend.app.repositories.system_read_publication_repo import (
        resolve_system_read_publication,
    )
    from backend.app.services import data_update_service
    from backend.app.tasks import data_update_center, system_read_publication
    from backend.app.tasks.financial_result_publication import FinancialPublicationPlan, FinancialTablePublicationSpec
    from scripts import run_global_data_refresh

    fixtures = import_module("tests.test_system_read_publication")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    source, governance = tmp_path / "active.duckdb", tmp_path / "governance"
    pnl_root, archive = tmp_path / "pnl-publications", tmp_path / "archive"
    fixtures._create_lineaged_source(source, preview_batch_id="batch-current")
    pnl = fixtures._publish_test_pnl(source, pnl_root)
    for index, cache_key in enumerate(fixtures._BOOTSTRAP_RESULT_CACHE_KEYS):
        preview = cache_key == "source_preview.foundation"
        fixtures._append_lineage(
            governance, cache_key=cache_key, run_id=f"formal-run-{index}",
            source_version="preview-z-current__preview-t-current" if preview else "source-current",
            rule_version="preview-rule" if preview else None,
            ingest_batch_id="batch-current" if preview else None,
        )
    fixtures._append_source_preview_sources(governance, archive_root=archive, ingest_batch_id="batch-current")
    monkeypatch.setattr("backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance", lambda *_a, **_k: None)
    required = (("fact_result", "report_date", 1), ("phase1_source_preview_summary", "report_date", 2))
    monkeypatch.setattr(run_global_data_refresh, "REQUIRED_DATE_TABLES", required)
    settings = SimpleNamespace(duckdb_path=source, governance_path=governance,
                               financial_publication_root=pnl_root, local_archive_path=archive,
                               system_read_publication_enabled=True, financial_publication_enabled=True)
    steps = list(fixtures._core_step_receipts())
    steps[-1]["result"].update(generation=pnl.generation, manifest_sha256=pnl.manifest_sha256)
    old = system_read_publication.publish_system_read_generation(
        settings, report_date="2026-09-15", data_update_run_id="old-request", global_run_id="old-global",
        step_receipts=tuple(steps), pnl_generation=pnl.generation, pnl_manifest_sha256=pnl.manifest_sha256,
        required_date_tables=required,
    )
    recovery_steps = steps
    if failed_step == "publish":
        # Reuse the compact database fixture, replacing only the production page
        # plan builder; sealing, source checks and atomic pointers remain real.
        recovery_steps = [dict(step) for step in steps[:-1]]
        recovery_steps[-1] = {**recovery_steps[-1], "result": {
            **recovery_steps[-1]["result"], "dependency_versions": {"source": "source-current"},
        }}

        def fixture_page_plan(_settings, **kwargs):
            return FinancialPublicationPlan(
                generation="pnl-recovery-fixture", expected_previous_generation=kwargs["expected_previous_generation"],
                tables=(FinancialTablePublicationSpec(name="fact_result", date_column="report_date", required_dates=("2026-09-15",)),),
                required_steps=tuple(step["name"] for step in kwargs["step_receipts"]), step_receipts=kwargs["step_receipts"],
                required_dependency_keys=("source", "pnl_by_business_page.payload_sha256"),
                dependency_versions={"source": "source-current", "pnl_by_business_page.payload_sha256": "payload-current"},
                coverage_dates={"pnl": ("2026-09-15",)},
                supported_api_versions=(fixtures.FINANCIAL_PUBLICATION_API_VERSION,),
                supported_schema_versions=(fixtures.FINANCIAL_PUBLICATION_SCHEMA_VERSION,),
                quality={"status": "passed", "checks": ({"name": "fixture", "status": "passed"},)},
                source_dependency_validator=lambda conn: {
                    "source": "source-current",
                    "pnl_by_business_page.payload_sha256": conn.execute("select payload_sha256 from fact_pnl_by_business_page_envelope").fetchone()[0],
                },
            )

        monkeypatch.setattr("backend.app.tasks.pnl_by_business_page_publication.build_pnl_by_business_financial_publication_plan", fixture_page_plan)
    failed_steps = [*recovery_steps, {"name": failed_step, "status": "failed"}]
    original = data_update_repo.save_run(governance, {
        "run_id": "failed-request", "workflow": "core_financial", "report_date": "2026-09-15",
        "global_run_id": "new-global", "status": "failed", "submitted_at": data_update_service.utc_now(),
        "failure_receipt": {"status": "failed", "run_id": "new-global", "report_date": "2026-09-15",
                            "failed_step": failed_step, "steps": failed_steps},
        "steps": [{"key": step["name"], "status": step["status"]} for step in failed_steps],
    })
    monkeypatch.setattr(data_update_service, "require_scheduler", lambda _: None)
    recovery = data_update_service.request_publication_recovery(
        settings, original["run_id"], requested_by="operator", idempotency_key="fixture-recovery",
    )
    if change_source:
        with duckdb.connect(str(source)) as conn:
            conn.execute("update fact_pnl_by_business_page_envelope set payload_sha256 = 'changed-source-cut'")
    monkeypatch.setattr(data_update_center, "_execute_core", lambda *_a, **_k: pytest.fail("must not recompute finance"))
    monkeypatch.setattr(data_update_center, "_recover_pending_pnl_by_business_precompute", lambda _: 0)
    if interrupt_after_pnl:
        publisher = system_read_publication.publish_system_read_generation

        def interrupted_system_publish(*_args, **_kwargs):
            raise RuntimeError("synthetic crash after PnL pointer commit")

        monkeypatch.setattr(system_read_publication, "publish_system_read_generation", interrupted_system_publish)
        assert data_update_center.drain_updates(settings) == 1
        assert resolve_system_read_publication(settings).generation == old.generation
        monkeypatch.setattr(system_read_publication, "publish_system_read_generation", publisher)
        recovery = data_update_service.request_publication_recovery(
            settings, original["run_id"], requested_by="operator", idempotency_key="retry-after-commit",
        )
        # Only the already committed exact PnL result may be reused on retry.
        monkeypatch.setattr("backend.app.tasks.financial_result_publication.publish_financial_result",
                            lambda **_kwargs: pytest.fail("must reuse committed PnL generation"))
    assert data_update_center.drain_updates(settings) == int(change_source)
    stored = next(run for run in data_update_repo.latest_runs(governance) if run["run_id"] == recovery["run_id"])
    current = resolve_system_read_publication(settings)
    if change_source:
        assert stored["status"] == "failed"
        assert current.generation == old.generation
        with duckdb.connect(str(current.database_path), read_only=True) as conn:
            assert conn.execute("select payload_sha256 from fact_pnl_by_business_page_envelope").fetchone() == ("payload-current",)
    else:
        assert stored["status"] == "completed"
        assert current.generation != old.generation
        assert resolve_system_read_publication(settings, old.generation).generation == old.generation
