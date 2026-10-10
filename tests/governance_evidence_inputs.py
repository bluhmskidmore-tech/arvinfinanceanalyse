"""Explicit synthetic inputs for evidence renderer tests, without private records.

These inputs validate catalog anchors and required record fields. They do not
prove historical command executions, live screenshots, or owner approval.
"""

import json
from pathlib import Path

import pytest

from scripts.mcp.moss_project_mcp import (
    PAGE_CATALOG_DATE_TABLES,
    page_trace_bundle,
    product_page_trace_bundles,
)
from tests.readiness_input_snapshot import build_readiness_input_snapshot_env


@pytest.fixture
def governance_evidence_inputs(tmp_path: Path, monkeypatch) -> dict[str, str]:
    inputs_root = tmp_path / "synthetic-readiness-inputs"
    inputs_root.mkdir()
    env = build_readiness_input_snapshot_env(inputs_root)
    # Average Balance is optional in the shared readiness snapshot, but its
    # evidence renderer needs a complete direct record for the ready case.
    bundle = page_trace_bundle(product_page_trace_bundles(), "average-balance")
    record = {
        "page_id": bundle["page_id"],
        "page_slug": "average-balance",
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "report_date": "2026-05-31",
        "basis": "analytical",
        "source_surface": "synthetic_readiness_fixture",
        "tables_used": PAGE_CATALOG_DATE_TABLES[bundle["page_id"]],
        "source_version": "sv_synthetic_readiness_average-balance",
        "rule_version": "rv_synthetic_readiness_v1",
        "created_at": "2026-06-01T00:00:00Z",
        "cache_key": "synthetic-readiness:average-balance:2026-05-31",
        "formal_use_allowed": False,
    }
    manifest = Path(env["MOSS_GOVERNANCE_PATH"]) / "cache_manifest.jsonl"
    with manifest.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return env
