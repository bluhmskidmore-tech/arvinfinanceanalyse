from __future__ import annotations

import json
import re
from pathlib import Path

import tomllib

from tests.helpers import load_module

ROOT = Path(__file__).resolve().parents[1]


def test_supply_chain_security_assets_exist():
    expected = [
        ROOT / ".gitleaks.toml",
        ROOT / "scripts" / "supply_chain_security_scan.py",
        ROOT / "scripts" / "osv_reconciliation_gate.py",
        ROOT / "docs" / "SUPPLY_CHAIN_SECURITY_SCANNING.md",
        ROOT / "docs" / "audits" / "osv-reconciliation-records.json",
    ]

    missing = [str(path) for path in expected if not path.exists()]
    assert not missing, "Missing expected supply-chain security assets:\n" + "\n".join(
        missing
    )


def test_gitleaks_config_extends_defaults_without_tracked_source_snapshot_allowlist():
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))

    assert config["extend"]["useDefault"] is True
    assert "disabledRules" not in config["extend"]

    allowlist_paths = "\n".join(
        path_pattern
        for allowlist in config.get("allowlists", [])
        for path_pattern in allowlist.get("paths", [])
    )

    assert "audit_pack/source_snapshot" not in allowlist_paths
    assert ".codex-tmp" in allowlist_paths
    assert ".omx" in allowlist_paths
    assert "data" in allowlist_paths
    assert "dist" in allowlist_paths
    assert "frontend/dist" in allowlist_paths
    assert "node_modules" in allowlist_paths
    assert ".venv" in allowlist_paths
    assert ".playwright-mcp" in allowlist_paths
    assert "test_output" in allowlist_paths
    assert "backend/app" not in allowlist_paths
    assert "frontend/src" not in allowlist_paths

    allowlist_regexes = "\n".join(
        regex
        for allowlist in config.get("allowlists", [])
        for regex in allowlist.get("regexes", [])
    )
    assert "regulatory_dv01" in allowlist_regexes
    assert "dominant_krd_bucket" in allowlist_regexes
    assert "cache_key" in allowlist_regexes
    assert "idempotency_key" in allowlist_regexes
    assert "candidate_idempotency_key" in allowlist_regexes
    assert "readiness_evidence_key" in allowlist_regexes
    assert "evidence_pack_key" in allowlist_regexes
    assert "apiKey" not in allowlist_regexes


def test_legacy_source_snapshot_is_removed_from_the_repository():
    assert not (ROOT / "audit_pack" / "source_snapshot").exists()


def test_mypy_source_digest_allowlist_requires_exact_file_rule_and_field_format():
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
    allowlist = next(
        entry
        for entry in config["allowlists"]
        if entry.get("targetRules") == ["generic-api-key"]
    )
    assert allowlist["condition"] == "AND"
    assert allowlist["regexTarget"] == "line"
    assert len(allowlist["paths"]) == 1
    assert len(allowlist["regexes"]) == 14
    path_pattern = re.compile(allowlist["paths"][0])
    field_patterns = [re.compile(pattern) for pattern in allowlist["regexes"]]

    def matches_field(line):
        return any(pattern.fullmatch(line) for pattern in field_patterns)

    assert path_pattern.fullmatch("scripts/mypy_baseline.json")
    assert path_pattern.fullmatch(r"scripts\mypy_baseline.json")
    assert not path_pattern.fullmatch("scripts/other.json")
    baseline = json.loads((ROOT / "scripts/mypy_baseline.json").read_text(encoding="utf-8"))
    source = "backend/app/agent/runtime/action_token.py"
    historical_digest = baseline["_meta"]["origin"]["sources_sha256"][source]
    assert matches_field(f'        "{source}": "{historical_digest}",\n')
    digest = "0123456789abcdef" * 4
    for field in ("api_key", "token", "scripts/api_key.py", f"{source}.bak"):
        assert not matches_field(f'        "{field}": "{digest}",\n')
    for value in (digest[:-1], f"synthetic_{digest}"):
        assert not matches_field(f'        "{source}": "{value}",\n')
    assert not matches_field(f'        "{source}": "{digest}",\n')


def test_supply_chain_scan_dry_run_emits_expected_plan(capsys):
    module = load_module(
        "scripts.supply_chain_security_scan",
        "scripts/supply_chain_security_scan.py",
    )

    exit_code = module.main(["--dry-run"])

    assert exit_code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["default_tool"] == "all"
    assert plan["gitleaks"]["config"] == ".gitleaks.toml"
    assert plan["gitleaks"]["report_path"].endswith("gitleaks-report.json")
    assert plan["gitleaks"]["command"][:4] == [
        "gitleaks",
        "dir",
        ".",
        "--config",
    ]
    assert "--report-format" in plan["gitleaks"]["command"]
    assert "--report-path" in plan["gitleaks"]["command"]
    assert plan["osv"]["lockfiles"] == [
        "backend/uv.lock",
        "frontend/package-lock.json",
    ]
    assert plan["osv"]["report_path"].endswith("osv-report.json")
    assert plan["osv"]["command"][:3] == ["osv-scanner", "scan", "source"]
    assert any(
        argument == "--lockfile=backend/uv.lock" for argument in plan["osv"]["command"]
    )
    assert any(
        argument == "--lockfile=frontend/package-lock.json"
        for argument in plan["osv"]["command"]
    )
    assert "backend/pyproject.toml" in plan["notes"]["unsupported_manifest_context"]


def test_supply_chain_scan_fails_clearly_when_tools_are_missing(monkeypatch, capsys):
    module = load_module(
        "scripts.supply_chain_security_scan",
        "scripts/supply_chain_security_scan.py",
    )

    monkeypatch.setattr(module.shutil, "which", lambda executable: None)

    exit_code = module.main([])

    assert exit_code == 2
    stderr = capsys.readouterr().err
    assert "Missing required executable(s): gitleaks, osv-scanner" in stderr


def test_supply_chain_scan_runs_selected_tool_with_expected_command(
    monkeypatch, tmp_path
):
    module = load_module(
        "scripts.supply_chain_security_scan",
        "scripts/supply_chain_security_scan.py",
    )

    monkeypatch.setattr(
        module.shutil, "which", lambda executable: f"C:/tools/{executable}.exe"
    )
    calls: list[dict[str, object]] = []

    def _fake_run(args, **kwargs):
        calls.append(
            {
                "args": list(args),
                "cwd": str(kwargs.get("cwd")),
            }
        )
        return module.subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    exit_code = module.main(["--tool", "osv", "--report-dir", str(tmp_path)])

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["cwd"] == str(ROOT)
    assert calls[0]["args"][:3] == ["osv-scanner", "scan", "source"]
    assert "--lockfile=backend/uv.lock" in calls[0]["args"]
    assert "--lockfile=frontend/package-lock.json" in calls[0]["args"]
    assert f"--output={(tmp_path / 'osv-report.json').as_posix()}" in calls[0]["args"]


def test_ci_wires_secret_and_osv_scans():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    gate = (ROOT / "scripts" / "osv_reconciliation_gate.py").read_text(encoding="utf-8")

    assert "name: Secret Scan" in workflow
    assert "python scripts/supply_chain_security_scan.py --tool gitleaks" in workflow
    assert "gitleaks-report" in workflow
    assert "name: OSV Dependency Scan" in workflow
    assert "needs: frontend" in workflow
    assert "releases/download/v2.3.0/osv-scanner_linux_amd64" in workflow
    assert (
        "e774e5770c31d60745c067be5f69bf3b46641b6d0e0ed87fd65e569cda35dc50" in workflow
    )
    assert "continue-on-error: true" in workflow
    assert "python scripts/osv_reconciliation_gate.py scan" in workflow
    assert "python scripts/osv_reconciliation_gate.py evaluate" in workflow
    assert "--scanner /tmp/osv-scanner" in workflow
    assert "--scan-receipt test_output/security-scans/osv-scan-receipt.json" in workflow
    assert "steps.osv_raw.outcome" not in workflow
    assert "test_output/security-scans/osv-adjudication.json" in workflow
    assert "test_output/security-scans/osv-report.json" in workflow
    assert "test_output/security-scans/osv-scan-receipt.json" in workflow
    assert (
        'EXPECTED_LOCKFILES = ("backend/uv.lock", "frontend/package-lock.json")' in gate
    )
    assert "google/osv-scanner-action/osv-reporter-action@" in workflow
    assert "IgnoredVulns" not in workflow
    assert "--ignore-vulns" not in workflow
