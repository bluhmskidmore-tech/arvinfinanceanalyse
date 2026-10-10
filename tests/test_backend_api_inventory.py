from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
import subprocess
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_SCRIPT = ROOT / "scripts" / "backend_api_inventory.py"
BASELINE_DIR = ROOT / "contracts" / "openapi"
OPENAPI_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})

# Endpoint and method counts used to be asserted as literals here, which meant the
# test flagged "the number moved" rather than "the contract moved" -- adding and
# deleting an endpoint looked identical, and both were fixed by editing the number.
# Those counts are now derived from the committed OpenAPI baseline, whose own diff
# gate (scripts/api_contract_check.py baseline-check) distinguishes the two.
# What stays pinned by name here is the registry-to-router correspondence.


@lru_cache(maxsize=None)
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


@lru_cache(maxsize=None)
def _baseline_spec(surface: str) -> dict:
    return json.loads((BASELINE_DIR / f"openapi.{surface}.json").read_text(encoding="utf-8"))


def _baseline_operations(surface: str) -> set[tuple[str, str]]:
    paths = _baseline_spec(surface)["paths"]
    return {
        (method.upper(), path)
        for path, path_item in paths.items()
        for method in path_item
        if method in OPENAPI_METHODS
    }


def _inventory_operations(payload: dict) -> set[tuple[str, str]]:
    return {(operation["method"], operation["path"]) for operation in payload["operations"]}


def _assert_summary_is_self_consistent(payload: dict) -> None:
    operations = payload["operations"]
    summary = payload["summary"]

    assert summary["operation_count"] == len(operations)
    assert summary["unique_path_count"] == len({operation["path"] for operation in operations})
    assert summary["method_counts"] == dict(sorted(Counter(op["method"] for op in operations).items()))
    assert summary["group_counts"] == dict(sorted(Counter(op["route_group"] for op in operations).items()))
    # A registry entry that stops contributing routes would otherwise vanish silently.
    assert summary["registry_entry_count"] == len({operation["registry_name"] for operation in operations})


def test_default_inventory_matches_release_default_surface() -> None:
    payload = json.loads(_run_inventory(surface="default"))

    assert payload["surface"] == "default"
    assert payload["effective_feature_flags"]["MOSS_AGENT_ENABLED"] is False
    assert not any(operation["path"].startswith("/api/agent") for operation in payload["operations"])
    _assert_summary_is_self_consistent(payload)


def test_full_inventory_covers_all_known_routes_and_required_fields() -> None:
    payload = json.loads(_run_inventory(surface="full"))
    operations = payload["operations"]

    assert payload["surface"] == "full"
    assert payload["effective_feature_flags"]["MOSS_AGENT_ENABLED"] is True
    _assert_summary_is_self_consistent(payload)

    assert len(_inventory_operations(payload)) == len(operations), "duplicate method/path pair in the inventory"
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


def test_inventory_surfaces_agree_with_the_committed_openapi_baseline() -> None:
    """The inventory is a view over the OpenAPI contract, not an independent count.

    Both are generated from the same route registry, so any disagreement means one
    of the two generators drifted rather than that the API changed.
    """
    for surface in ("default", "full"):
        payload = json.loads(_run_inventory(surface=surface))
        assert _inventory_operations(payload) == _baseline_operations(surface), (
            f"inventory and contracts/openapi/openapi.{surface}.json disagree; "
            "regenerate both with backend_api_inventory.py and api_contract_check.py baseline-update"
        )


def test_enabling_the_agent_flag_adds_exactly_the_agent_router() -> None:
    """The full surface is the default surface plus the feature-gated agent entry."""
    default_payload = json.loads(_run_inventory(surface="default"))
    full_payload = json.loads(_run_inventory(surface="full"))

    default_operations = _inventory_operations(default_payload)
    full_operations = _inventory_operations(full_payload)
    agent_operations = {
        (operation["method"], operation["path"])
        for operation in full_payload["operations"]
        if operation["registry_name"] == "agent"
    }

    assert default_operations < full_operations
    assert full_operations - default_operations == agent_operations
    registry_names = {operation["registry_name"] for operation in full_payload["operations"]}
    assert registry_names - {operation["registry_name"] for operation in default_payload["operations"]} == {"agent"}


def test_full_inventory_marks_nested_agent_workspace_without_duplicate_registry_entry() -> None:
    payload = json.loads(_run_inventory(surface="full"))
    agent_operations = [operation for operation in payload["operations"] if operation["path"].startswith("/api/agent")]

    assert agent_operations
    assert any(operation["path"] == "/api/agent/projects" for operation in agent_operations)
    assert any(
        operation["handler_module"] == "backend.app.api.routes.agent_workspace" for operation in agent_operations
    )
    assert {operation["registry_name"] for operation in agent_operations} == {"agent"}
    assert {operation["route_group"] for operation in agent_operations} == {"agent_experimental"}
    assert all(operation["feature_flag"] == "MOSS_AGENT_ENABLED" for operation in agent_operations)
    assert all(operation["registration"] == "feature_gated" for operation in agent_operations)


def test_only_the_agent_registry_entry_is_feature_gated() -> None:
    payload = json.loads(_run_inventory(surface="full"))
    gated = {
        operation["registry_name"]
        for operation in payload["operations"]
        if operation["registration"] == "feature_gated"
    }

    assert gated == {"agent"}
    assert all(
        operation["feature_flag"] == ""
        for operation in payload["operations"]
        if operation["registry_name"] != "agent"
    )


def test_json_csv_and_markdown_formats_report_the_same_full_surface() -> None:
    json_payload = json.loads(_run_inventory(surface="full", output_format="json"))
    csv_rows = list(csv.DictReader(io.StringIO(_run_inventory(surface="full", output_format="csv"))))
    markdown = _run_inventory(surface="full", output_format="markdown")
    summary = json_payload["summary"]

    assert len(csv_rows) == summary["operation_count"]
    assert {"method", "path", "route_group", "registry_name", "owner"} <= set(csv_rows[0])
    assert {(row["method"], row["path"]) for row in csv_rows} == _inventory_operations(json_payload)

    assert "- Surface: `full`" in markdown
    assert f"- Operations: **{summary['operation_count']}**" in markdown
    for group, count in summary["group_counts"].items():
        assert f"| `{group}` | {count} |" in markdown


def test_markdown_reports_the_declared_success_schema_and_never_the_validation_error() -> None:
    """The success column must come from the 2xx body, not from the 422 envelope."""
    json_payload = json.loads(_run_inventory(surface="full", output_format="json"))
    markdown = _run_inventory(surface="full", output_format="markdown")

    operation = next(
        operation
        for operation in json_payload["operations"]
        if operation["path"] == "/api/analysis/adb" and operation["method"] == "GET"
    )
    row = next(line for line in markdown.splitlines() if line.startswith("| GET | /api/analysis/adb |"))

    expected = f"| {operation['request_schema'] or '(none)'} | {operation['response_schema'] or '(none)'} |"
    assert expected in row
    assert "HTTPValidationError" not in row
    assert "HTTPValidationError" not in operation["response_schema"]


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

    assert default_payload["summary"]["operation_count"] < full_payload["summary"]["operation_count"]
    assert default_again == default_payload, "a preceding full-surface load leaked into the default surface"


def test_inventory_surface_ignores_the_ambient_agent_flag() -> None:
    """A developer's local config/.env must not change what the inventory reports."""
    outputs = []
    for ambient in ("false", "true"):
        completed = subprocess.run(
            [
                sys.executable,
                str(INVENTORY_SCRIPT),
                "--surface",
                "default",
                "--format",
                "json",
                "--output",
                "-",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            env={**os.environ, "MOSS_AGENT_ENABLED": ambient},
        )
        outputs.append(completed.stdout)

    assert outputs[0] == outputs[1]
