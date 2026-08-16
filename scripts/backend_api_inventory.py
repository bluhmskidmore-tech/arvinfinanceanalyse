from __future__ import annotations

import argparse
import csv
import importlib
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api_surface import (  # noqa: E402
    REGISTRY_FEATURE_FLAGS,
    SURFACE_CHOICES,
    SURFACE_HELP,
    surface_environment,
)

HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"})
CSV_FIELDS = (
    "surface",
    "method",
    "path",
    "operation_id",
    "operation_id_source",
    "registry_name",
    "route_group",
    "route_group_label",
    "owner",
    "namespace",
    "action_class",
    "registration",
    "feature_flag",
    "handler_module",
    "handler",
    "route_name",
    "tags",
    "request_schema",
    "response_schema",
    "response_statuses",
    "parameters",
    "response_model",
    "dependencies",
    "auth_dependencies",
    "auth_dependency_present",
    "write_candidate",
    "include_in_schema",
    "deprecated",
    "claim_boundary",
    "risk_boundary",
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a deterministic backend API inventory from the FastAPI route registry and its OpenAPI contract."
        )
    )
    parser.add_argument(
        "--surface",
        choices=SURFACE_CHOICES,
        default="default",
        help=SURFACE_HELP,
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv", "markdown"),
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )
    return parser


def _qualified_name(value: object | None) -> str:
    if value is None:
        return ""
    module = getattr(value, "__module__", "")
    qualname = getattr(value, "__qualname__", getattr(value, "__name__", ""))
    if module and qualname:
        return f"{module}.{qualname}"
    return str(value).replace("typing.", "")


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _schema_label(schema: object) -> str:
    if not isinstance(schema, dict) or not schema:
        return ""
    reference = schema.get("$ref")
    if isinstance(reference, str):
        return reference.rsplit("/", maxsplit=1)[-1]

    schema_type = schema.get("type")
    if schema_type == "array":
        return f"array[{_schema_label(schema.get('items', {})) or 'unknown'}]"
    if isinstance(schema_type, str):
        return schema_type

    for combinator in ("anyOf", "oneOf", "allOf"):
        choices = schema.get(combinator)
        if isinstance(choices, list):
            labels = [_schema_label(choice) or "unknown" for choice in choices]
            return f"{combinator}[{', '.join(labels)}]"

    return json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_schema_label(container: object) -> str:
    if not isinstance(container, dict):
        return ""
    content = container.get("content")
    if not isinstance(content, dict) or not content:
        return ""

    media = content.get("application/json")
    if not isinstance(media, dict):
        media = next((value for value in content.values() if isinstance(value, dict)), None)
    if not isinstance(media, dict):
        return ""
    return _schema_label(media.get("schema", {}))


def _primary_response_schema(operation: dict[str, Any]) -> tuple[str, list[str]]:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return "", []

    statuses = sorted(str(status) for status in responses)
    preferred = [status for status in statuses if status.isdigit() and 200 <= int(status) < 300]
    for status in preferred:
        label = _content_schema_label(responses.get(status))
        if label:
            return label, statuses
    if preferred:
        return (
            "no_content" if preferred == ["204"] else "unspecified_success",
            statuses,
        )

    for status in statuses:
        label = _content_schema_label(responses.get(status))
        if label:
            return label, statuses
    return "", statuses


def _parameter_labels(operation: dict[str, Any]) -> list[str]:
    parameters = operation.get("parameters")
    if not isinstance(parameters, list):
        return []

    labels: list[str] = []
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        location = str(parameter.get("in", "unknown"))
        name = str(parameter.get("name", "unknown"))
        required = "*" if parameter.get("required") else ""
        labels.append(f"{location}:{name}{required}")
    return labels


def _dependency_names(route: Any) -> list[str]:
    names: list[str] = []
    visited: set[int] = set()

    def visit(dependant: object) -> None:
        identity = id(dependant)
        if identity in visited:
            return
        visited.add(identity)
        for child in getattr(dependant, "dependencies", ()):
            names.append(_qualified_name(getattr(child, "call", None)))
            visit(child)

    visit(route.dependant)
    return _dedupe(names)


def _namespace(path: str) -> str:
    if path == "/api" or path.startswith("/api/"):
        return "api"
    if path == "/ui" or path.startswith("/ui/"):
        return "ui"
    if path == "/health" or path.startswith("/health/"):
        return "health"
    return "other"


def _action_class(method: str, path: str, handler: str) -> str:
    lowered_path = path.lower()
    lowered_handler = handler.lower()

    if "/export" in lowered_path:
        return "export"
    if lowered_path.endswith("/events"):
        return "stream"
    if "status" in lowered_path:
        return "status"
    if "manual-adjustments" in lowered_path:
        return "manual_adjustment_read" if method == "GET" else "manual_adjustment"
    if method == "GET":
        return "read"
    if method == "DELETE":
        return "delete"
    if method in {"PUT", "PATCH"}:
        return "update"
    if lowered_path.endswith("/query") or lowered_handler.startswith("query_"):
        return "query"
    if "refresh" in lowered_path or "refresh" in lowered_handler:
        return "refresh"
    if "backfill" in lowered_path or "backfill" in lowered_handler:
        return "backfill"
    if "ingest" in lowered_path or "ingest" in lowered_handler:
        return "ingest"
    if "/import" in lowered_path or "import_" in lowered_handler:
        return "import"
    if any(token in lowered_path or token in lowered_handler for token in ("rebuild", "recalc", "revalidate")):
        return "recompute"
    if lowered_handler.startswith("create_"):
        return "create"
    return "workflow_command"


def _response_model_name(route: Any) -> str:
    response_model = getattr(route, "response_model", None)
    return _qualified_name(response_model)


def _load_inventory(surface: str) -> dict[str, Any]:
    with surface_environment(surface):
        from fastapi import FastAPI
        from fastapi.routing import APIRoute

        api_module = importlib.import_module("backend.app.api")
        settings_module = importlib.import_module("backend.app.governance.settings")
        route_group_metadata = api_module.ROUTE_GROUP_METADATA
        route_registry = api_module.ROUTE_REGISTRY

        app = FastAPI(title="MOSS Backend API Inventory")
        app.include_router(api_module.router)
        openapi = app.openapi()

        operations: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for entry in route_registry:
            group_metadata = route_group_metadata[entry.group]
            feature_flag = REGISTRY_FEATURE_FLAGS.get(entry.name, "")
            registration = "feature_gated" if feature_flag else "always_registered"

            for route in entry.router.routes:
                if not isinstance(route, APIRoute):
                    continue
                dependencies = _dependency_names(route)
                auth_dependencies = [
                    dependency
                    for dependency in dependencies
                    if ".security." in dependency or "auth" in dependency.rsplit(".", maxsplit=1)[-1].lower()
                ]

                for method in sorted(route.methods or ()):
                    if method not in HTTP_METHODS:
                        continue
                    key = (method, route.path)
                    if key in seen:
                        raise RuntimeError(f"Duplicate registered operation: {method} {route.path}")
                    seen.add(key)

                    operation = openapi.get("paths", {}).get(route.path, {}).get(method.lower(), {})
                    if not isinstance(operation, dict):
                        operation = {}
                    operation_id = str(
                        operation.get("operationId") or route.operation_id or route.unique_id or route.name
                    )
                    operation_id_source = (
                        "explicit"
                        if route.operation_id
                        else "openapi_generated"
                        if operation.get("operationId")
                        else "route_fallback"
                    )
                    response_schema, response_statuses = _primary_response_schema(operation)
                    tags = _dedupe(
                        [
                            *(str(tag) for tag in operation.get("tags", []) if tag),
                            *(str(tag) for tag in route.tags if tag),
                            *(str(tag) for tag in entry.tags if tag),
                        ]
                    )
                    handler_module = getattr(route.endpoint, "__module__", "")
                    handler = getattr(
                        route.endpoint,
                        "__qualname__",
                        getattr(route.endpoint, "__name__", route.name),
                    )

                    operations.append(
                        {
                            "surface": surface,
                            "method": method,
                            "path": route.path,
                            "operation_id": operation_id,
                            "operation_id_source": operation_id_source,
                            "registry_name": entry.name,
                            "route_group": entry.group,
                            "route_group_label": group_metadata.label,
                            "owner": entry.owner,
                            "namespace": _namespace(route.path),
                            "action_class": _action_class(method, route.path, str(handler)),
                            "registration": registration,
                            "feature_flag": feature_flag,
                            "handler_module": handler_module,
                            "handler": str(handler),
                            "route_name": route.name,
                            "tags": tags,
                            "request_schema": _content_schema_label(operation.get("requestBody", {})),
                            "response_schema": response_schema,
                            "response_statuses": response_statuses,
                            "parameters": _parameter_labels(operation),
                            "response_model": _response_model_name(route),
                            "dependencies": dependencies,
                            "auth_dependencies": auth_dependencies,
                            "auth_dependency_present": bool(auth_dependencies),
                            "write_candidate": method not in {"GET", "HEAD", "OPTIONS"},
                            "include_in_schema": bool(route.include_in_schema),
                            "deprecated": bool(route.deprecated),
                            "claim_boundary": group_metadata.claim_boundary,
                            "risk_boundary": group_metadata.risk_boundary,
                        }
                    )

        operations.sort(key=lambda row: (row["path"], row["method"], row["registry_name"]))
        method_counts = Counter(row["method"] for row in operations)
        group_counts = Counter(row["route_group"] for row in operations)
        action_counts = Counter(row["action_class"] for row in operations)
        namespace_counts = Counter(row["namespace"] for row in operations)
        registration_counts = Counter(row["registration"] for row in operations)
        settings = settings_module.get_settings()

        return {
            "schema_version": 1,
            "surface": surface,
            "effective_feature_flags": {
                "MOSS_AGENT_ENABLED": bool(settings.agent_enabled),
            },
            "summary": {
                "registry_entry_count": len(route_registry),
                "operation_count": len(operations),
                "unique_path_count": len({row["path"] for row in operations}),
                "method_counts": dict(sorted(method_counts.items())),
                "group_counts": dict(sorted(group_counts.items())),
                "action_counts": dict(sorted(action_counts.items())),
                "namespace_counts": dict(sorted(namespace_counts.items())),
                "registration_counts": dict(sorted(registration_counts.items())),
            },
            "group_metadata": {
                group: {
                    "label": metadata.label,
                    "claim_boundary": metadata.claim_boundary,
                    "risk_boundary": metadata.risk_boundary,
                    "owner": metadata.owner,
                }
                for group, metadata in route_group_metadata.items()
            },
            "operations": operations,
        }


def _json_text(inventory: dict[str, Any]) -> str:
    return json.dumps(inventory, ensure_ascii=False, indent=2)


def _csv_value(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def _csv_text(inventory: dict[str, Any]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for operation in inventory["operations"]:
        writer.writerow({field: _csv_value(operation.get(field, "")) for field in CSV_FIELDS})
    return buffer.getvalue().rstrip("\n")


def _markdown_cell(value: object) -> str:
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _markdown_text(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    flags = inventory["effective_feature_flags"]
    lines = [
        "# Backend API Inventory",
        "",
        f"- Surface: `{inventory['surface']}`",
        f"- Operations: **{summary['operation_count']}**",
        f"- Unique paths: **{summary['unique_path_count']}**",
        f"- Registry entries: **{summary['registry_entry_count']}**",
        f"- Effective feature flags: `{json.dumps(flags, sort_keys=True)}`",
        "",
        "> Route groups are claim and risk boundaries, not endpoint-level business certification. "
        "The action class is a method/path/handler heuristic and requires domain review.",
        "",
        "## Group summary",
        "",
        "| Group | Operations |",
        "| --- | ---: |",
    ]
    for group, count in summary["group_counts"].items():
        lines.append(f"| `{group}` | {count} |")

    lines.extend(
        [
            "",
            "## Method summary",
            "",
            "| Method | Operations |",
            "| --- | ---: |",
        ]
    )
    for method, count in summary["method_counts"].items():
        lines.append(f"| `{method}` | {count} |")

    lines.extend(
        [
            "",
            "## Operations",
            "",
            "| Method | Path | Group | Registry | Action | Registration | Handler | Request | Response | Auth |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for operation in inventory["operations"]:
        feature = (
            f"{operation['registration']}:{operation['feature_flag']}"
            if operation["feature_flag"]
            else operation["registration"]
        )
        handler = f"{operation['handler_module']}.{operation['handler']}"
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    operation["method"],
                    operation["path"],
                    operation["route_group"],
                    operation["registry_name"],
                    operation["action_class"],
                    feature,
                    handler,
                    operation["request_schema"] or "(none)",
                    operation["response_schema"] or "(none)",
                    "yes" if operation["auth_dependency_present"] else "no",
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _serialize(inventory: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return _json_text(inventory)
    if output_format == "csv":
        return _csv_text(inventory)
    if output_format == "markdown":
        return _markdown_text(inventory)
    raise ValueError(f"Unsupported output format: {output_format}")


def _write_output(text: str, output: str) -> None:
    if output == "-":
        print(text)
        return
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    inventory = _load_inventory(args.surface)
    _write_output(_serialize(inventory, args.format), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
