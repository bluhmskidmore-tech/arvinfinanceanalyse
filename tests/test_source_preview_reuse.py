"""Integrity guards for reusing already materialized source-preview results."""

from copy import deepcopy
import os
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest

from backend.app.repositories import source_preview_repo, source_preview_reuse
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.tasks import source_preview_refresh
from tests.test_source_preview_write_batches import FAMILIES, _preview_payload, _stored_tables

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_source_preview,
]


@pytest.fixture
def preview_refresh(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    archive.mkdir()
    governance_path = tmp_path / "governance"
    duckdb_path = tmp_path / "preview.duckdb"
    governance = GovernanceRepository(base_dir=governance_path, backend_mode="jsonl")
    payload = _preview_payload("batch-current", repeated_traces=3)
    payload[2][0]["field_value"] = None
    source_files = []
    file_names = (
        "zqtz-20260831.xls",
        "tywl-20260831.xls",
        "FI-20260831.csv",
        "非标514-20260801-0831.xlsx",
        "非标516-20260801-0831.xlsx",
        "非标517-20260801-0831.xlsx",
    )
    for family, file_name in zip(FAMILIES, file_names):
        path = archive / file_name
        path.write_bytes(b"synthetic-source-one")
        source_files.append(path)
        governance.append(
            SOURCE_MANIFEST_STREAM,
            {
                "ingest_batch_id": "batch-current",
                "source_family": family,
                "source_file": path.name,
                "archived_path": str(path),
                "source_version": "sv_original",
                "report_date": "2026-08-31",
                "report_start_date": "2026-08-31",
                "report_end_date": "2026-08-31",
                "report_granularity": "day",
                "status": "completed",
                "created_at": "2026-09-15T09:00:00+08:00",
            },
        )

    state = SimpleNamespace(fail_after_write=False)

    def materialize(**kwargs):
        source_preview_repo._write_preview_tables(kwargs["duckdb_path"], *deepcopy(payload))
        if state.fail_after_write:
            raise RuntimeError("synthetic materialization failed")
        return deepcopy(payload[0])

    actions = {
        "snapshot": Mock(wraps=source_preview_refresh.snapshot_preview_tables),
        "materialize": Mock(side_effect=materialize),
        "cleanup": Mock(wraps=source_preview_refresh.cleanup_preview_backups),
        "restore": Mock(wraps=source_preview_refresh.restore_preview_tables),
    }
    for name, attribute in (
        ("snapshot", "snapshot_preview_tables"),
        ("materialize", "materialize_source_previews"),
        ("cleanup", "cleanup_preview_backups"),
        ("restore", "restore_preview_tables"),
    ):
        monkeypatch.setattr(source_preview_refresh, attribute, actions[name])
    monkeypatch.setattr(
        source_preview_refresh,
        "get_settings",
        lambda: SimpleNamespace(
            local_archive_path=archive,
            governance_sql_dsn="",
            source_preview_governance_backend="jsonl",
            job_state_dsn="",
        ),
    )
    monkeypatch.setattr(
        source_preview_refresh, "_run_source_preview_ingest", lambda **_: {"ingest_batch_id": ""}
    )
    run_ids = []

    def refresh(*, from_existing_manifests=False):
        run_id = f"preview-reuse-test-{len(run_ids)}"
        run_ids.append(run_id)
        return source_preview_refresh._refresh_source_preview_cache(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_path),
            data_root=str(tmp_path / "input"),
            run_id=run_id,
            from_existing_manifests=from_existing_manifests,
        )

    return SimpleNamespace(
        refresh=refresh,
        actions=actions,
        governance=governance,
        duckdb_path=duckdb_path,
        source_files=source_files,
        payload=payload,
        state=state,
        run_ids=run_ids,
    )


@pytest.mark.parametrize("from_existing_manifests", [False, True])
def test_unchanged_refresh_reuses_verified_results_without_backup_or_write(
    preview_refresh, from_existing_manifests
):
    env = preview_refresh
    first = env.refresh(from_existing_manifests=from_existing_manifests)
    before = _stored_tables(env.duckdb_path)
    counts = {name: action.call_count for name, action in env.actions.items()}

    second = env.refresh(from_existing_manifests=from_existing_manifests)

    assert first["reuse_status"] == "rebuilt"
    assert second["reuse_status"] == "reused"
    assert second["refresh_mode"] == first["refresh_mode"]
    for field in ("source_version", "report_dates", "preview_sources", "rule_version"):
        assert second[field] == first[field]
    assert {name: action.call_count for name, action in env.actions.items()} == counts
    assert counts == {"snapshot": 1, "materialize": 1, "cleanup": 1, "restore": 0}
    assert _stored_tables(env.duckdb_path) == before
    manifest = env.governance.read_all(CACHE_MANIFEST_STREAM)[-1]
    completed = env.governance.read_all(CACHE_BUILD_RUN_STREAM)[-1]
    assert manifest["run_id"] == completed["run_id"] == second["run_id"]
    assert manifest["preview_reuse"]["summaries"] == env.payload[0]
    assert completed["status"] == "completed"
    assert completed["reuse_status"] == "reused"


def test_same_name_size_and_mtime_do_not_hide_changed_source_bytes(preview_refresh):
    env = preview_refresh
    env.refresh()
    source = env.source_files[0]
    before = source.stat()
    source.write_bytes(b"synthetic-source-two")
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert source.stat().st_size == before.st_size
    assert source.stat().st_mtime_ns == before.st_mtime_ns

    assert env.refresh()["reuse_status"] == "rebuilt"
    assert env.actions["materialize"].call_count == 2


@pytest.mark.parametrize("identity_field", ["rule_version", "implementation_sha256"])
def test_changed_rule_or_implementation_identity_forces_rebuild(
    preview_refresh, monkeypatch, identity_field
):
    env = preview_refresh
    env.refresh()
    if identity_field == "rule_version":
        monkeypatch.setattr(source_preview_repo, "RULE_VERSION", "rv_changed")
    else:
        monkeypatch.setattr(source_preview_reuse, "_implementation_signature", lambda: "changed-code")

    assert env.refresh()["reuse_status"] == "rebuilt"
    assert env.actions["materialize"].call_count == 2


@pytest.mark.parametrize(
    ("table", "field"),
    [
        ("phase1_source_preview_summary", "source_file"),
        ("phase1_source_preview_groups", "group_label"),
        ("phase1_zqtz_preview_rows", "instrument_name"),
        ("phase1_tyw_preview_rows", "counterparty_name"),
        ("phase1_pnl_preview_rows", "portfolio_name"),
        ("phase1_nonstd_pnl_preview_rows", "raw_amount"),
        ("phase1_zqtz_rule_traces", "field_value"),
        ("phase1_tyw_rule_traces", "derived_label"),
        ("phase1_pnl_rule_traces", "field_name"),
        ("phase1_nonstd_pnl_rule_traces", "field_value"),
    ],
)
def test_same_row_count_content_change_in_any_preview_table_forces_rebuild(
    preview_refresh, table, field
):
    env = preview_refresh
    env.refresh()
    before = _stored_tables(env.duckdb_path)
    with duckdb.connect(str(env.duckdb_path)) as conn:
        row_count = conn.execute(f"select count(*) from {table}").fetchone()
        conn.execute(f"update {table} set {field} = ?", ["字段'已变化"])
        assert conn.execute(f"select count(*) from {table}").fetchone() == row_count

    assert env.refresh()["reuse_status"] == "rebuilt"
    assert env.actions["materialize"].call_count == 2
    assert _stored_tables(env.duckdb_path) == before


@pytest.mark.parametrize("change", ["missing", "duplicate", "null_to_empty"])
def test_trace_multiplicity_and_null_content_are_verified(preview_refresh, change):
    env = preview_refresh
    env.refresh()
    with duckdb.connect(str(env.duckdb_path)) as conn:
        if change == "missing":
            conn.execute("delete from phase1_zqtz_rule_traces where field_value is null")
        elif change == "duplicate":
            conn.execute(
                "insert into phase1_zqtz_rule_traces select * from phase1_zqtz_rule_traces limit 1"
            )
        else:
            conn.execute("update phase1_zqtz_rule_traces set field_value = '' where field_value is null")

    assert env.refresh()["reuse_status"] == "rebuilt"
    assert env.actions["materialize"].call_count == 2


@pytest.mark.parametrize(
    "damage", ["legacy", "malformed", "missing_table", "summary_changed", "unlinked_run"]
)
def test_incomplete_or_unlinked_reuse_receipt_falls_back_to_rebuild(preview_refresh, damage):
    env = preview_refresh
    env.refresh()
    receipt = deepcopy(env.governance.read_all(CACHE_MANIFEST_STREAM)[-1])
    if damage == "legacy":
        receipt.pop("preview_reuse")
    elif damage == "malformed":
        receipt["preview_reuse"] = {"inputs": [], "tables": "broken", "summaries": 1}
    elif damage == "missing_table":
        receipt["preview_reuse"]["tables"] = {}
    elif damage == "summary_changed":
        receipt["preview_reuse"]["summaries"][0]["total_rows"] = 999
    else:
        receipt["run_id"] = "never-completed-run"
    env.governance.append(CACHE_MANIFEST_STREAM, receipt)

    assert env.refresh()["reuse_status"] == "rebuilt"
    assert env.actions["materialize"].call_count == 2


def test_failed_rebuild_restores_results_and_does_not_publish_reusable_receipt(preview_refresh):
    env = preview_refresh
    env.refresh()
    original_tables = _stored_tables(env.duckdb_path)
    original_receipts = env.governance.read_all(CACHE_MANIFEST_STREAM)
    env.source_files[0].write_bytes(b"changed source")
    env.payload[1][0]["instrument_name"] = "失败写入'测试"
    env.state.fail_after_write = True

    with pytest.raises(RuntimeError, match="synthetic materialization failed"):
        env.refresh()

    assert _stored_tables(env.duckdb_path) == original_tables
    assert env.governance.read_all(CACHE_MANIFEST_STREAM) == original_receipts
    assert env.governance.read_all(CACHE_BUILD_RUN_STREAM)[-1]["status"] == "failed"
    assert env.actions["restore"].call_count == 1
    env.state.fail_after_write = False
    assert env.refresh()["reuse_status"] == "rebuilt"
    assert env.refresh()["reuse_status"] == "reused"
    assert env.actions["materialize"].call_count == 3


def test_missing_physical_table_cannot_reuse_old_success_receipt(preview_refresh):
    env = preview_refresh
    env.refresh()
    original_receipts = env.governance.read_all(CACHE_MANIFEST_STREAM)
    with duckdb.connect(str(env.duckdb_path)) as conn:
        conn.execute("drop table phase1_zqtz_rule_traces")

    # The existing writer does not repair tables removed after their migration
    # was recorded. Reuse must not conceal that storage failure as success.
    with pytest.raises(duckdb.CatalogException, match="phase1_zqtz_rule_traces"):
        env.refresh()

    assert env.actions["materialize"].call_count == 2
    assert env.governance.read_all(CACHE_MANIFEST_STREAM) == original_receipts
    assert env.governance.read_all(CACHE_BUILD_RUN_STREAM)[-1]["status"] == "failed"


def test_real_csv_parse_results_are_preserved_by_second_refresh(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    archive.mkdir()
    source = archive / "FI-20260831.csv"
    source.write_text(
        "\ufeff债券代码,投资类型,投资组合,成本中心,币种\n010221,H,组合甲,50,RMB\n",
        encoding="utf-8",
    )
    governance_path = tmp_path / "governance"
    duckdb_path = tmp_path / "preview.duckdb"
    governance = GovernanceRepository(base_dir=governance_path, backend_mode="jsonl")
    governance.append(
        SOURCE_MANIFEST_STREAM,
        {
            "ingest_batch_id": "batch-csv",
            "source_family": "pnl",
            "source_file": source.name,
            "archived_path": str(source),
            "source_version": "sv_csv",
            "report_date": "2026-08-31",
            "status": "completed",
            "created_at": "2026-09-15T09:00:00+08:00",
        },
    )
    monkeypatch.setattr(
        source_preview_refresh,
        "get_settings",
        lambda: SimpleNamespace(
            local_archive_path=archive,
            governance_sql_dsn="",
            source_preview_governance_backend="jsonl",
            job_state_dsn="",
        ),
    )
    monkeypatch.setattr(
        source_preview_refresh, "_run_source_preview_ingest", lambda **_: {"ingest_batch_id": ""}
    )
    materialize = Mock(wraps=source_preview_repo.materialize_source_previews)
    monkeypatch.setattr(source_preview_refresh, "materialize_source_previews", materialize)
    arguments = {
        "duckdb_path": str(duckdb_path),
        "governance_dir": str(governance_path),
        "data_root": str(tmp_path / "input"),
    }
    first = source_preview_refresh._refresh_source_preview_cache(**arguments, run_id="csv-first")
    original_tables = _stored_tables(duckdb_path)

    second = source_preview_refresh._refresh_source_preview_cache(**arguments, run_id="csv-second")

    assert first["reuse_status"] == "rebuilt"
    assert second["reuse_status"] == "reused"
    assert materialize.call_count == 1
    assert second["source_version"] == first["source_version"] == "sv_csv"
    assert second["report_dates"] == first["report_dates"] == ["2026-08-31"]
    assert _stored_tables(duckdb_path) == original_tables
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        assert conn.execute(
            "select instrument_code, portfolio_name, currency from phase1_pnl_preview_rows"
        ).fetchall() == [("010221", "组合甲", "RMB")]
        assert conn.execute("select count(*) from phase1_pnl_rule_traces").fetchone()[0] > 0
