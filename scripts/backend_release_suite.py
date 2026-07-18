from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_governance_lineage import audit_governance_lineage  # noqa: E402

RELEASE_SUITE_NAME = "governed-phase2-backend-release-suite"
GOVERNANCE_MCP_SUITE_NAME = "governance-mcp-contract-suite"
EXECUTIVE_RELEASE_SAMPLE_IDS = [
    "GS-EXEC-OVERVIEW-A",
    "GS-EXEC-PNL-ATTR-A",
    "GS-EXEC-SUMMARY-A",
]
RELEASE_SUITE_TESTS = [
    "tests/test_settings_contract.py",
    "tests/test_health_endpoints.py",
    "tests/test_positions_api_contract.py",
    "tests/test_pnl_api_contract.py",
    "tests/test_pnl_by_business_insights_contract.py",
    "tests/test_pnl_by_business_candidate_insights_contract.py",
    "tests/test_candidate_period_comparison_contract_alignment.py",
    "tests/test_risk_tensor_api.py",
    "tests/test_balance_analysis_api.py",
    "tests/test_bond_analytics_api.py",
    "tests/test_executive_dashboard_endpoints.py",
    "tests/test_cube_query_api.py",
    "tests/test_liability_analytics_api.py",
    "tests/test_liability_analytics_envelope_contract.py",
    "tests/test_result_meta_on_all_ui_endpoints.py",
    "tests/test_governance_lineage_audit.py",
    "tests/test_governance_doc_contract.py",
    "tests/test_golden_samples_capture_ready.py",
    "tests/test_ledger_pnl_net_interest_golden_sample.py",
    "tests/test_executive_release_contract.py",
    "tests/test_golden_sample_release_matrix.py",
    "tests/test_live_route_page_contract_completeness.py",
    "tests/test_no_finance_logic_in_frontend.py",
]
GOVERNANCE_MCP_FAST_SUITE_TESTS = ["tests/test_project_mcp_fast_contracts.py"]
GOVERNANCE_MCP_FULL_SUITE_TESTS = ["tests/test_project_mcp_servers.py"]


def _release_suite_env() -> dict[str, str]:
    return {
        "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS": "1",
        "MOSS_SKIP_POSTGRES_MIGRATIONS": "1",
        "MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST": "1",
    }


def _pytest_args() -> list[str]:
    return ["-m", "pytest", "-q", *RELEASE_SUITE_TESTS]


def _governance_mcp_pytest_args(mcp_profile: str = "fast") -> list[str]:
    if mcp_profile == "fast":
        return [
            "-m",
            "pytest",
            "-q",
            "-m",
            "mcp_fast",
            *GOVERNANCE_MCP_FAST_SUITE_TESTS,
        ]
    if mcp_profile == "full":
        return ["-m", "pytest", "-q", *GOVERNANCE_MCP_FULL_SUITE_TESTS]
    raise ValueError(f"Unsupported MCP profile: {mcp_profile}")


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
    live_governance_dir: str | None = None,
    governance_audit_output: str | None = None,
    mcp_profile: str = "fast",
) -> dict[str, object]:
    return {
        "suite_name": RELEASE_SUITE_NAME,
        "governance_audit": {
            "mode": "live" if live_governance_dir is not None else "fixture",
            "directory": live_governance_dir,
            "fail_on_empty": live_governance_dir is not None,
        },
        "governance_audit_output": governance_audit_output,
        "executive_release_sample_ids": EXECUTIVE_RELEASE_SAMPLE_IDS,
        "pytest_args": _pytest_args(),
        "governance_mcp_suite": {
            "suite_name": GOVERNANCE_MCP_SUITE_NAME,
            "profile": mcp_profile,
            "pytest_args": _governance_mcp_pytest_args(mcp_profile),
        },
        "env": _release_suite_env(),
    }


def run_release_suite(
    *,
    root: Path = ROOT,
    live_governance_dir: str | None = None,
    governance_audit_output: str | Path | None = None,
    mcp_profile: str = "fast",
) -> int:
    if live_governance_dir is not None:
        summary = audit_governance_lineage(root / live_governance_dir)
        _write_governance_audit_output(summary, governance_audit_output)
        if (
            int(summary.get("files_scanned", 0)) == 0
            or int(summary.get("rows_scanned", 0)) == 0
            or int(summary.get("dirty_rows", 0)) != 0
        ):
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 1

    with tempfile.TemporaryDirectory(prefix="moss-backend-release-") as storage_dir:
        isolated_root = Path(storage_dir)
        env = os.environ.copy()
        env.update(_release_suite_env())
        env["MOSS_GOVERNANCE_PATH"] = str(isolated_root / "governance")
        env["MOSS_DUCKDB_PATH"] = str(isolated_root / "moss.duckdb")
        completed = subprocess.run(
            [sys.executable, *_pytest_args()],
            cwd=root,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            return int(completed.returncode)

        governance_mcp_completed = subprocess.run(
            [sys.executable, *_governance_mcp_pytest_args(mcp_profile)],
            cwd=root,
            env=env,
            check=False,
        )
        return int(governance_mcp_completed.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live-governance-dir",
        help="Explicitly audit this runtime governance directory; empty input fails closed.",
    )
    parser.add_argument("--governance-audit-output")
    parser.add_argument("--mcp-profile", choices=("fast", "full"), default="fast")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.governance_audit_output and args.live_governance_dir is None:
        parser.error(
            "--governance-audit-output requires --live-governance-dir; "
            "the default suite uses isolated fixtures and emits no live audit artifact"
        )

    if args.dry_run:
        print(
            json.dumps(
                build_release_suite_plan(
                    live_governance_dir=args.live_governance_dir,
                    governance_audit_output=args.governance_audit_output,
                    mcp_profile=args.mcp_profile,
                ),
                ensure_ascii=False,
            )
        )
        return 0

    return run_release_suite(
        live_governance_dir=args.live_governance_dir,
        governance_audit_output=args.governance_audit_output,
        mcp_profile=args.mcp_profile,
    )


if __name__ == "__main__":
    raise SystemExit(main())
