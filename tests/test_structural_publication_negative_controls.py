"""Existing publisher protections must reject incoherent synthetic source cuts.

The generic formal table exercises real governance/fact qualification and the
actual sealed publisher. It is not full bond/balance computation acceptance.
"""
from __future__ import annotations

import duckdb
import pytest

from backend.app.repositories.financial_result_publication_repo import (
    FinancialPublicationConflict, FinancialPublicationInvalid, read_publication_pointer,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM, GovernanceRepository,
)
from backend.app.tasks.financial_result_publication import FinancialTablePublicationSpec, publish_financial_result
from backend.app.tasks.system_read_publication import _freeze_result_lineage, _source_cut_snapshot
from tests.test_system_read_publication_process_crash import (
    _NEW_GENERATION, _OLD_GENERATION, _REPORT_DATE, _SOURCE_DEPENDENCY,
    _plan, _read_sentinel, publication_fixture,
)


@pytest.mark.parametrize("invalid", ["fact_source", "missing_manifest", "manifest_source", "manifest_run", "failed_terminal"])
def test_publisher_rejects_invalid_exact_terminal_fact_cut_before_pointer_commit(publication_fixture, monkeypatch, invalid):
    settings, source, root, bundle = publication_fixture
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    repo = GovernanceRepository(settings.governance_path)
    cache_key, table = "bd031_synthetic:materialize:formal", "fact_formal_bd031_synthetic"
    versions = {"source_version": "sv_A", "rule_version": "rv_synthetic", "cache_version": "cv_synthetic", "vendor_version": "vv_synthetic"}
    row = {"run_id": "A", "cache_key": cache_key, "report_date": _REPORT_DATE, **versions}
    repo.append(CACHE_BUILD_RUN_STREAM, {**row, "status": "failed" if invalid == "failed_terminal" else "completed"})
    if invalid == "failed_terminal":
        repo.append(CACHE_BUILD_RUN_STREAM, {**row, "run_id": "decoy", "status": "completed"})
    if invalid != "missing_manifest":
        manifest = {**row, "fact_tables": [table], "input_sources": [], "basis": "formal"}
        if invalid == "manifest_source":
            manifest["source_version"] = "sv_other"
        if invalid == "manifest_run":
            manifest["run_id"] = "other"
        repo.append(CACHE_MANIFEST_STREAM, manifest)
    with duckdb.connect(str(source)) as conn:
        conn.execute(f"CREATE TABLE {table}(report_date DATE, amount BIGINT, source_version VARCHAR, rule_version VARCHAR, cache_version VARCHAR, vendor_version VARCHAR)")
        conn.execute(f"INSERT INTO {table} VALUES (?, 202, ?, ?, ?, ?)",
                     [_REPORT_DATE, "sv_B" if invalid == "fact_source" else "sv_A", "rv_synthetic", "cv_synthetic", "vv_synthetic"])
    specs = (FinancialTablePublicationSpec(name=table, date_column="report_date", required_dates=(_REPORT_DATE,)),)
    refs = (("A", cache_key),)
    before = read_publication_pointer(root)
    stages = []

    def validate(conn):
        frozen = _freeze_result_lineage(repo, lineage_references=refs, report_date=_REPORT_DATE)
        _source_cut_snapshot(conn, table_specs=specs, governance_streams=frozen, lineage_references=refs, report_date=_REPORT_DATE)
        return _SOURCE_DEPENDENCY

    expected = "does not match source facts" if invalid == "fact_source" else "completed terminal is missing" if invalid == "failed_terminal" else "cache manifest is missing"
    with pytest.raises(FinancialPublicationInvalid, match=expected):
        publish_financial_result(source_duckdb_path=source, publication_root=root,
                                 plan=_plan(generation=_NEW_GENERATION, expected_previous_generation=_OLD_GENERATION,
                                            bundle=bundle, source_dependency_validator=validate), on_stage=stages.append)
    assert read_publication_pointer(root) == before
    assert _read_sentinel(root, _OLD_GENERATION) == "ACTIVE"
    assert "pointer_committed" not in stages


def test_publisher_revalidates_changed_dependency_after_candidate_validation(publication_fixture):
    _settings, source, root, bundle = publication_fixture
    dependency, stages, observed = dict(_SOURCE_DEPENDENCY), [], []
    before = read_publication_pointer(root)

    def validate(_conn):
        observed.append(dict(dependency))
        return dict(dependency)

    def on_stage(stage):
        stages.append(stage)
        if stage == "candidate_validated":
            dependency["synthetic-source"] = "fixture-v2"

    with pytest.raises(FinancialPublicationConflict):
        publish_financial_result(source_duckdb_path=source, publication_root=root,
                                 plan=_plan(generation=_NEW_GENERATION, expected_previous_generation=_OLD_GENERATION,
                                            bundle=bundle, source_dependency_validator=validate), on_stage=on_stage)
    assert observed == [_SOURCE_DEPENDENCY, {"synthetic-source": "fixture-v2"}]
    assert "candidate_validated" in stages and "before_pointer_commit" not in stages
    assert "pointer_committed" not in stages
    assert read_publication_pointer(root) == before
    assert _read_sentinel(root, _OLD_GENERATION) == "ACTIVE"
