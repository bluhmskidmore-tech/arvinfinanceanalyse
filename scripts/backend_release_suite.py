from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_governance_lineage import audit_governance_lineage

RELEASE_SUITE_NAME = "governed-phase2-backend-release-suite"
RELEASE_SUITE_TESTS = [
    "tests/test_settings_contract.py",
    "tests/test_health_endpoints.py",
    "tests/test_positions_api_contract.py",
    "tests/test_pnl_api_contract.py",
    "tests/test_risk_tensor_api.py",
    "tests/test_balance_analysis_api.py",
    "tests/test_bond_analytics_api.py",
    "tests/test_executive_dashboard_endpoints.py",
    "tests/test_cube_query_api.py",
    "tests/test_liability_analytics_api.py",
    "tests/test_liability_analytics_envelope_contract.py",
    "tests/test_result_meta_on_all_ui_endpoints.py",
    "tests/test_governance_doc_contract.py",
    "tests/test_golden_samples_capture_ready.py",
]


def _release_suite_env() -> dict[str, str]:
    return {
        "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS": "1",
        "MOSS_SKIP_POSTGRES_MIGRATIONS": "1",
    }


def _pytest_args() -> list[str]:
    return ["-m", "pytest", "-q", *RELEASE_SUITE_TESTS]


def _write_governance_audit_output(
    summary: dict[str, object],
    output_path: str | Path | None,
) -> None:
    if output_path is None:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def build_release_suite_plan(
    *,
    governance_dir: str = "data/governance",
    governance_audit_output: str | None = None,
) -> dict[str, object]:
    return {
        "suite_name": RELEASE_SUITE_NAME,
        "governance_dir": governance_dir,
        "governance_audit_output": governance_audit_output,
        "pytest_args": _pytest_args(),
        "env": _release_suite_env(),
    }


def run_release_suite(
    *,
    root: Path = ROOT,
    governance_dir: str = "data/governance",
    governance_audit_output: str | Path | None = None,
) -> int:
    summary = audit_governance_lineage(root / governance_dir)
    _write_governance_audit_output(summary, governance_audit_output)
    if int(summary.get("dirty_rows", 0)) != 0:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1

    env = os.environ.copy()
    env.update(_release_suite_env())
    completed = subprocess.run(
        ["python", *_pytest_args()],
        cwd=root,
        env=env,
        check=False,
    )
    return int(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--governance-dir", default="data/governance")
    parser.add_argument("--governance-audit-output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(
            json.dumps(
                build_release_suite_plan(
                    governance_dir=args.governance_dir,
                    governance_audit_output=args.governance_audit_output,
                ),
                ensure_ascii=False,
            )
        )
        return 0

    return run_release_suite(
        governance_dir=args.governance_dir,
        governance_audit_output=args.governance_audit_output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
