from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.portfolio_home_krd_remap_review_queue import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
    build_queue,
)


DEFAULT_OUTPUT_DIR = ROOT / "docs" / "portfolio" / "krd-contract-decision"

SUMMARY_FIELDS = [
    "tenor_bucket",
    "all_rows",
    "nonzero_dv01_rows",
    "all_market_value",
    "nonzero_dv01_market_value",
    "dv01_sum",
    "mapped_to",
    "mapping_status",
    "risk_owner_decision",
    "decision_notes",
]

DETAIL_FIELDS = [
    "report_date",
    "instrument_code",
    "instrument_name",
    "portfolio_name",
    "cost_center",
    "market_value",
    "maturity_date",
    "tenor_bucket",
    "dv01",
    "mapped_to",
    "mapping_status",
    "source_version",
    "rule_version",
    "ingest_batch_id",
    "trace_id",
    "risk_owner_decision",
    "decision_notes",
]


def _int_value(payload: dict[str, object], key: str) -> int:
    return int(payload.get(key) or 0)


def _decimal_sum(rows: list[dict[str, object]], key: str) -> str:
    total = sum((Decimal(str(row.get(key) or "0")) for row in rows), Decimal("0"))
    return format(total.quantize(Decimal("0.00000001")), "f")


def _csv_rows(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_csv_rows(path: Path) -> tuple[list[str] | None, list[dict[str, str]] | None]:
    if not path.exists():
        return None, None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def _generated_rows(
    rows: list[dict[str, object]],
    fields: list[str],
    owner_fields: set[str],
) -> list[dict[str, str]]:
    return [
        {field: _csv_cell(row.get(field)) for field in fields if field not in owner_fields}
        for row in rows
    ]


def _manifest_export_files(report_date: str) -> dict[str, str]:
    base = Path("docs") / "portfolio" / "krd-contract-decision" / report_date
    return {
        "krd_remap_summary_csv": str(base / "krd_remap_summary.csv"),
        "krd_remap_detail_csv": str(base / "krd_remap_detail.csv"),
        "manifest_json": str(base / "manifest.json"),
        "owner_summary_md": str(base / "owner_summary.md"),
    }


def _export_summary(queue: dict[str, object]) -> dict[str, object]:
    summary_rows = _csv_rows(queue.get("krd_remap_summary", []))
    return {
        "remap_tenor_count": len(summary_rows),
        "mapped_tenor_count": sum(1 for row in summary_rows if row.get("mapping_status") == "mapped"),
        "unsupported_tenor_count": sum(
            1 for row in summary_rows if row.get("mapping_status") == "unsupported"
        ),
        "nonzero_dv01_rows": sum(_int_value(row, "nonzero_dv01_rows") for row in summary_rows),
        "dv01_sum": _decimal_sum(summary_rows, "dv01_sum"),
    }


def _acceptance_criteria() -> dict[str, object]:
    return {
        "strict_gate_command": "python scripts/portfolio_home_krd_remap_review_queue.py --require-clean",
        "risk_owner_decision_required": True,
        "does_not_approve_nearest_bucket": True,
        "generated_owner_fields_must_be_blank": True,
        "valid_decisions": [
            "approve_nearest_bucket",
            "require_exact_bucket_schema",
            "reject",
        ],
        "rerun_required": [
            "metric contract update",
            "risk tensor materialization",
            "portfolio full-closure evidence",
        ],
    }


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "risk_owner_decision": "",
                    "decision_notes": "",
                }
            )


def _owner_summary_markdown(packet: dict[str, object]) -> str:
    summary = packet.get("export_summary", {})
    criteria = packet.get("acceptance_criteria", {})
    decision_options = packet.get("decision_options", [])
    assert isinstance(summary, dict)
    assert isinstance(criteria, dict)
    assert isinstance(decision_options, list)
    return "\n".join(
        [
            "# Portfolio Home KRD Contract Decision Summary",
            "",
            "This summary is not an approval.",
            "",
            f"- Page: `{packet.get('page_slug')}` (`{packet.get('page_id')}`)",
            f"- Report date: `{packet.get('report_date')}`",
            f"- Export status: `{packet.get('export_status')}`",
            "- Required fields: `risk_owner_decision`, `decision_notes`",
            f"- Allowed decisions: {', '.join(f'`{decision}`' for decision in decision_options)}",
            f"- Strict gate: `{criteria.get('strict_gate_command')}`",
            f"- Remap tenor count: `{summary.get('remap_tenor_count')}`",
            f"- Mapped tenor count: `{summary.get('mapped_tenor_count')}`",
            f"- Unsupported tenor count: `{summary.get('unsupported_tenor_count')}`",
            f"- Non-zero DV01 rows: `{summary.get('nonzero_dv01_rows')}`",
            f"- DV01 sum: `{summary.get('dv01_sum')}`",
            "- Decision queue: `krd_remap_summary.csv`, `krd_remap_detail.csv`",
            (
                "- Generated owner fields must be blank: "
                f"`{str(criteria.get('generated_owner_fields_must_be_blank')).lower()}`"
            ),
            "- Boundary: generated CSV fields are blank and do not approve nearest-bucket mapping.",
            "",
            "## Owner Instructions",
            "",
            "- Fill `risk_owner_decision` on every summary and detail row.",
            (
                "- Fill `decision_notes` on every summary and detail row for every decision value; "
                "include the contract rationale or rejection reason."
            ),
            "- Do not edit `manifest.json`; rerun the export after owner decisions are captured.",
            "",
            "## Post-Decision Verification",
            "",
            "- `python scripts/portfolio_home_krd_remap_review_queue.py --require-clean`",
            "- `python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent`",
            "- `python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready`",
            "- `python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`",
            "",
            (
                "A filled CSV is still not approval until the business-owner approval template is "
                "completed and the strict scorecard gate passes."
            ),
            "",
        ],
    )


def build_export_packet(
    *,
    duckdb_path: Path,
    report_date: str,
    output_dir: Path,
    write_files: bool = True,
) -> dict[str, object]:
    queue = build_queue(
        duckdb_path=duckdb_path,
        report_date=report_date,
        limit=1_000_000,
    )
    blockers = queue.get("review_blockers", [])
    assert isinstance(blockers, list)
    packet: dict[str, object] = {
        "packet_kind": "portfolio_home_krd_contract_decision_export",
        "page_id": queue["page_id"],
        "page_slug": queue["page_slug"],
        "report_date": report_date,
        "duckdb_path": str(duckdb_path),
        "export_status": "clean" if not blockers else "decision_required",
        "review_blockers": blockers,
        "decision_options": queue.get("decision_options", []),
        "supported_krd_buckets": queue.get("supported_krd_buckets", []),
        "nearest_bucket_map": queue.get("nearest_bucket_map", {}),
        "export_summary": _export_summary(queue),
        "acceptance_criteria": _acceptance_criteria(),
        "export_files": None,
    }
    if not blockers:
        return packet

    target_dir = output_dir / report_date
    summary_csv = target_dir / "krd_remap_summary.csv"
    detail_csv = target_dir / "krd_remap_detail.csv"
    manifest_json = target_dir / "manifest.json"
    owner_summary_md = target_dir / "owner_summary.md"

    packet["export_files"] = {
        "krd_remap_summary_csv": str(summary_csv),
        "krd_remap_detail_csv": str(detail_csv),
        "manifest_json": str(manifest_json),
        "owner_summary_md": str(owner_summary_md),
    }
    if write_files:
        _write_csv(summary_csv, SUMMARY_FIELDS, _csv_rows(queue.get("krd_remap_summary", [])))
        _write_csv(detail_csv, DETAIL_FIELDS, _csv_rows(queue.get("krd_remap_rows", [])))
        manifest_packet = {**packet, "export_files": _manifest_export_files(report_date)}
        manifest_json.write_text(
            json.dumps(manifest_packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        owner_summary_md.write_text(_owner_summary_markdown(packet), encoding="utf-8")
    return packet


def _manifest_blockers(
    *,
    actual: dict[str, object] | None,
    expected: dict[str, object],
) -> list[str]:
    if actual is None:
        return ["manifest_missing_or_invalid"]
    expected_manifest = {**expected, "export_files": _manifest_export_files(str(expected["report_date"]))}
    blockers: list[str] = []
    for field in (
        "packet_kind",
        "page_id",
        "page_slug",
        "report_date",
        "duckdb_path",
        "export_status",
        "review_blockers",
        "decision_options",
        "supported_krd_buckets",
        "nearest_bucket_map",
        "export_files",
    ):
        if actual.get(field) != expected_manifest.get(field):
            blockers.append(f"manifest_{field}_mismatch")
    if actual.get("export_summary") != expected_manifest.get("export_summary"):
        blockers.append("manifest_export_summary_mismatch")
    if actual.get("acceptance_criteria") != expected_manifest.get("acceptance_criteria"):
        blockers.append("manifest_acceptance_criteria_mismatch")
    return blockers


def _csv_blockers(
    *,
    path: Path,
    name: str,
    fields: list[str],
    expected_rows: list[dict[str, object]],
) -> tuple[list[str], dict[str, object]]:
    owner_fields = {"risk_owner_decision", "decision_notes"}
    expected_generated_fields = [field for field in fields if field not in owner_fields]
    actual_fields, actual_rows = _read_csv_rows(path)
    if actual_rows is None or actual_fields is None:
        return [f"{name}_csv_missing"], {
            "path": str(path),
            "exists": False,
            "generated_row_count": None,
        }
    blockers: list[str] = []
    if actual_fields != fields:
        blockers.append(f"{name}_csv_header_mismatch")
    actual_generated_rows = [
        {field: row.get(field, "") for field in expected_generated_fields}
        for row in actual_rows
    ]
    expected_generated_rows = _generated_rows(
        expected_rows,
        fields,
        owner_fields,
    )
    if actual_generated_rows != expected_generated_rows:
        blockers.append(f"{name}_csv_generated_rows_mismatch")
    return blockers, {
        "path": str(path),
        "exists": True,
        "generated_row_count": len(actual_generated_rows),
        "expected_generated_row_count": len(expected_generated_rows),
        "header": actual_fields,
        "expected_header": fields,
    }


def build_current_status(
    *,
    duckdb_path: Path,
    report_date: str,
    output_dir: Path,
) -> dict[str, object]:
    queue = build_queue(
        duckdb_path=duckdb_path,
        report_date=report_date,
        limit=1_000_000,
    )
    packet = build_export_packet(
        duckdb_path=duckdb_path,
        report_date=report_date,
        output_dir=output_dir,
        write_files=False,
    )
    blockers: list[str] = []
    checks: dict[str, object] = {}
    if packet["export_status"] == "clean":
        return {
            "packet_kind": "portfolio_home_krd_contract_decision_export_current_check",
            "page_id": packet["page_id"],
            "page_slug": packet["page_slug"],
            "report_date": report_date,
            "artifact_dir": str(output_dir / report_date),
            "status": "current",
            "current": True,
            "current_blockers": [],
            "owner_input_boundary": {
                "owner_fields_are_owner_owned": True,
                "check_current_does_not_require_owner_fields_blank": True,
            },
            "checks": checks,
        }
    export_files = packet["export_files"]
    assert isinstance(export_files, dict)
    manifest_json = Path(str(export_files["manifest_json"]))
    owner_summary_md = Path(str(export_files["owner_summary_md"]))
    manifest_blockers = _manifest_blockers(
        actual=_read_json(manifest_json),
        expected=packet,
    )
    blockers.extend(manifest_blockers)
    expected_owner_summary = _owner_summary_markdown(packet)
    actual_owner_summary = (
        owner_summary_md.read_text(encoding="utf-8") if owner_summary_md.exists() else None
    )
    if actual_owner_summary != expected_owner_summary:
        blockers.append("owner_summary_mismatch")
    summary_blockers, summary_check = _csv_blockers(
        path=Path(str(export_files["krd_remap_summary_csv"])),
        name="krd_remap_summary",
        fields=SUMMARY_FIELDS,
        expected_rows=_csv_rows(queue.get("krd_remap_summary", [])),
    )
    detail_blockers, detail_check = _csv_blockers(
        path=Path(str(export_files["krd_remap_detail_csv"])),
        name="krd_remap_detail",
        fields=DETAIL_FIELDS,
        expected_rows=_csv_rows(queue.get("krd_remap_rows", [])),
    )
    blockers.extend(summary_blockers)
    blockers.extend(detail_blockers)
    checks = {
        "manifest": {
            "path": str(manifest_json),
            "status": "current" if not manifest_blockers else "stale",
            "blockers": manifest_blockers,
        },
        "owner_summary": {
            "path": str(owner_summary_md),
            "status": "current" if actual_owner_summary == expected_owner_summary else "stale",
        },
        "krd_remap_summary_csv": summary_check,
        "krd_remap_detail_csv": detail_check,
    }
    current = not blockers
    return {
        "packet_kind": "portfolio_home_krd_contract_decision_export_current_check",
        "page_id": packet["page_id"],
        "page_slug": packet["page_slug"],
        "report_date": report_date,
        "artifact_dir": str(output_dir / report_date),
        "status": "current" if current else "stale",
        "current": current,
        "current_blockers": blockers,
        "owner_input_boundary": {
            "owner_fields_are_owner_owned": True,
            "check_current_does_not_require_owner_fields_blank": True,
        },
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export portfolio-home KRD remap contract decision evidence for risk-owner review.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless no KRD contract decision export is required.",
    )
    parser.add_argument(
        "--check-current",
        action="store_true",
        help="Return non-zero unless the existing export package matches current generated evidence.",
    )
    args = parser.parse_args(argv)

    if args.check_current:
        status = build_current_status(
            duckdb_path=Path(args.duckdb_path),
            report_date=str(args.report_date),
            output_dir=Path(args.output_dir),
        )
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["current"] else 1

    packet = build_export_packet(
        duckdb_path=Path(args.duckdb_path),
        report_date=str(args.report_date),
        output_dir=Path(args.output_dir),
    )
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    if args.require_clean and packet["export_status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
