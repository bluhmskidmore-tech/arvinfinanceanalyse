"""Scoring-integrity regression tests for the agent-eval harness.

Pins the fail-closed semantics of the scoring pipeline
(``collect_measured_result`` -> ``validate_measured_result`` ->
``evaluate_result``): untrusted or unmeasured input must void the scorecard
or degrade the score, never inflate it.

Tests named ``test_known_gap_*`` pin behaviour that is currently NOT
intercepted. They pass on purpose and serve as red/green anchors for the
follow-up hardening work: once the corresponding fix lands, the assertions
must be inverted as described in each docstring.
"""

import json
import subprocess

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

from scripts.agent_eval.collect import CommandOutcome, collect_measured_result
from scripts.agent_eval.reward import DEFAULT_WEIGHTS, PASS_THRESHOLD, evaluate_result
from scripts.agent_eval.spec import (
    MEASUREMENT_SOURCE,
    validate_measured_result,
    validate_task_spec,
)


def _runner(exit_codes=None):
    codes = exit_codes or {}

    def run(command, cwd, timeout_seconds):
        return CommandOutcome(exit_code=codes.get(command, 0), duration_ms=1)

    return run


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit(repo, relative_path, content):
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", relative_path)
    _git(repo, "commit", "-m", f"add {relative_path}")
    return path


@pytest.fixture
def git_repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "harness@example.com")
    _git(tmp_path, "config", "user.name", "harness")
    _commit(tmp_path, "seed.txt", "seed\n")
    return tmp_path


def _task(**overrides):
    """A spec-valid task whose gates, check, and evidence can all be satisfied."""

    task = {
        "id": "scoring_integrity_demo_001",
        "page": "ledger-pnl",
        "goal": "Regression fixture for fail-closed scoring semantics.",
        "required_evidence": ["moss-metric-contracts"],
        "evidence_probes": {"moss-metric-contracts": "evidence/contracts.json"},
        "checks": ["run-unit-tests"],
        "business_gates": ["unit_consistency"],
        "page_gates": ["no_console_errors"],
        "gate_probes": {
            "unit_consistency": "python -m pytest tests/probe_unit_consistency.py -q",
            "no_console_errors": "python -m pytest tests/probe_console_errors.py -q",
        },
        "allowed_scope": ["frontend/src/features/ledger-pnl/", "evidence/"],
        "forbidden": ["frontend/src/api/client.ts"],
    }
    task.update(overrides)
    return validate_task_spec(task)


def _perfect_result(**overrides):
    """A hand-written result that would score 100 for ``_task()`` on its own."""

    result = {
        "evidence": ["moss-metric-contracts"],
        "checks": {"run-unit-tests": "passed"},
        "business_gates": {"unit_consistency": True},
        "page_gates": {"no_console_errors": True},
        "changed_files": ["frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx"],
    }
    result.update(overrides)
    return result


def _write_evidence(repo, content):
    artifact = repo / "evidence" / "contracts.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(content, encoding="utf-8")
    return artifact


def test_scorecard_is_void_when_protected_probe_file_changes(git_repo):
    """A committed probe target listed in probe_protected_paths is modified
    during the run: the measurement must be untrusted and the enforced
    validation step must raise, voiding the scorecard before any scoring."""

    probe_target = _commit(
        git_repo, "tests/test_ledger_pnl_contract.py", "def test_real():\n    assert True\n"
    )
    probe_target.write_text("def test_noop():\n    pass\n", encoding="utf-8")
    task = _task(probe_protected_paths=["tests/test_ledger_pnl_contract.py"])

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())

    assert result["measurement"]["integrity"]["trusted"] is False
    with pytest.raises(ValueError, match="Gate probe target modified"):
        validate_measured_result(result)


def test_empty_evidence_artifact_yields_missing_evidence_hard_failure(git_repo):
    """A zero-byte evidence artifact must not count as evidence, and the
    resulting hard failure must fail the scorecard even when the numeric
    score still reaches the pass threshold."""

    _write_evidence(git_repo, "")
    task = _task()

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())
    scorecard = evaluate_result(task, result)

    assert result["evidence"] == []
    assert "Missing required evidence: moss-metric-contracts" in scorecard["hard_failures"]
    assert scorecard["score"] >= PASS_THRESHOLD
    assert scorecard["status"] == "fail"


def test_out_of_scope_change_zeroes_diff_score_and_fails_scorecard():
    """A changed file outside a non-empty allowed_scope is a warning, not a
    hard failure, but it must zero the diff component and fail the card."""

    task = _task()
    result = _perfect_result(
        changed_files=[
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
            "backend/app/core_finance/pnl_engine.py",
        ]
    )

    scorecard = evaluate_result(task, result)

    assert scorecard["breakdown"]["diff"] == 0.0
    assert scorecard["score"] == 80.0
    assert scorecard["status"] == "fail"
    assert scorecard["hard_failures"] == []
    assert (
        "Out-of-scope path changed: backend/app/core_finance/pnl_engine.py"
        in scorecard["warnings"]
    )


def test_forbidden_path_change_is_hard_failure_even_inside_allowed_scope():
    """A forbidden path in changed_files is a hard failure and fails the
    scorecard even when the path also sits inside allowed_scope, so the
    block cannot be laundered through a generous scope declaration."""

    task = _task(
        allowed_scope=["frontend/src/features/ledger-pnl/"],
        forbidden=["frontend/src/features/ledger-pnl/api/client.ts"],
    )
    result = _perfect_result(
        changed_files=["frontend/src/features/ledger-pnl/api/client.ts"]
    )

    scorecard = evaluate_result(task, result)

    assert (
        "Forbidden path changed: frontend/src/features/ledger-pnl/api/client.ts"
        in scorecard["hard_failures"]
    )
    assert scorecard["status"] == "fail"
    assert scorecard["breakdown"]["diff"] == 0.0
    assert scorecard["warnings"] == []


def test_self_reported_result_is_rejected():
    """A hand-written result that never went through the collector scores a
    perfect 100 if fed straight to the reward function, which is exactly why
    the enforced validation step must reject it for lacking a measurement."""

    task = _task()
    self_reported = _perfect_result()

    scorecard = evaluate_result(task, self_reported)
    assert scorecard["score"] == 100
    assert scorecard["status"] == "pass"

    with pytest.raises(ValueError, match="'measurement' is required"):
        validate_measured_result(self_reported)


@pytest.mark.parametrize(
    ("measurement", "match"),
    [
        pytest.param(
            {"source": "agent-self-report", "schema_version": 1, "integrity": {"trusted": True}},
            "must be produced by",
            id="foreign-source",
        ),
        pytest.param(
            {"source": MEASUREMENT_SOURCE, "schema_version": 999, "integrity": {"trusted": True}},
            "Unsupported measurement schema_version",
            id="wrong-schema-version",
        ),
        pytest.param(
            {"source": MEASUREMENT_SOURCE, "schema_version": 1},
            "missing the 'integrity' block",
            id="integrity-block-missing",
        ),
        pytest.param(
            {"source": MEASUREMENT_SOURCE, "schema_version": 1, "integrity": {}},
            "Measurement is not trustworthy",
            id="trusted-flag-missing",
        ),
        pytest.param(
            {
                "source": MEASUREMENT_SOURCE,
                "schema_version": 1,
                "integrity": {
                    "trusted": False,
                    "violations": ["Gate probe target modified during the run: tests/test_x.py"],
                },
            },
            "Gate probe target modified",
            id="trusted-false-with-violations",
        ),
    ],
)
def test_measurement_with_forged_or_untrusted_provenance_is_rejected(measurement, match):
    """A measurement block whose source is not the collector, whose schema
    version is unknown, or whose integrity is absent/untrusted must be
    rejected regardless of how good the accompanying numbers look."""

    result = _perfect_result(measurement=measurement)

    with pytest.raises(ValueError, match=match):
        validate_measured_result(result)


def test_harness_self_edit_voids_the_measurement(git_repo):
    """The harness always protects its own scoring code.

    ``scripts/agent_eval/`` is in the collector's built-in protection list
    (``HARNESS_SELF_PATHS``), so a tracked mid-run modification of the
    harness's own ``reward.py`` voids the measurement even when the task's
    ``forbidden`` / ``probe_protected_paths`` lists never mention it.
    """

    harness_file = _commit(git_repo, "scripts/agent_eval/reward.py", "PASS_THRESHOLD = 90\n")
    harness_file.write_text("PASS_THRESHOLD = 0\n", encoding="utf-8")
    task = _task()

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())

    integrity = result["measurement"]["integrity"]
    assert "scripts/agent_eval/reward.py" in result["changed_files"]
    assert integrity["trusted"] is False
    assert any("scripts/agent_eval/reward.py" in violation for violation in integrity["violations"])
    with pytest.raises(ValueError, match="Measurement is not trustworthy"):
        validate_measured_result(result)


def test_known_gap_empty_allowed_scope_skips_out_of_scope_detection():
    """KNOWN GAP at the reward layer, mitigated at the spec layer.

    ``reward._diff_ratio`` guards the scope check with ``if allowed_scope
    and ...``, so ``allowed_scope: []`` means "unlimited" rather than
    "nothing may change". ``validate_task_spec`` now rejects tasks with an
    empty ``allowed_scope``, so a shipped task cannot hit this branch; the
    library-level laxity remains for callers that skip spec validation and
    is pinned here. If ``reward._diff_ratio`` ever changes semantics,
    invert these assertions (expect warnings, ``breakdown["diff"] == 0.0``,
    status "fail").
    """

    # Built without _task(): validate_task_spec now (correctly) rejects an
    # empty allowed_scope, and this test pins the reward layer beneath it.
    task = dict(_task())
    task["allowed_scope"] = []
    result = _perfect_result(
        changed_files=[
            "backend/app/core_finance/pnl_engine.py",
            "scripts/agent_eval/reward.py",
        ]
    )

    scorecard = evaluate_result(task, result)

    assert scorecard["warnings"] == []
    assert scorecard["breakdown"]["diff"] == DEFAULT_WEIGHTS["diff"]
    assert scorecard["score"] == 100
    assert scorecard["status"] == "pass"


def test_placeholder_evidence_artifact_is_rejected_by_the_minimal_schema(git_repo):
    """An evidence artifact must be a JSON object with a non-empty ``source``.

    A placeholder artifact (``{"placeholder": true}``) with no relationship
    to the declared evidence parses as JSON but names no ``source``, so the
    collector records it as ``missing_source`` instead of "present": the
    evidence list stays empty and the scorecard carries a "Missing required
    evidence" hard failure instead of a perfect pass.
    """

    _write_evidence(git_repo, json.dumps({"placeholder": True}))
    task = _task()

    result = collect_measured_result(task, repo_root=git_repo, run_command=_runner())
    scorecard = evaluate_result(task, result)

    assert result["evidence"] == []
    assert result["measurement"]["evidence_artifacts"][0]["status"] == "missing_source"
    assert "Missing required evidence: moss-metric-contracts" in scorecard["hard_failures"]
    assert scorecard["status"] == "fail"
