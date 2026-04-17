from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import load_module


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def test_audit_governance_lineage_reports_dirty_rows_without_mutating_files(tmp_path):
    module = load_module(
        "scripts.audit_governance_lineage",
        "scripts/audit_governance_lineage.py",
    )

    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    build_run_path = governance_dir / "cache_build_run.jsonl"
    manifest_path = governance_dir / "cache_manifest.jsonl"

    _write_jsonl(
        build_run_path,
        [
            {
                "run_id": "pnl-1",
                "cache_key": "pnl:phase2:materialize:formal",
                "job_name": "pnl_materialize",
                "source_version": "sv_a__sv_b,sv_c",
                "rule_version": "rv_a__rv_b",
            },
            {
                "run_id": "risk-1",
                "cache_key": "risk.tensor:formal",
                "job_name": "risk_tensor_materialize",
                "source_version": "sv_x,sv_y",
                "rule_version": "rv_x,rv_y",
            },
            {
                "run_id": "ok-1",
                "cache_key": "clean.cache",
                "job_name": "clean_job",
                "source_version": "sv_clean_a__sv_clean_b",
                "rule_version": "rv_clean_a__rv_clean_b",
            },
        ],
    )
    _write_jsonl(
        manifest_path,
        [
            {
                "cache_key": "pnl:phase2:materialize:formal",
                "source_version": "sv_a__sv_b,sv_c",
                "rule_version": "rv_a__rv_b",
            }
        ],
    )

    original_build_run = build_run_path.read_text(encoding="utf-8")
    original_manifest = manifest_path.read_text(encoding="utf-8")

    summary = module.audit_governance_lineage(governance_dir)

    assert summary["files_scanned"] == 2
    assert summary["rows_scanned"] == 4
    assert summary["dirty_rows"] == 3
    assert summary["dirty_cache_keys"] == 2

    findings = {
        (item["cache_key"], item["field_name"]): item
        for item in summary["findings"]
    }
    assert findings[("pnl:phase2:materialize:formal", "source_version")]["dirty_row_count"] == 2
    assert findings[("pnl:phase2:materialize:formal", "source_version")]["normalized_value"] == "sv_a__sv_b__sv_c"
    assert findings[("risk.tensor:formal", "rule_version")]["normalized_value"] == "rv_x__rv_y"
    assert findings[("risk.tensor:formal", "source_version")]["sample_values"] == ["sv_x,sv_y"]

    assert build_run_path.read_text(encoding="utf-8") == original_build_run
    assert manifest_path.read_text(encoding="utf-8") == original_manifest
