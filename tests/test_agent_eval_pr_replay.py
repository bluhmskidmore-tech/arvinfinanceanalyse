import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.agent_eval import collect as collect_module
from scripts.agent_eval import pr_replay as pr_replay_module
from scripts.agent_eval.collect import CommandOutcome
from scripts.agent_eval.pr_replay import (
    COMMENT_MARKER,
    _render_task_section,
    _split_hard_failures,
    _task_applies,
    _unmapped_shared_files,
    _worktree_signature,
    main,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

TASK = {
    "id": "pr_probe_demo_001",
    "page": "ledger-pnl",
    "goal": "PR replay selection fixture.",
    # 证据工件走运行期产物目录（.codex-tmp/ 被 .gitignore），CI 检出中恒缺失：
    # 复现生产任务的 evidence_probes 形态，报告必须把它与探针红灯区分开。
    "required_evidence": ["moss-metric-contracts"],
    "evidence_probes": {
        "moss-metric-contracts": ".codex-tmp/agent-eval/evidence/metric-contracts.json"
    },
    "checks": [],
    "business_gates": ["unit_consistency"],
    "page_gates": [],
    "gate_probes": {},
    "gate_probe_gaps": {"unit_consistency": "fixture gap reason"},
    "allowed_scope": ["frontend/src/features/ledger-pnl/"],
    "forbidden": ["backend/app/schema_registry/"],
}


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
def pr_repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "harness@example.com")
    _git(tmp_path, "config", "user.name", "harness")
    _commit(tmp_path, "seed.txt", "seed\n")
    _git(tmp_path, "branch", "base")
    return tmp_path


def test_task_applies_matches_scope_prefix_against_diff():
    changed = ["frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx"]
    assert _task_applies(TASK, changed) is True

    unrelated = ["backend/app/services/pnl_service.py", "docs/readme.md"]
    assert _task_applies(TASK, unrelated) is False

    assert _task_applies(TASK, []) is False


def test_pr_trigger_scope_selects_domain_files_without_changing_allowed_scope():
    task = dict(
        TASK,
        allowed_scope=["frontend/src/features/ledger-pnl/", "frontend/src/api/", "frontend/src/test/"],
        pr_trigger_scope=[
            "frontend/src/features/ledger-pnl/",
            "frontend/src/api/pnlCoreClient.ts",
            "frontend/src/test/LedgerPnl*",
        ],
    )

    assert _task_applies(task, ["frontend/src/api/pnlCoreClient.ts"])
    assert _task_applies(task, ["frontend/src/test/LedgerPnlPage.test.tsx"])
    assert not _task_applies(task, ["frontend/src/api/agentClient.ts"])
    assert not _task_applies(task, ["frontend/src/test/AgentPanel.test.tsx"])
    assert task["allowed_scope"] == [
        "frontend/src/features/ledger-pnl/", "frontend/src/api/", "frontend/src/test/"
    ]


def test_shipped_trigger_mapping_retains_cross_page_files_and_classifies_unknowns():
    task_paths = sorted((Path(__file__).resolve().parents[1] / "scripts/agent_eval/tasks").glob("*.json"))
    tasks = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in task_paths]

    def selected(path):
        return {task["id"] for _, task in tasks if _task_applies(task, [path])}

    all_ids = {task["id"] for _, task in tasks}
    assert len(all_ids) == 7
    assert selected("frontend/src/api/client.ts") == all_ids
    assert selected("frontend/src/api/httpResponseError.ts") == all_ids
    assert selected("frontend/src/test/setup.ts") == all_ids
    embedded_agent_pages = {
        "bond_analytics_contract_001", "dashboard_home_contract_001",
        "pnl_attribution_contract_001",
    }
    assert selected("frontend/src/api/agentClient.ts") == embedded_agent_pages
    assert selected("frontend/src/test/AgentEmbeddedReleaseGate.test.tsx") == embedded_agent_pages
    assert selected("frontend/src/test/AgentPanel.test.tsx") == embedded_agent_pages
    assert selected("frontend/src/test/BalanceMovementAnalysisPage.test.tsx") == {
        "balance_analysis_contract_001"
    }
    assert selected("frontend/src/test/BondKpiRow.unit.test.tsx") == {
        "bond_analytics_contract_001"
    }
    assert selected("frontend/src/test/PnlCoreClientRevalidation.test.ts") == {
        "dashboard_home_contract_001", "ledger_pnl_unit_mismatch_001"
    }
    assert selected("frontend/src/test/AgentClient.test.ts") == set()
    assert _unmapped_shared_files(["frontend/src/test/AgentClient.test.ts"], tasks) == []
    assert _unmapped_shared_files(["frontend/src/test/AgentNew.test.ts"], tasks) == [
        "frontend/src/test/AgentNew.test.ts"
    ]
    assert selected("frontend/src/api/productCategoryClient.ts") == {
        "pnl_attribution_contract_001", "product_category_pnl_contract_001"
    }
    for dashboard_dependency in (
        "pnlCoreClient.ts", "pnlCoreMockClient.ts", "candidateFinancialIndicatorsClient.ts",
        "marketDataClient.ts", "marketDataMockClient.ts", "pnlAttributionMockClient.ts",
        "contracts/researchCalendar.ts",
    ):
        assert "dashboard_home_contract_001" in selected(
            f"frontend/src/api/{dashboard_dependency}"
        )
    assert selected("frontend/src/test/BalanceAnalysisPage.test.tsx") == {
        "balance_analysis_contract_001"
    }
    assert selected("frontend/src/test/RiskTensorPage.test.tsx") == {"risk_tensor_contract_001"}
    assert _unmapped_shared_files(["frontend/src/api/newSharedClient.ts"], tasks) == [
        "frontend/src/api/newSharedClient.ts"
    ]


@pytest.mark.parametrize(
    ("changed_path", "expected_count", "mapping_review"),
    [
        ("frontend/src/api/pnlCoreClient.ts", 1, False),
        ("frontend/src/api/newSharedClient.ts", 2, True),
        ("frontend/src/test/AgentClient.test.ts", 0, False),
    ],
)
def test_pr_replay_fails_open_for_unmapped_shared_file(
    pr_repo, tmp_path, monkeypatch, changed_path, expected_count, mapping_review
):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    for task_id, trigger in (
        ("ledger", "frontend/src/api/pnlCoreClient.ts"),
        ("balance", "frontend/src/api/balanceAnalysisClient.ts"),
    ):
        task = dict(
            TASK,
            id=task_id,
            allowed_scope=["frontend/src/api/", "frontend/src/test/"],
            pr_trigger_scope=[trigger],
        )
        (tasks_dir / f"{task_id}.json").write_text(json.dumps(task), encoding="utf-8")
    _commit(pr_repo, changed_path, "export const changed = true;\n")
    calls = []

    def fake_run_replay(task_path, task, base_ref, out_root, repo_root, command_cache):
        calls.append(task["id"])
        return {
            "exit_code": 0,
            "stderr_tail": "",
            "scorecard": {"status": "pass", "score": 100},
            "result": {"measurement": {"integrity": {"trusted": True, "violations": []}}},
        }

    monkeypatch.setattr(pr_replay_module, "_run_replay", fake_run_replay)
    out_md = tmp_path / "report.md"
    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--out-md", str(out_md),
    ]) == 0

    assert len(calls) == expected_count
    report = out_md.read_text(encoding="utf-8")
    assert ("选择器映射待复核" in report) is mapping_review
    if mapping_review:
        assert changed_path in report


def test_split_hard_failures_separates_gaps_and_missing_evidence_from_real_failures():
    hard = [
        "Business gate failed: unit_consistency",
        "Required check failed: npm --prefix frontend run typecheck",
        "Missing required evidence: moss-metric-contracts",
        "Page gate failed: page_loads",
    ]
    real, gaps, missing_evidence = _split_hard_failures(
        hard, unprobed={"unit_consistency", "page_loads"}
    )

    # 证据工件缺失不得混入"真实失败"（探针变红）：它的 gate 名不在 unprobed
    # 分流里，旧实现会把它归为 real。
    assert real == ["Required check failed: npm --prefix frontend run typecheck"]
    assert gaps == [
        "Business gate failed: unit_consistency",
        "Page gate failed: page_loads",
    ]
    assert missing_evidence == ["Missing required evidence: moss-metric-contracts"]


def test_render_task_section_marks_void_when_measurement_is_rejected():
    outcome = {
        "exit_code": 2,
        "stderr_tail": "Invalid agent eval measurement: Measurement is not trustworthy: x",
        "scorecard": None,
        "result": {
            "measurement": {
                "integrity": {
                    "trusted": False,
                    "violations": ["Scoring harness file modified during the run: scripts/agent_eval/reward.py"],
                }
            }
        },
        "archive": None,
    }

    section = _render_task_section(TASK, outcome)

    assert "void" in section
    assert "scripts/agent_eval/reward.py" in section
    assert "人工评审" in section


def test_end_to_end_no_applicable_task_renders_skip_report(pr_repo, tmp_path, capsys):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")
    _commit(pr_repo, "docs/unrelated.md", "outside every task scope\n")
    out_md = tmp_path / "report.md"

    exit_code = main(
        [
            "--base-ref",
            "base",
            "--repo-root",
            str(pr_repo),
            "--tasks-dir",
            "tasks",
            "--out-root",
            str(tmp_path / "archives"),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    report = out_md.read_text(encoding="utf-8")
    assert report.startswith(COMMENT_MARKER)
    assert "适用任务 0/1" in report
    assert "未运行评测" in report


def test_preflight_skips_dependency_setup_for_no_applicable_task_but_keeps_report(
    pr_repo, tmp_path, capsys
):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")
    _commit(pr_repo, "docs/unrelated.md", "outside every task scope\n")
    args = [
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--out-md", str(tmp_path / "report.md"),
    ]

    assert main([*args, "--preflight"]) == 0
    assert capsys.readouterr().out == "needs_dependency_setup=false\n"
    assert main(args) == 0
    assert "适用任务 0/1" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_preflight_skips_dependency_setup_for_deterministic_void_but_keeps_report(
    pr_repo, tmp_path, capsys
):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    task = dict(TASK, allowed_scope=["scripts/agent_eval/"])
    (tasks_dir / "demo.json").write_text(json.dumps(task), encoding="utf-8")
    _git(pr_repo, "add", "tasks")
    _git(pr_repo, "commit", "-m", "add task")
    _git(pr_repo, "branch", "-f", "base", "HEAD")
    _commit(pr_repo, "scripts/agent_eval/reward.py", "PASS_THRESHOLD = 0\n")
    args = [
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--out-md", str(tmp_path / "report.md"),
    ]

    assert main([*args, "--preflight"]) == 0
    assert capsys.readouterr().out == "needs_dependency_setup=false\n"
    assert main(args) == 0
    assert "**void**" in (tmp_path / "report.md").read_text(encoding="utf-8")
    archive = tmp_path / "archives" / TASK["id"]
    result = json.loads((archive / "result.json").read_text(encoding="utf-8"))
    assert result["measurement"]["integrity"]["trusted"] is False
    assert result["measurement"]["commands"] == []
    assert "status: invalid" in (archive / "summary.txt").read_text(encoding="utf-8")
    assert not (archive / "scorecard.json").exists()


def test_preflight_keeps_dependency_setup_for_trusted_selected_task(pr_repo, tmp_path, capsys):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")

    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--preflight",
    ]) == 0
    assert capsys.readouterr().out == "needs_dependency_setup=true\n"


def test_preflight_keeps_dependency_setup_when_only_one_selected_task_is_void(
    pr_repo, capsys
):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    for task_id, protected_paths in (("void", ["tests/probe.py"]), ("trusted", [])):
        task = dict(TASK, id=task_id, probe_protected_paths=protected_paths)
        (tasks_dir / f"{task_id}.json").write_text(json.dumps(task), encoding="utf-8")
    _commit(pr_repo, "tests/probe.py", "def test_probe(): pass\n")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")

    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--preflight",
    ]) == 0
    assert capsys.readouterr().out == "needs_dependency_setup=true\n"


def test_preflight_orchestration_failure_does_not_emit_skip_signal(pr_repo, capsys):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")

    assert main([
        "--base-ref", "no-such-ref", "--repo-root", str(pr_repo),
        "--tasks-dir", "tasks", "--preflight",
    ]) == 2
    output = capsys.readouterr()
    assert "needs_dependency_setup=false" not in output.out
    assert "orchestration error" in output.err


def test_ci_preflight_guards_agent_replay_dependency_setup():
    workflow_path = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    job = workflow.split("\n  agent-eval-replay:\n", 1)[1].split("\n  backend-full-pytest:\n", 1)[0]

    def named_step(name):
        return job.split(f"\n      - name: {name}\n", 1)[1].split("\n      - name: ", 1)[0]

    preflight = named_step("Check PR replay dependency setup")
    assert "id: agent_eval_preflight" in preflight
    assert preflight.index("git fetch") < preflight.index("--preflight")
    assert '--preflight >> "$GITHUB_OUTPUT"' in preflight
    guard = "if: steps.agent_eval_preflight.outputs.needs_dependency_setup != 'false'"
    assert job.index("- name: Set up Python") < job.index("- name: Check PR replay dependency setup")
    assert job.index("- name: Check PR replay dependency setup") < job.index("- name: Set up uv")
    for name in (
        "Set up uv", "Install backend dependencies from backend/uv.lock",
        "Set up Node.js", "Install frontend dependencies", "Install Playwright Chromium",
    ):
        assert guard in named_step(name)
    assert "\n        if:" not in named_step("Run PR replay evaluation")


def test_end_to_end_applicable_task_runs_replay_and_reports_probe_gap(pr_repo, tmp_path):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")
    _git(pr_repo, "add", "tasks/demo.json")
    _git(pr_repo, "commit", "-m", "add task")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx", "export const x = 1;\n")
    out_md = tmp_path / "report.md"

    exit_code = main(
        [
            "--base-ref",
            "base",
            "--repo-root",
            str(pr_repo),
            "--tasks-dir",
            "tasks",
            "--out-root",
            str(tmp_path / "archives"),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    report = out_md.read_text(encoding="utf-8")
    assert "适用任务 1/1" in report
    assert "pr_probe_demo_001" in report
    assert "fail" in report
    assert "探针缺口（1）" in report
    assert "fixture gap reason" in report
    # .codex-tmp/ 工件在检出中不存在：单列"证据工件缺失"，且不得渲染成真实失败。
    assert "证据工件缺失（1）" in report
    assert "Missing required evidence: moss-metric-contracts" in report
    assert "工件状态：missing" in report
    assert "真实失败" not in report
    assert "不阻塞合并" in report

    archive = tmp_path / "archives" / "pr_probe_demo_001"
    assert (archive / "scorecard.json").is_file()
    assert (archive / "result.json").is_file()
    assert (archive / "summary.txt").is_file()


def test_orchestration_fails_closed_on_bad_base_ref(pr_repo, tmp_path, capsys):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")

    exit_code = main(
        [
            "--base-ref",
            "no-such-ref",
            "--repo-root",
            str(pr_repo),
            "--tasks-dir",
            "tasks",
            "--out-root",
            str(tmp_path / "archives"),
        ]
    )

    assert exit_code == 2
    assert "orchestration error" in capsys.readouterr().err


@pytest.mark.parametrize("failure_mode", ["raises", "returns_two"])
def test_replay_anomaly_fails_orchestration_and_clears_stale_archive(
    pr_repo, tmp_path, monkeypatch, capsys, failure_mode
):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")

    archive = tmp_path / "archives" / TASK["id"]
    archive.mkdir(parents=True)
    (archive / "result.json").write_text(json.dumps({"measurement": {"integrity": {"trusted": True}}}), encoding="utf-8")
    (archive / "scorecard.json").write_text(json.dumps({"status": "pass", "score": 100}), encoding="utf-8")
    (archive / "summary.txt").write_text("status: pass\n", encoding="utf-8")
    (archive / "task.json").write_text(json.dumps(TASK), encoding="utf-8")

    def broken_replay(*args, **kwargs):
        if failure_mode == "raises":
            raise OSError("replay executable broke")
        return 2

    monkeypatch.setattr(pr_replay_module.replay, "main", broken_replay)
    report_path = tmp_path / "report.md"
    exit_code = main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--out-md", str(report_path),
    ])

    assert exit_code == 2
    report = report_path.read_text(encoding="utf-8")
    assert "orchestration error" in report
    assert "**void**" not in report
    assert "**pass**" not in report
    assert "orchestration error" in capsys.readouterr().err
    for artifact in ("result.json", "scorecard.json", "summary.txt", "task.json"):
        assert not (archive / artifact).exists()


def test_new_integrity_void_replaces_stale_pass_archive(pr_repo, tmp_path):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    task = dict(TASK, allowed_scope=["scripts/agent_eval/"])
    (tasks_dir / "demo.json").write_text(json.dumps(task), encoding="utf-8")
    _git(pr_repo, "add", "tasks")
    _git(pr_repo, "commit", "-m", "add task")
    _git(pr_repo, "branch", "-f", "base", "HEAD")
    _commit(pr_repo, "scripts/agent_eval/reward.py", "PASS_THRESHOLD = 0\n")

    archive = tmp_path / "archives" / TASK["id"]
    archive.mkdir(parents=True)
    (archive / "scorecard.json").write_text(json.dumps({"status": "pass", "score": 100}), encoding="utf-8")
    (archive / "summary.txt").write_text("status: pass\n", encoding="utf-8")
    report_path = tmp_path / "report.md"

    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--out-md", str(report_path),
    ]) == 0
    assert "**void**" in report_path.read_text(encoding="utf-8")
    assert not (archive / "scorecard.json").exists()
    result = json.loads((archive / "result.json").read_text(encoding="utf-8"))
    assert result["measurement"]["integrity"]["trusted"] is False
    assert result["measurement"]["integrity"]["violations"]
    assert "status: invalid" in (archive / "summary.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("missing", ["task.json", "result.json", "scorecard.json", "summary.txt"])
def test_replay_missing_current_artifact_is_orchestration_error(
    pr_repo, tmp_path, monkeypatch, missing
):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")

    def incomplete_replay(argv, **kwargs):
        archive = Path(argv[argv.index("--out-dir") + 1])
        payloads = {
            "task.json": TASK,
            "result.json": {"measurement": {"integrity": {"trusted": True, "violations": []}}},
            "scorecard.json": {"status": "pass", "score": 100},
            "summary.txt": "status: pass\n",
        }
        for name, payload in payloads.items():
            if name == missing:
                continue
            destination = archive / name
            if name.endswith(".json"):
                destination.write_text(json.dumps(payload), encoding="utf-8")
            else:
                destination.write_text(payload, encoding="utf-8")
        return 0

    monkeypatch.setattr(pr_replay_module.replay, "main", incomplete_replay)
    report_path = tmp_path / "report.md"
    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--out-md", str(report_path),
    ]) == 2
    report = report_path.read_text(encoding="utf-8")
    assert "orchestration error" in report
    assert "**void**" not in report
    assert "**pass**" not in report


@pytest.mark.parametrize("kind", ["parent", "absolute"])
def test_unsafe_task_id_cannot_touch_external_archive(
    pr_repo, tmp_path, monkeypatch, capsys, kind
):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "scorecard.json"
    sentinel.write_text("keep external artifact", encoding="utf-8")
    task_id = "../outside" if kind == "parent" else str(outside)
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(
        json.dumps(dict(TASK, id=task_id)), encoding="utf-8"
    )
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")
    calls = []
    monkeypatch.setattr(pr_replay_module.replay, "main", lambda *args, **kwargs: calls.append(1) or 2)

    exit_code = main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"),
    ])

    assert sentinel.read_text(encoding="utf-8") == "keep external artifact"
    assert calls == []
    assert exit_code == 2
    assert "unsafe task id" in capsys.readouterr().err.lower()


def test_duplicate_task_id_fails_before_replay(pr_repo, tmp_path, capsys):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    for name in ("first", "second"):
        (tasks_dir / f"{name}.json").write_text(json.dumps(TASK), encoding="utf-8")

    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--preflight",
    ]) == 2
    assert "duplicate task id" in capsys.readouterr().err.lower()


def test_case_only_duplicate_task_ids_fail_before_replay(pr_repo, tmp_path, capsys):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    for name, task_id in (("first", "Foo"), ("second", "foo")):
        (tasks_dir / f"{name}.json").write_text(
            json.dumps(dict(TASK, id=task_id)), encoding="utf-8"
        )

    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--preflight",
    ]) == 2
    assert "duplicate task id" in capsys.readouterr().err.lower()


def test_hyphenated_task_id_remains_valid(pr_repo, tmp_path, capsys):
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(
        json.dumps(dict(TASK, id="pr-probe-demo-001")), encoding="utf-8"
    )

    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(tmp_path / "archives"), "--preflight",
    ]) == 0
    assert capsys.readouterr().out == "needs_dependency_setup=false\n"


def test_symlinked_task_archive_cannot_touch_external_artifact(
    pr_repo, tmp_path, monkeypatch
):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "scorecard.json"
    sentinel.write_text("keep external artifact", encoding="utf-8")
    out_root = tmp_path / "archives"
    out_root.mkdir()
    try:
        os.symlink(outside, out_root / TASK["id"], target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"directory symlinks unavailable: {error}")

    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "demo.json").write_text(json.dumps(TASK), encoding="utf-8")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")
    calls = []
    monkeypatch.setattr(pr_replay_module.replay, "main", lambda *args, **kwargs: calls.append(1) or 2)

    assert main([
        "--base-ref", "base", "--repo-root", str(pr_repo), "--tasks-dir", "tasks",
        "--out-root", str(out_root),
    ]) == 2
    assert sentinel.read_text(encoding="utf-8") == "keep external artifact"
    assert calls == []


def test_run_replay_guard_rejects_absolute_id_without_touching_external_artifact(
    tmp_path, monkeypatch
):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "scorecard.json"
    sentinel.write_text("keep external artifact", encoding="utf-8")
    out_root = tmp_path / "archives"
    out_root.mkdir()
    task = dict(TASK, id=str(outside))
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(task), encoding="utf-8")
    calls = []
    monkeypatch.setattr(pr_replay_module.replay, "main", lambda *args, **kwargs: calls.append(1) or 2)

    outcome = pr_replay_module._run_replay(
        task_path, task, "base", out_root, tmp_path, {}
    )

    assert sentinel.read_text(encoding="utf-8") == "keep external artifact"
    assert calls == []
    assert outcome["exit_code"] == 2
    assert "escapes output root" in outcome["stderr_tail"]


def test_applicable_tasks_reuse_identical_check_without_losing_task_archives(
    pr_repo, tmp_path, monkeypatch
):
    output_root = tmp_path.parent / f"{tmp_path.name}-output"
    output_root.mkdir()
    command = "npm --prefix frontend run typecheck"
    calls = []

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        return CommandOutcome(exit_code=0)

    monkeypatch.setattr(collect_module, "run_shell_command", runner)
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    for task_id in ("first", "second"):
        task = dict(TASK, id=task_id, checks=[command])
        (tasks_dir / f"{task_id}.json").write_text(json.dumps(task), encoding="utf-8")
    _git(pr_repo, "add", "tasks")
    _git(pr_repo, "commit", "-m", "add tasks")
    _git(pr_repo, "branch", "-f", "base", "HEAD")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")

    exit_code = main(
        [
            "--base-ref", "base",
            "--repo-root", str(pr_repo),
            "--tasks-dir", "tasks",
            "--out-root", str(output_root / "archives"),
        ]
    )

    assert exit_code == 0
    assert calls == [command]
    for task_id, reused in (("first", False), ("second", True)):
        archive = output_root / "archives" / task_id
        result = json.loads((archive / "result.json").read_text(encoding="utf-8"))
        scorecard = json.loads((archive / "scorecard.json").read_text(encoding="utf-8"))
        assert result["checks"][command] == "passed"
        assert result["measurement"]["commands"][0].get("reused_cached_run", False) is reused
        assert scorecard["status"] == "fail"  # the declared gate and evidence still fail closed


def test_worktree_edit_between_tasks_invalidates_shared_check(pr_repo, tmp_path, monkeypatch):
    output_root = tmp_path.parent / f"{tmp_path.name}-output"
    output_root.mkdir()
    command = "npm --prefix frontend run typecheck"
    calls = []

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        with (cwd / "tracked.txt").open("a", encoding="utf-8") as file:
            file.write("x")
        return CommandOutcome(exit_code=0)

    monkeypatch.setattr(collect_module, "run_shell_command", runner)
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    for task_id in ("first", "second"):
        (tasks_dir / f"{task_id}.json").write_text(
            json.dumps(dict(TASK, id=task_id, checks=[command])), encoding="utf-8"
        )
    _git(pr_repo, "add", "tasks")
    _git(pr_repo, "commit", "-m", "add tasks")
    _commit(pr_repo, "tracked.txt", "")
    _git(pr_repo, "branch", "-f", "base", "HEAD")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")

    assert main([
        "--base-ref", "base",
        "--repo-root", str(pr_repo),
        "--tasks-dir", "tasks",
        "--out-root", str(output_root / "archives"),
    ]) == 0

    assert calls == [command, command]
    second_result = json.loads(
        (output_root / "archives" / "second" / "result.json").read_text(encoding="utf-8")
    )
    assert second_result["measurement"]["commands"][0].get("reused_cached_run", False) is False


def test_harness_change_reports_void_without_running_check(pr_repo, tmp_path):
    output_root = tmp_path.parent / f"{tmp_path.name}-output"
    output_root.mkdir()
    counter = output_root / "check-runs.txt"
    command = (
        f'"{sys.executable}" -c "from pathlib import Path; '
        f"Path('{counter.as_posix()}').write_text('ran')\""
    )
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    task = dict(TASK, checks=[command], allowed_scope=["scripts/agent_eval/"])
    (tasks_dir / "demo.json").write_text(json.dumps(task), encoding="utf-8")
    _git(pr_repo, "add", "tasks")
    _git(pr_repo, "commit", "-m", "add task")
    _git(pr_repo, "branch", "-f", "base", "HEAD")
    _commit(pr_repo, "scripts/agent_eval/reward.py", "PASS_THRESHOLD = 0\n")

    assert main([
        "--base-ref", "base",
        "--repo-root", str(pr_repo),
        "--tasks-dir", "tasks",
        "--out-root", str(output_root / "archives"),
    ]) == 0

    archive = output_root / "archives" / TASK["id"]
    result = json.loads((archive / "result.json").read_text(encoding="utf-8"))
    report = (output_root / "archives" / "summary.md").read_text(encoding="utf-8")
    assert result["measurement"]["commands"] == []
    assert not counter.exists()
    assert not (archive / "scorecard.json").exists()
    assert "status: invalid" in (archive / "summary.txt").read_text(encoding="utf-8")
    assert "**void**" in report
    assert "scripts/agent_eval/reward.py" in report


@pytest.mark.parametrize(("kind", "command"), [
    ("gate", "python -m pytest tests/test_probe.py -q"),
    ("check", "custom-check"),
    ("check", "npm --prefix frontend run debt:audit"),
])
def test_non_allowlisted_command_runs_per_task_when_ignored_runtime_state_changes(
    pr_repo, tmp_path, monkeypatch, kind, command
):
    _commit(pr_repo, ".gitignore", ".codex-tmp/\n")
    tasks_dir = pr_repo / "tasks"
    tasks_dir.mkdir()
    for task_id in ("first", "second"):
        task = dict(
            TASK,
            id=task_id,
            **({"gate_probes": {"unit_consistency": command}} if kind == "gate" else {"checks": [command]}),
        )
        (tasks_dir / f"{task_id}.json").write_text(json.dumps(task), encoding="utf-8")
    _git(pr_repo, "add", "tasks")
    _git(pr_repo, "commit", "-m", "add tasks")
    _git(pr_repo, "branch", "-f", "base", "HEAD")
    _commit(pr_repo, "frontend/src/features/ledger-pnl/page.tsx", "export const x = 1;\n")

    calls = []

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        runtime_file = cwd / ".codex-tmp" / "state.txt"
        if runtime_file.exists():
            return CommandOutcome(exit_code=1)
        runtime_file.parent.mkdir()
        runtime_file.write_text("changed after first task", encoding="utf-8")
        return CommandOutcome(exit_code=0)

    monkeypatch.setattr(collect_module, "run_shell_command", runner)
    output_root = tmp_path.parent / f"{tmp_path.name}-output"

    assert main([
        "--base-ref", "base",
        "--repo-root", str(pr_repo),
        "--tasks-dir", "tasks",
        "--out-root", str(output_root),
    ]) == 0

    assert calls == [command, command]
    first = json.loads((output_root / "first" / "result.json").read_text(encoding="utf-8"))
    second = json.loads((output_root / "second" / "result.json").read_text(encoding="utf-8"))
    field, key = ("business_gates", "unit_consistency") if kind == "gate" else ("checks", command)
    assert first[field][key] == "passed"
    assert second[field][key] == "failed"
    assert second["measurement"]["commands"][0].get("reused_cached_run", False) is False


def test_worktree_signature_frames_untracked_paths_and_contents(pr_repo):
    first_path = pr_repo / "a"
    first_path.write_bytes(b"bc")
    first_signature = _worktree_signature(pr_repo)
    first_path.unlink()
    (pr_repo / "ab").write_bytes(b"c")

    assert _worktree_signature(pr_repo) != first_signature
