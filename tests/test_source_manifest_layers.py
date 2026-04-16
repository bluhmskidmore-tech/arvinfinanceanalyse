from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import load_module


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_build_source_manifest_layers_writes_latest_and_lineage_index(tmp_path):
    module = load_module(
        "scripts.build_source_manifest_layers",
        "scripts/build_source_manifest_layers.py",
    )

    manifest_path = tmp_path / "source_manifest.jsonl"
    rows = [
        {
            "ingest_batch_id": "ib-old",
            "source_family": "zqtz",
            "report_date": "2025-12-31",
            "source_file": "ZQTZSHOW-20251231.xls",
            "source_version": "sv-old",
            "archived_path": "archive/old.xls",
            "created_at": "2026-01-01T00:00:00+00:00",
            "status": "completed",
        },
        {
            "ingest_batch_id": "ib-new",
            "source_family": "zqtz",
            "report_date": "2025-12-31",
            "source_file": "ZQTZSHOW-20251231.xls",
            "source_version": "sv-new",
            "archived_path": "archive/new.xls",
            "created_at": "2026-01-02T00:00:00+00:00",
            "status": "completed",
        },
        {
            "ingest_batch_id": "ib-tyw",
            "source_family": "tyw",
            "report_date": "2025-12-31",
            "source_file": "TYWLSHOW-20251231.xls",
            "source_version": "sv-tyw",
            "archived_path": "archive/tyw.xls",
            "created_at": "2026-01-02T00:00:00+00:00",
            "status": "completed",
        },
    ]
    _write_jsonl(manifest_path, rows)

    summary = module.build_source_manifest_layers(
        manifest_path=manifest_path,
        latest_output_path=tmp_path / "source_manifest_latest.jsonl",
        lineage_output_path=tmp_path / "source_manifest_lineage_index.jsonl",
        apply_changes=True,
    )

    latest_rows = _read_jsonl(tmp_path / "source_manifest_latest.jsonl")
    lineage_rows = _read_jsonl(tmp_path / "source_manifest_lineage_index.jsonl")
    family_rows = _read_jsonl(tmp_path / "lineage_by_family" / "zqtz.jsonl")
    month_rows = _read_jsonl(tmp_path / "lineage_by_month" / "2025-12.jsonl")

    assert [(row["source_family"], row["ingest_batch_id"]) for row in latest_rows] == [
        ("tyw", "ib-tyw"),
        ("zqtz", "ib-new"),
    ]
    assert len(lineage_rows) == 3
    assert len(family_rows) == 2
    assert {row["ingest_batch_id"] for row in family_rows} == {"ib-old", "ib-new"}
    assert len(month_rows) == 3
    assert summary["latest_row_count"] == 2
    assert summary["lineage_row_count"] == 3
    assert summary["family_shard_count"] == 2
    assert summary["month_shard_count"] == 1


def test_build_source_manifest_layers_dry_run_does_not_write_outputs(tmp_path):
    module = load_module(
        "scripts.build_source_manifest_layers",
        "scripts/build_source_manifest_layers.py",
    )

    manifest_path = tmp_path / "source_manifest.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "ingest_batch_id": "ib-1",
                "source_family": "zqtz",
                "report_date": "2025-12-31",
                "source_file": "ZQTZSHOW-20251231.xls",
                "source_version": "sv-1",
                "archived_path": "archive/a.xls",
                "created_at": "2026-01-01T00:00:00+00:00",
                "status": "completed",
            }
        ],
    )

    summary = module.build_source_manifest_layers(
        manifest_path=manifest_path,
        latest_output_path=tmp_path / "source_manifest_latest.jsonl",
        lineage_output_path=tmp_path / "source_manifest_lineage_index.jsonl",
        apply_changes=False,
    )

    assert summary["latest_row_count"] == 1
    assert not (tmp_path / "source_manifest_latest.jsonl").exists()
    assert not (tmp_path / "source_manifest_lineage_index.jsonl").exists()
    assert not (tmp_path / "lineage_by_family").exists()
    assert not (tmp_path / "lineage_by_month").exists()
