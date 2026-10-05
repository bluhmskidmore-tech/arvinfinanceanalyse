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
import hashlib
import importlib
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api_surface import SURFACE_CHOICES, SURFACE_HELP, surface_environment  # noqa: E402
from scripts.trusted_base_source import (  # noqa: E402
    BaseSourceError,
    isolated_backend_source,
    read_committed_blob,
    run_source_python,
    source_environment,
)

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
_GIT_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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


def _canonical_receipt_json(payload: dict[str, Any]) -> str:
    """Compact canonical form used only for stable receipt digests."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _spec_sha256(payload: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_json(payload).encode("utf-8"))


def _receipt_sha256(report: dict[str, Any]) -> str:
    canonical = dict(report)
    canonical.pop("receipt_sha256", None)
    return _sha256_bytes(_canonical_receipt_json(canonical).encode("utf-8"))


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


class BaselineGitError(RuntimeError):
    """A sanitized git-baseline failure safe to surface in CLI reports."""


def _run_git(args: list[str], *, failure_message: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as error:
        raise BaselineGitError(failure_message) from error


def _resolve_baseline_ref(ref: str) -> str:
    """Resolve a moving ref once so every surface compares against one commit."""
    completed = _run_git(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        failure_message="baseline ref could not be resolved",
    )
    resolved = completed.stdout.strip()
    if completed.returncode != 0 or _GIT_COMMIT_RE.fullmatch(resolved) is None:
        raise BaselineGitError("baseline ref could not be resolved")
    return resolved.lower()


def _read_baseline_from_ref(resolved_commit: str, relative_path: str) -> dict[str, Any] | None:
    """Read one baseline from an already-resolved commit.

    ``git ls-tree`` distinguishes a legitimately absent first baseline from a
    lower-level git failure without exposing stderr or local filesystem paths.
    """
    try:
        raw = read_committed_blob(ROOT, resolved_commit, relative_path)
    except BaseSourceError as error:
        raise BaselineGitError("baseline could not be read from resolved commit") from error
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise BaselineGitError("baseline at resolved commit is not valid JSON") from error
    if not isinstance(payload, dict):
        raise BaselineGitError("baseline at resolved commit is not a JSON object")
    if not isinstance(payload.get("openapi"), str) or not payload["openapi"].startswith("3.") or not isinstance(payload.get("paths"), dict):
        raise BaselineGitError("baseline at resolved commit is not a valid OpenAPI snapshot")
    return payload


def _read_baseline_from_disk(surface: str) -> dict[str, Any] | None:
    path = baseline_path(surface)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _derive_openapi_baselines(
    commit: str, surfaces: tuple[str, ...], source_parent: Path,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Render missing snapshots from exact base code without importing PR code."""
    code = """
import json
import importlib.metadata
root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root), str(root / 'backend')]
from backend.app.main import app
for name, module in tuple(sys.modules.items()):
    if name in {'backend', 'app'} or name.startswith(('backend.', 'app.')):
        locations = [getattr(module, '__file__', None), *getattr(module, '__path__', [])]
        if any(location and not Path(location).resolve().is_relative_to(root) for location in locations):
            raise RuntimeError('backend import escaped isolated base source')
print(json.dumps({'spec': app.openapi(), 'runtime': {
    'python': '.'.join(map(str, sys.version_info[:3])),
    'fastapi': importlib.metadata.version('fastapi'),
    'pydantic': importlib.metadata.version('pydantic'),
    'pydantic-settings': importlib.metadata.version('pydantic-settings'),
}}))
"""
    derived = {}
    try:
        with isolated_backend_source(ROOT, commit, source_parent) as source:
            for surface in surfaces:
                environment = source_environment(source.root)
                environment["MOSS_AGENT_ENABLED"] = "true" if surface == "full" else "false"
                completed = run_source_python(source, code, [], environment=environment)
                if completed.returncode != 0:
                    raise BaseSourceError("trusted base OpenAPI export failed")
                payload = json.loads(completed.stdout)
                spec, runtime = payload["spec"], payload["runtime"]
                if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict) or not isinstance(runtime, dict):
                    raise BaseSourceError("trusted base OpenAPI export is invalid")
                derived[surface] = (spec, source.provenance() | {
                    "runtime": runtime,
                    "surface_flags": {"MOSS_AGENT_ENABLED": environment["MOSS_AGENT_ENABLED"]},
                    "command": "import exact-base backend.app.main; app.openapi() without lifespan",
                })
    except (BaseSourceError, ValueError, KeyError, TypeError) as error:
        raise BaselineGitError("missing baseline could not be derived from exact base source") from error
    return derived


def acknowledgement_candidate_ids(finding: dict[str, str]) -> tuple[str, str]:
    """Exact id, then the surface-agnostic form.

    A route that exists on both baseline surfaces produces one finding per surface;
    the `*|...` form lets a single reviewed entry cover both.
    """
    exact = finding["id"]
    return exact, f"*|{finding['kind']}|{finding['operation']}|{finding['target']}"


def load_acknowledgements() -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return entries plus structural problems without rejecting legacy unused entries.

    The strict owner/consumer/migration/expiry policy is applied only when an
    entry actually matches a breaking finding. This keeps historical unused
    entries visible without letting their legacy shape authorize a release.
    """
    if not ACKNOWLEDGEMENTS_PATH.exists():
        return {}, []
    try:
        payload = json.loads(ACKNOWLEDGEMENTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return {}, [f"{ACKNOWLEDGEMENTS_NAME} is not valid JSON: {error}"]
    except OSError:
        return {}, [f"{ACKNOWLEDGEMENTS_NAME} could not be read"]

    problems: list[str] = []
    entries = payload.get("acknowledgements") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {}, [f"{ACKNOWLEDGEMENTS_NAME} must contain an 'acknowledgements' array"]

    resolved: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"acknowledgement #{index} is not an object")
            continue
        finding_id = entry.get("id")
        if not isinstance(finding_id, str) or not finding_id.strip():
            problems.append(f"acknowledgement #{index} is missing a non-empty 'id'")
            continue
        finding_id = finding_id.strip()
        if finding_id in seen_ids:
            if finding_id not in duplicate_ids:
                problems.append(f"duplicate acknowledgement id {finding_id!r}")
            duplicate_ids.add(finding_id)
            resolved.pop(finding_id, None)
            continue
        seen_ids.add(finding_id)
        resolved[finding_id] = entry
    return resolved, problems


def _validate_used_acknowledgement(
    finding_id: str,
    entry: dict[str, Any],
    *,
    today: date,
) -> list[str]:
    """Validate the full governance record only when it would authorize a finding."""
    problems: list[str] = []
    for required_field in ("owner", "reason", "approved_by", "migration_plan"):
        value = entry.get(required_field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"acknowledgement {finding_id!r} is missing a non-empty {required_field!r}")

    consumers = entry.get("affected_consumers")
    if (
        not isinstance(consumers, list)
        or not consumers
        or any(not isinstance(consumer, str) or not consumer.strip() for consumer in consumers)
    ):
        problems.append(
            f"acknowledgement {finding_id!r} must contain a non-empty 'affected_consumers' string list"
        )

    expires_at = entry.get("expires_at")
    expiry: date | None = None
    if not isinstance(expires_at, str) or _ISO_DATE_RE.fullmatch(expires_at) is None:
        problems.append(f"acknowledgement {finding_id!r} must contain expires_at as YYYY-MM-DD")
    else:
        try:
            expiry = date.fromisoformat(expires_at)
        except ValueError:
            problems.append(f"acknowledgement {finding_id!r} must contain a valid expires_at date")
    if expiry is not None and expiry < today:
        problems.append(f"acknowledgement {finding_id!r} expired before this gate evaluation")
    return problems


def _acknowledgements_sha256() -> str | None:
    try:
        return _sha256_bytes(ACKNOWLEDGEMENTS_PATH.read_bytes())
    except OSError:
        return None


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
    lines.append(f"receipt status: {report['status']}")
    lines.append(f"release gate eligible: {'yes' if report['release_gate_eligible'] else 'no'}")
    lines.append("")

    if report["baseline_problems"]:
        lines.append("Baseline problems:")
        for problem in report["baseline_problems"]:
            surface = f" ({problem['surface']})" if problem.get("surface") else ""
            lines.append(f"  - {problem['code']}{surface}")
        lines.append("")

    for surface_report in report["surfaces"]:
        surface = surface_report["surface"]
        lines.append(f"[{surface}] {surface_report['operation_count']} operations")
        if surface_report["baseline_missing"]:
            if report["allow_bootstrap_baseline"]:
                lines.append("  - compared commit has no baseline; diagnostic bootstrap was explicitly allowed")
            else:
                lines.append(
                    "  ! compared commit has no baseline; rerun only with --allow-bootstrap-baseline to diagnose"
                )
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

    result_label = {
        "passed": "PASS",
        "diagnostic": "DIAGNOSTIC",
        "failed": "FAIL",
    }.get(report["status"], "FAIL")
    lines.append(f"RESULT: {result_label}")
    if report["status"] == "failed":
        lines.append("")
        lines.append(
            "A breaking change needs an explicit, reviewable acknowledgement entry in "
            f"{BASELINE_DIR_NAME}/{ACKNOWLEDGEMENTS_NAME} with owner, reason, approved_by, affected_consumers, "
            "migration_plan, and an unexpired expires_at, plus an updated snapshot."
        )
    return "\n".join(lines)


def _baseline_check(
    surfaces: tuple[str, ...],
    baseline_ref: str | None,
    allow_stale_baseline: bool,
    json_output: str | None,
    allow_bootstrap_baseline: bool = False,
    *,
    today: date | None = None,
    derive_missing_baseline: Path | None = None,
) -> int:
    acknowledgements, acknowledgement_problems = load_acknowledgements()
    acknowledgement_digest = _acknowledgements_sha256()
    used_acknowledgements: set[str] = set()
    matched_acknowledgements: set[str] = set()
    command_succeeded = not acknowledgement_problems
    evaluation_date = today or datetime.now(timezone.utc).date()
    baseline_problems: list[dict[str, str]] = []
    surface_reports: list[dict[str, Any]] = []
    derived_baselines: dict[str, tuple[dict[str, Any], dict[str, Any]]] | None = None
    derivation_failed = False

    resolved_baseline_commit: str | None = None
    if baseline_ref:
        try:
            resolved_baseline_commit = _resolve_baseline_ref(baseline_ref)
        except BaselineGitError:
            command_succeeded = False
            baseline_problems.append({"code": "baseline_ref_unresolved"})

    for surface in surfaces:
        head_spec = _load_openapi(surface)
        head_text = _canonical_json(head_spec)
        relative_path = baseline_relative_path(surface)
        baseline_error: str | None = None
        baseline_provenance: dict[str, Any] | None = None

        if baseline_ref:
            if resolved_baseline_commit is None:
                base_spec = None
                baseline_error = "baseline_ref_unresolved"
            else:
                try:
                    base_spec = _read_baseline_from_ref(resolved_baseline_commit, relative_path)
                    if base_spec is None and derive_missing_baseline is not None:
                        if derived_baselines is None and not derivation_failed:
                            missing_surfaces = []
                            for candidate in surfaces:
                                try:
                                    if _read_baseline_from_ref(resolved_baseline_commit, baseline_relative_path(candidate)) is None:
                                        missing_surfaces.append(candidate)
                                except BaselineGitError:
                                    # Corrupt or unreadable snapshots never use source fallback.
                                    continue
                            try:
                                derived_baselines = _derive_openapi_baselines(
                                    resolved_baseline_commit, tuple(missing_surfaces), derive_missing_baseline,
                                )
                            except BaselineGitError:
                                derivation_failed = True
                        if derivation_failed or surface not in (derived_baselines or {}):
                            raise BaselineGitError("exact base source derivation failed")
                        base_spec, baseline_provenance = derived_baselines[surface]
                except BaselineGitError:
                    base_spec = None
                    baseline_error = "baseline_read_failed"
                    command_succeeded = False
                    baseline_problems.append({"code": baseline_error, "surface": surface})
        else:
            base_spec = _read_baseline_from_disk(surface)

        disk_text = baseline_path(surface).read_text(encoding="utf-8") if baseline_path(surface).exists() else None
        stale_baseline = disk_text != head_text
        baseline_missing = base_spec is None and baseline_error is None
        if baseline_ref and resolved_baseline_commit is not None and baseline_missing:
            baseline_problems.append({"code": "baseline_missing", "surface": surface})
            if not allow_bootstrap_baseline:
                command_succeeded = False

        findings = diff_contracts(surface, base_spec, head_spec) if base_spec is not None else []
        for finding in findings:
            if finding["severity"] != BREAKING:
                continue
            for candidate in acknowledgement_candidate_ids(finding):
                entry = acknowledgements.get(candidate)
                if entry is None:
                    continue
                matched_acknowledgements.add(candidate)
                entry_problems = _validate_used_acknowledgement(
                    candidate,
                    entry,
                    today=evaluation_date,
                )
                if entry_problems:
                    acknowledgement_problems.extend(entry_problems)
                    finding["acknowledgement_rejected"] = True
                    command_succeeded = False
                else:
                    finding["acknowledged"] = True
                    finding["acknowledgement_id"] = candidate
                    used_acknowledgements.add(candidate)
                break

        unacknowledged = [
            finding
            for finding in findings
            if finding["severity"] == BREAKING and not finding.get("acknowledged")
        ]
        if unacknowledged or (stale_baseline and not allow_stale_baseline):
            command_succeeded = False

        surface_reports.append(
            {
                "surface": surface,
                "operation_count": len(extract_contract(head_spec)),
                "baseline_missing": baseline_missing,
                "baseline_error": baseline_error,
                "stale_baseline": stale_baseline,
                "baseline_sha256": _spec_sha256(base_spec) if base_spec is not None else None,
                "baseline_origin": "derived_source" if baseline_provenance is not None else "committed_snapshot",
                "baseline_provenance": baseline_provenance,
                "head_sha256": _spec_sha256(head_spec),
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

    acknowledgement_problems = list(dict.fromkeys(acknowledgement_problems))
    release_gate_eligible = (
        command_succeeded
        and baseline_ref is not None
        and resolved_baseline_commit is not None
        and not allow_stale_baseline
        and not allow_bootstrap_baseline
        and acknowledgement_digest is not None
        and not baseline_problems
        and not any(surface_report["baseline_missing"] for surface_report in surface_reports)
    )
    status = "passed" if release_gate_eligible else ("diagnostic" if command_succeeded else "failed")
    report = {
        "schema_version": 2,
        "receipt_kind": "openapi_contract_gate",
        "status": status,
        "outcome": status,
        "evaluated_on": evaluation_date.isoformat(),
        "baseline_source": (
            f"git commit {resolved_baseline_commit}"
            if resolved_baseline_commit is not None
            else ("unresolved git ref" if baseline_ref else "working tree")
        ),
        "resolved_baseline_commit": resolved_baseline_commit,
        "allow_stale_baseline": allow_stale_baseline,
        "allow_bootstrap_baseline": allow_bootstrap_baseline,
        "baseline_problems": baseline_problems,
        "surfaces": surface_reports,
        "acknowledgements_sha256": acknowledgement_digest,
        "acknowledgement_problems": acknowledgement_problems,
        "used_acknowledgements": sorted(used_acknowledgements),
        "unused_acknowledgements": sorted(set(acknowledgements) - matched_acknowledgements),
        "release_gate_eligible": release_gate_eligible,
        "command_succeeded": command_succeeded,
        "passed": release_gate_eligible,
    }
    report["receipt_sha256"] = _receipt_sha256(report)

    print(_render_report(report))
    if json_output:
        target = Path(json_output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if command_succeeded else 1


def schemathesis_command(schema_path: str = ".codex-tmp/openapi.json", base_url: str = "http://127.0.0.1:7888") -> str:
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
    check_parser.add_argument(
        "--allow-bootstrap-baseline",
        action="store_true",
        help=(
            "Allow a diagnostic run when a valid compared commit has no baseline file. "
            "The resulting receipt is never release-gate eligible."
        ),
    )
    check_parser.add_argument("--json", dest="json_output", default=None, help="Write the machine-readable report here.")
    check_parser.add_argument(
        "--derive-missing-baseline", metavar="SOURCE_PARENT", type=Path,
        help="derive absent trusted snapshots from exact base source in an isolated .codex-tmp directory",
    )

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
        if args.derive_missing_baseline and (not args.baseline_ref or args.allow_bootstrap_baseline):
            parser.error("--derive-missing-baseline requires --baseline-ref and cannot use diagnostic bootstrap")
        return _baseline_check(
            tuple(args.surfaces or BASELINE_SURFACES),
            args.baseline_ref,
            args.allow_stale_baseline,
            args.json_output,
            args.allow_bootstrap_baseline,
            derive_missing_baseline=args.derive_missing_baseline,
        )
    if args.command == "schemathesis-command":
        return _print_schemathesis_command()
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
