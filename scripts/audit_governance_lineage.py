from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

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


def _is_dirty_lineage_value(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and "," in text


def audit_governance_lineage(governance_dir: str | Path) -> dict[str, object]:
    root = Path(governance_dir)
    files_scanned = 0
    rows_scanned = 0
    dirty_rows = 0
    findings_by_key: dict[tuple[str, str], dict[str, object]] = {}

    for filename in TARGET_FILENAMES:
        path = root / filename
        if not path.exists():
            continue
        files_scanned += 1
        for row in _read_jsonl(path):
            rows_scanned += 1
            cache_key = str(row.get("cache_key") or "").strip() or "<missing-cache-key>"
            row_dirty = False
            for field_name in TARGET_FIELDS:
                raw_value = row.get(field_name)
                if not _is_dirty_lineage_value(raw_value):
                    continue
                row_dirty = True
                finding_key = (cache_key, field_name)
                finding = findings_by_key.setdefault(
                    finding_key,
                    {
                        "cache_key": cache_key,
                        "field_name": field_name,
                        "dirty_row_count": 0,
                        "sample_values": [],
                        "normalized_value": _normalize_lineage_value(raw_value),
                    },
                )
                finding["dirty_row_count"] = int(finding["dirty_row_count"]) + 1
                sample_values = finding["sample_values"]
                if raw_value not in sample_values and len(sample_values) < 5:
                    sample_values.append(raw_value)
            if row_dirty:
                dirty_rows += 1

    findings = sorted(
        findings_by_key.values(),
        key=lambda item: (str(item["cache_key"]), str(item["field_name"])),
    )
    return {
        "governance_dir": str(root),
        "files_scanned": files_scanned,
        "rows_scanned": rows_scanned,
        "dirty_rows": dirty_rows,
        "dirty_cache_keys": len({item["cache_key"] for item in findings}),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--governance-dir", default="data/governance")
    args = parser.parse_args()
    summary = audit_governance_lineage(args.governance_dir)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
