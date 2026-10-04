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
# tests/AGENTS.md 第 3 层：排除面的 feature/workflow/ETL acceptance 不进默认门禁。
EXCLUDED_SURFACE_DEFAULT_MARKER_EXPR = "not excluded_surface_acceptance"
EXECUTIVE_RELEASE_SAMPLE_IDS = [
    "GS-EXEC-OVERVIEW-A",
    "GS-EXEC-PNL-ATTR-A",
    "GS-EXEC-SUMMARY-A",
]
RELEASE_SUITE_TESTS = [
    "tests/test_backend_release_suite.py",
    "tests/test_caliber_gate_mapping.py",
    "tests/test_system_online_read_boundary.py",
    "tests/test_system_online_publication_concurrency.py",
    "tests/test_system_read_publication_process_crash.py",
    "tests/test_campisi_formal_bridge_coverage.py",
    "tests/test_product_category_read_boundary.py",
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
    "tests/test_backend_dependency_contract.py",
    "tests/test_ci_skip_registry.py",
    "tests/test_api_contract_baseline_gate.py",
    "tests/test_api_response_model_field_preservation.py",
    "tests/test_release_approval_registry.py",
    "tests/test_release_approval_evidence_gate.py",
    "tests/test_release_control_golden_blocker_review.py",
    "tests/test_wp7_release_rehearsal.py",
    "tests/test_wp7_fixed_income_pilot_preflight.py",
    "tests/test_no_finance_logic_in_frontend.py",
    # 分层边界守卫（api/service 不得含金融公式 token、不得直连 DuckDB 写路径）；
    # 2026-09-02 系统审计 A1/E1 纳入 PR 门禁。tests/test_duckdb_write_boundary.py 仅是
    # 从 test_service_storage_boundaries.py 重新导出 4 个同名用例的别名，纳入会在同一次
    # pytest 调用里重复收集执行，故不列入。
    "tests/test_no_finance_logic_in_api.py",
    "tests/test_api_route_boundaries.py",
    "tests/test_service_storage_boundaries.py",
    # caliber 口径红线（无条件兜底；与 scripts/check_caliber_gate.py 路径触发门禁互为双保险）
    "tests/test_caliber_rule_fx_mid_conversion.py",
    "tests/test_caliber_rule_hat_mapping.py",
    "tests/test_caliber_rule_subject_514_516_517_merge.py",
    "tests/test_caliber_rule_issuance_exclusion.py",
    "tests/test_caliber_rule_formal_scenario_gate.py",
    "tests/test_caliber_rule_accounting_basis.py",
]
GOVERNANCE_MCP_FAST_SUITE_TESTS = ["tests/test_project_mcp_fast_contracts.py"]
GOVERNANCE_MCP_FULL_SUITE_TESTS = [
    "tests/test_project_mcp_servers.py",
    "tests/test_project_mcp_launcher_runtime.py",
]


def _release_suite_env() -> dict[str, str]:
    return {
        "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS": "1",
        "MOSS_SKIP_POSTGRES_MIGRATIONS": "1",
        "MOSS_SKIP_STORAGE_READINESS_CHECKS": "1",
        "MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST": "1",
    }


def _marker_selection(
    phase_marker_expr: str | None,
    *,
    include_excluded_surfaces: bool,
) -> list[str]:
    """Build the ``-m`` argv fragment for one phase.

    pytest keeps only the last ``-m``, so a phase carrying its own selection
    (governance MCP fast needs ``mcp_fast``) must fold the default excluded-surface
    filter into the same expression rather than pass a second flag.
    """

    if include_excluded_surfaces:
        marker_expr = phase_marker_expr
    elif phase_marker_expr is None:
        marker_expr = EXCLUDED_SURFACE_DEFAULT_MARKER_EXPR
    else:
        marker_expr = f"{phase_marker_expr} and {EXCLUDED_SURFACE_DEFAULT_MARKER_EXPR}"
    return [] if marker_expr is None else ["-m", marker_expr]


def _pytest_args(*, include_excluded_surfaces: bool = False) -> list[str]:
    selection = _marker_selection(
        None,
        include_excluded_surfaces=include_excluded_surfaces,
    )
    return ["-m", "pytest", "-q", *selection, *RELEASE_SUITE_TESTS]


def _governance_mcp_pytest_args(
    mcp_profile: str = "fast",
    *,
    include_excluded_surfaces: bool = False,
) -> list[str]:
    if mcp_profile == "fast":
        phase_marker_expr: str | None = "mcp_fast"
        suite_tests = GOVERNANCE_MCP_FAST_SUITE_TESTS
    elif mcp_profile == "full":
        phase_marker_expr = None
        suite_tests = GOVERNANCE_MCP_FULL_SUITE_TESTS
    else:
        raise ValueError(f"Unsupported MCP profile: {mcp_profile}")

    selection = _marker_selection(
        phase_marker_expr,
        include_excluded_surfaces=include_excluded_surfaces,
    )
    return ["-m", "pytest", "-q", *selection, *suite_tests]


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
    include_excluded_surfaces: bool = False,
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
        "pytest_args": _pytest_args(include_excluded_surfaces=include_excluded_surfaces),
        "governance_mcp_suite": {
            "suite_name": GOVERNANCE_MCP_SUITE_NAME,
            "profile": mcp_profile,
            "pytest_args": _governance_mcp_pytest_args(
                mcp_profile,
                include_excluded_surfaces=include_excluded_surfaces,
            ),
        },
        "env": _release_suite_env(),
    }


def run_release_suite(
    *,
    root: Path = ROOT,
    live_governance_dir: str | None = None,
    governance_audit_output: str | Path | None = None,
    mcp_profile: str = "fast",
    include_excluded_surfaces: bool = False,
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
        # 两个阶段都要跑完再汇总：第一阶段失败即返回会让 MCP 契约阶段的结果在同一次
        # 门禁里不可见，修一处红再跑一遍才能看到另一处。退出码取第一个非零阶段的值，
        # 与此前"哪个阶段失败就返回它的 returncode"的语义保持一致。
        bounded_completed = subprocess.run(
            [
                sys.executable,
                *_pytest_args(include_excluded_surfaces=include_excluded_surfaces),
            ],
            cwd=root,
            env=env,
            check=False,
        )
        governance_mcp_completed = subprocess.run(
            [
                sys.executable,
                *_governance_mcp_pytest_args(
                    mcp_profile,
                    include_excluded_surfaces=include_excluded_surfaces,
                ),
            ],
            cwd=root,
            env=env,
            check=False,
        )

    phase_results = {
        RELEASE_SUITE_NAME: int(bounded_completed.returncode),
        GOVERNANCE_MCP_SUITE_NAME: int(governance_mcp_completed.returncode),
    }
    exit_code = next((code for code in phase_results.values() if code != 0), 0)
    print(
        "release suite phases: "
        + " ".join(f"{name}={code}" for name, code in phase_results.items())
        + f" -> exit {exit_code}"
    )
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live-governance-dir",
        help="Explicitly audit this runtime governance directory; empty input fails closed.",
    )
    parser.add_argument("--governance-audit-output")
    parser.add_argument("--mcp-profile", choices=("fast", "full"), default="fast")
    parser.add_argument(
        "--include-excluded-surfaces",
        action="store_true",
        help=(
            "Also run excluded-surface acceptance tests; the default gate selects "
            f'-m "{EXCLUDED_SURFACE_DEFAULT_MARKER_EXPR}".'
        ),
    )
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
                    include_excluded_surfaces=args.include_excluded_surfaces,
                ),
                ensure_ascii=False,
            )
        )
        return 0

    return run_release_suite(
        live_governance_dir=args.live_governance_dir,
        governance_audit_output=args.governance_audit_output,
        mcp_profile=args.mcp_profile,
        include_excluded_surfaces=args.include_excluded_surfaces,
    )


if __name__ == "__main__":
    raise SystemExit(main())
