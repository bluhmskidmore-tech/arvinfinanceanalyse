from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.portfolio_home_closure_scorecard import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
    DEFAULT_TEMPLATE,
    build_scorecard,
    non_negative_portfolio_limit,
)
from scripts.portfolio_home_limit import validate_non_negative_portfolio_limit  # noqa: E402
from scripts.portfolio_home_manifest_consistency import (  # noqa: E402
    generated_owner_fields_boundaries,
)


def _csv_check_summary(checks: list[dict[str, object]]) -> dict[str, object]:
    by_name = {str(item.get("name")): item for item in checks if isinstance(item, dict)}
    krd = by_name.get("krd_contract_decision_manifest", {})
    maturity = by_name.get("maturity_remediation_manifest", {})
    krd_csv = krd.get("csv_checks", {}) if isinstance(krd, dict) else {}
    maturity_csv = maturity.get("csv_checks", {}) if isinstance(maturity, dict) else {}
    assert isinstance(krd_csv, dict)
    assert isinstance(maturity_csv, dict)
    return {
        "krd_summary_row_count": krd_csv.get("summary_row_count"),
        "krd_detail_row_count": krd_csv.get("detail_row_count"),
        "krd_owner_decision_fields_blank": krd_csv.get("owner_decision_fields_blank"),
        "bond_missing_maturity_row_count": maturity_csv.get("bond_missing_maturity_row_count"),
        "tyw_liability_missing_maturity_row_count": maturity_csv.get(
            "tyw_liability_missing_maturity_row_count",
        ),
        "maturity_owner_fields_blank": maturity_csv.get("owner_fields_blank"),
    }


def build_dependency_consistency(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path,
    limit: int,
    docs_root: Path = ROOT / "docs",
) -> dict[str, object]:
    limit = validate_non_negative_portfolio_limit(
        limit,
        label="dependency consistency limit",
    )
    scorecard = build_scorecard(
        duckdb_path=duckdb_path,
        report_date=report_date,
        template_path=template_path,
        limit=limit,
        docs_root=docs_root,
    )
    gates = scorecard.get("gates", {})
    assert isinstance(gates, dict)
    dependency_gate = gates.get("approval_dependency_consistency", {})
    assert isinstance(dependency_gate, dict)
    checks = dependency_gate.get("manifest_consistency_checks", [])
    assert isinstance(checks, list)
    blockers = dependency_gate.get("blockers", [])
    assert isinstance(blockers, list)
    return {
        "check_kind": "portfolio_home_dependency_consistency",
        "page_id": scorecard["page_id"],
        "page_slug": scorecard["page_slug"],
        "report_date": scorecard["report_date"],
        "duckdb_path": scorecard["duckdb_path"],
        "template_path": scorecard["template_path"],
        "docs_root": str(docs_root),
        "dependency_consistency_status": dependency_gate.get("status"),
        "dependency_consistency_blockers": blockers,
        "csv_check_summary": _csv_check_summary(checks),
        "generated_owner_fields_boundaries": generated_owner_fields_boundaries(checks),
        "manifest_consistency_checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check portfolio-home approval dependency manifest and CSV consistency.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--template-path", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument(
        "--limit",
        type=lambda value: non_negative_portfolio_limit(
            value,
            label="dependency consistency limit",
        ),
        default=3,
    )
    parser.add_argument(
        "--require-consistent",
        action="store_true",
        help="Return non-zero unless manifests and CSV evidence match the current scorecard.",
    )
    args = parser.parse_args(argv)

    report = build_dependency_consistency(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        template_path=Path(args.template_path),
        limit=int(args.limit),
        docs_root=Path(args.docs_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_consistent and report["dependency_consistency_status"] != "consistent":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
