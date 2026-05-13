from __future__ import annotations

import json
import tomllib
from pathlib import Path

from tests.helpers import load_module


ROOT = Path(__file__).resolve().parents[1]


def test_supply_chain_security_assets_exist():
    expected = [
        ROOT / ".gitleaks.toml",
        ROOT / "scripts" / "supply_chain_security_scan.py",
        ROOT / "docs" / "SUPPLY_CHAIN_SECURITY_SCANNING.md",
    ]

    missing = [str(path) for path in expected if not path.exists()]
    assert not missing, "Missing expected supply-chain security assets:\n" + "\n".join(missing)


def test_gitleaks_config_extends_defaults_with_narrow_generated_artifact_allowlists():
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))

    assert config["extend"]["useDefault"] is True
    assert "disabledRules" not in config["extend"]

    allowlist_paths = "\n".join(
        path_pattern
        for allowlist in config.get("allowlists", [])
        for path_pattern in allowlist.get("paths", [])
    )

    assert "audit_pack/source_snapshot" in allowlist_paths
    assert "node_modules" in allowlist_paths
    assert ".venv" in allowlist_paths
    assert ".playwright-mcp" in allowlist_paths
    assert "test_output" in allowlist_paths
    assert "backend/app" not in allowlist_paths
    assert "frontend/src" not in allowlist_paths


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
        argument == "--lockfile=backend/uv.lock"
        for argument in plan["osv"]["command"]
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


def test_supply_chain_scan_runs_selected_tool_with_expected_command(monkeypatch, tmp_path):
    module = load_module(
        "scripts.supply_chain_security_scan",
        "scripts/supply_chain_security_scan.py",
    )

    monkeypatch.setattr(module.shutil, "which", lambda executable: f"C:/tools/{executable}.exe")
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

    assert "name: Secret Scan" in workflow
    assert "python scripts/supply_chain_security_scan.py --tool gitleaks" in workflow
    assert "gitleaks-report" in workflow
    assert "name: OSV Dependency Scan" in workflow
    assert "google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@v2.3.0" in workflow
    assert "--lockfile=backend/uv.lock" in workflow
    assert "--lockfile=frontend/package-lock.json" in workflow
