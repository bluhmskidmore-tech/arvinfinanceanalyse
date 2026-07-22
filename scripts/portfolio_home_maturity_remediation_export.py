from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.portfolio_home_maturity_remediation_queue import (  # noqa: E402
    DEFAULT_DUCKDB,
    DEFAULT_REPORT_DATE,
    build_queue,
)


DEFAULT_OUTPUT_DIR = ROOT / "docs" / "portfolio" / "maturity-remediation"

BOND_FIELDS = [
    "report_date",
    "instrument_code",
    "instrument_name",
    "portfolio_name",
    "cost_center",
    "market_value",
    "dv01",
    "tenor_bucket",
    "source_version",
    "rule_version",
    "ingest_batch_id",
    "trace_id",
    "proposed_maturity_date",
    "owner_decision",
    "owner_comment",
]

TYW_FIELDS = [
    "report_date",
    "position_id",
    "product_type",
    "position_side",
    "counterparty_name",
    "position_scope",
    "currency_basis",
    "principal_amount",
    "funding_cost_rate",
    "source_version",
    "rule_version",
    "ingest_batch_id",
    "trace_id",
    "proposed_maturity_date",
    "owner_decision",
    "owner_comment",
]


def _int_value(payload: dict[str, object], key: str) -> int:
    return int(payload.get(key) or 0)


def _str_value(payload: dict[str, object], key: str) -> str:
    return str(payload.get(key) or "0")


def _export_summary(queue: dict[str, object]) -> dict[str, object]:
    bond_no_maturity_summary = queue["bond_no_maturity_summary"]
    bond_summary = queue["bond_missing_maturity_summary"]
    tyw_summary = queue["tyw_liability_missing_maturity_summary"]
    assert isinstance(bond_no_maturity_summary, dict)
    assert isinstance(bond_summary, dict)
    assert isinstance(tyw_summary, dict)
    return {
        "bond_no_maturity_rows": _int_value(
            bond_no_maturity_summary,
            "no_maturity_rows",
        ),
        "bond_no_maturity_market_value": _str_value(
            bond_no_maturity_summary,
            "no_maturity_market_value",
        ),
        "bond_missing_maturity_rows": _int_value(bond_summary, "missing_maturity_rows"),
        "tyw_liability_missing_maturity_rows": _int_value(tyw_summary, "missing_maturity_rows"),
        "bond_missing_maturity_market_value": _str_value(
            bond_summary,
            "missing_maturity_market_value",
        ),
        "tyw_liability_missing_maturity_principal": _str_value(
            tyw_summary,
            "missing_maturity_principal",
        ),
    }


def _acceptance_criteria(report_date: str) -> dict[str, object]:
    return {
        "strict_gate_command": (
            "python scripts/portfolio_home_maturity_remediation_queue.py "
            f"--report-date {report_date} --require-empty"
        ),
        "requires_source_remediation_or_signed_exclusion": True,
        "owner_decision_scope": "TYW liability missing-maturity rows only",
        "bond_no_maturity_requires_owner_decision": False,
        "no_frontend_or_inferred_fill": True,
        "generated_owner_fields_must_be_blank": True,
        "rerun_required": [
            "formal TYW balance materialization",
            "portfolio full-closure evidence",
        ],
    }


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


def _nonblank_owner_input_paths(paths: list[Path]) -> list[Path]:
    owner_fields = ("proposed_maturity_date", "owner_decision", "owner_comment")
    populated_paths: list[Path] = []
    for path in paths:
        _, rows = _read_csv_rows(path)
        if rows is None:
            continue
        if any(
            any((row.get(field) or "").strip() for field in owner_fields)
            for row in rows
        ):
            populated_paths.append(path)
    return populated_paths


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
    base = Path("docs") / "portfolio" / "maturity-remediation" / report_date
    return {
        "bond_missing_maturity_csv": str(base / "bond_missing_maturity.csv"),
        "tyw_liability_missing_maturity_csv": str(base / "tyw_liability_missing_maturity.csv"),
        "manifest_json": str(base / "manifest.json"),
        "owner_summary_md": str(base / "owner_summary.md"),
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
                    "proposed_maturity_date": "",
                    "owner_decision": "",
                    "owner_comment": "",
                }
            )


def _owner_summary_markdown(packet: dict[str, object]) -> str:
    summary = packet.get("export_summary", {})
    criteria = packet.get("acceptance_criteria", {})
    assert isinstance(summary, dict)
    assert isinstance(criteria, dict)
    return "\n".join(
        [
            "# Portfolio Home Maturity Remediation Summary",
            "",
            "This summary is not an approval.",
            "",
            f"- Page: `{packet.get('page_slug')}` (`{packet.get('page_id')}`)",
            f"- Report date: `{packet.get('report_date')}`",
            f"- Export status: `{packet.get('export_status')}`",
            "- Required TYW fields: `proposed_maturity_date`, `owner_decision`, `owner_comment`",
            "- Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`",
            f"- Strict gate: `{criteria.get('strict_gate_command')}`",
            f"- Bond no-maturity rows: `{summary.get('bond_no_maturity_rows')}`",
            (
                "- Bond no-maturity market value: "
                f"`{summary.get('bond_no_maturity_market_value')}`"
            ),
            (
                "- Bond remediation rows (compatibility): "
                f"`{summary.get('bond_missing_maturity_rows')}`"
            ),
            f"- TYW liability missing maturity rows: `{summary.get('tyw_liability_missing_maturity_rows')}`",
            (
                "- TYW liability missing maturity principal: "
                f"`{summary.get('tyw_liability_missing_maturity_principal')}`"
            ),
            "- Decision queue: `tyw_liability_missing_maturity.csv` only",
            "- Compatibility file: `bond_missing_maturity.csv` is header-only; no bond owner decision is required.",
            "- Bond ledger boundary: null `maturity_date` means no maturity date and requires no owner-supplied date.",
            (
                "- Generated owner fields must be blank: "
                f"`{str(criteria.get('generated_owner_fields_must_be_blank')).lower()}`"
            ),
            "- Boundary: generated CSV fields are blank and do not fill or infer maturity dates.",
            "",
            "## Owner Instructions",
            "",
            "- Fill `owner_decision` on every TYW liability row.",
            "- Fill `owner_comment` on every TYW liability row for every decision value.",
            "- Use `remediate_source` only when the TYW source maturity date will be fixed and rematerialized.",
            "- Use `approve_scoped_exclusion` only with a signed TYW exclusion rationale in `owner_comment`.",
            "- Do not use frontend-inferred dates or synthetic TYW maturity dates as remediation evidence.",
            "- After owner decisions are captured, do not rerun the normal export; use `--check-current` before owner-decision intake.",
            "",
            "## Post-Decision Verification",
            "",
            (
                "- `python scripts/portfolio_home_maturity_remediation_export.py "
                f"--report-date {packet.get('report_date')} --output-dir docs/portfolio/maturity-remediation --check-current`"
            ),
            f"- `{criteria.get('strict_gate_command')}`",
            (
                "- `python scripts/portfolio_home_dependency_consistency_check.py "
                f"--report-date {packet.get('report_date')} --limit 3 --require-consistent`"
            ),
            (
                "- `python scripts/portfolio_home_owner_decision_intake_check.py "
                f"--report-date {packet.get('report_date')} --limit 3 --require-ready`"
            ),
            (
                "- `python scripts/portfolio_home_closure_scorecard.py "
                f"--report-date {packet.get('report_date')} --limit 3 --require-full-score`"
            ),
            "",
            (
                "A filled TYW CSV is still not approval until source remediation or signed exclusion "
                "evidence is captured and the business-owner approval template is completed."
            ),
            "",
        ],
    )


def _default_output_dir(output_dir: Path, report_date: str) -> Path:
    return output_dir / report_date


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
    summary = _export_summary(queue)
    blockers = queue.get("remediation_blockers", [])
    assert isinstance(blockers, list)
    acceptance = _acceptance_criteria(report_date)
    packet: dict[str, object] = {
        "packet_kind": "portfolio_home_maturity_remediation_export",
        "page_id": queue["page_id"],
        "page_slug": queue["page_slug"],
        "report_date": report_date,
        "duckdb_path": str(duckdb_path),
        "export_status": "clean" if not blockers else "blocked",
        "remediation_blockers": blockers,
        "export_summary": summary,
        "acceptance_criteria": acceptance,
        "export_files": None,
    }
    if not blockers:
        return packet

    target_dir = _default_output_dir(output_dir, report_date)
    bond_csv = target_dir / "bond_missing_maturity.csv"
    tyw_csv = target_dir / "tyw_liability_missing_maturity.csv"
    manifest_json = target_dir / "manifest.json"
    owner_summary_md = target_dir / "owner_summary.md"

    packet["export_files"] = {
        "bond_missing_maturity_csv": str(bond_csv),
        "tyw_liability_missing_maturity_csv": str(tyw_csv),
        "manifest_json": str(manifest_json),
        "owner_summary_md": str(owner_summary_md),
    }
    if write_files:
        owner_input_paths = _nonblank_owner_input_paths([bond_csv, tyw_csv])
        if owner_input_paths:
            paths = ", ".join(str(path) for path in owner_input_paths)
            raise ValueError(
                "Refusing to overwrite maturity remediation owner input: "
                f"{paths}. Use --check-current or choose a new output directory."
            )

        _write_csv(
            bond_csv,
            BOND_FIELDS,
            _csv_rows(queue.get("bond_missing_maturity_rows", [])),
        )
        _write_csv(
            tyw_csv,
                TYW_FIELDS,
                _csv_rows(queue.get("tyw_liability_missing_maturity_rows", [])),
            )
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
        "remediation_blockers",
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
    owner_fields = {"proposed_maturity_date", "owner_decision", "owner_comment"}
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
    checks: dict[str, object] = {}
    if packet["export_status"] == "clean":
        return {
            "packet_kind": "portfolio_home_maturity_remediation_export_current_check",
            "page_id": packet["page_id"],
            "page_slug": packet["page_slug"],
            "report_date": report_date,
            "artifact_dir": str(_default_output_dir(output_dir, report_date)),
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
    blockers = _manifest_blockers(
        actual=_read_json(manifest_json),
        expected=packet,
    )
    expected_owner_summary = _owner_summary_markdown(packet)
    actual_owner_summary = (
        owner_summary_md.read_text(encoding="utf-8") if owner_summary_md.exists() else None
    )
    if actual_owner_summary != expected_owner_summary:
        blockers.append("owner_summary_mismatch")
    bond_blockers, bond_check = _csv_blockers(
        path=Path(str(export_files["bond_missing_maturity_csv"])),
        name="bond_missing_maturity",
        fields=BOND_FIELDS,
        expected_rows=_csv_rows(queue.get("bond_missing_maturity_rows", [])),
    )
    tyw_blockers, tyw_check = _csv_blockers(
        path=Path(str(export_files["tyw_liability_missing_maturity_csv"])),
        name="tyw_liability_missing_maturity",
        fields=TYW_FIELDS,
        expected_rows=_csv_rows(queue.get("tyw_liability_missing_maturity_rows", [])),
    )
    blockers.extend(bond_blockers)
    blockers.extend(tyw_blockers)
    checks = {
        "manifest": {
            "path": str(manifest_json),
            "status": "current" if "manifest_export_summary_mismatch" not in blockers else "stale",
        },
        "owner_summary": {
            "path": str(owner_summary_md),
            "status": "current" if actual_owner_summary == expected_owner_summary else "stale",
        },
        "bond_missing_maturity_csv": bond_check,
        "tyw_liability_missing_maturity_csv": tyw_check,
    }
    current = not blockers
    return {
        "packet_kind": "portfolio_home_maturity_remediation_export_current_check",
        "page_id": packet["page_id"],
        "page_slug": packet["page_slug"],
        "report_date": report_date,
        "artifact_dir": str(_default_output_dir(output_dir, report_date)),
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
        description="Export portfolio-home missing-maturity remediation queues for data-owner review.",
    )
    parser.add_argument("--duckdb-path", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--report-date", default=DEFAULT_REPORT_DATE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless no maturity remediation export is required.",
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
