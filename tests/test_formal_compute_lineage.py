from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from tests.helpers import load_module


def _load_lineage_module():
    return load_module(
        "backend.app.governance.formal_compute_lineage",
        "backend/app/governance/formal_compute_lineage.py",
    )


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _governance_repo(tmp_path: Path, *, backend_mode: str = "jsonl"):
    governance_mod = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    sql_dsn = ""
    if backend_mode != "jsonl":
        sql_dsn = f"sqlite:///{tmp_path / 'governance.sqlite'}"
    repo = governance_mod.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=sql_dsn,
        backend_mode=backend_mode,
    )
    return governance_mod, repo, sql_dsn


def test_resolve_formal_manifest_lineage_returns_latest_matching_record(tmp_path):
    lineage_mod = _load_lineage_module()
    manifest_path = tmp_path / "cache_manifest.jsonl"
    _append_jsonl(
        manifest_path,
        {
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_old",
            "source_version": "sv_old",
            "vendor_version": "vv_none",
            "rule_version": "rv_old",
        },
    )
    _append_jsonl(
        manifest_path,
        {
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_new",
            "source_version": "sv_new",
            "vendor_version": "vv_choice",
            "rule_version": "rv_new",
        },
    )

    latest = lineage_mod.resolve_formal_manifest_lineage(
        governance_dir=str(tmp_path),
        cache_key="mock_standard:materialize:formal",
    )

    assert latest["cache_version"] == "cv_new"
    assert latest["source_version"] == "sv_new"
    assert latest["vendor_version"] == "vv_choice"
    assert latest["rule_version"] == "rv_new"


def test_resolve_formal_manifest_lineage_fails_closed_when_required_fields_missing(tmp_path):
    lineage_mod = _load_lineage_module()
    _append_jsonl(
        tmp_path / "cache_manifest.jsonl",
        {
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_new",
            "source_version": "sv_new",
            "vendor_version": "",
            "rule_version": "rv_new",
        },
    )

    with pytest.raises(RuntimeError, match="missing vendor_version"):
        lineage_mod.resolve_formal_manifest_lineage(
            governance_dir=str(tmp_path),
            cache_key="mock_standard:materialize:formal",
        )


def test_resolve_completed_formal_build_lineage_returns_latest_completed_row_for_report_date(tmp_path):
    lineage_mod = _load_lineage_module()
    build_run_path = tmp_path / "cache_build_run.jsonl"
    _append_jsonl(
        build_run_path,
        {
            "run_id": "run-1",
            "job_name": "mock_standard_materialize",
            "status": "completed",
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_old",
            "source_version": "sv_old",
            "vendor_version": "vv_none",
            "rule_version": "rv_old",
            "report_date": "2025-12-31",
        },
    )
    _append_jsonl(
        build_run_path,
        {
            "run_id": "run-2",
            "job_name": "mock_standard_materialize",
            "status": "completed",
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_new",
            "source_version": "sv_new",
            "vendor_version": "vv_choice",
            "rule_version": "rv_new",
            "report_date": "2025-12-31",
        },
    )
    _append_jsonl(
        build_run_path,
        {
            "run_id": "run-3",
            "job_name": "mock_standard_materialize",
            "status": "running",
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_running",
            "source_version": "sv_running",
            "vendor_version": "vv_none",
            "rule_version": "rv_new",
            "report_date": "2025-12-31",
        },
    )

    latest = lineage_mod.resolve_completed_formal_build_lineage(
        governance_dir=str(tmp_path),
        cache_key="mock_standard:materialize:formal",
        job_name="mock_standard_materialize",
        report_date="2025-12-31",
    )

    assert latest is not None
    assert latest["run_id"] == "run-2"
    assert latest["cache_version"] == "cv_new"
    assert latest["source_version"] == "sv_new"


def test_resolve_completed_formal_build_lineage_ignores_other_jobs_and_empty_source_versions(tmp_path):
    lineage_mod = _load_lineage_module()
    build_run_path = tmp_path / "cache_build_run.jsonl"
    _append_jsonl(
        build_run_path,
        {
            "run_id": "run-1",
            "job_name": "other_job",
            "status": "completed",
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_other",
            "source_version": "sv_other",
            "vendor_version": "vv_none",
            "rule_version": "rv_other",
            "report_date": "2025-12-31",
        },
    )
    _append_jsonl(
        build_run_path,
        {
            "run_id": "run-2",
            "job_name": "mock_standard_materialize",
            "status": "completed",
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_bad",
            "source_version": "",
            "vendor_version": "vv_none",
            "rule_version": "rv_bad",
            "report_date": "2025-12-31",
        },
    )

    latest = lineage_mod.resolve_completed_formal_build_lineage(
        governance_dir=str(tmp_path),
        cache_key="mock_standard:materialize:formal",
        job_name="mock_standard_materialize",
        report_date="2025-12-31",
    )

    assert latest is None


def test_resolve_completed_formal_build_lineage_skips_newer_invalid_completed_row_and_keeps_latest_valid(tmp_path):
    lineage_mod = _load_lineage_module()
    build_run_path = tmp_path / "cache_build_run.jsonl"
    _append_jsonl(
        build_run_path,
        {
            "run_id": "run-valid",
            "job_name": "mock_standard_materialize",
            "status": "completed",
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_valid",
            "source_version": "sv_valid",
            "vendor_version": "vv_valid",
            "rule_version": "rv_valid",
            "report_date": "2025-12-31",
        },
    )
    _append_jsonl(
        build_run_path,
        {
            "run_id": "run-invalid-newer",
            "job_name": "mock_standard_materialize",
            "status": "completed",
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_invalid",
            "source_version": "",
            "vendor_version": "vv_invalid",
            "rule_version": "rv_invalid",
            "report_date": "2025-12-31",
        },
    )

    latest = lineage_mod.resolve_completed_formal_build_lineage(
        governance_dir=str(tmp_path),
        cache_key="mock_standard:materialize:formal",
        job_name="mock_standard_materialize",
        report_date="2025-12-31",
    )

    assert latest is not None
    assert latest["run_id"] == "run-valid"
    assert latest["source_version"] == "sv_valid"


def test_resolve_formal_manifest_lineage_ignores_snapshot_and_preview_streams(tmp_path):
    lineage_mod = _load_lineage_module()
    _append_jsonl(
        tmp_path / "snapshot_manifest.jsonl",
        {
            "cache_key": "mock_standard:materialize:formal",
            "source_version": "sv_snapshot",
            "vendor_version": "vv_snapshot",
            "rule_version": "rv_snapshot",
        },
    )
    _append_jsonl(
        tmp_path / "source_manifest.jsonl",
        {
            "cache_key": "mock_standard:materialize:formal",
            "source_version": "sv_preview",
            "vendor_version": "vv_preview",
            "rule_version": "rv_preview",
        },
    )

    with pytest.raises(RuntimeError, match="Canonical formal lineage unavailable"):
        lineage_mod.resolve_formal_manifest_lineage(
            governance_dir=str(tmp_path),
            cache_key="mock_standard:materialize:formal",
        )


def test_resolve_completed_formal_build_lineage_ignores_snapshot_style_build_records(tmp_path):
    lineage_mod = _load_lineage_module()
    _append_jsonl(
        tmp_path / "snapshot_build_run.jsonl",
        {
            "run_id": "snapshot-run-1",
            "job_name": "snapshot_materialize",
            "status": "completed",
            "cache_key": "mock_standard:materialize:formal",
            "source_version": "sv_snapshot",
            "report_date": "2025-12-31",
        },
    )

    latest = lineage_mod.resolve_completed_formal_build_lineage(
        governance_dir=str(tmp_path),
        cache_key="mock_standard:materialize:formal",
        job_name="mock_standard_materialize",
        report_date="2025-12-31",
    )

    assert latest is None


def test_resolve_formal_manifest_lineage_supports_sql_authority_governance(tmp_path):
    lineage_mod = _load_lineage_module()
    governance_mod, repo, sql_dsn = _governance_repo(tmp_path, backend_mode="sql-authority")
    repo.append(
        governance_mod.CACHE_MANIFEST_STREAM,
        {
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_sql",
            "source_version": "sv_sql",
            "vendor_version": "vv_sql",
            "rule_version": "rv_sql",
            "created_at": "2026-04-12T12:00:00+00:00",
        },
    )

    latest = lineage_mod.resolve_formal_manifest_lineage(
        governance_dir=str(tmp_path),
        cache_key="mock_standard:materialize:formal",
        sql_dsn=sql_dsn,
        backend_mode="sql-authority",
    )

    assert latest["cache_version"] == "cv_sql"
    assert latest["source_version"] == "sv_sql"
    assert latest["vendor_version"] == "vv_sql"
    assert latest["rule_version"] == "rv_sql"


def test_resolve_completed_formal_build_lineage_supports_sql_authority_governance(tmp_path):
    lineage_mod = _load_lineage_module()
    governance_mod, repo, sql_dsn = _governance_repo(tmp_path, backend_mode="sql-authority")
    repo.append(
        governance_mod.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-sql-1",
            "job_name": "mock_standard_materialize",
            "status": "completed",
            "cache_key": "mock_standard:materialize:formal",
            "cache_version": "cv_sql",
            "lock": "lock:duckdb:formal:mock-standard:materialize",
            "source_version": "sv_sql",
            "vendor_version": "vv_sql",
            "rule_version": "rv_sql",
            "report_date": "2025-12-31",
            "created_at": "2026-04-12T12:00:00+00:00",
        },
    )

    latest = lineage_mod.resolve_completed_formal_build_lineage(
        governance_dir=str(tmp_path),
        cache_key="mock_standard:materialize:formal",
        job_name="mock_standard_materialize",
        report_date="2025-12-31",
        sql_dsn=sql_dsn,
        backend_mode="sql-authority",
    )

    assert latest is not None
    assert latest["run_id"] == "run-sql-1"
    assert latest["source_version"] == "sv_sql"
    assert latest["rule_version"] == "rv_sql"


def test_resolve_formal_facts_lineage_prefers_build_then_rows_then_manifest(tmp_path):
    lineage_mod = _load_lineage_module()
    _append_jsonl(
        tmp_path / "cache_build_run.jsonl",
        {
            "run_id": "run-1",
            "job_name": "bond_analytics_materialize",
            "status": "completed",
            "cache_key": "bond_analytics:materialize:formal",
            "cache_version": "cv_build",
            "source_version": "",
            "vendor_version": "vv_build",
            "rule_version": "rv_build",
            "report_date": "2026-03-31",
        },
    )
    _append_jsonl(
        tmp_path / "cache_manifest.jsonl",
        {
            "cache_key": "bond_analytics:materialize:formal",
            "cache_version": "cv_manifest",
            "source_version": "sv_manifest",
            "vendor_version": "vv_manifest",
            "rule_version": "rv_manifest",
        },
    )

    lineage = lineage_mod.resolve_formal_facts_lineage(
        governance_dir=str(tmp_path),
        cache_key="bond_analytics:materialize:formal",
        job_name="bond_analytics_materialize",
        report_date="2026-03-31",
        has_rows=True,
        row_source_versions=["sv_row_b", "sv_row_a", ""],
        default_source_version="sv_empty",
        default_rule_version="rv_default",
        default_cache_version="cv_default",
    )

    assert lineage == {
        "source_version": "sv_row_a__sv_row_b",
        "rule_version": "rv_build",
        "cache_version": "cv_build",
        "vendor_version": "vv_build",
    }


def test_resolve_formal_facts_lineage_returns_defaults_when_no_rows_or_build_exist(tmp_path):
    lineage_mod = _load_lineage_module()

    lineage = lineage_mod.resolve_formal_facts_lineage(
        governance_dir=str(tmp_path),
        cache_key="bond_analytics:materialize:formal",
        job_name="bond_analytics_materialize",
        report_date="2026-03-31",
        has_rows=False,
        row_source_versions=[],
        default_source_version="sv_empty",
        default_rule_version="rv_default",
        default_cache_version="cv_default",
    )

    assert lineage == {
        "source_version": "sv_empty",
        "rule_version": "rv_default",
        "cache_version": "cv_default",
        "vendor_version": "vv_none",
    }


def test_resolve_formal_facts_lineage_keeps_manifest_fallback_when_rows_exist_without_source_versions(tmp_path):
    lineage_mod = _load_lineage_module()
    _append_jsonl(
        tmp_path / "cache_manifest.jsonl",
        {
            "cache_key": "bond_analytics:materialize:formal",
            "cache_version": "cv_manifest",
            "source_version": "sv_manifest",
            "vendor_version": "vv_manifest",
            "rule_version": "rv_manifest",
        },
    )

    lineage = lineage_mod.resolve_formal_facts_lineage(
        governance_dir=str(tmp_path),
        cache_key="bond_analytics:materialize:formal",
        job_name="bond_analytics_materialize",
        report_date="2026-03-31",
        has_rows=True,
        row_source_versions=["", ""],
        default_source_version="sv_empty",
        default_rule_version="rv_default",
        default_cache_version="cv_default",
    )

    assert lineage == {
        "source_version": "sv_empty",
        "rule_version": "rv_manifest",
        "cache_version": "cv_manifest",
        "vendor_version": "vv_manifest",
    }


def test_resolve_formal_dates_lineage_uses_manifest_then_fallback_then_defaults(tmp_path):
    lineage_mod = _load_lineage_module()
    _append_jsonl(
        tmp_path / "cache_manifest.jsonl",
        {
            "cache_key": "bond_analytics:materialize:formal",
            "cache_version": "cv_manifest",
            "source_version": "sv_manifest",
            "vendor_version": "vv_manifest",
            "rule_version": "rv_manifest",
        },
    )

    manifest_lineage = lineage_mod.resolve_formal_dates_lineage(
        governance_dir=str(tmp_path),
        cache_key="bond_analytics:materialize:formal",
        report_dates=["2026-03-31"],
        default_source_version="sv_empty",
        default_rule_version="rv_default",
        default_cache_version="cv_default",
        fallback_lineage_loader=lambda _report_date: {
            "source_version": "sv_fallback",
            "rule_version": "rv_fallback",
            "cache_version": "cv_fallback",
            "vendor_version": "vv_fallback",
        },
    )

    assert manifest_lineage == {
        "source_version": "sv_manifest",
        "rule_version": "rv_manifest",
        "cache_version": "cv_manifest",
        "vendor_version": "vv_manifest",
    }

    fallback_lineage = lineage_mod.resolve_formal_dates_lineage(
        governance_dir=str(tmp_path / "missing"),
        cache_key="bond_analytics:materialize:formal",
        report_dates=["2026-03-31"],
        default_source_version="sv_empty",
        default_rule_version="rv_default",
        default_cache_version="cv_default",
        fallback_lineage_loader=lambda _report_date: {
            "source_version": "sv_fallback",
            "rule_version": "rv_fallback",
            "cache_version": "cv_fallback",
            "vendor_version": "vv_fallback",
        },
    )

    assert fallback_lineage == {
        "source_version": "sv_fallback",
        "rule_version": "rv_fallback",
        "cache_version": "cv_fallback",
        "vendor_version": "vv_fallback",
    }

    default_lineage = lineage_mod.resolve_formal_dates_lineage(
        governance_dir=str(tmp_path / "missing-default"),
        cache_key="bond_analytics:materialize:formal",
        report_dates=[],
        default_source_version="sv_empty",
        default_rule_version="rv_default",
        default_cache_version="cv_default",
    )

    assert default_lineage == {
        "source_version": "sv_empty",
        "rule_version": "rv_default",
        "cache_version": "cv_default",
        "vendor_version": "vv_none",
    }


def test_resolve_formal_dates_lineage_normalizes_partial_fallback_with_defaults(tmp_path):
    lineage_mod = _load_lineage_module()

    fallback_lineage = lineage_mod.resolve_formal_dates_lineage(
        governance_dir=str(tmp_path / "missing-partial"),
        cache_key="bond_analytics:materialize:formal",
        report_dates=["2026-03-31"],
        default_source_version="sv_empty",
        default_rule_version="rv_default",
        default_cache_version="cv_default",
        default_vendor_version="vv_none",
        fallback_lineage_loader=lambda _report_date: {
            "source_version": "sv_fallback",
            "rule_version": "",
        },
    )

    assert fallback_lineage == {
        "source_version": "sv_fallback",
        "rule_version": "rv_default",
        "cache_version": "cv_default",
        "vendor_version": "vv_none",
    }


def test_resolve_formal_lineage_supports_live_postgres_sql_authority(tmp_path):
    sql_dsn = os.getenv("MOSS_TEST_POSTGRES_DSN", "").strip()
    if not sql_dsn:
        pytest.skip("MOSS_TEST_POSTGRES_DSN not configured")

    lineage_mod = _load_lineage_module()
    governance_mod, repo, _unused_sql_dsn = _governance_repo(tmp_path, backend_mode="jsonl")
    repo = governance_mod.GovernanceRepository(
        base_dir=tmp_path,
        sql_dsn=sql_dsn,
        backend_mode="sql-authority",
    )

    suffix = uuid.uuid4().hex
    cache_key = f"mock_standard:materialize:formal:{suffix}"
    report_date = "2025-12-31"
    repo.append(
        governance_mod.CACHE_MANIFEST_STREAM,
        {
            "cache_key": cache_key,
            "cache_version": f"cv_pg_{suffix}",
            "source_version": f"sv_pg_{suffix}",
            "vendor_version": f"vv_pg_{suffix}",
            "rule_version": f"rv_pg_{suffix}",
            "created_at": "2026-04-12T12:00:00+00:00",
        },
    )
    repo.append(
        governance_mod.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": f"run-pg-{suffix}",
            "job_name": "mock_standard_materialize",
            "status": "completed",
            "cache_key": cache_key,
            "cache_version": f"cv_pg_{suffix}",
            "lock": "lock:duckdb:formal:mock-standard:materialize",
            "source_version": f"sv_pg_{suffix}",
            "vendor_version": f"vv_pg_{suffix}",
            "rule_version": f"rv_pg_{suffix}",
            "report_date": report_date,
            "created_at": "2026-04-12T12:00:00+00:00",
        },
    )

    manifest = lineage_mod.resolve_formal_manifest_lineage(
        governance_dir=str(tmp_path),
        cache_key=cache_key,
        sql_dsn=sql_dsn,
        backend_mode="sql-authority",
    )
    build = lineage_mod.resolve_completed_formal_build_lineage(
        governance_dir=str(tmp_path),
        cache_key=cache_key,
        job_name="mock_standard_materialize",
        report_date=report_date,
        sql_dsn=sql_dsn,
        backend_mode="sql-authority",
    )

    assert manifest["cache_key"] == cache_key
    assert manifest["source_version"] == f"sv_pg_{suffix}"
    assert build is not None
    assert build["cache_key"] == cache_key
    assert build["run_id"] == f"run-pg-{suffix}"
