"""
Aggregate caliber violation counts across all registered rules for CI drift detection.

Writes ``caliber-violations-summary.json`` (this file doubles as the baseline for ``--ci``).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core_finance.calibers import get_caliber_rule
from backend.scripts.audit_caliber_violations import (
    KNOWN_RULES,
    count_by_confidence,
    scan_violations,
)

SUMMARY_FILENAME = "caliber-violations-summary.json"


def _repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def build_summary(project_root: Path | None = None) -> dict[str, Any]:
    root = project_root if project_root is not None else _repo_root_from_script()
    generated_at_utc = (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    rules_payload: dict[str, Any] = {}
    for rid in KNOWN_RULES:
        violations, suppressed = scan_violations(rule_id=rid, project_root=root)
        totals = count_by_confidence(violations)
        rule = get_caliber_rule(rid)
        rules_payload[rid] = {
            "rule_id": rid,
            "canonical_module": rule.canonical_module,
            "canonical_callable": rule.canonical_callable,
            "suppressed": suppressed,
            "totals": {
                "high": totals["high"],
                "medium": totals["medium"],
                "low": totals["low"],
                "all": totals["all"],
            },
        }
    return {
        "schema_version": 1,
        "generated_at_utc": generated_at_utc,
        "rules": rules_payload,
    }


def write_summary(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def compare_against_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    regressions: list[str] = []
    cur_rules: dict[str, Any] = current["rules"]
    base_rules: dict[str, Any] = baseline.get("rules", {})
    for rid, cur_entry in sorted(cur_rules.items()):
        base_entry = base_rules.get(rid)
        if base_entry is None:
            continue
        cur_high = int(cur_entry["totals"]["high"])
        base_high = int(base_entry["totals"]["high"])
        if cur_high > base_high:
            regressions.append(rid)
    return {"drift_detected": bool(regressions), "regressions": regressions}


def _print_table(summary: dict[str, Any]) -> None:
    print("rule_id | high | med | low | all")
    print("--------|------|-----|-----|----")
    for rid in sorted(summary["rules"].keys()):
        t = summary["rules"][rid]["totals"]
        print(
            f"{rid} | {t['high']} | {t['medium']} | {t['low']} | {t['all']}"
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Caliber violations summary + CI drift check.")
    p.add_argument(
        "--output-dir",
        metavar="DIR",
        default=".omx/reports",
        help="Directory for caliber-violations-summary.json (default: .omx/reports)",
    )
    p.add_argument(
        "--ci",
        action="store_true",
        help="Compare current scan to on-disk summary without writing; exit 1 on high-count regression.",
    )
    p.add_argument(
        "--print",
        action="store_true",
        dest="print_table",
        help="Print human-readable totals to stdout.",
    )
    args = p.parse_args(list(argv) if argv is not None else sys.argv[1:])

    root = _repo_root_from_script()
    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()
    summary_path = out_dir / SUMMARY_FILENAME

    if args.ci:
        if not summary_path.is_file():
            print(f"[caliber-summary] missing baseline: {summary_path}", file=sys.stderr)
            return 2
        baseline = json.loads(summary_path.read_text(encoding="utf-8"))
        current = build_summary(project_root=root)
        result = compare_against_baseline(current, baseline)
        if args.print_table:
            _print_table(current)
        if result["drift_detected"]:
            print(
                "[caliber-summary] CI regression (high count increased): "
                + ", ".join(result["regressions"]),
                file=sys.stderr,
            )
            return 1
        print("[caliber-summary] CI OK — no high-severity regression.")
        return 0

    summary = build_summary(project_root=root)
    write_summary(summary, summary_path)
    if args.print_table:
        _print_table(summary)
    print(f"[caliber-summary] wrote {summary_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
