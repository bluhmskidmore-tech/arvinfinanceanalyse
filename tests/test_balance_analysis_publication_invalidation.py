from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        duckdb_path=str(tmp_path / "facts.duckdb"),
        balance_analysis_publication_root=str(tmp_path / "published"),
        financial_publication_root="",
        balance_analysis_publication_enabled=False,
    )


def _seed_publications(root: Path, generations: tuple[tuple[str, str], ...]) -> None:
    """Build only the synthetic sealed artifacts required by the real reader."""
    from backend.app.repositories import financial_result_publication_repo as repo

    (root / "generations").mkdir(parents=True)
    retained = []
    for generation, report_date in generations:
        payload = {"coverage_dates": {"balance_analysis_overview": [report_date]}}
        payload_json = repo.canonical_json_bytes(payload).decode("utf-8")
        payload_sha256 = repo.sha256_bytes(payload_json.encode("utf-8"))
        database_path = repo.generation_database_path(root, generation)
        with duckdb.connect(str(database_path)) as conn:
            conn.execute(
                f"create table {repo.PUBLICATION_MANIFEST_TABLE} ("
                "protocol_version varchar, generation varchar, "
                "sealed_payload_json varchar, sealed_payload_sha256 varchar)"
            )
            conn.execute(
                f"insert into {repo.PUBLICATION_MANIFEST_TABLE} values (?, ?, ?, ?)",
                [repo.PUBLICATION_PROTOCOL_VERSION, generation, payload_json, payload_sha256],
            )
        manifest = {
            "protocol_version": repo.PUBLICATION_PROTOCOL_VERSION,
            "generation": generation,
            "validity": {"state": "valid"},
            "compatibility": {
                "supported_api_versions": ["balance-analysis-api/v1"],
                "supported_schema_versions": ["balance-analysis-overview/v1"],
            },
            "database": {
                "file_name": database_path.name,
                "size_bytes": database_path.stat().st_size,
                "sha256": repo.sha256_file(database_path),
            },
            "sealed_payload": payload,
            "sealed_payload_sha256": payload_sha256,
        }
        manifest_bytes = repo.canonical_json_bytes(manifest)
        repo.generation_manifest_path(root, generation).write_bytes(manifest_bytes)
        retained.append(
            {"generation": generation, "manifest_sha256": repo.sha256_bytes(manifest_bytes)}
        )
    (root / repo.PUBLICATION_POINTER_FILE).write_bytes(
        repo.canonical_json_bytes(
            {
                "protocol_version": repo.PUBLICATION_PROTOCOL_VERSION,
                **retained[0],
                "validity": {"state": "valid"},
                "retained_generations": retained,
            }
        )
    )


def test_balance_fact_guard_does_not_import_publication_actor(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    root = Path(settings.balance_analysis_publication_root)
    _seed_publications(root, (("current", "2025-12-31"), ("previous", "2025-12-31")))
    original_import = builtins.__import__
    modules_before = set(sys.modules)

    def guarded_import(name, *args, **kwargs):
        if name.startswith(("backend.app.tasks", "backend.app.services")):
            raise AssertionError(f"Fact invalidation imported an upper-layer module: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    from backend.app.governance import settings as settings_module
    from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    state_module = sys.modules.get("backend.app.repositories.balance_analysis_publication_state")
    if state_module is not None:
        monkeypatch.setattr(state_module, "get_settings", lambda: settings)
    original_connect = duckdb.connect

    class ReachedFactConnection(RuntimeError):
        pass

    def connect(database, *args, **kwargs):
        if Path(database).resolve() == Path(settings.duckdb_path).resolve():
            raise ReachedFactConnection("invalidation completed before fact connection")
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", connect)
    with repository_task_write_scope("backend.app.tasks.invalidation_test"):
        with pytest.raises(ReachedFactConnection, match="invalidation completed"):
            BalanceAnalysisRepository(settings.duckdb_path).replace_formal_balance_rows(
                report_date="2025-12-31",
                zqtz_rows=[],
                tyw_rows=[],
                writer_lock_already_held=True,
            )

    from backend.app.repositories.balance_analysis_publication_state import (
        invalidate_balance_analysis_publications_before_fact_change,
    )

    assert invalidate_balance_analysis_publications_before_fact_change(
        source_duckdb_path=settings.duckdb_path,
        report_dates=(),
        reason="empty-date replay",
        settings=settings,
    ) == ()
    assert (root / "invalidations" / "current.json").is_file()
    assert (root / "invalidations" / "previous.json").is_file()
    assert not Path(settings.duckdb_path).exists()
    assert not any(
        name.startswith(("backend.app.tasks", "backend.app.services"))
        for name in set(sys.modules) - modules_before
    )


def test_fact_change_revokes_retained_before_current_when_reads_are_disabled(tmp_path) -> None:
    from backend.app.repositories.balance_analysis_publication_state import (
        invalidate_balance_analysis_publications_before_fact_change,
    )

    settings = _settings(tmp_path)
    root = Path(settings.balance_analysis_publication_root)
    _seed_publications(root, (("current", "2025-12-31"), ("previous", "2025-12-31")))

    assert invalidate_balance_analysis_publications_before_fact_change(
        source_duckdb_path=settings.duckdb_path,
        report_dates=("2025-12-31",),
        reason="replace balance facts",
        settings=settings,
    ) == ("previous", "current")
    pointer = json.loads((root / "current.json").read_text(encoding="utf-8"))
    assert pointer["validity"]["state"] == "invalid"
    for generation in ("current", "previous"):
        receipt = json.loads((root / "invalidations" / f"{generation}.json").read_text(encoding="utf-8"))
        assert receipt["generation"] == generation
        assert receipt["reason"] == "replace balance facts"


def test_retained_generation_is_revoked_after_current_was_already_revoked(tmp_path) -> None:
    from backend.app.repositories.balance_analysis_publication_state import (
        invalidate_balance_analysis_publications_before_fact_change,
    )
    from backend.app.repositories.financial_result_publication_repo import invalidate_financial_generation

    settings = _settings(tmp_path)
    root = Path(settings.balance_analysis_publication_root)
    _seed_publications(root, (("current", "2026-01-31"), ("previous", "2025-12-31")))
    invalidate_financial_generation(root, generation="current", reason="newer date changed")

    assert invalidate_balance_analysis_publications_before_fact_change(
        source_duckdb_path=settings.duckdb_path,
        report_dates=("2025-12-31",),
        reason="older date changed",
        settings=settings,
    ) == ("previous",)


@pytest.mark.parametrize("case", ["other_database", "empty_dates", "uncovered_date"])
def test_unaffected_fact_change_preserves_publications(tmp_path, case) -> None:
    from backend.app.repositories.balance_analysis_publication_state import (
        invalidate_balance_analysis_publications_before_fact_change,
    )

    settings = _settings(tmp_path)
    root = Path(settings.balance_analysis_publication_root)
    _seed_publications(root, (("current", "2025-12-31"),))
    pointer_before = (root / "current.json").read_bytes()
    source_path = tmp_path / "other.duckdb" if case == "other_database" else settings.duckdb_path
    dates = () if case == "empty_dates" else ("2026-01-31" if case == "uncovered_date" else "2025-12-31",)

    assert invalidate_balance_analysis_publications_before_fact_change(
        source_duckdb_path=source_path,
        report_dates=dates,
        reason="unaffected change",
        settings=settings,
    ) == ()
    assert (root / "current.json").read_bytes() == pointer_before
    assert not (root / "invalidations").exists()


def test_corrupt_retained_manifest_blocks_before_any_invalidation(tmp_path) -> None:
    from backend.app.repositories.balance_analysis_publication_state import (
        BalanceAnalysisPublicationNotReady,
        invalidate_balance_analysis_publications_before_fact_change,
    )
    from backend.app.repositories.financial_result_publication_repo import generation_manifest_path

    settings = _settings(tmp_path)
    root = Path(settings.balance_analysis_publication_root)
    _seed_publications(root, (("current", "2025-12-31"), ("previous", "2025-12-31")))
    pointer_before = (root / "current.json").read_bytes()
    generation_manifest_path(root, "previous").write_bytes(b"{broken manifest")

    with pytest.raises(BalanceAnalysisPublicationNotReady, match="Cannot validate committed"):
        invalidate_balance_analysis_publications_before_fact_change(
            source_duckdb_path=settings.duckdb_path,
            report_dates=("2025-12-31",),
            reason="replacement must fail closed",
            settings=settings,
        )
    assert (root / "current.json").read_bytes() == pointer_before
    assert not (root / "invalidations").exists()


def test_balance_replace_aborts_before_fact_connection_on_invalidation_failure(tmp_path, monkeypatch) -> None:
    from backend.app.repositories import balance_analysis_publication_state as state
    from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    database = tmp_path / "facts.duckdb"
    observed = []

    def fail(**kwargs):
        observed.append(kwargs)
        raise RuntimeError("publication invalidation unavailable")

    def unexpected_connect(*args, **kwargs):
        raise AssertionError("fact connection opened before successful invalidation")

    monkeypatch.setattr(state, "invalidate_balance_analysis_publications_before_fact_change", fail)
    monkeypatch.setattr(duckdb, "connect", unexpected_connect)
    with repository_task_write_scope("backend.app.tasks.invalidation_test"):
        with pytest.raises(RuntimeError, match="publication invalidation unavailable"):
            BalanceAnalysisRepository(str(database)).replace_formal_balance_rows(
                report_date="2025-12-31", zqtz_rows=[], tyw_rows=[],
            )
    assert observed == [{
        "source_duckdb_path": str(database),
        "report_dates": ("2025-12-31",),
        "reason": "formal_balance_facts_replace",
    }]
    assert not database.exists()


def test_v24_aborts_before_formal_backfill_on_invalidation_failure(tmp_path, monkeypatch) -> None:
    from backend.app.repositories import balance_analysis_publication_state as state
    from backend.app.repositories.duckdb_migrations import _v24_zqtz_accounting_sub_type

    database = tmp_path / "migration.duckdb"
    observed = []

    def fail(**kwargs):
        observed.append(kwargs)
        raise RuntimeError("publication invalidation unavailable")

    monkeypatch.setattr(state, "invalidate_balance_analysis_publications_before_fact_change", fail)
    with duckdb.connect(str(database)) as conn:
        for table in ("zqtz_bond_daily_snapshot", "fact_formal_zqtz_balance_daily"):
            conn.execute(f"create table {table} (report_date varchar, business_type_primary varchar, sub_type varchar)")
        conn.execute("insert into fact_formal_zqtz_balance_daily values ('2025-12-31', 'government', '')")
        with pytest.raises(RuntimeError, match="publication invalidation unavailable"):
            _v24_zqtz_accounting_sub_type(conn)
        assert conn.execute("select sub_type from fact_formal_zqtz_balance_daily").fetchall() == [("",)]
    assert len(observed) == 1
    assert Path(observed[0]["source_duckdb_path"]).samefile(database)
    assert observed[0]["report_dates"] == ("2025-12-31",)
    assert observed[0]["reason"] == "migration_v24_formal_balance_sub_type_backfill"
