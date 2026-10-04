from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

import backend.app.tasks.data_update_center as data_update_center
import backend.app.tasks.system_read_publication as system_read_publication
from backend.app.tasks.balance_analysis_materialize import (
    compose_balance_analysis_source_version,
)
from backend.app.repositories.financial_result_publication_repo import (
    FINANCIAL_PUBLICATION_API_VERSION,
    FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    open_financial_generation,
    read_publication_pointer,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.data_update_repo import save_run as save_data_update_run
from backend.app.repositories.system_read_publication_repo import (
    current_system_read_context,
    resolve_system_read_publication,
    system_read_scope,
    system_read_publication_root,
)
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationInvalid,
    FinancialPublicationPlan,
    FinancialTablePublicationSpec,
    publish_financial_result,
    _validate_table_coverage,
)
from backend.app.tasks.system_read_publication import (
    SYSTEM_READ_CORE_REQUIRED_STEPS,
    SYSTEM_READ_PUBLICATION_API_VERSION,
    SYSTEM_READ_PUBLICATION_SCHEMA_VERSION,
    _BOOTSTRAP_RESULT_CACHE_KEYS,
    _balance_manifest_matches_current_facts,
    _accounting_asset_movement_manifest_matches_current_facts,
    _bond_manifest_matches_current_facts,
    _freeze_result_lineage,
    _bootstrap_persisted_steps,
    _require_terminal_fact_link,
    _pnl_manifest_matches_current_facts,
    _risk_manifest_matches_current_facts,
    _source_preview_manifest_matches_current_facts,
    _select_bootstrap_lineage_references,
    _source_cut_snapshot,
    publish_preserved_system_read_generation,
    publish_qualified_balance_daily_system_read_generation,
    publish_qualified_system_read_bootstrap,
    publish_system_read_generation,
    recover_committed_system_read_publication,
    qualify_existing_system_read_bootstrap,
)
from backend.app.services.pretrade_qualification import (
    unavailable_pretrade_qualification,
)
from scripts.run_global_data_refresh import GlobalDataRefreshFailed
from tests.helpers import ROOT


def _create_source(path: Path, *, external_csv: Path | None = None) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute("create schema analytics")
        conn.execute("create table fact_result(report_date date, value integer)")
        conn.execute("insert into fact_result values ('2026-09-15', 11)")
        conn.execute("create table analytics.dimension(code varchar)")
        conn.execute("insert into analytics.dimension values ('A')")
        conn.execute("create view analytics.result_view as select value from main.fact_result")
        conn.execute("create macro analytics.add_one(value) as value + 1")
        if external_csv is not None:
            escaped = str(external_csv).replace("'", "''")
            conn.execute(
                "create view analytics.external_view as "
                f"select * from read_csv_auto('{escaped}')"
            )
    finally:
        conn.close()


def _bundle(source: Path, governance: Path) -> dict[str, object]:
    return {
        "protocol_version": 1,
        "active_database_identity": str(source.resolve()),
        "full_database": True,
        "governance_base_identity": str(governance.resolve()),
        "governance_streams": {
            "cache_build_run": [
                {
                    "run_id": "formal-run",
                    "cache_key": "formal-cache",
                    "status": "completed",
                }
            ],
            "cache_manifest": [
                {"cache_key": "formal-cache", "fact_tables": ["fact_result"]}
            ],
        },
        "pnl_generation": "pnl-generation",
        "pnl_manifest_sha256": "a" * 64,
        "data_update_run_id": "data-update-run",
        "global_run_id": "global-run",
        "workflow": "core_financial",
        "report_date": "2026-09-15",
    }


def _plan(
    source: Path,
    governance: Path,
    *,
    dependency_validator,
) -> FinancialPublicationPlan:
    return FinancialPublicationPlan(
        generation="system-read-2026-09-15-fixture",
        expected_previous_generation=None,
        tables=(
            FinancialTablePublicationSpec(
                name="fact_result",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
        ),
        required_steps=("verify",),
        step_receipts=(
            {
                "name": "verify",
                "status": "completed",
                "result": {"status": "completed", "report_date": "2026-09-15"},
            },
        ),
        required_dependency_keys=("source",),
        dependency_versions={"source": "source-v1"},
        coverage_dates={"core": ("2026-09-15",)},
        supported_api_versions=(SYSTEM_READ_PUBLICATION_API_VERSION,),
        supported_schema_versions=(SYSTEM_READ_PUBLICATION_SCHEMA_VERSION,),
        quality={
            "status": "passed",
            "checks": ({"name": "coverage", "status": "passed"},),
        },
        source_dependency_validator=dependency_validator,
        full_database=True,
        system_read_bundle=_bundle(source, governance),
    )


def _create_lineaged_source(path: Path, *, preview_batch_id: str = "") -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            "create table fact_result("
            "report_date date, value integer, source_version varchar)"
        )
        conn.execute(
            "insert into fact_result values ('2026-09-15', 11, 'source-current')"
        )
        conn.execute("create schema analytics")
        conn.execute("create view analytics.result_view as select value from main.fact_result")
        conn.execute("create macro analytics.add_one(value) as value + 1")
        conn.execute(
            "create table fact_pnl_by_business_page_envelope("
            "report_date date, dependency_versions_json varchar, payload_sha256 varchar, "
            "protocol_version varchar)"
        )
        conn.execute(
            "insert into fact_pnl_by_business_page_envelope values "
            "('2026-09-15', '{\"source\":\"source-current\"}', "
            "'payload-current', 'pnl_by_business_page_envelope/v1')"
        )
        conn.execute(
            "create table phase1_source_preview_summary("
            "report_date date, ingest_batch_id varchar, batch_created_at varchar, "
            "source_family varchar, source_file varchar, source_version varchar, "
            "rule_version varchar)"
        )
        conn.execute(
            "insert into phase1_source_preview_summary values "
            "('2026-09-15', ?, '2026-09-15T01:00:00Z', "
            "'zqtz', 'zqtz-current.csv', 'preview-z-current', 'preview-rule'), "
            "('2026-09-15', ?, '2026-09-15T01:00:00Z', "
            "'tyw', 'tyw-current.csv', 'preview-t-current', 'preview-rule')",
            [preview_batch_id, preview_batch_id],
        )
    finally:
        conn.close()


def _publish_test_pnl(source: Path, publication_root: Path):
    plan = FinancialPublicationPlan(
        generation="pnl-2026-09-15-fixture",
        expected_previous_generation=None,
        tables=(
            FinancialTablePublicationSpec(
                name="fact_result",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
        ),
        required_steps=("verify",),
        step_receipts=(
            {
                "name": "verify",
                "status": "completed",
                "result": {"status": "completed", "report_date": "2026-09-15"},
            },
        ),
        required_dependency_keys=(
            "pnl_by_business_page.payload_sha256",
            "source",
        ),
        dependency_versions={
            "pnl_by_business_page.payload_sha256": "payload-current",
            "source": "source-current",
        },
        coverage_dates={"pnl": ("2026-09-15",)},
        supported_api_versions=(FINANCIAL_PUBLICATION_API_VERSION,),
        supported_schema_versions=(FINANCIAL_PUBLICATION_SCHEMA_VERSION,),
        quality={
            "status": "passed",
            "checks": ({"name": "fixture", "status": "passed"},),
        },
        source_dependency_validator=lambda _conn: {
            "pnl_by_business_page.payload_sha256": "payload-current",
            "source": "source-current",
        },
    )
    return publish_financial_result(
        source_duckdb_path=source,
        publication_root=publication_root,
        plan=plan,
    )


def _append_lineage(
    governance: Path,
    *,
    cache_key: str,
    run_id: str,
    source_version: str,
    input_sources: tuple[str, ...] | None = None,
    rule_version: str | None = None,
    ingest_batch_id: str | None = None,
) -> None:
    repo = GovernanceRepository(base_dir=governance, backend_mode="jsonl")
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": "fixture",
            "cache_key": cache_key,
            "status": "completed",
            "report_date": "2026-09-15",
            "source_version": source_version,
            **({"rule_version": rule_version} if rule_version is not None else {}),
            "ingest_batch_id": ingest_batch_id,
        },
    )
    repo.append(
        CACHE_MANIFEST_STREAM,
        {
            "run_id": run_id,
            "cache_key": cache_key,
            "report_date": "2026-09-15",
            "source_version": source_version,
            **({"rule_version": rule_version} if rule_version is not None else {}),
            "fact_tables": ["fact_result"],
            **(
                {"input_sources": list(input_sources)}
                if input_sources is not None
                else {}
            ),
        },
    )


def _append_source_preview_sources(
    governance: Path,
    *,
    archive_root: Path,
    ingest_batch_id: str,
    manifest_archive_root: Path | None = None,
) -> None:
    archive_root.mkdir()
    resolved_manifest_root = manifest_archive_root or archive_root
    resolved_manifest_root.mkdir(exist_ok=True)
    for source_file in ("zqtz-current.csv", "tyw-current.csv"):
        (archive_root / source_file).write_text(source_file, encoding="utf-8")
        (resolved_manifest_root / source_file).write_text(source_file, encoding="utf-8")
    GovernanceRepository(base_dir=governance, backend_mode="jsonl").append_many_atomic(
        [
            (
                SOURCE_MANIFEST_STREAM,
                {
                    "status": "completed",
                    "ingest_batch_id": ingest_batch_id,
                    "source_family": source_family,
                    "source_file": source_file,
                    "source_version": source_version,
                    "report_date": "2026-09-15",
                    "created_at": "2026-09-15T00:30:00Z",
                    "archived_path": str(resolved_manifest_root / source_file),
                },
            )
            for source_family, source_file, source_version in (
                ("zqtz", "zqtz-current.csv", "preview-z-current"),
                ("tyw", "tyw-current.csv", "preview-t-current"),
            )
        ]
    )


def _core_step_receipts() -> tuple[dict[str, object], ...]:
    receipts: list[dict[str, object]] = []
    for index, step_name in enumerate(SYSTEM_READ_CORE_REQUIRED_STEPS):
        result: dict[str, object] = {
            "status": "completed",
            "report_date": "2026-09-15",
        }
        if index < len(_BOOTSTRAP_RESULT_CACHE_KEYS):
            result.update(
                {
                    "run_id": f"formal-run-{index}",
                    "cache_key": _BOOTSTRAP_RESULT_CACHE_KEYS[index],
                }
            )
        receipts.append(
            {
                "name": step_name,
                "status": "completed",
                "result": result,
            }
        )
    return tuple(receipts)


def _persisted_bootstrap_steps(pnl_receipt) -> list[dict[str, object]]:
    return [
        {
            "key": step_name,
            "status": "completed",
            "started_at": f"2026-09-15T00:00:{index:02d}+00:00",
            "finished_at": f"2026-09-15T00:01:{index:02d}+00:00",
            "elapsed_seconds": 60.0,
            **(
                {
                    "result": {
                        "status": "completed",
                        "generation": pnl_receipt.generation,
                        "manifest_sha256": pnl_receipt.manifest_sha256,
                    }
                }
                if step_name == "publish"
                else {}
            ),
        }
        for index, step_name in enumerate(SYSTEM_READ_CORE_REQUIRED_STEPS)
    ]


def _bootstrap_settings_and_run(
    tmp_path: Path,
    *,
    duplicate_current_balance: bool = False,
    source_preview_terminal_mode: str = "explicit",
    invalid_source_preview_archive: bool = False,
):
    source = tmp_path / "active.duckdb"
    governance = tmp_path / "governance"
    pnl_root = tmp_path / "pnl-publications"
    preview_batch_id = "batch-current" if source_preview_terminal_mode == "explicit" else ""
    _create_lineaged_source(source, preview_batch_id=preview_batch_id)
    pnl_receipt = _publish_test_pnl(source, pnl_root)
    archive_root = tmp_path / "source-preview-archive"
    manifest_archive_root = tmp_path / "outside-source-preview-archive"
    _append_source_preview_sources(
        governance,
        archive_root=archive_root,
        ingest_batch_id=preview_batch_id,
        manifest_archive_root=(
            manifest_archive_root if invalid_source_preview_archive else None
        ),
    )
    for index, cache_key in enumerate(_BOOTSTRAP_RESULT_CACHE_KEYS):
        if cache_key == "source_preview.foundation":
            terminal_variants = {
                "explicit": (("", "batch-current", "preview-rule", None),),
                "duplicate_empty": (
                    ("-none", None, "preview-rule", None),
                    ("-empty", "", "preview-rule", None),
                ),
                "single_unknown": (("-unknown", "", None, None),),
                "conflicting_empty": (
                    ("-a", "", "preview-rule", ("phase1_source_preview_summary",)),
                    ("-b", "", "preview-rule", ("different-input",)),
                ),
            }[source_preview_terminal_mode]
            terminal_source_version = (
                "preview-z-current__preview-t-current"
                if source_preview_terminal_mode == "explicit"
                else "preview-t-current__preview-z-current"
            )
            for suffix, batch_id, rule_version, input_sources in terminal_variants:
                _append_lineage(
                    governance,
                    cache_key=cache_key,
                    run_id=f"current-{index}{suffix}",
                    source_version=terminal_source_version,
                    rule_version=rule_version,
                    ingest_batch_id=batch_id,
                    input_sources=input_sources,
                )
            continue
        _append_lineage(
            governance,
            cache_key=cache_key,
            run_id=f"current-{index}",
            source_version="source-current",
        )
    if duplicate_current_balance:
        _append_lineage(
            governance,
            cache_key=_BOOTSTRAP_RESULT_CACHE_KEYS[0],
            run_id="current-duplicate",
            source_version="source-current",
            input_sources=("different-input",),
        )
    save_data_update_run(
        governance,
        {
            "run_id": "data-update-run",
            "workflow": "core_financial",
            "report_date": "2026-09-15",
            "global_run_id": "global-run",
            "status": "completed",
            "submitted_at": "2026-09-15T00:00:00+00:00",
            "steps": _persisted_bootstrap_steps(pnl_receipt),
        },
    )
    return SimpleNamespace(
        duckdb_path=str(source),
        governance_path=governance,
        financial_publication_root=str(pnl_root),
        system_read_publication_enabled=True,
        local_archive_path=str(archive_root),
    )


def _isolate_bootstrap_to_real_source_preview_predicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = system_read_publication._manifest_matches_current_facts

    def scoped_match(conn, *, manifest, **kwargs):
        if str(manifest.get("cache_key") or "") != "source_preview.foundation":
            return True
        return original(conn, manifest=manifest, **kwargs)

    monkeypatch.setattr(
        system_read_publication,
        "_manifest_matches_current_facts",
        scoped_match,
    )


def _forbid_source_ingest_and_financial_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("bootstrap must not ingest sources or replay the financial chain")

    monkeypatch.setattr(
        "backend.app.tasks.source_preview_refresh._run_source_preview_ingest",
        forbidden,
    )
    monkeypatch.setattr(data_update_center, "_execute_core", forbidden)


def _spy_real_source_preview_predicate(
    monkeypatch: pytest.MonkeyPatch,
) -> list[bool | None]:
    calls: list[bool | None] = []
    original = system_read_publication._source_preview_manifest_matches_current_facts

    def spy(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result)
        return result

    monkeypatch.setattr(
        system_read_publication,
        "_source_preview_manifest_matches_current_facts",
        spy,
    )
    return calls


def test_full_database_publication_preserves_schema_view_and_macro_from_read_only_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "system-read"
    governance = tmp_path / "governance"
    governance.mkdir()
    _create_source(source)
    validation_calls: list[str] = []

    def dependency_validator(_conn):
        validation_calls.append("validated")
        return {"source": "source-v1"}

    receipt = publish_financial_result(
        source_duckdb_path=source,
        publication_root=root,
        plan=_plan(source, governance, dependency_validator=dependency_validator),
        writer_lock_already_held=True,
    )

    assert validation_calls == ["validated", "validated"]
    assert read_publication_pointer(root)["generation"] == receipt.generation  # type: ignore[index]
    with open_financial_generation(
        root,
        generation=receipt.generation,
        reader_api_version=SYSTEM_READ_PUBLICATION_API_VERSION,
        reader_schema_version=SYSTEM_READ_PUBLICATION_SCHEMA_VERSION,
    ) as (conn, resolved):
        assert conn.execute("select value from analytics.result_view").fetchone() == (11,)
        assert conn.execute("select analytics.add_one(11)").fetchone() == (12,)
        assert conn.execute("select code from analytics.dimension").fetchone() == ("A",)
        sealed = resolved.manifest["sealed_payload"]
        assert sealed["system_read_bundle"]["active_database_identity"] == str(source.resolve())
        child_guard_root = source.parent
        child_guard_receipt = child_guard_root / "pytest-duckdb-guard-attempts.jsonl"
        writer = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys\n"
                    "import _pytest_duckdb_guard as guard\n"
                    "guard.register_pytest_duckdb_temp_root(sys.argv[2])\n"
                    "guard.set_pytest_duckdb_guard_phase('child')\n"
                    "try:\n"
                    "    import duckdb\n"
                    "    c=duckdb.connect(sys.argv[1])\n"
                    "    try:\n"
                    "        c.execute(\"insert into fact_result values ('2026-09-15', 12)\")\n"
                    "    finally:\n"
                    "        c.close()\n"
                    "finally:\n"
                    "    guard.finalize_pytest_duckdb_guard()\n"
                ),
                str(source),
                str(child_guard_root),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert writer.returncode == 0, writer.stderr
        child_attempts = [
            json.loads(line)
            for line in child_guard_receipt.read_text(encoding="utf-8").splitlines()
        ]
        assert len(child_attempts) == 1
        child_attempt = child_attempts[0]
        assert child_attempt["pid"] != os.getpid()
        assert child_attempt["phase"] == "child"
        assert child_attempt["target_classification"] == "owned_temp"
        assert child_attempt["canonical_path"] == str(source.resolve())
        assert child_attempt["access"] == "read_write_or_default"
        assert child_attempt["decision"] == "allow"
        assert child_attempt["expected_denial"] is False
        assert "sql" not in child_attempt and "rows" not in child_attempt


def test_publish_system_read_generation_resolves_complete_small_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    source = tmp_path / "active.duckdb"
    governance = tmp_path / "governance"
    pnl_root = tmp_path / "pnl-publications"
    archive_root = tmp_path / "source-preview-archive"
    _create_lineaged_source(source, preview_batch_id="batch-current")
    pnl_receipt = _publish_test_pnl(source, pnl_root)
    for index, cache_key in enumerate(_BOOTSTRAP_RESULT_CACHE_KEYS):
        _append_lineage(
            governance,
            cache_key=cache_key,
            run_id=f"formal-run-{index}",
            source_version=(
                "preview-z-current__preview-t-current"
                if cache_key == "source_preview.foundation"
                else "source-current"
            ),
            rule_version=(
                "preview-rule" if cache_key == "source_preview.foundation" else None
            ),
            ingest_batch_id=(
                "batch-current" if cache_key == "source_preview.foundation" else None
            ),
        )
    _append_source_preview_sources(
        governance,
        archive_root=archive_root,
        ingest_batch_id="batch-current",
    )
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    settings = SimpleNamespace(
        duckdb_path=str(source),
        governance_path=governance,
        financial_publication_root=str(pnl_root),
        system_read_publication_enabled=True,
        local_archive_path=str(archive_root),
    )

    receipt = publish_system_read_generation(
        settings,
        report_date="2026-09-15",
        data_update_run_id="data-update-run",
        global_run_id="global-run",
        step_receipts=_core_step_receipts(),
        pnl_generation=pnl_receipt.generation,
        pnl_manifest_sha256=pnl_receipt.manifest_sha256,
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )

    resolved = resolve_system_read_publication(settings, receipt.generation)
    assert resolved.generation == receipt.generation
    bundle = resolved.manifest["sealed_payload"]["system_read_bundle"]
    assert bundle["protocol_version"] == 2
    assert bundle["pretrade_availability"] == unavailable_pretrade_qualification(
        "no_prior_system_read_pretrade_qualification"
    )
    with system_read_scope(settings, receipt.generation):
        context = current_system_read_context()
        assert context is not None
        assert dict(context.pretrade_availability) == bundle["pretrade_availability"]
    assert receipt.resource_limits is not None
    assert receipt.resource_limits["profile"] == "bounded_v1"
    assert receipt.resource_limits["scope"] == "system_read_publication"
    assert {
        observation["label"]
        for observation in receipt.resource_limits["observations"]
    } >= {"system_read_source", "system_read_candidate_build"}
    conn = duckdb.connect(str(resolved.database_path), read_only=True)
    try:
        assert conn.execute("select analytics.add_one(value) from fact_result").fetchone() == (12,)
        assert conn.execute("select value from analytics.result_view").fetchone() == (11,)
    finally:
        conn.close()


def test_normal_publication_rejects_missing_required_domain_terminal_reference() -> None:
    receipts = list(_core_step_receipts())
    broken = dict(receipts[2])
    broken["result"] = {
        "status": "completed",
        "report_date": "2026-09-15",
    }
    receipts[2] = broken

    with pytest.raises(FinancialPublicationInvalid, match="risk_tensor:materialize:formal"):
        system_read_publication._collect_lineage_references(tuple(receipts))


def test_system_publication_rejects_pnl_dependency_cut_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "active.duckdb"
    pnl_root = tmp_path / "pnl-publications"
    _create_lineaged_source(source)
    pnl_receipt = _publish_test_pnl(source, pnl_root)
    conn = duckdb.connect(str(source))
    try:
        conn.execute(
            "update fact_pnl_by_business_page_envelope "
            "set payload_sha256 = 'payload-changed'"
        )
    finally:
        conn.close()
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    settings = SimpleNamespace(financial_publication_root=str(pnl_root))
    conn = duckdb.connect(str(source), read_only=True)
    try:
        with pytest.raises(FinancialPublicationInvalid, match="current committed PnL"):
            system_read_publication._pnl_source_dependency_snapshot(
                settings,
                conn,
                report_date="2026-09-15",
                generation=pnl_receipt.generation,
                manifest_sha256="f" * 64,
                require_current_pointer=True,
            )
        with pytest.raises(FinancialPublicationInvalid, match="does not match"):
            system_read_publication._pnl_source_dependency_snapshot(
                settings,
                conn,
                report_date="2026-09-15",
                generation=pnl_receipt.generation,
                manifest_sha256=pnl_receipt.manifest_sha256,
                require_current_pointer=True,
            )
    finally:
        conn.close()


def test_bootstrap_read_only_preflight_then_publish_resolves_without_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_bootstrap_to_real_source_preview_predicate(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(tmp_path)
    system_root = system_read_publication_root(settings)
    assert not system_root.exists()

    qualification = qualify_existing_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )

    assert qualification["status"] == "completed"
    assert qualification["original_child_run_ids_recovered"] is False
    assert {
        reference["run_id"]
        for reference in qualification["qualified_terminal_references"]
    } == {f"current-{index}" for index in range(len(_BOOTSTRAP_RESULT_CACHE_KEYS))}
    assert not system_root.exists()

    receipt = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )
    resolved = resolve_system_read_publication(settings, receipt.generation)
    assert resolved.generation == receipt.generation
    bundle = resolved.manifest["sealed_payload"]["system_read_bundle"]
    assert bundle["data_update_run_id"] == "data-update-run"


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_source_preview
def test_bootstrap_qualifies_same_identity_none_and_empty_batch_source_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_bootstrap_to_real_source_preview_predicate(monkeypatch)
    preview_calls = _spy_real_source_preview_predicate(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(
        tmp_path,
        source_preview_terminal_mode="duplicate_empty",
    )
    source = Path(settings.duckdb_path)
    before_source = (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    system_root = system_read_publication_root(settings)

    qualification = qualify_existing_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )

    source_preview_reference = next(
        reference
        for reference in qualification["qualified_terminal_references"]
        if reference["cache_key"] == "source_preview.foundation"
    )
    assert source_preview_reference["run_id"] == "current-6-empty"
    assert preview_calls == [True, True]
    assert not system_root.exists()

    receipt = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )

    resolved = resolve_system_read_publication(settings, receipt.generation)
    assert resolved.generation == receipt.generation
    assert all(result is True for result in preview_calls)
    assert (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    ) == before_source


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_source_preview
def test_bootstrap_keeps_explicit_source_preview_batch_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_bootstrap_to_real_source_preview_predicate(monkeypatch)
    preview_calls = _spy_real_source_preview_predicate(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(
        tmp_path,
        source_preview_terminal_mode="explicit",
    )

    qualification = qualify_existing_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )

    source_preview_reference = next(
        reference
        for reference in qualification["qualified_terminal_references"]
        if reference["cache_key"] == "source_preview.foundation"
    )
    assert source_preview_reference["run_id"] == "current-6"
    assert preview_calls == [True, True]


@pytest.mark.parametrize(
    "case",
    ("unknown", "per_family_changed", "invalid_archive", "identity_mismatch"),
)
@pytest.mark.excluded_surface_regression
@pytest.mark.surface_source_preview
def test_bootstrap_rejects_unqualified_empty_batch_source_preview_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    _isolate_bootstrap_to_real_source_preview_predicate(monkeypatch)
    preview_calls = _spy_real_source_preview_predicate(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(
        tmp_path,
        source_preview_terminal_mode=(
            "single_unknown" if case == "unknown" else "duplicate_empty"
        ),
        invalid_source_preview_archive=case == "invalid_archive",
    )
    source = Path(settings.duckdb_path)
    if case == "per_family_changed":
        changed_file = Path(settings.local_archive_path) / "zqtz-new.csv"
        changed_file.write_text("zqtz-new.csv", encoding="utf-8")
        GovernanceRepository(
            base_dir=Path(settings.governance_path),
            backend_mode="jsonl",
        ).append(
            SOURCE_MANIFEST_STREAM,
            {
                "status": "completed",
                "ingest_batch_id": "",
                "source_family": "zqtz",
                "source_file": "zqtz-new.csv",
                "source_version": "preview-z-new",
                "report_date": "2026-09-16",
                "created_at": "2026-09-16T00:30:00Z",
                "archived_path": str(changed_file),
            },
        )
        conn = duckdb.connect(str(source))
        try:
            conn.execute(
                "insert into phase1_source_preview_summary values "
                "('2026-09-16', '', '2026-09-16T01:00:00Z', "
                "'zqtz', 'zqtz-new.csv', 'preview-z-new', 'preview-rule')"
            )
        finally:
            conn.close()
    elif case == "identity_mismatch":
        conn = duckdb.connect(str(source))
        try:
            conn.execute(
                "update phase1_source_preview_summary "
                "set source_version = 'preview-z-mismatch' where source_family = 'zqtz'"
            )
        finally:
            conn.close()
    before_source = (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    system_root = system_read_publication_root(settings)

    with pytest.raises(FinancialPublicationInvalid, match="candidates=0"):
        qualify_existing_system_read_bootstrap(
            settings,
            data_update_run_id="data-update-run",
            required_date_tables=(
                ("fact_result", "report_date", 1),
                ("phase1_source_preview_summary", "report_date", 2),
            ),
        )

    assert preview_calls
    assert preview_calls == ([None] if case == "unknown" else [False])
    assert not (system_root / "current.json").exists()
    assert (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    ) == before_source


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_source_preview
def test_bootstrap_preserves_genuinely_conflicting_qualified_empty_batch_terminals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    _isolate_bootstrap_to_real_source_preview_predicate(monkeypatch)
    preview_calls = _spy_real_source_preview_predicate(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(
        tmp_path,
        source_preview_terminal_mode="conflicting_empty",
    )

    with pytest.raises(FinancialPublicationInvalid, match="candidates=2"):
        qualify_existing_system_read_bootstrap(
            settings,
            data_update_run_id="data-update-run",
            required_date_tables=(
                ("fact_result", "report_date", 1),
                ("phase1_source_preview_summary", "report_date", 2),
            ),
        )

    assert preview_calls == [True, True]


def test_bootstrap_read_only_preflight_fails_closed_without_publication_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    settings = _bootstrap_settings_and_run(
        tmp_path,
        duplicate_current_balance=True,
    )
    system_root = system_read_publication_root(settings)

    with pytest.raises(FinancialPublicationInvalid, match="uniquely qualify"):
        qualify_existing_system_read_bootstrap(
            settings,
            data_update_run_id="data-update-run",
            required_date_tables=(("fact_result", "report_date", 1),),
        )

    assert not system_root.exists()


def test_full_database_publication_rejects_external_view_and_keeps_pointer_uncommitted(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.duckdb"
    root = tmp_path / "system-read"
    governance = tmp_path / "governance"
    governance.mkdir()
    external_csv = tmp_path / "external.csv"
    external_csv.write_text("value\n1\n", encoding="utf-8")
    _create_source(source, external_csv=external_csv)

    with pytest.raises(FinancialPublicationInvalid, match="external dependency"):
        publish_financial_result(
            source_duckdb_path=source,
            publication_root=root,
            plan=_plan(
                source,
                governance,
                dependency_validator=lambda _conn: {"source": "source-v1"},
            ),
            writer_lock_already_held=True,
        )

    assert read_publication_pointer(root, require_valid=False) is None
    source.unlink()


def test_system_read_bundle_is_rejected_on_selected_table_publication(tmp_path: Path) -> None:
    source = tmp_path / "source.duckdb"
    governance = tmp_path / "governance"
    governance.mkdir()
    _create_source(source)
    plan = _plan(
        source,
        governance,
        dependency_validator=lambda _conn: {"source": "source-v1"},
    )
    invalid = FinancialPublicationPlan(
        **{
            **plan.__dict__,
            "full_database": False,
        }
    )

    with pytest.raises(FinancialPublicationInvalid, match="only for a full-database"):
        publish_financial_result(
            source_duckdb_path=source,
            publication_root=tmp_path / "system-read",
            plan=invalid,
        )


def test_frozen_governance_keeps_authoritative_history_order_while_exact_run_is_required() -> None:
    history_runs = [
        {
            "run_id": "historical-run",
            "cache_key": "formal-cache",
            "status": "completed",
            "report_date": "2026-08-31",
            "source_version": "source-old",
        },
        {
            "run_id": "exact-run",
            "cache_key": "formal-cache",
            "status": "completed",
            "report_date": "2026-09-15",
            "source_version": "source-current",
        },
    ]
    history_manifests = [
        {
            "cache_key": "formal-cache",
            "source_version": "source-old",
            "fact_tables": ["fact_result"],
        },
        {
            "cache_key": "formal-cache",
            "source_version": "source-current",
            "fact_tables": ["fact_result"],
        },
    ]

    class Repo:
        def read_all(self, stream):
            return history_runs if stream == "cache_build_run" else history_manifests

    frozen = _freeze_result_lineage(
        Repo(),  # type: ignore[arg-type]
        lineage_references=(("exact-run", "formal-cache"),),
        report_date="2026-09-15",
    )

    assert frozen["cache_build_run"] == history_runs
    assert frozen["cache_manifest"] == history_manifests


def test_terminal_fact_link_rejects_missing_domain_and_mixed_fact_versions() -> None:
    streams = {
        "cache_build_run": [
            {
                "run_id": "exact-run",
                "cache_key": "formal-cache",
                "status": "completed",
                "report_date": "2026-09-15",
                "source_version": "source-current",
            }
        ],
        "cache_manifest": [
            {
                "run_id": "exact-run",
                "cache_key": "formal-cache",
                "source_version": "source-current",
                "fact_tables": ["fact_result"],
            }
        ],
    }
    mixed_profile = {
        "fact_result": {
            "lineage_values": {"source_version": ["source-current", "source-other"]}
        }
    }
    with pytest.raises(FinancialPublicationInvalid, match="does not match source facts"):
        _require_terminal_fact_link(
            streams,
            table_profiles=mixed_profile,
            lineage_references=(("exact-run", "formal-cache"),),
            report_date="2026-09-15",
        )

    with pytest.raises(FinancialPublicationInvalid, match="does not cover required"):
        _require_terminal_fact_link(
            streams,
            table_profiles={
                "fact_result": {
                    "lineage_values": {"source_version": ["source-current"]}
                },
                "unlinked_domain": {"lineage_values": {}},
            },
            lineage_references=(("exact-run", "formal-cache"),),
            report_date="2026-09-15",
        )


def test_source_cut_identity_changes_when_fact_value_changes(tmp_path: Path) -> None:
    database = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(database))
    try:
        conn.execute(
            "create table fact_result(report_date date, value integer, source_version varchar)"
        )
        conn.execute("insert into fact_result values ('2026-09-15', 11, 'source-current')")
        streams = {
            "cache_build_run": [
                {
                    "run_id": "exact-run",
                    "cache_key": "formal-cache",
                    "status": "completed",
                    "report_date": "2026-09-15",
                    "source_version": "source-current",
                }
            ],
            "cache_manifest": [
                {
                    "run_id": "exact-run",
                    "cache_key": "formal-cache",
                    "source_version": "source-current",
                    "fact_tables": ["fact_result"],
                }
            ],
        }
        specs = (
            FinancialTablePublicationSpec(
                name="fact_result",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
        )
        before = _source_cut_snapshot(
            conn,
            table_specs=specs,
            governance_streams=streams,
            lineage_references=(("exact-run", "formal-cache"),),
            report_date="2026-09-15",
        )
        conn.execute("update fact_result set value = 12")
        after = _source_cut_snapshot(
            conn,
            table_specs=specs,
            governance_streams=streams,
            lineage_references=(("exact-run", "formal-cache"),),
            report_date="2026-09-15",
        )
    finally:
        conn.close()

    assert before["table.fact_result"] != after["table.fact_result"]


def test_source_cut_identity_detects_replaced_duplicate_pair(tmp_path: Path) -> None:
    database = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(database))
    try:
        conn.execute(
            "create table fact_result(report_date date, value integer, source_version varchar)"
        )
        conn.execute(
            "insert into fact_result values "
            "('2026-09-15', 11, 'source-current'), "
            "('2026-09-15', 11, 'source-current')"
        )
        streams = {
            "cache_build_run": [
                {
                    "run_id": "exact-run",
                    "cache_key": "formal-cache",
                    "status": "completed",
                    "report_date": "2026-09-15",
                    "source_version": "source-current",
                }
            ],
            "cache_manifest": [
                {
                    "run_id": "exact-run",
                    "cache_key": "formal-cache",
                    "source_version": "source-current",
                    "fact_tables": ["fact_result"],
                }
            ],
        }
        specs = (
            FinancialTablePublicationSpec(
                name="fact_result",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
        )
        before = _source_cut_snapshot(
            conn,
            table_specs=specs,
            governance_streams=streams,
            lineage_references=(("exact-run", "formal-cache"),),
            report_date="2026-09-15",
        )
        conn.execute("update fact_result set value = 12")
        after = _source_cut_snapshot(
            conn,
            table_specs=specs,
            governance_streams=streams,
            lineage_references=(("exact-run", "formal-cache"),),
            report_date="2026-09-15",
        )
    finally:
        conn.close()

    assert before["table.fact_result"] != after["table.fact_result"]


def test_balance_terminal_source_version_reuses_producer_semantics_on_small_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository

    assert compose_balance_analysis_source_version(
        ["source-b", "source-a", "source-a"],
        ["fx-b", "fx-a", "fx-a"],
    ) == "fx-a__fx-b__source-a__source-b"
    database = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(database))
    try:
        conn.execute(
            "create table fact_formal_zqtz_balance_daily("
            "report_date date, source_version varchar, ingest_batch_id varchar)"
        )
        conn.execute(
            "create table fact_formal_tyw_balance_daily("
            "report_date date, source_version varchar, ingest_batch_id varchar)"
        )
        conn.execute(
            "create table fx_daily_mid(trade_date date, source_version varchar)"
        )
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values "
            "('2026-09-15', 'source-b', 'batch-z'), "
            "('2026-09-15', 'source-a', 'batch-z')"
        )
        conn.execute(
            "insert into fact_formal_tyw_balance_daily values "
            "('2026-09-15', 'source-a', 'batch-t')"
        )
        conn.execute(
            "insert into fx_daily_mid values "
            "('2026-09-15', 'fx-a'), ('2026-09-15', 'sv_fx_identity')"
        )
        monkeypatch.setattr(
            BalanceAnalysisRepository,
            "load_zqtz_snapshot_rows",
            lambda _self, _date, ingest_batch_id=None: [
                SimpleNamespace(currency_code="USD")
            ]
            if ingest_batch_id == "batch-z"
            else [],
        )
        monkeypatch.setattr(
            BalanceAnalysisRepository,
            "load_tyw_snapshot_rows",
            lambda _self, _date, ingest_batch_id=None: [
                SimpleNamespace(currency_code="CNY")
            ]
            if ingest_batch_id == "batch-t"
            else [],
        )
        monkeypatch.setattr(
            BalanceAnalysisRepository,
            "lookup_formal_fx_rate",
            lambda _self, *, report_date, base_currency: SimpleNamespace(
                source_version="fx-a" if base_currency == "USD" else "sv_fx_identity"
            ),
        )
        specs = (
            FinancialTablePublicationSpec(
                name="fact_formal_zqtz_balance_daily",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
            FinancialTablePublicationSpec(
                name="fact_formal_tyw_balance_daily",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
            FinancialTablePublicationSpec(
                name="fx_daily_mid",
                date_column="trade_date",
                required_dates=("2026-09-15",),
            ),
        )
        expected = compose_balance_analysis_source_version(
            {"source-a", "source-b"},
            {"fx-a"},
        )
        current = _balance_manifest_matches_current_facts(
            conn,
            manifest={"source_version": expected},
            table_specs=specs,
            report_date="2026-09-15",
        )
        historical = _balance_manifest_matches_current_facts(
            conn,
            manifest={"source_version": "historical"},
            table_specs=specs,
            report_date="2026-09-15",
        )
    finally:
        conn.close()

    assert current is True
    assert historical is False


def test_bond_terminal_source_version_uses_exact_snapshot_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
    from backend.app.tasks.bond_analytics_materialize import _combine_source_versions

    database = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(database))
    rows = [{"source_version": "source-b"}, {"source_version": "source-a"}]
    monkeypatch.setattr(
        BondAnalyticsRepository,
        "load_snapshot_rows",
        lambda _self, report_date: rows if report_date == "2026-09-15" else [],
    )
    specs = tuple(
        FinancialTablePublicationSpec(
            name=name,
            date_column="report_date",
            required_dates=("2026-09-15",),
        )
        for name in (
            "zqtz_bond_daily_snapshot",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_bond_analytics_daily",
        )
    )
    try:
        assert _bond_manifest_matches_current_facts(
            conn,
            manifest={"source_version": _combine_source_versions(rows)},
            table_specs=specs,
            report_date="2026-09-15",
        ) is True
        assert _bond_manifest_matches_current_facts(
            conn,
            manifest={"source_version": "historical"},
            table_specs=specs,
            report_date="2026-09-15",
        ) is False
    finally:
        conn.close()


def test_risk_terminal_versions_match_exact_single_fact_row(tmp_path: Path) -> None:
    database = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(database))
    try:
        conn.execute(
            "create table fact_formal_risk_tensor_daily("
            "report_date date, cache_version varchar, source_version varchar, "
            "rule_version varchar)"
        )
        conn.execute(
            "insert into fact_formal_risk_tensor_daily values "
            "('2026-09-15', 'cache-current', 'source-current', 'rule-current')"
        )
        specs = (
            FinancialTablePublicationSpec(
                name="fact_formal_risk_tensor_daily",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
        )
        assert _risk_manifest_matches_current_facts(
            conn,
            manifest={
                "cache_version": "cache-current",
                "source_version": "source-current",
                "rule_version": "rule-current",
            },
            table_specs=specs,
            report_date="2026-09-15",
        ) is True
        assert _risk_manifest_matches_current_facts(
            conn,
            manifest={
                "cache_version": "cache-current",
                "source_version": "source-historical",
                "rule_version": "rule-current",
            },
            table_specs=specs,
            report_date="2026-09-15",
        ) is False
    finally:
        conn.close()


def test_risk_terminal_without_date_column_cannot_qualify_lineage(tmp_path: Path) -> None:
    conn = duckdb.connect(":memory:")
    try:
        result = _risk_manifest_matches_current_facts(
            conn,
            manifest={
                "cache_version": "cache-current",
                "source_version": "source-current",
                "rule_version": "rule-current",
            },
            table_specs=(FinancialTablePublicationSpec(name="fact_formal_risk_tensor_daily"),),
            report_date="2026-09-15",
        )
        assert result is not True
        assert not (tmp_path / "published" / "CURRENT").exists()
    finally:
        conn.close()


def test_pnl_terminal_source_version_uses_both_exact_fact_partitions(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.pnl_materialize import compose_formal_pnl_source_version

    database = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(database))
    try:
        conn.execute(
            "create table fact_formal_pnl_fi("
            "report_date date, source_version varchar, rule_version varchar)"
        )
        conn.execute(
            "create table fact_nonstd_pnl_bridge("
            "report_date date, source_version varchar, rule_version varchar)"
        )
        conn.execute(
            "insert into fact_formal_pnl_fi values "
            "('2026-09-15', 'source-a', 'rule-current'), "
            "('2026-09-15', 'source-b', 'rule-current')"
        )
        conn.execute(
            "insert into fact_nonstd_pnl_bridge values "
            "('2026-09-15', 'source-c', 'rule-current'), "
            "('2026-09-14', 'historical', 'rule-historical')"
        )
        expected = compose_formal_pnl_source_version(
            [SimpleNamespace(source_version="source-a"), SimpleNamespace(source_version="source-b")],
            [SimpleNamespace(source_version="source-c")],
        )
        specs = (
            FinancialTablePublicationSpec(
                name="fact_formal_pnl_fi",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
        )
        assert _pnl_manifest_matches_current_facts(
            conn,
            manifest={"source_version": expected, "rule_version": "rule-current"},
            table_specs=specs,
            report_date="2026-09-15",
        ) is True
        assert _pnl_manifest_matches_current_facts(
            conn,
            manifest={"source_version": expected, "rule_version": "rule-historical"},
            table_specs=specs,
            report_date="2026-09-15",
        ) is False
    finally:
        conn.close()


def test_accounting_terminal_uses_exact_partition_tokens_and_module_rule_prefix(
    tmp_path: Path,
) -> None:
    from backend.app.tasks.accounting_asset_movement import _rows_source_version

    database = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(database))
    try:
        conn.execute(
            "create table fact_accounting_asset_movement_monthly("
            "report_date date, currency_basis varchar, source_version varchar, "
            "rule_version varchar)"
        )
        conn.execute(
            "insert into fact_accounting_asset_movement_monthly values "
            "('2026-09-15', 'CNX', 'source-b__source-a', 'module-rule__calc-b'), "
            "('2026-09-15', 'CNX', 'source-a', 'module-rule__calc-a')"
        )
        specs = (
            FinancialTablePublicationSpec(
                name="fact_accounting_asset_movement_monthly",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
        )
        expected = _rows_source_version(
            [
                SimpleNamespace(source_version="source-b__source-a"),
                SimpleNamespace(source_version="source-a"),
            ]
        )
        manifest = {
            "source_version": expected,
            "rule_version": "module-rule",
            "lineage": {"currency_basis": "CNX"},
        }
        assert _accounting_asset_movement_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            table_specs=specs,
            report_date="2026-09-15",
        ) is True
        conn.execute(
            "update fact_accounting_asset_movement_monthly "
            "set rule_version = 'wrong-rule' where source_version = 'source-a'"
        )
        assert _accounting_asset_movement_manifest_matches_current_facts(
            conn,
            manifest=manifest,
            table_specs=specs,
            report_date="2026-09-15",
        ) is False
    finally:
        conn.close()


def test_source_preview_terminal_uses_exact_batch_and_authoritative_manifest_order(
    tmp_path: Path,
) -> None:
    archive_b = tmp_path / "b.csv"
    archive_a = tmp_path / "a.csv"
    archive_b.write_text("b\n", encoding="utf-8")
    archive_a.write_text("a\n", encoding="utf-8")
    source_manifests = [
        {
            "status": "completed",
            "ingest_batch_id": "batch-current",
            "source_family": "zqtz",
            "source_file": "b.csv",
            "source_version": "source-b",
            "archived_path": str(archive_b),
        },
        {
            "status": "completed",
            "ingest_batch_id": "batch-current",
            "source_family": "tyw",
            "source_file": "a.csv",
            "source_version": "source-a",
            "archived_path": str(archive_a),
        },
    ]
    database = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(database))
    try:
        conn.execute(
            "create table phase1_source_preview_summary("
            "report_date date, ingest_batch_id varchar, batch_created_at varchar, "
            "source_family varchar, source_file varchar, "
            "source_version varchar, rule_version varchar)"
        )
        conn.execute(
            "insert into phase1_source_preview_summary values "
            "('2026-09-15', 'batch-current', '2026-09-15T01:00:00Z', "
            "'tyw', 'a.csv', 'source-a', 'preview-rule'), "
            "('2026-09-15', 'batch-current', '2026-09-15T01:00:00Z', "
            "'zqtz', 'b.csv', 'source-b', 'preview-rule')"
        )
        specs = (
            FinancialTablePublicationSpec(
                name="phase1_source_preview_summary",
                date_column="report_date",
                required_dates=("2026-09-15",),
            ),
        )
        assert _source_preview_manifest_matches_current_facts(
            conn,
            manifest={
                "source_version": "source-b__source-a",
                "rule_version": "preview-rule",
            },
            terminal_run={"ingest_batch_id": "batch-current"},
            table_specs=specs,
            source_manifest_rows=source_manifests,
            source_preview_archive_root=tmp_path,
        ) is True
        assert _source_preview_manifest_matches_current_facts(
            conn,
            manifest={
                "source_version": "source-a__source-b",
                "rule_version": "preview-rule",
            },
            terminal_run={"ingest_batch_id": "batch-current"},
            table_specs=specs,
            source_manifest_rows=source_manifests,
            source_preview_archive_root=tmp_path,
        ) is False

        old_b = tmp_path / "old-b.csv"
        old_a = tmp_path / "old-a.csv"
        old_b.write_text("old-b\n", encoding="utf-8")
        old_a.write_text("old-a\n", encoding="utf-8")
        historical_manifests = [
            {
                "status": "completed",
                "ingest_batch_id": "batch-old",
                "source_family": "zqtz",
                "source_file": "old-b.csv",
                "source_version": "source-old-b",
                "archived_path": str(old_b),
            },
            {
                "status": "completed",
                "ingest_batch_id": "batch-old",
                "source_family": "tyw",
                "source_file": "old-a.csv",
                "source_version": "source-old-a",
                "archived_path": str(old_a),
            },
            *source_manifests,
        ]
        conn.execute(
            "insert into phase1_source_preview_summary values "
            "('2026-09-14', 'batch-old', '2026-09-14T01:00:00Z', "
            "'zqtz', 'old-b.csv', 'source-old-b', 'preview-rule'), "
            "('2026-09-14', 'batch-old', '2026-09-14T01:00:00Z', "
            "'tyw', 'old-a.csv', 'source-old-a', 'preview-rule')"
        )
        assert _source_preview_manifest_matches_current_facts(
            conn,
            manifest={
                "source_version": "source-old-b__source-old-a",
                "rule_version": "preview-rule",
            },
            terminal_run={"ingest_batch_id": "batch-old"},
            table_specs=specs,
            source_manifest_rows=historical_manifests,
            source_preview_archive_root=tmp_path,
        ) is False
    finally:
        conn.close()


def test_bootstrap_requires_real_timed_ten_step_receipt_and_exact_pnl_result() -> None:
    step_names = (
        "formal_balance",
        "bond_analytics",
        "risk_tensor",
        "formal_pnl",
        "product_category_pnl",
        "accounting_asset_movement",
        "source_preview",
        "verify",
        "pnl_by_business_page_prepare",
        "publish",
    )
    steps = [
        {
            "key": name,
            "status": "completed",
            "started_at": f"start-{index}",
            "finished_at": f"finish-{index}",
            "elapsed_seconds": index + 0.1,
            **(
                {
                    "result": {
                        "status": "completed",
                        "generation": "pnl-generation",
                        "manifest_sha256": "a" * 64,
                    }
                }
                if name == "publish"
                else {}
            ),
        }
        for index, name in enumerate(step_names)
    ]

    assert _bootstrap_persisted_steps({"steps": steps}) == tuple(steps)
    missing_time = [dict(step) for step in steps]
    missing_time[0].pop("started_at")
    with pytest.raises(FinancialPublicationInvalid, match="lacks started_at"):
        _bootstrap_persisted_steps({"steps": missing_time})
    missing_pnl = [dict(step) for step in steps]
    missing_pnl[-1].pop("result")
    with pytest.raises(FinancialPublicationInvalid, match="exact persisted PnL"):
        _bootstrap_persisted_steps({"steps": missing_pnl})


def test_bootstrap_lineage_qualification_fails_when_a_domain_is_ambiguous() -> None:
    cache_keys = (
        "balance_analysis:materialize:formal",
        "bond_analytics:materialize:formal",
        "risk_tensor:materialize:formal",
        "pnl:phase2:materialize:formal",
        "product_category_pnl.formal",
        "accounting_asset_movement.monthly",
        "source_preview.foundation",
    )
    runs = [
        {
            "run_id": f"run-{index}",
            "cache_key": cache_key,
            "status": "completed",
            "report_date": "2026-09-15",
            "source_version": f"source-{index}",
        }
        for index, cache_key in enumerate(cache_keys)
    ]
    manifests = [
        {
            "cache_key": cache_key,
            "source_version": f"source-{index}",
            "report_date": "2026-09-15",
        }
        for index, cache_key in enumerate(cache_keys)
    ]

    class Repo:
        def read_all(self, stream):
            return runs if stream == "cache_build_run" else manifests

    references = _select_bootstrap_lineage_references(
        Repo(),  # type: ignore[arg-type]
        report_date="2026-09-15",
    )
    assert tuple(cache_key for _run_id, cache_key in references) == cache_keys

    runs.append({**runs[0], "run_id": "ambiguous-run"})
    with pytest.raises(FinancialPublicationInvalid, match="uniquely qualify"):
        _select_bootstrap_lineage_references(
            Repo(),  # type: ignore[arg-type]
            report_date="2026-09-15",
        )


def test_data_update_pre_cas_system_publish_failure_never_retries_financial_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {
        "run_id": "data-update-run",
        "workflow": "core_financial",
        "report_date": "2026-09-15",
        "status": "queued",
        "attempt": 0,
    }
    saved: list[dict[str, object]] = []
    execute_calls = 0

    def latest_runs(_governance_path: Path) -> list[dict[str, object]]:
        return [dict(current)]

    def save_run(_governance_path: Path, payload: dict[str, object]) -> None:
        current.clear()
        current.update(payload)
        saved.append(dict(payload))

    def fail_before_cas(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal execute_calls
        execute_calls += 1
        try:
            raise TimeoutError("candidate export timed out before pointer commit")
        except TimeoutError as cause:
            raise GlobalDataRefreshFailed(
                {
                    "status": "failed",
                    "failed_step": "system_read_publish",
                    "steps": [
                        {
                            "name": "system_read_publish",
                            "status": "failed",
                            "error_message": str(cause),
                        }
                    ],
                }
            ) from cause

    monkeypatch.setattr(data_update_center, "latest_runs", latest_runs)
    monkeypatch.setattr(data_update_center, "save_run", save_run)
    monkeypatch.setattr(
        data_update_center,
        "acquire_lock",
        lambda *_args, **_kwargs: nullcontext(),
    )
    monkeypatch.setattr(
        data_update_center,
        "input_preflight",
        lambda *_args, **_kwargs: {"ready": True},
    )
    monkeypatch.setattr(data_update_center, "_execute_core", fail_before_cas)
    monkeypatch.setattr(
        data_update_center,
        "_recover_pending_pnl_by_business_precompute",
        lambda *_args, **_kwargs: 0,
    )

    result = data_update_center._drain_updates_active(
        SimpleNamespace(governance_path=tmp_path)
    )

    assert result == 1
    assert execute_calls == 1
    assert saved[-1]["status"] == "failed"
    assert saved[-1].get("retry_after") is None
    assert saved[-1]["failure_receipt"]["failed_step"] == "system_read_publish"
    assert all(row.get("status") != "retrying" for row in saved)


def test_data_update_post_cas_recovery_only_repairs_metadata_without_financial_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {
        "run_id": "data-update-run",
        "workflow": "core_financial",
        "report_date": "2026-09-15",
        "status": "running",
        "attempt": 1,
        "steps": [{"key": "publish", "status": "completed"}],
    }
    saved: list[dict[str, object]] = []
    execute_calls = 0
    recover_calls = 0

    def latest_runs(_governance_path: Path) -> list[dict[str, object]]:
        return [dict(current)]

    def save_run(_governance_path: Path, payload: dict[str, object]) -> None:
        current.clear()
        current.update(payload)
        saved.append(dict(payload))

    def forbidden_execute(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal execute_calls
        execute_calls += 1
        raise AssertionError("financial chain must not replay after a committed CAS")

    def recover_committed(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal recover_calls
        recover_calls += 1
        return {
            "generation": "system-read-2026-09-15-0123456789abcdef0123",
            "manifest_sha256": "b" * 64,
            "global_run_id": "global-run",
        }

    monkeypatch.setattr(data_update_center, "latest_runs", latest_runs)
    monkeypatch.setattr(data_update_center, "save_run", save_run)
    monkeypatch.setattr(
        data_update_center,
        "acquire_lock",
        lambda *_args, **_kwargs: nullcontext(),
    )
    monkeypatch.setattr(data_update_center, "_execute_core", forbidden_execute)
    monkeypatch.setattr(
        data_update_center,
        "_recover_pending_pnl_by_business_precompute",
        lambda *_args, **_kwargs: 0,
    )
    monkeypatch.setattr(
        system_read_publication,
        "recover_committed_system_read_publication",
        recover_committed,
    )

    result = data_update_center._drain_updates_active(
        SimpleNamespace(governance_path=tmp_path)
    )

    assert result == 0
    assert recover_calls == 1
    assert execute_calls == 0
    assert saved[-1]["status"] == "completed"
    assert saved[-1]["global_run_id"] == "global-run"
    recovered_step = next(
        step
        for step in saved[-1]["steps"]
        if step["key"] == "system_read_publish"
    )
    assert recovered_step["status"] == "completed"
    assert recovered_step["result"]["generation"].startswith("system-read-")


@pytest.mark.parametrize("publication_enabled", [False, True])
def test_balance_only_update_honors_publication_flag_and_preserves_writer_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    publication_enabled: bool,
) -> None:
    current = {
        "run_id": "balance-run",
        "workflow": "balance_daily",
        "report_date": "2026-09-15",
        "status": "queued",
        "attempt": 0,
    }
    saved: list[dict[str, object]] = []
    publish_calls: list[dict[str, object]] = []

    def latest_runs(_governance_path: Path) -> list[dict[str, object]]:
        return [dict(current)]

    def save_run(_governance_path: Path, payload: dict[str, object]) -> None:
        current.clear()
        current.update(payload)
        saved.append(dict(payload))

    monkeypatch.setattr(data_update_center, "latest_runs", latest_runs)
    monkeypatch.setattr(data_update_center, "save_run", save_run)
    monkeypatch.setattr(
        data_update_center,
        "acquire_lock",
        lambda *_args, **_kwargs: nullcontext(),
    )
    monkeypatch.setattr(
        data_update_center,
        "input_preflight",
        lambda *_args, **_kwargs: {"ready": True},
    )
    monkeypatch.setattr(
        data_update_center,
        "_execute_balance",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "report_date": "2026-09-15",
            "pipeline": {
                "status": "completed",
                "balance": {"run_id": "balance-child"},
                "bond_analytics": {"run_id": "bond-child"},
                "risk_tensor": {"run_id": "risk-child"},
            },
        },
    )
    monkeypatch.setattr(
        system_read_publication,
        "publish_qualified_balance_daily_system_read_generation",
        lambda _settings, **kwargs: (
            publish_calls.append(kwargs)
            or SimpleNamespace(
                generation="system-read-2026-09-15-0123456789abcdef0123",
                manifest_sha256="b" * 64,
            )
        ),
    )
    monkeypatch.setattr(
        data_update_center,
        "_recover_pending_pnl_by_business_precompute",
        lambda *_args, **_kwargs: 0,
    )

    result = data_update_center._drain_updates_active(
        SimpleNamespace(
            governance_path=tmp_path,
            system_read_publication_enabled=publication_enabled,
        )
    )

    assert result == 0
    assert saved[-1]["status"] == "completed"
    if not publication_enabled:
        assert publish_calls == []
        assert "system_read_publication" not in saved[-1]
        return
    assert len(publish_calls) == 1
    assert publish_calls[0]["data_update_run_id"] == "balance-run"
    assert publish_calls[0]["writer_receipt"] == {
        "status": "completed",
        "run_id": "balance-run",
        "workflow": "balance_daily",
        "report_date": "2026-09-15",
        "pipeline": {
            "status": "completed",
            "balance": {"run_id": "balance-child"},
            "bond_analytics": {"run_id": "bond-child"},
            "risk_tensor": {"run_id": "risk-child"},
        },
    }
    assert saved[-1]["system_read_publication"]["writer_run_id"] == "balance-run"
    assert saved[-1]["steps"][-1]["key"] == "system_read_publish"
    assert saved[-1]["steps"][-1]["status"] == "completed"


def test_balance_publication_failure_is_terminal_without_business_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {
        "run_id": "balance-run",
        "workflow": "balance_daily",
        "report_date": "2026-09-15",
        "status": "queued",
        "attempt": 0,
    }
    saved: list[dict[str, object]] = []
    execute_calls = 0

    def latest_runs(_governance_path: Path) -> list[dict[str, object]]:
        return [dict(current)]

    def save_run(_governance_path: Path, payload: dict[str, object]) -> None:
        current.clear()
        current.update(payload)
        saved.append(dict(payload))

    def execute(*_args, **_kwargs) -> dict[str, object]:
        nonlocal execute_calls
        execute_calls += 1
        return {
            "status": "completed",
            "report_date": "2026-09-15",
            "pipeline": {"status": "completed"},
        }

    monkeypatch.setattr(data_update_center, "latest_runs", latest_runs)
    monkeypatch.setattr(data_update_center, "save_run", save_run)
    monkeypatch.setattr(data_update_center, "acquire_lock", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(data_update_center, "input_preflight", lambda *_args, **_kwargs: {"ready": True})
    monkeypatch.setattr(data_update_center, "_execute_balance", execute)
    monkeypatch.setattr(
        system_read_publication,
        "publish_qualified_balance_daily_system_read_generation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("publisher lock")),
    )
    monkeypatch.setattr(
        data_update_center,
        "_recover_pending_pnl_by_business_precompute",
        lambda *_args, **_kwargs: 0,
    )

    assert data_update_center._drain_updates_active(
        SimpleNamespace(governance_path=tmp_path, system_read_publication_enabled=True)
    ) == 1
    assert execute_calls == 1
    assert saved[-1]["status"] == "failed"
    assert saved[-1].get("retry_after") is None
    assert saved[-1]["failure_receipt"]["failed_step"] == "system_read_publish"
    assert saved[-1]["steps"][-1]["key"] == "system_read_publish"
    assert saved[-1]["steps"][-1]["status"] == "failed"


@pytest.mark.parametrize(
    ("column_type", "value"),
    [
        ("date", "2026-09-16"),
        ("varchar", "2026-09-16"),
        ("timestamp", "2026-09-16T08:30:00"),
    ],
)
def test_financial_table_coverage_accepts_date_string_and_timestamp_columns(
    tmp_path: Path,
    column_type: str,
    value: str,
) -> None:
    source = tmp_path / f"coverage-{column_type}.duckdb"
    with duckdb.connect(str(source)) as conn:
        conn.execute(f"create table event(received_at {column_type}, value integer)")
        conn.execute("insert into event values (?, 1)", [value])
        result = _validate_table_coverage(
            conn,
            spec=FinancialTablePublicationSpec(
                name="event",
                date_column="received_at",
                required_dates=("2026-09-16",),
            ),
            catalog="main",
        )

    assert result["coverage_row_counts"] == {"2026-09-16": 1}


def test_market_preserved_publication_requires_under_lock_source_validator() -> None:
    with pytest.raises(FinancialPublicationInvalid, match="under-lock"):
        publish_preserved_system_read_generation(
            SimpleNamespace(),
            writer_run_id="market-aggregate-run",
            workflow="market_daily",
            report_date="2026-09-16",
            writer_receipt={
                "status": "completed",
                "run_id": "market-aggregate-run",
                "workflow": "market_daily",
                "report_date": "2026-09-16",
            },
            changed_table_coverage=(
                ("choice_news_event", "received_at", "2026-09-16", 1),
            ),
        )


def test_balance_publication_uses_exact_four_changed_terminals_and_daily_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def publish_preserved(_settings, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status="completed")

    monkeypatch.setattr(
        system_read_publication,
        "publish_preserved_system_read_generation",
        publish_preserved,
    )
    writer_receipt = {
        "status": "completed",
        "run_id": "balance-parent",
        "workflow": "balance_daily",
        "report_date": "2026-09-16",
        "pipeline": {
            "balance_runtime": {
                "run": {"run_id": "balance-child"},
                "lineage": {"cache_key": "balance_analysis:materialize:formal"},
            },
            "bond_analytics": {
                "run_id": "bond-child",
                "cache_key": "bond_analytics:materialize:formal",
            },
            "risk_tensor": {
                "run_id": "risk-child",
                "cache_key": "risk_tensor:materialize:formal",
            },
            "source_preview": {
                "run_id": "preview-child",
                "cache_key": "source_preview.foundation",
                "report_dates": ["2026-09-16"],
            },
        },
    }

    result = publish_qualified_balance_daily_system_read_generation(
        SimpleNamespace(),
        data_update_run_id="balance-parent",
        report_date="2026-09-16",
        writer_receipt=writer_receipt,
    )

    assert result.status == "completed"
    assert captured["data_update_run_id"] == "balance-parent"
    assert set(captured["changed_terminal_references"]) == {
        (
            "balance-child",
            "balance_analysis:materialize:formal",
            "2026-09-16",
        ),
        ("bond-child", "bond_analytics:materialize:formal", "2026-09-16"),
        ("risk-child", "risk_tensor:materialize:formal", "2026-09-16"),
        ("preview-child", "source_preview.foundation", "2026-09-16"),
    }
    assert (
        "phase1_source_preview_summary",
        "report_date",
        "2026-09-16",
        1,
    ) in captured["changed_table_coverage"]


def test_balance_publication_keeps_source_preview_actual_date_for_historical_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        system_read_publication,
        "publish_preserved_system_read_generation",
        lambda _settings, **kwargs: captured.update(kwargs)
        or SimpleNamespace(status="completed"),
    )
    writer_receipt = {
        "status": "completed",
        "run_id": "balance-parent",
        "workflow": "balance_daily",
        "report_date": "2026-09-16",
        "pipeline": {
            "balance": {
                "run_id": "balance-child",
                "cache_key": "balance_analysis:materialize:formal",
            },
            "bond_analytics": {
                "run_id": "bond-child",
                "cache_key": "bond_analytics:materialize:formal",
            },
            "risk_tensor": {
                "run_id": "risk-child",
                "cache_key": "risk_tensor:materialize:formal",
            },
            "source_preview": {
                "status": "completed",
                "run_id": "preview-child",
                "cache_key": "source_preview.foundation",
                "report_dates": ["2026-09-20", "2026-08-31"],
            },
        },
    }

    publish_qualified_balance_daily_system_read_generation(
        SimpleNamespace(),
        data_update_run_id="balance-parent",
        report_date="2026-09-16",
        writer_receipt=writer_receipt,
    )

    assert (
        "phase1_source_preview_summary",
        "report_date",
        "2026-09-20",
        1,
    ) in captured["changed_table_coverage"]
    assert (
        "preview-child",
        "source_preview.foundation",
        "2026-09-20",
    ) in captured["changed_terminal_references"]


def test_preserved_publication_keeps_mixed_domain_dates_and_old_generation_immutable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_bootstrap_to_real_source_preview_predicate(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(tmp_path)
    first = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )
    old_database = first.database_path
    old_manifest = first.manifest_path
    old_bytes = (old_database.read_bytes(), old_manifest.read_bytes())
    source = Path(settings.duckdb_path)
    with duckdb.connect(str(source)) as conn:
        conn.execute(
            "create table choice_news_event(received_at timestamp, headline varchar)"
        )
        conn.execute(
            "insert into choice_news_event values "
            "('2026-09-16 08:30:00', 'qualified market receipt')"
        )
    source_before = (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    validator_databases: list[str] = []

    def validate_changed_source(conn: duckdb.DuckDBPyConnection) -> dict[str, str]:
        validator_databases.append(
            str(conn.execute("select current_database()").fetchone()[0])
        )
        return {
            "source_cut_sha256": hashlib.sha256(
                str(
                    conn.execute(
                        "select count(*), max(received_at) from choice_news_event"
                    ).fetchone()
                ).encode()
            ).hexdigest(),
            "external_receipts_sha256": "a" * 64,
        }

    publication = publish_preserved_system_read_generation(
        settings,
        writer_run_id="market-aggregate-run",
        workflow="market_daily",
        report_date="2026-09-16",
        writer_receipt={
            "status": "completed",
            "run_id": "market-aggregate-run",
            "workflow": "market_daily",
            "report_date": "2026-09-16",
            "latest_received_at": "2026-09-16T08:30:00Z",
        },
        changed_table_coverage=(
            ("choice_news_event", "received_at", "2026-09-16", 1),
        ),
        changed_source_validator=validate_changed_source,
        pretrade_availability=unavailable_pretrade_qualification(
            "shared_publisher_unit_test_has_no_pretrade_producer"
        ),
    )

    resolved = resolve_system_read_publication(settings, publication.generation)
    sealed_payload = resolved.manifest["sealed_payload"]
    assert sealed_payload["coverage_dates"] == {
        "choice_news_event": ["2026-09-16"],
        "fact_result": ["2026-09-15"],
        "phase1_source_preview_summary": ["2026-09-15"],
    }
    bundle = sealed_payload["system_read_bundle"]
    assert bundle["writer_run_id"] == "market-aggregate-run"
    assert bundle["data_update_run_id"] is None
    assert bundle["global_run_id"] is None
    assert next(
        row["report_date"]
        for row in bundle["terminal_references"]
        if row["cache_key"] == "pnl:phase2:materialize:formal"
    ) == "2026-09-15"
    assert old_database.read_bytes() == old_bytes[0]
    assert old_manifest.read_bytes() == old_bytes[1]
    assert len(validator_databases) >= 2
    assert (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    ) == source_before
    recovered = recover_committed_system_read_publication(
        settings,
        writer_run_id="market-aggregate-run",
        report_date="2026-09-16",
        workflow="market_daily",
    )
    assert recovered is not None
    assert recovered["writer_run_id"] == "market-aggregate-run"
    assert "data_update_run_id" not in recovered
    assert "global_run_id" not in recovered
    assert resolve_system_read_publication(settings).generation == publication.generation

    pointer_before_preserved_change = read_publication_pointer(
        system_read_publication_root(settings), require_valid=True
    )
    with duckdb.connect(str(source)) as conn:
        conn.execute(
            "update fact_result set value = 12 where report_date = '2026-09-15'"
        )
    with pytest.raises(
        FinancialPublicationInvalid,
        match="Preserved sealed source cut changed for 'fact_result'",
    ):
        publish_preserved_system_read_generation(
            settings,
            writer_run_id="market-aggregate-run-after-preserved-change",
            workflow="market_daily",
            report_date="2026-09-16",
            writer_receipt={
                "status": "completed",
                "run_id": "market-aggregate-run-after-preserved-change",
                "workflow": "market_daily",
                "report_date": "2026-09-16",
            },
            changed_table_coverage=(
                ("choice_news_event", "received_at", "2026-09-16", 1),
            ),
            changed_source_validator=validate_changed_source,
            pretrade_availability=unavailable_pretrade_qualification(
                "shared_publisher_unit_test_has_no_pretrade_producer"
            ),
        )
    assert read_publication_pointer(
        system_read_publication_root(settings), require_valid=True
    ) == pointer_before_preserved_change


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_source_preview
def test_preserved_publication_rejects_new_balance_manifests_until_preview_is_refreshed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_bootstrap_to_real_source_preview_predicate(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(
        tmp_path,
        source_preview_terminal_mode="duplicate_empty",
    )
    first = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )
    source = Path(settings.duckdb_path)
    with duckdb.connect(str(source)) as conn:
        conn.execute("create table market_event(report_date date, value integer)")
        conn.execute("insert into market_event values ('2026-09-16', 1)")
    archive_root = Path(settings.local_archive_path)
    repo = GovernanceRepository(base_dir=settings.governance_path, backend_mode="jsonl")
    rows = []
    for family, fixture_name, source_file in (
        ("zqtz", "ZQTZSHOW-20251231.xls", "ZQTZSHOW-20260916.xls"),
        ("tyw", "TYWLSHOW-20251231.xls", "TYWLSHOW-20260916.xls"),
    ):
        archived = archive_root / source_file
        archived.write_bytes((ROOT / "data_input" / fixture_name).read_bytes())
        rows.append(
            (
                SOURCE_MANIFEST_STREAM,
                {
                    "status": "completed",
                    "ingest_batch_id": "balance-batch-new",
                    "source_family": family,
                    "source_file": source_file,
                    "source_version": f"{family}-source-new",
                    "report_date": "2026-09-16",
                    "created_at": "2026-09-16T01:00:00Z",
                    "archived_path": str(archived),
                },
            )
        )
    repo.append_many_atomic(rows)
    pointer_before = read_publication_pointer(
        system_read_publication_root(settings), require_valid=True
    )
    source_before = (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )

    with pytest.raises(FinancialPublicationInvalid, match="source version"):
        publish_preserved_system_read_generation(
            settings,
            writer_run_id="market-aggregate-run",
            workflow="market_daily",
            report_date="2026-09-16",
            writer_receipt={
                "status": "completed",
                "run_id": "market-aggregate-run",
                "workflow": "market_daily",
                "report_date": "2026-09-16",
            },
            changed_table_coverage=(
                ("market_event", "report_date", "2026-09-16", 1),
            ),
            changed_source_validator=lambda conn: {
                "source_cut_sha256": hashlib.sha256(
                    str(conn.execute("select * from market_event").fetchall()).encode()
                ).hexdigest(),
                    "external_receipts_sha256": "a" * 64,
                },
                pretrade_availability=unavailable_pretrade_qualification(
                    "shared_publisher_unit_test_has_no_pretrade_producer"
                ),
        )

    assert read_publication_pointer(
        system_read_publication_root(settings), require_valid=True
    ) == pointer_before
    assert resolve_system_read_publication(settings).generation == first.generation
    assert (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        hashlib.sha256(source.read_bytes()).hexdigest(),
    ) == source_before

    import backend.app.tasks.source_preview_refresh as preview_refresh

    monkeypatch.setattr(preview_refresh, "get_settings", lambda: settings)
    with duckdb.connect(str(source)) as conn:
        conn.execute("drop table phase1_source_preview_summary")
    preview_result = preview_refresh._refresh_source_preview_cache(
        duckdb_path=str(source),
        governance_dir=str(settings.governance_path),
        data_root=str(tmp_path / "unused-input"),
        from_existing_manifests=True,
    )
    assert preview_result["status"] == "completed"
    assert preview_result["refresh_mode"] == "existing_manifests"
    publication = publish_preserved_system_read_generation(
        settings,
        writer_run_id="market-aggregate-run",
        workflow="market_daily",
        report_date="2026-09-16",
        writer_receipt={
            "status": "completed",
            "run_id": "market-aggregate-run",
            "workflow": "market_daily",
            "report_date": "2026-09-16",
        },
        changed_table_coverage=(
            ("market_event", "report_date", "2026-09-16", 1),
            ("phase1_source_preview_summary", "report_date", "2026-09-16", 2),
        ),
        changed_terminal_references=(
            (
                str(preview_result["run_id"]),
                "source_preview.foundation",
                "2026-09-16",
            ),
        ),
        changed_source_validator=lambda conn: {
            "source_cut_sha256": hashlib.sha256(
                str(
                    (
                        conn.execute("select * from market_event").fetchall(),
                        conn.execute(
                            "select source_family, source_version "
                            "from phase1_source_preview_summary order by 1"
                        ).fetchall(),
                    )
                ).encode()
            ).hexdigest(),
                "external_receipts_sha256": "a" * 64,
            },
            pretrade_availability=unavailable_pretrade_qualification(
                "shared_publisher_unit_test_has_no_pretrade_producer"
            ),
        )
    assert publication.generation != first.generation


def test_preserved_publication_rejects_changed_writer_cut_after_full_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication.require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_bootstrap_to_real_source_preview_predicate(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(tmp_path)
    first = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )
    source = Path(settings.duckdb_path)
    with duckdb.connect(str(source)) as conn:
        conn.execute("create table market_event(report_date date, value integer)")
        conn.execute("insert into market_event values ('2026-09-16', 1)")
    pointer_before = read_publication_pointer(
        system_read_publication_root(settings), require_valid=True
    )
    calls = 0
    external_receipt_hash = "a" * 64

    def changing_validator(conn: duckdb.DuckDBPyConnection) -> dict[str, str]:
        nonlocal calls, external_receipt_hash
        calls += 1
        result = {
            "source_cut_sha256": hashlib.sha256(
                str(conn.execute("select * from market_event").fetchall()).encode()
            ).hexdigest(),
            "external_receipts_sha256": external_receipt_hash,
        }
        if calls == 2:
            external_receipt_hash = "b" * 64
        return result

    with pytest.raises(FinancialPublicationInvalid, match="Writer-qualified source cut changed"):
        publish_preserved_system_read_generation(
            settings,
            writer_run_id="market-aggregate-run",
            workflow="market_daily",
            report_date="2026-09-16",
            writer_receipt={
                "status": "completed",
                "run_id": "market-aggregate-run",
                "workflow": "market_daily",
                "report_date": "2026-09-16",
            },
            changed_table_coverage=(
                ("market_event", "report_date", "2026-09-16", 1),
            ),
            changed_source_validator=changing_validator,
            pretrade_availability=unavailable_pretrade_qualification(
                "shared_publisher_unit_test_has_no_pretrade_producer"
            ),
        )

    assert calls == 3
    assert read_publication_pointer(
        system_read_publication_root(settings), require_valid=True
    ) == pointer_before
    assert resolve_system_read_publication(settings).generation == first.generation
