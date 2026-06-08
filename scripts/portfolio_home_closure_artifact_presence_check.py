from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_portfolio_home_business_owner_approval import DEFAULT_TEMPLATE  # noqa: E402
from scripts.portfolio_home_closure_artifact_summary import (  # noqa: E402
    artifact_current_summary as build_artifact_current_summary,
    artifact_presence_report,
)
from scripts.portfolio_home_full_closure_evidence import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
)
from scripts.portfolio_home_limit import (  # noqa: E402
    non_negative_portfolio_limit,
    validate_non_negative_portfolio_limit,
)
from scripts.portfolio_home_owner_action_packet import build_packet  # noqa: E402


def build_report(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    docs_root: Path,
    limit: int,
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="closure artifact presence limit",
    )
    packet = build_packet(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=docs_root,
        limit=limit,
    )
    intake_summary = packet.get("owner_decision_intake_summary")
    assert isinstance(intake_summary, dict)
    artifact_current = build_artifact_current_summary(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        docs_root=docs_root,
        intake_summary=intake_summary,
    )
    closure_matrix = packet.get("blocker_closure_matrix", [])
    assert isinstance(closure_matrix, list)
    report = artifact_presence_report(
        docs_root=docs_root,
        closure_matrix=closure_matrix,
        artifact_current_summary=artifact_current,
    )
    return {
        "check_kind": "portfolio_home_closure_artifact_presence",
        "page_id": packet.get("page_id"),
        "page_slug": packet.get("page_slug"),
        "report_date": packet.get("report_date", report_date),
        "duckdb_path": str(duckdb_path),
        "template_path": str(template_path),
        "docs_root": str(docs_root),
        "current_score": packet.get("current_score"),
        "remaining_gap": packet.get("remaining_gap"),
        "score_status": packet.get("score_status"),
        "full_score_ready": packet.get("full_score_ready"),
        "score_blockers": packet.get("score_blockers", []),
        **report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check portfolio-home owner closure artifacts exist and match current evidence.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="closure artifact presence limit",
        ),
        default=3,
    )
    parser.add_argument(
        "--require-current",
        action="store_true",
        help="Return non-zero unless every owner closure artifact is present and current.",
    )
    args = parser.parse_args(argv)

    report = build_report(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        docs_root=Path(args.docs_root),
        limit=int(args.limit),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_current and not report["current"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
