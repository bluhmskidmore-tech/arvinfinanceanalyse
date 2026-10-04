from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _load_module():
    return load_module(
        "scripts.stock_analysis_current_rule_factor_manifest",
        "scripts/stock_analysis_current_rule_factor_manifest.py",
    )


def _governed_inputs(trusted_root: Path) -> dict[str, Any]:
    return {
        "trusted_root": trusted_root.resolve(),
        "calendar_receipt": {
            "authority_status": "approved",
            "canonical_receipt_sha256": "A" * 64,
        },
        "evaluation_as_of_date": "2026-08-23",
        "source_receipts": [
            {
                "receipt_kind": "pit_source_availability_v1",
                "sources": [
                    {
                        "table": "stock_adjustment_factor",
                        "source_version": "sv-factor",
                        "vendor_version": "vv-choice",
                        "rule_version": "rv-factor",
                        "run_id": "run-factor",
                        "available_at": "2026-08-23",
                    }
                ],
            }
        ],
        "version_tuple": {
            "candidate_rule_version": "rv_candidate_history_current",
            "execution_formula_version": "fv_execution_v5",
            "strict_coverage": True,
            "fallback_covered": False,
        },
        "governed_run_id": "stock-analysis-current-rule-governed-v1-ABC",
        "start_date": "2026-03-03",
        "end_date": "2026-03-04",
        "open_dates": ["2026-03-03", "2026-03-04"],
    }


def _replay_report() -> dict[str, Any]:
    return {
        "requested_range": {
            "start_date": "2026-03-03",
            "end_date": "2026-03-04",
            "requested_date_count": 2,
        },
        "plan_digest_version": "stock_analysis_current_rule_replay_plan_v2",
        "plan_digest": "B" * 64,
        "date_results": [
            {
                "trade_date": "2026-03-03",
                "status": "selection_completed_with_signals",
                "accepted_candidate_count": 1,
                "accepted_candidate_codes": ["600000.SH"],
                "candidates": [
                    {
                        "stock_code": "600000.SH",
                        "signal_kind": "breakout",
                    }
                ],
                "future_business_date_violations": [],
                "future_availability_violations": [],
            },
            {
                "trade_date": "2026-03-04",
                "status": "selection_completed_no_signals",
                "accepted_candidate_count": 0,
                "accepted_candidate_codes": [],
                "candidates": [],
                "future_business_date_violations": [],
                "future_availability_violations": [],
            },
        ],
    }


def _manifest(status: str = "ready") -> dict[str, Any]:
    missing = (
        [
            {
                "stock_code": "600000.SH",
                "trade_date": "2026-03-03",
                "physical_cell_key": {
                    "stock_code": "600000.SH",
                    "trade_date": "2026-03-03",
                },
                "status": "missing",
                "cell_statuses": ["missing"],
                "occurrence_count": 1,
                "candidate_references": [
                    {"signal_date": "2026-03-03", "role": "signal"}
                ],
                "remediation_action": (
                    "supply_or_reconcile_exact_date_factor_with_attested_source"
                ),
            }
        ]
        if status == "gaps_found"
        else []
    )
    return {
        "schema_version": 1,
        "manifest_kind": "stock_analysis_current_rule_factor_manifest_v1",
        "status": status,
        "certification_allowed": False,
        "remediation_only": True,
        "governed_run_id": "stock-analysis-current-rule-governed-v1-ABC",
        "evaluation_as_of_date": "2026-08-23",
        "candidate_cells": [
            {
                "signal_date": "2026-03-03",
                "stock_code": "600000.SH",
                "role": "signal",
                "factor_date": "2026-03-03",
                "physical_cell_key": {
                    "stock_code": "600000.SH",
                    "trade_date": "2026-03-03",
                },
                "execution_data_status": "complete",
                "strict_exact_date_lookup": True,
                "status": (
                    "missing" if status == "gaps_found" else "present_pit_usable"
                ),
                "adj_factor": None if status == "gaps_found" else 1.0,
                "source_identity": None,
                "available_at": None,
                "source_receipt_match": status != "gaps_found",
                "observed_row_count": 0 if status == "gaps_found" else 1,
                "distinct_observation_count": 0 if status == "gaps_found" else 1,
            }
        ],
        "missing_unique_cells": missing,
        "summary": {
            "runner_date_count": 2,
            "runner_status_counts": {
                "selection_completed_with_signals": 1,
                "selection_completed_no_signals": 1,
            },
            "signal_date_count": 1,
            "zero_signal_date_count": 1,
            "policy_inactive_date_count": 0,
            "accepted_candidate_count": 1,
            "candidate_cell_count": 6,
            "expected_candidate_cell_count": 6,
            "cell_status_counts": {
                "missing": 1 if status == "gaps_found" else 0,
                "present_pit_usable": 0 if status == "gaps_found" else 6,
            },
            "pit_usable_cell_count": 0 if status == "gaps_found" else 6,
            "gap_cell_count": 1 if status == "gaps_found" else 0,
            "missing_unique_cell_count": len(missing),
            "blocker_count": 1 if status == "blocked" else 0,
        },
        "blockers": ([] if status != "blocked" else ["runner_date_coverage_mismatch"]),
        "database": {
            "sha256_before": "D" * 64,
            "sha256_after": "D" * 64,
            "unchanged": True,
        },
        "canonical_manifest_sha256": "C" * 64,
    }


def _patch_inputs_and_replay(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
    trusted_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    governed_calls: list[dict[str, Any]] = []
    replay_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        module.cohort_bundle_cli,
        "_load_governed_inputs",
        lambda **kwargs: governed_calls.append(dict(kwargs))
        or _governed_inputs(trusted_root),
    )
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: replay_calls.append(dict(kwargs)) or _replay_report(),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_current_rule_factor_manifest",
        lambda payload: (True, ()),
    )
    return governed_calls, replay_calls


def _run(
    module: Any,
    *,
    db_path: Path,
    trusted_root: Path,
    catalog_path: Path,
    output_file: str | Path = "factor-manifest.json",
) -> dict[str, Any]:
    return module.run_current_rule_factor_manifest_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt="calendar.json",
        source_availability_receipts=["source-a.json", "source-b.json"],
        version_tuple_file="version.json",
        choice_stock_catalog_file=catalog_path,
        output_file=output_file,
        evaluation_as_of_date="2026-08-23",
        max_workers=3,
        created_at="2026-08-23T12:00:00Z",
    )


def _files(tmp_path: Path) -> tuple[Path, Path, Path]:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"read-only-db-fixture")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text("{}", encoding="utf-8")
    return db_path, trusted_root, catalog_path


def test_cli_persists_real_manifest_shape_and_binds_governed_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    governed_calls, replay_calls = _patch_inputs_and_replay(
        module,
        monkeypatch,
        trusted_root,
    )
    builder_calls: list[dict[str, Any]] = []
    expected_manifest = _manifest("ready")
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_current_rule_factor_manifest",
        lambda **kwargs: builder_calls.append(dict(kwargs)) or expected_manifest,
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
    )

    output = trusted_root / "factor-manifest.json"
    assert result["status"] == "ready"
    assert result["database_unchanged"] is True
    assert result["output_file"] == str(output.resolve())
    assert result["canonical_manifest_sha256"] == "C" * 64
    assert result["summary"] == {
        key: value
        for key, value in expected_manifest["summary"].items()
        if not isinstance(value, dict)
    }
    assert json.loads(output.read_text(encoding="utf-8")) == expected_manifest
    assert governed_calls[0]["source_availability_receipts"] == [
        "source-a.json",
        "source-b.json",
    ]
    assert replay_calls == [
        {
            "duckdb_path": db_path.resolve(),
            "start_date": "2026-03-03",
            "end_date": "2026-03-04",
            "choice_stock_catalog_file": catalog_path,
            "max_workers": 3,
        }
    ]
    call = builder_calls[0]
    assert call["governed_run_id"] == _governed_inputs(trusted_root)["governed_run_id"]
    assert call["runner_results"] == _replay_report()["date_results"]
    assert call["source_availability_receipts"] == _governed_inputs(trusted_root)[
        "source_receipts"
    ]
    assert call["calendar_receipt_sha256"] == "A" * 64
    assert call["replay_plan_digest_version"] == (
        "stock_analysis_current_rule_replay_plan_v2"
    )
    assert call["replay_plan_digest"] == "B" * 64


def test_cli_treats_gaps_found_as_success_and_persists_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_current_rule_factor_manifest",
        lambda **kwargs: _manifest("gaps_found"),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
        output_file="gaps.json",
    )

    assert result["status"] == "gaps_found"
    assert result["blockers"] == []
    assert result["summary"]["missing_unique_cell_count"] == 1
    assert (trusted_root / "gaps.json").is_file()


def test_cli_rejects_output_escape_before_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: pytest.fail("replay must not run for escaped output"),
    )
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_current_rule_factor_manifest",
        lambda **kwargs: pytest.fail("builder must not run for escaped output"),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
        output_file=tmp_path / "escaped.json",
    )

    assert result["status"] == "error"
    assert result["output_file"] is None
    assert not (tmp_path / "escaped.json").exists()


def test_cli_refuses_overwrite_and_preserves_existing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    existing = trusted_root / "factor-manifest.json"
    existing.write_text("keep-me", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: pytest.fail("replay must not run when output exists"),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
    )

    assert result["status"] == "error"
    assert existing.read_text(encoding="utf-8") == "keep-me"


def test_cli_rejects_symlink_component_in_output_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = trusted_root / "linked"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: pytest.fail("replay must not run through a symlink"),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
        output_file="linked/factor-manifest.json",
    )

    assert result["status"] == "error"
    assert not (outside / "factor-manifest.json").exists()


def test_cli_reports_cleanup_failure_without_hiding_original_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_current_rule_factor_manifest",
        lambda **kwargs: _manifest("ready"),
    )
    original_load = module._load_json_object

    def mismatched_persisted_manifest(path):
        if path.name == "factor-manifest.json":
            return {"status": "mismatched"}
        return original_load(path)

    def denied_cleanup(**kwargs):
        raise OSError("private-path-must-not-appear-in-logs")

    monkeypatch.setattr(module, "_load_json_object", mismatched_persisted_manifest)
    monkeypatch.setattr(module, "_remove_new_manifest_file", denied_cleanup)
    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
    )

    assert result["status"] == "error"
    assert result["blockers"] == ["factor_manifest_cli_failed_FactorManifestCliError"]
    assert (trusted_root / "factor-manifest.json").is_file()
    assert "cleanup failed" in caplog.text
    assert "OSError" in caplog.text
    assert "private-path-must-not-appear-in-logs" not in caplog.text


def test_cli_removes_new_artifact_when_database_hash_drifts_after_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_current_rule_factor_manifest",
        lambda **kwargs: _manifest("ready"),
    )
    hashes = iter(["D" * 64, "D" * 64, "D" * 64, "E" * 64])
    monkeypatch.setattr(module, "_file_sha256", lambda path: next(hashes))

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == [
        "duckdb_hash_changed_during_manifest_persistence"
    ]
    assert result["database_unchanged"] is False
    assert not (trusted_root / "factor-manifest.json").exists()


def test_cli_does_not_persist_blocked_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_current_rule_factor_manifest",
        lambda **kwargs: _manifest("blocked"),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["runner_date_coverage_mismatch"]
    assert result["output_file"] is None
    assert not (trusted_root / "factor-manifest.json").exists()


def test_cli_blocks_when_replay_dates_do_not_exactly_match_governed_calendar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    replay = _replay_report()
    replay["date_results"] = list(reversed(replay["date_results"]))
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: replay,
    )
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_current_rule_factor_manifest",
        lambda **kwargs: pytest.fail(
            "builder must not run for governed calendar mismatch"
        ),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == [
        "runner_dates_do_not_match_governed_open_dates"
    ]
    assert result["database_unchanged"] is True
    assert not (trusted_root / "factor-manifest.json").exists()


def test_cli_fail_closes_invalid_builder_manifest_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    real_validator = (
        module.manifest_task.validate_stock_analysis_current_rule_factor_manifest
    )
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    invalid_manifest = _manifest("ready")
    invalid_manifest["canonical_manifest_sha256"] = "0" * 64
    monkeypatch.setattr(
        module.manifest_task,
        "build_stock_analysis_current_rule_factor_manifest",
        lambda **kwargs: invalid_manifest,
    )
    monkeypatch.setattr(
        module.manifest_task,
        "validate_stock_analysis_current_rule_factor_manifest",
        real_validator,
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["factor_manifest_validation_failed"]
    assert result["database_unchanged"] is True
    assert not (trusted_root / "factor-manifest.json").exists()


def test_cli_redacts_exception_details_and_main_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    db_path, trusted_root, catalog_path = _files(tmp_path)
    _patch_inputs_and_replay(module, monkeypatch, trusted_root)
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("vendor_token=TOP-SECRET")
        ),
    )

    result = _run(
        module,
        db_path=db_path,
        trusted_root=trusted_root,
        catalog_path=catalog_path,
    )
    assert result["status"] == "error"
    assert "TOP-SECRET" not in json.dumps(result)

    monkeypatch.setattr(
        module,
        "run_current_rule_factor_manifest_cli",
        lambda **kwargs: {
            "status": "gaps_found",
            "blockers": [],
            "database_unchanged": True,
        },
    )
    exit_code = module.main(
        [
            "--duckdb-path",
            str(db_path),
            "--trusted-evidence-root",
            str(trusted_root),
            "--approved-calendar-receipt",
            "calendar.json",
            "--source-availability-receipt",
            "source.json",
            "--version-tuple-file",
            "version.json",
            "--choice-stock-catalog-file",
            str(catalog_path),
            "--output-file",
            "gaps.json",
            "--evaluation-as-of-date",
            "2026-08-23",
        ]
    )
    printed = capsys.readouterr().out
    assert exit_code == module.EXIT_SUCCESS
    assert json.loads(printed)["status"] == "gaps_found"
    assert "\n  " not in printed
