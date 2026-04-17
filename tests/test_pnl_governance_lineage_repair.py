from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import load_module


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_repair_pnl_governance_lineage_normalizes_dirty_versions_and_keeps_backup(tmp_path):
    module = load_module(
        "scripts.repair_pnl_governance_lineage",
        "scripts/repair_pnl_governance_lineage.py",
    )

    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    build_run_path = governance_dir / "cache_build_run.jsonl"
    manifest_path = governance_dir / "cache_manifest.jsonl"

    dirty_source_version = "sv_a__sv_b,sv_c__sv_a"
    _write_jsonl(
        build_run_path,
        [
            {
                "run_id": "pnl-1",
                "job_name": "pnl_materialize",
                "cache_key": "pnl:phase2:materialize:formal",
                "source_version": dirty_source_version,
                "rule_version": "rv_a,rv_b",
            },
            {
                "run_id": "other-1",
                "job_name": "other_job",
                "cache_key": "other.cache",
                "source_version": dirty_source_version,
                "rule_version": "rv_other,rv_keep",
            },
        ],
    )
    _write_jsonl(
        manifest_path,
        [
            {
                "cache_key": "pnl:phase2:materialize:formal",
                "source_version": dirty_source_version,
                "rule_version": "rv_a,rv_b",
            },
        ],
    )

    summary = module.repair_pnl_governance_lineage(governance_dir, apply_changes=True)

    assert summary["files_scanned"] == 2
    assert summary["rows_updated"] == 2
    assert build_run_path.with_suffix(".jsonl.bak").exists()
    assert manifest_path.with_suffix(".jsonl.bak").exists()

    repaired_build_rows = _read_jsonl(build_run_path)
    repaired_manifest_rows = _read_jsonl(manifest_path)

    assert repaired_build_rows[0]["source_version"] == "sv_a__sv_b__sv_c"
    assert repaired_build_rows[0]["rule_version"] == "rv_a__rv_b"
    assert repaired_build_rows[1]["source_version"] == dirty_source_version
    assert repaired_manifest_rows[0]["source_version"] == "sv_a__sv_b__sv_c"
    assert repaired_manifest_rows[0]["rule_version"] == "rv_a__rv_b"
