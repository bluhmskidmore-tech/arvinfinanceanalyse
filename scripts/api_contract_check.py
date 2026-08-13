"""Local and CI entry points for the FastAPI OpenAPI contract surface.

Three jobs live here:

* `export-openapi` renders the OpenAPI document for a pinned route surface.
* `baseline-update` / `baseline-check` maintain and enforce the committed
  contract snapshots under `contracts/openapi/`.
* `schemathesis-command` prints the offline fuzz command.

The breaking-change gate compares the *current* code against the baseline as it
exists on a git ref (normally the PR base branch). Regenerating the snapshot in
the same pull request therefore does not silence a removal or a type change;
clearing one requires an explicit entry in the acknowledgements file, which is
itself reviewable.
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api_surface import SURFACE_CHOICES, SURFACE_HELP, surface_environment  # noqa: E402

BASELINE_DIR_NAME = "contracts/openapi"
BASELINE_DIR = ROOT / "contracts" / "openapi"
BASELINE_SURFACES: tuple[str, ...] = ("default", "full")
ACKNOWLEDGEMENTS_NAME = "breaking-change-acknowledgements.json"
ACKNOWLEDGEMENTS_PATH = BASELINE_DIR / ACKNOWLEDGEMENTS_NAME
HTTP_METHODS: tuple[str, ...] = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
# Schema graphs are cyclic (a node type that lists its own children). The ref
# guard below handles named cycles; this cap bounds anonymous nesting.
MAX_SCHEMA_DEPTH = 12

BREAKING = "breaking"
ADDITIVE = "additive"

# The flattener collapses a schema that names no field at all -- `response_model=dict`
# rendering as `{"additionalProperties": true, "type": "object"}`, or a missing
# `response_model` rendering as `{}` -- into the single anonymous root entry ".".
# Replacing such a schema with a real one is a coverage *gain*, but naively it looks
# like the "." field disappeared. `_schema_precision_change` tells the two apart.
OPAQUE_ROOT_TYPES = frozenset({"object", "unknown"})


# --------------------------------------------------------------------------------------
# Spec loading and canonical serialization
# --------------------------------------------------------------------------------------


def _load_openapi(surface: str) -> dict[str, Any]:
    """Render the real application's OpenAPI document with `surface` feature flags pinned.

    Importing `backend.app.main` builds the app but never enters its lifespan, so
    no storage migration, cache warmup, or DuckDB connection runs here.
    """
    with surface_environment(surface):
        main_module = importlib.import_module("backend.app.main")
        payload = main_module.app.openapi()
    if not isinstance(payload, dict):
        raise RuntimeError(f"OpenAPI export for surface {surface!r} did not return an object")
    return payload


def _canonical_json(payload: dict[str, Any]) -> str:
    """Key-sorted rendering so committed snapshots diff on meaning, not dict ordering."""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def baseline_relative_path(surface: str) -> str:
    return f"{BASELINE_DIR_NAME}/openapi.{surface}.json"


def baseline_path(surface: str) -> Path:
    return BASELINE_DIR / f"openapi.{surface}.json"


# --------------------------------------------------------------------------------------
# Contract extraction
# --------------------------------------------------------------------------------------


def _resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    node: Any = spec
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, dict) else None


def _short_label(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "unknown"
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return ref.rsplit("/", maxsplit=1)[-1]
    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        return schema_type
    if isinstance(schema_type, list):
        return "|".join(sorted(str(item) for item in schema_type))
    return "unknown"


def _scalar_signature(schema: dict[str, Any]) -> str:
    parts: list[str] = []
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        parts.append("|".join(sorted(str(item) for item in schema_type)))
    elif isinstance(schema_type, str):
        parts.append(schema_type)
    schema_format = schema.get("format")
    if isinstance(schema_format, str):
        parts.append(f"format={schema_format}")
    return ",".join(parts) if parts else "unknown"


def _enum_values(schema: dict[str, Any]) -> list[str] | None:
    values = schema.get("enum")
    if not isinstance(values, list):
        return None
    return sorted(json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values)


def _leaf(prefix: str, type_signature: str, required: bool, enum: list[str] | None = None) -> dict[str, Any]:
    return {prefix or ".": {"type": type_signature, "required": required, "enum": enum}}


def _flatten_schema(
    schema: Any,
    spec: dict[str, Any],
    *,
    prefix: str = "",
    required: bool = True,
    seen_refs: frozenset[str] = frozenset(),
    depth: int = 0,
) -> dict[str, dict[str, Any]]:
    """Flatten a JSON Schema into `{dotted.field.path: {type, required, enum}}`.

    Array items get a `[]` segment and free-form maps get a `{}` segment, so a
    renamed or retyped leaf shows up as a distinct path rather than as an opaque
    `$ref` swap.
    """
    if not isinstance(schema, dict):
        return _leaf(prefix, "unknown", required)
    if depth > MAX_SCHEMA_DEPTH:
        return _leaf(prefix, "<max-depth>", required)

    ref = schema.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", maxsplit=1)[-1]
        if name in seen_refs:
            return _leaf(prefix, f"<recursive:{name}>", required)
        target = _resolve_ref(spec, ref)
        if target is None:
            return _leaf(prefix, f"<unresolved:{name}>", required)
        return _flatten_schema(
            target,
            spec,
            prefix=prefix,
            required=required,
            seen_refs=seen_refs | {name},
            depth=depth + 1,
        )

    all_of = schema.get("allOf")
    if isinstance(all_of, list) and all_of:
        merged: dict[str, dict[str, Any]] = {}
        for member in all_of:
            merged.update(
                _flatten_schema(
                    member,
                    spec,
                    prefix=prefix,
                    required=required,
                    seen_refs=seen_refs,
                    depth=depth + 1,
                )
            )
        return merged

    for combinator in ("oneOf", "anyOf"):
        choices = schema.get(combinator)
        if not isinstance(choices, list) or not choices:
            continue
        # `Optional[X]` renders as anyOf[X, null]; descend so the real shape is compared.
        concrete = [item for item in choices if isinstance(item, dict) and item.get("type") != "null"]
        if len(concrete) == 1:
            return _flatten_schema(
                concrete[0],
                spec,
                prefix=prefix,
                required=required,
                seen_refs=seen_refs,
                depth=depth + 1,
            )
        labels = ", ".join(sorted(_short_label(item) for item in choices))
        return _leaf(prefix, f"{combinator}[{labels}]", required)

    # Container nodes get their own entry so that dropping a whole `result` object,
    # or making it optional, is visible instead of only its leaves moving.
    properties = schema.get("properties")
    if isinstance(properties, dict) and properties:
        required_names = {str(name) for name in schema.get("required", []) if isinstance(name, str)}
        fields: dict[str, dict[str, Any]] = {} if not prefix else _leaf(prefix, "object", required)
        for name, sub_schema in sorted(properties.items()):
            child_prefix = f"{prefix}.{name}" if prefix else str(name)
            fields.update(
                _flatten_schema(
                    sub_schema,
                    spec,
                    prefix=child_prefix,
                    required=str(name) in required_names,
                    seen_refs=seen_refs,
                    depth=depth + 1,
                )
            )
        return fields

    if schema.get("type") == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            return _leaf(prefix, "array", required)
        fields = _leaf(prefix, "array", required) if prefix else {}
        # Items are always present within the list; the array field itself carries
        # the optionality, recorded on the node above.
        fields.update(
            _flatten_schema(
                items,
                spec,
                prefix=f"{prefix}[]",
                required=True,
                seen_refs=seen_refs,
                depth=depth + 1,
            )
        )
        return fields

    additional = schema.get("additionalProperties")
    if isinstance(additional, dict) and additional:
        fields = _leaf(prefix, "object-map", required) if prefix else {}
        fields.update(
            _flatten_schema(
                additional,
                spec,
                prefix=f"{prefix}{{}}",
                required=True,
                seen_refs=seen_refs,
                depth=depth + 1,
            )
        )
        return fields

    if schema.get("type") == "object":
        return _leaf(prefix, "object", required)

    return _leaf(prefix, _scalar_signature(schema), required, _enum_values(schema))


def _json_content_schema(container: Any) -> dict[str, Any] | None:
    if not isinstance(container, dict):
        return None
    content = container.get("content")
    if not isinstance(content, dict) or not content:
        return None
    media = content.get("application/json")
    if not isinstance(media, dict):
        media = next((value for value in content.values() if isinstance(value, dict)), None)
    if not isinstance(media, dict):
        return None
    schema = media.get("schema")
    return schema if isinstance(schema, dict) else None


def _operation_contract(operation: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for raw_parameter in operation.get("parameters", []) or []:
        parameter = raw_parameter
        if isinstance(parameter, dict) and isinstance(parameter.get("$ref"), str):
            resolved = _resolve_ref(spec, parameter["$ref"])
            if resolved is not None:
                parameter = resolved
        if not isinstance(parameter, dict):
            continue
        key = f"{parameter.get('in', 'unknown')}:{parameter.get('name', 'unknown')}"
        parameters[key] = {
            "required": bool(parameter.get("required")),
            "fields": _flatten_schema(parameter.get("schema") or {}, spec),
        }

    request_body = operation.get("requestBody")
    body_contract: dict[str, Any] | None = None
    if isinstance(request_body, dict):
        if isinstance(request_body.get("$ref"), str):
            resolved_body = _resolve_ref(spec, request_body["$ref"])
            if resolved_body is not None:
                request_body = resolved_body
        body_schema = _json_content_schema(request_body)
        body_contract = {
            "required": bool(request_body.get("required")),
            "fields": _flatten_schema(body_schema, spec) if body_schema is not None else {},
            "has_schema": body_schema is not None,
        }

    # Only 2xx responses are governed. Error envelopes (422 HTTPValidationError and
    # friends) are framework-generated and their churn would drown the real signal.
    responses: dict[str, Any] = {}
    for status, response in (operation.get("responses") or {}).items():
        status_text = str(status)
        if not (status_text.isdigit() and 200 <= int(status_text) < 300):
            continue
        response_schema = _json_content_schema(response)
        responses[status_text] = {
            "has_schema": response_schema is not None,
            "fields": _flatten_schema(response_schema, spec) if response_schema is not None else {},
        }

    return {
        "operation_id": str(operation.get("operationId") or ""),
        "deprecated": bool(operation.get("deprecated")),
        "parameters": parameters,
        "request_body": body_contract,
        "responses": responses,
    }


def extract_contract(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Reduce a whole OpenAPI document to `{"GET /api/x": operation_contract}`."""
    contract: dict[str, dict[str, Any]] = {}
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return contract

    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            continue
        shared_parameters = path_item.get("parameters")
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            if isinstance(shared_parameters, list) and shared_parameters:
                merged_operation = dict(operation)
                merged_operation["parameters"] = [
                    *shared_parameters,
                    *(operation.get("parameters") or []),
                ]
                operation = merged_operation
            contract[f"{method.upper()} {path}"] = _operation_contract(operation, spec)
    return contract


# --------------------------------------------------------------------------------------
# Diff engine
# --------------------------------------------------------------------------------------


def _finding(
    surface: str,
    severity: str,
    kind: str,
    operation: str,
    target: str,
    detail: str,
) -> dict[str, str]:
    return {
        "id": f"{surface}|{kind}|{operation}|{target}",
        "surface": surface,
        "severity": severity,
        "kind": kind,
        "operation": operation,
        "target": target,
        "detail": detail,
    }


def _is_opaque_root(fields: dict[str, Any]) -> bool:
    """True when the whole scope flattens to one unnamed root that pins no field."""
    if set(fields) != {"."}:
        return False
    return str((fields.get(".") or {}).get("type") or "") in OPAQUE_ROOT_TYPES


def _schema_precision_change(
    base_fields: dict[str, Any],
    head_fields: dict[str, Any],
) -> str | None:
    """Classify a swap between an opaque body and a field-level one.

    Returns "tightened" when a body that named nothing starts naming fields, and
    "loosened" for the reverse. Both directions are invisible to a per-field diff:
    the opaque side has exactly one entry, ".", which is not a real field name.
    """
    base_opaque = _is_opaque_root(base_fields)
    head_opaque = _is_opaque_root(head_fields)
    if base_opaque and not head_opaque and head_fields:
        return "tightened"
    if head_opaque and not base_opaque and base_fields:
        return "loosened"
    return None


def _diff_field_maps(
    surface: str,
    operation: str,
    scope: str,
    base_fields: dict[str, Any],
    head_fields: dict[str, Any],
    *,
    direction: str,
) -> list[dict[str, str]]:
    """Compare two flattened field maps.

    `direction` is "response" for data the server promises to return and "request"
    for data the client is allowed to send; the two invert which changes hurt.
    """
    findings: list[dict[str, str]] = []
    for field_path, base_facts in sorted(base_fields.items()):
        head_facts = head_fields.get(field_path)
        target = f"{scope}:{field_path}"
        # "." is the flattener's name for a scalar sitting at the root of the scope.
        label = scope if field_path == "." else f"{scope} field '{field_path}'"
        if head_facts is None:
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    f"{direction}_field_removed",
                    operation,
                    target,
                    f"{label} was removed",
                )
            )
            continue
        if base_facts.get("type") != head_facts.get("type"):
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    f"{direction}_field_type_changed",
                    operation,
                    target,
                    f"{label} type {base_facts.get('type')!r} -> {head_facts.get('type')!r}",
                )
            )
        base_required = bool(base_facts.get("required"))
        head_required = bool(head_facts.get("required"))
        if direction == "response" and base_required and not head_required:
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "response_field_became_optional",
                    operation,
                    target,
                    f"{label} is no longer guaranteed to be present",
                )
            )
        if direction == "request" and not base_required and head_required:
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "request_field_became_required",
                    operation,
                    target,
                    f"{label} became required",
                )
            )

        base_enum = base_facts.get("enum")
        head_enum = head_facts.get("enum")
        if isinstance(base_enum, list) and isinstance(head_enum, list):
            if direction == "response":
                # A new response enum member can fall through an exhaustive client switch.
                added = sorted(set(head_enum) - set(base_enum))
                if added:
                    findings.append(
                        _finding(
                            surface,
                            BREAKING,
                            "response_enum_value_added",
                            operation,
                            target,
                            f"{label} gained enum value(s) {', '.join(added)}",
                        )
                    )
            else:
                removed = sorted(set(base_enum) - set(head_enum))
                if removed:
                    findings.append(
                        _finding(
                            surface,
                            BREAKING,
                            "request_enum_value_removed",
                            operation,
                            target,
                            f"{label} no longer accepts {', '.join(removed)}",
                        )
                    )
        elif isinstance(base_enum, list) and head_enum is None and direction == "request":
            pass  # widening a request enum to a free value is additive

    for field_path, head_facts in sorted(head_fields.items()):
        if field_path in base_fields:
            continue
        target = f"{scope}:{field_path}"
        if direction == "request" and bool(head_facts.get("required")):
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "required_request_field_added",
                    operation,
                    target,
                    f"{scope} gained required field '{field_path}'",
                )
            )
        else:
            findings.append(
                _finding(
                    surface,
                    ADDITIVE,
                    f"{direction}_field_added",
                    operation,
                    target,
                    f"{scope} gained field '{field_path}'",
                )
            )
    return findings


def _diff_parameters(
    surface: str,
    operation: str,
    base: dict[str, Any],
    head: dict[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for key, base_parameter in sorted(base.items()):
        head_parameter = head.get(key)
        if head_parameter is None:
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "parameter_removed",
                    operation,
                    key,
                    f"parameter '{key}' was removed",
                )
            )
            continue
        if not base_parameter.get("required") and head_parameter.get("required"):
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "parameter_became_required",
                    operation,
                    key,
                    f"parameter '{key}' changed from optional to required",
                )
            )
        findings.extend(
            _diff_field_maps(
                surface,
                operation,
                f"parameter {key}",
                base_parameter.get("fields") or {},
                head_parameter.get("fields") or {},
                direction="request",
            )
        )

    for key, head_parameter in sorted(head.items()):
        if key in base:
            continue
        if head_parameter.get("required"):
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "required_parameter_added",
                    operation,
                    key,
                    f"new required parameter '{key}'",
                )
            )
        else:
            findings.append(
                _finding(
                    surface,
                    ADDITIVE,
                    "optional_parameter_added",
                    operation,
                    key,
                    f"new optional parameter '{key}'",
                )
            )
    return findings


def _diff_request_body(
    surface: str,
    operation: str,
    base: dict[str, Any] | None,
    head: dict[str, Any] | None,
) -> list[dict[str, str]]:
    if base is None:
        if head is not None and head.get("required"):
            return [
                _finding(
                    surface,
                    BREAKING,
                    "required_request_body_added",
                    operation,
                    "requestBody",
                    "operation now requires a request body",
                )
            ]
        return []
    if head is None:
        return [
            _finding(
                surface,
                BREAKING,
                "request_body_removed",
                operation,
                "requestBody",
                "request body was removed",
            )
        ]

    findings: list[dict[str, str]] = []
    if not base.get("required") and head.get("required"):
        findings.append(
            _finding(
                surface,
                BREAKING,
                "request_body_became_required",
                operation,
                "requestBody",
                "request body changed from optional to required",
            )
        )
    findings.extend(
        _diff_field_maps(
            surface,
            operation,
            "requestBody",
            base.get("fields") or {},
            head.get("fields") or {},
            direction="request",
        )
    )
    return findings


def _diff_responses(
    surface: str,
    operation: str,
    base: dict[str, Any],
    head: dict[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for status, base_response in sorted(base.items()):
        head_response = head.get(status)
        if head_response is None:
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "response_status_removed",
                    operation,
                    status,
                    f"success response {status} was removed",
                )
            )
            continue
        if base_response.get("has_schema") and not head_response.get("has_schema"):
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "response_schema_removed",
                    operation,
                    status,
                    f"response {status} lost its declared schema",
                )
            )
            continue

        base_fields = base_response.get("fields") or {}
        head_fields = head_response.get("fields") or {}
        precision_change = _schema_precision_change(base_fields, head_fields)
        if precision_change == "tightened":
            # Every field is new relative to a body that promised nothing, so the
            # per-field diff would emit hundreds of meaningless "gained field"
            # entries. Report the coverage gain once instead.
            findings.append(
                _finding(
                    surface,
                    ADDITIVE,
                    "response_contract_tightened",
                    operation,
                    status,
                    f"response {status} replaced a free-form body with a field-level schema "
                    f"({len(head_fields)} field paths now governed)",
                )
            )
            continue
        if precision_change == "loosened":
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "response_contract_loosened",
                    operation,
                    status,
                    f"response {status} replaced a field-level schema with a free-form body, "
                    f"dropping {len(base_fields)} governed field paths",
                )
            )
            continue

        findings.extend(
            _diff_field_maps(
                surface,
                operation,
                f"response {status}",
                base_fields,
                head_fields,
                direction="response",
            )
        )

    for status, head_response in sorted(head.items()):
        if status in base:
            continue
        findings.append(
            _finding(
                surface,
                ADDITIVE,
                "response_status_added",
                operation,
                status,
                f"new success response {status}"
                + (" with a declared schema" if head_response.get("has_schema") else ""),
            )
        )
    return findings


def diff_contracts(
    surface: str,
    base_spec: dict[str, Any],
    head_spec: dict[str, Any],
) -> list[dict[str, str]]:
    base = extract_contract(base_spec)
    head = extract_contract(head_spec)

    findings: list[dict[str, str]] = []
    for operation, base_contract in sorted(base.items()):
        head_contract = head.get(operation)
        if head_contract is None:
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "operation_removed",
                    operation,
                    "-",
                    "operation was removed from the contract",
                )
            )
            continue
        if base_contract["operation_id"] != head_contract["operation_id"]:
            findings.append(
                _finding(
                    surface,
                    BREAKING,
                    "operation_id_changed",
                    operation,
                    "operationId",
                    f"operationId {base_contract['operation_id']!r} -> {head_contract['operation_id']!r}",
                )
            )
        findings.extend(
            _diff_parameters(surface, operation, base_contract["parameters"], head_contract["parameters"])
        )
        findings.extend(
            _diff_request_body(surface, operation, base_contract["request_body"], head_contract["request_body"])
        )
        findings.extend(_diff_responses(surface, operation, base_contract["responses"], head_contract["responses"]))

    for operation in sorted(head):
        if operation not in base:
            findings.append(
                _finding(surface, ADDITIVE, "operation_added", operation, "-", "new operation")
            )
    return findings


# --------------------------------------------------------------------------------------
# Baseline / acknowledgement I/O
# --------------------------------------------------------------------------------------


def _read_baseline_from_ref(ref: str, relative_path: str) -> dict[str, Any] | None:
    completed = subprocess.run(
        ["git", "show", f"{ref}:{relative_path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        return None
    return json.loads(completed.stdout)


def _read_baseline_from_disk(surface: str) -> dict[str, Any] | None:
    path = baseline_path(surface)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def acknowledgement_candidate_ids(finding: dict[str, str]) -> tuple[str, str]:
    """Exact id, then the surface-agnostic form.

    A route that exists on both baseline surfaces produces one finding per surface;
    the `*|...` form lets a single reviewed entry cover both.
    """
    exact = finding["id"]
    return exact, f"*|{finding['kind']}|{finding['operation']}|{finding['target']}"


def load_acknowledgements() -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return `{finding_id: entry}` plus any structural problems in the file."""
    if not ACKNOWLEDGEMENTS_PATH.exists():
        return {}, []
    try:
        payload = json.loads(ACKNOWLEDGEMENTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return {}, [f"{ACKNOWLEDGEMENTS_NAME} is not valid JSON: {error}"]

    problems: list[str] = []
    entries = payload.get("acknowledgements") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {}, [f"{ACKNOWLEDGEMENTS_NAME} must contain an 'acknowledgements' array"]

    resolved: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"acknowledgement #{index} is not an object")
            continue
        finding_id = entry.get("id")
        if not isinstance(finding_id, str) or not finding_id.strip():
            problems.append(f"acknowledgement #{index} is missing a non-empty 'id'")
            continue
        for required_field in ("reason", "approved_by"):
            value = entry.get(required_field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"acknowledgement '{finding_id}' is missing a non-empty '{required_field}'")
        resolved[finding_id] = entry
    return resolved, problems


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------


def _export_openapi(surface: str, output: str) -> int:
    serialized = _canonical_json(_load_openapi(surface))
    if output == "-":
        sys.stdout.write(serialized)
        return 0
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialized, encoding="utf-8")
    return 0


def _baseline_update(surfaces: tuple[str, ...]) -> int:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    for surface in surfaces:
        path = baseline_path(surface)
        serialized = _canonical_json(_load_openapi(surface))
        changed = not path.exists() or path.read_text(encoding="utf-8") != serialized
        path.write_text(serialized, encoding="utf-8")
        print(f"{'updated' if changed else 'unchanged'}: {baseline_relative_path(surface)}")
    print(
        "\nReview the snapshot diff before committing. If it contains a breaking change, "
        f"add the matching entry to {BASELINE_DIR_NAME}/{ACKNOWLEDGEMENTS_NAME}."
    )
    return 0


def _render_report(report: dict[str, Any]) -> str:
    lines: list[str] = ["OpenAPI contract gate", "=" * 21, ""]
    lines.append(f"baseline source: {report['baseline_source']}")
    lines.append("")

    for surface_report in report["surfaces"]:
        surface = surface_report["surface"]
        lines.append(f"[{surface}] {surface_report['operation_count']} operations")
        if surface_report["baseline_missing"]:
            lines.append(f"  - no baseline found at {baseline_relative_path(surface)} on the compared ref (bootstrap)")
        if surface_report["stale_baseline"]:
            lines.append(
                f"  ! committed snapshot {baseline_relative_path(surface)} does not match the current code; "
                "run: python scripts/api_contract_check.py baseline-update"
            )
        counts = surface_report["counts"]
        lines.append(
            f"  breaking={counts['breaking']} acknowledged={counts['acknowledged']} additive={counts['additive']}"
        )
        if counts.get("tightened"):
            lines.append(
                f"  + {counts['tightened']} operation(s) upgraded from a free-form body to a field-level schema"
            )
        for finding in surface_report["findings"]:
            if finding["severity"] == ADDITIVE:
                continue
            marker = "ACK " if finding.get("acknowledged") else "FAIL"
            lines.append(f"  {marker} {finding['kind']}: {finding['operation']} :: {finding['detail']}")
            if not finding.get("acknowledged"):
                lines.append(f"       id: {finding['id']}")
        additive = [finding for finding in surface_report["findings"] if finding["severity"] == ADDITIVE]
        for finding in additive[:20]:
            lines.append(f"  ok   {finding['kind']}: {finding['operation']} :: {finding['detail']}")
        if len(additive) > 20:
            lines.append(f"  ok   ... and {len(additive) - 20} more additive changes")
        lines.append("")

    if report["acknowledgement_problems"]:
        lines.append("Acknowledgement file problems:")
        lines.extend(f"  - {problem}" for problem in report["acknowledgement_problems"])
        lines.append("")
    if report["unused_acknowledgements"]:
        lines.append("Unused acknowledgements (safe to delete once the change is on the base branch):")
        lines.extend(f"  - {entry}" for entry in report["unused_acknowledgements"])
        lines.append("")

    lines.append(f"RESULT: {'PASS' if report['passed'] else 'FAIL'}")
    if not report["passed"]:
        lines.append("")
        lines.append(
            "A breaking change needs an explicit, reviewable acknowledgement entry in "
            f"{BASELINE_DIR_NAME}/{ACKNOWLEDGEMENTS_NAME} (id / reason / approved_by), plus an updated snapshot."
        )
    return "\n".join(lines)


def _baseline_check(
    surfaces: tuple[str, ...],
    baseline_ref: str | None,
    allow_stale_baseline: bool,
    json_output: str | None,
) -> int:
    acknowledgements, acknowledgement_problems = load_acknowledgements()
    used_acknowledgements: set[str] = set()
    passed = not acknowledgement_problems
    surface_reports: list[dict[str, Any]] = []

    for surface in surfaces:
        head_spec = _load_openapi(surface)
        head_text = _canonical_json(head_spec)
        relative_path = baseline_relative_path(surface)

        if baseline_ref:
            base_spec = _read_baseline_from_ref(baseline_ref, relative_path)
        else:
            base_spec = _read_baseline_from_disk(surface)

        disk_text = baseline_path(surface).read_text(encoding="utf-8") if baseline_path(surface).exists() else None
        stale_baseline = disk_text != head_text

        findings = diff_contracts(surface, base_spec, head_spec) if base_spec is not None else []
        for finding in findings:
            if finding["severity"] != BREAKING:
                continue
            for candidate in acknowledgement_candidate_ids(finding):
                if candidate in acknowledgements:
                    finding["acknowledged"] = True
                    used_acknowledgements.add(candidate)
                    break

        unacknowledged = [
            finding
            for finding in findings
            if finding["severity"] == BREAKING and not finding.get("acknowledged")
        ]
        if unacknowledged or (stale_baseline and not allow_stale_baseline):
            passed = False

        surface_reports.append(
            {
                "surface": surface,
                "operation_count": len(extract_contract(head_spec)),
                "baseline_missing": base_spec is None,
                "stale_baseline": stale_baseline,
                "counts": {
                    "breaking": len(unacknowledged),
                    "acknowledged": sum(1 for finding in findings if finding.get("acknowledged")),
                    "additive": sum(1 for finding in findings if finding["severity"] == ADDITIVE),
                    "tightened": sum(
                        1 for finding in findings if finding["kind"] == "response_contract_tightened"
                    ),
                },
                "findings": findings,
            }
        )

    report = {
        "schema_version": 1,
        "baseline_source": f"git ref {baseline_ref}" if baseline_ref else "working tree",
        "allow_stale_baseline": allow_stale_baseline,
        "surfaces": surface_reports,
        "acknowledgement_problems": acknowledgement_problems,
        "unused_acknowledgements": sorted(set(acknowledgements) - used_acknowledgements),
        "passed": passed,
    }

    print(_render_report(report))
    if json_output:
        target = Path(json_output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


def schemathesis_command(schema_path: str = ".codex-tmp/openapi.json", base_url: str = "http://127.0.0.1:8000") -> str:
    """Schemathesis 4.x `run` takes a LOCATION plus `-u/--url`; there is no `--app`."""
    return f"schemathesis run {schema_path} --url {base_url}"


def _print_schemathesis_command() -> int:
    print(schemathesis_command())
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local API contract tooling entry points for FastAPI OpenAPI checks."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export-openapi",
        help="Export the FastAPI OpenAPI document to stdout or a file.",
    )
    export_parser.add_argument("--surface", choices=SURFACE_CHOICES, default="default", help=SURFACE_HELP)
    export_parser.add_argument("--output", default="-", help="Output path, or '-' for stdout.")

    update_parser = subparsers.add_parser(
        "baseline-update",
        help="Rewrite the committed OpenAPI baseline snapshots from the current code.",
    )
    update_parser.add_argument(
        "--surface",
        choices=BASELINE_SURFACES,
        action="append",
        dest="surfaces",
        help="Limit the update to one surface (repeatable). Defaults to every baseline surface.",
    )

    check_parser = subparsers.add_parser(
        "baseline-check",
        help="Fail on breaking contract changes relative to the committed OpenAPI baseline.",
    )
    check_parser.add_argument(
        "--surface",
        choices=BASELINE_SURFACES,
        action="append",
        dest="surfaces",
        help="Limit the check to one surface (repeatable). Defaults to every baseline surface.",
    )
    check_parser.add_argument(
        "--baseline-ref",
        default=None,
        help=(
            "Git ref to read the baseline from, e.g. 'origin/main'. Using the pull request base "
            "branch is what stops a same-PR snapshot rewrite from clearing the gate."
        ),
    )
    check_parser.add_argument(
        "--allow-stale-baseline",
        action="store_true",
        help="Report, but do not fail on, a committed snapshot that no longer matches the code.",
    )
    check_parser.add_argument("--json", dest="json_output", default=None, help="Write the machine-readable report here.")

    subparsers.add_parser(
        "schemathesis-command",
        help="Print the recommended local Schemathesis smoke command.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "export-openapi":
        return _export_openapi(args.surface, args.output)
    if args.command == "baseline-update":
        return _baseline_update(tuple(args.surfaces or BASELINE_SURFACES))
    if args.command == "baseline-check":
        return _baseline_check(
            tuple(args.surfaces or BASELINE_SURFACES),
            args.baseline_ref,
            args.allow_stale_baseline,
            args.json_output,
        )
    if args.command == "schemathesis-command":
        return _print_schemathesis_command()
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
