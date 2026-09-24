"""Path-triggered PR regressions for caliber and the balance update flow.

The six caliber red-line tests (tests/test_caliber_rule_*.py) are also
unconditional members of the bounded release suite
(scripts/backend_release_suite.py, since 2026-08-12). This gate is the
targeted fast-reaction half of that double insurance: when the PR diff
touches a mapped source module, the matching test files run directly, so a
regression is attributed to the diff that caused it instead of surfacing as
a generic suite failure.

``CALIBER_GATE_MAP`` includes the imports of the six caliber test files
(including ``importlib.import_module(DESCRIPTOR.canonical_module)`` targets)
and focused numerical goldens for the curve engine and PnL bridge. The same
fail-closed selector also covers the first-scope data-update and balance-read
paths on codex/V1; frontend changes select a separate bounded Vitest job.
``tests/test_caliber_gate_mapping.py`` guards the map against drift: mapped
paths must exist, and every caliber test file must stay mapped.

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
_TEST_CURVE = "tests/test_curve_engine_golden.py"
_TEST_PNL_BRIDGE = "tests/test_pnl_bridge_golden.py"
_TEST_PNL_BRIDGE_DURATION = "tests/test_pnl_bridge_modified_duration.py"
_TEST_DATA_UPDATES = "tests/test_data_updates.py"
_TEST_DATA_UPDATE_BALANCE_INTEGRATION = "tests/test_data_update_balance_integration.py"
_TEST_QUEUE_LAUNCHER = "tests/test_data_update_queue_launcher_logging.py"
_TEST_QUEUE_INSTALLER = "tests/test_install_data_update_queue.py"
_TEST_DATA_HEALTH = "tests/test_data_health.py"
_TEST_GLOBAL_REFRESH = "tests/test_global_data_refresh.py"
_TEST_BALANCE_API = "tests/test_balance_analysis_api.py"
_TEST_BALANCE_CORE = "tests/test_balance_analysis_core.py"

_ALL_CALIBER_TESTS = (
    _TEST_ACCOUNTING_BASIS,
    _TEST_FORMAL_SCENARIO_GATE,
    _TEST_FX_MID_CONVERSION,
    _TEST_HAT_MAPPING,
    _TEST_ISSUANCE_EXCLUSION,
    _TEST_SUBJECT_MERGE,
)

# Source file -> regression test files that must run when the file changes.
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
    # Curve goldens exercise the four engine modules; the bridge golden also
    # checks the downstream PnL effect of curve inputs.
    "backend/app/core_finance/curve_engine/": (_TEST_CURVE, _TEST_PNL_BRIDGE),
    "backend/app/core_finance/pnl_bridge.py": (
        _TEST_PNL_BRIDGE,
        _TEST_PNL_BRIDGE_DURATION,
    ),
    # First-scope request, receipt, and balance read path on codex/V1.
    "backend/app/api/__init__.py": (_TEST_DATA_UPDATES, _TEST_DATA_UPDATE_BALANCE_INTEGRATION),
    "backend/app/api/routes/data_updates.py": (_TEST_DATA_UPDATES, _TEST_DATA_UPDATE_BALANCE_INTEGRATION),
    "backend/app/repositories/data_update_repo.py": (_TEST_DATA_UPDATES, _TEST_DATA_UPDATE_BALANCE_INTEGRATION),
    "backend/app/schemas/data_updates.py": (_TEST_DATA_UPDATES, _TEST_DATA_UPDATE_BALANCE_INTEGRATION),
    "backend/app/services/data_update_service.py": (_TEST_DATA_UPDATES, _TEST_DATA_UPDATE_BALANCE_INTEGRATION),
    "backend/app/tasks/data_update_center.py": (_TEST_DATA_UPDATES, _TEST_DATA_UPDATE_BALANCE_INTEGRATION),
    "backend/app/api/routes/data_health.py": (_TEST_DATA_HEALTH, _TEST_DATA_UPDATES),
    "backend/app/services/data_health_service.py": (_TEST_DATA_HEALTH, _TEST_DATA_UPDATES),
    "scripts/run_global_data_refresh.py": (_TEST_GLOBAL_REFRESH, _TEST_DATA_UPDATES),
    "scripts/scheduling/drain_data_updates.ps1": (_TEST_QUEUE_LAUNCHER, _TEST_QUEUE_INSTALLER),
    "scripts/scheduling/install_data_update_queue.ps1": (_TEST_QUEUE_INSTALLER,),
    "backend/app/api/routes/balance_analysis.py": (_TEST_BALANCE_API,),
    "backend/app/schemas/balance_analysis.py": (_TEST_BALANCE_API,),
    "backend/app/services/balance_analysis_service.py": (_TEST_BALANCE_API,),
    "backend/app/repositories/balance_analysis_repo.py": (_TEST_BALANCE_API,),
    "backend/app/tasks/balance_analysis_materialize.py": (_TEST_BALANCE_API,),
    "backend/app/core_finance/balance_analysis.py": (
        _TEST_BALANCE_CORE,
        _TEST_BALANCE_API,
    ),
    _TEST_DATA_UPDATES: (_TEST_DATA_UPDATES,),
    _TEST_DATA_UPDATE_BALANCE_INTEGRATION: (_TEST_DATA_UPDATE_BALANCE_INTEGRATION,),
    _TEST_QUEUE_LAUNCHER: (_TEST_QUEUE_LAUNCHER,),
    _TEST_QUEUE_INSTALLER: (_TEST_QUEUE_INSTALLER,),
    _TEST_BALANCE_API: (_TEST_BALANCE_API,),
}

# Relevant frontend edits need the bounded page/API checks in the V1 PR job.
# Keep these paths exact where possible so unrelated features do not install npm.
FRONTEND_FIRST_SCOPE_PATHS = (
    "frontend/src/features/platform-config/",
    "frontend/src/features/balance-analysis/",
    "frontend/src/api/dataUpdatesClient.ts",
    "frontend/src/api/dataUpdatesClient.test.ts",
    "frontend/src/api/balanceAnalysisClient.ts",
    "frontend/src/api/balanceAnalysisClient.datesContract.test.ts",
    "frontend/src/api/balanceMovementClient.ts",
    "frontend/src/api/balanceMovementClient.test.ts",
    "frontend/src/api/homeSupplementalClient.ts",
    "frontend/src/api/clientContext.ts",
    "frontend/src/api/transport.ts",
    "frontend/src/api/contracts/balanceLedger.ts",
    "frontend/src/test/PlatformConfigPage.test.tsx",
    "frontend/src/test/BalanceAnalysisDateSemanticsContract.test.tsx",
    "frontend/src/test/BalanceAnalysisPage.test.tsx",
    "frontend/src/test/BalanceMovementRequestBoundary.test.tsx",
    "frontend/tests/playwright/data-update-center-balance-daily.spec.mjs",
)

DATA_UPDATE_BROWSER_PATHS = (
    "frontend/src/features/platform-config/",
    "frontend/src/api/dataUpdatesClient.ts",
    "frontend/src/api/dataUpdatesClient.test.ts",
    "frontend/src/api/balanceAnalysisClient.ts",
    "frontend/src/api/homeSupplementalClient.ts",
    "frontend/tests/playwright/data-update-center-balance-daily.spec.mjs",
)

SCHEDULER_WINDOWS_PATHS = (
    "scripts/scheduling/drain_data_updates.ps1",
    "scripts/scheduling/install_data_update_queue.ps1",
    _TEST_QUEUE_LAUNCHER,
    _TEST_QUEUE_INSTALLER,
)

# Formal calculation and release-cutoff edits still require the canonical
# bounded release suite; ordinary data-update orchestration does not.
FORMAL_RELEASE_PATHS = (
    "backend/app/core_finance/",
    "backend/app/tasks/formal_balance_pipeline.py",
    "backend/app/tasks/balance_analysis_materialize.py",
    "scripts/backend_release_suite.py",
    "docs/V3_CUTOFF_EXIT_CRITERIA.md",
)


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
    """Return the sorted mapped test files required by *changed_files*."""
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


def selects_frontend_first_scope(changed_files: Iterable[str]) -> bool:
    """Whether the V1 PR needs first-scope frontend checks."""
    return any(
        _matches(changed.replace("\\", "/").strip(), source)
        for changed in changed_files
        for source in FRONTEND_FIRST_SCOPE_PATHS
    )


def selects_data_update_browser_scope(changed_files: Iterable[str]) -> bool:
    """Whether the V1 PR needs the synthetic daily-balance browser contract."""
    return any(
        _matches(changed.replace("\\", "/").strip(), source)
        for changed in changed_files
        for source in DATA_UPDATE_BROWSER_PATHS
    )


def selects_scheduler_windows_scope(changed_files: Iterable[str]) -> bool:
    """Whether the PowerShell scheduler contract needs a Windows runner."""
    return any(
        _matches(changed.replace("\\", "/").strip(), source)
        for changed in changed_files
        for source in SCHEDULER_WINDOWS_PATHS
    )


def selects_formal_release_scope(changed_files: Iterable[str]) -> bool:
    """Whether the V1 PR must run the existing backend release suite."""
    return any(
        _matches(changed.replace("\\", "/").strip(), source)
        for changed in changed_files
        for source in FORMAL_RELEASE_PATHS
    )


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
            "Run mapped regression tests when the diff against --base-ref "
            "touches mapped caliber, data-update, or balance source files."
        )
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Git ref the PR diff is compared against, e.g. origin/main.",
    )
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print base ref, changed files and matched tests as JSON; do not run pytest.",
    )
    output_mode.add_argument(
        "--frontend-scope",
        action="store_true",
        help="Print true/false for the bounded V1 frontend job; do not run pytest.",
    )
    output_mode.add_argument(
        "--data-update-browser-scope",
        action="store_true",
        help="Print true/false for the synthetic daily-balance browser check.",
    )
    output_mode.add_argument(
        "--scheduler-scope",
        action="store_true",
        help="Print true/false for the Windows scheduler contract checks.",
    )
    output_mode.add_argument(
        "--release-scope",
        action="store_true",
        help="Print true/false for the canonical backend release suite; do not run pytest.",
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

    if args.frontend_scope:
        print(str(selects_frontend_first_scope(changed_files)).lower())
        return 0

    if args.data_update_browser_scope:
        print(str(selects_data_update_browser_scope(changed_files)).lower())
        return 0

    if args.scheduler_scope:
        print(str(selects_scheduler_windows_scope(changed_files)).lower())
        return 0

    if args.release_scope:
        print(str(selects_formal_release_scope(changed_files)).lower())
        return 0

    if args.dry_run:
        print(
            json.dumps(
                {
                    "base_ref": args.base_ref,
                    "changed_files": changed_files,
                    "matched_tests": matched_tests,
                    "frontend_scope_selected": selects_frontend_first_scope(changed_files),
                    "data_update_browser_scope_selected": selects_data_update_browser_scope(changed_files),
                    "scheduler_windows_scope_selected": selects_scheduler_windows_scope(changed_files),
                    "release_scope_selected": selects_formal_release_scope(changed_files),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not matched_tests:
        print(
            "caliber-gate: no mapped backend source changed vs "
            f"'{args.base_ref}'; nothing to run."
        )
        return 0

    print(
        f"caliber-gate: diff vs '{args.base_ref}' requires "
        f"{len(matched_tests)} mapped test file(s):"
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
