from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.repositories.source_manifest_repo import (
    MANIFEST_ELIGIBLE_STATUSES,
    SourceManifestRepository,
)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _latest_manifest_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    repo = SourceManifestRepository(rows=list(rows))
    latest_by_slot = repo._latest_by_source_slot()
    return sorted(
        latest_by_slot.values(),
        key=lambda row: (
            str(row.get("source_family", "")),
            str(row.get("report_date", "")),
            str(row.get("source_file", row.get("file_name", ""))),
        ),
    )


def _lineage_index_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    lineage_rows: list[dict[str, object]] = []
    for row in rows:
        if str(row.get("status", "")) not in MANIFEST_ELIGIBLE_STATUSES:
            continue
        lineage_rows.append(
            {
                "source_family": row.get("source_family"),
                "report_date": row.get("report_date"),
                "source_file": row.get("source_file", row.get("file_name")),
                "ingest_batch_id": row.get("ingest_batch_id"),
                "source_version": row.get("source_version"),
                "status": row.get("status"),
                "created_at": row.get("created_at"),
                "archived_path": row.get("archived_path"),
                "rerun_of_batch_id": row.get("rerun_of_batch_id"),
            }
        )
    return sorted(
        lineage_rows,
        key=lambda row: (
            str(row.get("source_family", "")),
            str(row.get("report_date", "")),
            str(row.get("source_file", "")),
            str(row.get("created_at", "")),
            str(row.get("ingest_batch_id", "")),
        ),
    )


def _write_lineage_shards(base_dir: Path, lineage_rows: list[dict[str, object]]) -> tuple[int, int]:
    family_dir = base_dir / "lineage_by_family"
    month_dir = base_dir / "lineage_by_month"
    family_dir.mkdir(parents=True, exist_ok=True)
    month_dir.mkdir(parents=True, exist_ok=True)

    family_buckets: dict[str, list[dict[str, object]]] = {}
    month_buckets: dict[str, list[dict[str, object]]] = {}
    for row in lineage_rows:
        family = str(row.get("source_family") or "unknown")
        report_date = str(row.get("report_date") or "")
        month = report_date[:7] if len(report_date) >= 7 else "unknown"
        family_buckets.setdefault(family, []).append(row)
        month_buckets.setdefault(month, []).append(row)

    for family, rows in family_buckets.items():
        _write_jsonl(family_dir / f"{family}.jsonl", rows)
    for month, rows in month_buckets.items():
        _write_jsonl(month_dir / f"{month}.jsonl", rows)

    return len(family_buckets), len(month_buckets)


def build_source_manifest_layers(
    *,
    manifest_path: Path,
    latest_output_path: Path,
    lineage_output_path: Path,
    apply_changes: bool,
) -> dict[str, object]:
    rows = _read_jsonl(manifest_path)
    latest_rows = _latest_manifest_rows(rows)
    lineage_rows = _lineage_index_rows(rows)
    summary = {
        "manifest_path": str(manifest_path),
        "latest_output_path": str(latest_output_path),
        "lineage_output_path": str(lineage_output_path),
        "manifest_row_count": len(rows),
        "latest_row_count": len(latest_rows),
        "lineage_row_count": len(lineage_rows),
        "family_shard_count": 0,
        "month_shard_count": 0,
        "applied": bool(apply_changes),
    }
    if apply_changes:
        latest_output_path.parent.mkdir(parents=True, exist_ok=True)
        lineage_output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_jsonl(latest_output_path, latest_rows)
        _write_jsonl(lineage_output_path, lineage_rows)
        family_shards, month_shards = _write_lineage_shards(lineage_output_path.parent, lineage_rows)
        summary["family_shard_count"] = family_shards
        summary["month_shard_count"] = month_shards
    else:
        summary["family_shard_count"] = len({str(row.get("source_family") or "unknown") for row in lineage_rows})
        summary["month_shard_count"] = len(
            {
                (str(row.get("report_date") or "")[:7] if len(str(row.get("report_date") or "")) >= 7 else "unknown")
                for row in lineage_rows
            }
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--governance-dir", default="data/governance")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    governance_dir = Path(args.governance_dir).expanduser()
    summary = build_source_manifest_layers(
        manifest_path=governance_dir / "source_manifest.jsonl",
        latest_output_path=governance_dir / "source_manifest_latest.jsonl",
        lineage_output_path=governance_dir / "source_manifest_lineage_index.jsonl",
        apply_changes=not args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
