from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

import scripts.portfolio_home_evidence_packet_guard as guard_module
from scripts.portfolio_home_evidence_packet_guard import (
    ARTIFACT_PRESENCE_COMMAND,
    build_report,
)
from scripts.verify_portfolio_home_scorecard_commands import (
    build_report as real_build_verification_report,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_evidence_packet_guard.py"
DUCKDB = ROOT / "data" / "moss.duckdb"
TEMPLATE = ROOT / "docs" / "portfolio" / "portfolio-home-business-owner-approval-template.md"
REPORT_DATE = "2026-05-31"
JSON_OWNER_DECISION_ARTIFACTS = [
    ("evidence_snapshot", "portfolio-home-evidence-snapshot.json"),
    ("owner_action_packet", "portfolio-home-owner-action-packet.json"),
    (
        "business_owner_approval_packet",
        "portfolio-home-business-owner-approval-packet.json",
    ),
]
JSON_OWNER_DECISION_ALIGNMENT_ARTIFACTS = [
    ("evidence_snapshot", "portfolio-home-evidence-snapshot.json"),
    ("owner_action_packet", "portfolio-home-owner-action-packet.json"),
    (
        "business_owner_approval_packet",
        "portfolio-home-business-owner-approval-packet.json",
    ),
]
JSON_SCORE_BLOCKER_ACTION_COVERAGE_ARTIFACTS = [
    ("owner_action_packet", "portfolio-home-owner-action-packet.json"),
    (
        "business_owner_approval_packet",
        "portfolio-home-business-owner-approval-packet.json",
    ),
]
JSON_BUSINESS_OWNER_ACTIVATION_GUARD_SUMMARY_LOCATIONS = [
    (
        "evidence_snapshot",
        "portfolio-home-evidence-snapshot.json",
        ("business_owner_approval_packet_summary", "activation_guard"),
        "business_owner_approval_packet_summary",
    ),
    (
        "owner_action_packet",
        "portfolio-home-owner-action-packet.json",
        ("owner_packets", "business_owner", "activation_guard"),
        "business_owner",
    ),
]
JSON_EVIDENCE_SCOPE_LOCATIONS = [
    (
        "evidence_snapshot",
        "portfolio-home-evidence-snapshot.json",
        ("handoff_completeness_summary", "evidence_scope"),
    ),
    (
        "evidence_snapshot",
        "portfolio-home-evidence-snapshot.json",
        (
            "business_owner_approval_packet_summary",
            "risk_warning_clean_status",
            "evidence_scope",
        ),
    ),
    (
        "owner_action_packet",
        "portfolio-home-owner-action-packet.json",
        ("evidence_scope",),
    ),
    (
        "owner_action_packet",
        "portfolio-home-owner-action-packet.json",
        ("risk_warning_clean_status", "evidence_scope"),
    ),
    (
        "owner_action_packet",
        "portfolio-home-owner-action-packet.json",
        ("owner_packets", "business_owner", "evidence_scope"),
    ),
    (
        "business_owner_approval_packet",
        "portfolio-home-business-owner-approval-packet.json",
        ("approval_summary", "evidence_scope"),
    ),
    (
        "business_owner_approval_packet",
        "portfolio-home-business-owner-approval-packet.json",
        ("risk_warning_clean_status", "evidence_scope"),
    ),
    (
        "owner_input_needed_summary",
        "portfolio-home-owner-input-needed-summary.json",
        ("evidence_scope",),
    ),
]
JSON_EVIDENCE_SCOPE_BOOLEAN_OVERCLAIMS = [
    (
        "evidence_snapshot",
        "portfolio-home-evidence-snapshot.json",
        ("handoff_completeness_summary", "evidence_scope"),
        "proves_full_score_closure",
    ),
    (
        "owner_action_packet",
        "portfolio-home-owner-action-packet.json",
        ("evidence_scope",),
        "approves_metric_or_page",
    ),
    (
        "business_owner_approval_packet",
        "portfolio-home-business-owner-approval-packet.json",
        ("approval_summary", "evidence_scope"),
        "writes_governance_records",
    ),
    (
        "owner_input_needed_summary",
        "portfolio-home-owner-input-needed-summary.json",
        ("evidence_scope",),
        "captures_business_owner_approval",
    ),
]
REAL_CONTEXT_TEST_PREFIXES = (
    "test_portfolio_home_evidence_packet_guard_reports_current_packets",
    "test_portfolio_home_evidence_packet_guard_cli_require_clean",
    "test_portfolio_home_evidence_packet_guard_propagates_handoff_completeness_blocker",
    "test_portfolio_home_evidence_packet_guard_rejects_negative_limit",
)


@lru_cache(maxsize=1)
def _baseline_guard_dependency_outputs() -> dict[str, object]:
    docs_root = ROOT / "docs"
    return {
        "artifact_presence": guard_module.build_artifact_presence_report(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            docs_root=docs_root,
            limit=3,
        ),
        "scorecard": guard_module.build_scorecard(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            limit=3,
            docs_root=docs_root,
        ),
        "owner_input_summary": guard_module.build_owner_input_summary(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            docs_root=docs_root,
            limit=3,
        ),
        "intake_check": guard_module.build_intake_check(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            docs_root=docs_root,
            limit=3,
        ),
        "handoff_completeness": guard_module.build_handoff_completeness_report(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            docs_root=docs_root,
            limit=3,
        ),
        "business_owner_approval_packet": guard_module.build_business_owner_approval_packet(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            docs_root=docs_root,
            limit=3,
        ),
        "owner_action_packet": guard_module.build_owner_action_packet(
            duckdb_path=DUCKDB,
            report_date=REPORT_DATE,
            template_path=TEMPLATE,
            docs_root=docs_root,
            limit=3,
        ),
        "verification_report": guard_module.build_verification_report(
            limit=1,
            expected_state="blocked",
            docs_root=docs_root,
        ),
    }


@pytest.fixture(autouse=True)
def _cache_guard_expected_context(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if any(request.node.name.startswith(prefix) for prefix in REAL_CONTEXT_TEST_PREFIXES):
        return
    cached = _baseline_guard_dependency_outputs()

    def _cached(name: str):
        def _wrapper(*_args: object, **_kwargs: object) -> object:
            return copy.deepcopy(cached[name])

        return _wrapper

    monkeypatch.setattr(
        guard_module,
        "build_artifact_presence_report",
        _cached("artifact_presence"),
    )
    monkeypatch.setattr(guard_module, "build_scorecard", _cached("scorecard"))
    monkeypatch.setattr(
        guard_module,
        "build_owner_input_summary",
        _cached("owner_input_summary"),
    )
    monkeypatch.setattr(guard_module, "build_intake_check", _cached("intake_check"))
    monkeypatch.setattr(
        guard_module,
        "build_handoff_completeness_report",
        _cached("handoff_completeness"),
    )
    monkeypatch.setattr(
        guard_module,
        "build_business_owner_approval_packet",
        _cached("business_owner_approval_packet"),
    )
    monkeypatch.setattr(
        guard_module,
        "build_owner_action_packet",
        _cached("owner_action_packet"),
    )
    monkeypatch.setattr(
        guard_module,
        "build_verification_report",
        _cached("verification_report"),
    )


def _copy_portfolio_docs(tmp_path: Path) -> Path:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    return docs_root


def _refresh_handoff_derivatives(docs_root: Path) -> None:
    for filename in (
        "portfolio-home-owner-input-needed-summary.json",
        "portfolio-home-owner-handoff-packet.md",
    ):
        source = ROOT / "docs" / "portfolio" / filename
        target = docs_root / "portfolio" / filename
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def test_portfolio_home_evidence_packet_guard_reuses_cached_verifier_report_for_default_context() -> None:
    cached = _baseline_guard_dependency_outputs()

    assert guard_module.build_verification_report is not real_build_verification_report
    assert guard_module.build_verification_report(
        limit=1,
        expected_state="blocked",
        docs_root=ROOT / "docs",
    ) == cached["verification_report"]


def _run_guard(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def _scope_at(payload: dict[str, object], path: tuple[str, ...]) -> dict[str, object]:
    current: object = payload
    for key in path:
        assert isinstance(current, dict)
        current = current[key]
    assert isinstance(current, dict)
    return current


def _scope_label(path: tuple[str, ...]) -> str:
    return "_".join(path)


def test_portfolio_home_evidence_packet_guard_reports_current_packets() -> None:
    report = build_report(docs_root=ROOT / "docs")

    assert report["status"] == "clean"
    assert report["blockers"] == []
    assert report["required_command"] == ARTIFACT_PRESENCE_COMMAND
    assert report["handoff_completeness"]["status"] == "clean"
    assert report["handoff_completeness"]["handoff_ready"] is True
    assert report["handoff_completeness"]["handoff_current_status"]["status"] == "current"
    assert report["expected_boundary"] == {
        "page_id": "PAGE-PORTFOLIO-HOME-001",
        "page_slug": "portfolio",
        "report_date": "2026-05-31",
        "current_score": "99.86 / 100",
        "remaining_gap": "0.14",
        "score_status": "blocked",
        "full_score_ready": False,
        "score_blockers": [
            "risk_tensor_quality_warning",
            "krd_contract_decision_required",
            "bond_maturity_date_remediation_required",
            "tyw_liability_maturity_date_remediation_required",
            "duration_exclusion_warning_mismatch",
            "risk_tensor_warning_mismatch",
            "business_owner_approval",
            "owner_decision_intake_blocked",
        ],
    }
    assert report["artifact_presence_summary"] == {
        "status": "current",
        "current": True,
        "blockers": [],
        "artifact_current_summary": {
            "krd": {
                "status": "current",
                "current": True,
                "current_blockers": [],
            },
            "maturity": {
                "status": "current",
                "current": True,
                "current_blockers": [],
            },
            "business_owner_approval_template": {
                "status": "present",
                "current": True,
                "current_blockers": [],
            },
            "exact_bucket_schema_evidence": {
                "status": "not_required",
                "current": True,
                "current_blockers": [],
            },
            "nearest_bucket_approval_evidence": {
                "status": "not_required",
                "current": True,
                "current_blockers": [],
            },
            "maturity_scoped_exclusion_evidence": {
                "status": "not_required",
                "current": True,
                "current_blockers": [],
            },
        },
    }
    assert [artifact["name"] for artifact in report["artifacts"]] == [
        "evidence_snapshot",
        "owner_action_packet",
        "business_owner_approval_packet",
        "owner_input_needed_summary",
        "owner_handoff_packet",
        "full_closure_signoff_packet",
    ]
    for artifact in report["artifacts"]:
        assert artifact["status"] == "clean"
        assert artifact["blockers"] == []
        if artifact["kind"] in {"json", "owner_summary", "markdown"}:
            assert artifact["boundary_status"] == "clean"
            assert artifact["boundary_mismatches"] == []


def test_portfolio_home_evidence_packet_guard_cli_require_clean() -> None:
    returncode, payload = _run_guard("--require-clean")

    assert returncode == 0
    assert payload["status"] == "clean"
    assert payload["required_command"] == ARTIFACT_PRESENCE_COMMAND


def test_portfolio_home_evidence_packet_guard_blocks_snapshot_missing_summary(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    snapshot_path = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot.pop("closure_artifact_presence_summary", None)
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "evidence_snapshot_closure_artifact_presence_summary_missing" in report["blockers"]


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_packet_missing_summary(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet.pop("closure_artifact_presence_summary", None)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_action_packet_closure_artifact_presence_summary_missing" in report["blockers"]


def test_portfolio_home_evidence_packet_guard_blocks_business_owner_packet_missing_summary(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-business-owner-approval-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet.pop("closure_artifact_presence_summary", None)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "business_owner_approval_packet_closure_artifact_presence_summary_missing"
        in report["blockers"]
    )


def test_portfolio_home_evidence_packet_guard_blocks_json_packet_boundary_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["report_date"] = "2026-06-01"
    packet["current_score"] = "100.00 / 100"
    packet["full_score_ready"] = True
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_action_packet_report_date_mismatch" in report["blockers"]
    assert "owner_action_packet_current_score_mismatch" in report["blockers"]
    assert "owner_action_packet_full_score_ready_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["boundary_status"] == "blocked"
    assert artifacts["owner_action_packet"]["boundary_mismatches"] == [
        {
            "field": "report_date",
            "expected": "2026-05-31",
            "actual": "2026-06-01",
        },
        {
            "field": "current_score",
            "expected": "99.86 / 100",
            "actual": "100.00 / 100",
        },
        {
            "field": "full_score_ready",
            "expected": False,
            "actual": True,
        },
    ]


@pytest.mark.parametrize(("artifact_name", "filename"), JSON_OWNER_DECISION_ARTIFACTS)
def test_portfolio_home_evidence_packet_guard_blocks_owner_decision_summary_drift(
    tmp_path: Path,
    artifact_name: str,
    filename: str,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / filename
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    owner_decision_summary = packet["owner_decision_intake_summary"]
    assert isinstance(owner_decision_summary, dict)
    owner_decision_summary["intake_ready"] = True
    owner_decision_summary["decision_gap_counts"] = {}
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert f"{artifact_name}_owner_decision_intake_summary_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts[artifact_name]["status"] == "blocked"


@pytest.mark.parametrize(
    ("artifact_name", "filename", "replacement"),
    [
        ("evidence_snapshot", "portfolio-home-evidence-snapshot.json", None),
        ("owner_action_packet", "portfolio-home-owner-action-packet.json", "stale"),
    ],
)
def test_portfolio_home_evidence_packet_guard_blocks_owner_decision_summary_missing(
    tmp_path: Path,
    artifact_name: str,
    filename: str,
    replacement: object,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / filename
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if replacement is None:
        packet.pop("owner_decision_intake_summary", None)
    else:
        packet["owner_decision_intake_summary"] = replacement
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert f"{artifact_name}_owner_decision_intake_summary_missing" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts[artifact_name]["status"] == "blocked"


@pytest.mark.parametrize(("artifact_name", "filename"), JSON_OWNER_DECISION_ALIGNMENT_ARTIFACTS)
def test_portfolio_home_evidence_packet_guard_blocks_owner_decision_alignment_missing(
    tmp_path: Path,
    artifact_name: str,
    filename: str,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / filename
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet.pop("owner_decision_intake_alignment", None)
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert f"{artifact_name}_owner_decision_intake_alignment_missing" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts[artifact_name]["status"] == "blocked"


@pytest.mark.parametrize(("artifact_name", "filename"), JSON_OWNER_DECISION_ALIGNMENT_ARTIFACTS)
def test_portfolio_home_evidence_packet_guard_blocks_owner_decision_alignment_drift(
    tmp_path: Path,
    artifact_name: str,
    filename: str,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / filename
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    alignment = packet["owner_decision_intake_alignment"]
    assert isinstance(alignment, dict)
    alignment["status"] = "blocked"
    alignment["blockers"] = ["owner_decision_intake_alignment_intake_ready_mismatch"]
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert f"{artifact_name}_owner_decision_intake_alignment_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts[artifact_name]["status"] == "blocked"


@pytest.mark.parametrize(("artifact_name", "filename"), JSON_OWNER_DECISION_ALIGNMENT_ARTIFACTS)
def test_portfolio_home_evidence_packet_guard_blocks_scorecard_owner_gate_summary_drift(
    tmp_path: Path,
    artifact_name: str,
    filename: str,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / filename
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    gate_summary = packet["scorecard_owner_decision_intake_gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["intake_ready"] = True
    gate_summary["blockers"] = []
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    _refresh_handoff_derivatives(docs_root)

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert f"{artifact_name}_scorecard_owner_decision_intake_gate_summary_mismatch" in report[
        "blockers"
    ]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts[artifact_name]["status"] == "blocked"


@pytest.mark.parametrize(
    ("artifact_name", "filename"),
    JSON_SCORE_BLOCKER_ACTION_COVERAGE_ARTIFACTS,
)
def test_portfolio_home_evidence_packet_guard_blocks_score_blocker_action_coverage_drift(
    tmp_path: Path,
    artifact_name: str,
    filename: str,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / filename
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    coverage = packet["score_blocker_action_coverage"]
    assert isinstance(coverage, dict)
    coverage["covered_blockers"] = ["business_owner_approval"]
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    _refresh_handoff_derivatives(docs_root)

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert f"{artifact_name}_score_blocker_action_coverage_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts[artifact_name]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_business_owner_packet_missing_partial_owner_activation_guard(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-business-owner-approval-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    activation_guard = packet["activation_guard"]
    assert isinstance(activation_guard, dict)
    activation_guard.pop("partial_owner_evidence_activation_invalid")
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "business_owner_approval_packet_activation_guard_partial_owner_evidence_activation_invalid_missing"
        in report["blockers"]
    )
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["business_owner_approval_packet"]["status"] == "blocked"


@pytest.mark.parametrize(
    ("artifact_name", "filename", "guard_path", "blocker_label"),
    JSON_BUSINESS_OWNER_ACTIVATION_GUARD_SUMMARY_LOCATIONS,
)
def test_portfolio_home_evidence_packet_guard_blocks_summary_missing_partial_owner_activation_guard(
    tmp_path: Path,
    artifact_name: str,
    filename: str,
    guard_path: tuple[str, ...],
    blocker_label: str,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    approval_packet_path = (
        docs_root / "portfolio" / "portfolio-home-business-owner-approval-packet.json"
    )
    approval_packet = json.loads(approval_packet_path.read_text(encoding="utf-8"))
    source_guard = approval_packet["activation_guard"]
    assert isinstance(source_guard, dict)
    packet_path = docs_root / "portfolio" / filename
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    guard_parent = _scope_at(packet, guard_path[:-1])
    guard_parent[guard_path[-1]] = copy.deepcopy(source_guard)
    activation_guard = guard_parent[guard_path[-1]]
    assert isinstance(activation_guard, dict)
    activation_guard.pop("partial_owner_evidence_activation_invalid")
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        f"{artifact_name}_{blocker_label}_activation_guard_"
        "partial_owner_evidence_activation_invalid_missing"
    ) in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts[artifact_name]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_evidence_snapshot_business_owner_summary_canonical_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    snapshot_path = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    summary = snapshot["business_owner_approval_packet_summary"]
    assert isinstance(summary, dict)
    summary["approval_action_item_count"] = 0
    packet_path = docs_root / "portfolio" / "portfolio-home-business-owner-approval-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    approval_summary = packet["approval_summary"]
    assert isinstance(approval_summary, dict)
    approval_summary["approval_action_item_count"] = 0
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "evidence_snapshot_business_owner_approval_packet_summary_canonical_mismatch"
        in report["blockers"]
    )
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["evidence_snapshot"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_evidence_snapshot_verifier_canonical_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    snapshot_path = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    verifier = snapshot["verification_report"]
    assert isinstance(verifier, dict)
    results = verifier["results"]
    assert isinstance(results, list)
    result = results[0]
    assert isinstance(result, dict)
    result["name"] = "stale_full_closure_evidence"
    verifier["verification_status"] = "matched_expected_blocked_state"
    verifier["all_matched_expected_exit"] = True
    verifier["all_matched_expected_when_blocked"] = True
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "evidence_snapshot_verification_report_canonical_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["evidence_snapshot"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_requires_limited_verifier_scope(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    snapshot_path = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot.pop("verification_scope", None)
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "evidence_snapshot_verification_scope_missing" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["evidence_snapshot"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_verifier_scope_overclaim(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    snapshot_path = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["verification_scope"] = {
        "scope": "full",
        "embedded_result_count": 1,
        "total_verification_command_count": 1,
        "embedded_result_count_matches_report": True,
        "all_commands_embedded": True,
        "full_verification_command": "python scripts/verify_portfolio_home_scorecard_commands.py --require-matched",
        "requires_full_verification_for_full_score": False,
        "proves_full_score_closure": True,
        "certification_effect": "full_score_verified",
    }
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "evidence_snapshot_verification_scope_canonical_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["evidence_snapshot"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_evidence_snapshot_gate_summary_canonical_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    snapshot_path = docs_root / "portfolio" / "portfolio-home-evidence-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    gate_summary = snapshot["gate_summary"]
    assert isinstance(gate_summary, dict)
    gate_summary["business_owner_approval_status"] = "captured"
    gate_summary["owner_decision_intake_ready"] = True
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "evidence_snapshot_gate_summary_canonical_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["evidence_snapshot"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_assignment_coverage_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assignment_coverage = packet["assignment_coverage"]
    assert isinstance(assignment_coverage, dict)
    assignment_coverage["assigned_blockers"] = ["business_owner_approval"]
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    _refresh_handoff_derivatives(docs_root)

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_action_packet_assignment_coverage_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_assignment_coverage_uses_score_blocker_order() -> None:
    coverage = guard_module._owner_action_assignment_coverage(
        {
            "score_blockers": [
                "first_blocker",
                "second_blocker",
                "third_blocker",
            ],
            "owner_packets": {
                "risk_owner": {"blockers": ["third_blocker"]},
                "data_owner": {"blockers": ["first_blocker"]},
                "business_owner": {"blockers": ["second_blocker"]},
            },
        },
    )

    assert coverage == {
        "status": "clean",
        "score_blockers": [
            "first_blocker",
            "second_blocker",
            "third_blocker",
        ],
        "assigned_blockers": [
            "first_blocker",
            "second_blocker",
            "third_blocker",
        ],
        "unassigned_blockers": [],
        "duplicate_assigned_blockers": [],
        "unexpected_assigned_blockers": [],
    }


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_action_command_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    owner_packets = packet["owner_packets"]
    assert isinstance(owner_packets, dict)
    risk_owner = owner_packets["risk_owner"]
    assert isinstance(risk_owner, dict)
    actions = risk_owner["actions"]
    assert isinstance(actions, list)
    action = next(
        item
        for item in actions
        if isinstance(item, dict)
        and item.get("blocker") == "risk_tensor_quality_warning"
    )
    action["evidence_command"] = "python scripts/portfolio_home_full_closure_evidence.py"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "owner_action_packet_risk_owner_action_risk_tensor_quality_warning_mismatch"
        in report["blockers"]
    )
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_exit_criteria_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    owner_packets = packet["owner_packets"]
    assert isinstance(owner_packets, dict)
    business_owner = owner_packets["business_owner"]
    assert isinstance(business_owner, dict)
    actions = business_owner["actions"]
    assert isinstance(actions, list)
    action = next(
        item
        for item in actions
        if isinstance(item, dict) and item.get("blocker") == "business_owner_approval"
    )
    action["exit_criteria"] = "Approval template is present."
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "owner_action_packet_business_owner_action_business_owner_approval_mismatch"
        in report["blockers"]
    )
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_canonical_action_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    owner_packets = packet["owner_packets"]
    assert isinstance(owner_packets, dict)
    risk_owner = owner_packets["risk_owner"]
    assert isinstance(risk_owner, dict)
    actions = risk_owner["actions"]
    assert isinstance(actions, list)
    action = next(
        item
        for item in actions
        if isinstance(item, dict)
        and item.get("blocker") == "risk_tensor_quality_warning"
    )
    matrix = packet["blocker_closure_matrix"]
    assert isinstance(matrix, list)
    row = next(
        item
        for item in matrix
        if isinstance(item, dict)
        and item.get("blocker") == "risk_tensor_quality_warning"
    )
    stale_command = "python scripts/portfolio_home_full_closure_evidence.py"
    action["evidence_command"] = stale_command
    row["recheck_commands"] = [stale_command]
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "owner_action_packet_blocker_closure_matrix_canonical_mismatch"
        in report["blockers"]
    )
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_blocker_closure_matrix_coverage_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    coverage = packet["blocker_closure_matrix_coverage"]
    assert isinstance(coverage, dict)
    coverage["covered_blockers"] = ["business_owner_approval"]
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    _refresh_handoff_derivatives(docs_root)

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_action_packet_blocker_closure_matrix_coverage_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_owner_alignment_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    owner_packets = packet["owner_packets"]
    assert isinstance(owner_packets, dict)
    risk_owner = owner_packets["risk_owner"]
    assert isinstance(risk_owner, dict)
    risk_owner["owner_decision_intake_alignment_status"] = "blocked"
    risk_owner["owner_decision_intake_alignment_blockers"] = [
        "owner_decision_intake_alignment_intake_ready_mismatch",
    ]
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "owner_action_packet_risk_owner_owner_decision_intake_alignment_mismatch"
        in report["blockers"]
    )
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_dependency_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    owner_packets = packet["owner_packets"]
    assert isinstance(owner_packets, dict)
    risk_owner = owner_packets["risk_owner"]
    assert isinstance(risk_owner, dict)
    risk_owner["dependency_consistency_status"] = "blocked"
    risk_owner["dependency_consistency_blockers"] = [
        "krd_contract_decision_manifest_owner_decision_fields_not_blank",
    ]
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_action_packet_risk_owner_dependency_consistency_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_csv_summary_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    owner_packets = packet["owner_packets"]
    assert isinstance(owner_packets, dict)
    data_owner = owner_packets["data_owner"]
    assert isinstance(data_owner, dict)
    csv_summary = data_owner["csv_check_summary"]
    assert isinstance(csv_summary, dict)
    csv_summary["bond_missing_maturity_row_count"] = 0
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_action_packet_data_owner_csv_check_summary_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_owner_action_boundary_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    packet_path = docs_root / "portfolio" / "portfolio-home-owner-action-packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    owner_packets = packet["owner_packets"]
    assert isinstance(owner_packets, dict)
    business_owner = owner_packets["business_owner"]
    assert isinstance(business_owner, dict)
    boundaries = business_owner["generated_owner_fields_boundaries"]
    assert isinstance(boundaries, dict)
    boundaries["maturity_remediation_manifest"] = False
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "owner_action_packet_business_owner_generated_owner_fields_boundaries_mismatch"
        in report["blockers"]
    )
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_action_packet"]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_evidence_scope_certification_effect_overclaim(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    expected_blockers: list[str] = []
    for artifact_name, filename, scope_path in JSON_EVIDENCE_SCOPE_LOCATIONS:
        packet_path = docs_root / "portfolio" / filename
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        scope = _scope_at(packet, scope_path)
        scope["certification_effect"] = "certifies_page"
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        expected_blockers.append(
            f"{artifact_name}_{_scope_label(scope_path)}_certification_effect_overclaims",
        )

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    for blocker in expected_blockers:
        assert blocker in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    for artifact_name, _, _ in JSON_EVIDENCE_SCOPE_LOCATIONS:
        assert artifacts[artifact_name]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_requires_evidence_scope_certification_effect(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    expected_blockers: list[str] = []
    for artifact_name, filename, scope_path in JSON_EVIDENCE_SCOPE_LOCATIONS:
        packet_path = docs_root / "portfolio" / filename
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        scope = _scope_at(packet, scope_path)
        scope.pop("certification_effect")
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        expected_blockers.append(
            f"{artifact_name}_{_scope_label(scope_path)}_certification_effect_missing",
        )

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    for blocker in expected_blockers:
        assert blocker in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    for artifact_name, _, _ in JSON_EVIDENCE_SCOPE_LOCATIONS:
        assert artifacts[artifact_name]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_evidence_scope_boolean_overclaims(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    expected_blockers: list[str] = []
    for artifact_name, filename, scope_path, field in JSON_EVIDENCE_SCOPE_BOOLEAN_OVERCLAIMS:
        packet_path = docs_root / "portfolio" / filename
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        scope = _scope_at(packet, scope_path)
        scope[field] = True
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        expected_blockers.append(f"{artifact_name}_{_scope_label(scope_path)}_{field}_overclaims")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    for blocker in expected_blockers:
        assert blocker in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    for artifact_name, _, _, _ in JSON_EVIDENCE_SCOPE_BOOLEAN_OVERCLAIMS:
        assert artifacts[artifact_name]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_stale_owner_input_summary(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    summary_path = docs_root / "portfolio" / "portfolio-home-owner-input-needed-summary.json"
    summary_path.write_text(json.dumps({"summary_kind": "stale"}), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_input_needed_summary_stale" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_input_needed_summary"]["status"] == "blocked"
    assert artifacts["owner_input_needed_summary"]["current"] is False


def test_portfolio_home_evidence_packet_guard_propagates_handoff_completeness_blocker(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    handoff_path = docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"
    handoff_path.write_text("# stale owner handoff", encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert (
        "owner_handoff_completeness_owner_handoff_packet_not_current"
        in report["blockers"]
    )
    assert report["handoff_completeness"]["status"] == "blocked"
    assert report["handoff_completeness"]["handoff_current_status"]["status"] == "stale"


def test_portfolio_home_evidence_packet_guard_blocks_handoff_missing_command(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    handoff_path = docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"
    handoff_path.write_text(
        handoff_path.read_text(encoding="utf-8").replace(ARTIFACT_PRESENCE_COMMAND, ""),
        encoding="utf-8",
    )

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_handoff_packet_artifact_presence_command_missing" in report["blockers"]


@pytest.mark.parametrize(
    ("artifact_name", "filename", "current_text", "stale_text", "expected_blocker"),
    [
        (
            "owner_handoff_packet",
            "portfolio-home-owner-handoff-packet.md",
            (
                "Risk-owner CSV decisions, nearest-bucket or exact-bucket evidence, "
                "data-owner CSV decisions, scoped-exclusion evidence, and business-owner "
                "approval are reconciled"
            ),
            (
                "Risk-owner CSV decisions, data-owner CSV decisions, exact-bucket "
                "evidence, and business-owner approval are reconciled"
            ),
            "owner_handoff_packet_owner_decision_intake_stale_krd_evidence_wording_mismatch",
        ),
        (
            "full_closure_signoff_packet",
            "portfolio-home-full-closure-sign-off-packet.md",
            "nearest-bucket approval or exact-bucket schema evidence",
            "exact-bucket evidence",
            "full_closure_signoff_packet_owner_decision_intake_stale_krd_evidence_wording_mismatch",
        ),
    ],
)
def test_portfolio_home_evidence_packet_guard_blocks_stale_exact_bucket_only_wording(
    tmp_path: Path,
    artifact_name: str,
    filename: str,
    current_text: str,
    stale_text: str,
    expected_blocker: str,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    artifact_path = docs_root / "portfolio" / filename
    text = artifact_path.read_text(encoding="utf-8")
    assert current_text in text
    artifact_path.write_text(text.replace(current_text, stale_text), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert expected_blocker in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts[artifact_name]["status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_handoff_markdown_scope_overclaim(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    handoff_path = docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"
    handoff = handoff_path.read_text(encoding="utf-8")
    handoff = handoff.replace("- Certification effect: `none`", "- Certification effect: `certifies_page`")
    handoff = handoff.replace(
        "- Handoff approves metric or page: `false`",
        "- Handoff approves metric or page: `true`",
    )
    handoff = handoff.replace(
        "- Handoff writes governance records: `false`",
        "- Handoff writes governance records: `true`",
    )
    handoff = handoff.replace(
        "- Handoff captures business-owner approval: `false`",
        "- Handoff captures business-owner approval: `true`",
    )
    handoff_path.write_text(handoff, encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_handoff_packet_certification_effect_scope_mismatch" in report["blockers"]
    assert "owner_handoff_packet_approves_metric_or_page_scope_mismatch" in report["blockers"]
    assert "owner_handoff_packet_writes_governance_records_scope_mismatch" in report["blockers"]
    assert "owner_handoff_packet_captures_business_owner_approval_scope_mismatch" in report["blockers"]


def test_portfolio_home_evidence_packet_guard_blocks_handoff_boundary_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    handoff_path = docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"
    handoff = handoff_path.read_text(encoding="utf-8")
    handoff = handoff.replace("- Report date: `2026-05-31`", "- Report date: `2026-06-01`")
    handoff = handoff.replace("- Current score: `99.86 / 100`", "- Current score: `100.00 / 100`")
    handoff = handoff.replace("- Score status: `blocked`", "- Score status: `ready_for_full_score`")
    handoff = handoff.replace("- Full score closure ready: `false`", "- Full score closure ready: `true`")
    handoff = handoff.replace("- `owner_decision_intake_blocked`", "")
    handoff_path.write_text(handoff, encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_handoff_packet_report_date_mismatch" in report["blockers"]
    assert "owner_handoff_packet_current_score_mismatch" in report["blockers"]
    assert "owner_handoff_packet_score_status_mismatch" in report["blockers"]
    assert "owner_handoff_packet_full_score_ready_mismatch" in report["blockers"]
    assert "owner_handoff_packet_score_blockers_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["owner_handoff_packet"]["boundary_status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_blocks_signoff_missing_summary(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    signoff_path = docs_root / "portfolio" / "portfolio-home-full-closure-sign-off-packet.md"
    signoff_path.write_text(
        signoff_path.read_text(encoding="utf-8").replace(
            "Closure artifact presence check reports `status=current`, `current=true`, and no blockers.",
            "",
        ),
        encoding="utf-8",
    )

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "full_closure_signoff_packet_artifact_presence_summary_missing" in report["blockers"]


def test_portfolio_home_evidence_packet_guard_blocks_signoff_markdown_scope_overclaim(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    signoff_path = docs_root / "portfolio" / "portfolio-home-full-closure-sign-off-packet.md"
    signoff = signoff_path.read_text(encoding="utf-8")
    signoff = signoff.replace(
        "Formal use allowed: `formal_use_allowed=false`",
        "Formal use allowed: `formal_use_allowed=true`",
    )
    signoff = signoff.replace(
        "Closure approved: `closure_approved=false`",
        "Closure approved: `closure_approved=true`",
    )
    signoff = signoff.replace("- `approves_metric_or_page=false`", "- `approves_metric_or_page=true`")
    signoff = signoff.replace("- `writes_governance_records=false`", "- `writes_governance_records=true`")
    signoff = signoff.replace(
        "- `proves_capture_ready_page_execution=false`",
        "- `proves_capture_ready_page_execution=true`",
    )
    signoff = signoff.replace(
        "- `captures_business_owner_approval=false`",
        "- `captures_business_owner_approval=true`",
    )
    signoff = signoff.replace("- `certification_effect=none`", "- `certification_effect=certifies_page`")
    signoff = signoff.replace(
        "This packet is prepared for business-owner and risk-owner review only. "
        "It does not approve page closure, metric formal use, or portfolio decision-grade wording.",
        "This packet approves page closure, metric formal use, and portfolio decision-grade wording.",
    )
    signoff = signoff.replace(
        "This handoff does not capture approval, write governance records, prove capture-ready "
        "page parity, or grant closure. Keep `formal_use_allowed=false` and "
        "`closure_approved=false` until business-owner approval and rematerialized evidence are "
        "explicitly captured.",
        "This handoff captures approval, writes governance records, proves capture-ready page "
        "parity, and grants closure.",
    )
    signoff_path.write_text(signoff, encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "full_closure_signoff_packet_formal_use_allowed_scope_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_closure_approved_scope_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_approves_metric_or_page_scope_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_writes_governance_records_scope_mismatch" in report["blockers"]
    assert (
        "full_closure_signoff_packet_proves_capture_ready_page_execution_scope_mismatch"
        in report["blockers"]
    )
    assert (
        "full_closure_signoff_packet_captures_business_owner_approval_scope_mismatch"
        in report["blockers"]
    )
    assert "full_closure_signoff_packet_certification_effect_scope_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_decision_boundary_scope_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_reviewer_handoff_scope_mismatch" in report["blockers"]


def test_portfolio_home_evidence_packet_guard_blocks_signoff_boundary_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    signoff_path = docs_root / "portfolio" / "portfolio-home-full-closure-sign-off-packet.md"
    signoff = signoff_path.read_text(encoding="utf-8")
    signoff = signoff.replace("Page ID: `PAGE-PORTFOLIO-HOME-001`", "Page ID: `PAGE-DRIFT`")
    signoff = signoff.replace("Current closure score: `99.86 / 100`", "Current closure score: `100.00 / 100`")
    signoff = signoff.replace("Remaining full-score gap: `0.14`", "Remaining full-score gap: `0.00`")
    signoff = signoff.replace(
        "Closure scorecard reports `score_status=blocked` and `full_score_ready=false`.",
        "Closure scorecard reports `score_status=ready_for_full_score` and `full_score_ready=true`.",
    )
    signoff = signoff.replace(
        "Evidence snapshot reports `snapshot_kind=portfolio_home_closure_evidence`, "
        "`score_status=blocked`, `full_score_ready=false`, and an embedded verifier status of "
        "`matched_expected_blocked_state`.",
        "Evidence snapshot reports `snapshot_kind=portfolio_home_closure_evidence`, "
        "`score_status=ready_for_full_score`, `full_score_ready=true`, and an embedded verifier "
        "status of `matched_expected_blocked_state`.",
    )
    signoff = signoff.replace("`owner_decision_intake_blocked`.", ".")
    signoff_path.write_text(signoff, encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "full_closure_signoff_packet_page_id_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_current_score_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_remaining_gap_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_score_status_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_full_score_ready_mismatch" in report["blockers"]
    assert "full_closure_signoff_packet_score_blockers_mismatch" in report["blockers"]
    artifacts = {artifact["name"]: artifact for artifact in report["artifacts"]}
    assert artifacts["full_closure_signoff_packet"]["boundary_status"] == "blocked"


def test_portfolio_home_evidence_packet_guard_rejects_negative_limit() -> None:
    with pytest.raises(ValueError) as error:
        build_report(docs_root=ROOT / "docs", limit=-1)

    assert str(error.value) == "Portfolio-home evidence packet guard limit must be non-negative: -1"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home evidence packet guard limit must be non-negative: -1" in completed.stderr
