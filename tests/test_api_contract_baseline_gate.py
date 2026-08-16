"""Proof that the OpenAPI baseline gate actually blocks breaking contract changes.

The gate is the only thing standing between a silent backend rename and a page
that renders `undefined`, so it needs its own regression net. Every scenario
below mutates a deep copy of the committed baseline and asserts how
`diff_contracts` classifies the result.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SCRIPT = ROOT / "scripts" / "api_contract_check.py"
BASELINE_DIR = ROOT / "contracts" / "openapi"
BASELINE_SURFACES = ("default", "full")
ACKNOWLEDGEMENTS_PATH = BASELINE_DIR / "breaking-change-acknowledgements.json"


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location("api_contract_check_under_test", CONTRACT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract_module = _load_contract_module()


@pytest.fixture(scope="module")
def baseline() -> dict[str, Any]:
    return json.loads((BASELINE_DIR / "openapi.default.json").read_text(encoding="utf-8"))


def _breaking(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    return [finding for finding in findings if finding["severity"] == "breaking"]


def _kinds(findings: list[dict[str, str]]) -> set[str]:
    return {finding["kind"] for finding in findings}


SCALAR_TYPES = frozenset({"string", "integer", "number", "boolean"})


def _scalar_properties(schema: dict[str, Any]) -> list[str]:
    return sorted(
        name
        for name, sub_schema in (schema.get("properties") or {}).items()
        if isinstance(sub_schema, dict) and sub_schema.get("type") in SCALAR_TYPES
    )


def _pick_operation_with_object_response(spec: dict[str, Any]) -> tuple[str, str]:
    """First GET whose 200 body is a `$ref` to an object carrying a mutable scalar."""
    for path, path_item in sorted(spec["paths"].items()):
        operation = path_item.get("get")
        if not isinstance(operation, dict):
            continue
        media = (((operation.get("responses") or {}).get("200") or {}).get("content") or {}).get("application/json")
        if not isinstance(media, dict) or not isinstance(media.get("schema"), dict):
            continue
        ref = media["schema"].get("$ref")
        if not isinstance(ref, str):
            continue
        target = contract_module._resolve_ref(spec, ref)
        if isinstance(target, dict) and _scalar_properties(target):
            return path, "get"
    raise AssertionError("baseline has no GET operation with a referenced scalar-bearing object response")


def _inline_200_schema(spec: dict[str, Any], path: str, method: str) -> dict[str, Any]:
    """Replace the `$ref` 200 body with its resolved copy so one operation can be mutated alone."""
    media = spec["paths"][path][method]["responses"]["200"]["content"]["application/json"]
    resolved = contract_module._resolve_ref(spec, media["schema"]["$ref"])
    assert resolved is not None
    media["schema"] = copy.deepcopy(resolved)
    return media["schema"]


def _pick_scalar_property(schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    names = _scalar_properties(schema)
    assert names, "response object has no scalar property to mutate"
    return names[0], schema["properties"][names[0]]


def _pick_optional_query_parameter(spec: dict[str, Any]) -> tuple[str, str, str]:
    for path, path_item in sorted(spec["paths"].items()):
        for method, operation in sorted(path_item.items()):
            if not isinstance(operation, dict):
                continue
            for index, parameter in enumerate(operation.get("parameters") or []):
                if (
                    isinstance(parameter, dict)
                    and parameter.get("in") == "query"
                    and not parameter.get("required")
                ):
                    return path, method, str(index)
    raise AssertionError("baseline has no optional query parameter")


# --------------------------------------------------------------------------------------
# The committed artifacts
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("surface", BASELINE_SURFACES)
def test_baseline_snapshot_is_committed_and_parses(surface: str) -> None:
    path = BASELINE_DIR / f"openapi.{surface}.json"
    assert path.exists(), f"missing committed OpenAPI baseline for the {surface} surface"
    spec = json.loads(path.read_text(encoding="utf-8"))
    assert spec["openapi"].startswith("3.")
    assert spec["paths"], "baseline snapshot has no paths"


def test_baseline_snapshots_are_canonically_serialized() -> None:
    """Byte-stable snapshots keep the review diff about meaning, not key ordering."""
    for surface in BASELINE_SURFACES:
        path = BASELINE_DIR / f"openapi.{surface}.json"
        text = path.read_text(encoding="utf-8")
        assert text == contract_module._canonical_json(json.loads(text))


def test_default_surface_baseline_excludes_feature_gated_agent_routes() -> None:
    default_spec = json.loads((BASELINE_DIR / "openapi.default.json").read_text(encoding="utf-8"))
    full_spec = json.loads((BASELINE_DIR / "openapi.full.json").read_text(encoding="utf-8"))

    assert not [path for path in default_spec["paths"] if path.startswith("/api/agent")]
    assert [path for path in full_spec["paths"] if path.startswith("/api/agent")]
    assert set(default_spec["paths"]) < set(full_spec["paths"])


def test_acknowledgement_file_is_valid_and_entries_are_justified() -> None:
    assert ACKNOWLEDGEMENTS_PATH.exists()
    acknowledgements, problems = contract_module.load_acknowledgements()
    assert problems == []
    for finding_id, entry in acknowledgements.items():
        assert entry["reason"].strip(), f"acknowledgement {finding_id} has an empty reason"
        assert entry["approved_by"].strip(), f"acknowledgement {finding_id} has no approver"


# --------------------------------------------------------------------------------------
# Breaking-change detection
# --------------------------------------------------------------------------------------


def test_identical_spec_produces_no_findings(baseline: dict[str, Any]) -> None:
    assert contract_module.diff_contracts("default", baseline, copy.deepcopy(baseline)) == []


def test_inlining_a_ref_is_not_reported_as_a_change(baseline: dict[str, Any]) -> None:
    """`$ref` resolution must compare the referenced shape, not the reference itself."""
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    _inline_200_schema(head, path, method)

    assert contract_module.diff_contracts("default", baseline, head) == []


def test_removed_operation_is_breaking(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    del head["paths"][path][method]

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert [finding["kind"] for finding in findings] == ["operation_removed"]
    assert findings[0]["operation"] == f"{method.upper()} {path}"


def test_removed_response_field_is_breaking(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    schema = _inline_200_schema(head, path, method)
    field_name, _ = _pick_scalar_property(schema)
    del schema["properties"][field_name]
    if field_name in schema.get("required", []):
        schema["required"].remove(field_name)

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert _kinds(findings) == {"response_field_removed"}
    assert findings[0]["target"] == f"response 200:{field_name}"


def test_renamed_response_field_is_breaking(baseline: dict[str, Any]) -> None:
    """The audit's motivating case: `result.total_pnl` -> `result.pnl_total`."""
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    schema = _inline_200_schema(head, path, method)
    field_name, field_schema = _pick_scalar_property(schema)
    del schema["properties"][field_name]
    schema["properties"][f"{field_name}_renamed"] = field_schema
    if field_name in schema.get("required", []):
        schema["required"] = [f"{field_name}_renamed" if n == field_name else n for n in schema["required"]]

    findings = contract_module.diff_contracts("default", baseline, head)
    assert "response_field_removed" in _kinds(_breaking(findings))
    assert "response_field_added" in _kinds(findings)


def test_response_field_type_change_is_breaking(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    schema = _inline_200_schema(head, path, method)
    field_name, field_schema = _pick_scalar_property(schema)
    field_schema["type"] = "boolean" if field_schema["type"] != "boolean" else "string"

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert _kinds(findings) == {"response_field_type_changed"}
    assert findings[0]["target"] == f"response 200:{field_name}"


def test_response_field_losing_its_guarantee_is_breaking(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    schema = _inline_200_schema(head, path, method)
    field_name, _ = _pick_scalar_property(schema)
    if field_name not in schema.get("required", []):
        pytest.skip("chosen scalar response property is already optional")
    schema["required"] = [name for name in schema["required"] if name != field_name]

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert _kinds(findings) == {"response_field_became_optional"}
    assert findings[0]["target"] == f"response 200:{field_name}"


def test_response_losing_its_schema_is_breaking(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    del head["paths"][path][method]["responses"]["200"]["content"]

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert _kinds(findings) == {"response_schema_removed"}


def test_parameter_becoming_required_is_breaking(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method, index = _pick_optional_query_parameter(baseline)
    head["paths"][path][method]["parameters"][int(index)]["required"] = True

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert _kinds(findings) == {"parameter_became_required"}


def test_parameter_type_change_and_removal_are_breaking(baseline: dict[str, Any]) -> None:
    path, method, index = _pick_optional_query_parameter(baseline)

    retyped = copy.deepcopy(baseline)
    parameter = retyped["paths"][path][method]["parameters"][int(index)]
    parameter["schema"] = {"type": "boolean"}
    assert _kinds(_breaking(contract_module.diff_contracts("default", baseline, retyped))) == {
        "request_field_type_changed"
    }

    removed = copy.deepcopy(baseline)
    del removed["paths"][path][method]["parameters"][int(index)]
    assert _kinds(_breaking(contract_module.diff_contracts("default", baseline, removed))) == {"parameter_removed"}


def test_new_required_parameter_is_breaking(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    head["paths"][path][method].setdefault("parameters", []).append(
        {"name": "mandatory_new_filter", "in": "query", "required": True, "schema": {"type": "string"}}
    )

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert _kinds(findings) == {"required_parameter_added"}


def test_operation_id_change_is_breaking(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    head["paths"][path][method]["operationId"] += "_v2"

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert _kinds(findings) == {"operation_id_changed"}


# --------------------------------------------------------------------------------------
# Additive changes must stay out of the way
# --------------------------------------------------------------------------------------


def test_new_operation_is_additive_only(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    head["paths"]["/api/brand-new-surface"] = {
        "get": {
            "operationId": "brand_new_surface_get",
            "responses": {
                "200": {
                    "description": "ok",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            },
        }
    }

    findings = contract_module.diff_contracts("default", baseline, head)
    assert _breaking(findings) == []
    assert _kinds(findings) == {"operation_added"}


def test_new_optional_parameter_and_new_response_field_are_additive(baseline: dict[str, Any]) -> None:
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    head["paths"][path][method].setdefault("parameters", []).append(
        {"name": "optional_new_filter", "in": "query", "required": False, "schema": {"type": "string"}}
    )
    schema = _inline_200_schema(head, path, method)
    schema["properties"]["brand_new_field"] = {"type": "string"}

    findings = contract_module.diff_contracts("default", baseline, head)
    assert _breaking(findings) == []
    assert _kinds(findings) == {"optional_parameter_added", "response_field_added"}


@pytest.mark.parametrize(
    "opaque_schema",
    [
        pytest.param({"additionalProperties": True, "type": "object"}, id="response_model-dict"),
        pytest.param({}, id="no-response_model"),
    ],
)
def test_replacing_a_free_form_body_with_a_real_schema_is_a_coverage_gain(
    baseline: dict[str, Any],
    opaque_schema: dict[str, Any],
) -> None:
    """`response_model=dict` -> a real envelope must not read as a removal.

    The flattener represents a body that names no field as the single anonymous
    entry ".", so a per-field diff sees that entry disappear. Blocking that would
    make the gate punish exactly the work that gives it something to guard.
    """
    path, method = _pick_operation_with_object_response(baseline)
    base = copy.deepcopy(baseline)
    base["paths"][path][method]["responses"]["200"]["content"]["application/json"]["schema"] = copy.deepcopy(
        opaque_schema
    )

    findings = contract_module.diff_contracts("default", base, copy.deepcopy(baseline))

    assert _breaking(findings) == []
    tightened = [finding for finding in findings if finding["kind"] == "response_contract_tightened"]
    assert [finding["operation"] for finding in tightened] == [f"{method.upper()} {path}"]
    assert tightened[0]["target"] == "200"


def test_replacing_a_real_schema_with_a_free_form_body_is_breaking(baseline: dict[str, Any]) -> None:
    """The inverse of the coverage gain: giving up field-level governance."""
    head = copy.deepcopy(baseline)
    path, method = _pick_operation_with_object_response(baseline)
    head["paths"][path][method]["responses"]["200"]["content"]["application/json"]["schema"] = {
        "additionalProperties": True,
        "type": "object",
    }

    findings = _breaking(contract_module.diff_contracts("default", baseline, head))
    assert _kinds(findings) == {"response_contract_loosened"}
    assert findings[0]["operation"] == f"{method.upper()} {path}"


def test_tightening_allowance_does_not_apply_to_request_bodies(baseline: dict[str, Any]) -> None:
    """Narrowing what a client may send stays breaking; only responses get the pass."""
    base = copy.deepcopy(baseline)
    head = copy.deepcopy(baseline)
    path = "/api/contract-gate-probe"
    for spec, body_schema in (
        (base, {"additionalProperties": True, "type": "object"}),
        (head, {"type": "object", "properties": {"only_this": {"type": "string"}}, "required": ["only_this"]}),
    ):
        spec["paths"][path] = {
            "post": {
                "operationId": "contract_gate_probe_post",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": body_schema}},
                },
                "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {}}}}},
            }
        }

    findings = contract_module.diff_contracts("default", base, head)
    assert "required_request_field_added" in _kinds(_breaking(findings))


def test_a_missing_baseline_bootstraps_instead_of_failing(baseline: dict[str, Any]) -> None:
    """The first pull request that introduces a surface has nothing to diff against."""
    findings = contract_module.diff_contracts("default", {"paths": {}}, baseline)
    assert _breaking(findings) == []
    assert _kinds(findings) == {"operation_added"}


# --------------------------------------------------------------------------------------
# The escape hatch
# --------------------------------------------------------------------------------------


def test_acknowledgement_ids_are_stable_and_surface_agnostic_form_is_offered() -> None:
    finding = contract_module._finding(
        "default", "breaking", "operation_removed", "GET /api/foo", "-", "gone"
    )
    exact, wildcard = contract_module.acknowledgement_candidate_ids(finding)

    assert exact == "default|operation_removed|GET /api/foo|-"
    assert wildcard == "*|operation_removed|GET /api/foo|-"
