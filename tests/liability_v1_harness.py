from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "liability_v1_samples"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
TEMPLATE_PATH = FIXTURE_DIR / "manifest.template.json"
DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
AUTHORITY_MATRIX_PATH = DOCS_DIR / "liability_v1_field_authority_matrix.md"
GATES_DOC_PATH = DOCS_DIR / "liability_v1_compatibility_gates.md"


@dataclass(frozen=True)
class InterfaceSpec:
    sample_key: str
    path: str
    compatibility_oracle: str = "v1_payload"
    semantic_oracle: str = "authority_matrix"
    monthly_basis_gate_required: bool = False


INTERFACE_SPECS: dict[str, InterfaceSpec] = {
    "risk_buckets": InterfaceSpec(
        sample_key="risk_buckets",
        path="/api/risk/buckets",
    ),
    "yield_metrics": InterfaceSpec(
        sample_key="yield_metrics",
        path="/api/analysis/yield_metrics",
    ),
    "liabilities_counterparty": InterfaceSpec(
        sample_key="liabilities_counterparty",
        path="/api/analysis/liabilities/counterparty",
    ),
    "liabilities_monthly": InterfaceSpec(
        sample_key="liabilities_monthly",
        path="/api/liabilities/monthly",
        monthly_basis_gate_required=True,
    ),
}


@dataclass(frozen=True)
class SampleCase:
    sample_id: str
    interface: str
    request: dict[str, Any]
    expected: dict[str, Any]
    source: dict[str, Any]
    raw: dict[str, Any]

    @property
    def spec(self) -> InterfaceSpec:
        try:
            return INTERFACE_SPECS[self.interface]
        except KeyError as exc:
            raise pytest.UsageError(f"Unknown liability V1 sample interface: {self.interface}") from exc

    @property
    def compatibility_payload(self) -> dict[str, Any]:
        return dict(self.expected.get("compatibility", {}).get("payload", {}))

    @property
    def compatibility_oracle(self) -> str:
        return str(self.expected.get("compatibility", {}).get("oracle", "")).strip()

    @property
    def semantic_contract(self) -> dict[str, Any]:
        return dict(self.expected.get("semantic", {}))

    @property
    def semantic_oracle(self) -> str:
        return str(self.semantic_contract.get("oracle", "")).strip()


def load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise pytest.UsageError(f"Expected JSON object in {path}")
    return data


def load_template_manifest() -> dict[str, Any]:
    return load_json_file(TEMPLATE_PATH)


def load_real_manifest_or_skip() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        pytest.skip(
            "No liability V1 sample manifest found. Copy "
            f"{TEMPLATE_PATH.name} to manifest.json and fill real V1 payloads first."
        )
    manifest = load_json_file(MANIFEST_PATH)
    replay_enabled = manifest.get("replay_enabled")
    if replay_enabled is False:
        pytest.skip(
            "Liability V1 manifest exists but replay is disabled. "
            "Promote the draft manifest to replay_enabled=true only after real or approved quasi-real samples are ready."
        )
    return manifest


def sample_cases_from_manifest(manifest: dict[str, Any]) -> list[SampleCase]:
    raw_samples = manifest.get("samples")
    if not isinstance(raw_samples, list) or not raw_samples:
        raise pytest.UsageError("Liability V1 sample manifest must contain a non-empty samples list.")

    cases: list[SampleCase] = []
    for raw_sample in raw_samples:
        if not isinstance(raw_sample, dict):
            raise pytest.UsageError("Each liability V1 sample entry must be a JSON object.")
        cases.append(
            SampleCase(
                sample_id=str(raw_sample.get("sample_id", "")).strip(),
                interface=str(raw_sample.get("interface", "")).strip(),
                request=dict(raw_sample.get("request", {})),
                expected=dict(raw_sample.get("expected", {})),
                source=dict(raw_sample.get("source", {})),
                raw=raw_sample,
            )
        )
    return cases


def require_replay_duckdb_path(manifest: dict[str, Any]) -> str:
    env_name = str(manifest.get("duckdb_path_env", "MOSS_DUCKDB_PATH")).strip() or "MOSS_DUCKDB_PATH"
    duckdb_path = os.getenv(env_name, "").strip()
    if not duckdb_path:
        pytest.skip(f"Set {env_name} before replaying liability V1 samples against the current API.")
    return duckdb_path


def load_text_file(path: Path) -> str:
    if not path.exists():
        raise pytest.UsageError(f"Missing required artifact: {path}")
    return path.read_text(encoding="utf-8")


def load_authority_matrix_text() -> str:
    return load_text_file(AUTHORITY_MATRIX_PATH)


def load_gates_doc_text() -> str:
    return load_text_file(GATES_DOC_PATH)


def authority_field_paths(case: SampleCase) -> list[str]:
    fields = case.semantic_contract.get("authority_field_paths", [])
    if not isinstance(fields, list):
        raise pytest.UsageError(f"{case.sample_id}: semantic.authority_field_paths must be a list.")
    return [str(field).strip() for field in fields if str(field).strip()]


def semantic_gate_findings(case: SampleCase) -> list[str]:
    matrix_text = load_authority_matrix_text()
    gates_text = load_gates_doc_text()
    findings: list[str] = []

    if case.spec.path not in matrix_text:
        findings.append(f"{case.sample_id}: interface path missing from authority matrix")

    if "V1 compatibility seam" not in matrix_text:
        findings.append(f"{case.sample_id}: authority matrix does not declare seam identity")

    for field_path in authority_field_paths(case):
        if field_path not in matrix_text:
            findings.append(f"{case.sample_id}: authority field path missing from matrix: {field_path}")

    if "compatibility seam gate" not in gates_text:
        findings.append(f"{case.sample_id}: compatibility seam gate missing from gate doc")

    if "governed surface gate" not in gates_text:
        findings.append(f"{case.sample_id}: governed surface gate missing from gate doc")

    if case.spec.monthly_basis_gate_required:
        for token in ("observed", "locf", "calendar_zero"):
            if token not in gates_text:
                findings.append(f"{case.sample_id}: monthly basis token missing from gate doc: {token}")

    return findings


def compatibility_diffs(actual: Any, expected: Any, *, path: str = "$") -> list[str]:
    diffs: list[str] = []

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {type(actual).__name__}"]

        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            diffs.append(f"{path}.{key}: missing in actual payload")
        for key in sorted(actual_keys - expected_keys):
            diffs.append(f"{path}.{key}: unexpected field in actual payload")
        for key in sorted(expected_keys & actual_keys):
            diffs.extend(compatibility_diffs(actual[key], expected[key], path=f"{path}.{key}"))
        return diffs

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected list, got {type(actual).__name__}"]
        if len(actual) != len(expected):
            diffs.append(f"{path}: expected list length {len(expected)}, got {len(actual)}")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected, strict=False)):
            diffs.extend(compatibility_diffs(actual_item, expected_item, path=f"{path}[{index}]"))
        return diffs

    if actual != expected:
        diffs.append(f"{path}: expected {expected!r}, got {actual!r}")
    return diffs


def summarize_diffs(diffs: list[str]) -> str:
    return "\n".join(f"- {diff}" for diff in diffs)


def monthly_basis_gate(case: SampleCase) -> dict[str, Any]:
    return dict(case.semantic_contract.get("basis_gate", {}))
