from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import load_module

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_SURFACE_ACCEPTANCE_MARKER = "excluded_surface_acceptance"

# 清单内文件里“已知且被审阅过”的用例级排除面验收标记。
# 这些用例会被默认门禁 deselect，其所在文件仍靠同文件的 regression 用例守住底线。
# 新增任何一条都必须在这里显式登记，否则守卫报红——门禁只允许被显式削弱，不允许被静默掏空。
GATED_ACCEPTANCE_CASE_WAIVERS = {
    "tests/test_liability_analytics_api.py": [
        "test_yield_by_period_returns_envelope_with_empty_periods_on_empty_db",
        "test_yield_metrics_payload_adds_backend_nim_stress_from_official_nim",
    ],
}


def _references_acceptance_marker(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and child.attr == EXCLUDED_SURFACE_ACCEPTANCE_MARKER
        ):
            return True
        if (
            isinstance(child, ast.Constant)
            and child.value == EXCLUDED_SURFACE_ACCEPTANCE_MARKER
        ):
            return True
    return False


def _is_pytestmark_assignment(node: ast.AST) -> bool:
    if isinstance(node, ast.Assign):
        targets: list[ast.expr] = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    else:
        return False
    return any(
        isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets
    )


def _acceptance_deselections(source: str) -> tuple[list[str], list[str]]:
    """Split a test module's acceptance markers into blanket scopes and single cases.

    Blanket scopes (module-level / class-level ``pytestmark``, class decorators) remove a
    whole module or class from the default gate; single cases come from per-test
    decorators, including ``pytest.param(marks=...)`` inside ``parametrize``.
    """

    tree = ast.parse(source)
    blanket: set[str] = set()
    cases: set[str] = set()

    for node in tree.body:
        if _is_pytestmark_assignment(node) and _references_acceptance_marker(node):
            blanket.add("模块级 pytestmark")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if any(
                _references_acceptance_marker(decorator)
                for decorator in node.decorator_list
            ):
                blanket.add(f"类装饰器 {node.name}")
            for child in node.body:
                if _is_pytestmark_assignment(child) and _references_acceptance_marker(
                    child
                ):
                    blanket.add(f"类级 pytestmark {node.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(
                _references_acceptance_marker(decorator)
                for decorator in node.decorator_list
            ):
                cases.add(node.name)

    return sorted(blanket), sorted(cases)


def _scan_gated_suite_files(module):
    """Map every gate-listed file to its acceptance deselections, plus missing files."""

    gated_lists = {
        "RELEASE_SUITE_TESTS": module.RELEASE_SUITE_TESTS,
        "GOVERNANCE_MCP_FAST_SUITE_TESTS": module.GOVERNANCE_MCP_FAST_SUITE_TESTS,
        "GOVERNANCE_MCP_FULL_SUITE_TESTS": module.GOVERNANCE_MCP_FULL_SUITE_TESTS,
    }
    missing: list[str] = []
    scanned: dict[str, tuple[str, list[str], list[str]]] = {}
    for list_name, test_paths in gated_lists.items():
        for test_path in test_paths:
            source_path = ROOT / test_path
            if not source_path.is_file():
                missing.append(f"{list_name}: {test_path}")
                continue
            # utf-8-sig: 清单里部分测试文件带 BOM，ast.parse 无法解析 \ufeff 前缀。
            blanket, cases = _acceptance_deselections(
                source_path.read_text(encoding="utf-8-sig")
            )
            scanned[test_path] = (list_name, blanket, cases)
    return missing, scanned


def test_backend_release_suite_declares_bounded_phase2_gate():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    assert module.RELEASE_SUITE_NAME == "governed-phase2-backend-release-suite"
    assert module.GOVERNANCE_MCP_SUITE_NAME == "governance-mcp-contract-suite"
    assert module.RELEASE_SUITE_TESTS == [
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
        "tests/test_api_contract_baseline_gate.py",
        "tests/test_api_response_model_field_preservation.py",
        "tests/test_no_finance_logic_in_frontend.py",
        "tests/test_caliber_rule_fx_mid_conversion.py",
        "tests/test_caliber_rule_hat_mapping.py",
        "tests/test_caliber_rule_subject_514_516_517_merge.py",
        "tests/test_caliber_rule_issuance_exclusion.py",
        "tests/test_caliber_rule_formal_scenario_gate.py",
        "tests/test_caliber_rule_accounting_basis.py",
    ]
    assert module.GOVERNANCE_MCP_FAST_SUITE_TESTS == [
        "tests/test_project_mcp_fast_contracts.py"
    ]
    assert module.GOVERNANCE_MCP_FULL_SUITE_TESTS == ["tests/test_project_mcp_servers.py"]
    assert module.EXECUTIVE_RELEASE_SAMPLE_IDS == [
        "GS-EXEC-OVERVIEW-A",
        "GS-EXEC-PNL-ATTR-A",
        "GS-EXEC-SUMMARY-A",
    ]


def test_backend_release_suite_dry_run_emits_expected_plan(capsys):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    exit_code = module.main(["--dry-run"])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["suite_name"] == "governed-phase2-backend-release-suite"
    assert report["governance_audit"] == {
        "mode": "fixture",
        "directory": None,
        "fail_on_empty": False,
    }
    assert report["pytest_args"] == [
        "-m",
        "pytest",
        "-q",
        "-m",
        "not excluded_surface_acceptance",
        *module.RELEASE_SUITE_TESTS,
    ]
    assert report["governance_mcp_suite"] == {
        "suite_name": "governance-mcp-contract-suite",
        "profile": "fast",
        "pytest_args": [
            "-m",
            "pytest",
            "-q",
            "-m",
            "mcp_fast and not excluded_surface_acceptance",
            *module.GOVERNANCE_MCP_FAST_SUITE_TESTS,
        ],
    }
    assert report["executive_release_sample_ids"] == module.EXECUTIVE_RELEASE_SAMPLE_IDS
    assert report["env"]["MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS"] == "1"
    assert report["env"]["MOSS_SKIP_POSTGRES_MIGRATIONS"] == "1"
    # 默认选择只走显式 argv，不再劫持开发者环境里已有的 PYTEST_ADDOPTS。
    assert "PYTEST_ADDOPTS" not in report["env"]


def test_backend_release_suite_dry_run_can_include_excluded_surfaces(capsys):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    exit_code = module.main(["--dry-run", "--include-excluded-surfaces"])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["pytest_args"] == ["-m", "pytest", "-q", *module.RELEASE_SUITE_TESTS]
    assert report["governance_mcp_suite"]["pytest_args"] == [
        "-m",
        "pytest",
        "-q",
        "-m",
        "mcp_fast",
        *module.GOVERNANCE_MCP_FAST_SUITE_TESTS,
    ]


def test_backend_release_suite_dry_run_preserves_governance_audit_output_arg(capsys):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    exit_code = module.main(
        [
            "--dry-run",
            "--live-governance-dir",
            "tmp/governance",
            "--governance-audit-output",
            "governance-lineage-audit.json",
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["governance_audit_output"] == "governance-lineage-audit.json"
    assert report["governance_audit"] == {
        "mode": "live",
        "directory": "tmp/governance",
        "fail_on_empty": True,
    }


def test_backend_release_suite_rejects_audit_output_without_live_directory():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    with pytest.raises(SystemExit) as exc_info:
        module.main(
            ["--dry-run", "--governance-audit-output", "misleading-empty.json"]
        )

    assert exc_info.value.code == 2


def test_backend_release_suite_dry_run_can_select_full_mcp_profile(capsys):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    exit_code = module.main(["--dry-run", "--mcp-profile", "full"])

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["governance_mcp_suite"] == {
        "suite_name": "governance-mcp-contract-suite",
        "profile": "full",
        "pytest_args": [
            "-m",
            "pytest",
            "-q",
            "-m",
            "not excluded_surface_acceptance",
            *module.GOVERNANCE_MCP_FULL_SUITE_TESTS,
        ],
    }


def test_backend_release_suite_blocks_before_pytest_when_governance_audit_is_dirty(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {
            "governance_dir": str(governance_dir),
            "files_scanned": 1,
            "dirty_rows": 2,
            "findings": [{"cache_key": "broken.cache"}],
        },
    )

    calls: list[tuple[list[str], str]] = []

    def _fake_run(*args, **kwargs):
        calls.append((list(args[0]), str(kwargs.get("cwd"))))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    exit_code = module.run_release_suite(
        root=ROOT,
        live_governance_dir="data/governance",
    )

    assert exit_code == 1
    assert calls == []


def test_backend_release_suite_live_governance_audit_fails_closed_when_empty(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {
            "governance_dir": str(governance_dir),
            "files_scanned": 0,
            "dirty_rows": 0,
            "findings": [],
        },
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kwargs: calls.append(list(args)),
    )

    assert module.run_release_suite(
        root=ROOT,
        live_governance_dir="empty-governance",
    ) == 1
    assert calls == []


def test_backend_release_suite_live_governance_audit_fails_closed_when_no_rows(
    monkeypatch,
):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {
            "governance_dir": str(governance_dir),
            "files_scanned": 1,
            "rows_scanned": 0,
            "dirty_rows": 0,
            "findings": [],
        },
    )
    calls: list[list[str]] = []
    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(
        root=ROOT,
        live_governance_dir="empty-jsonl-governance",
    ) == 1
    assert calls == []


def test_backend_release_suite_runs_bounded_then_governance_mcp_pytest_when_clean(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    def _unexpected_live_audit(_governance_dir):
        raise AssertionError("default release suite must not inspect local live governance")

    monkeypatch.setattr(module, "audit_governance_lineage", _unexpected_live_audit)

    calls: list[dict[str, object]] = []

    def _fake_run(args, **kwargs):
        calls.append(
            {
                "args": list(args),
                "cwd": str(kwargs.get("cwd")),
                "env": dict(kwargs.get("env", {})),
            }
        )
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    exit_code = module.run_release_suite(root=ROOT)

    assert exit_code == 0
    assert len(calls) == 2
    assert calls[0]["args"] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        "not excluded_surface_acceptance",
        *module.RELEASE_SUITE_TESTS,
    ]
    assert calls[1]["args"] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        "mcp_fast and not excluded_surface_acceptance",
        *module.GOVERNANCE_MCP_FAST_SUITE_TESTS,
    ]
    # 默认选择走 argv，脚本不再注入 PYTEST_ADDOPTS 覆盖开发者环境里的同名变量。
    assert "PYTEST_ADDOPTS" not in module._release_suite_env()
    for call in calls:
        assert call["cwd"] == str(ROOT)
        for key, value in module._release_suite_env().items():
            assert call["env"][key] == value


def test_backend_release_suite_uses_one_cleaned_temp_storage_root_for_both_pytest_runs(
    monkeypatch,
    tmp_path,
):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    ambient_governance = tmp_path / "ambient-governance"
    ambient_duckdb = tmp_path / "ambient.duckdb"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(ambient_governance))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(ambient_duckdb))

    observed_roots: list[Path] = []

    def _fake_run(args, **kwargs):
        env = kwargs["env"]
        governance_path = Path(env["MOSS_GOVERNANCE_PATH"])
        duckdb_path = Path(env["MOSS_DUCKDB_PATH"])

        assert governance_path != ambient_governance
        assert duckdb_path != ambient_duckdb
        assert governance_path.name == "governance"
        assert duckdb_path.name == "moss.duckdb"
        assert governance_path.parent == duckdb_path.parent

        isolated_root = governance_path.parent
        if not observed_roots:
            governance_path.mkdir(parents=True, exist_ok=True)
            (governance_path / ".locks").mkdir()
            (governance_path / ".locks" / "release-test.lock").write_text(
                "locked",
                encoding="utf-8",
            )
            duckdb_path.write_bytes(b"duckdb-test")
        else:
            assert isolated_root == observed_roots[0]
            assert (governance_path / ".locks" / "release-test.lock").is_file()
            assert duckdb_path.read_bytes() == b"duckdb-test"
        observed_roots.append(isolated_root)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(root=ROOT) == 0
    assert len(observed_roots) == 2
    assert not observed_roots[0].exists()
    assert not ambient_governance.exists()
    assert not ambient_duckdb.exists()


def test_bounded_release_tests_do_not_use_repo_relative_fake_governance():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    offenders = [
        test_path
        for test_path in module.RELEASE_SUITE_TESTS
        if '"fake-governance"'
        in (ROOT / test_path).read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_gated_release_suite_files_are_not_marked_excluded_surface_acceptance():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    missing, scanned = _scan_gated_suite_files(module)

    assert missing == [], "发布套件清单引用了不存在的测试文件：\n" + "\n".join(
        f"  - {entry}" for entry in missing
    )

    offenders = [
        f"{list_name}: {test_path} -> {', '.join(blanket)}"
        for test_path, (list_name, blanket, _cases) in sorted(scanned.items())
        if blanket
    ]
    assert offenders == [], (
        "发布套件清单内的文件不得标为排除面验收（"
        f"{EXCLUDED_SURFACE_ACCEPTANCE_MARKER}），否则门禁将静默失效："
        '默认选择 -m "not excluded_surface_acceptance" 会把整个模块/类 deselect，'
        "发布套件不再验证它们却照样报绿。\n"
        "违规文件：\n"
        + "\n".join(f"  - {entry}" for entry in offenders)
        + "\n处理方式：改用 excluded_surface_regression 标记，"
        "或显式把该文件移出 scripts/backend_release_suite.py 的清单并说明理由。"
    )


def test_gated_release_suite_per_case_acceptance_waivers_stay_declared():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    _missing, scanned = _scan_gated_suite_files(module)
    observed = {
        test_path: cases
        for test_path, (_list_name, _blanket, cases) in scanned.items()
        if cases
    }

    assert observed == GATED_ACCEPTANCE_CASE_WAIVERS, (
        "发布套件清单内文件的用例级排除面验收标记发生了未登记的变化，"
        "门禁会静默少跑这些用例却照样报绿。\n"
        f"当前扫描结果：{json.dumps(observed, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        f"已登记豁免：{json.dumps(GATED_ACCEPTANCE_CASE_WAIVERS, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        "处理方式：若确属排除面验收，请在 GATED_ACCEPTANCE_CASE_WAIVERS 显式登记并说明理由；"
        "否则改用 excluded_surface_regression 标记，把用例留在门禁内。"
    )


def test_backend_release_suite_stops_before_governance_mcp_when_bounded_pytest_fails(
    monkeypatch,
):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {"governance_dir": str(governance_dir), "dirty_rows": 0},
    )
    calls: list[list[str]] = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 7)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(root=ROOT) == 7
    assert calls == [
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            "not excluded_surface_acceptance",
            *module.RELEASE_SUITE_TESTS,
        ]
    ]


def test_backend_release_suite_returns_governance_mcp_failure(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {"governance_dir": str(governance_dir), "dirty_rows": 0},
    )
    calls: list[list[str]] = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0 if len(calls) == 1 else 9)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(root=ROOT) == 9
    assert calls == [
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            "not excluded_surface_acceptance",
            *module.RELEASE_SUITE_TESTS,
        ],
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            "mcp_fast and not excluded_surface_acceptance",
            *module.GOVERNANCE_MCP_FAST_SUITE_TESTS,
        ],
    ]


def test_backend_release_suite_can_run_full_governance_mcp_profile(monkeypatch):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )
    monkeypatch.setattr(
        module,
        "audit_governance_lineage",
        lambda governance_dir: {"governance_dir": str(governance_dir), "dirty_rows": 0},
    )
    calls: list[list[str]] = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    assert module.run_release_suite(root=ROOT, mcp_profile="full") == 0
    assert calls[-1] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        "not excluded_surface_acceptance",
        *module.GOVERNANCE_MCP_FULL_SUITE_TESTS,
    ]


def test_backend_release_suite_writes_governance_audit_output_when_requested(monkeypatch, tmp_path):
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    summary = {
        "governance_dir": str(tmp_path / "gov"),
        "files_scanned": 1,
        "rows_scanned": 1,
        "dirty_rows": 0,
        "findings": [],
    }
    monkeypatch.setattr(module, "audit_governance_lineage", lambda governance_dir: summary)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0),
    )

    output_path = tmp_path / "governance-lineage-audit.json"
    exit_code = module.run_release_suite(
        root=ROOT,
        live_governance_dir=str(tmp_path / "gov"),
        governance_audit_output=output_path,
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == summary
