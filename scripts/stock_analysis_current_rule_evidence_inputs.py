#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.governance.stock_analysis_calendar_approval_decision import (  # noqa: E402
    build_stock_analysis_calendar_approval_decision,
    validate_stock_analysis_calendar_approval_decision,
)
from backend.app.governance.stock_analysis_calendar_receipt import (  # noqa: E402
    APPROVED_AUTHORITY_STATUS,
    build_stock_analysis_calendar_receipt,
    validate_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_version_tuple import (  # noqa: E402
    build_stock_analysis_current_rule_version_tuple,
    validate_stock_analysis_current_rule_version_tuple,
)
from backend.app.governance.stock_analysis_source_availability_receipt import (  # noqa: E402
    build_stock_analysis_source_availability_receipt,
    validate_stock_analysis_source_availability_receipt,
)
from backend.app.repositories.stock_analysis_theme_overlay_reader import (  # noqa: E402
    BACKFILL_DISABLED_FINGERPRINT,
)
from backend.app.repositories.tushare_adapter import (  # noqa: E402
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)

EXIT_READY = 0
EXIT_BLOCKED = 2

CALENDAR_RECEIPT_FILENAME = "approved_calendar_receipt.json"
CALENDAR_DECISION_FILENAME = "calendar_approval_decision.json"
SOURCE_RECEIPT_FILENAME = "source_availability_receipt.json"
VERSION_TUPLE_FILENAME = "current_rule_version_tuple.json"

DEFAULT_APPROVED_BY_LABEL = "workspace_owner"
DEFAULT_RECORDED_BY_AGENT = "stock_analysis_current_rule_evidence_inputs"

# This is an explicit allow-list of persisted inputs used by the current-rule
# replay. It is intentionally not discovered from the database at runtime.
DEFAULT_SOURCE_TABLE_WHITELIST: Mapping[str, str] = {
    "choice_stock_daily_observation": "trade_date",
    "stock_adjustment_factor": "trade_date",
    "choice_stock_universe": "as_of_date",
    "choice_stock_sector_membership": "as_of_date",
    "choice_stock_concept_membership": "as_of_date",
    "choice_stock_limit_quality": "as_of_date",
    "choice_stock_factor_snapshot": "as_of_date",
    "fact_choice_macro_daily": "trade_date",
    "choice_market_snapshot": "trade_date",
    "fact_market_breadth_daily": "trade_date",
    "fact_livermore_gate_supplement_daily": "trade_date",
}

_ARTIFACT_FILENAMES = (
    CALENDAR_RECEIPT_FILENAME,
    CALENDAR_DECISION_FILENAME,
    SOURCE_RECEIPT_FILENAME,
    VERSION_TUPLE_FILENAME,
)


class EvidenceInputGenerationError(ValueError):
    """Raised when formal evidence inputs cannot be produced safely."""


def run_current_rule_evidence_inputs_cli(
    *,
    duckdb_path: str | Path,
    start_date: str,
    end_date: str,
    calendar_json: str | Path | None,
    fetch_tushare_calendar: bool,
    choice_catalog: str | Path,
    output_dir: str | Path,
    owner_approval_id: str,
    captured_at: str | None = None,
    approved_at: str | None = None,
    recorded_at: str | None = None,
    approved_by_label: str = DEFAULT_APPROVED_BY_LABEL,
    recorded_by_agent: str = DEFAULT_RECORDED_BY_AGENT,
    approval_reference: str | None = None,
    theme_overlay_fingerprint: str = BACKFILL_DISABLED_FINGERPRINT,
    table_whitelist: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Create four validated, read-only evidence inputs in a new directory."""

    target_db = _require_existing_file(duckdb_path, field_name="duckdb_path")
    catalog_path = _require_existing_file(choice_catalog, field_name="choice_catalog")
    requested_start = _strict_date(start_date, field_name="start_date")
    requested_end = _strict_date(end_date, field_name="end_date")
    if requested_end < requested_start:
        raise EvidenceInputGenerationError(
            "end_date must be on or after start_date"
        )
    normalized_owner_approval_id = _required_text(
        owner_approval_id,
        field_name="owner_approval_id",
    )
    output_path = _new_output_directory_path(output_dir)
    calendar_file_path = _calendar_source_path(
        calendar_json=calendar_json,
        fetch_tushare_calendar=fetch_tushare_calendar,
    )

    database_sha256_before = _file_sha256(target_db)
    calendar_rows = (
        _fetch_tushare_calendar_rows(
            start_date=requested_start,
            end_date=requested_end,
        )
        if fetch_tushare_calendar
        else _load_calendar_json_rows(calendar_file_path)
    )
    observed_at = _utc_datetime_text(
        captured_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        field_name="captured_at",
    )

    approved_calendar_receipt = build_stock_analysis_calendar_receipt(
        calendar_rows=_normalize_calendar_rows(calendar_rows),
        request_start_date=requested_start.isoformat(),
        request_end_date=requested_end.isoformat(),
        fetched_at=observed_at,
        authority_status=APPROVED_AUTHORITY_STATUS,
        owner_approval_id=normalized_owner_approval_id,
    )
    _require_valid(
        validate_stock_analysis_calendar_receipt(approved_calendar_receipt),
        artifact_name="approved calendar receipt",
    )

    normalized_approved_at = _utc_datetime_text(
        approved_at or observed_at,
        field_name="approved_at",
    )
    normalized_recorded_at = _utc_datetime_text(
        recorded_at or observed_at,
        field_name="recorded_at",
    )
    calendar_decision = build_stock_analysis_calendar_approval_decision(
        approved_calendar_receipt=approved_calendar_receipt,
        owner_approval_id=normalized_owner_approval_id,
        approved_at=normalized_approved_at,
        recorded_at=normalized_recorded_at,
        approved_by_label=_required_text(
            approved_by_label,
            field_name="approved_by_label",
        ),
        recorded_by_agent=_required_text(
            recorded_by_agent,
            field_name="recorded_by_agent",
        ),
        approval_reference=_required_text(
            approval_reference or normalized_owner_approval_id,
            field_name="approval_reference",
        ),
    )
    _require_valid(
        validate_stock_analysis_calendar_approval_decision(
            calendar_decision,
            approved_calendar_receipt=approved_calendar_receipt,
        ),
        artifact_name="calendar approval decision",
    )

    source_receipt = build_stock_analysis_source_availability_receipt(
        duckdb_path=target_db,
        table_whitelist=(
            dict(table_whitelist)
            if table_whitelist is not None
            else dict(DEFAULT_SOURCE_TABLE_WHITELIST)
        ),
        captured_at=observed_at,
    )
    _require_valid(
        validate_stock_analysis_source_availability_receipt(source_receipt),
        artifact_name="source availability receipt",
    )

    try:
        catalog_json = catalog_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise EvidenceInputGenerationError(
            "choice_catalog must be readable UTF-8 JSON"
        ) from exc
    version_tuple = build_stock_analysis_current_rule_version_tuple(
        approved_calendar_receipt=approved_calendar_receipt,
        source_availability_receipts=[source_receipt],
        choice_catalog_json=catalog_json,
        theme_overlay_fingerprint=theme_overlay_fingerprint,
    )
    _require_valid(
        validate_stock_analysis_current_rule_version_tuple(version_tuple),
        artifact_name="current-rule version tuple",
    )

    database_sha256_before_write = _file_sha256(target_db)
    if database_sha256_before_write != database_sha256_before:
        raise EvidenceInputGenerationError(
            "DuckDB changed while evidence inputs were being generated"
        )

    artifacts: dict[str, dict[str, Any]] = {
        "approved_calendar_receipt": approved_calendar_receipt,
        "calendar_approval_decision": calendar_decision,
        "source_availability_receipt": source_receipt,
        "current_rule_version_tuple": version_tuple,
    }
    artifact_paths = _write_and_verify_artifacts(
        output_dir=output_path,
        artifacts=artifacts,
        duckdb_path=target_db,
        database_sha256_before=database_sha256_before,
    )
    database_sha256_after = _file_sha256(target_db)
    if database_sha256_after != database_sha256_before:
        _cleanup_created_output(
            output_dir=output_path,
            artifact_paths=artifact_paths.values(),
        )
        raise EvidenceInputGenerationError(
            "DuckDB changed while evidence inputs were being persisted"
        )

    return {
        "status": "ready",
        "output_dir": str(output_path),
        "duckdb_path": str(target_db),
        "duckdb_sha256_before": database_sha256_before,
        "duckdb_sha256_after": database_sha256_after,
        "database_unchanged": True,
        "calendar_source": (
            "tushare.trade_cal:SSE"
            if fetch_tushare_calendar
            else "caller_provided_calendar_json"
        ),
        "calendar_request": {
            "start_date": requested_start.isoformat(),
            "end_date": requested_end.isoformat(),
        },
        "source_table_whitelist": dict(
            table_whitelist
            if table_whitelist is not None
            else DEFAULT_SOURCE_TABLE_WHITELIST
        ),
        "artifacts": {
            artifact_name: {
                "path": str(path),
                "file_sha256": _file_sha256(path),
            }
            for artifact_name, path in artifact_paths.items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate validated, read-only current-rule evidence inputs. "
            "This command never materializes or promotes data."
        )
    )
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    calendar_group = parser.add_mutually_exclusive_group(required=True)
    calendar_group.add_argument("--calendar-json")
    calendar_group.add_argument(
        "--fetch-tushare-calendar",
        action="store_true",
    )
    parser.add_argument("--choice-catalog", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--owner-approval-id", required=True)
    parser.add_argument("--captured-at")
    parser.add_argument("--approved-at")
    parser.add_argument("--recorded-at")
    parser.add_argument("--approved-by-label", default=DEFAULT_APPROVED_BY_LABEL)
    parser.add_argument("--recorded-by-agent", default=DEFAULT_RECORDED_BY_AGENT)
    parser.add_argument("--approval-reference")
    args = parser.parse_args(argv)

    try:
        result = run_current_rule_evidence_inputs_cli(
            duckdb_path=args.duckdb_path,
            start_date=args.start_date,
            end_date=args.end_date,
            calendar_json=args.calendar_json,
            fetch_tushare_calendar=bool(args.fetch_tushare_calendar),
            choice_catalog=args.choice_catalog,
            output_dir=args.output_dir,
            owner_approval_id=args.owner_approval_id,
            captured_at=args.captured_at,
            approved_at=args.approved_at,
            recorded_at=args.recorded_at,
            approved_by_label=args.approved_by_label,
            recorded_by_agent=args.recorded_by_agent,
            approval_reference=args.approval_reference,
        )
    except Exception as exc:  # fail closed without leaking vendor credentials
        result = {
            "status": "blocked",
            "blockers": [
                "evidence_input_generation_failed:" + type(exc).__name__
            ],
            "database_unchanged": None,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_BLOCKED

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_READY


def _fetch_tushare_calendar_rows(
    *,
    start_date: date,
    end_date: date,
) -> list[Mapping[str, object]]:
    token = resolve_tushare_token_with_settings_fallback(get_settings())
    if not token:
        raise EvidenceInputGenerationError(
            "Tushare credentials are not configured"
        )
    try:
        client = import_tushare_pro().pro_api(token)
        frame = client.trade_cal(
            exchange="SSE",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            fields="exchange,cal_date,is_open,pretrade_date",
        )
    except Exception as exc:
        raise EvidenceInputGenerationError(
            "Tushare trade_cal:SSE fetch failed"
        ) from exc

    if frame is None:
        raise EvidenceInputGenerationError(
            "Tushare trade_cal:SSE returned no calendar rows"
        )
    try:
        raw_rows = frame.to_dict(orient="records")
    except (AttributeError, TypeError, ValueError) as exc:
        raise EvidenceInputGenerationError(
            "Tushare trade_cal:SSE returned an unsupported response"
        ) from exc
    if not isinstance(raw_rows, list) or not raw_rows:
        raise EvidenceInputGenerationError(
            "Tushare trade_cal:SSE returned no calendar rows"
        )
    return _mapping_rows(raw_rows, field_name="Tushare trade_cal:SSE response")


def _calendar_source_path(
    *,
    calendar_json: str | Path | None,
    fetch_tushare_calendar: bool,
) -> Path | None:
    if fetch_tushare_calendar:
        if calendar_json is not None:
            raise EvidenceInputGenerationError(
                "calendar_json and fetch_tushare_calendar are mutually exclusive"
            )
        return None
    if calendar_json is None:
        raise EvidenceInputGenerationError(
            "calendar_json is required unless fetch_tushare_calendar is enabled"
        )
    return _require_existing_file(calendar_json, field_name="calendar_json")


def _load_calendar_json_rows(path: Path | None) -> list[Mapping[str, object]]:
    if path is None:
        raise EvidenceInputGenerationError("calendar_json path is required")
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_non_finite_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise EvidenceInputGenerationError(
            "calendar_json must be valid UTF-8 JSON without duplicate keys"
        ) from exc
    if isinstance(raw, Mapping):
        raw = raw.get("calendar_rows")
    if not isinstance(raw, list) or not raw:
        raise EvidenceInputGenerationError(
            "calendar_json must contain a non-empty row array or calendar_rows array"
        )
    return _mapping_rows(raw, field_name="calendar_json rows")


def _normalize_calendar_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        normalized.append(
            {
                "exchange": _required_text(
                    row.get("exchange", "SSE"),
                    field_name=f"calendar_rows[{index}].exchange",
                ),
                "cal_date": _vendor_date_text(
                    row.get("cal_date"),
                    field_name=f"calendar_rows[{index}].cal_date",
                ),
                "is_open": row.get("is_open"),
                "pretrade_date": _optional_vendor_date_text(
                    row.get("pretrade_date"),
                    field_name=f"calendar_rows[{index}].pretrade_date",
                ),
            }
        )
    return normalized


def _write_and_verify_artifacts(
    *,
    output_dir: Path,
    artifacts: Mapping[str, Mapping[str, object]],
    duckdb_path: Path,
    database_sha256_before: str,
) -> dict[str, Path]:
    filename_by_name = {
        "approved_calendar_receipt": CALENDAR_RECEIPT_FILENAME,
        "calendar_approval_decision": CALENDAR_DECISION_FILENAME,
        "source_availability_receipt": SOURCE_RECEIPT_FILENAME,
        "current_rule_version_tuple": VERSION_TUPLE_FILENAME,
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_link_components(output_dir.parent, field_name="output_dir parent")
    output_dir.mkdir(exist_ok=False)

    artifact_paths: dict[str, Path] = {}
    try:
        for artifact_name, payload in artifacts.items():
            filename = filename_by_name[artifact_name]
            artifact_path = _child_path(
                output_dir=output_dir,
                filename=filename,
            )
            artifact_paths[artifact_name] = artifact_path
            _write_json_exclusive(artifact_path, payload)

        persisted = {
            artifact_name: _load_json_object(path)
            for artifact_name, path in artifact_paths.items()
        }
        for artifact_name, expected in artifacts.items():
            if persisted[artifact_name] != dict(expected):
                raise EvidenceInputGenerationError(
                    f"persisted {artifact_name} does not match generated content"
                )
        _require_valid(
            validate_stock_analysis_calendar_receipt(
                persisted["approved_calendar_receipt"]
            ),
            artifact_name="persisted approved calendar receipt",
        )
        _require_valid(
            validate_stock_analysis_calendar_approval_decision(
                persisted["calendar_approval_decision"],
                approved_calendar_receipt=persisted["approved_calendar_receipt"],
            ),
            artifact_name="persisted calendar approval decision",
        )
        _require_valid(
            validate_stock_analysis_source_availability_receipt(
                persisted["source_availability_receipt"]
            ),
            artifact_name="persisted source availability receipt",
        )
        _require_valid(
            validate_stock_analysis_current_rule_version_tuple(
                persisted["current_rule_version_tuple"]
            ),
            artifact_name="persisted current-rule version tuple",
        )
        if _file_sha256(duckdb_path) != database_sha256_before:
            raise EvidenceInputGenerationError(
                "DuckDB changed while evidence artifacts were being written"
            )
    except Exception:
        _cleanup_created_output(
            output_dir=output_dir,
            artifact_paths=artifact_paths.values(),
        )
        raise
    return artifact_paths


def _write_json_exclusive(path: Path, payload: Mapping[str, object]) -> None:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_non_finite_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise EvidenceInputGenerationError(
            f"persisted artifact is not valid JSON: {path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise EvidenceInputGenerationError(
            f"persisted artifact must be a JSON object: {path.name}"
        )
    return payload


def _new_output_directory_path(path: str | Path) -> Path:
    raw = _absolute_without_resolve(path)
    _assert_no_link_components(raw, field_name="output_dir")
    if raw.exists():
        raise EvidenceInputGenerationError(
            "output_dir must be a new path; existing evidence is never overwritten"
        )
    return raw


def _child_path(*, output_dir: Path, filename: str) -> Path:
    if filename not in _ARTIFACT_FILENAMES:
        raise EvidenceInputGenerationError("artifact filename is not allowed")
    candidate = _absolute_without_resolve(output_dir / filename)
    try:
        candidate.relative_to(output_dir)
    except ValueError as exc:
        raise EvidenceInputGenerationError(
            "artifact path escaped caller-provided output_dir"
        ) from exc
    return candidate


def _cleanup_created_output(
    *,
    output_dir: Path,
    artifact_paths: Sequence[Path] | Any,
) -> None:
    for path in artifact_paths:
        candidate = _child_path(output_dir=output_dir, filename=Path(path).name)
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        output_dir.rmdir()
    except OSError:
        pass


def _assert_no_link_components(path: Path, *, field_name: str) -> None:
    current: Path | None = None
    for part in path.parts:
        current = Path(part) if current is None else current / part
        if not current.exists():
            continue
        if current.is_symlink():
            raise EvidenceInputGenerationError(
                f"{field_name} contains a symlink component"
            )
        is_junction = getattr(current, "is_junction", None)
        if callable(is_junction):
            try:
                if bool(is_junction()):
                    raise EvidenceInputGenerationError(
                        f"{field_name} contains a junction component"
                    )
            except OSError as exc:
                raise EvidenceInputGenerationError(
                    f"{field_name} link status could not be verified"
                ) from exc


def _require_existing_file(path: str | Path, *, field_name: str) -> Path:
    candidate = Path(path).resolve()
    if not candidate.is_file():
        raise EvidenceInputGenerationError(
            f"{field_name} must be an existing file"
        )
    return candidate


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _strict_date(value: object, *, field_name: str) -> date:
    text = _required_text(value, field_name=field_name)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceInputGenerationError(
            f"{field_name} must be strict YYYY-MM-DD"
        ) from exc
    if parsed.isoformat() != text:
        raise EvidenceInputGenerationError(
            f"{field_name} must be strict YYYY-MM-DD"
        )
    return parsed


def _utc_datetime_text(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceInputGenerationError(
            f"{field_name} must be an ISO UTC datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise EvidenceInputGenerationError(
            f"{field_name} must be a UTC datetime"
        )
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _vendor_date_text(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    if len(text) == 8 and text.isdigit():
        try:
            return datetime.strptime(text, "%Y%m%d").date().isoformat()
        except ValueError as exc:
            raise EvidenceInputGenerationError(
                f"{field_name} must be YYYYMMDD or YYYY-MM-DD"
            ) from exc
    return _strict_date(text, field_name=field_name).isoformat()


def _optional_vendor_date_text(
    value: object,
    *,
    field_name: str,
) -> str | None:
    if value is None or not str(value).strip():
        return None
    return _vendor_date_text(value, field_name=field_name)


def _required_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, (str, Path)):
        raise EvidenceInputGenerationError(f"{field_name} must be text")
    normalized = str(value).strip()
    if not normalized:
        raise EvidenceInputGenerationError(f"{field_name} must be non-empty")
    return normalized


def _mapping_rows(
    rows: Sequence[object],
    *,
    field_name: str,
) -> list[Mapping[str, object]]:
    result: list[Mapping[str, object]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise EvidenceInputGenerationError(
                f"{field_name}[{index}] must be an object"
            )
        result.append(row)
    return result


def _require_valid(
    validation: tuple[bool, tuple[str, ...]],
    *,
    artifact_name: str,
) -> None:
    ok, errors = validation
    if not ok:
        detail = "; ".join(errors) or "unknown validation error"
        raise EvidenceInputGenerationError(
            f"{artifact_name} validation failed: {detail}"
        )


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant: {value}")


def _absolute_without_resolve(path: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(path))))


if __name__ == "__main__":
    raise SystemExit(main())
