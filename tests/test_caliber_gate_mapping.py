"""Guard tests for caliber and selected formal-compute path-trigger checks.

Covers three surfaces:

1. ``CALIBER_GATE_MAP`` integrity: every mapped source and test path exists,
   and the map covers every ``tests/test_caliber_rule_*.py`` file on disk (so
   a future caliber test cannot silently stay outside the gate).
2. Pure matching semantics of ``resolve_required_tests`` (exact path, prefix,
   dedup, deterministic ordering).
3. CLI + git diff behavior against a temporary git repository with an
   injected small gate map: mapped change -> matched tests in dry-run JSON,
   unrelated change -> empty match, invalid base ref -> fail-closed non-zero
   exit.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
from importlib import util
from pathlib import Path

import pytest

from scripts import backend_release_suite, check_caliber_gate as gate

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CALIBER_TESTS = {
    "tests/test_caliber_rule_accounting_basis.py",
    "tests/test_caliber_rule_formal_scenario_gate.py",
    "tests/test_caliber_rule_fx_mid_conversion.py",
    "tests/test_caliber_rule_hat_mapping.py",
    "tests/test_caliber_rule_issuance_exclusion.py",
    "tests/test_caliber_rule_subject_514_516_517_merge.py",
}


@pytest.mark.parametrize("source_path, required", [
    ("backend/app/main.py", {"tests/test_system_online_read_boundary.py", "tests/test_system_online_publication_concurrency.py", "tests/test_boundary_surface_inventory.py"}),
    ("backend/app/api/routes/system_read_publication.py", {"tests/test_system_online_read_boundary.py", "tests/test_boundary_surface_inventory.py"}),
    ("backend/app/tasks/system_read_publication.py", {"tests/test_system_read_publication_process_crash.py", "tests/test_system_online_publication_concurrency.py"}),
    ("backend/app/services/campisi_attribution_service.py", {"tests/test_campisi_formal_bridge_coverage.py"}),
    ("backend/app/services/product_category_pnl_service.py", {"tests/test_product_category_read_boundary.py"}),
    ("scripts/backend_release_suite.py", {"tests/test_backend_release_suite.py"}),
    ("backend/app/services/pnl_v1_snapshot_validation.py", {"tests/test_pnl_v1_source_integrity.py", "tests/test_pnl_api_contract.py"}),
])
def test_audited_read_and_publication_boundaries_are_selected(source_path, required):
    assert required <= set(gate.resolve_required_tests([source_path]))


@pytest.mark.parametrize(("source_path", "expected_tests"), [
    ("backend/app/core_finance/macro/toolkit/system_sources.py", {
        "tests/test_macro_immutable_read_selection.py",
        "tests/test_macro_system_sources_pushdown.py",
        "tests/test_macro_toolkit_scripts.py",
    }),
    ("backend/app/services/macro_toolkit_refresh_receipt_service.py", {
        "tests/test_macro_toolkit_refresh_failure_health.py",
        "tests/test_macro_toolkit_refresh_receipt_service.py",
    }),
    ("backend/app/services/livermore_candidate_history_service.py", {
        "tests/test_market_data_livermore_candidate_history.py",
        "tests/test_pretrade_producer_full_integration.py",
        "tests/test_pretrade_sealed_api_integration.py",
    }),
    ("backend/app/services/livermore_candidate_history_window_stats.py", {
        "tests/test_market_data_livermore_candidate_history.py",
        "tests/test_pretrade_producer_full_integration.py",
        "tests/test_pretrade_sealed_api_integration.py",
    }),
    ("backend/app/tasks/livermore_candidate_history_materialize.py", {
        "tests/test_livermore_candidate_writer_admission.py",
        "tests/test_market_data_livermore_candidate_history.py",
        "tests/test_pretrade_producer_full_integration.py",
        "tests/test_pretrade_sealed_api_integration.py",
    }),
    ("backend/scripts/audit_caliber_violations.py", {
        "tests/test_audit_caliber_violations_script.py",
        "tests/test_caliber_audit_ci_gate.py",
    }),
    ("backend/scripts/backfill_stock_factor_market_cap_tushare.py", {
        "tests/test_backfill_stock_factor_market_cap_tushare.py",
    }),
    ("backend/app/tasks/stock_factor_market_cap_backfill.py", {
        "tests/test_backfill_stock_factor_market_cap_tushare.py",
    }),
    ("scripts/bond_risk_shadow_candidate.py", {
        "tests/test_bond_risk_shadow_candidate.py",
    }),
    ("scripts/portfolio_home_evidence_packet_guard.py", {
        "tests/test_portfolio_home_evidence_packet_guard.py",
        "tests/test_portfolio_home_scorecard_command_verifier.py",
    }),
    ("scripts/portfolio_home_evidence_snapshot.py", {
        "tests/test_portfolio_home_evidence_snapshot.py",
        "tests/test_portfolio_home_scorecard_command_verifier.py",
    }),
    ("scripts/verify_portfolio_home_scorecard_commands.py", {
        "tests/test_portfolio_home_evidence_packet_guard.py",
        "tests/test_portfolio_home_evidence_snapshot.py",
        "tests/test_portfolio_home_scorecard_command_verifier.py",
    }),
    ("scripts/rematerialize_fixed_income_versions.py", {
        "tests/test_rematerialize_fixed_income_versions.py",
    }),
    ("scripts/stock_analysis_page_gap_factor_manifest.py", {
        "tests/test_stock_analysis_page_gap_factor_manifest.py",
    }),
    ("scripts/stock_analysis_page_gap_manifest.py", {
        "tests/test_stock_analysis_page_gap_manifest_cli.py",
    }),
    ("scripts/stock_research_daily.py", {
        "tests/test_stock_research_daily.py",
    }),
    ("scripts/verify_system_audit_monitoring_snapshot.py", {
        "tests/test_system_audit_monitoring_snapshot_verifier.py",
    }),
    ("scripts/wp7_release_rehearsal.py", {
        "tests/test_wp7_release_rehearsal.py",
    }),
    ("backend/app/tasks/wp7_rehearsal_bundle.py", {
        "tests/test_wp7_release_rehearsal.py",
    }),
    ("scripts/check_full_pytest_partition.py", {
        "tests/test_full_pytest_platform.py",
    }),
])
def test_ci_remediation_paths_select_only_their_direct_checks(
    source_path: str, expected_tests: set[str],
) -> None:
    assert gate.resolve_required_tests([source_path]) == sorted(expected_tests)
    neighboring_source = source_path.removesuffix(".py") + "_extra.py"
    assert gate.resolve_required_tests([neighboring_source]) == []


@pytest.mark.parametrize(("source_path", "expected_tests"), [
    ("backend/app/services/bond_analytics_service.py", {
        "tests/test_lazy_task_import_constants.py",
        "tests/test_bond_analytics_service.py",
        "tests/test_advanced_attribution_contract.py",
        "tests/test_pnl_audit_repair.py",
        "tests/test_structural_generation_cache.py",
        "tests/test_structural_bond_positions.py",
    }),
    ("backend/app/services/pnl_bridge_service.py", {
        "tests/test_lazy_task_import_constants.py",
        "tests/test_pnl_bridge_result_meta_dates.py",
        "tests/test_pnl_api_contract.py",
        "tests/test_campisi_formal_bridge_coverage.py",
    }),
])
def test_cache_identity_repairs_keep_existing_checks_and_select_identity_guards(
    source_path: str, expected_tests: set[str],
) -> None:
    assert expected_tests <= set(gate.resolve_required_tests([source_path]))


@pytest.mark.parametrize("test_path", [
    "tests/test_system_online_read_boundary.py",
    "tests/test_system_online_publication_concurrency.py",
    "tests/test_system_read_publication_process_crash.py",
    "tests/test_campisi_formal_bridge_coverage.py",
    "tests/test_product_category_read_boundary.py",
    "tests/test_backend_release_suite.py",
])
def test_audited_boundary_test_changes_select_themselves(test_path):
    assert set(gate.resolve_required_tests([test_path])) == {test_path, "tests/test_caliber_gate_mapping.py"}


def test_every_mapped_source_path_exists_in_repo() -> None:
    for source in gate.CALIBER_GATE_MAP:
        target = REPO_ROOT / source
        if source.endswith("/"):
            assert target.is_dir(), f"mapped prefix does not exist: {source}"
        else:
            assert target.is_file(), f"mapped source file does not exist: {source}"


def test_map_covers_every_caliber_rule_test_file() -> None:
    mapped_tests = {
        test_file
        for test_files in gate.CALIBER_GATE_MAP.values()
        for test_file in test_files
    }
    on_disk = {
        f"tests/{path.name}"
        for path in (REPO_ROOT / "tests").glob("test_caliber_rule_*.py")
    }
    # Guard the guard: the six known red-line tests must be on disk, so the
    # coverage assertion below cannot pass vacuously against an empty glob.
    assert EXPECTED_CALIBER_TESTS <= on_disk
    assert {
        path for path in mapped_tests if Path(path).name.startswith("test_caliber_rule_")
    } == on_disk, (
        "CALIBER_GATE_MAP must retain every caliber rule test on disk; "
        "update scripts/check_caliber_gate.py when adding a caliber test"
    )
    for test_file in mapped_tests:
        assert (REPO_ROOT / test_file).is_file(), (
            f"mapped test does not exist: {test_file}"
        )


def test_curve_and_pnl_bridge_source_changes_select_existing_goldens() -> None:
    assert gate.resolve_required_tests(
        ["backend/app/core_finance/curve_engine/interpolation.py"]
    ) == ["tests/test_curve_engine_golden.py", "tests/test_pnl_bridge_golden.py"]
    assert gate.resolve_required_tests(
        ["backend/app/core_finance/pnl_bridge.py"]
    ) == [
        "tests/test_campisi_dirty_input.py",
        "tests/test_pnl_api_contract.py",
        "tests/test_pnl_bridge_ambiguity.py",
        "tests/test_pnl_bridge_core.py",
        "tests/test_pnl_bridge_golden.py",
        "tests/test_pnl_bridge_modified_duration.py",
        "tests/test_yield_curve_consumer_symmetry.py",
    ]


def test_data_update_and_balance_paths_select_first_scope_regressions() -> None:
    assert gate.resolve_required_tests(
        ["backend/app/services/data_health_service.py"]
    ) == [
        "tests/test_data_health.py",
        "tests/test_data_health_schtasks_query.py",
        "tests/test_data_updates.py",
    ]
    assert gate.resolve_required_tests(
        ["tests/test_data_health_schtasks_query.py"]
    ) == [
        "tests/test_caliber_gate_mapping.py",
        "tests/test_data_health_schtasks_query.py",
    ]
    assert gate.resolve_required_tests(
        ["backend/app/api/routes/balance_analysis.py"]
    ) == [
        "tests/test_balance_analysis_api.py",
        "tests/test_balance_analysis_overview_publication.py",
    ]
    assert gate.resolve_required_tests(
        ["docs/unrelated-note.md"]
    ) == []


@pytest.mark.parametrize(
    ("source", "publication_checks"),
    [
        ("backend/app/api/__init__.py", []),
        ("backend/app/api/routes/data_updates.py", []),
        ("backend/app/repositories/data_update_repo.py", [
            "tests/test_system_read_publication.py",
            "tests/test_system_read_publication_process_crash.py",
        ]),
        ("backend/app/schemas/data_updates.py", []),
        ("backend/app/services/data_update_service.py", []),
        ("backend/app/tasks/data_update_center.py", [
            "tests/test_system_read_publication.py",
            "tests/test_system_read_publication_process_crash.py",
        ]),
    ],
)
def test_data_update_source_selects_same_date_integration(
    source: str, publication_checks: list[str],
) -> None:
    assert gate.resolve_required_tests([source]) == [
        "tests/test_data_update_balance_integration.py",
        "tests/test_data_updates.py",
    ] + publication_checks


def test_queue_scheduler_and_test_changes_select_focused_regressions() -> None:
    assert gate.resolve_required_tests(
        ["scripts/scheduling/drain_data_updates.ps1"]
    ) == [
        "tests/test_data_update_queue_launcher_logging.py",
        "tests/test_install_data_update_queue.py",
    ]
    assert gate.resolve_required_tests(
        ["scripts/scheduling/install_data_update_queue.ps1"]
    ) == ["tests/test_install_data_update_queue.py"]
    for test_file in (
        "tests/test_data_update_balance_integration.py",
        "tests/test_data_update_queue_launcher_logging.py",
        "tests/test_install_data_update_queue.py",
    ):
        assert gate.resolve_required_tests([test_file]) == [
            "tests/test_caliber_gate_mapping.py", test_file,
        ]
    assert gate.resolve_required_tests(["scripts/scheduling/unrelated.ps1"]) == []


def test_windows_scheduler_scope_is_limited_to_two_scripts_and_tests() -> None:
    assert gate.selects_scheduler_windows_scope(
        ["scripts/scheduling/drain_data_updates.ps1"]
    )
    assert gate.selects_scheduler_windows_scope(
        ["tests/test_install_data_update_queue.py"]
    )
    assert not gate.selects_scheduler_windows_scope(
        ["backend/app/tasks/data_update_center.py", "docs/note.md"]
    )


def test_frontend_first_scope_selection_is_bounded() -> None:
    assert gate.selects_frontend_first_scope(
        ["frontend/src/api/dataUpdatesClient.ts"]
    )
    assert gate.selects_frontend_first_scope(
        ["frontend\\src\\features\\balance-analysis\\pages\\BalanceAnalysisPage.tsx"]
    )
    assert not gate.selects_frontend_first_scope(
        ["frontend/src/features/risk-tensor/RiskTensorPage.tsx", "docs/note.md"]
    )


def test_data_update_browser_scope_only_selects_the_daily_balance_path() -> None:
    assert set(gate.DATA_UPDATE_BROWSER_PATHS) <= set(gate.FRONTEND_FIRST_SCOPE_PATHS)
    assert gate.selects_data_update_browser_scope(
        ["frontend/src/features/platform-config/DataUpdateCenter.tsx"]
    )
    assert gate.selects_data_update_browser_scope(
        ["frontend/tests/playwright/data-update-center-balance-daily.spec.mjs"]
    )
    assert not gate.selects_data_update_browser_scope(
        ["frontend/src/api/balanceMovementClient.ts", "docs/note.md"]
    )


def test_formal_release_scope_uses_canonical_boundary() -> None:
    assert gate.selects_formal_release_scope(
        ["backend/app/core_finance/balance_analysis.py"]
    )
    assert gate.selects_formal_release_scope(
        ["backend/app/tasks/formal_balance_pipeline.py"]
    )
    assert not gate.selects_formal_release_scope(
        ["backend/app/tasks/data_update_center.py", "docs/note.md"]
    )


def test_every_selected_test_exists_and_selects_itself_with_the_mapping_guard() -> None:
    for test_paths in gate.CALIBER_GATE_MAP.values():
        for test_path in test_paths:
            assert (REPO_ROOT / test_path).is_file(), f"missing check: {test_path}"
            assert set(gate.resolve_required_tests([test_path])) == {
                test_path, "tests/test_caliber_gate_mapping.py"
            }


def test_imported_regressions_are_selected_by_production_and_test_changes() -> None:
    # Discover the regression cohort independently of CALIBER_GATE_MAP. Keeping
    # only the map's internal self-selection invariant missed these new files.
    patterns = (
        "test_structural_*.py",
        "test_selected_generation_context_*.py",
        "test_balance_campisi_fin002_*.py",
        "test_adb_comparison_*_contract.py",
        "test_fx_analytical_fallback_*.py",
        "test_fx_analytical_previous_observation.py",
        "test_fx_analytical_view_service.py",
        "test_fx_selected_availability*.py",
        "test_fx_sql_null_chain.py",
        "test_macro_*_truthfulness.py",
        "test_*_xlsx_text_contract.py",
        "test_xlsx_text_independent_review.py",
        "test_import_duplicate_fields_contract.py",
        "test_ledger_multipart_integrity.py",
        "test_bond_dv01_limit_finite_admission.py",
        "test_stock_limit_price_duplicate_contract.py",
        "test_stock_selected_generation_context.py",
        "test_stock_signal_adjustment.py",
        "test_livermore_factor_verified_geometry.py",
        "test_livermore_factor_geometry_review.py",
        "test_credit_dashboard_demo_disclosure.py",
        "test_product_category_pnl_flow.py",
        "test_qdb_gl_missing_average_contract.py",
        "test_qdb_gl_monthly_analysis_core.py",
        "test_pnl_v1_source_integrity.py",
    )
    regression_files: set[Path] = set()
    for pattern in patterns:
        matches = set((REPO_ROOT / "tests").glob(pattern))
        assert matches, f"missing regression cohort: {pattern}"
        regression_files.update(matches)

    source_omissions: list[str] = []
    test_omissions: list[str] = []
    for regression in sorted(regression_files):
        test_path = regression.relative_to(REPO_ROOT).as_posix()
        modules: set[str] = set()
        literals: set[str] = set()
        # Read imports and explicit load_module/source paths without importing
        # the financial tests or executing their fixtures and production code.
        for node in ast.walk(ast.parse(regression.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
                modules.update(f"{node.module}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.add(node.value)
        production_sources = {
            f"{module.replace('.', '/')}.py"
            for module in modules | literals
            if module.startswith("backend.app.")
        } | {
            literal for literal in literals
            if literal.startswith("backend/app/") and literal.endswith(".py")
        }
        production_sources = {
            source for source in production_sources if (REPO_ROOT / source).is_file()
        }
        assert production_sources, f"no production dependency found: {test_path}"
        if test_path not in gate.resolve_required_tests(production_sources):
            source_omissions.append(test_path)
        if set(gate.resolve_required_tests([test_path])) != {
            test_path, "tests/test_caliber_gate_mapping.py",
        }:
            test_omissions.append(test_path)

    assert not source_omissions, f"production changes omit regressions: {source_omissions}"
    assert not test_omissions, f"test changes omit regressions: {test_omissions}"


def test_resolve_required_tests_exact_prefix_dedup_and_order() -> None:
    small_map = {
        "src/exact.py": ("tests/test_b.py",),
        "pkg/": ("tests/test_a.py", "tests/test_b.py"),
    }
    matched = gate.resolve_required_tests(
        ["src/exact.py", "pkg\\inner\\mod.py", "unrelated.md"],
        gate_map=small_map,
    )
    assert matched == ["tests/test_a.py", "tests/test_b.py"]
    assert gate.resolve_required_tests(["unrelated.md"], gate_map=small_map) == []
    assert gate.resolve_required_tests([], gate_map=small_map) == []


@pytest.mark.parametrize(
    ("changed_path", "expected_tests"),
    [
        (
            "backend/app/core_finance/curve_engine/bootstrapper.py",
            {"tests/test_curve_engine_golden.py"},
        ),
        (
            "backend/app/core_finance/bond_duration.py",
            {"tests/test_bond_duration_goldens.py", "tests/test_krd_golden.py"},
        ),
        (
            "backend/app/core_finance/pnl_bridge.py",
            {"tests/test_pnl_bridge_golden.py"},
        ),
        (
            "backend/app/core_finance/curve_engine/new_interpolation.py",
            {"tests/test_curve_engine_golden.py", "tests/test_pnl_bridge_golden.py"},
        ),
        (
            "backend/app/core_finance/bond_analytics/common.py",
            {
                "tests/test_bond_duration_goldens.py",
                "tests/test_krd_golden.py",
                "tests/test_pnl_bridge_golden.py",
            },
        ),
        (
            "backend/app/core_finance/decimal_utils.py",
            {
                "tests/test_decimal_utils_strict.py",
                "tests/test_fx_rates_golden.py",
                "tests/test_pnl_materialize_flow.py",
            },
        ),
        (
            "backend/app/core_finance/fx_calendar.py",
            {
                "tests/test_fx_rates_golden.py",
                "tests/test_balance_analysis_materialize_flow.py",
                "tests/test_pnl_materialize_flow.py",
            },
        ),
        (
            "backend/app/repositories/balance_analysis_repo.py",
            {
                "tests/test_balance_analysis_snapshot_fact_consistency.py",
                "tests/test_balance_analysis_materialize_flow.py",
            },
        ),
    ],
)
def test_formal_compute_change_selects_existing_independent_checks(
    changed_path: str, expected_tests: set[str]
) -> None:
    selected = gate.resolve_required_tests([changed_path])
    assert expected_tests <= set(selected)
    assert selected == sorted(set(selected))


@pytest.mark.parametrize(
    ("changed_path", "required_checks"),
    [
        ("backend/app/core_finance/campisi.py", {
            "tests/test_campisi.py", "tests/test_campisi_formula_golden.py",
        }),
        ("backend/app/core_finance/bond_four_effects.py", {
            "tests/test_campisi_formula_golden.py",
        }),
        ("backend/app/services/campisi_attribution_service.py", {
            "tests/test_campisi_attribution_service.py",
        }),
        ("backend/app/core_finance/pnl_attribution/workbench.py", {
            "tests/test_pnl_attribution_workbench_contract.py",
        }),
        ("backend/app/services/pnl_attribution_service.py", {
            "tests/test_pnl_attribution_service_explicit_numeric.py",
        }),
        ("backend/app/core_finance/credit_spread_analysis.py", {
            "backend/tests/core_finance/test_credit_spread_analysis.py",
        }),
        ("backend/app/core_finance/balance_analysis_workbook.py", {
            "tests/test_balance_workbook_decimal_nan_guard.py",
        }),
        ("backend/app/core_finance/pnl_bridge.py", {
            "tests/test_pnl_bridge_modified_duration.py",
            "tests/test_pnl_bridge_core.py", "tests/test_pnl_api_contract.py",
            "tests/test_pnl_bridge_ambiguity.py",
            "tests/test_campisi_dirty_input.py",
        }),
        ("backend/app/services/pnl_bridge_service.py", {
            "tests/test_pnl_bridge_core.py", "tests/test_pnl_api_contract.py",
            "tests/test_pnl_bridge_ambiguity.py",
            "tests/test_campisi_dirty_input.py",
        }),
        ("backend/app/core_finance/rate_units.py", {
            "tests/test_rate_units.py", "tests/test_campisi.py",
        }),
        ("backend/app/core_finance/fx_calendar.py", {
            "tests/test_fx_calendar.py", "tests/test_formal_fx_rate_validity.py",
        }),
        ("backend/app/core_finance/fx_rates.py", {
            "tests/test_fx_rates.py", "tests/test_formal_fx_rate_validity.py",
        }),
        ("backend/app/tasks/fx_mid_materialize.py", {
            "tests/test_fx_mid_materialize.py",
        }),
        ("backend/app/repositories/balance_analysis_repo.py", {
            "tests/test_formal_fx_rate_validity.py",
        }),
        ("backend/app/repositories/pnl_repo.py", {
            "tests/test_formal_fx_rate_validity.py",
        }),
    ],
)
def test_audited_calculation_paths_select_their_numerical_regressions(
    changed_path: str, required_checks: set[str],
) -> None:
    """A path gate must exercise the numeric boundary implicated by the audit."""
    assert required_checks <= set(gate.resolve_required_tests([changed_path]))


@pytest.mark.parametrize(
    ("changed_path", "expected_tests"),
    [
        (
            "backend/app/repositories/pnl_precompute_state.py",
            {
                "tests/test_pnl_fact_precompute_invalidation.py",
                "tests/test_pnl_by_business_precompute_state.py",
            },
        ),
        (
            "backend/app/repositories/financial_result_publication_repo.py",
            {"tests/test_financial_result_publication.py"},
        ),
        (
            "backend/app/tasks/pnl_by_business_page_publication.py",
            {
                "tests/test_financial_result_publication.py",
                "tests/test_pnl_by_business_page_lifecycle.py",
            },
        ),
        (
            "backend/app/services/pnl_task_dispatch.py",
            {
                "tests/test_pnl_by_business_page_lifecycle.py",
                "tests/test_pnl_publication_api_contract.py",
            },
        ),
        (
            "backend/app/services/pnl_by_business_precompute_lifecycle.py",
            {
                "tests/test_pnl_by_business_precompute_state.py",
                "tests/test_pnl_by_business_adjustment_handoff.py",
                "tests/test_pnl_by_business_page_lifecycle.py",
            },
        ),
        (
            "backend/app/core_finance/pnl_independent_reconciliation.py",
            {"tests/test_pnl_independent_reconciliation.py"},
        ),
        (
            "backend/app/repositories/pnl_independent_reference_repo.py",
            {
                "tests/test_pnl_independent_reconciliation.py",
                "tests/test_pnl_overview_independent_reference_api.py",
            },
        ),
    ],
)
def test_runtime_remediation_change_selects_its_bounded_checks(
    changed_path: str, expected_tests: set[str]
) -> None:
    selected = gate.resolve_required_tests([changed_path])
    assert expected_tests <= set(selected)
    assert selected == sorted(set(selected))


@pytest.mark.parametrize(
    "source_path",
    [
        "backend/app/tasks/balance_analysis_materialize.py",
        "backend/app/tasks/pnl_materialize.py",
        "backend/app/tasks/bond_analytics_materialize.py",
        "backend/app/tasks/risk_tensor_materialize.py",
    ],
)
def test_four_real_materializers_select_the_joint_replay(source_path: str) -> None:
    assert "tests/test_formal_compute_joint_replay.py" in gate.resolve_required_tests(
        [source_path]
    )


@pytest.mark.parametrize(
    "source_path",
    [
        "backend/app/repositories/balance_analysis_repo.py",
        "backend/app/repositories/financial_result_publication_repo.py",
        "backend/app/tasks/balance_analysis_materialize.py",
        "backend/app/tasks/balance_analysis_overview_publication.py",
        "backend/app/tasks/financial_result_publication.py",
        "backend/app/services/balance_analysis_publication_service.py",
        "backend/app/services/balance_analysis_service.py",
        "backend/app/api/routes/balance_analysis.py",
        "backend/app/schemas/balance_analysis.py",
        "backend/app/governance/settings.py",
    ],
)
def test_balance_publication_changes_select_its_bounded_checks(source_path: str) -> None:
    assert "tests/test_balance_analysis_overview_publication.py" in (
        gate.resolve_required_tests([source_path])
    )


@pytest.mark.parametrize(
    "source_path",
    [
        "backend/app/tasks/broker.py",
        "backend/app/tasks/worker_bootstrap.py",
        "backend/app/tasks/worker_recovery.py",
    ],
)
def test_worker_recovery_changes_select_bootstrap_checks(source_path: str) -> None:
    assert gate.resolve_required_tests([source_path]) == [
        "tests/test_worker_bootstrap.py"
    ]


def test_resource_scope_changes_select_budget_and_publication_checks() -> None:
    assert gate.resolve_required_tests(
        ["backend/app/tasks/pnl_by_business_resource_scope.py"]
    ) == [
        "tests/test_financial_result_publication.py",
        "tests/test_pnl_by_business_precompute_state.py",
    ]


def test_curve_prefix_does_not_claim_unrelated_financial_modules_are_covered() -> None:
    assert gate.resolve_required_tests(
        ["backend/app/core_finance/curve_engineering.py", "docs/metric_dictionary.md"]
    ) == []


@pytest.mark.parametrize("source_path", [
    "backend/app/api/routes/data_updates.py",
    "backend/app/services/data_update_service.py",
    "backend/app/repositories/data_update_repo.py",
    "backend/app/tasks/data_update_center.py",
    "scripts/run_global_data_refresh.py",
])
def test_data_update_changes_select_request_and_retry_regressions(source_path: str) -> None:
    assert "tests/test_data_updates.py" in gate.resolve_required_tests([source_path])


@pytest.mark.parametrize("source_path", [
    "backend/app/tasks/data_update_center.py",
    "backend/app/repositories/data_update_repo.py",
    "backend/app/tasks/system_read_publication.py",
    "backend/app/repositories/system_read_publication_repo.py",
    "backend/app/tasks/financial_result_publication.py",
    "backend/app/repositories/financial_result_publication_repo.py",
    "scripts/run_global_data_refresh.py",
])
def test_system_publication_changes_select_no_replay_regressions(source_path: str) -> None:
    assert "tests/test_system_read_publication.py" in gate.resolve_required_tests([source_path])


@pytest.mark.parametrize("source_path", [
    "backend/app/core_finance/product_category_pnl.py",
    "backend/app/core_finance/field_normalization.py",
    "backend/app/core_finance/config/product_category_contract.py",
    "backend/app/core_finance/config/product_category_mapping.py",
    "backend/app/core_finance/config/classification_rules.py",
    "backend/app/config/product_category_mapping.py",
    "backend/app/repositories/product_category_pnl_repo.py",
    "backend/app/services/product_category_source_service.py",
    "backend/app/services/source_file_hash.py",
    "backend/app/tasks/product_category_pnl.py",
    "backend/app/tasks/product_category_refresh_state.py",
    "backend/app/schema_registry/duckdb/08_product_category_pnl.sql",
])
def test_product_refresh_dependencies_select_year_reuse_regressions(source_path: str) -> None:
    assert "tests/test_product_category_incremental_materialization.py" in (
        gate.resolve_required_tests([source_path])
    )


@pytest.mark.parametrize("test_path", [
    "tests/test_data_updates.py",
    "tests/test_system_read_publication.py",
    "tests/test_product_category_incremental_materialization.py",
])
def test_refresh_regression_changes_select_itself_and_mapping_guard(test_path: str) -> None:
    assert gate.resolve_required_tests([test_path]) == sorted([
        test_path, "tests/test_caliber_gate_mapping.py",
    ])


def test_refresh_gate_does_not_expand_to_unrelated_or_excluded_surfaces() -> None:
    assert gate.resolve_required_tests([
        "backend/app/tasks/choice_news.py",
        "backend/app/tasks/source_preview_refresh.py",
        "backend/app/services/macro_toolkit_refresh_receipt_service_extra.py",
        "backend/app/services/data_update_service_extra.py",
    ]) == []


@pytest.mark.parametrize("source_path", [
    "backend/app/api/routes/product_category_pnl.py",
    "backend/app/schemas/product_category_pnl.py",
    "backend/app/schemas/materialize.py",
    "backend/app/services/product_category_pnl_service.py",
    "scripts/api_contract_check.py",
    "tests/test_product_category_api_contract.py",
])
def test_product_api_contract_dependencies_select_http_contract_guard(source_path: str) -> None:
    assert "tests/test_product_category_api_contract.py" in gate.resolve_required_tests([source_path])


@pytest.mark.parametrize("source_path", [
    "backend/app/core_finance/bond_duration.py",
    "backend/app/core_finance/bond_analytics/common.py",
    "backend/app/core_finance/bond_analytics/engine.py",
    "backend/app/core_finance/bond_four_effects.py",
    "backend/app/core_finance/krd.py",
    "backend/app/core_finance/cashflow_projection.py",
])
def test_coupon_calendar_changes_select_cross_entrypoint_date_checks(source_path: str) -> None:
    assert "tests/test_bond_coupon_date_boundary.py" in gate.resolve_required_tests([source_path])


@pytest.mark.parametrize("source_path", [
    "backend/app/core_finance/campisi.py",
    "backend/app/core_finance/bond_four_effects.py",
    "backend/app/core_finance/bond_duration.py",
    "backend/app/core_finance/bond_analytics/common.py",
    "backend/app/core_finance/cashflow_projection.py",
    "tests/test_decimal_first_batch_lock.py",
])
def test_campisi_duration_changes_select_decimal_locks(source_path: str) -> None:
    assert "tests/test_decimal_first_batch_lock.py" in gate.resolve_required_tests([source_path])


@pytest.mark.parametrize("source_path", [
    "backend/app/repositories/snapshot_repo.py",
    "backend/app/tasks/snapshot_materialize.py",
    "tests/test_snapshot_dq_guardrails.py",
    "tests/test_snapshot_materialize_flow.py",
])
def test_snapshot_merge_changes_select_quality_and_materialization_checks(source_path: str) -> None:
    selected = gate.resolve_required_tests([source_path])
    if source_path.startswith("backend/"):
        assert {"tests/test_snapshot_dq_guardrails.py", "tests/test_snapshot_materialize_flow.py"} <= set(selected)
    else:
        assert source_path in selected


@pytest.mark.parametrize("source_path, regression", [
    ("backend/app/core_finance/bond_analytics/common.py", "tests/test_bond_analytics_core.py"),
    ("backend/app/core_finance/bond_analytics/engine.py", "tests/test_bond_analytics_engine.py"),
    ("backend/app/core_finance/bond_duration.py", "tests/test_bond_duration.py"),
    ("backend/app/core_finance/bond_four_effects.py", "tests/test_bond_four_effects.py"),
    ("backend/app/core_finance/krd.py", "tests/test_krd.py"),
    ("backend/app/core_finance/credit_spread.py", "tests/test_credit_spread.py"),
])
def test_observed_zero_ytm_paths_select_null_distinction_regressions(
    source_path: str, regression: str,
) -> None:
    assert regression in gate.resolve_required_tests([source_path])


@pytest.mark.parametrize("source_path, expected_tests", [
    ("backend/app/core_finance/config/product_category_mapping.py",
     ["tests/test_product_category_incremental_materialization.py",
      "tests/test_product_category_manual_reference_flow.py"]),
    ("backend/app/core_finance/config/product_category_contract.py",
     ["tests/test_product_category_incremental_materialization.py",
      "tests/test_product_category_manual_reference_flow.py"]),
    ("backend/app/core_finance/pnl_constants.py", ["tests/test_pnl_materialize_flow.py"]),
])
def test_canonical_pnl_authority_changes_select_materialized_reference(
    source_path: str, expected_tests: list[str],
) -> None:
    assert gate.resolve_required_tests([source_path]) == expected_tests


def test_changed_golden_runs_itself_and_the_mapping_guard() -> None:
    assert gate.resolve_required_tests(["tests/test_curve_engine_golden.py"]) == [
        "tests/test_caliber_gate_mapping.py",
        "tests/test_curve_engine_golden.py",
    ]


def test_changed_gate_runs_all_registered_checks_and_the_mapping_guard() -> None:
    selected = set(gate.resolve_required_tests(["scripts/check_caliber_gate.py"]))
    assert EXPECTED_CALIBER_TESTS <= selected
    assert {
        "tests/test_caliber_gate_mapping.py",
        "tests/test_curve_engine_golden.py",
        "tests/test_bond_duration_goldens.py",
        "tests/test_pnl_bridge_golden.py",
        "tests/test_krd_golden.py",
        "tests/test_balance_analysis_snapshot_fact_consistency.py",
        "tests/test_balance_analysis_overview_publication.py",
        "tests/test_formal_compute_joint_replay.py",
        "tests/test_worker_bootstrap.py",
    } <= selected
    assert selected == {
        test_path
        for test_paths in gate.CALIBER_GATE_MAP.values()
        for test_path in test_paths
    }


def test_cli_runs_selected_numeric_checks_and_propagates_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        gate,
        "list_changed_files",
        lambda _base_ref, *, cwd: ["backend/app/core_finance/bond_duration.py"],
    )
    calls: list[list[str]] = []

    def failed_pytest(command: list[str], *, cwd: Path, check: bool):
        assert cwd == REPO_ROOT
        assert check is False
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(gate.subprocess, "run", failed_pytest)
    assert gate.main(["--base-ref", "base", "--workers", "1"]) == 1
    assert calls == [[
        gate.sys.executable,
        "-m",
        "pytest",
        "tests/test_bond_coupon_date_boundary.py",
        "tests/test_bond_duration.py",
        "tests/test_bond_duration_goldens.py",
        "tests/test_decimal_first_batch_lock.py",
        "tests/test_krd_golden.py",
        "-q",
        "-n",
        "0",
    ]]


@pytest.mark.parametrize(("cpu_count", "expected"), [(None, "0"), (1, "0"), (2, "2"), (16, "4")])
def test_caliber_workers_default_caps_without_changing_selection(monkeypatch, cpu_count, expected):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setattr(backend_release_suite.os, "cpu_count", lambda: cpu_count)
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: ["backend/app/core_finance/credit_spread.py"])
    calls = []
    monkeypatch.setattr(gate.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)) or subprocess.CompletedProcess(command, 0))

    assert gate.main(["--base-ref", "base"]) == 0
    assert calls == [([
        gate.sys.executable, "-m", "pytest", "tests/test_credit_spread.py", "-q", "-n", expected,
    ], {"cwd": REPO_ROOT, "check": False})]


@pytest.mark.parametrize("option", ["-n 2", "-n2", "-n auto", "--numprocesses 2", "--numprocesses=2"])
def test_caliber_workers_preserve_addopts_and_allow_serial_override(monkeypatch, option):
    addopts = f"-p _pytest_duckdb_guard -m integration {option}"
    monkeypatch.setenv("PYTEST_ADDOPTS", addopts)
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: ["backend/app/core_finance/credit_spread.py"])
    calls = []
    monkeypatch.setattr(gate.subprocess, "run", lambda command, **kwargs: calls.append(command) or subprocess.CompletedProcess(command, 0))

    assert gate.main(["--base-ref", "base"]) == 0
    assert calls[-1] == [gate.sys.executable, "-m", "pytest", "tests/test_credit_spread.py", "-q"]
    assert gate.main(["--base-ref", "base", "--workers", "1"]) == 0
    assert calls[-1] == [gate.sys.executable, "-m", "pytest", "tests/test_credit_spread.py", "-q", "-n", "0"]
    assert os.environ["PYTEST_ADDOPTS"] == addopts


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_caliber_workers_reject_invalid_cli_before_diff(monkeypatch, value):
    monkeypatch.setattr(gate, "list_changed_files", lambda *args, **kwargs: pytest.fail("must not compute diff"))
    with pytest.raises(SystemExit) as exc:
        gate.main(["--base-ref", "base", "--workers", value])
    assert exc.value.code == 2


def test_caliber_workers_missing_xdist_fails_clearly_before_execution(monkeypatch, capsys):
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: ["backend/app/core_finance/credit_spread.py"])
    real_find_spec = util.find_spec
    monkeypatch.setattr(util, "find_spec", lambda name, *args, **kwargs: None if name == "xdist" else real_find_spec(name, *args, **kwargs))
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not execute pytest"))
    assert gate.main(["--base-ref", "base"]) == 2
    output = capsys.readouterr().err
    assert "pytest-xdist" in output
    assert gate.sys.executable in output
    assert "uv sync --frozen --project backend --extra dev" in output


def test_caliber_workers_bad_addopts_fails_clearly_before_execution(monkeypatch, capsys):
    monkeypatch.setenv("PYTEST_ADDOPTS", '-n "unterminated')
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: ["backend/app/core_finance/credit_spread.py"])
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not execute pytest"))
    assert gate.main(["--base-ref", "base"]) == 2
    assert "PYTEST_ADDOPTS" in capsys.readouterr().err


@pytest.mark.parametrize("scope", ["--dry-run", "--frontend-scope", "--data-update-browser-scope", "--scheduler-scope", "--release-scope"])
def test_caliber_workers_selection_modes_do_not_require_xdist(monkeypatch, scope):
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: ["backend/app/core_finance/credit_spread.py"])
    monkeypatch.setattr(util, "find_spec", lambda *args, **kwargs: pytest.fail("selection must stay stdlib-only"))
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not execute pytest"))
    assert gate.main(["--base-ref", "base", scope]) == 0


@pytest.mark.parametrize(("path", "jobs"), [
    ("backend/app/core_finance/credit_spread.py", ["backend-full-pytest"]),
    ("backend/app/core_finance/new_module.py", ["backend-full-pytest"]),
    ("backend/app/core_finance/rate_units.py", ["backend-full-pytest"]),
    ("backend/app/tasks/broker.py", ["backend-full-pytest"]),
    ("backend/app/new_domain/new_module.py", ["backend-full-pytest"]),
    ("tests/new_unmarked_test.py", ["backend-full-pytest"]),
    ("tests/new_domain/conftest.py", ["backend-full-pytest"]),
    ("pytest.ini", ["backend-full-pytest"]),
    ("backend/uv.lock", ["backend-full-pytest"]),
    ("scripts/check_caliber_gate.py", ["backend-full-pytest"]),
    ("scripts/backend_release_suite.py", ["backend-full-pytest"]),
    ("frontend/package-lock.json", ["frontend"]),
    ("frontend/src/shared/new_hook.ts", ["frontend"]),
    ("scripts/new_runtime_probe.mjs", ["api-contract", "backend-full-pytest", "frontend"]),
    ("backend/app/api/routes/balance_analysis.py", ["api-contract", "backend-full-pytest", "frontend"]),
    ("backend/app/schemas/balance_analysis.py", ["api-contract", "backend-full-pytest", "frontend"]),
    ("frontend/src/api/contracts/balanceLedger.ts", ["api-contract", "backend-full-pytest", "frontend"]),
    ("docs/unmapped_metric.md", ["api-contract", "backend-full-pytest", "frontend"]),
])
def test_shadow_selection_suggests_full_layers_without_guessing_domain_tests(path, jobs):
    required_before = gate.resolve_required_tests([path])
    shadow = gate.build_shadow_selection([path], [{"status": "M", "paths": [path]}])
    assert shadow["mode"] == "advisory_only"
    assert shadow["recommended_jobs"] == jobs
    assert shadow["mandatory_test_file_count"] == len(required_before)
    assert gate.resolve_required_tests([path]) == required_before
    assert "not executed" in shadow["execution_note"]


@pytest.mark.parametrize("path", [
    "backend/app/core_finance/pnl_constants.py",
    "backend/app/core_finance/bond_analytics/read_models.py",
])
def test_shadow_core_finance_changes_require_full_backend_advice(path):
    required_before = gate.resolve_required_tests([path])
    assert required_before, "these mapped dependencies must retain their existing checks"
    shadow = gate.build_shadow_selection([path], [{"status": "M", "paths": [path]}])
    assert shadow["recommended_jobs"] == ["backend-full-pytest"]
    assert gate.resolve_required_tests([path]) == required_before


@pytest.mark.parametrize("path", [
    "backend/app/core_finance/action_attribution.py",
    "backend/app/services/bond_analytics_service.py",
    "tests/test_pnl_audit_repair.py",
])
def test_ttm_repair_dependencies_select_its_registered_regression(path):
    selected = set(gate.resolve_required_tests([path]))
    assert "tests/test_pnl_audit_repair.py" in selected
    if path == "backend/app/services/bond_analytics_service.py":
        assert {"tests/test_bond_analytics_service.py", "tests/test_advanced_attribution_contract.py"} <= selected
    elif path == "tests/test_pnl_audit_repair.py":
        assert "tests/test_caliber_gate_mapping.py" in selected


def test_shadow_report_never_changes_actual_pytest_selection_or_failure(monkeypatch, capsys):
    path = "backend/app/core_finance/credit_spread.py"
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: [path])
    monkeypatch.setattr(gate, "_list_shadow_changes", lambda _base_ref: [
        {"status": "R100", "paths": ["backend/app/new_domain/old.py", path]},
    ])
    assert gate.main(["--base-ref", "base", "--dry-run", "--shadow-selection"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["matched_tests"] == ["tests/test_credit_spread.py"]
    assert report["shadow_selection"]["recommended_jobs"] == ["backend-full-pytest"]
    monkeypatch.setattr(gate, "_list_shadow_changes", lambda *args: pytest.fail("actual execution must not read shadow advice"))
    calls = []
    monkeypatch.setattr(gate.subprocess, "run", lambda command, **kwargs: calls.append(command) or subprocess.CompletedProcess(command, 7))
    assert gate.main(["--base-ref", "base", "--workers", "1"]) == 7
    assert calls == [[gate.sys.executable, "-m", "pytest", "tests/test_credit_spread.py", "-q", "-n", "0"]]


def test_shadow_mode_requires_dry_run_before_reading_diff(monkeypatch):
    monkeypatch.setattr(gate, "list_changed_files", lambda *args, **kwargs: pytest.fail("must not read diff"))
    with pytest.raises(SystemExit) as exc:
        gate.main(["--base-ref", "base", "--shadow-selection"])
    assert exc.value.code == 2


def test_shadow_evidence_failure_discloses_full_advice_without_changing_mandatory_selection(monkeypatch, capsys):
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: ["backend/app/core_finance/credit_spread.py"])
    monkeypatch.setattr(gate, "_list_shadow_changes", lambda _base_ref: (_ for _ in ()).throw(gate.CaliberGateError("synthetic malformed rename evidence")))
    assert gate.main(["--base-ref", "base", "--dry-run", "--shadow-selection"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["matched_tests"] == ["tests/test_credit_spread.py"]
    shadow = report["shadow_selection"]
    assert shadow["status"] == "unavailable"
    assert "malformed rename" in shadow["evidence_error"]
    assert shadow["recommended_jobs"] == ["api-contract", "backend-full-pytest", "frontend"]


@pytest.mark.parametrize("output", ["R100\0only-one-path\0", "?\0path.py\0", "M\0\0"])
def test_shadow_rejects_malformed_name_status_evidence(monkeypatch, output):
    monkeypatch.setattr(gate.subprocess, "run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=output, stderr=""))
    with pytest.raises(gate.CaliberGateError):
        gate._list_shadow_changes("base")


def _run_git(repo: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0, f"git {args} failed: {completed.stderr}"


@pytest.fixture()
def gate_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temporary git repo with one gated file, one unrelated file, tag 'base'.

    Also points the gate script at this repo and injects a small gate map, so
    the tests below exercise diff matching without rebuilding the real
    core_finance tree.
    """
    empty_config = tmp_path / "empty-gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "-c", "init.defaultBranch=main", "init", "--quiet")
    _run_git(repo, "config", "user.email", "caliber-gate@example.invalid")
    _run_git(repo, "config", "user.name", "Caliber Gate Test")
    (repo / "src").mkdir()
    (repo / "src" / "gated_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "unrelated.txt").write_text("base\n", encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "--quiet", "-m", "base")
    _run_git(repo, "tag", "base")

    monkeypatch.setattr(gate, "ROOT", repo)
    monkeypatch.setattr(
        gate,
        "CALIBER_GATE_MAP",
        {"src/gated_module.py": ("tests/test_caliber_rule_hat_mapping.py",)},
    )
    return repo


def test_dry_run_reports_matched_tests_for_gated_change(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "touch gated module")

    exit_code = gate.main(["--base-ref", "base", "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["base_ref"] == "base"
    assert payload["changed_files"] == ["src/gated_module.py"]
    assert payload["matched_tests"] == ["tests/test_caliber_rule_hat_mapping.py"]


def test_cli_propagates_real_selected_pytest_failure(
    gate_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Run one synthetic failure through git diff, selection and actual pytest."""
    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "touch gated module")
    test_dir = gate_repo / "tests"
    test_dir.mkdir()
    (test_dir / "test_caliber_rule_hat_mapping.py").write_text(
        "def test_bounded_gate_failure():\n"
        "    assert False, 'bounded gate failure reached real pytest'\n",
        encoding="utf-8",
    )
    (gate_repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    # This subprocess uses only the synthetic test above. Keep the repository's
    # DuckDB guard explicitly enabled even outside its usual conftest tree.
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p _pytest_duckdb_guard")
    python_path = os.pathsep.join(filter(None, [str(REPO_ROOT), os.getenv("PYTHONPATH")]))
    monkeypatch.setenv("PYTHONPATH", python_path)

    assert gate.main(["--base-ref", "base"]) == 1

    captured = capfd.readouterr()
    assert "bounded gate failure reached real pytest" in captured.out
    assert "1 failed" in captured.out


def test_dry_run_reports_no_tests_for_unrelated_change(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "touch unrelated file")

    exit_code = gate.main(["--base-ref", "base", "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["changed_files"] == ["unrelated.txt"]
    assert payload["matched_tests"] == []
    assert payload["mapped_files"] == []
    assert payload["unmapped_files"] == ["unrelated.txt"]
    assert payload["unmapped_file_count"] == 1
    assert "not a complete backend" in payload["selection_scope"]
    assert "does not mean untested or verified" in payload["selection_note"]


def test_selection_report_lists_unmapped_paths_even_when_other_files_match(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(gate, "CALIBER_GATE_MAP", {"src/gated.py": ("tests/test_gated.py",)})
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: [
        "src\\gated.py", "src/gated.py", "src/unmapped.py", "docs/readme.md",
    ])
    assert gate.main(["--base-ref", "base", "--dry-run"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["matched_tests"] == ["tests/test_gated.py"]
    assert payload["mapped_files"] == ["src/gated.py"]
    assert payload["unmapped_files"] == ["docs/readme.md", "src/unmapped.py"]
    assert payload["changed_file_count"] == 3
    assert payload["mapped_file_count"] == 1
    assert payload["unmapped_file_count"] == 2


def test_unmapped_normal_execution_discloses_selection_boundary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(gate, "list_changed_files", lambda _base_ref, *, cwd: ["backend/app/unknown.py"])
    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not invent a test selection"))
    assert gate.main(["--base-ref", "base"]) == 0
    output = capsys.readouterr().out
    assert "0 mapped changed path(s), 1 unmapped path(s), 0 selected test file(s)" in output
    assert "does not mean untested or verified" in output
    assert "complete path lists" in output


def test_invalid_base_ref_fails_closed(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = gate.main(["--base-ref", "no-such-ref", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "FAIL-CLOSED" in captured.err
    assert "no-such-ref" in captured.err


def test_frontend_scope_cli_selects_affected_and_unrelated_changes(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        gate, "FRONTEND_FIRST_SCOPE_PATHS", ("src/gated_module.py",)
    )
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "unrelated")
    assert gate.main(["--base-ref", "base", "--frontend-scope"]) == 0
    assert capsys.readouterr().out == "false\n"

    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "affected")
    assert gate.main(["--base-ref", "base", "--frontend-scope"]) == 0
    assert capsys.readouterr().out == "true\n"


def test_release_scope_cli_selects_affected_and_unrelated_changes(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "FORMAL_RELEASE_PATHS", ("src/gated_module.py",))
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "unrelated")
    assert gate.main(["--base-ref", "base", "--release-scope"]) == 0
    assert capsys.readouterr().out == "false\n"

    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "formal source")
    assert gate.main(["--base-ref", "base", "--release-scope"]) == 0
    assert capsys.readouterr().out == "true\n"


def test_browser_scope_cli_selects_affected_and_unrelated_changes(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "DATA_UPDATE_BROWSER_PATHS", ("src/gated_module.py",))
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "unrelated")
    assert gate.main(["--base-ref", "base", "--data-update-browser-scope"]) == 0
    assert capsys.readouterr().out == "false\n"

    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "browser source")
    assert gate.main(["--base-ref", "base", "--data-update-browser-scope"]) == 0
    assert capsys.readouterr().out == "true\n"


def test_scheduler_scope_cli_selects_affected_and_unrelated_changes(
    gate_repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "SCHEDULER_WINDOWS_PATHS", ("src/gated_module.py",))
    (gate_repo / "unrelated.txt").write_text("changed\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "unrelated")
    assert gate.main(["--base-ref", "base", "--scheduler-scope"]) == 0
    assert capsys.readouterr().out == "false\n"

    (gate_repo / "src" / "gated_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    _run_git(gate_repo, "commit", "--quiet", "-am", "scheduler source")
    assert gate.main(["--base-ref", "base", "--scheduler-scope"]) == 0
    assert capsys.readouterr().out == "true\n"


def test_selected_pytest_failure_propagates_nonzero(
    gate_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_test = gate_repo / "tests" / "test_data_update_balance_integration.py"
    selected_test.parent.mkdir()
    selected_test.write_text("def test_red():\n    assert False\n", encoding="utf-8")
    changed_source = gate_repo / "backend" / "app" / "api" / "routes" / "data_updates.py"
    changed_source.parent.mkdir(parents=True)
    changed_source.write_text("VALUE = 2\n", encoding="utf-8")
    monkeypatch.setattr(
        gate,
        "CALIBER_GATE_MAP",
        {
            "backend/app/api/routes/data_updates.py": (
                "tests/test_data_update_balance_integration.py",
            ),
        },
    )
    _run_git(gate_repo, "add", ".")
    _run_git(gate_repo, "commit", "--quiet", "-m", "selected failing regression")

    assert gate.main(["--base-ref", "base"]) == 1


def test_shadow_real_rename_checks_both_paths_without_expanding_mandatory_tests(gate_repo, monkeypatch, capsys):
    old_path, new_path = "src/gated_module.py", "src/renamed_module.py"
    (gate_repo / old_path).rename(gate_repo / new_path)
    _run_git(gate_repo, "add", "-A")
    _run_git(gate_repo, "commit", "--quiet", "-m", "rename source")
    monkeypatch.setattr(gate, "CALIBER_GATE_MAP", {
        old_path: ("tests/test_old_consumer.py",), new_path: ("tests/test_new_consumer.py",),
    })
    assert gate.main(["--base-ref", "base", "--dry-run", "--shadow-selection"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["matched_tests"] == ["tests/test_new_consumer.py"]
    shadow = report["shadow_selection"]
    assert shadow["change_status_counts"]["R"] == 1
    assert shadow["additional_registered_test_count"] == 1
    assert shadow["additional_registered_test_examples"] == ["tests/test_old_consumer.py"]


def test_shadow_real_deletion_retains_existing_mandatory_checks(gate_repo, capsys):
    (gate_repo / "src/gated_module.py").unlink()
    _run_git(gate_repo, "commit", "--quiet", "-am", "delete source")
    assert gate.main(["--base-ref", "base", "--dry-run", "--shadow-selection"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["matched_tests"] == ["tests/test_caliber_rule_hat_mapping.py"]
    assert report["shadow_selection"]["change_status_counts"]["D"] == 1


def test_shadow_invalid_base_still_fails_closed_before_advice(gate_repo, monkeypatch, capsys):
    monkeypatch.setattr(gate, "_list_shadow_changes", lambda *args: pytest.fail("must not trust failed base diff"))
    assert gate.main(["--base-ref", "missing-base", "--dry-run", "--shadow-selection"]) == 2
    assert "FAIL-CLOSED" in capsys.readouterr().err


def test_shadow_mapped_document_keeps_its_registered_tests(monkeypatch):
    path = "docs/known_contract.md"
    monkeypatch.setattr(gate, "CALIBER_GATE_MAP", {path: ("tests/test_known_contract.py",)})
    shadow = gate.build_shadow_selection([path], [{"status": "M", "paths": [path]}])
    assert shadow["mandatory_test_file_count"] == 1
    assert gate.resolve_required_tests([path]) == ["tests/test_known_contract.py"]
