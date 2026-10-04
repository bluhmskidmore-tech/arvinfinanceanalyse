from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from backend.app.governance import (
    stock_analysis_current_rule_factor_vendor_receipt as current_rule_receipt,
)
from scripts import (
    stock_analysis_current_rule_factor_vendor_dry_run as current_rule_dry_run,
)
from scripts import stock_analysis_page_gap_factor_vendor_dry_run as dry_run


class _FakeClient:
    def __init__(self, rows_by_date: dict[str, list[dict[str, object]]]) -> None:
        self.rows_by_date = rows_by_date
        self.calls: list[dict[str, object]] = []

    def adj_factor(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        return self.rows_by_date.get(str(kwargs["trade_date"]), [])


class _RetryClient(_FakeClient):
    def __init__(
        self,
        rows_by_date: dict[str, list[dict[str, object]]],
        *,
        failures_by_date: dict[str, list[Exception]],
    ) -> None:
        super().__init__(rows_by_date)
        self.failures_by_date = failures_by_date

    def adj_factor(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        trade_date = str(kwargs["trade_date"])
        failures = self.failures_by_date.get(trade_date, [])
        if failures:
            raise failures.pop(0)
        return self.rows_by_date.get(trade_date, [])


def _factor_manifest(db_path: Path) -> dict[str, object]:
    cells = [
        {"stock_code": "000001.SZ", "trade_date": "2026-01-05"},
        {"stock_code": "600000.SH", "trade_date": "2026-01-05"},
        {"stock_code": "000002.SZ", "trade_date": "2026-01-06"},
    ]
    db_sha = dry_run._evidence_helpers._file_sha256(db_path)
    target_sha = current_rule_receipt._canonical_json_sha256(cells)
    return {
        "manifest_kind": "stock_analysis_page_gap_factor_manifest_v1",
        "status": "gaps_found",
        "remediation_only": True,
        "strict_exact_date_lookup": True,
        "carry_forward_allowed": False,
        "fallback_allowed": False,
        "write_allowed": False,
        "historical_availability_proven": False,
        "certification_allowed": False,
        "downstream_materialization_allowed": False,
        "blockers": [],
        "target_cells": cells,
        "target_cell_count": 3,
        "target_cells_sha256": target_sha,
        "requested_unique_date_count": 2,
        "canonical_manifest_sha256": "A" * 64,
        "database": {
            "path": str(db_path.resolve()),
            "sha256_before": db_sha,
            "sha256_after": db_sha,
            "unchanged": True,
            "read_only": True,
        },
        "page_manifest_binding": {
            "path": str((db_path.parent / "page.json").resolve()),
            "file_sha256": "C" * 64,
            "canonical_manifest_sha256": "D" * 64,
            "manifest_kind": "stock_analysis_page_gap_manifest_v1",
            "page_id": "GAP-STOCK-ANALYSIS-PAGE",
            "page_route": "/stock-analysis",
            "page_metric_key": "data_health.adjustment_factor_gap",
            "database_path": str(db_path.resolve()),
            "database_sha256": db_sha,
            "page_gap_view_count": 4,
            "missing_factor_cell_count": 3,
        },
    }


def _write_manifest(root: Path, db_path: Path) -> Path:
    manifest = _factor_manifest(db_path)
    page_path = root / "page.json"
    page = {
        "manifest_kind": "stock_analysis_page_gap_manifest_v1",
        "status": "gaps_found",
        "blockers": [],
        "canonical_manifest_sha256": "D" * 64,
        "page_id": "GAP-STOCK-ANALYSIS-PAGE",
        "page_route": "/stock-analysis",
        "page_metric_key": "data_health.adjustment_factor_gap",
        "summary": {
            "page_gap_view_count_before": 4,
            "unique_missing_factor_cell_count": 3,
        },
        "database": dict(manifest["database"]),
        "missing_factor_cells": list(manifest["target_cells"]),
    }
    page_path.write_text(json.dumps(page), encoding="utf-8")
    manifest["page_manifest_binding"]["path"] = str(page_path.resolve())  # type: ignore[index]
    manifest["page_manifest_binding"]["file_sha256"] = (  # type: ignore[index]
        dry_run._evidence_helpers._file_sha256(page_path)
    )
    path = root / "factor.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _allow_formal_validators(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dry_run.manifest_task,
        "validate_stock_analysis_page_gap_factor_manifest",
        lambda manifest: (True, ()),
    )
    monkeypatch.setattr(
        dry_run.receipt_task.factor_manifest_task,
        "validate_stock_analysis_page_gap_factor_manifest",
        lambda manifest: (True, ()),
    )
    monkeypatch.setattr(
        dry_run.page_manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda manifest: (True, ()),
    )


def _client() -> _FakeClient:
    return _FakeClient(
        {
            "20260105": [
                {"ts_code": "000001.SZ", "trade_date": "20260105", "adj_factor": 1.1},
                {"ts_code": "600000.SH", "trade_date": "20260105", "adj_factor": 2.2},
                {"ts_code": "999999.SH", "trade_date": "20260105", "adj_factor": 9.9},
            ],
            "20260106": [
                {"ts_code": "000002.SZ", "trade_date": "20260106", "adj_factor": 3.3}
            ],
        }
    )


def test_dry_run_exact_match_persists_receipt_and_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"read-only-db-sentinel")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest_path = _write_manifest(evidence, db_path)
    _allow_formal_validators(monkeypatch)
    client = _client()

    result = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        client=client,
    )

    assert result["status"] == "ready"
    assert result["vendor_call_count"] == 2
    assert len(client.calls) == 2
    assert result["factor_approval_scope_sha256"]
    persisted = json.loads((evidence / "vendor.json").read_text(encoding="utf-8"))
    assert persisted["requested_cell_count"] == 3
    assert persisted["returned_cell_count"] == 3
    assert persisted["vendor_call_count"] == 2
    factor_binding = persisted["factor_manifest_binding"]
    page_binding = persisted["page_manifest_binding"]
    recomputed_scope = dry_run.receipt_task.factor_approval_scope_sha256(
        factor_manifest_file_sha256=factor_binding["file_sha256"],
        factor_manifest_canonical_sha256=factor_binding["canonical_manifest_sha256"],
        page_manifest_file_sha256=page_binding["file_sha256"],
        page_manifest_canonical_sha256=page_binding["canonical_manifest_sha256"],
        vendor_receipt_file_sha256=dry_run._evidence_helpers._file_sha256(
            evidence / "vendor.json"
        ),
        vendor_receipt_canonical_sha256=persisted["canonical_receipt_sha256"],
        database_sha256_before=persisted["database"]["sha256_before"],
        returned_cells_sha256=persisted["returned_cells_sha256"],
        target_cell_count=persisted["returned_cell_count"],
        source_version=persisted["proposed_source_version"],
        run_id=persisted["proposed_run_id"],
    )
    assert result["factor_approval_scope_sha256"] == recomputed_scope
    assert db_path.read_bytes() == b"read-only-db-sentinel"


def test_call_budget_blocks_before_client_use(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest_path = _write_manifest(evidence, db_path)
    _allow_formal_validators(monkeypatch)
    client = _client()

    result = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=1,
        client=client,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["vendor_call_budget_exceeded"]
    assert client.calls == []
    assert not (evidence / "vendor.json").exists()


def test_missing_or_duplicate_vendor_cell_blocks_without_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest_path = _write_manifest(evidence, db_path)
    _allow_formal_validators(monkeypatch)
    bad = _client()
    bad.rows_by_date["20260106"] = []

    result = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        client=bad,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["factor_vendor_exact_match_failed"]
    assert not (evidence / "vendor.json").exists()


def test_existing_output_and_path_escape_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest_path = _write_manifest(evidence, db_path)
    (evidence / "vendor.json").write_text("preserve", encoding="utf-8")
    _allow_formal_validators(monkeypatch)

    existing = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        client=_client(),
    )
    escaped = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file=tmp_path / "outside.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        client=_client(),
    )

    assert existing["status"] == "error"
    assert escaped["status"] == "error"
    assert (evidence / "vendor.json").read_text(encoding="utf-8") == "preserve"
    assert not (tmp_path / "outside.json").exists()


def test_shared_vendor_payload_helpers_are_locked() -> None:
    assert dry_run._vendor_helpers._target_rows_from_vendor_payload is (
        current_rule_dry_run._target_rows_from_vendor_payload
    )
    assert dry_run._vendor_helpers._strict_exact_match is (
        current_rule_dry_run._strict_exact_match
    )


def test_external_page_manifest_tamper_blocks_before_vendor_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest_path = _write_manifest(evidence, db_path)
    page_path = evidence / "page.json"
    page = json.loads(page_path.read_text(encoding="utf-8"))
    page["missing_factor_cells"] = page["missing_factor_cells"][:-1]
    page_path.write_text(json.dumps(page), encoding="utf-8")
    _allow_formal_validators(monkeypatch)
    client = _client()

    result = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        client=client,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["page_manifest_external_binding_failed"]
    assert client.calls == []
    assert not (evidence / "vendor.json").exists()


def test_symlinked_evidence_file_is_rejected_before_vendor_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"db")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    real_root = tmp_path / "outside"
    real_root.mkdir()
    real_manifest = _write_manifest(real_root, db_path)
    linked_manifest = evidence / "factor.json"
    try:
        linked_manifest.symlink_to(real_manifest)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    _allow_formal_validators(monkeypatch)
    client = _client()

    result = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=linked_manifest,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        client=client,
    )

    assert result["status"] == "error"
    assert client.calls == []
    assert not (evidence / "vendor.json").exists()


def test_transient_vendor_failure_retries_then_persists_exact_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"read-only-db-sentinel")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest_path = _write_manifest(evidence, db_path)
    _allow_formal_validators(monkeypatch)
    base_client = _client()
    client = _RetryClient(
        base_client.rows_by_date,
        failures_by_date={
            "20260105": [requests.exceptions.ConnectionError("credential=secret")]
        },
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(dry_run.time, "sleep", sleep_calls.append)

    result = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        retry_attempts=3,
        retry_sleep_seconds=0.25,
        client=client,
    )

    assert result["status"] == "ready"
    assert result["vendor_call_count"] == 2
    assert [call["trade_date"] for call in client.calls] == [
        "20260105",
        "20260105",
        "20260106",
    ]
    assert sleep_calls == [0.25]
    receipt = json.loads((evidence / "vendor.json").read_text(encoding="utf-8"))
    assert receipt["vendor_call_count"] == 2
    assert db_path.read_bytes() == b"read-only-db-sentinel"


def test_non_retryable_vendor_failure_fails_immediately_without_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"read-only-db-sentinel")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest_path = _write_manifest(evidence, db_path)
    _allow_formal_validators(monkeypatch)
    base_client = _client()
    client = _RetryClient(
        base_client.rows_by_date,
        failures_by_date={"20260105": [ValueError("credential=secret")]},
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(dry_run.time, "sleep", sleep_calls.append)

    result = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        retry_attempts=3,
        retry_sleep_seconds=0.25,
        client=client,
    )

    assert result["status"] == "error"
    assert result["blockers"] == ["factor_vendor_dry_run_failed_ValueError"]
    assert len(client.calls) == 1
    assert sleep_calls == []
    assert not (evidence / "vendor.json").exists()
    assert db_path.read_bytes() == b"read-only-db-sentinel"
    assert "credential" not in json.dumps(result)


def test_retry_exhaustion_fails_closed_without_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "moss.duckdb"
    db_path.write_bytes(b"read-only-db-sentinel")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest_path = _write_manifest(evidence, db_path)
    _allow_formal_validators(monkeypatch)
    base_client = _client()
    client = _RetryClient(
        base_client.rows_by_date,
        failures_by_date={
            "20260105": [
                requests.exceptions.ConnectionError("credential=secret")
                for _ in range(3)
            ]
        },
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(dry_run.time, "sleep", sleep_calls.append)

    result = dry_run.run_page_gap_factor_vendor_dry_run(
        duckdb_path=db_path,
        trusted_evidence_root=evidence,
        factor_manifest_file=manifest_path,
        output_file="vendor.json",
        captured_at="2026-08-24T10:00:00Z",
        max_vendor_calls=2,
        retry_attempts=3,
        retry_sleep_seconds=0.25,
        client=client,
    )

    assert result["status"] == "error"
    assert result["blockers"] == ["factor_vendor_dry_run_failed_ConnectionError"]
    assert result["vendor_call_count"] == 0
    assert len(client.calls) == 3
    assert sleep_calls == [0.25, 0.25]
    assert not (evidence / "vendor.json").exists()
    assert db_path.read_bytes() == b"read-only-db-sentinel"
    assert "credential" not in json.dumps(result)


def test_cli_forwards_explicit_retry_controls(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}

    def _fake_run(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "blocked"}

    monkeypatch.setattr(dry_run, "run_page_gap_factor_vendor_dry_run", _fake_run)

    exit_code = dry_run.main(
        [
            "--duckdb-path",
            "db.duckdb",
            "--trusted-evidence-root",
            "evidence",
            "--factor-manifest-file",
            "factor.json",
            "--output-file",
            "vendor.json",
            "--captured-at",
            "2026-08-24T10:00:00Z",
            "--max-vendor-calls",
            "87",
            "--retry-attempts",
            "5",
            "--retry-sleep-seconds",
            "0.125",
        ]
    )

    assert exit_code == dry_run.EXIT_BLOCKED
    assert captured["retry_attempts"] == 5
    assert captured["retry_sleep_seconds"] == 0.125
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
