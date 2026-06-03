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
    args = parser.parse_args()

    if args.write_template:
        _emit_json_payload(_write_bond_dv01_limit_config_template(args.write_template))
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
        parser.error("--config-path is required unless --write-template or --check-status is provided")

    payload = import_bond_dv01_limit_config.fn(
        config_path=args.config_path,
        governance_dir=args.governance_dir,
        report_date=args.report_date,
        dry_run=args.dry_run,
    )
    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
