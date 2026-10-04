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
import subprocess
from datetime import date
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


def test_legacy_unused_acknowledgements_remain_structurally_valid() -> None:
    assert ACKNOWLEDGEMENTS_PATH.exists()
    acknowledgements, problems = contract_module.load_acknowledgements()
    assert problems == []
    assert acknowledgements
    assert all(finding_id.strip() for finding_id in acknowledgements)


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


# --------------------------------------------------------------------------------------
# Release-control receipt and base-ref hardening
# --------------------------------------------------------------------------------------


def _probe_spec(*, include_operation: bool) -> dict[str, Any]:
    paths: dict[str, Any] = {}
    if include_operation:
        paths["/api/contract-probe"] = {
            "get": {
                "operationId": "contract_probe_get",
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"value": {"type": "string"}},
                                    "required": ["value"],
                                }
                            }
                        },
                    }
                },
            }
        }
    return {
        "openapi": "3.1.0",
        "info": {"title": "contract probe", "version": "1"},
        "paths": paths,
    }


def _valid_acknowledgement(finding_id: str, *, expires_at: str = "2099-12-31") -> dict[str, Any]:
    return {
        "id": finding_id,
        "owner": "api-platform",
        "reason": "The consumer migration has been reviewed.",
        "approved_by": "release-authority",
        "affected_consumers": ["moss-frontend"],
        "migration_plan": "Deploy the compatible frontend before removing the old field.",
        "expires_at": expires_at,
    }


def _run_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    base_spec: dict[str, Any] | None,
    head_spec: dict[str, Any],
    acknowledgements: dict[str, dict[str, Any]] | None = None,
    baseline_ref: str | None = "origin/main",
    resolve_error: str | None = None,
    allow_bootstrap_baseline: bool = False,
    allow_stale_baseline: bool = False,
    output_name: str = "receipt.json",
) -> tuple[int, dict[str, Any], str]:
    disk_baseline = tmp_path / "openapi.default.json"
    disk_baseline.write_text(contract_module._canonical_json(head_spec), encoding="utf-8")
    output = tmp_path / output_name

    monkeypatch.setattr(contract_module, "_load_openapi", lambda _surface: copy.deepcopy(head_spec))
    monkeypatch.setattr(contract_module, "baseline_path", lambda _surface: disk_baseline)
    monkeypatch.setattr(
        contract_module,
        "load_acknowledgements",
        lambda: (copy.deepcopy(acknowledgements or {}), []),
    )
    monkeypatch.setattr(contract_module, "_acknowledgements_sha256", lambda: "A" * 64)
    if resolve_error is None:
        monkeypatch.setattr(contract_module, "_resolve_baseline_ref", lambda _ref: "b" * 40)
    else:

        def _raise_resolution_error(_ref: str) -> str:
            raise contract_module.BaselineGitError(resolve_error)

        monkeypatch.setattr(contract_module, "_resolve_baseline_ref", _raise_resolution_error)
    monkeypatch.setattr(
        contract_module,
        "_read_baseline_from_ref",
        lambda _commit, _relative_path: copy.deepcopy(base_spec),
    )

    exit_code = contract_module._baseline_check(
        ("default",),
        baseline_ref,
        allow_stale_baseline,
        str(output),
        allow_bootstrap_baseline,
        today=date(2026, 8, 31),
    )
    serialized = output.read_text(encoding="utf-8")
    return exit_code, json.loads(serialized), serialized


def test_invalid_baseline_ref_fails_closed_without_leaking_git_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    head = _probe_spec(include_operation=False)
    exit_code, report, serialized = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=None,
        head_spec=head,
        resolve_error=r"fatal: unsafe repository at C:\private\checkout",
    )

    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["release_gate_eligible"] is False
    assert report["resolved_baseline_commit"] is None
    assert report["baseline_problems"] == [{"code": "baseline_ref_unresolved"}]
    assert "private" not in serialized
    assert "fatal:" not in serialized


def test_git_ref_resolution_error_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failed_git(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["git"],
            returncode=128,
            stdout="",
            stderr=r"fatal: C:\private\repository is unsafe",
        )

    monkeypatch.setattr(contract_module.subprocess, "run", _failed_git)

    with pytest.raises(contract_module.BaselineGitError) as raised:
        contract_module._resolve_baseline_ref("origin/main")
    assert str(raised.value) == "baseline ref could not be resolved"
    assert "private" not in str(raised.value)


def test_git_process_start_error_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_os_error(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise OSError(r"cannot execute C:\private\git.exe")

    monkeypatch.setattr(contract_module.subprocess, "run", _raise_os_error)

    with pytest.raises(contract_module.BaselineGitError) as raised:
        contract_module._resolve_baseline_ref("origin/main")
    assert str(raised.value) == "baseline ref could not be resolved"
    assert "private" not in str(raised.value)


def test_valid_commit_with_no_baseline_path_is_reported_as_missing() -> None:
    resolved = contract_module._resolve_baseline_ref("HEAD")

    assert (
        contract_module._read_baseline_from_ref(
            resolved,
            "contracts/openapi/__wp3_missing_baseline__.json",
        )
        is None
    )


def test_missing_baseline_on_valid_ref_fails_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    exit_code, report, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=None,
        head_spec=_probe_spec(include_operation=False),
    )

    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["release_gate_eligible"] is False
    assert report["surfaces"][0]["baseline_missing"] is True
    assert report["surfaces"][0]["baseline_sha256"] is None


def test_explicit_bootstrap_is_diagnostic_but_never_release_eligible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, report, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=None,
        head_spec=_probe_spec(include_operation=False),
        allow_bootstrap_baseline=True,
    )
    console = capsys.readouterr().out

    assert exit_code == 0
    assert report["command_succeeded"] is True
    assert report["passed"] is False
    assert report["status"] == report["outcome"] == "diagnostic"
    assert report["release_gate_eligible"] is False
    assert "RESULT: DIAGNOSTIC" in console
    assert "RESULT: PASS" not in console


def test_same_pr_snapshot_rewrite_cannot_clear_base_ref_breaking_finding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = _probe_spec(include_operation=True)
    head = _probe_spec(include_operation=False)
    exit_code, report, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=base,
        head_spec=head,
    )

    assert exit_code == 1
    surface = report["surfaces"][0]
    assert surface["stale_baseline"] is False
    assert surface["counts"]["breaking"] == 1
    assert surface["baseline_sha256"] == contract_module._spec_sha256(base)
    assert surface["head_sha256"] == contract_module._spec_sha256(head)


def test_used_legacy_acknowledgement_does_not_authorize_a_breaking_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = _probe_spec(include_operation=True)
    head = _probe_spec(include_operation=False)
    finding = _breaking(contract_module.diff_contracts("default", base, head))[0]
    legacy = {
        "id": finding["id"],
        "reason": "Legacy reason only.",
        "approved_by": "legacy-approver",
    }

    exit_code, report, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=base,
        head_spec=head,
        acknowledgements={finding["id"]: legacy},
    )

    assert exit_code == 1
    assert report["surfaces"][0]["counts"] == {
        "breaking": 1,
        "acknowledged": 0,
        "additive": 0,
        "tightened": 0,
    }
    assert any("owner" in problem for problem in report["acknowledgement_problems"])
    assert any("affected_consumers" in problem for problem in report["acknowledgement_problems"])
    assert any("migration_plan" in problem for problem in report["acknowledgement_problems"])
    assert any("expires_at" in problem for problem in report["acknowledgement_problems"])


def test_complete_unexpired_used_acknowledgement_can_authorize_the_finding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = _probe_spec(include_operation=True)
    head = _probe_spec(include_operation=False)
    finding = _breaking(contract_module.diff_contracts("default", base, head))[0]

    exit_code, report, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=base,
        head_spec=head,
        acknowledgements={finding["id"]: _valid_acknowledgement(finding["id"])},
    )

    assert exit_code == 0
    assert report["command_succeeded"] is True
    assert report["passed"] is True
    assert report["status"] == report["outcome"] == "passed"
    assert report["release_gate_eligible"] is True
    assert report["surfaces"][0]["counts"]["acknowledged"] == 1
    assert report["used_acknowledgements"] == [finding["id"]]


def test_expired_used_acknowledgement_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base = _probe_spec(include_operation=True)
    head = _probe_spec(include_operation=False)
    finding = _breaking(contract_module.diff_contracts("default", base, head))[0]

    exit_code, report, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=base,
        head_spec=head,
        acknowledgements={
            finding["id"]: _valid_acknowledgement(finding["id"], expires_at="2026-08-30")
        },
    )

    assert exit_code == 1
    assert report["surfaces"][0]["counts"]["acknowledged"] == 0
    assert any("expired" in problem for problem in report["acknowledgement_problems"])


def test_duplicate_acknowledgement_ids_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    acknowledgement_path = tmp_path / "acknowledgements.json"
    duplicate_id = "*|operation_removed|GET /api/example|-"
    acknowledgement_path.write_text(
        json.dumps(
            {
                "acknowledgements": [
                    _valid_acknowledgement(duplicate_id),
                    _valid_acknowledgement(duplicate_id),
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(contract_module, "ACKNOWLEDGEMENTS_PATH", acknowledgement_path)

    acknowledgements, problems = contract_module.load_acknowledgements()

    assert duplicate_id not in acknowledgements
    assert problems == [f"duplicate acknowledgement id {duplicate_id!r}"]


def test_receipt_digest_is_canonical_and_stable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    unchanged = _probe_spec(include_operation=True)
    first_code, first, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=unchanged,
        head_spec=unchanged,
        output_name="first.json",
    )
    second_code, second, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=unchanged,
        head_spec=unchanged,
        output_name="second.json",
    )

    assert first_code == second_code == 0
    assert first["status"] == "passed"
    assert first["receipt_sha256"] == second["receipt_sha256"]
    assert first["receipt_sha256"] == contract_module._receipt_sha256(first)
    assert len(first["receipt_sha256"]) == 64
    assert first["acknowledgements_sha256"] == "A" * 64


@pytest.mark.parametrize(
    ("baseline_ref", "allow_stale_baseline"),
    [(None, False), ("origin/main", True)],
)
def test_diagnostic_modes_never_emit_a_passed_release_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    baseline_ref: str | None,
    allow_stale_baseline: bool,
) -> None:
    unchanged = _probe_spec(include_operation=True)
    exit_code, report, _ = _run_receipt(
        monkeypatch,
        tmp_path,
        base_spec=unchanged,
        head_spec=unchanged,
        baseline_ref=baseline_ref,
        allow_stale_baseline=allow_stale_baseline,
        output_name=f"diagnostic-{baseline_ref is None}.json",
    )
    console = capsys.readouterr().out

    assert exit_code == 0
    assert report["command_succeeded"] is True
    assert report["passed"] is False
    assert report["status"] == report["outcome"] == "diagnostic"
    assert report["release_gate_eligible"] is False
    assert "RESULT: DIAGNOSTIC" in console
    assert "RESULT: PASS" not in console
