"""Caliber path-trigger gate for PR CI.

The six caliber red-line tests (tests/test_caliber_rule_*.py) are also
unconditional members of the bounded release suite
(scripts/backend_release_suite.py, since 2026-08-12). This gate is the
targeted fast-reaction half of that double insurance: when the PR diff
touches a source module that a caliber test imports, the matching test files
are run directly, so a caliber regression is attributed to the exact diff
that caused it instead of surfacing as a generic suite failure.

``CALIBER_GATE_MAP`` is derived from the import statements of the six caliber
test files (including ``importlib.import_module(DESCRIPTOR.canonical_module)``
targets asserted inside those tests). ``tests/test_caliber_gate_mapping.py``
guards the map against drift (paths must exist; every caliber test file must
stay mapped).

Usage::

    python scripts/check_caliber_gate.py --base-ref origin/main [--dry-run]

Fail-closed: if the diff against ``--base-ref`` cannot be computed (unknown
ref, git unavailable, not a repository), the gate exits non-zero instead of
silently passing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_TEST_ACCOUNTING_BASIS = "tests/test_caliber_rule_accounting_basis.py"
_TEST_FORMAL_SCENARIO_GATE = "tests/test_caliber_rule_formal_scenario_gate.py"
_TEST_FX_MID_CONVERSION = "tests/test_caliber_rule_fx_mid_conversion.py"
_TEST_HAT_MAPPING = "tests/test_caliber_rule_hat_mapping.py"
_TEST_ISSUANCE_EXCLUSION = "tests/test_caliber_rule_issuance_exclusion.py"
_TEST_SUBJECT_MERGE = "tests/test_caliber_rule_subject_514_516_517_merge.py"

_ALL_CALIBER_TESTS = (
    _TEST_ACCOUNTING_BASIS,
    _TEST_FORMAL_SCENARIO_GATE,
    _TEST_FX_MID_CONVERSION,
    _TEST_HAT_MAPPING,
    _TEST_ISSUANCE_EXCLUSION,
    _TEST_SUBJECT_MERGE,
)

# Source file -> caliber test files that must run when the file changes.
# Keys are repo-relative POSIX paths; a key ending with "/" is a prefix match.
CALIBER_GATE_MAP: dict[str, tuple[str, ...]] = {
    # Shared caliber framework: every caliber test starts with
    # `from backend.app.core_finance.calibers import ...`. The package
    # __init__ re-exports enums/descriptor/registry symbols used by the
    # tests (Basis/View/Resolution/ALL_CELLS, get_caliber_rule,
    # assert_canonical_callsite, CaliberCalibrationViolation), and
    # rules/__init__ side-effect-registers every bundled rule descriptor
    # (asserted by each test's *_is_registered_after_package_import case).
    "backend/app/core_finance/calibers/__init__.py": _ALL_CALIBER_TESTS,
    "backend/app/core_finance/calibers/descriptor.py": _ALL_CALIBER_TESTS,
    "backend/app/core_finance/calibers/enums.py": _ALL_CALIBER_TESTS,
    "backend/app/core_finance/calibers/registry.py": _ALL_CALIBER_TESTS,
    "backend/app/core_finance/calibers/rules/__init__.py": _ALL_CALIBER_TESTS,
    # Rule modules: each caliber test imports its own DESCRIPTOR module.
    "backend/app/core_finance/calibers/rules/accounting_basis.py": (
        _TEST_ACCOUNTING_BASIS,
    ),
    "backend/app/core_finance/calibers/rules/formal_scenario_gate.py": (
        _TEST_FORMAL_SCENARIO_GATE,
    ),
    "backend/app/core_finance/calibers/rules/fx_mid_conversion.py": (
        _TEST_FX_MID_CONVERSION,
    ),
    "backend/app/core_finance/calibers/rules/hat_mapping.py": (
        _TEST_HAT_MAPPING,
    ),
    "backend/app/core_finance/calibers/rules/issuance_exclusion.py": (
        _TEST_ISSUANCE_EXCLUSION,
    ),
    "backend/app/core_finance/calibers/rules/subject_514_516_517_merge.py": (
        _TEST_SUBJECT_MERGE,
    ),
    # Canonical modules imported by specific tests, either statically
    # (subject merge: LEDGER_PNL_ACCOUNT_PREFIXES; accounting basis:
    # derive_accounting_basis_value) or via
    # importlib.import_module(DESCRIPTOR.canonical_module) (hat mapping,
    # issuance exclusion, fx mid conversion).
    "backend/app/core_finance/config/classification_rules.py": (
        _TEST_HAT_MAPPING,
        _TEST_ISSUANCE_EXCLUSION,
        _TEST_SUBJECT_MERGE,
    ),
    "backend/app/core_finance/field_normalization.py": (
        _TEST_ACCOUNTING_BASIS,
    ),
    "backend/app/core_finance/fx_rates.py": (
        _TEST_FX_MID_CONVERSION,
    ),
}


class CaliberGateError(RuntimeError):
    """Raised when the PR diff cannot be determined; callers must fail closed."""


def _matches(changed_file: str, map_key: str) -> bool:
    if map_key.endswith("/"):
        return changed_file.startswith(map_key)
    return changed_file == map_key


def resolve_required_tests(
    changed_files: Iterable[str],
    gate_map: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Return the sorted caliber test files required by *changed_files*."""
    if gate_map is None:
        gate_map = CALIBER_GATE_MAP
    required: set[str] = set()
    for changed in changed_files:
        normalized = changed.replace("\\", "/").strip()
        if not normalized:
            continue
        for source, tests in gate_map.items():
            if _matches(normalized, source):
                required.update(tests)
    return sorted(required)


def list_changed_files(base_ref: str, *, cwd: Path) -> list[str]:
    """List files changed between the merge base of *base_ref* and HEAD."""
    command = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as exc:
        raise CaliberGateError(
            f"unable to invoke git ({exc}); refusing to skip the caliber gate"
        ) from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise CaliberGateError(
            f"git diff failed for base ref '{base_ref}' "
            f"(exit code {completed.returncode}): {stderr or '<no stderr>'}"
        )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run caliber red-line tests when the diff against --base-ref "
            "touches mapped backend/app/core_finance source files."
        )
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Git ref the PR diff is compared against, e.g. origin/main.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print base ref, changed files and matched tests as JSON; do not run pytest.",
    )
    args = parser.parse_args(argv)

    try:
        changed_files = list_changed_files(args.base_ref, cwd=ROOT)
    except CaliberGateError as exc:
        print(f"caliber-gate: FAIL-CLOSED: {exc}", file=sys.stderr)
        print(
            "caliber-gate: the PR diff could not be computed, so the gate "
            "refuses to pass silently. Fix the base ref / git setup and rerun.",
            file=sys.stderr,
        )
        return 2

    matched_tests = resolve_required_tests(changed_files)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "base_ref": args.base_ref,
                    "changed_files": changed_files,
                    "matched_tests": matched_tests,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not matched_tests:
        print(
            "caliber-gate: no caliber-mapped core_finance source changed vs "
            f"'{args.base_ref}'; nothing to run."
        )
        return 0

    print(
        f"caliber-gate: diff vs '{args.base_ref}' requires "
        f"{len(matched_tests)} caliber test file(s):"
    )
    for test_file in matched_tests:
        print(f"  - {test_file}")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *matched_tests, "-q"],
        cwd=ROOT,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
