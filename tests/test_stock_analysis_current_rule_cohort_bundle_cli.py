from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _load_module():
    return load_module(
        "scripts.stock_analysis_current_rule_cohort_bundle",
        "scripts/stock_analysis_current_rule_cohort_bundle.py",
    )


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _ready_calendar() -> dict[str, object]:
    return {
        "authority_status": "approved",
        "canonical_receipt_sha256": "A" * 64,
        "request": {"start_date": "2026-07-01", "end_date": "2026-07-03"},
        "calendar_rows": [
            {"cal_date": "2026-07-01", "is_open": 1},
            {"cal_date": "2026-07-02", "is_open": 1},
            {"cal_date": "2026-07-03", "is_open": 1},
        ],
    }


def _version_tuple() -> dict[str, object]:
    return {
        "candidate_rule_version": "rv_candidate_history_current",
        "stock_candidate_selection_formula_version": "rv_livermore_stock_candidates_bundle_v7",
        "candidate_outcome_formula_version": "fv_livermore_candidate_forward_close_dual_adjust_v2",
        "execution_formula_version": "fv_livermore_candidate_execution_dual_adjust_v5",
        "matched_baseline_formula_version": "fv_livermore_matched_baseline_v3",
        "market_gate_rule_version": "rv_market_gate_current_v2",
        "signal_confluence_rule_version": "rv_signal_confluence_current_v4",
        "macro_formula_version": "fv_macro_bundle_current_v1",
        "candidate_source_version": "sv_candidate_current",
        "execution_source_version": "sv_execution_current",
        "matched_baseline_source_version": "sv_matched_baseline_current",
        "macro_source_version": "sv_macro_current",
        "theme_overlay_fingerprint": "overlay-fingerprint-1",
        "choice_catalog_fingerprint": "catalog-fingerprint-1",
        "stock_candidate_selection_policy": "exp3b",
        "decision_metric_basis": "net_next_open_adj",
        "coverage_authority_mode": "approved_calendar_receipt_v1",
        "strict_coverage": True,
        "fallback_covered": False,
    }


def _source_receipt() -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_kind": "pit_source_availability_v1",
        "captured_at": "2026-08-23T10:00:00+08:00",
        "sources": [
            {
                "table": "choice_stock_daily_observation",
                "source_version": "sv-obs",
                "vendor_version": "vv-choice",
                "rule_version": "rv-obs",
                "run_id": "run-obs",
                "available_at": "2026-07-03",
            }
        ],
    }


def _bundle_result(batch_dir: Path) -> dict[str, object]:
    batch_dir.mkdir(parents=True, exist_ok=True)
    bundle = batch_dir / "bundle.json"
    dry = batch_dir / "dry-run-receipt.json"
    bundle.write_text("{}", encoding="utf-8")
    dry.write_text(
        json.dumps({"bundle_path": str(bundle.resolve()), "canonical_receipt_sha256": "STALE"}, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "bundle_path": str(bundle.resolve()),
        "bundle_sha256": "B" * 64,
        "dry_run_receipt_path": str(dry.resolve()),
        "dry_run_receipt_sha256": "C" * 64,
        "zero_signal_certificate_paths": [],
        "summary": {"completed_dates": 20, "matched_entry_count": 100},
    }


def test_cli_runs_ready_path_and_renames_pending_batch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    calendar_path = _write_json(trusted_root / "calendar.json", _ready_calendar())
    source_path = _write_json(trusted_root / "source.json", _source_receipt())
    version_path = _write_json(trusted_root / "version.json", _version_tuple())

    monkeypatch.setattr(module.producer_task, "validate_stock_analysis_calendar_receipt", lambda payload: (True, []))
    monkeypatch.setattr(module.producer_task, "_existing_directory", lambda path, field_name: Path(path).resolve())
    monkeypatch.setattr(module.producer_task, "_trusted_existing_file", lambda trusted_root, raw_path, field_name: Path(raw_path).resolve())
    monkeypatch.setattr(module.producer_task, "_load_json_object", lambda path, field_name: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(module.producer_task, "_freeze_version_tuple", lambda payload: dict(payload))
    monkeypatch.setattr(module.producer_task, "_open_calendar_dates", lambda payload: ["2026-07-01", "2026-07-02", "2026-07-03"])
    monkeypatch.setattr(module.producer_task, "_sha256_text", lambda value, field_name: str(value))
    monkeypatch.setattr(module.producer_task, "_canonical_sha256", lambda payload: "S" * 64)
    monkeypatch.setattr(module.producer_task, "derive_expected_stock_analysis_current_rule_governed_run_id", lambda **kwargs: "governed-123")
    
    def fake_build_dry_run_receipt(duckdb_path, bundle_path, receipt_path, created_at):
        payload = {
            "bundle_path": str(Path(bundle_path).resolve()),
            "canonical_receipt_sha256": "R" * 64,
        }
        Path(receipt_path).write_text(
            json.dumps(payload, sort_keys=True),
            encoding="utf-8",
        )
        return payload

    monkeypatch.setattr(
        module.producer_task,
        "build_stock_analysis_current_rule_cohort_dry_run",
        fake_build_dry_run_receipt,
    )

    replay_calls: list[dict[str, object]] = []
    evidence_calls: list[dict[str, object]] = []
    produce_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: replay_calls.append(dict(kwargs)) or {
            "requested_range": {"start_date": "2026-07-01", "end_date": "2026-07-03"},
            "summary": {"status_counts": {"selection_completed_with_signals": 3}, "attempted_dates": 3},
            "blockers": [],
            "diagnostic_limitations": ["selection_only_diagnostic_no_replay_maturity"],
            "date_results": [{"trade_date": "2026-07-01", "status": "selection_completed_with_signals"}],
        },
    )
    monkeypatch.setattr(
        module.evidence_task,
        "collect_stock_analysis_current_rule_cohort_evidence",
        lambda **kwargs: evidence_calls.append(dict(kwargs)) or {
            "status": "ready",
            "counts": {"completed_dates": 20, "matched_entry_count": 100},
            "blockers": [],
            "date_evidence": [{"trade_date": "2026-07-01", "signal_facts": [], "runner_result": {}}],
        },
    )

    def fake_produce(**kwargs):
        produce_calls.append(dict(kwargs))
        return _bundle_result(Path(kwargs["output_root"]) / str(kwargs["batch_name"]))

    monkeypatch.setattr(module.producer_task, "produce_stock_analysis_current_rule_cohort_bundle", fake_produce)

    result = module.run_current_rule_cohort_bundle_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt=calendar_path,
        source_availability_receipts=[source_path],
        version_tuple_file=version_path,
        output_root=output_root,
        batch_name="batch-a",
        cohort_id="cohort-a",
        run_id="run-a",
        evaluation_as_of_date="2026-08-23",
        choice_stock_catalog_file=catalog,
        max_workers=3,
        created_at="2026-08-23T10:00:00Z",
    )

    assert result["status"] == "ready"
    assert result["blockers"] == []
    assert result["replay"]["report_blockers"] == []
    assert result["replay"]["diagnostic_limitations"] == [
        "selection_only_diagnostic_no_replay_maturity"
    ]
    assert result["governed_run_id"] == "governed-123"
    assert result["database_unchanged"] is True
    assert replay_calls[0]["start_date"] == "2026-07-01"
    assert replay_calls[0]["end_date"] == "2026-07-03"
    assert evidence_calls[0]["governed_run_id"] == "governed-123"
    assert produce_calls and str(produce_calls[0]["batch_name"]).startswith(".pending-batch-a-")
    assert str(result["bundle"]["bundle_path"]).endswith("batch-a\\bundle.json") or str(result["bundle"]["bundle_path"]).endswith("batch-a/bundle.json")
    final_receipt_path = output_root / "batch-a" / "dry-run-receipt.json"
    final_receipt = json.loads(final_receipt_path.read_text(encoding="utf-8"))
    assert final_receipt["bundle_path"] == str((output_root / "batch-a" / "bundle.json").resolve())
    assert final_receipt["canonical_receipt_sha256"] == "R" * 64
    assert result["bundle"]["dry_run_receipt_sha256"] == "R" * 64
    assert (output_root / "batch-a" / "bundle.json").is_file()
    assert not any(path.name.startswith(".pending-batch-a-") for path in output_root.iterdir())


def test_cli_blocks_when_evidence_is_not_ready_and_never_calls_producer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    calendar_path = _write_json(trusted_root / "calendar.json", _ready_calendar())
    source_path = _write_json(trusted_root / "source.json", _source_receipt())
    version_path = _write_json(trusted_root / "version.json", _version_tuple())

    monkeypatch.setattr(module.producer_task, "validate_stock_analysis_calendar_receipt", lambda payload: (True, []))
    monkeypatch.setattr(module.producer_task, "_existing_directory", lambda path, field_name: Path(path).resolve())
    monkeypatch.setattr(module.producer_task, "_trusted_existing_file", lambda trusted_root, raw_path, field_name: Path(raw_path).resolve())
    monkeypatch.setattr(module.producer_task, "_load_json_object", lambda path, field_name: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(module.producer_task, "_freeze_version_tuple", lambda payload: dict(payload))
    monkeypatch.setattr(module.producer_task, "_open_calendar_dates", lambda payload: ["2026-07-01", "2026-07-02"])
    monkeypatch.setattr(module.producer_task, "_sha256_text", lambda value, field_name: str(value))
    monkeypatch.setattr(module.producer_task, "_canonical_sha256", lambda payload: "S" * 64)
    monkeypatch.setattr(module.producer_task, "derive_expected_stock_analysis_current_rule_governed_run_id", lambda **kwargs: "governed-123")
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: {
            "summary": {},
            "blockers": [],
            "diagnostic_limitations": ["calendar_authority_unavailable"],
            "date_results": [],
        },
    )
    monkeypatch.setattr(
        module.evidence_task,
        "collect_stock_analysis_current_rule_cohort_evidence",
        lambda **kwargs: {
            "status": "blocked",
            "counts": {"completed_dates": 19, "matched_entry_count": 99},
            "blockers": ["completed_dates_below_threshold", "matched_entry_count_below_threshold"],
            "date_evidence": [],
        },
    )
    monkeypatch.setattr(
        module.producer_task,
        "produce_stock_analysis_current_rule_cohort_bundle",
        lambda **kwargs: pytest.fail("producer must not run when evidence is blocked"),
    )

    result = module.run_current_rule_cohort_bundle_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt=calendar_path,
        source_availability_receipts=[source_path],
        version_tuple_file=version_path,
        output_root=output_root,
        batch_name="batch-b",
        cohort_id="cohort-b",
        run_id="run-b",
        evaluation_as_of_date="2026-08-23",
        choice_stock_catalog_file=catalog,
        max_workers=2,
        created_at="2026-08-23T10:00:00Z",
    )

    assert result["status"] == "blocked"
    assert "completed_dates_below_threshold" in result["blockers"]
    assert "calendar_authority_unavailable" not in result["blockers"]
    assert result["replay"]["diagnostic_limitations"] == [
        "calendar_authority_unavailable"
    ]
    assert result["evidence"]["blockers"] == [
        "completed_dates_below_threshold",
        "matched_entry_count_below_threshold",
    ]
    assert "bundle" not in result
    assert not (output_root / "batch-b").exists()


def test_cli_errors_when_version_tuple_file_escapes_trusted_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    calendar_path = _write_json(trusted_root / "calendar.json", _ready_calendar())
    source_path = _write_json(trusted_root / "source.json", _source_receipt())
    outside_version = _write_json(tmp_path / "outside-version.json", _version_tuple())

    def fake_trusted_existing_file(*, trusted_root, raw_path, field_name):
        path = Path(raw_path).resolve()
        if field_name == "version_tuple_file":
            raise module.producer_task.CurrentRuleCohortError(
                "version_tuple_file must stay within its governed root"
            )
        return path

    monkeypatch.setattr(module.producer_task, "_existing_directory", lambda path, field_name: Path(path).resolve())
    monkeypatch.setattr(module.producer_task, "_trusted_existing_file", fake_trusted_existing_file)
    monkeypatch.setattr(module.producer_task, "_load_json_object", lambda path, field_name: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(module.producer_task, "validate_stock_analysis_calendar_receipt", lambda payload: (True, []))
    monkeypatch.setattr(module.producer_task, "_open_calendar_dates", lambda payload: ["2026-07-01", "2026-07-02"])
    monkeypatch.setattr(module.producer_task, "_freeze_version_tuple", lambda payload: dict(payload))

    result = module.run_current_rule_cohort_bundle_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt=calendar_path,
        source_availability_receipts=[source_path],
        version_tuple_file=outside_version,
        output_root=output_root,
        batch_name="batch-c",
        cohort_id="cohort-c",
        run_id="run-c",
        evaluation_as_of_date="2026-08-23",
        choice_stock_catalog_file=catalog,
        max_workers=2,
        created_at="2026-08-23T10:00:00Z",
    )

    assert result["status"] == "error"
    assert any("version_tuple_file must stay within its governed root" in blocker for blocker in result["blockers"])


def test_cli_errors_when_source_receipt_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    calendar_path = _write_json(trusted_root / "calendar.json", _ready_calendar())
    version_path = _write_json(trusted_root / "version.json", _version_tuple())
    missing_source = trusted_root / "missing-source.json"

    def fake_trusted_existing_file(*, trusted_root, raw_path, field_name):
        if field_name == "source_availability_receipts[0]":
            raise module.producer_task.CurrentRuleCohortError(
                "source_availability_receipts[0] must be an existing file"
            )
        return Path(raw_path).resolve()

    monkeypatch.setattr(module.producer_task, "_existing_directory", lambda path, field_name: Path(path).resolve())
    monkeypatch.setattr(module.producer_task, "_trusted_existing_file", fake_trusted_existing_file)
    monkeypatch.setattr(module.producer_task, "_load_json_object", lambda path, field_name: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(module.producer_task, "validate_stock_analysis_calendar_receipt", lambda payload: (True, []))
    monkeypatch.setattr(module.producer_task, "_open_calendar_dates", lambda payload: ["2026-07-01", "2026-07-02"])
    monkeypatch.setattr(module.producer_task, "_freeze_version_tuple", lambda payload: dict(payload))

    result = module.run_current_rule_cohort_bundle_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt=calendar_path,
        source_availability_receipts=[missing_source],
        version_tuple_file=version_path,
        output_root=output_root,
        batch_name="batch-d",
        cohort_id="cohort-d",
        run_id="run-d",
        evaluation_as_of_date="2026-08-23",
        choice_stock_catalog_file=catalog,
        max_workers=2,
        created_at="2026-08-23T10:00:00Z",
    )

    assert result["status"] == "error"
    assert any("source_availability_receipts[0] must be an existing file" in blocker for blocker in result["blockers"])


def test_cli_blocks_when_db_hash_changes_before_producer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    calendar_path = _write_json(trusted_root / "calendar.json", _ready_calendar())
    source_path = _write_json(trusted_root / "source.json", _source_receipt())
    version_path = _write_json(trusted_root / "version.json", _version_tuple())

    monkeypatch.setattr(module.producer_task, "validate_stock_analysis_calendar_receipt", lambda payload: (True, []))
    monkeypatch.setattr(module.producer_task, "_existing_directory", lambda path, field_name: Path(path).resolve())
    monkeypatch.setattr(module.producer_task, "_trusted_existing_file", lambda trusted_root, raw_path, field_name: Path(raw_path).resolve())
    monkeypatch.setattr(module.producer_task, "_load_json_object", lambda path, field_name: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(module.producer_task, "_freeze_version_tuple", lambda payload: dict(payload))
    monkeypatch.setattr(module.producer_task, "_open_calendar_dates", lambda payload: ["2026-07-01", "2026-07-02"])
    monkeypatch.setattr(module.producer_task, "_sha256_text", lambda value, field_name: str(value))
    monkeypatch.setattr(module.producer_task, "_canonical_sha256", lambda payload: "S" * 64)
    monkeypatch.setattr(module.producer_task, "derive_expected_stock_analysis_current_rule_governed_run_id", lambda **kwargs: "governed-123")
    monkeypatch.setattr(module, "build_current_rule_replay_dry_run", lambda **kwargs: {"summary": {}, "date_results": []})
    monkeypatch.setattr(
        module.evidence_task,
        "collect_stock_analysis_current_rule_cohort_evidence",
        lambda **kwargs: pytest.fail("evidence must not run after replay hash drift"),
    )
    monkeypatch.setattr(
        module.producer_task,
        "produce_stock_analysis_current_rule_cohort_bundle",
        lambda **kwargs: pytest.fail("producer must not run when DB hash changed"),
    )
    hashes = iter(["A" * 64, "B" * 64, "B" * 64])
    monkeypatch.setattr(module, "_file_sha256", lambda path: next(hashes))

    result = module.run_current_rule_cohort_bundle_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt=calendar_path,
        source_availability_receipts=[source_path],
        version_tuple_file=version_path,
        output_root=output_root,
        batch_name="batch-e",
        cohort_id="cohort-e",
        run_id="run-e",
        evaluation_as_of_date="2026-08-23",
        choice_stock_catalog_file=catalog,
        max_workers=2,
        created_at="2026-08-23T10:00:00Z",
    )

    assert result["status"] == "blocked"
    assert "duckdb_hash_changed_during_replay" in result["blockers"]
    assert result["database_unchanged"] is False


def test_cli_preserves_preexisting_final_batch_when_replay_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    calendar_path = _write_json(trusted_root / "calendar.json", _ready_calendar())
    source_path = _write_json(trusted_root / "source.json", _source_receipt())
    version_path = _write_json(trusted_root / "version.json", _version_tuple())
    final_batch = output_root / "batch-existing"
    final_batch.mkdir()
    sentinel = final_batch / "sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")

    monkeypatch.setattr(module.producer_task, "validate_stock_analysis_calendar_receipt", lambda payload: (True, []))
    monkeypatch.setattr(module.producer_task, "_existing_directory", lambda path, field_name: Path(path).resolve())
    monkeypatch.setattr(module.producer_task, "_trusted_existing_file", lambda trusted_root, raw_path, field_name: Path(raw_path).resolve())
    monkeypatch.setattr(module.producer_task, "_load_json_object", lambda path, field_name: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(module.producer_task, "_freeze_version_tuple", lambda payload: dict(payload))
    monkeypatch.setattr(module.producer_task, "_open_calendar_dates", lambda payload: ["2026-07-01", "2026-07-02"])
    monkeypatch.setattr(module.producer_task, "_sha256_text", lambda value, field_name: str(value))
    monkeypatch.setattr(module.producer_task, "_canonical_sha256", lambda payload: "S" * 64)
    monkeypatch.setattr(module.producer_task, "derive_expected_stock_analysis_current_rule_governed_run_id", lambda **kwargs: "governed-123")
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("replay boom")),
    )

    result = module.run_current_rule_cohort_bundle_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt=calendar_path,
        source_availability_receipts=[source_path],
        version_tuple_file=version_path,
        output_root=output_root,
        batch_name="batch-existing",
        cohort_id="cohort-existing",
        run_id="run-existing",
        evaluation_as_of_date="2026-08-23",
        choice_stock_catalog_file=catalog,
        max_workers=2,
        created_at="2026-08-23T10:00:00Z",
    )

    assert result["status"] == "error"
    assert any("replay boom" in blocker for blocker in result["blockers"])
    assert sentinel.read_text(encoding="utf-8") == "keep-me"
    assert final_batch.is_dir()


def test_cli_cleans_only_new_final_batch_when_hash_changes_after_final_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    calendar_path = _write_json(trusted_root / "calendar.json", _ready_calendar())
    source_path = _write_json(trusted_root / "source.json", _source_receipt())
    version_path = _write_json(trusted_root / "version.json", _version_tuple())
    keep_dir = output_root / "keep-existing"
    keep_dir.mkdir()
    keep_sentinel = keep_dir / "sentinel.txt"
    keep_sentinel.write_text("keep-me", encoding="utf-8")

    monkeypatch.setattr(module.producer_task, "validate_stock_analysis_calendar_receipt", lambda payload: (True, []))
    monkeypatch.setattr(module.producer_task, "_existing_directory", lambda path, field_name: Path(path).resolve())
    monkeypatch.setattr(module.producer_task, "_trusted_existing_file", lambda trusted_root, raw_path, field_name: Path(raw_path).resolve())
    monkeypatch.setattr(module.producer_task, "_load_json_object", lambda path, field_name: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(module.producer_task, "_freeze_version_tuple", lambda payload: dict(payload))
    monkeypatch.setattr(module.producer_task, "_open_calendar_dates", lambda payload: ["2026-07-01", "2026-07-02", "2026-07-03"])
    monkeypatch.setattr(module.producer_task, "_sha256_text", lambda value, field_name: str(value))
    monkeypatch.setattr(module.producer_task, "_canonical_sha256", lambda payload: "S" * 64)
    monkeypatch.setattr(module.producer_task, "derive_expected_stock_analysis_current_rule_governed_run_id", lambda **kwargs: "governed-123")

    def fake_build_dry_run_receipt(duckdb_path, bundle_path, receipt_path, created_at):
        payload = {
            "bundle_path": str(Path(bundle_path).resolve()),
            "canonical_receipt_sha256": "R" * 64,
        }
        Path(receipt_path).write_text(
            json.dumps(payload, sort_keys=True),
            encoding="utf-8",
        )
        return payload

    monkeypatch.setattr(
        module.producer_task,
        "build_stock_analysis_current_rule_cohort_dry_run",
        fake_build_dry_run_receipt,
    )
    monkeypatch.setattr(
        module,
        "build_current_rule_replay_dry_run",
        lambda **kwargs: {
            "requested_range": {"start_date": "2026-07-01", "end_date": "2026-07-03"},
            "summary": {"status_counts": {"selection_completed_with_signals": 3}, "attempted_dates": 3},
            "blockers": [],
            "date_results": [{"trade_date": "2026-07-01", "status": "selection_completed_with_signals"}],
        },
    )
    monkeypatch.setattr(
        module.evidence_task,
        "collect_stock_analysis_current_rule_cohort_evidence",
        lambda **kwargs: {
            "status": "ready",
            "counts": {"completed_dates": 20, "matched_entry_count": 100},
            "blockers": [],
            "date_evidence": [{"trade_date": "2026-07-01", "signal_facts": [], "runner_result": {}}],
        },
    )
    monkeypatch.setattr(
        module.producer_task,
        "produce_stock_analysis_current_rule_cohort_bundle",
        lambda **kwargs: _bundle_result(Path(kwargs["output_root"]) / str(kwargs["batch_name"])),
    )
    hashes = iter(["A" * 64, "A" * 64, "A" * 64, "A" * 64, "B" * 64])
    monkeypatch.setattr(module, "_file_sha256", lambda path: next(hashes))

    result = module.run_current_rule_cohort_bundle_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt=calendar_path,
        source_availability_receipts=[source_path],
        version_tuple_file=version_path,
        output_root=output_root,
        batch_name="batch-cleanup",
        cohort_id="cohort-cleanup",
        run_id="run-cleanup",
        evaluation_as_of_date="2026-08-23",
        choice_stock_catalog_file=catalog,
        max_workers=2,
        created_at="2026-08-23T10:00:00Z",
    )

    assert result["status"] == "blocked"
    assert "duckdb_hash_changed_after_final_dry_run" in result["blockers"]
    assert not (output_root / "batch-cleanup").exists()
    assert keep_sentinel.read_text(encoding="utf-8") == "keep-me"
    assert keep_dir.is_dir()


def test_cli_rejects_batch_name_traversal_without_creating_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}", encoding="utf-8")
    calendar_path = _write_json(trusted_root / "calendar.json", _ready_calendar())
    source_path = _write_json(trusted_root / "source.json", _source_receipt())
    version_path = _write_json(trusted_root / "version.json", _version_tuple())

    monkeypatch.setattr(module.producer_task, "validate_stock_analysis_calendar_receipt", lambda payload: (True, []))
    monkeypatch.setattr(module.producer_task, "_existing_directory", lambda path, field_name: Path(path).resolve())
    monkeypatch.setattr(module.producer_task, "_trusted_existing_file", lambda trusted_root, raw_path, field_name: Path(raw_path).resolve())
    monkeypatch.setattr(module.producer_task, "_load_json_object", lambda path, field_name: json.loads(Path(path).read_text(encoding="utf-8")))
    monkeypatch.setattr(module.producer_task, "_freeze_version_tuple", lambda payload: dict(payload))
    monkeypatch.setattr(module.producer_task, "_open_calendar_dates", lambda payload: ["2026-07-01", "2026-07-02"])
    monkeypatch.setattr(module.producer_task, "_sha256_text", lambda value, field_name: str(value))
    monkeypatch.setattr(module.producer_task, "_canonical_sha256", lambda payload: "S" * 64)
    monkeypatch.setattr(module.producer_task, "derive_expected_stock_analysis_current_rule_governed_run_id", lambda **kwargs: "governed-123")
    monkeypatch.setattr(module, "build_current_rule_replay_dry_run", lambda **kwargs: pytest.fail("replay must not run for invalid batch_name"))

    result = module.run_current_rule_cohort_bundle_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        approved_calendar_receipt=calendar_path,
        source_availability_receipts=[source_path],
        version_tuple_file=version_path,
        output_root=output_root,
        batch_name="../escaped",
        cohort_id="cohort-t",
        run_id="run-t",
        evaluation_as_of_date="2026-08-23",
        choice_stock_catalog_file=catalog,
        max_workers=2,
        created_at="2026-08-23T10:00:00Z",
    )

    assert result["status"] == "error"
    assert any("batch_name must be a single safe path segment" in blocker for blocker in result["blockers"])
    assert not (tmp_path / "escaped").exists()


def test_cli_rejects_temp_batch_link_swap_before_delete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    output_root = tmp_path / "output"
    output_root.mkdir()
    temp_batch = output_root / ".pending-batch-x"
    temp_batch.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")

    path_type = type(temp_batch)
    original_exists = path_type.exists
    original_is_symlink = path_type.is_symlink
    swapped = {"value": False}

    def fake_exists(self: Path) -> bool:
        exists = original_exists(self)
        if self == temp_batch and exists and not swapped["value"]:
            swapped["value"] = True
        return exists

    def fake_is_symlink(self: Path) -> bool:
        if self == temp_batch and swapped["value"]:
            return True
        return original_is_symlink(self)

    monkeypatch.setattr(path_type, "exists", fake_exists, raising=True)
    monkeypatch.setattr(path_type, "is_symlink", fake_is_symlink, raising=True)

    with pytest.raises(
        module.producer_task.CurrentRuleCohortError,
        match="temporary batch directory contains forbidden symlink/junction component",
    ):
        module._safe_remove_temp_batch(temp_batch, output_root=output_root)

    assert temp_batch.is_dir()
    assert sentinel.read_text(encoding="utf-8") == "keep-me"


def test_cli_rejects_final_batch_link_swap_before_delete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    output_root = tmp_path / "output"
    output_root.mkdir()
    final_batch = output_root / "batch-x"
    final_batch.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")

    path_type = type(final_batch)
    original_exists = path_type.exists
    original_is_symlink = path_type.is_symlink
    swapped = {"value": False}

    def fake_exists(self: Path) -> bool:
        exists = original_exists(self)
        if self == final_batch and exists and not swapped["value"]:
            swapped["value"] = True
        return exists

    def fake_is_symlink(self: Path) -> bool:
        if self == final_batch and swapped["value"]:
            return True
        return original_is_symlink(self)

    monkeypatch.setattr(path_type, "exists", fake_exists, raising=True)
    monkeypatch.setattr(path_type, "is_symlink", fake_is_symlink, raising=True)

    with pytest.raises(
        module.producer_task.CurrentRuleCohortError,
        match="final batch directory contains forbidden symlink/junction component",
    ):
        module._safe_remove_final_batch(final_batch, output_root=output_root)

    assert final_batch.is_dir()
    assert sentinel.read_text(encoding="utf-8") == "keep-me"


def test_cli_rejects_temp_receipt_link_swap_before_unlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    output_root = tmp_path / "output"
    output_root.mkdir()
    temp_batch = output_root / ".pending-batch-y"
    temp_batch.mkdir()
    receipt = temp_batch / "dry-run-receipt.json"
    receipt.write_text("{}", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")

    path_type = type(receipt)
    original_exists = path_type.exists
    original_is_symlink = path_type.is_symlink
    swapped = {"value": False}

    def fake_exists(self: Path) -> bool:
        exists = original_exists(self)
        if self == receipt and exists and not swapped["value"]:
            swapped["value"] = True
        return exists

    def fake_is_symlink(self: Path) -> bool:
        if self == receipt and swapped["value"]:
            return True
        return original_is_symlink(self)

    monkeypatch.setattr(path_type, "exists", fake_exists, raising=True)
    monkeypatch.setattr(path_type, "is_symlink", fake_is_symlink, raising=True)

    with pytest.raises(
        module.producer_task.CurrentRuleCohortError,
        match="dry_run_receipt_path contains forbidden symlink/junction component",
    ):
        module._remove_file_if_present(
            receipt,
            governed_root=temp_batch,
            field_name="dry_run_receipt_path",
        )

    assert receipt.is_file()
    assert sentinel.read_text(encoding="utf-8") == "keep-me"


def test_cli_rejects_temp_batch_link_swap_before_rename(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    output_root = tmp_path / "output"
    output_root.mkdir()
    temp_batch = output_root / ".pending-batch-z"
    temp_batch.mkdir()
    final_batch = output_root / "batch-z"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")

    path_type = type(temp_batch)
    original_is_symlink = path_type.is_symlink
    swapped = {"value": True}

    def fake_is_symlink(self: Path) -> bool:
        if self == temp_batch and swapped["value"]:
            return True
        return original_is_symlink(self)

    monkeypatch.setattr(path_type, "is_symlink", fake_is_symlink, raising=True)

    with pytest.raises(
        module.producer_task.CurrentRuleCohortError,
        match="temporary batch directory contains forbidden symlink/junction component",
    ):
        module._safe_promote_temp_batch(
            temp_batch_dir=temp_batch,
            final_batch_dir=final_batch,
            output_root=output_root,
        )

    assert temp_batch.is_dir()
    assert not final_batch.exists()
    assert sentinel.read_text(encoding="utf-8") == "keep-me"


def test_cli_main_returns_structured_error_when_duckdb_missing(
    capsys,
) -> None:
    module = _load_module()

    exit_code = module.main(
        [
            "--duckdb-path",
            "F:/definitely-missing/stock-analysis.duckdb",
            "--trusted-evidence-root",
            "F:/trusted",
            "--approved-calendar-receipt",
            "F:/trusted/calendar.json",
            "--source-availability-receipt",
            "F:/trusted/source.json",
            "--version-tuple-file",
            "F:/trusted/version.json",
            "--output-root",
            "F:/output",
            "--batch-name",
            "batch-missing-db",
            "--cohort-id",
            "cohort-missing-db",
            "--run-id",
            "run-missing-db",
            "--evaluation-as-of-date",
            "2026-08-23",
            "--choice-stock-catalog-file",
            "F:/catalog.json",
        ]
    )

    parsed = json.loads(capsys.readouterr().out)
    assert exit_code == module.EXIT_BLOCKED
    assert parsed["status"] == "error"
    assert any("duckdb_path must be an existing file" in blocker for blocker in parsed["blockers"])


def test_cli_main_prints_json_and_returns_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "run_current_rule_cohort_bundle_cli",
        lambda **kwargs: {"status": "blocked", "blockers": ["example"], "database_unchanged": True},
    )

    exit_code = module.main(
        [
            "--duckdb-path",
            "F:/db.duckdb",
            "--trusted-evidence-root",
            "F:/trusted",
            "--approved-calendar-receipt",
            "F:/trusted/calendar.json",
            "--source-availability-receipt",
            "F:/trusted/source.json",
            "--version-tuple-file",
            "F:/trusted/version.json",
            "--output-root",
            "F:/output",
            "--batch-name",
            "batch-z",
            "--cohort-id",
            "cohort-z",
            "--run-id",
            "run-z",
            "--evaluation-as-of-date",
            "2026-08-23",
            "--choice-stock-catalog-file",
            "F:/catalog.json",
        ]
    )

    parsed = json.loads(capsys.readouterr().out)
    assert exit_code == module.EXIT_BLOCKED
    assert parsed["status"] == "blocked"
    assert parsed["blockers"] == ["example"]
