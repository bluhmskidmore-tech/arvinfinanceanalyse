from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import duckdb

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.bond_analytics_service import (
    DV01_LIMIT_CONFIG_CLASSES,
    DV01_LIMIT_CONFIG_REQUIRED_FIELDS,
    DV01_LIMIT_CONFIG_STREAM,
    get_dv01_limit_config_status,
)
from backend.app.tasks.broker import register_actor_once


def _emit_json_payload(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered, file=sys.stdout)


def _write_bond_dv01_limit_config_template(template_path: str) -> dict[str, object]:
    target = Path(template_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(DV01_LIMIT_CONFIG_REQUIRED_FIELDS))
        writer.writeheader()
        for accounting_class in DV01_LIMIT_CONFIG_CLASSES:
            writer.writerow(
                {
                    "accounting_class": accounting_class,
                    "limit_dv01": "",
                    "warning_dv01": "",
                    "hedge_target_dv01": "",
                    "limit_source": "",
                    "limit_source_version": "",
                    "limit_rule_version": "",
                    "limit_effective_date": "",
                }
            )
    return {
        "status": "template_written",
        "template_path": str(target),
        "required_accounting_classes": list(DV01_LIMIT_CONFIG_CLASSES),
        "required_fields": list(DV01_LIMIT_CONFIG_REQUIRED_FIELDS),
    }


def _check_bond_dv01_limit_config_status(
    *,
    governance_dir: str | None = None,
    report_date: str | date | None = None,
) -> dict[str, object]:
    settings = get_settings()
    governance_path = Path(governance_dir or settings.governance_path)
    status_report_date = _resolve_status_report_date(report_date, [])
    return {
        "status": "status_checked",
        "config_stream": DV01_LIMIT_CONFIG_STREAM,
        "governance_dir": str(governance_path),
        "report_date": status_report_date.isoformat(),
        "limit_config_status": _current_status_payload(governance_path, status_report_date),
    }


def _build_bond_dv01_limit_config_reference_baseline(
    *,
    duckdb_path: str | None = None,
    report_date: str | date | None = None,
) -> dict[str, object]:
    settings = get_settings()
    db_path = Path(duckdb_path or settings.duckdb_path)
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        table_exists = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where table_name = 'fact_formal_bond_analytics_daily'
            """
        ).fetchone()[0]
        if not table_exists:
            resolved_report_date = _resolve_status_report_date(report_date, [])
            baseline = {}
            unmapped: list[str] = []
        else:
            resolved_report_date = _resolve_reference_report_date(conn, report_date)
            baseline = _reference_baseline_by_class(conn, resolved_report_date)
            unmapped = _reference_unmapped_classes(conn, resolved_report_date)
    finally:
        conn.close()

    rows = [
        _reference_baseline_row(accounting_class, baseline.get(accounting_class, {}))
        for accounting_class in ("AC", "OCI", "TPL")
    ]
    rows.append(_reference_baseline_row("all", baseline.get("all", {})))
    return {
        "status": "reference_baseline_built",
        "source_table": "fact_formal_bond_analytics_daily",
        "duckdb_path": str(db_path),
        "report_date": resolved_report_date.isoformat(),
        "business_limit_fields_blank": True,
        "note": "Reference only; business-approved DV01 limits must still be filled manually.",
        "required_accounting_classes": list(DV01_LIMIT_CONFIG_CLASSES),
        "unmapped_accounting_classes": unmapped,
        "rows": rows,
    }


def _write_bond_dv01_limit_config_reference_baseline_csv(
    output_path: str,
    *,
    report_date: str | date | None = None,
) -> dict[str, object]:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _build_bond_dv01_limit_config_reference_baseline(report_date=report_date)
    fieldnames = [
        "accounting_class",
        "current_position_count",
        "current_face_value",
        "current_market_value",
        "current_total_dv01",
        "current_face_weighted_modified_duration",
        "limit_dv01",
        "warning_dv01",
        "hedge_target_dv01",
        "limit_source",
        "limit_source_version",
        "limit_rule_version",
        "limit_effective_date",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["rows"]:
            writer.writerow(
                {
                    "accounting_class": row["accounting_class"],
                    "current_position_count": row["position_count"],
                    "current_face_value": row["face_value"],
                    "current_market_value": row["market_value"],
                    "current_total_dv01": row["current_total_dv01"],
                    "current_face_weighted_modified_duration": row["face_weighted_modified_duration"],
                    "limit_dv01": "",
                    "warning_dv01": "",
                    "hedge_target_dv01": "",
                    "limit_source": "",
                    "limit_source_version": "",
                    "limit_rule_version": "",
                    "limit_effective_date": "",
                }
            )
    return {
        "status": "reference_baseline_csv_written",
        "output_path": str(target),
        "report_date": payload["report_date"],
        "source_table": payload["source_table"],
        "business_limit_fields_blank": True,
        "unmapped_accounting_classes": payload["unmapped_accounting_classes"],
        "required_accounting_classes": payload["required_accounting_classes"],
    }


def _import_bond_dv01_limit_config(
    *,
    config_path: str,
    governance_dir: str | None = None,
    report_date: str | date | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    settings = get_settings()
    governance_path = Path(governance_dir or settings.governance_path)
    raw_records, load_errors = _load_config_records(Path(config_path))
    normalized_records, validation_errors = _normalize_config_records(raw_records)
    validation_errors = [*load_errors, *validation_errors]
    configured_classes = _ordered_classes(record["accounting_class"] for record in normalized_records)
    missing_classes = [item for item in DV01_LIMIT_CONFIG_CLASSES if item not in configured_classes]
    if missing_classes:
        validation_errors.append(f"Missing direct DV01 limit config for classes: {', '.join(missing_classes)}")
    status_report_date = _resolve_status_report_date(report_date, normalized_records)
    status_payload = _current_status_payload(governance_path, status_report_date)

    if validation_errors:
        return _result_payload(
            status="blocked",
            config_path=Path(config_path),
            governance_path=governance_path,
            status_report_date=status_report_date,
            configured_classes=configured_classes,
            missing_classes=missing_classes,
            records_loaded=len(raw_records),
            records_written=0,
            dry_run=dry_run,
            validation_errors=validation_errors,
            status_payload=status_payload,
        )

    if dry_run:
        return _result_payload(
            status="validated",
            config_path=Path(config_path),
            governance_path=governance_path,
            status_report_date=status_report_date,
            configured_classes=configured_classes,
            missing_classes=[],
            records_loaded=len(raw_records),
            records_written=0,
            dry_run=True,
            validation_errors=[],
            status_payload=status_payload,
        )

    records_to_write = [
        _record_for_governance(record, report_date=status_report_date)
        for record in normalized_records
    ]
    repo = GovernanceRepository(base_dir=governance_path)
    repo.append_many_atomic([(DV01_LIMIT_CONFIG_STREAM, record) for record in records_to_write])
    status_payload = _current_status_payload(governance_path, status_report_date)
    return _result_payload(
        status="imported",
        config_path=Path(config_path),
        governance_path=governance_path,
        status_report_date=status_report_date,
        configured_classes=configured_classes,
        missing_classes=[],
        records_loaded=len(raw_records),
        records_written=len(records_to_write),
        dry_run=False,
        validation_errors=[],
        status_payload=status_payload,
    )


def _load_config_records(config_path: Path) -> tuple[list[dict[str, object]], list[str]]:
    if not config_path.exists():
        return [], [f"Config file does not exist: {config_path}"]
    try:
        if config_path.suffix.lower() == ".csv":
            return _load_csv_records(config_path), []
        if config_path.suffix.lower() == ".jsonl":
            return _load_jsonl_records(config_path), []
        return _load_json_records(config_path), []
    except (OSError, json.JSONDecodeError, csv.Error) as exc:
        return [], [f"Failed to load DV01 limit config file: {exc}"]


def _load_json_records(config_path: Path) -> list[dict[str, object]]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    return []


def _load_jsonl_records(config_path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in config_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _load_csv_records(config_path: Path) -> list[dict[str, object]]:
    with config_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _normalize_config_records(records: list[dict[str, object]]) -> tuple[list[dict[str, str]], list[str]]:
    normalized: list[dict[str, str]] = []
    errors: list[str] = []
    seen_classes: set[str] = set()
    if not records:
        return [], ["DV01 limit config file has no records."]

    for index, record in enumerate(records, start=1):
        row_errors: list[str] = []
        missing_fields = [
            field
            for field in DV01_LIMIT_CONFIG_REQUIRED_FIELDS
            if not _field_has_value(record.get(field))
        ]
        if missing_fields:
            row_errors.append(f"missing fields: {', '.join(missing_fields)}")
        accounting_class = _normalize_accounting_class(record.get("accounting_class"))
        if accounting_class is None:
            row_errors.append("accounting_class must be AC, OCI, TPL, or all")
        elif accounting_class in seen_classes:
            row_errors.append(f"duplicate accounting_class: {accounting_class}")

        for field in ("limit_dv01", "warning_dv01", "hedge_target_dv01"):
            parsed = _positive_decimal(record.get(field))
            if parsed is None:
                row_errors.append(f"{field} must be greater than 0")

        effective_date = _parse_iso_date(record.get("limit_effective_date"))
        if effective_date is None:
            row_errors.append("limit_effective_date must be an ISO date")

        if row_errors:
            errors.append(f"Row {index}: {'; '.join(row_errors)}")
            continue

        assert accounting_class is not None
        seen_classes.add(accounting_class)
        normalized.append(
            {
                "accounting_class": accounting_class,
                "limit_dv01": _decimal_text(record["limit_dv01"]),
                "warning_dv01": _decimal_text(record["warning_dv01"]),
                "hedge_target_dv01": _decimal_text(record["hedge_target_dv01"]),
                "limit_source": str(record["limit_source"]).strip(),
                "limit_source_version": str(record["limit_source_version"]).strip(),
                "limit_rule_version": str(record["limit_rule_version"]).strip(),
                "limit_effective_date": effective_date.isoformat(),
            }
        )
    return normalized, errors


def _record_for_governance(record: dict[str, str], *, report_date: date) -> dict[str, object]:
    return {
        **record,
        "report_date": report_date.isoformat(),
        "imported_at": datetime.now(UTC).isoformat(),
    }


def _result_payload(
    *,
    status: str,
    config_path: Path,
    governance_path: Path,
    status_report_date: date,
    configured_classes: list[str],
    missing_classes: list[str],
    records_loaded: int,
    records_written: int,
    dry_run: bool,
    validation_errors: list[str],
    status_payload: dict[str, object],
) -> dict[str, object]:
    return {
        "status": status,
        "config_stream": DV01_LIMIT_CONFIG_STREAM,
        "config_path": str(config_path),
        "governance_dir": str(governance_path),
        "report_date": status_report_date.isoformat(),
        "required_accounting_classes": list(DV01_LIMIT_CONFIG_CLASSES),
        "configured_accounting_classes": configured_classes,
        "missing_accounting_classes": missing_classes,
        "required_fields": list(DV01_LIMIT_CONFIG_REQUIRED_FIELDS),
        "records_loaded": records_loaded,
        "records_written": records_written,
        "dry_run": dry_run,
        "validation_errors": validation_errors,
        "limit_config_status": status_payload,
    }


def _current_status_payload(governance_path: Path, report_date: date) -> dict[str, object]:
    with _temporary_governance_path(governance_path):
        return get_dv01_limit_config_status(report_date)


def _resolve_reference_report_date(conn: duckdb.DuckDBPyConnection, report_date: str | date | None) -> date:
    if isinstance(report_date, date):
        return report_date
    if report_date:
        return date.fromisoformat(str(report_date))
    row = conn.execute("select max(cast(report_date as date)) from fact_formal_bond_analytics_daily").fetchone()
    if row is None or row[0] is None:
        return date.today()
    return row[0]


def _reference_baseline_by_class(conn: duckdb.DuckDBPyConnection, report_date: date) -> dict[str, dict[str, object]]:
    rows = conn.execute(
        """
        select
            case
                when accounting_class in ('AC', 'OCI', 'TPL') then accounting_class
                else 'all'
            end as accounting_class,
            count(*) as position_count,
            coalesce(sum(face_value), 0) as face_value,
            coalesce(sum(market_value), 0) as market_value,
            coalesce(sum(dv01), 0) as current_total_dv01,
            case
                when coalesce(sum(face_value), 0) > 0
                then coalesce(sum(face_value * modified_duration), 0) / sum(face_value)
                else 0
            end as face_weighted_modified_duration
        from fact_formal_bond_analytics_daily
        where cast(report_date as date) = ?
        group by 1
        """,
        [report_date],
    ).fetchall()
    result = {str(row[0]): _reference_baseline_payload(row) for row in rows}
    direct_total = conn.execute(
        """
        select
            count(*) as position_count,
            coalesce(sum(face_value), 0) as face_value,
            coalesce(sum(market_value), 0) as market_value,
            coalesce(sum(dv01), 0) as current_total_dv01,
            case
                when coalesce(sum(face_value), 0) > 0
                then coalesce(sum(face_value * modified_duration), 0) / sum(face_value)
                else 0
            end as face_weighted_modified_duration
        from fact_formal_bond_analytics_daily
        where cast(report_date as date) = ?
        """,
        [report_date],
    ).fetchone()
    if direct_total is not None:
        result["all"] = _reference_baseline_payload(("all", *direct_total))
    return result


def _reference_unmapped_classes(conn: duckdb.DuckDBPyConnection, report_date: date) -> list[str]:
    rows = conn.execute(
        """
        select distinct accounting_class
        from fact_formal_bond_analytics_daily
        where cast(report_date as date) = ?
          and (accounting_class not in ('AC', 'OCI', 'TPL') or accounting_class is null)
        order by accounting_class
        """,
        [report_date],
    ).fetchall()
    return [str(row[0] or "null") for row in rows]


def _reference_baseline_payload(row: tuple[object, ...]) -> dict[str, object]:
    return {
        "position_count": int(row[1] or 0),
        "face_value": _decimal_output(row[2]),
        "market_value": _decimal_output(row[3]),
        "current_total_dv01": _decimal_output(row[4]),
        "face_weighted_modified_duration": _decimal_output(row[5]),
    }


def _reference_baseline_row(accounting_class: str, baseline: dict[str, object]) -> dict[str, object]:
    return {
        "accounting_class": accounting_class,
        "position_count": int(baseline.get("position_count") or 0),
        "face_value": str(baseline.get("face_value") or "0"),
        "market_value": str(baseline.get("market_value") or "0"),
        "current_total_dv01": str(baseline.get("current_total_dv01") or "0"),
        "face_weighted_modified_duration": str(baseline.get("face_weighted_modified_duration") or "0"),
        "limit_dv01": "",
        "warning_dv01": "",
        "hedge_target_dv01": "",
        "limit_source": "",
        "limit_source_version": "",
        "limit_rule_version": "",
        "limit_effective_date": "",
    }


@contextmanager
def _temporary_governance_path(governance_path: Path) -> Iterator[None]:
    previous = os.environ.get("MOSS_GOVERNANCE_PATH")
    os.environ["MOSS_GOVERNANCE_PATH"] = str(governance_path)
    get_settings.cache_clear()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("MOSS_GOVERNANCE_PATH", None)
        else:
            os.environ["MOSS_GOVERNANCE_PATH"] = previous
        get_settings.cache_clear()


def _resolve_status_report_date(report_date: str | date | None, records: list[dict[str, str]]) -> date:
    if isinstance(report_date, date):
        return report_date
    if report_date:
        return date.fromisoformat(str(report_date))
    effective_dates = [date.fromisoformat(record["limit_effective_date"]) for record in records]
    if effective_dates:
        return max(effective_dates)
    return date.today()


def _ordered_classes(values: Iterator[str] | list[str]) -> list[str]:
    available = set(values)
    return [item for item in DV01_LIMIT_CONFIG_CLASSES if item in available]


def _field_has_value(value: object) -> bool:
    return str(value or "").strip() != ""


def _normalize_accounting_class(value: object) -> str | None:
    text = str(value or "").strip()
    if text.lower() == "all":
        return "all"
    text = text.upper()
    if text in {"AC", "OCI", "TPL"}:
        return text
    return None


def _parse_iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _positive_decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value or "").strip())
    except (InvalidOperation, ValueError):
        return None
    if parsed <= Decimal("0"):
        return None
    return parsed


def _decimal_text(value: object) -> str:
    parsed = _positive_decimal(value)
    if parsed is None:
        return "0"
    return format(parsed, "f")


def _decimal_output(value: object) -> str:
    if value is None:
        return "0"
    try:
        return format(Decimal(str(value)).quantize(Decimal("0.00000001")), "f")
    except (InvalidOperation, ValueError):
        return "0"


import_bond_dv01_limit_config = register_actor_once(
    "import_bond_dv01_limit_config",
    _import_bond_dv01_limit_config,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import formal DV01 limit config into the governance stream.")
    parser.add_argument("--config-path")
    parser.add_argument("--governance-dir")
    parser.add_argument("--report-date")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-template")
    parser.add_argument("--check-status", action="store_true")
    parser.add_argument("--reference-baseline", action="store_true")
    parser.add_argument("--reference-baseline-csv")
    args = parser.parse_args()

    if args.write_template:
        _emit_json_payload(_write_bond_dv01_limit_config_template(args.write_template))
        return
    if args.reference_baseline:
        _emit_json_payload(
            _build_bond_dv01_limit_config_reference_baseline(
                report_date=args.report_date,
            )
        )
        return
    if args.reference_baseline_csv:
        _emit_json_payload(
            _write_bond_dv01_limit_config_reference_baseline_csv(
                args.reference_baseline_csv,
                report_date=args.report_date,
            )
        )
        return
    if args.check_status:
        _emit_json_payload(
            _check_bond_dv01_limit_config_status(
                governance_dir=args.governance_dir,
                report_date=args.report_date,
            )
        )
        return
    if not args.config_path:
        parser.error("--config-path is required unless --write-template, --check-status, --reference-baseline, or --reference-baseline-csv is provided")

    payload = import_bond_dv01_limit_config.fn(
        config_path=args.config_path,
        governance_dir=args.governance_dir,
        report_date=args.report_date,
        dry_run=args.dry_run,
    )
    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
