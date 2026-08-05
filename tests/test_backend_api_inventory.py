from __future__ import annotations

import csv
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_SCRIPT = ROOT / "scripts" / "backend_api_inventory.py"


def _run_inventory(*, surface: str, output_format: str = "json") -> str:
    completed = subprocess.run(
        [
            sys.executable,
            str(INVENTORY_SCRIPT),
            "--surface",
            surface,
            "--format",
            output_format,
            "--output",
            "-",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.stdout


def test_default_inventory_matches_release_default_surface() -> None:
    payload = json.loads(_run_inventory(surface="default"))

    assert payload["surface"] == "default"
    assert payload["effective_feature_flags"]["MOSS_AGENT_ENABLED"] is False
    assert payload["summary"]["registry_entry_count"] == 33
    assert payload["summary"]["operation_count"] == 246
    assert payload["summary"]["unique_path_count"] == 239
    assert not any(operation["path"].startswith("/api/agent") for operation in payload["operations"])


def test_full_inventory_covers_all_known_routes_and_required_fields() -> None:
    payload = json.loads(_run_inventory(surface="full"))
    operations = payload["operations"]

    assert payload["surface"] == "full"
    assert payload["effective_feature_flags"]["MOSS_AGENT_ENABLED"] is True
    assert payload["summary"]["registry_entry_count"] == 34
    assert payload["summary"]["operation_count"] == 263
    assert payload["summary"]["unique_path_count"] == 252
    assert payload["summary"]["method_counts"] == {
        "DELETE": 1,
        "GET": 210,
        "PATCH": 1,
        "POST": 49,
        "PUT": 2,
    }
    assert len({(operation["method"], operation["path"]) for operation in operations}) == 263
    assert operations == sorted(
        operations,
        key=lambda row: (row["path"], row["method"], row["registry_name"]),
    )

    required_fields = {
        "method",
        "path",
        "operation_id",
        "registry_name",
        "route_group",
        "owner",
        "handler_module",
        "handler",
        "tags",
        "action_class",
        "registration",
    }
    assert required_fields <= operations[0].keys()
    assert all(operation["surface"] == "full" for operation in operations)
    assert all(operation["operation_id"] for operation in operations)
    assert all(operation["owner"] for operation in operations)


def test_full_inventory_marks_nested_agent_workspace_without_duplicate_registry_entry() -> None:
    payload = json.loads(_run_inventory(surface="full"))
    agent_operations = [operation for operation in payload["operations"] if operation["path"].startswith("/api/agent")]

    assert len(agent_operations) == 17
    assert any(operation["path"] == "/api/agent/projects" for operation in agent_operations)
    assert any(
        operation["handler_module"] == "backend.app.api.routes.agent_workspace" for operation in agent_operations
    )
    assert {operation["registry_name"] for operation in agent_operations} == {"agent"}
    assert all(operation["feature_flag"] == "MOSS_AGENT_ENABLED" for operation in agent_operations)


def test_json_csv_and_markdown_formats_report_the_same_full_surface() -> None:
    json_payload = json.loads(_run_inventory(surface="full", output_format="json"))
    csv_rows = list(csv.DictReader(io.StringIO(_run_inventory(surface="full", output_format="csv"))))
    markdown = _run_inventory(surface="full", output_format="markdown")

    assert len(csv_rows) == json_payload["summary"]["operation_count"] == 263
    assert {"method", "path", "route_group", "registry_name", "owner"} <= set(csv_rows[0])
    assert "- Surface: `full`" in markdown
    assert "- Operations: **263**" in markdown
    assert "| `agent_experimental` | 17 |" in markdown
    adb_line = next(line for line in markdown.splitlines() if line.startswith("| GET | /api/analysis/adb |"))
    assert "| (none) | unspecified_success |" in adb_line
    assert "HTTPValidationError" not in adb_line


def test_surface_switching_is_isolated_in_one_process() -> None:
    spec = importlib.util.spec_from_file_location(
        "backend_api_inventory_under_test",
        INVENTORY_SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    default_payload = module._load_inventory("default")
    full_payload = module._load_inventory("full")
    default_again = module._load_inventory("default")

    assert default_payload["summary"]["operation_count"] == 246
    assert full_payload["summary"]["operation_count"] == 263
    assert default_again["summary"]["operation_count"] == 246
