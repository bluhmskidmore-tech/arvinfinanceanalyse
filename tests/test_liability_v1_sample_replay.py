from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import load_module
from tests.liability_v1_harness import (
    compatibility_diffs,
    load_real_manifest_or_skip,
    monthly_basis_gate,
    require_replay_duckdb_path,
    sample_cases_from_manifest,
    semantic_gate_findings,
    summarize_diffs,
)


def _build_client() -> TestClient:
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    return TestClient(main_mod.app)


def test_liability_v1_samples_replay_current_compatibility_surface() -> None:
    manifest = load_real_manifest_or_skip()
    require_replay_duckdb_path(manifest)
    cases = sample_cases_from_manifest(manifest)
    client = _build_client()

    for case in cases:
        response = client.get(case.spec.path, params=case.request)
        assert response.status_code == 200, f"{case.sample_id}: unexpected HTTP {response.status_code}"

        diffs = compatibility_diffs(response.json(), case.compatibility_payload)
        assert not diffs, f"{case.sample_id} compatibility diffs:\n{summarize_diffs(diffs)}"


def test_liability_v1_samples_keep_semantic_contracts_explicit() -> None:
    manifest = load_real_manifest_or_skip()
    cases = sample_cases_from_manifest(manifest)

    for case in cases:
        semantic = case.semantic_contract
        assert semantic.get("oracle") == case.spec.semantic_oracle
        assert semantic.get("status") in {"pending", "approved", "compatibility_only"}
        assert not semantic_gate_findings(case)

        if case.spec.monthly_basis_gate_required:
            gate = monthly_basis_gate(case)
            assert gate.get("status") in {"pending", "approved"}
            assert gate.get("reason")
