import os
import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]

ROOT = Path(__file__).resolve().parents[1]


def run_launcher(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "start-hermes-agent-team.ps1"),
            *args,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def run_finance_cluster(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "start-moss-finance-audit-cluster.ps1"),
            *args,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def test_prepare_only_generates_team_board_and_role_prompts(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "unit-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
        "-WslDistro",
        "HermesUbuntu",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "Hermes agent team prepared" in completed.stdout
    assert "Run with -Launch to open the team windows" in completed.stdout

    team_dir = output_root / "unit-team"
    board = team_dir / "TEAM_BOARD.md"
    manifest = team_dir / "manifest.json"
    runner = team_dir / "launch" / "run-role.ps1"
    assert board.exists()
    assert manifest.exists()
    assert "Build the MOSS agent system" in board.read_text(encoding="utf-8")
    assert "Role Workspaces" in board.read_text(encoding="utf-8")
    assert_powershell_script_parses(runner)
    runner_text = runner.read_text(encoding="utf-8")
    assert "[Console]::InputEncoding" in runner_text
    assert "[Console]::OutputEncoding" in runner_text
    assert "PYTHONIOENCODING" in runner_text
    assert "PYTHONUTF8" in runner_text
    assert "wsl.exe" in runner_text
    assert "$WslCommand" in runner_text
    assert "Invoke-NativeCommand -Command $HermesCommand" in runner_text
    assert "Read and follow the Hermes role prompt at" in runner_text
    assert "DispatchUrl" in runner_text
    assert "DispatchToken" in runner_text
    assert "TaskClaimToken" in runner_text
    assert "claim_token" in runner_text
    assert "X-Hermes-Dispatch-Token" in runner_text
    assert "/api/task/heartbeat" in runner_text
    assert "/api/task/complete" in runner_text
    assert "Invoke-RestMethod" in runner_text

    expected_roles = {
        "lead": "Leader",
        "product-manager": "Product Manager",
        "frontend-developer": "Frontend Developer",
        "developer": "Developer",
        "backend-api-contract-engineer": "Backend API Contract Engineer",
        "metric-caliber-officer": "Metric Caliber Officer",
        "data-lineage-auditor": "Data Lineage Auditor",
        "security-permission-auditor": "Security Permission Auditor",
        "asset-liability-manager": "Asset Liability Manager",
        "pnl-attribution-analyst": "PnL Attribution Analyst",
        "risk-manager": "Risk Manager",
        "fixed-income-analyst": "Fixed Income Analyst",
        "market-data-specialist": "Market Data Specialist",
        "valuation-accounting-reconciler": "Valuation Accounting Reconciler",
        "ui-ux-page-closer": "UI UX Page Closer",
        "docs-delivery-manager": "Docs Delivery Manager",
        "code-reviewer": "Code Reviewer",
        "qa": "QA",
    }
    for slug, title in expected_roles.items():
        prompt_path = team_dir / "prompts" / f"{slug}.md"
        inbox_path = team_dir / "inbox" / f"{slug}.md"
        outbox_path = team_dir / "outbox" / f"{slug}.md"
        launcher_path = team_dir / "launch" / f"{slug}.ps1"
        workspace_path = team_dir / "workspaces" / slug

        assert prompt_path.exists(), f"missing prompt for {slug}"
        prompt = prompt_path.read_text(encoding="utf-8")
        assert title in prompt
        assert "TEAM_BOARD.md" in prompt
        assert str(inbox_path) in prompt
        assert str(outbox_path) in prompt
        assert str(workspace_path) in prompt
        assert "/mnt/" in prompt
        assert "Role playbook:" in prompt
        assert "Checklist:" in prompt
        assert "Evidence to collect:" in prompt
        assert "Handoff format:" in prompt

        assert inbox_path.exists(), f"missing inbox for {slug}"
        assert outbox_path.exists(), f"missing outbox for {slug}"
        assert launcher_path.exists(), f"missing launcher for {slug}"
        assert workspace_path.exists(), f"missing workspace for {slug}"
        launcher = launcher_path.read_text(encoding="utf-8")
        assert "[Console]::InputEncoding" in launcher
        assert "[Console]::OutputEncoding" in launcher
        assert "run-role.ps1" in launcher
        assert "HermesUbuntu" in launcher
        assert "Backend = 'Wsl'" in launcher
        assert f"Workspace = '{workspace_path}'" in launcher
        assert "DispatchToken =" in launcher
        assert "TaskClaimToken = $TaskClaimToken" in launcher
        assert_powershell_script_parses(launcher_path)

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    role_payload = {role["slug"]: role for role in manifest_payload["roles"]}
    assert role_payload["developer"]["workspace"] == str(
        team_dir / "workspaces" / "developer"
    )
    assert role_payload["frontend-developer"]["workspace"] == str(
        team_dir / "workspaces" / "frontend-developer"
    )
    assert role_payload["frontend-developer"]["backend_workspace"].startswith("/mnt/")
    assert role_payload["developer"]["backend_workspace"].startswith("/mnt/")
    assert manifest_payload["queue"] == str(team_dir / "queue" / "tasks.json")
    assert manifest_payload["dispatch_token"]


def test_luxury_role_prompts_include_domain_specific_playbooks(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "luxury-prompts-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    prompt_dir = output_root / "luxury-prompts-team" / "prompts"
    expected_terms = {
        "lead": ["lane map", "decision log", "stop rule"],
        "product-manager": ["business question", "non-goal", "acceptance criteria"],
        "frontend-developer": ["adapter/model/formatter/selector", "browser verification", "debt:audit"],
        "developer": ["smallest effective implementation", "targeted tests", "no unrelated refactor"],
        "backend-api-contract-engineer": ["result_meta", "route contract", "OpenAPI"],
        "metric-caliber-officer": ["metric_id", "unit", "formal/candidate/excluded"],
        "data-lineage-auditor": ["API response -> adapter/model", "source_version", "fallback/stale"],
        "security-permission-auditor": ["write route", "execute permission", "audit record"],
        "asset-liability-manager": ["asset", "liability", "net position"],
        "pnl-attribution-analyst": ["realized", "unrealized", "residual"],
        "risk-manager": ["DV01", "KRD", "CS01"],
        "fixed-income-analyst": ["duration", "convexity", "spread"],
        "market-data-specialist": ["source_version", "stale", "fallback"],
        "valuation-accounting-reconciler": ["ledger", "514/516/517", "sign convention"],
        "ui-ux-page-closer": ["first-screen conclusion", "no data", "definition pending"],
        "docs-delivery-manager": ["runbook", "acceptance checklist", "final synthesis"],
        "code-reviewer": ["findings first", "file/line", "missing tests"],
        "qa": ["verification matrix", "targeted tests", "failure evidence"],
    }
    for slug, terms in expected_terms.items():
        prompt = (prompt_dir / f"{slug}.md").read_text(encoding="utf-8")
        for term in terms:
            assert term in prompt, f"{slug} prompt missing {term!r}"


def test_windows_backend_launcher_uses_native_hermes(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "windows-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Windows",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout

    launcher = output_root / "windows-team" / "launch" / "lead.ps1"
    text = launcher.read_text(encoding="utf-8")
    assert "wsl.exe" not in text
    assert "run-role.ps1" in text
    assert "Backend = 'Windows'" in text
    assert_powershell_script_parses(launcher)


def test_generated_runner_resumes_session_id(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "resume-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    runner_text = (output_root / "resume-team" / "launch" / "run-role.ps1").read_text(
        encoding="utf-8"
    )
    assert "chat --resume $sessionId" in runner_text
    assert "hermes chat --continue" not in runner_text


def test_roles_argument_limits_seed_and_launch_targets(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "lead-only-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
        "-Roles",
        "lead",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    manifest = (output_root / "lead-only-team" / "manifest.json").read_text(
        encoding="utf-8"
    )
    assert '"selected_roles":' in manifest
    assert '"lead"' in manifest


def test_prepare_only_generates_team_dashboard(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "dashboard-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    dashboard = output_root / "dashboard-team" / "dashboard.html"
    assert dashboard.exists()
    html = dashboard.read_text(encoding="utf-8")
    assert "Agent 团队控制台" in html
    assert "grid-template-columns: repeat(auto-fit" in html
    assert "frontend-developer" in html
    assert "backend-api-contract-engineer" in html
    assert "metric-caliber-officer" in html
    assert "data-lineage-auditor" in html
    assert "security-permission-auditor" in html
    assert "asset-liability-manager" in html
    assert "pnl-attribution-analyst" in html
    assert "risk-manager" in html
    assert "fixed-income-analyst" in html
    assert "market-data-specialist" in html
    assert "valuation-accounting-reconciler" in html
    assert "ui-ux-page-closer" in html
    assert "docs-delivery-manager" in html
    assert "派发任务" in html
    assert "已派发并唤醒" in html
    assert "任务状态" in html
    assert "需要处理" in html
    assert "执行日志" in html
    assert "最近任务" in html
    assert "/api/status" in html
    assert "X-Hermes-Dispatch-Token" not in html
    assert 'href="manifest.json"' not in html
    manifest_payload = json.loads(
        (output_root / "dashboard-team" / "manifest.json").read_text(encoding="utf-8-sig")
    )
    assert manifest_payload["dispatch_token"]
    assert manifest_payload["dispatch_token"] not in html
    assert "data-attention=" in html
    assert "data-dispatch-role" in html
    assert "data-workspace=" in html
    assert "data-queue=" in html
    assert "data-retry=" in html
    assert "/api/dispatch" in html
    assert "/api/retry" in html
    assert "启动派发服务" in html
    for title in [
        "总经理",
        "产品经理",
        "开发工程师",
        "代码审查员",
        "测试/QA",
    ]:
        assert title in html
    assert "dashboard.html" in (
        output_root / "dashboard-team" / "manifest.json"
    ).read_text(encoding="utf-8")


def test_dashboard_renders_existing_outbox_and_session_state(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "dashboard-state-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout

    team_dir = output_root / "dashboard-state-team"
    (team_dir / "outbox" / "lead.md").write_text(
        "# Outbox: Leader\n\nLeader has assigned five lanes.\n",
        encoding="utf-8",
    )
    (team_dir / "sessions" / "lead.txt").write_text(
        "20260607_020304_abcdef\n",
        encoding="utf-8",
    )

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "dashboard-state-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout

    html = (team_dir / "dashboard.html").read_text(encoding="utf-8")
    assert "Leader has assigned five lanes." in html
    assert "20260607_020304_abcdef" in html
    assert "已连接" in html


def test_generated_role_launcher_executes_runner_with_arguments(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "launcher-exec-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
        "-Roles",
        "lead",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    team_dir = output_root / "launcher-exec-team"
    capture = team_dir / "launch" / "capture.txt"
    runner = team_dir / "launch" / "run-role.ps1"
    runner.write_text(
        "\n".join(
            [
                "param(",
                "  [string]$Backend,",
                "  [string]$WslDistro,",
                "  [string]$Workspace,",
                "  [string]$BackendWorkspace,",
                "  [string]$RoleTitle,",
                "  [string]$PromptPath,",
                "  [string]$BackendPromptPath,",
                "  [string]$SessionFile,",
                "  [string]$SessionTitle,",
                "  [string]$AutoTaskId,",
                "  [string]$TaskClaimToken,",
                "  [int]$MaxTurns,",
                "  [string]$HermesCommand,",
                "  [string]$WslCommand,",
                "  [string]$DispatchUrl,",
                "  [string]$DispatchToken",
                ")",
                f"Set-Content -LiteralPath '{capture}' -Value \"$Backend|$RoleTitle|$SessionTitle|$AutoTaskId|$TaskClaimToken|$HermesCommand|$WslCommand|$DispatchUrl|$DispatchToken\" -Encoding UTF8",
            ]
        ),
        encoding="utf-8",
    )

    launched = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(team_dir / "launch" / "lead.ps1"),
            "-AutoTaskId",
            "20260607-101112",
            "-TaskClaimToken",
            "claim-unit-token",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert launched.returncode == 0, launched.stderr + launched.stdout
    captured = capture.read_text(encoding="utf-8-sig").strip()
    parts = captured.split("|")
    assert parts[:8] == [
        "Wsl",
        "Leader",
        "launcher-exec-team/lead",
        "20260607-101112",
        "claim-unit-token",
        "hermes",
        "wsl.exe",
        "http://127.0.0.1:8795",
    ]
    assert parts[8]


def test_seed_sessions_tolerates_native_stderr_when_exit_code_is_zero(tmp_path):
    output_root = tmp_path / "hermes-teams"
    fake_wsl = tmp_path / "fake-wsl.cmd"
    fake_wsl.write_text(
        "\n".join(
            [
                "@echo off",
                "echo diagnostic on stderr 1>&2",
                "echo ROLE_INITIALIZED Leader",
                "echo session_id: 20260607_010203_abcdef",
                "exit /b 0",
            ]
        ),
        encoding="utf-8",
    )

    completed = run_launcher(
        "-PrepareOnly",
        "-SeedSessions",
        "-Roles",
        "lead",
        "-TeamId",
        "stderr-seed-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
        "-WslCommand",
        str(fake_wsl),
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    session_file = output_root / "stderr-seed-team" / "sessions" / "lead.txt"
    assert session_file.read_text(encoding="utf-8-sig").strip() == (
        "20260607_010203_abcdef"
    )


def test_wsl_seed_rename_stays_inside_wsl():
    script = (ROOT / "scripts" / "start-hermes-agent-team.ps1").read_text(
        encoding="utf-8"
    )
    assert "sessions rename $sessionId" in script
    assert "$WslCommand" in script
    assert "$HermesCommand" in script


def test_dispatch_server_launcher_passes_manifest_token():
    script_path = ROOT / "scripts" / "start-hermes-team-dispatch.ps1"
    script = script_path.read_text(encoding="utf-8")

    assert "dispatch_token" in script
    assert "--token $dispatchToken" in script
    assert "must bind to loopback only" in script
    assert "Regenerate the team" in script
    assert_powershell_script_parses(script_path)


def test_finance_audit_cluster_wrapper_generates_specialized_team(tmp_path):
    output_root = tmp_path / "hermes-teams"

    completed = run_finance_cluster(
        "-PrepareOnly",
        "-TeamId",
        "finance-cluster-unit",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Windows",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    team_dir = output_root / "finance-cluster-unit"
    board = (team_dir / "TEAM_BOARD.md").read_text(encoding="utf-8-sig")
    manifest = json.loads((team_dir / "manifest.json").read_text(encoding="utf-8-sig"))

    assert "MOSS V3 金融系统审计员工集群" in board
    assert "固收口径优先" in board
    assert "外币债券是否已折人民币" in board
    assert "market_value 是 clean 还是 dirty" in board
    assert "固收分析师" in board
    assert manifest["cluster_profile"] == "moss_finance_audit"
    assert "fixed_income_p0" in manifest["audit_focus"]
    assert manifest["dispatch_manual"].endswith("docs\\hermes-finance-audit-cluster.md")

    expected_roles = {
        "lead",
        "product-manager",
        "metric-caliber-officer",
        "data-lineage-auditor",
        "fixed-income-analyst",
        "asset-liability-manager",
        "valuation-accounting-reconciler",
        "pnl-attribution-analyst",
        "risk-manager",
        "market-data-specialist",
        "backend-api-contract-engineer",
        "developer",
        "frontend-developer",
        "ui-ux-page-closer",
        "security-permission-auditor",
        "code-reviewer",
        "qa",
        "docs-delivery-manager",
    }
    assert set(manifest["selected_roles"]) == expected_roles
    for role in expected_roles:
        assert (team_dir / "prompts" / f"{role}.md").exists()
        assert (team_dir / "inbox" / f"{role}.md").exists()
        assert (team_dir / "outbox" / f"{role}.md").exists()

    fixed_income_inbox = (team_dir / "inbox" / "fixed-income-analyst.md").read_text(
        encoding="utf-8-sig"
    )
    assert "clean/dirty market_value" in fixed_income_inbox
    assert "DV01 CNY/1bp" in fixed_income_inbox
    assert "不猜指标口径" in fixed_income_inbox
    assert_powershell_script_parses(ROOT / "scripts" / "start-moss-finance-audit-cluster.ps1")


def test_finance_audit_cluster_wrapper_passes_roles_as_one_argument(tmp_path):
    completed = run_finance_cluster(
        "-PrepareOnly",
        "-TeamId",
        "finance-role-argument-unit",
        "-Backend",
        "Windows",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    team_dir = ROOT / ".omx" / "hermes-teams" / "finance-role-argument-unit"
    try:
        assert (team_dir / "manifest.json").exists()
        assert not (ROOT / "product-manager" / "finance-role-argument-unit").exists()
        manifest = json.loads((team_dir / "manifest.json").read_text(encoding="utf-8-sig"))
        assert "product-manager" in manifest["selected_roles"]
    finally:
        if team_dir.exists():
            resolved = team_dir.resolve()
            allowed_root = (ROOT / ".omx" / "hermes-teams").resolve()
            assert resolved.is_relative_to(allowed_root)
            shutil.rmtree(resolved)


def assert_powershell_script_parses(path: Path):
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "$tokens=$null; $errs=$null; "
                f"$null=[System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$tokens,[ref]$errs); "
                "if($errs.Count){ $errs | ForEach-Object { $_.Message }; exit 1 }"
            ),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
