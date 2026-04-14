from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import load_module


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_compact_cache_build_run_preserves_latest_record_per_source_preview_run_id(tmp_path):
    module = load_module(
        "scripts.compact_source_preview_governance",
        "scripts/compact_source_preview_governance.py",
    )

    path = tmp_path / "cache_build_run.jsonl"
    rows = [
        {
            "run_id": "r-1",
            "job_name": "source_preview_refresh",
            "status": "running",
            "cache_key": "source_preview.foundation",
        },
        {
            "run_id": "r-1",
            "job_name": "source_preview_refresh",
            "status": "completed",
            "cache_key": "source_preview.foundation",
        },
        {
            "run_id": "r-2",
            "job_name": "source_preview_refresh",
            "status": "running",
            "cache_key": "source_preview.foundation",
        },
        {
            "run_id": "other",
            "job_name": "bond_analytics_materialize",
            "status": "running",
            "cache_key": "bond_analytics:materialize:formal",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    summary = module.compact_cache_build_run(path, apply_changes=True)

    compacted = _read_jsonl(path)
    assert [(row["run_id"], row["status"]) for row in compacted] == [
        ("r-1", "completed"),
        ("r-2", "running"),
        ("other", "running"),
    ]
    assert summary["removed_rows"] == 1


def test_compact_cache_build_run_dry_run_leaves_file_unchanged(tmp_path):
    module = load_module(
        "scripts.compact_source_preview_governance",
        "scripts/compact_source_preview_governance.py",
    )

    path = tmp_path / "cache_build_run.jsonl"
    original = [
        {
            "run_id": "r-1",
            "job_name": "source_preview_refresh",
            "status": "running",
            "cache_key": "source_preview.foundation",
        },
        {
            "run_id": "r-1",
            "job_name": "source_preview_refresh",
            "status": "failed",
            "cache_key": "source_preview.foundation",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in original) + "\n",
        encoding="utf-8",
    )

    summary = module.compact_cache_build_run(path, apply_changes=False)

    assert _read_jsonl(path) == original
    assert summary["removed_rows"] == 1

