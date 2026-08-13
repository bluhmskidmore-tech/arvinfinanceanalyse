from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPECTRAL_RULESET = ROOT / ".spectral.yaml"
SPECTRAL_IGNORE = ROOT / ".spectralignore"
OPENAPI_SCRIPT = ROOT / "scripts" / "api_contract_check.py"
DOCS = ROOT / "docs" / "API_CONTRACT_TOOLING.md"


def _run_script(*args: str) -> str:
    completed = subprocess.run(
        [sys.executable, str(OPENAPI_SCRIPT), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.stdout


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

    payload = json.loads(_run_script("export-openapi", "--output", "-"))
    assert payload["openapi"].startswith("3.")
    assert payload["info"]["title"] == "MOSS Agent Analytics OS"
    assert "/health/live" in payload["paths"]


def test_export_defaults_to_the_release_surface_and_can_widen_to_the_full_one() -> None:
    """Without a pinned surface the export would follow the developer's config/.env."""
    default_payload = json.loads(_run_script("export-openapi", "--surface", "default", "--output", "-"))
    full_payload = json.loads(_run_script("export-openapi", "--surface", "full", "--output", "-"))

    assert json.loads(_run_script("export-openapi", "--output", "-")) == default_payload
    assert not [path for path in default_payload["paths"] if path.startswith("/api/agent")]
    assert [path for path in full_payload["paths"] if path.startswith("/api/agent")]
    assert set(default_payload["paths"]) < set(full_payload["paths"])


def test_exported_openapi_operation_ids_are_unique() -> None:
    payload = json.loads(_run_script("export-openapi", "--output", "-"))
    operation_ids = [
        operation["operationId"]
        for path_item in payload["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert len(operation_ids) == len(set(operation_ids))


def test_api_contract_script_prints_offline_schemathesis_command() -> None:
    command = _run_script("schemathesis-command").strip()

    assert command.startswith("schemathesis run ")
    # Schemathesis 4.x dropped `--app`; the printed command must stay runnable.
    assert "--app" not in command
    assert "--url" in command
    assert ".codex-tmp/openapi.json" in command


def _schemathesis_executable() -> str | None:
    """Prefer the CLI installed beside the interpreter running the tests."""
    scripts_dir = Path(sys.executable).parent
    for candidate in (scripts_dir / "schemathesis.exe", scripts_dir / "schemathesis"):
        if candidate.exists():
            return str(candidate)
    return shutil.which("schemathesis")


def test_printed_schemathesis_command_passes_option_validation() -> None:
    """Every token must be an option Schemathesis still recognises.

    Pointed at a path that does not exist, the CLI should complain about the file
    rather than about an unknown option; `--app` used to fail here.
    """
    executable = _schemathesis_executable()
    if executable is None:
        pytest.skip("schemathesis CLI is not installed")

    tokens = _run_script("schemathesis-command").strip().split()
    assert tokens[0] == "schemathesis"
    command = [executable, *tokens[1:]]
    command = [token if token != ".codex-tmp/openapi.json" else ".codex-tmp/no-such-spec.json" for token in command]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr

    assert "No such option" not in output, output
    assert "does not exist" in output, output


def test_ci_runs_api_contract_export_lint_and_breaking_change_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "name: API Contract" in workflow
    assert (
        "python scripts/api_contract_check.py export-openapi --surface default --output .codex-tmp/openapi.json"
        in workflow
    )
    assert "npx --prefix frontend spectral lint .codex-tmp/openapi.json -r .spectral.yaml" in workflow
    # The gate must read the baseline from the base branch, not from the pull request.
    assert 'python scripts/api_contract_check.py baseline-check \\\n            --baseline-ref "origin/${{ github.base_ref }}"' in workflow


def test_docs_describe_the_baseline_workflow_and_current_tool_versions() -> None:
    text = DOCS.read_text(encoding="utf-8")

    assert "baseline-update" in text
    assert "baseline-check" in text
    assert "breaking-change-acknowledgements.json" in text
    # The boundary note used to justify excluding Schemathesis with "this backend
    # pins pytest<9"; backend/pyproject.toml now requires pytest>=9.0.3,<10.
    assert "this backend pins" not in text
    assert "pytest>=9.0.3,<10" in text
    assert "--app=backend.app.main:app" not in text
