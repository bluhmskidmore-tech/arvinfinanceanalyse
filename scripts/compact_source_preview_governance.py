from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.source_preview_refresh_service import (
    SOURCE_PREVIEW_REFRESH_CACHE_KEY,
    SOURCE_PREVIEW_REFRESH_JOB_NAME,
    _collapse_refresh_records,
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


def _is_source_preview_refresh_record(row: dict[str, object]) -> bool:
    return (
        str(row.get("job_name", "")) == SOURCE_PREVIEW_REFRESH_JOB_NAME
        and str(row.get("cache_key", "")) == SOURCE_PREVIEW_REFRESH_CACHE_KEY
    )


def compact_cache_build_run(path: Path, *, apply_changes: bool) -> dict[str, object]:
    rows = _read_jsonl(path)
    target_rows = [row for row in rows if _is_source_preview_refresh_record(row)]
    collapsed_target_rows = _collapse_refresh_records(target_rows)
    collapsed_by_run_id = {
        str(row.get("run_id") or ""): row
        for row in collapsed_target_rows
        if str(row.get("run_id") or "").strip()
    }

    compacted_rows: list[dict[str, object]] = []
    emitted_run_ids: set[str] = set()
    for row in rows:
        if not _is_source_preview_refresh_record(row):
            compacted_rows.append(row)
            continue
        run_id = str(row.get("run_id") or "").strip()
        if not run_id or run_id in emitted_run_ids:
            continue
        compacted = collapsed_by_run_id.get(run_id)
        if compacted is not None:
            compacted_rows.append(compacted)
            emitted_run_ids.add(run_id)

    removed_rows = len(rows) - len(compacted_rows)
    summary = {
        "path": str(path),
        "original_rows": len(rows),
        "written_rows": len(compacted_rows),
        "removed_rows": removed_rows,
        "target_run_count": len(collapsed_target_rows),
        "applied": bool(apply_changes),
    }

    if apply_changes:
        backup_path = path.with_suffix(path.suffix + ".bak")
        if path.exists():
            shutil.copy2(path, backup_path)
        _write_jsonl(path, compacted_rows)
        summary["backup_path"] = str(backup_path)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--governance-dir", default="data/governance")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = Path(args.governance_dir).expanduser() / "cache_build_run.jsonl"
    summary = compact_cache_build_run(path, apply_changes=not args.dry_run)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
