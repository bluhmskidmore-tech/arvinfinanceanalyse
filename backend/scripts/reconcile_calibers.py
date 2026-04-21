"""
Placeholder reconciliation report: relates audit baselines to future canonical migration.

No production migration yet — emits an informational Markdown summary only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from backend.app.core_finance.calibers import list_caliber_rules
from backend.scripts.audit_caliber_violations import KNOWN_RULES

BASELINE_GLOB = "caliber-violations-{rule_id}-baseline.json"


def _load_audit_total(output_dir: Path, rule_id: str) -> int | None:
    path = output_dir / BASELINE_GLOB.format(rule_id=rule_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return int(data.get("totals", {}).get("all", 0))


def build_report_markdown(*, report_date: str, output_dir: Path) -> str:
    lines: list[str] = [
        f"# Caliber reconciliation — {report_date}",
        "",
        f"- Generated (UTC): `{datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}`",
        f"- Audit report directory: `{output_dir.as_posix()}`",
        f"- Registry rules (import order may differ): `{', '.join(KNOWN_RULES)}`",
        "",
        "This report is a skeleton: canonical-vs-inline reconciliation runs are gated on migration.",
        "",
    ]
    for rule in sorted(list_caliber_rules(), key=lambda r: r.rule_id):
        rid = rule.rule_id
        n = _load_audit_total(output_dir, rid)
        baseline_file = (output_dir / BASELINE_GLOB.format(rule_id=rid)).as_posix()
        if n is None:
            lines.append(f"## `{rid}`")
            lines.append("")
            lines.append(f"- Audit baseline not found (`{baseline_file}`). Run `python -m backend.scripts.audit_caliber_violations` first.")
            lines.append("")
            continue
        lines.append(f"## `{rid}`")
        lines.append("")
        lines.append(f"- Canonical: `{rule.canonical_module}.{rule.canonical_callable}`")
        lines.append(f"- Audit baseline: `{baseline_file}`")
        if n == 0:
            lines.append("- **Status**: no inline implementations to reconcile against — see audit baseline (0 findings).")
        else:
            lines.append(
                f"- **Status**: **{n}** inline candidate(s) pending migration (per audit baseline)."
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Caliber reconciliation report (informational).")
    p.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Report date stamp (default: UTC today).",
    )
    p.add_argument(
        "--output-dir",
        metavar="DIR",
        default=".omx/reports",
        help="Where audit baselines and this report live (default: .omx/reports)",
    )
    args = p.parse_args(list(argv) if argv is not None else sys.argv[1:])

    out = Path(args.output_dir)
    if not out.is_absolute():
        out = (Path.cwd() / out).resolve()

    if args.date:
        report_date = args.date
    else:
        report_date = datetime.now(UTC).date().isoformat()

    body = build_report_markdown(report_date=report_date, output_dir=out)
    dest = out / f"caliber-reconciliation-{report_date}.md"
    out.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    print(f"[caliber-reconcile] wrote {dest.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
