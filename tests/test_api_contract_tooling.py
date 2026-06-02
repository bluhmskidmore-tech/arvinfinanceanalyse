from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPECTRAL_RULESET = ROOT / ".spectral.yaml"
SPECTRAL_IGNORE = ROOT / ".spectralignore"
OPENAPI_SCRIPT = ROOT / "scripts" / "api_contract_check.py"


def test_spectral_ruleset_extends_oas_and_targets_local_openapi() -> None:
    assert SPECTRAL_RULESET.exists(), "Expected Spectral ruleset at repo root"
    text = SPECTRAL_RULESET.read_text(encoding="utf-8")

    assert "extends:" in text
    assert "spectral:oas" in text
    assert "operation-operationId" in text
    assert "operation-description: off" in text
    assert "operation-tags" in text
    assert "path-params" in text


def test_spectral_ignore_excludes_generated_or_archived_inputs_only() -> None:
    assert SPECTRAL_IGNORE.exists(), "Expected .spectralignore for noisy non-source inputs"
    lines = {
        line.strip()
        for line in SPECTRAL_IGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "audit_pack/**" in lines
    assert "backend/data/**" in lines


def test_api_contract_script_exports_openapi_locally() -> None:
    assert OPENAPI_SCRIPT.exists(), "Expected local API contract helper script"

    completed = subprocess.run(
        [
            sys.executable,
            str(OPENAPI_SCRIPT),
            "export-openapi",
            "--output",
            "-",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["openapi"].startswith("3.")
    assert payload["info"]["title"] == "MOSS Agent Analytics OS"
    assert "/health/live" in payload["paths"]


def test_exported_openapi_operation_ids_are_unique() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(OPENAPI_SCRIPT),
            "export-openapi",
            "--output",
            "-",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    payload = json.loads(completed.stdout)
    operation_ids = [
        operation["operationId"]
        for path_item in payload["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert len(operation_ids) == len(set(operation_ids))


def test_api_contract_script_prints_offline_schemathesis_command() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(OPENAPI_SCRIPT),
            "schemathesis-command",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    command = completed.stdout.strip()
    assert "schemathesis run" in command
    assert "--app=backend.app.main:app" in command
    assert "/openapi.json" in command


def test_ci_runs_api_contract_export_and_spectral_lint() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "name: API Contract" in workflow
    assert "python scripts/api_contract_check.py export-openapi --output .codex-tmp/openapi.json" in workflow
    assert "npx --prefix frontend spectral lint .codex-tmp/openapi.json -r .spectral.yaml" in workflow
