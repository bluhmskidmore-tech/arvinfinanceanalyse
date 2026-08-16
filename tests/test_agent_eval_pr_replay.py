import json
import subprocess

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

from scripts.agent_eval.pr_replay import (
    COMMENT_MARKER,
    _render_task_section,
    _split_hard_failures,
    _task_applies,
    main,
)

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
