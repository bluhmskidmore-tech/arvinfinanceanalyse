from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

PNL_CACHE_KEY = "pnl:phase2:materialize:formal"
TARGET_FILENAMES = ("cache_build_run.jsonl", "cache_manifest.jsonl")
TARGET_FIELDS = ("source_version", "rule_version")


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


def _normalize_lineage_value(value: object) -> str:
    tokens: set[str] = set()
    text = str(value or "").strip()
    if not text:
        return ""
    for part in text.split("__"):
        for dirty_part in part.split(","):
            normalized = dirty_part.strip()
            if normalized:
                tokens.add(normalized)
    return "__".join(sorted(tokens))


def _repair_row(row: dict[str, object]) -> tuple[dict[str, object], bool]:
    if str(row.get("cache_key") or "").strip() != PNL_CACHE_KEY:
        return row, False

    updated = dict(row)
    changed = False
    for field_name in TARGET_FIELDS:
        original = str(updated.get(field_name) or "")
        normalized = _normalize_lineage_value(original)
        if normalized and normalized != original:
            updated[field_name] = normalized
            changed = True
    return updated, changed


def repair_pnl_governance_lineage(governance_dir: str | Path, *, apply_changes: bool) -> dict[str, object]:
    root = Path(governance_dir)
    files_scanned = 0
    rows_updated = 0
    backups: list[str] = []

    for filename in TARGET_FILENAMES:
        path = root / filename
        if not path.exists():
            continue
        files_scanned += 1
        rows = _read_jsonl(path)
        rewritten: list[dict[str, object]] = []
        file_changed = False
        for row in rows:
            repaired, changed = _repair_row(row)
            rewritten.append(repaired)
            if changed:
                rows_updated += 1
                file_changed = True
        if apply_changes and file_changed:
            backup_path = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup_path)
            backups.append(str(backup_path))
            _write_jsonl(path, rewritten)

    return {
        "governance_dir": str(root),
        "files_scanned": files_scanned,
        "rows_updated": rows_updated,
        "applied": bool(apply_changes),
        "backup_paths": backups,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--governance-dir", default="data/governance")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = repair_pnl_governance_lineage(
        args.governance_dir,
        apply_changes=not args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
