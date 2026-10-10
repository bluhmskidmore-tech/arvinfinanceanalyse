"""W-CI-gate-2026-04-21 — locks in zero-violations contract for caliber inline audits.

This module is intentionally **stricter in intent** than ``test_audit_caliber_violations_script.py``:
those tests exercise the audit *mechanism* (regex shapes, suppression / skip logic, report
IO). This file asserts the *outcome* on the live repo: every registered rule must currently
have zero unjustified violations when ``scan_violations`` runs over the real tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.scripts.audit_caliber_violations import (
    _GATE_ENFORCED_RULES,
    KNOWN_RULES,
    scan_violations,
)

ROOT = Path(__file__).resolve().parents[1]


def test_known_rules_registry_has_at_least_five() -> None:
    assert len(KNOWN_RULES) >= 5


def test_accounting_basis_is_gate_enforced() -> None:
    assert "accounting_basis" in KNOWN_RULES
    assert "accounting_basis" in _GATE_ENFORCED_RULES


@pytest.mark.parametrize("rule_id", tuple(sorted(_GATE_ENFORCED_RULES)))
def test_caliber_audit_zero_unjustified_violations(rule_id: str) -> None:
    violations, _suppressed = scan_violations(rule_id, project_root=ROOT)
    if violations:
        lines: list[str] = []
        for v in violations[:3]:
            lines.append(f"  {v['file']}:{v['line']} — {v['snippet']!r}")
        pytest.fail(
            f"Rule {rule_id!r} has {len(violations)} unjustified violation(s). "
            f"First up to 3 (file:line + snippet):\n"
            + "\n".join(lines)
            + f"\nIf a hit is intentional, add `# Human: caliber-{rule_id}-justified` "
            "(or equivalent marker in lookback) per audit script rules."
        )


@pytest.mark.parametrize(
    ("formal_use_entry", "expected_patterns"),
    [
        ('"formal_use_allowed": False,', set()),
        ('"formal_use_allowed": True,', {"basis_eq_scenario_str"}),
        ("", {"basis_eq_scenario_str"}),
        ('"formal_use_allowed": allowed,', {"basis_eq_scenario_str"}),
        ('"formal_use_allowed": False, **overrides,', {"basis_eq_scenario_str"}),
        ('"formal_use_allowed": True, "formal_use_allowed": False,', {"basis_eq_scenario_str"}),
    ],
)
def test_scenario_metadata_context_requires_unambiguous_formal_use_false(
    tmp_path: Path, formal_use_entry: str, expected_patterns: set[str]
) -> None:
    services = tmp_path / "backend" / "app" / "services"
    services.mkdir(parents=True)
    (services / "metadata.py").write_text(
        "def cancelled_meta(request):\n"
        f"    return {{{formal_use_entry} \"scenario_flag\": request.basis == \"scenario\"}}\n",
        encoding="utf-8",
    )

    violations, suppressed = scan_violations("formal_scenario_gate", project_root=tmp_path)

    assert {item["pattern_id"] for item in violations} == expected_patterns
    assert suppressed == 0


def test_closed_metadata_does_not_hide_an_actual_gate_on_the_same_line(tmp_path: Path) -> None:
    services = tmp_path / "backend" / "app" / "services"
    services.mkdir(parents=True)
    (services / "gate.py").write_text(
        "def inline_gate(request):\n"
        "    return ({\"formal_use_allowed\": False, \"scenario_flag\": request.basis == \"scenario\"}, request.basis == \"scenario\")\n",
        encoding="utf-8",
    )

    violations, suppressed = scan_violations("formal_scenario_gate", project_root=tmp_path)

    assert [item["pattern_id"] for item in violations] == ["basis_eq_scenario_str"]
    assert suppressed == 0


@pytest.mark.parametrize(
    ("branch_body", "fallback", "expected_patterns"),
    [
        ('return "formal_calendar"', 'return "snapshot_calendar"', set()),
        ("return True", "return False", {"if_formal_branch"}),
        ('authorize()\n        return "formal_calendar"', 'return "snapshot_calendar"', {"if_formal_branch"}),
    ],
)
def test_source_provenance_context_requires_literal_labels_and_no_side_effects(
    tmp_path: Path, branch_body: str, fallback: str, expected_patterns: set[str]
) -> None:
    services = tmp_path / "backend" / "app" / "services"
    services.mkdir(parents=True)
    (services / "provenance.py").write_text(
        "def combine_sources(bases):\n"
        "    has_formal = any(\"formal\" in basis for basis in bases)\n"
        "    has_snapshot = any(\"snapshot\" in basis for basis in bases)\n"
        "    if has_formal and has_snapshot:\n"
        "        return \"formal+snapshot_calendar\"\n"
        f"    if has_formal:\n        {branch_body}\n"
        f"    {fallback}\n",
        encoding="utf-8",
    )

    violations, suppressed = scan_violations("formal_scenario_gate", project_root=tmp_path)

    assert {item["pattern_id"] for item in violations} == expected_patterns
    assert suppressed == 0
