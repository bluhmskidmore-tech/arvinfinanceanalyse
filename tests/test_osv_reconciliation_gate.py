from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "scripts" / "osv_reconciliation_gate.py"
RECORDS_PATH = ROOT / "docs" / "audits" / "osv-reconciliation-records.json"
NOW = datetime(2026, 8, 7, 0, 0, tzinfo=timezone.utc)
SCANNER_SHA256 = "e774e5770c31d60745c067be5f69bf3b46641b6d0e0ed87fd65e569cda35dc50"
LOCKFILES = ("backend/uv.lock", "frontend/package-lock.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ensure_scan_inputs(root: Path) -> None:
    backend_lock = root / "backend" / "uv.lock"
    frontend_lock = root / "frontend" / "package-lock.json"
    backend_lock.parent.mkdir(parents=True, exist_ok=True)
    frontend_lock.parent.mkdir(parents=True, exist_ok=True)
    if not backend_lock.exists():
        backend_lock.write_text("version = 1\n", encoding="utf-8")
    if not frontend_lock.exists():
        frontend_lock.write_text('{"lockfileVersion": 3}', encoding="utf-8")


def _raw_report(*findings: dict[str, str]) -> dict[str, object]:
    packages: list[dict[str, object]] = []
    for finding in findings:
        packages.append(
            {
                "package": {
                    "name": finding["package"],
                    "version": finding["version"],
                    "ecosystem": finding["ecosystem"],
                },
                "vulnerabilities": [{"id": finding["advisory_id"]}],
            }
        )
    return {
        "results": [
            {
                "source": {
                    "path": findings[0]["source"],
                    "type": "lockfile",
                },
                "packages": packages,
            }
        ]
        if findings
        else []
    }


def _active_record(root: Path) -> dict[str, object]:
    _ensure_scan_inputs(root)
    lockfile = root / "frontend" / "package-lock.json"
    boundary = root / "frontend" / "src" / "test" / "routerSecurityBoundary.test.ts"
    boundary.parent.mkdir(parents=True, exist_ok=True)
    boundary.write_text("test('router boundary', () => {});", encoding="utf-8")
    return {
        "record_id": "react-router-7.18.2-GHSA-qwww-vcr4-c8h2",
        "status": "active",
        "disposition": "upstream_metadata_false_positive_patched",
        "advisory_id": "GHSA-qwww-vcr4-c8h2",
        "ecosystem": "npm",
        "package": "react-router",
        "version": "7.18.2",
        "lockfile": "frontend/package-lock.json",
        "lockfile_sha256": _sha256(lockfile),
        "boundary_test": {
            "path": "frontend/src/test/routerSecurityBoundary.test.ts",
            "sha256": _sha256(boundary),
        },
        "responsible_owner_type": "security_owner",
        "owner": "Security Engineering Owner",
        "approver": "Release Security Approver",
        "approved_at": "2026-08-07T00:00:00+00:00",
        "expires_at": "2026-08-21T23:59:59+08:00",
        "reason": "Maintainer backported the advisory fix to the exact v7 package release.",
        "sources": [
            {
                "kind": "maintainer_advisory",
                "url": "https://github.com/remix-run/react-router/security/advisories/GHSA-qwww-vcr4-c8h2",
                "retrieved_at": "2026-08-07T00:00:00+00:00",
            },
            {
                "kind": "maintainer_backport",
                "url": "https://github.com/remix-run/react-router/pull/15353",
                "retrieved_at": "2026-08-07T00:00:00+00:00",
            },
        ],
    }


def _scan_receipt(root: Path, raw_path: Path, *, exit_code: int) -> dict[str, object]:
    raw_relative = raw_path.relative_to(root).as_posix()
    return {
        "schema_version": 1,
        "status": "completed",
        "completed": True,
        "started_at": "2026-08-07T00:00:00+00:00",
        "completed_at": "2026-08-07T00:00:00+00:00",
        "scanner": {
            "name": "osv-scanner",
            "version": "2.3.0",
            "binary_sha256": SCANNER_SHA256,
            "exit_code": exit_code,
        },
        "arguments": [
            "scan",
            "source",
            f"--output={raw_relative}",
            "--format=json",
            "--lockfile=backend/uv.lock",
            "--lockfile=frontend/package-lock.json",
        ],
        "lockfiles": [
            {"path": lockfile, "sha256": _sha256(root / lockfile)}
            for lockfile in LOCKFILES
        ],
        "raw_report": {"path": raw_relative, "sha256": _sha256(raw_path)},
        "errors": [],
    }


def _write_gate_inputs(
    root: Path,
    *,
    findings: list[dict[str, str]] | None = None,
    records: list[dict[str, object]] | None = None,
    scanner_exit_code: int | None = None,
) -> tuple[Path, Path, Path, Path]:
    _ensure_scan_inputs(root)
    finding = {
        "source": (root / "frontend" / "package-lock.json").as_posix(),
        "ecosystem": "npm",
        "package": "react-router",
        "version": "7.18.2",
        "advisory_id": "GHSA-qwww-vcr4-c8h2",
    }
    selected_findings = findings if findings is not None else [finding]
    raw_path = root / "reports" / "osv-report.json"
    receipt_path = root / "reports" / "osv-scan-receipt.json"
    records_path = root / "records.json"
    output_path = root / "reports" / "osv-adjudication.json"
    _write_json(raw_path, _raw_report(*selected_findings))
    _write_json(
        receipt_path,
        _scan_receipt(
            root,
            raw_path,
            exit_code=scanner_exit_code
            if scanner_exit_code is not None
            else (1 if selected_findings else 0),
        ),
    )
    _write_json(
        records_path,
        {
            "schema_version": 1,
            "records": records if records is not None else [_active_record(root)],
        },
    )
    return raw_path, receipt_path, records_path, output_path


def _run_gate(module, root: Path, paths: tuple[Path, Path, Path, Path]):
    raw_path, receipt_path, records_path, output_path = paths
    return module.run_gate(
        raw_report_path=raw_path,
        scan_receipt_path=receipt_path,
        records_path=records_path,
        output_path=output_path,
        root=root,
        now=NOW,
    )


def test_exact_tuple_reconciliation_passes_without_modifying_raw_report(tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    paths = _write_gate_inputs(tmp_path)
    raw_before = paths[0].read_bytes()

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 0
    assert paths[0].read_bytes() == raw_before
    assert result["status"] == "pass"
    assert result["scanner_exit_code"] == 1
    assert result["counts"] == {"raw": 1, "reconciled": 1, "unresolved": 0}
    assert result["raw_report_sha256"] == hashlib.sha256(raw_before).hexdigest()
    assert (
        result["reconciled"][0]["record_id"]
        == "react-router-7.18.2-GHSA-qwww-vcr4-c8h2"
    )
    assert result["unresolved"] == []
    assert json.loads(paths[3].read_text(encoding="utf-8")) == result


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (
            lambda record: record.update(status="pending_owner_approval"),
            "status must be active",
        ),
        (lambda record: record.update(owner=None), "owner identity is required"),
        (lambda record: record.update(approver="TBD"), "approver identity is required"),
        (
            lambda record: record.update(approver=record["owner"]),
            "owner and approver must be different identities",
        ),
        (lambda record: record.update(approved_at=None), "approved_at is required"),
        (
            lambda record: record.update(expires_at="2026-08-06T23:59:59+00:00"),
            "record is expired",
        ),
        (
            lambda record: record.update(lockfile_sha256="0" * 64),
            "lockfile sha256 mismatch",
        ),
        (
            lambda record: record["boundary_test"].update(sha256="0" * 64),
            "boundary test sha256 mismatch",
        ),
        (
            lambda record: record["sources"][0].update(
                url="https://example.com/not-maintainer"
            ),
            "canonical github.com HTTPS URL",
        ),
        (
            lambda record: record["sources"][1].update(
                url="https://github.com/attacker/react-router/pull/15353"
            ),
            "trusted remix-run/react-router repository",
        ),
    ],
)
def test_record_governance_or_evidence_failure_is_fail_closed(
    tmp_path, mutation, expected_error
):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    record = _active_record(tmp_path)
    mutation(record)
    paths = _write_gate_inputs(tmp_path, records=[record])

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 1
    assert result["status"] == "fail"
    assert result["counts"] == {"raw": 1, "reconciled": 0, "unresolved": 1}
    assert any(
        expected_error in error
        for error in result["record_errors"][record["record_id"]]
    )


def test_version_change_does_not_match_exact_record(tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    record = _active_record(tmp_path)
    changed = {
        "source": (tmp_path / "frontend" / "package-lock.json").as_posix(),
        "ecosystem": "npm",
        "package": "react-router",
        "version": "7.18.3",
        "advisory_id": "GHSA-qwww-vcr4-c8h2",
    }
    paths = _write_gate_inputs(tmp_path, findings=[changed], records=[record])

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 1
    assert result["counts"] == {"raw": 1, "reconciled": 0, "unresolved": 1}
    assert result["unresolved"][0]["reason"] == "no exact reconciliation record"


def test_additional_vulnerability_remains_unresolved(tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    record = _active_record(tmp_path)
    source = (tmp_path / "frontend" / "package-lock.json").as_posix()
    findings = [
        {
            "source": source,
            "ecosystem": "npm",
            "package": "react-router",
            "version": "7.18.2",
            "advisory_id": "GHSA-qwww-vcr4-c8h2",
        },
        {
            "source": source,
            "ecosystem": "npm",
            "package": "another-package",
            "version": "1.0.0",
            "advisory_id": "GHSA-2222-3333-4444",
        },
    ]
    paths = _write_gate_inputs(tmp_path, findings=findings, records=[record])

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 1
    assert result["counts"] == {"raw": 2, "reconciled": 1, "unresolved": 1}
    assert result["unresolved"][0]["finding"]["advisory_id"] == "GHSA-2222-3333-4444"


def test_id_wide_or_wildcard_record_is_rejected(tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    record = _active_record(tmp_path)
    record["version"] = "*"
    paths = _write_gate_inputs(tmp_path, records=[record])

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 1
    assert any(
        "version must be exact" in error
        for error in result["record_errors"][record["record_id"]]
    )
    assert result["counts"]["unresolved"] == 1


def test_operational_failure_with_partial_reconciled_report_cannot_pass(tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    paths = _write_gate_inputs(tmp_path)
    receipt = json.loads(paths[1].read_text(encoding="utf-8"))
    receipt["status"] = "failed"
    receipt["completed"] = False
    receipt["scanner"]["exit_code"] = 127
    receipt["errors"] = ["scanner general error"]
    _write_json(paths[1], receipt)

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 1
    assert result["status"] == "fail"
    assert result["counts"]["raw"] == 1
    assert any("completed scan" in error for error in result["input_errors"])
    assert any("exit_code must be 0" in error for error in result["input_errors"])


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        (lambda receipt: receipt["lockfiles"].pop(0), "exactly cover"),
        (
            lambda receipt: receipt["lockfiles"][0].update(sha256="0" * 64),
            "lockfile sha256 mismatch",
        ),
        (
            lambda receipt: receipt["raw_report"].update(sha256="0" * 64),
            "raw_report sha256 mismatch",
        ),
        (
            lambda receipt: receipt["scanner"].update(binary_sha256="0" * 64),
            "pinned release artifact",
        ),
        (
            lambda receipt: receipt.update(arguments=["scan", "source"]),
            "exact expected scan command",
        ),
    ],
)
def test_scan_receipt_tampering_or_partial_coverage_fails_closed(
    tmp_path, mutation, expected_error
):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    paths = _write_gate_inputs(tmp_path)
    receipt = json.loads(paths[1].read_text(encoding="utf-8"))
    mutation(receipt)
    _write_json(paths[1], receipt)

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 1
    assert any(expected_error in error for error in result["input_errors"])


@pytest.mark.parametrize(
    ("findings", "exit_code", "expected_error"),
    [([], 1, "exit code 1 has no corresponding"), (None, 0, "exit code 0 contradicts")],
)
def test_scanner_result_code_must_agree_with_raw_findings(
    tmp_path, findings, exit_code, expected_error
):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    paths = _write_gate_inputs(
        tmp_path,
        findings=findings,
        scanner_exit_code=exit_code,
        records=[] if findings == [] else None,
    )

    gate_exit, result = _run_gate(module, tmp_path, paths)

    assert gate_exit == 1
    assert any(expected_error in error for error in result["input_errors"])


@pytest.mark.parametrize("target_index", [0, 1, 2])
def test_gate_refuses_to_overwrite_any_input(tmp_path, target_index):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    paths = _write_gate_inputs(tmp_path)
    target = paths[target_index]
    before = target.read_bytes()

    with pytest.raises(module.GateInputError, match="must not overwrite"):
        module.run_gate(
            raw_report_path=paths[0],
            scan_receipt_path=paths[1],
            records_path=paths[2],
            output_path=target,
            root=tmp_path,
            now=NOW,
        )

    assert target.read_bytes() == before


def test_unused_active_record_fails_and_requires_removal(tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    record = _active_record(tmp_path)
    paths = _write_gate_inputs(tmp_path, findings=[], records=[record])

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 1
    assert result["unused_active_records"] == [record["record_id"]]
    assert any("must be removed" in error for error in result["ledger_errors"])


def test_clean_completed_scan_passes_after_unused_records_are_removed(tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    paths = _write_gate_inputs(tmp_path, findings=[], records=[])

    exit_code, result = _run_gate(module, tmp_path, paths)

    assert exit_code == 0
    assert result["status"] == "pass"
    assert result["counts"] == {"raw": 0, "reconciled": 0, "unresolved": 0}


def test_raw_scan_runner_writes_completed_exact_coverage_receipt(monkeypatch, tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    _ensure_scan_inputs(tmp_path)
    scanner = tmp_path / "tools" / "osv-scanner"
    scanner.parent.mkdir(parents=True)
    scanner.write_bytes(b"pinned fake scanner")
    monkeypatch.setattr(module, "EXPECTED_SCANNER_SHA256", _sha256(scanner))
    captured: dict[str, object] = {}

    def fake_run(command, *, cwd, check):
        captured.update(command=command, cwd=cwd, check=check)
        output_arg = next(arg for arg in command if arg.startswith("--output="))
        _write_json(Path(cwd) / output_arg.split("=", 1)[1], _raw_report())
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    raw_path = tmp_path / "reports" / "osv-report.json"
    receipt_path = tmp_path / "reports" / "osv-scan-receipt.json"

    exit_code, receipt = module.run_raw_scan_with_receipt(
        scanner=scanner,
        raw_report_path=raw_path,
        scan_receipt_path=receipt_path,
        root=tmp_path,
        now=NOW,
    )

    assert exit_code == 0
    assert receipt["status"] == "completed"
    assert receipt["completed"] is True
    assert receipt["scanner"]["exit_code"] == 0
    assert [item["path"] for item in receipt["lockfiles"]] == list(LOCKFILES)
    assert captured["command"][1:] == receipt["arguments"]
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == receipt


def test_raw_scan_runner_records_operational_failure_even_with_partial_raw(
    monkeypatch, tmp_path
):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    _ensure_scan_inputs(tmp_path)
    scanner = tmp_path / "tools" / "osv-scanner"
    scanner.parent.mkdir(parents=True)
    scanner.write_bytes(b"pinned fake scanner")
    monkeypatch.setattr(module, "EXPECTED_SCANNER_SHA256", _sha256(scanner))

    def fake_run(command, *, cwd, check):
        output_arg = next(arg for arg in command if arg.startswith("--output="))
        finding = {
            "source": (Path(cwd) / "frontend" / "package-lock.json").as_posix(),
            "ecosystem": "npm",
            "package": "react-router",
            "version": "7.18.2",
            "advisory_id": "GHSA-qwww-vcr4-c8h2",
        }
        _write_json(Path(cwd) / output_arg.split("=", 1)[1], _raw_report(finding))
        return SimpleNamespace(returncode=127)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    exit_code, receipt = module.run_raw_scan_with_receipt(
        scanner=scanner,
        raw_report_path=tmp_path / "reports" / "osv-report.json",
        scan_receipt_path=tmp_path / "reports" / "osv-scan-receipt.json",
        root=tmp_path,
        now=NOW,
    )

    assert exit_code == 2
    assert receipt["status"] == "failed"
    assert receipt["completed"] is False
    assert receipt["scanner"]["exit_code"] == 127
    assert any("documented result code" in error for error in receipt["errors"])


def test_raw_scan_runner_refuses_to_overwrite_records_ledger(tmp_path):
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    _ensure_scan_inputs(tmp_path)
    ledger = tmp_path / "docs" / "audits" / "osv-reconciliation-records.json"
    _write_json(ledger, {"schema_version": 1, "records": []})
    before = ledger.read_bytes()

    with pytest.raises(module.GateInputError, match="must not overwrite"):
        module.run_raw_scan_with_receipt(
            scanner=tmp_path / "missing-scanner",
            raw_report_path=ledger,
            scan_receipt_path=tmp_path / "reports" / "receipt.json",
            root=tmp_path,
            now=NOW,
        )

    assert ledger.read_bytes() == before


def test_repository_ledger_contains_no_stale_reconciliation_records():
    payload = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))

    assert payload == {"schema_version": 1, "records": []}


def test_repository_ledger_blocks_a_reintroduced_finding_without_an_exact_record():
    module = load_module(
        "scripts.osv_reconciliation_gate", GATE_PATH.relative_to(ROOT).as_posix()
    )
    finding = {
        "source": (ROOT / "frontend" / "package-lock.json").as_posix(),
        "ecosystem": "npm",
        "package": "react-router",
        "version": "7.18.2",
        "advisory_id": "GHSA-qwww-vcr4-c8h2",
    }
    payload = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))

    result = module.evaluate_reconciliation(
        raw_report=_raw_report(finding),
        records_payload=payload,
        root=ROOT,
        now=NOW,
        scanner_exit_code=1,
        scan_receipt_errors=[],
    )

    assert result["status"] == "fail"
    assert result["counts"] == {"raw": 1, "reconciled": 0, "unresolved": 1}
    assert result["record_errors"] == {}
    assert result["unresolved"][0]["reason"] == "no exact reconciliation record"
