from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _load_module():
    return load_module(
        "scripts.stock_analysis_page_gap_manifest",
        "scripts/stock_analysis_page_gap_manifest.py",
    )


def _manifest(status: str = "gaps_found") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_kind": "stock_analysis_page_gap_manifest_v1",
        "status": status,
        "created_at": "2026-08-24T12:00:00Z",
        "evaluation_as_of_date": "2026-08-24",
        "page_id": "GAP-STOCK-ANALYSIS-PAGE",
        "page_route": "/stock-analysis",
        "primary_api": "/api/data-health",
        "page_metric_key": "data_health.adjustment_factor_gap",
        "source_contract": {
            "result_kind": "data_health.overview",
            "rule_version": "rv_data_health_v1",
            "formal_use_allowed": False,
            "metric_semantics": (
                "count each horizon independently when return_*_net is non-null "
                "and return_*_net_adj is null across all physical execution rows "
                "and signal kinds"
            ),
        },
        "approval_boundary": {
            "write_allowed": False,
            "materialization_allowed": False,
            "vendor_fetch_executed": False,
            "historical_availability_proven": False,
            "certification_allowed": False,
            "fallback_allowed": False,
        },
        "database": {
            "path": "F:/tmp/mock.duckdb",
            "sha256_before": "D" * 64,
            "sha256_after": "D" * 64,
            "unchanged": True,
            "read_only": True,
        },
        "summary": {
            "page_gap_view_count_before": 5022 if status == "gaps_found" else 0,
            "factor_write_only_projected_gap_view_count": 5022
            if status == "gaps_found"
            else 0,
            "factor_write_only_reduction": 0,
            "conditional_full_materialization_projected_gap_view_count": 0,
            "conditional_full_materialization_reduction": 5022
            if status == "gaps_found"
            else 0,
            "conditional_full_materialization_note": (
                "Upper bound only: assumes every exact factor cell can be reconciled "
                "to a valid value and a full-horizon materializer rewrites every "
                "affected execution row."
            ),
            "current_recomputable_gap_view_count": 0,
            "unique_execution_key_count": 2446,
            "unique_required_factor_cell_count": 5548,
            "unique_missing_factor_cell_count": 3405 if status == "gaps_found" else 0,
            "missing_factor_requirement_use_count": 6514
            if status == "gaps_found"
            else 0,
            "horizon_counts": (
                [
                    {"value": "20d", "count": 2077},
                    {"value": "10d", "count": 1426},
                    {"value": "5d", "count": 982},
                    {"value": "1d", "count": 537},
                ]
                if status == "gaps_found"
                else []
            ),
            "classification_counts_by_horizon": {},
            "signal_kind_counts": [],
            "missing_factor_role_scope_counts": [],
            "factor_quality": {
                "missing_required_cell_count": 3405 if status == "gaps_found" else 0,
                "invalid_required_cell_count": 0,
                "ambiguous_required_cell_count": 0,
            },
            "legacy_repair_coverage": {
                "coverage_kind": "selector_candidate",
                "selector_signal_kind": "stock_candidate",
                "selector_scope_only": True,
                "effective_repair_preview_executed": False,
                "selector_candidate_logical_key_count": 0,
                "covered_gap_view_count": 0,
                "covered_horizon_counts": [],
            },
        },
        "legacy_repair_coverage": {
            "coverage_kind": "selector_candidate",
            "selector_signal_kind": "stock_candidate",
            "selector_scope_only": True,
            "effective_repair_preview_executed": False,
            "selector_candidate_logical_key_count": 0,
            "covered_gap_view_count": 0,
            "covered_horizon_counts": [],
        },
        "gap_views": [],
        "missing_factor_cells": [],
        "blockers": [] if status != "blocked" else ["runner_date_coverage_mismatch"],
        "canonical_manifest_sha256": "C" * 64,
    }


def _files(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"read-only-db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    return db_path, trusted_root


def _create_real_page_gap_db(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
              market_state varchar,
              signal_close double,
              entry_date varchar,
              entry_price double,
              entry_executable boolean,
              exit_date_1d varchar,
              exit_price_1d double,
              return_1d_net double,
              return_1d_net_adj double,
              exit_date_5d varchar,
              exit_price_5d double,
              return_5d_net double,
              return_5d_net_adj double,
              exit_date_10d varchar,
              exit_price_10d double,
              return_10d_net double,
              return_10d_net_adj double,
              exit_date_20d varchar,
              exit_price_20d double,
              return_20d_net double,
              return_20d_net_adj double,
              data_status varchar,
              formula_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history (
              signal_date, stock_code, stock_name, signal_kind,
              candidate_rank, market_state, signal_close, entry_date,
              entry_price, entry_executable, exit_date_1d, exit_price_1d,
              return_1d_net, return_1d_net_adj, data_status,
              formula_version, run_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2026-01-02",
                "600000.SH",
                "浦发银行",
                "theme_breakout",
                1,
                "bull",
                10.0,
                "2026-01-05",
                10.0,
                True,
                "2026-01-06",
                10.2,
                0.01,
                None,
                "complete",
                "fv_livermore_candidate_execution_dual_adjust_v5",
                "e2e-execution-run",
            ],
        )
    finally:
        conn.close()


def test_help_has_no_apply_or_execute_flags(capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_module()
    with pytest.raises(SystemExit) as exc_info:
        module.main(["--help"])
    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--duckdb-path" in help_text
    assert "--trusted-evidence-root" in help_text
    assert "--apply" not in help_text
    assert "--execute" not in help_text


@pytest.mark.parametrize("status", ["ready", "gaps_found"])
def test_cli_persists_compact_summary_for_success(
    status: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    expected_manifest = _manifest(status)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: expected_manifest,
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (True, ()),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    output = trusted_root / "page-gap.json"
    assert result["status"] == status
    assert result["database_unchanged"] is True
    assert result["output_file"] == str(output.resolve())
    assert json.loads(output.read_text(encoding="utf-8")) == expected_manifest
    assert not list(trusted_root.glob(".page-gap.json.owner-*"))
    assert (
        result["summary"]["horizon_counts"]
        == expected_manifest["summary"]["horizon_counts"]
    )
    assert "factor_quality" not in result["summary"]
    assert "classification_counts_by_horizon" not in result["summary"]
    assert result["summary"]["factor_write_only_projected_gap_view_count"] == (
        5022 if status == "gaps_found" else 0
    )
    assert (
        result["summary"]["conditional_full_materialization_projected_gap_view_count"]
        == 0
    )
    assert "gap_views" not in result
    assert "missing_factor_cells" not in result


def test_cli_real_builder_validator_e2e_persists_valid_manifest(
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "page-gap-e2e.duckdb"
    trusted_root = tmp_path / "trusted-e2e"
    trusted_root.mkdir()
    _create_real_page_gap_db(db_path)

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap-e2e.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    output = trusted_root / "page-gap-e2e.json"
    assert output.is_file(), result
    persisted = json.loads(output.read_text(encoding="utf-8"))
    valid, errors = module.manifest_task.validate_stock_analysis_page_gap_manifest(
        persisted
    )
    assert result["status"] == "gaps_found"
    assert result["database_unchanged"] is True
    assert result["summary"]["page_gap_view_count_before"] == 1
    assert result["summary"]["horizon_counts"] == [{"value": "1d", "count": 1}]
    assert persisted["page_route"] == "/stock-analysis"
    assert persisted["primary_api"] == "/api/data-health"
    assert persisted["approval_boundary"]["write_allowed"] is False
    assert valid, errors


def test_cli_rejects_output_escape_without_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    outside = tmp_path / "outside.json"
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: pytest.fail("builder must not run for escaped output"),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file=outside,
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["output_file_outside_trusted_root"]
    assert outside.exists() is False


def test_cli_rejects_symlink_component(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    outside = tmp_path / "outside-dir"
    outside.mkdir()
    linked = trusted_root / "linked"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: pytest.fail("builder must not run through symlink path"),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="linked/page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["output_file_contains_symlink_or_junction_component"]
    assert (outside / "page-gap.json").exists() is False


def test_cli_rejects_symlinked_duckdb_before_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    linked_db = tmp_path / "linked.duckdb"
    try:
        linked_db.symlink_to(db_path)
    except OSError:
        pytest.skip("symlink creation unavailable")
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: pytest.fail("builder must not run through linked DB"),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=linked_db,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["duckdb_path_contains_symlink_or_junction_component"]
    assert (trusted_root / "page-gap.json").exists() is False


def test_cli_refuses_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    existing = trusted_root / "page-gap.json"
    existing.write_text("keep-me", encoding="utf-8")
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: pytest.fail("builder must not run when output exists"),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["output_file_must_be_new"]
    assert existing.read_text(encoding="utf-8") == "keep-me"


def test_cli_blocks_invalid_manifest_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: _manifest("gaps_found"),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (
            False,
            ("bad-hash", "secret path C:/private/report.json"),
        ),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == [
        "page_gap_manifest_validation_failed",
        "bad-hash",
        "validation_error_2_detail_redacted",
    ]
    assert "private" not in json.dumps(result)
    assert (trusted_root / "page-gap.json").exists() is False


def test_cli_blocks_manifest_blocked_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: _manifest("blocked"),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (True, ()),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["runner_date_coverage_mismatch"]
    assert (trusted_root / "page-gap.json").exists() is False


def test_cli_redacts_builder_exception_and_main_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("token=SECRET")),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )
    assert result["status"] == "error"
    assert json.dumps(result).find("SECRET") == -1

    monkeypatch.setattr(
        module,
        "run_stock_analysis_page_gap_manifest_cli",
        lambda **kwargs: {
            "status": "gaps_found",
            "blockers": [],
            "database_unchanged": True,
            "summary": {"page_gap_view_count_before": 5022},
        },
    )
    success_code = module.main(
        [
            "--duckdb-path",
            str(db_path),
            "--trusted-evidence-root",
            str(trusted_root),
            "--output-file",
            "page-gap.json",
            "--evaluation-as-of-date",
            "2026-08-24",
            "--created-at",
            "2026-08-24T12:00:00Z",
        ]
    )
    printed = capsys.readouterr().out
    assert success_code == module.EXIT_SUCCESS
    printed_payload = json.loads(printed)
    assert printed_payload["status"] == "gaps_found"
    assert printed_payload["summary"] == {"page_gap_view_count_before": 5022}
    assert "gap_views" not in printed_payload
    assert "\n  " not in printed

    monkeypatch.setattr(
        module,
        "run_stock_analysis_page_gap_manifest_cli",
        lambda **kwargs: {"status": "blocked", "blockers": ["x"]},
    )
    assert (
        module.main(
            [
                "--duckdb-path",
                str(db_path),
                "--trusted-evidence-root",
                str(trusted_root),
                "--output-file",
                "page-gap.json",
                "--evaluation-as-of-date",
                "2026-08-24",
                "--created-at",
                "2026-08-24T12:00:00Z",
            ]
        )
        == module.EXIT_BLOCKED
    )

    monkeypatch.setattr(
        module,
        "run_stock_analysis_page_gap_manifest_cli",
        lambda **kwargs: {"status": "error", "blockers": ["x"]},
    )
    assert (
        module.main(
            [
                "--duckdb-path",
                str(db_path),
                "--trusted-evidence-root",
                str(trusted_root),
                "--output-file",
                "page-gap.json",
                "--evaluation-as-of-date",
                "2026-08-24",
                "--created-at",
                "2026-08-24T12:00:00Z",
            ]
        )
        == module.EXIT_RUNTIME_ERROR
    )


def test_cli_detects_duckdb_hash_drift_after_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: _manifest("ready"),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (True, ()),
    )
    hashes = iter(["A" * 64, "B" * 64])
    monkeypatch.setattr(module, "_file_sha256", lambda path: next(hashes))

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["duckdb_hash_changed_during_manifest_build"]
    assert (trusted_root / "page-gap.json").exists() is False


def test_cli_removes_new_output_when_duckdb_drifts_after_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: _manifest("gaps_found"),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (True, ()),
    )
    hashes = iter(["A" * 64, "A" * 64, "B" * 64])
    monkeypatch.setattr(module, "_file_sha256", lambda path: next(hashes))

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["duckdb_hash_changed_during_manifest_persistence"]
    assert result["database_unchanged"] is False
    assert (trusted_root / "page-gap.json").exists() is False


def test_exclusive_publish_preserves_output_created_by_another_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output = trusted_root / "page-gap.json"
    real_link = module.os.link

    def _publish_race(source: Path, target: Path, **kwargs: object) -> None:
        target.write_text("another-process-output", encoding="utf-8")
        real_link(source, target, **kwargs)

    monkeypatch.setattr(module.os, "link", _publish_race)
    with pytest.raises(FileExistsError):
        module._write_json_exclusive(
            trusted_root=trusted_root, output_file=output, payload={"valid": True}
        )

    assert output.read_text(encoding="utf-8") == "another-process-output"
    assert not list(trusted_root.glob(".page-gap.json.owner-*"))


def test_exclusive_write_fails_closed_when_hardlinks_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output = trusted_root / "page-gap.json"

    def _unavailable(*_args: object, **_kwargs: object) -> None:
        raise OSError("hardlinks unavailable")

    monkeypatch.setattr(module.os, "link", _unavailable)
    with pytest.raises(OSError, match="hardlinks unavailable"):
        module._write_json_exclusive(
            trusted_root=trusted_root, output_file=output, payload={"valid": True}
        )

    assert not output.exists()
    assert not list(trusted_root.glob(".page-gap.json.owner-*"))


def test_cli_removes_partial_output_when_exclusive_flush_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: _manifest("gaps_found"),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (True, ()),
    )
    monkeypatch.setattr(
        module.os,
        "fsync",
        lambda file_descriptor: (_ for _ in ()).throw(OSError("disk failure")),
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "error"
    assert result["blockers"] == ["page_gap_manifest_cli_failed_OSError"]
    assert (trusted_root / "page-gap.json").exists() is False


def test_cli_removes_output_when_persisted_readback_does_not_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: _manifest("gaps_found"),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (True, ()),
    )
    monkeypatch.setattr(
        module,
        "_load_json_object",
        lambda path: {"tampered": True},
    )

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    assert result["status"] == "error"
    assert result["blockers"] == ["page_gap_manifest_cli_failed_CliRuntimeError"]
    assert (trusted_root / "page-gap.json").exists() is False


@pytest.mark.parametrize("same_content", [False, True])
def test_cli_does_not_delete_replacement_swapped_in_after_exclusive_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    same_content: bool,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_page_gap_manifest",
        lambda **kwargs: _manifest("gaps_found"),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda payload: (True, ()),
    )

    replacement_text = "replacement-owned-by-another-process"

    def _swap_then_fail(path: Path) -> dict[str, Any]:
        nonlocal replacement_text
        if same_content:
            replacement_text = path.read_text(encoding="utf-8")
        path.unlink()
        path.write_text(replacement_text, encoding="utf-8")
        raise RuntimeError("simulated readback race")

    monkeypatch.setattr(module, "_load_json_object", _swap_then_fail)

    result = module.run_stock_analysis_page_gap_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        output_file="page-gap.json",
        evaluation_as_of_date="2026-08-24",
        created_at="2026-08-24T12:00:00Z",
    )

    replacement = trusted_root / "page-gap.json"
    assert result["status"] == "error"
    assert replacement.read_text(encoding="utf-8") == replacement_text
    assert not list(trusted_root.glob(".page-gap.json.owner-*"))
