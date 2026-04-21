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
    KNOWN_RULES,
    _GATE_ENFORCED_RULES,
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
