"""Deterministic 2026-07-31 Decimal-precision backfill entry point.

This command is deliberately narrower than ``run_global_data_refresh.py``.  It
accepts only the pinned report date and ingest batch, validates immutable local
inputs with read-only checks, and invokes exactly the snapshot, balance, bond,
and risk actors.  It never ingests sources, materializes FX, prepares curves,
or fetches vendor data.

The command is an execution mechanism, not an approval mechanism.  Write mode
requires operator-provided maintenance-window and DBA-backup references, but it
cannot independently validate those external artifacts or remove the BLOCKED
state recorded in the production runbook.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from time import perf_counter
from typing import Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.app.governance.settings import get_settings  # noqa: E402


RUNNER_VERSION = "decimal_precision_backfill.runner.v1"
GLOBAL_REFRESH_LOCK_KEY = "lock:global-core-data-refresh"
TARGET_REPORT_DATE = "2026-07-31"
TARGET_INGEST_BATCH_ID = "ib_caddbbe10b2e"
TARGET_SOURCE_FAMILIES = ("zqtz", "tyw")
REQUIRED_SCHEMA_MIGRATIONS = tuple(range(1, 40))

SOURCE_CONTRACTS: dict[str, dict[str, object]] = {
    "zqtz": {
        "source_version": "sv_de5be20e6794",
        "file_name": "ZQTZSHOW-20260731__96e96983b31f__ib_caddbbe10b2e.xls",
        "bytes": 1_396_224,
        "sha256": "DE5BE20E6794F50326E4171D2094F4F6AE62E75DA170F269013F05D2333FB132",
        "raw_rows": 1_872,
        "canonical_rows": 1_872,
    },
    "tyw": {
        "source_version": "sv_7023ef05edc8",
        "file_name": "TYWLSHOW-20260731__37b24b37611d__ib_caddbbe10b2e.xls",
        "bytes": 1_433_088,
        "sha256": "7023EF05EDC8E65D85B97981123896D36F71957F8EAAE13AF783DF999B57883B",
        "raw_rows": 3_133,
        "canonical_rows": 3_128,
    },
}

EXPECTED_TARGET_COUNTS = {
    "zqtz_bond_daily_snapshot": 1_872,
    "tyw_interbank_daily_snapshot": 3_128,
    "fact_formal_zqtz_balance_daily": 3_744,
    "fact_formal_tyw_balance_daily": 6_256,
    "fact_formal_bond_analytics_daily": 1_750,
    "fact_formal_risk_tensor_daily": 1,
}
VERIFIER_ALLOWED_TARGET_DATE_TABLES = tuple(sorted(EXPECTED_TARGET_COUNTS))
VERIFIER_ALLOWED_TARGET_DATE_TABLE_KEYS = tuple(
    f"main.{table}" for table in VERIFIER_ALLOWED_TARGET_DATE_TABLES
)
VERIFIER_FROZEN_TABLES = (
    "fact_formal_yield_curve_daily",
    "fx_daily_mid",
)
VERIFIER_FROZEN_TABLE_KEYS = tuple(f"main.{table}" for table in VERIFIER_FROZEN_TABLES)
VERIFIER_OTHER_TABLES_POLICY = "unchanged_full_table_digest"
VERIFIER_ALGORITHM_MARKERS = {
    "canonical_serialization": "typed length-framed UTF-8/binary bytes; Decimal as sign+digits+exponent tuple",
    "inventory_scope": "BASE TABLE only; views/indexes/constraints require the runner schema-registry gate",
}
RECEIPT_COUNT_CONTRACT = {
    "snapshot_zqtz": 1_872,
    "snapshot_tyw": 3_128,
    "balance_zqtz": 3_744,
    "balance_tyw": 6_256,
    "bond": 1_750,
    "risk_rows": 1,
    "raw_parsed_zqtz": 1_872,
    "raw_parsed_tyw": 3_133,
}

STAGE_TABLES = {
    "snapshot": ("zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"),
    "balance": ("fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"),
    "bond": ("fact_formal_bond_analytics_daily",),
    "risk": ("fact_formal_risk_tensor_daily",),
}
REQUIRED_LINEAGE_FIELDS = {
    "zqtz_bond_daily_snapshot": (
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ),
    "tyw_interbank_daily_snapshot": (
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ),
    "fact_formal_zqtz_balance_daily": (
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ),
    "fact_formal_tyw_balance_daily": (
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ),
    "fact_formal_bond_analytics_daily": (
        "source_version",
        "rule_version",
        "ingest_batch_id",
        "trace_id",
    ),
    "fact_formal_risk_tensor_daily": (
        "source_version",
        "rule_version",
        "cache_version",
        "upstream_source_version",
        "upstream_rule_version",
        "upstream_cache_version",
        "liability_source_version",
        "liability_rule_version",
        "trace_id",
    ),
}

FORMAL_STAGE_CONTRACTS = {
    "balance": {
        "cache_key": "balance_analysis:materialize:formal",
        "rule_version": "rv_balance_analysis_formal_materialize_v1",
        "cache_version": "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
        "counts": {"zqtz_rows": 3_744, "tyw_rows": 6_256},
        "fact_tables": (
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        ),
    },
    "bond": {
        "cache_key": "bond_analytics:materialize:formal",
        "rule_version": "rv_bond_analytics_formal_materialize_v1",
        "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1",
        "counts": {"row_count": 1_750},
        "fact_tables": ("fact_formal_bond_analytics_daily",),
    },
    "risk": {
        "cache_key": "risk_tensor:materialize:formal",
        "rule_version": "rv_risk_tensor_formal_materialize_v5",
        "cache_version": "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v5",
        "counts": {"bond_count": 1_750},
        "fact_tables": ("fact_formal_risk_tensor_daily",),
    },
}

EXPECTED_FX = {
    "AUD": {
        "rate": Decimal("4.74410000"),
        "lineage": (
            "CFETS",
            "sv_fx_chinamoney_4d21e1e9a6c3",
            "chinamoney",
            "vv_chinamoney_fx_20260731_4d21e1e9a6c3",
            "EMM00058129",
        ),
    },
    "CAD": {
        "rate": Decimal("4.82060000"),
        "lineage": (
            "CFETS",
            "sv_fx_chinamoney_4d21e1e9a6c3",
            "chinamoney",
            "vv_chinamoney_fx_20260731_4d21e1e9a6c3",
            "EMM00058130",
        ),
    },
    "EUR": {
        "rate": Decimal("7.78860000"),
        "lineage": (
            "CFETS",
            "sv_fx_chinamoney_4d21e1e9a6c3",
            "chinamoney",
            "vv_chinamoney_fx_20260731_4d21e1e9a6c3",
            "EMM00058125",
        ),
    },
    "HKD": {
        "rate": Decimal("0.86559000"),
        "lineage": (
            "CFETS",
            "sv_fx_chinamoney_4d21e1e9a6c3",
            "chinamoney",
            "vv_chinamoney_fx_20260731_4d21e1e9a6c3",
            "EMM01588399",
        ),
    },
    "USD": {
        "rate": Decimal("6.78940000"),
        "lineage": (
            "CFETS",
            "sv_fx_chinamoney_4d21e1e9a6c3",
            "chinamoney",
            "vv_chinamoney_fx_20260731_4d21e1e9a6c3",
            "EMM00058124",
        ),
    },
}

CURVE_CONTRACTS = {
    "aaa_credit": {
        "points": 9,
        "vendor_name": "choice",
        "vendor_version": "vv_choice_aaa_credit_20260630_8c11af661fd4",
        "source_version": "sv_yield_curve_aaa_credit_8c11af661fd4",
        "sha256": "6433D1B9E3A2373A25637470201CBC46947979A70D3A185FB680130502B0F8F9",
    },
    "cdb": {
        "points": 8,
        "vendor_name": "choice",
        "vendor_version": "vv_choice_cdb_20260630_3a6861339722",
        "source_version": "sv_yield_curve_cdb_3a6861339722",
        "sha256": "7C85EDF86AE1D07C32FCCBC705C9193C12B46063E720E79A8405232CDDCCEB56",
    },
    "treasury": {
        "points": 9,
        "vendor_name": "akshare",
        "vendor_version": "vv_akshare_treasury_20260630_f91623b0de5c",
        "source_version": "sv_yield_curve_treasury_f91623b0de5c",
        "sha256": "DBD41DF5E9EC93347610E394E58DBCF1A17C3027B7B0E0E24B4F5C35C5C602CD",
    },
}

KNOWN_SOURCE_WARNINGS = (
    {
        "instrument_code": "XS3034102791",
        "field": "ytm",
        "source_value": "878.3497",
        "handling": "formal bond analytics normalizes the value to missing; this backfill does not correct it",
    },
    {
        "instrument_code": "XS3047137040",
        "field": "ytm",
        "source_value": "20720.9302",
        "handling": "formal bond analytics normalizes the value to missing; this backfill does not correct it",
    },
)


class DecimalPrecisionBackfillFailed(RuntimeError):
    """Raised after a fail-closed receipt has been assembled."""

    def __init__(self, receipt: dict[str, object]):
        self.receipt = receipt
        super().__init__(
            f"Decimal precision backfill failed at {receipt.get('failed_step')}"
        )


@dataclass(frozen=True)
class BackfillPaths:
    duckdb_path: Path
    governance_dir: Path
    archive_root: Path
    baseline_db_path: Path
    receipt_path: Path
    verifier_temp_dir: Path


@dataclass(frozen=True)
class BackfillActors:
    snapshot: Callable[..., dict[str, object]]
    balance: Callable[..., dict[str, object]]
    bond: Callable[..., dict[str, object]]
    risk: Callable[..., dict[str, object]]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _file_fingerprint(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": _file_sha256(path),
    }


def _require_unchanged_fingerprint(
    path: Path,
    expected: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    observed = _file_fingerprint(path)
    _require(
        observed == dict(expected),
        f"{label} changed after preflight: expected={dict(expected)!r}, observed={observed!r}",
    )
    return observed


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _resolve_paths(
    *,
    duckdb_path: str | Path,
    governance_dir: str | Path,
    archive_root: str | Path,
    baseline_db_path: str | Path,
    receipt_path: str | Path,
    verifier_temp_dir: str | Path,
) -> BackfillPaths:
    raw = {
        "duckdb_path": Path(duckdb_path),
        "governance_dir": Path(governance_dir),
        "archive_root": Path(archive_root),
        "baseline_db_path": Path(baseline_db_path),
        "receipt_path": Path(receipt_path),
        "verifier_temp_dir": Path(verifier_temp_dir),
    }
    for name, path in raw.items():
        _require(
            path.is_absolute(), f"{name} must be an explicit absolute path: {path}"
        )

    paths = BackfillPaths(**{name: path.resolve() for name, path in raw.items()})
    _require(
        paths.duckdb_path.is_file(), f"DuckDB file does not exist: {paths.duckdb_path}"
    )
    _require(
        paths.baseline_db_path.is_file(),
        f"Baseline DuckDB does not exist: {paths.baseline_db_path}",
    )
    _require(
        paths.governance_dir.is_dir(),
        f"Governance directory does not exist: {paths.governance_dir}",
    )
    _require(
        paths.archive_root.is_dir(),
        f"Archive root does not exist: {paths.archive_root}",
    )
    _require(
        paths.receipt_path.parent.is_dir(),
        f"Receipt parent does not exist: {paths.receipt_path.parent}",
    )
    _require(
        paths.verifier_temp_dir.is_dir(),
        f"Verifier temp directory does not exist: {paths.verifier_temp_dir}",
    )
    _require(
        not _same_path(paths.duckdb_path, paths.baseline_db_path),
        "Baseline and current DuckDB paths must be distinct.",
    )
    _require(
        not _same_path(paths.receipt_path, paths.duckdb_path)
        and not _same_path(paths.receipt_path, paths.baseline_db_path),
        "Receipt path must not overwrite either DuckDB input.",
    )
    for label, evidence_path in (
        ("baseline_db_path", paths.baseline_db_path),
        ("receipt_path", paths.receipt_path),
        ("verifier_temp_dir", paths.verifier_temp_dir),
    ):
        _require(
            not _is_within(evidence_path, paths.archive_root),
            f"{label} must not be inside the immutable archive root: {evidence_path}",
        )
        _require(
            not _is_within(evidence_path, paths.governance_dir),
            f"{label} must not be inside the governance directory: {evidence_path}",
        )
    return paths


def _probe_git(repo_root: Path) -> dict[str, object]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    return {
        "repo_root": str(Path(run("rev-parse", "--show-toplevel")).resolve()),
        "head": run("rev-parse", "HEAD"),
        "status": run("status", "--porcelain=v1", "--untracked-files=all"),
    }


def _validate_production_gate(
    *,
    paths: BackfillPaths,
    approved_commit: str | None,
    settings: object,
    git_probe: Callable[[Path], dict[str, object]],
) -> dict[str, object]:
    expected_commit = str(approved_commit or "").strip()
    _require(
        re.fullmatch(r"[0-9a-fA-F]{40}", expected_commit) is not None,
        "Write/read-only production preflight requires an approved full 40-character Git commit SHA.",
    )
    _require(
        str(getattr(settings, "environment", "")).strip().lower() == "production",
        "MOSS environment must be production.",
    )
    _require(
        str(getattr(settings, "governance_backend", "")).strip() == "sql-authority",
        "Production governance_backend must be sql-authority.",
    )
    _require(
        str(getattr(settings, "source_preview_governance_backend", "")).strip()
        == "sql-authority",
        "Production source_preview_governance_backend must be sql-authority.",
    )
    _require(
        bool(str(getattr(settings, "governance_sql_dsn", "")).strip()),
        "Production governance SQL authority must be configured.",
    )

    settings_paths = {
        "duckdb_path": Path(str(getattr(settings, "duckdb_path", ""))).resolve(),
        "governance_dir": Path(str(getattr(settings, "governance_path", ""))).resolve(),
        "archive_root": Path(
            str(getattr(settings, "local_archive_path", ""))
        ).resolve(),
    }
    for name, expected_path in settings_paths.items():
        actual_path = getattr(paths, name)
        _require(
            _same_path(actual_path, expected_path),
            f"Explicit {name} does not match resolved production settings: explicit={actual_path}, settings={expected_path}",
        )

    repo_root = ROOT.resolve()
    for label, evidence_path in (
        ("baseline_db_path", paths.baseline_db_path),
        ("receipt_path", paths.receipt_path),
        ("verifier_temp_dir", paths.verifier_temp_dir),
    ):
        _require(
            not _is_within(evidence_path, repo_root),
            f"{label} must be outside the repository for production evidence: {evidence_path}",
        )

    git_state = git_probe(repo_root)
    observed_root = Path(str(git_state.get("repo_root") or "")).resolve()
    observed_head = str(git_state.get("head") or "").strip()
    observed_status = str(git_state.get("status") or "")
    _require(
        _same_path(observed_root, repo_root),
        f"Unexpected Git repository root: {observed_root}",
    )
    _require(
        observed_head.lower() == expected_commit.lower(),
        f"Runtime commit {observed_head!r} does not match approved commit {expected_commit!r}.",
    )
    _require(
        not observed_status.strip(),
        "Production preflight requires a clean, review-approved working tree.",
    )
    return {
        "status": "passed",
        "environment": "production",
        "governance_backend": "sql-authority",
        "source_preview_governance_backend": "sql-authority",
        "governance_sql_configured": True,
        "approved_commit": expected_commit.lower(),
        "observed_commit": observed_head.lower(),
        "working_tree_clean": True,
    }


def _archive_inventory(archive_root: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for path in sorted(
        (item for item in archive_root.rglob("*") if item.is_file()),
        key=lambda item: item.as_posix(),
    ):
        resolved = path.resolve()
        _require(
            _is_within(resolved, archive_root),
            f"Archive inventory path escaped approved root: {resolved}",
        )
        stat = resolved.stat()
        rows.append(
            {
                "relative_path": resolved.relative_to(archive_root).as_posix(),
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": _file_sha256(resolved),
            }
        )
    return {
        "file_count": len(rows),
        "total_bytes": sum(int(row["bytes"]) for row in rows),
        "inventory_sha256": _canonical_json_sha256(rows),
        "files": rows,
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
        _require(
            isinstance(payload, dict),
            f"JSONL row is not an object at {path}:{line_number}",
        )
        rows.append(payload)
    return rows


def _replay_locked_archives(
    selected: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    from backend.app.repositories.snapshot_repo import (
        merge_tyw_rows_by_grain,
        merge_zqtz_rows_by_grain,
    )
    from backend.app.repositories.snapshot_row_parse import (
        parse_tyw_snapshot_rows_from_bytes,
        parse_zqtz_snapshot_rows_from_bytes,
    )
    from backend.app.tasks.snapshot_materialize import SNAPSHOT_RULE_VERSION

    replay: dict[str, object] = {}
    for family in TARGET_SOURCE_FAMILIES:
        row = selected[family]
        path = Path(str(row["archived_path"]))
        common = {
            "file_bytes": path.read_bytes(),
            "ingest_batch_id": TARGET_INGEST_BATCH_ID,
            "source_version": str(row["source_version"]),
            "source_file": str(row.get("source_file") or path.name),
            "rule_version": SNAPSHOT_RULE_VERSION,
        }
        if family == "zqtz":
            raw_rows = parse_zqtz_snapshot_rows_from_bytes(**common)
            canonical_rows = merge_zqtz_rows_by_grain(raw_rows)
        else:
            raw_rows = parse_tyw_snapshot_rows_from_bytes(**common)
            canonical_rows = merge_tyw_rows_by_grain(raw_rows)
        contract = SOURCE_CONTRACTS[family]
        _require(
            len(raw_rows) == contract["raw_rows"],
            f"{family} parser row count mismatch: {len(raw_rows)}",
        )
        _require(
            len(canonical_rows) == contract["canonical_rows"],
            f"{family} canonical row count mismatch: {len(canonical_rows)}",
        )
        report_dates = sorted({str(item.get("report_date") or "") for item in raw_rows})
        _require(
            report_dates == [TARGET_REPORT_DATE],
            f"{family} archive contains unexpected report dates: {report_dates}",
        )
        replay[family] = {
            "raw_rows": len(raw_rows),
            "canonical_rows": len(canonical_rows),
            "merged_row_reduction": len(raw_rows) - len(canonical_rows),
            "report_dates": report_dates,
        }
    return replay


_SNAPSHOT_DECIMAL_FIELDS = {
    "zqtz": {
        "face_value_native",
        "market_value_native",
        "amortized_cost_native",
        "accrued_interest_native",
        "coupon_rate",
        "ytm_value",
    },
    "tyw": {"principal_native", "accrued_interest_native", "funding_cost_rate"},
}
SNAPSHOT_SOURCE_FIELDS = {
    "zqtz": (
        "report_date",
        "instrument_code",
        "instrument_name",
        "portfolio_name",
        "cost_center",
        "account_category",
        "asset_class",
        "bond_type",
        "business_type_primary",
        "sub_type",
        "issuer_name",
        "industry_name",
        "rating",
        "currency_code",
        "face_value_native",
        "market_value_native",
        "amortized_cost_native",
        "accrued_interest_native",
        "coupon_rate",
        "ytm_value",
        "maturity_date",
        "next_call_date",
        "overdue_days",
        "is_issuance_like",
        "interest_mode",
        "value_date",
        "customer_attribute",
        "source_version",
        "rule_version",
        "ingest_batch_id",
    ),
    "tyw": (
        "report_date",
        "position_id",
        "product_type",
        "position_side",
        "counterparty_name",
        "account_type",
        "special_account_type",
        "core_customer_type",
        "currency_code",
        "principal_native",
        "accrued_interest_native",
        "funding_cost_rate",
        "maturity_date",
        "pledged_bond_code",
        "source_version",
        "rule_version",
        "ingest_batch_id",
    ),
}
_DECIMAL_SCALE_8 = Decimal("0.00000001")


def _normalize_snapshot_value(family: str, field_name: str, value: object) -> object:
    if value is None:
        return None
    if field_name in _SNAPSHOT_DECIMAL_FIELDS[family]:
        return Decimal(str(value)).quantize(_DECIMAL_SCALE_8, rounding=ROUND_HALF_UP)
    if field_name in {"report_date", "maturity_date", "next_call_date", "value_date"}:
        return str(value) if str(value) else None
    return value


def _decimal_q8(value: object) -> Decimal:
    return Decimal(str(value)).quantize(_DECIMAL_SCALE_8, rounding=ROUND_HALF_UP)


def _compare_snapshot_rows(
    duckdb_path: Path,
    expected_by_family: Mapping[str, list[dict[str, object]]],
) -> dict[str, object]:
    from backend.app.repositories.snapshot_repo import tyw_grain_key, zqtz_grain_key

    receipt: dict[str, object] = {}
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        for family, table, grain_fn in (
            ("zqtz", "zqtz_bond_daily_snapshot", zqtz_grain_key),
            ("tyw", "tyw_interbank_daily_snapshot", tyw_grain_key),
        ):
            expected_rows = expected_by_family[family]
            _require(
                expected_rows, f"{family} archive replay unexpectedly produced no rows."
            )
            fields = list(SNAPSHOT_SOURCE_FIELDS[family])
            missing_expected_fields = sorted(
                field
                for field in fields
                if any(field not in row for row in expected_rows)
            )
            _require(
                not missing_expected_fields,
                f"{family} parser replay omitted explicit source fields: {missing_expected_fields}",
            )
            columns = ", ".join(f'"{field}"' for field in fields)
            raw_rows = conn.execute(
                f'select {columns} from "{table}" where cast(report_date as varchar) = ?',
                [TARGET_REPORT_DATE],
            ).fetchall()
            database_rows = [dict(zip(fields, row, strict=True)) for row in raw_rows]

            def normalized_row(row: Mapping[str, object]) -> dict[str, object]:
                return {
                    field: _normalize_snapshot_value(family, field, row.get(field))
                    for field in fields
                }

            normalized_expected = [normalized_row(row) for row in expected_rows]
            normalized_database = [normalized_row(row) for row in database_rows]
            expected_map = {grain_fn(row): row for row in normalized_expected}
            database_map = {grain_fn(row): row for row in normalized_database}
            expected_keys = set(expected_map)
            database_keys = set(database_map)
            missing_keys = expected_keys - database_keys
            extra_keys = database_keys - expected_keys
            mismatches: list[dict[str, object]] = []
            null_mismatch_rows = 0
            value_mismatch_rows = 0
            for key in sorted(expected_keys & database_keys, key=repr):
                left = expected_map[key]
                right = database_map[key]
                differing_fields = [
                    field for field in fields if left.get(field) != right.get(field)
                ]
                if differing_fields:
                    if any(
                        (left.get(field) is None) != (right.get(field) is None)
                        for field in differing_fields
                    ):
                        null_mismatch_rows += 1
                    if any(
                        left.get(field) is not None
                        and right.get(field) is not None
                        and left.get(field) != right.get(field)
                        for field in differing_fields
                    ):
                        value_mismatch_rows += 1
                    mismatches.append(
                        {
                            "grain": repr(key),
                            "fields": differing_fields,
                            "expected": {
                                field: left.get(field) for field in differing_fields
                            },
                            "database": {
                                field: right.get(field) for field in differing_fields
                            },
                        }
                    )
            duplicate_expected = len(normalized_expected) - len(expected_map)
            duplicate_database = len(normalized_database) - len(database_map)
            family_passed = not (
                missing_keys
                or extra_keys
                or mismatches
                or duplicate_expected
                or duplicate_database
            )
            receipt[family] = {
                "status": "passed" if family_passed else "failed",
                "expected_row_count": len(normalized_expected),
                "database_row_count": len(normalized_database),
                "missing_key_count": len(missing_keys),
                "extra_key_count": len(extra_keys),
                "mismatched_row_count": len(mismatches),
                "null_mismatch_row_count": null_mismatch_rows,
                "value_mismatch_row_count": value_mismatch_rows,
                "duplicate_expected_grain_count": duplicate_expected,
                "duplicate_database_grain_count": duplicate_database,
                "mismatch_examples": mismatches[:5],
                "missing_key_examples": [
                    repr(key) for key in sorted(missing_keys, key=repr)[:5]
                ],
                "extra_key_examples": [
                    repr(key) for key in sorted(extra_keys, key=repr)[:5]
                ],
            }
    finally:
        conn.close()
    receipt["status"] = (
        "passed"
        if all(
            isinstance(receipt.get(family), dict)
            and receipt[family].get("status") == "passed"
            for family in TARGET_SOURCE_FAMILIES
        )
        else "failed"
    )
    return receipt


def _snapshot_archive_tieout(
    paths: BackfillPaths,
    selected: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    from backend.app.repositories.snapshot_repo import (
        merge_tyw_rows_by_grain,
        merge_zqtz_rows_by_grain,
    )
    from backend.app.repositories.snapshot_row_parse import (
        parse_tyw_snapshot_rows_from_bytes,
        parse_zqtz_snapshot_rows_from_bytes,
    )
    from backend.app.tasks.snapshot_materialize import SNAPSHOT_RULE_VERSION

    expected_by_family: dict[str, list[dict[str, object]]] = {}
    for family in TARGET_SOURCE_FAMILIES:
        row = selected[family]
        archive_path = Path(str(row["archived_path"]))
        common = {
            "file_bytes": archive_path.read_bytes(),
            "ingest_batch_id": TARGET_INGEST_BATCH_ID,
            "source_version": str(row["source_version"]),
            "source_file": str(row.get("source_file") or archive_path.name),
            "rule_version": SNAPSHOT_RULE_VERSION,
        }
        if family == "zqtz":
            expected_by_family[family] = merge_zqtz_rows_by_grain(
                parse_zqtz_snapshot_rows_from_bytes(**common)
            )
        else:
            expected_by_family[family] = merge_tyw_rows_by_grain(
                parse_tyw_snapshot_rows_from_bytes(**common)
            )
    return _compare_snapshot_rows(paths.duckdb_path, expected_by_family)


def _require_snapshot_archive_tieout(evidence: Mapping[str, object]) -> None:
    tie_out = evidence.get("source_to_snapshot_tie_out")
    _require(
        isinstance(tie_out, dict) and tie_out.get("status") == "passed",
        f"Current target-date snapshot does not exactly match locked archive source fields: {tie_out}",
    )


def _immutable_source_evidence(evidence: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in evidence.items()
        if key != "source_to_snapshot_tie_out"
    }


def _validate_source_inputs(paths: BackfillPaths) -> dict[str, object]:
    manifest_path = paths.governance_dir / "source_manifest.jsonl"
    _require(manifest_path.is_file(), f"Source manifest is missing: {manifest_path}")
    manifest_rows = _read_jsonl(manifest_path)
    scoped = [
        row
        for row in manifest_rows
        if str(row.get("report_date") or "") == TARGET_REPORT_DATE
        and str(row.get("ingest_batch_id") or "") == TARGET_INGEST_BATCH_ID
        and str(row.get("source_family") or "") in SOURCE_CONTRACTS
    ]
    _require(
        len(scoped) == 2,
        f"Expected exactly two pinned source_manifest rows, got {len(scoped)}.",
    )
    _require(
        {str(row.get("source_family")) for row in scoped}
        == set(TARGET_SOURCE_FAMILIES),
        "Pinned source manifests must contain exactly zqtz and tyw.",
    )

    selected: dict[str, dict[str, object]] = {}
    locked_receipt: list[dict[str, object]] = []
    for row in scoped:
        family = str(row["source_family"])
        contract = SOURCE_CONTRACTS[family]
        _require(
            str(row.get("status") or "") in {"completed", "rerun"},
            f"Ineligible {family} source manifest status: {row.get('status')!r}",
        )
        _require(
            str(row.get("source_version") or "") == contract["source_version"],
            f"{family} source_version does not match the pinned contract.",
        )
        raw_archive_path = Path(str(row.get("archived_path") or ""))
        _require(
            raw_archive_path.is_absolute(),
            f"{family} archived_path must be absolute: {raw_archive_path}",
        )
        archive_path = raw_archive_path.resolve()
        _require(
            archive_path.is_file(),
            f"Pinned {family} archive is missing: {archive_path}",
        )
        _require(
            _is_within(archive_path, paths.archive_root),
            f"Pinned {family} archive escaped approved root: {archive_path}",
        )
        _require(
            archive_path.name == contract["file_name"],
            f"Pinned {family} archive filename mismatch: {archive_path.name}",
        )
        fingerprint = _file_fingerprint(archive_path)
        _require(
            fingerprint["bytes"] == contract["bytes"],
            f"Pinned {family} archive byte length mismatch.",
        )
        _require(
            fingerprint["sha256"] == contract["sha256"],
            f"Pinned {family} archive SHA256 mismatch.",
        )
        normalized = dict(row)
        normalized["archived_path"] = str(archive_path)
        selected[family] = normalized
        locked_receipt.append(
            {
                "family": family,
                "source_version": row["source_version"],
                "status": row["status"],
                **fingerprint,
            }
        )

    return {
        "source_manifest": _file_fingerprint(manifest_path),
        "locked_archives": sorted(locked_receipt, key=lambda item: str(item["family"])),
        "archive_inventory": _archive_inventory(paths.archive_root),
        "parser_replay": _replay_locked_archives(selected),
        "source_to_snapshot_tie_out": _snapshot_archive_tieout(paths, selected),
    }


def _validate_database_contract(duckdb_path: Path) -> dict[str, object]:
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        table_names = {
            str(row[0])
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        _require(
            "_schema_migrations" in table_names,
            "DuckDB is missing _schema_migrations; refusing task-side DDL.",
        )
        applied_versions = {
            int(row[0])
            for row in conn.execute("select version from _schema_migrations").fetchall()
        }
        missing_versions = sorted(set(REQUIRED_SCHEMA_MIGRATIONS) - applied_versions)
        _require(
            not missing_versions,
            f"DuckDB is missing required schema migrations: {missing_versions}",
        )

        counts = {
            table: int(
                conn.execute(
                    f'select count(*) from "{table}" where cast(report_date as varchar) = ?',
                    [TARGET_REPORT_DATE],
                ).fetchone()[0]
            )
            for table in EXPECTED_TARGET_COUNTS
        }
        _require(
            counts == EXPECTED_TARGET_COUNTS,
            f"Target-date table counts do not match the pinned contract: {counts}",
        )

        lineage_checks: dict[str, dict[str, int]] = {}
        for table, field_names in REQUIRED_LINEAGE_FIELDS.items():
            field_checks: dict[str, int] = {}
            for field_name in field_names:
                missing_count = int(
                    conn.execute(
                        f"""
                        select count(*)
                        from "{table}"
                        where cast(report_date as varchar) = ?
                          and coalesce(trim(cast("{field_name}" as varchar)), '') = ''
                        """,
                        [TARGET_REPORT_DATE],
                    ).fetchone()[0]
                )
                _require(
                    missing_count == 0,
                    f"{table}.{field_name} has {missing_count} blank target-date values.",
                )
                field_checks[field_name] = missing_count
            lineage_checks[table] = field_checks

        balance_trace_checks: dict[str, dict[str, int]] = {}
        for family, snapshot_table, balance_table in (
            ("zqtz", "zqtz_bond_daily_snapshot", "fact_formal_zqtz_balance_daily"),
            ("tyw", "tyw_interbank_daily_snapshot", "fact_formal_tyw_balance_daily"),
        ):
            snapshot_duplicate_count = int(
                conn.execute(
                    f"""
                    select count(*) from (
                      select trace_id from "{snapshot_table}"
                      where cast(report_date as varchar) = ?
                      group by trace_id having count(*) <> 1
                    )
                    """,
                    [TARGET_REPORT_DATE],
                ).fetchone()[0]
            )
            invalid_formal_pair_count = int(
                conn.execute(
                    f"""
                    select count(*) from (
                      select trace_id
                      from "{balance_table}"
                      where cast(report_date as varchar) = ?
                      group by trace_id
                      having count(*) <> 2
                         or sum(case when currency_basis = 'native' then 1 else 0 end) <> 1
                         or sum(case when currency_basis = 'CNY' then 1 else 0 end) <> 1
                    )
                    """,
                    [TARGET_REPORT_DATE],
                ).fetchone()[0]
            )
            missing_formal_trace_count = int(
                conn.execute(
                    f"""
                    select count(*)
                    from (select distinct trace_id from "{snapshot_table}" where cast(report_date as varchar) = ?) s
                    left join (select distinct trace_id from "{balance_table}" where cast(report_date as varchar) = ?) f
                      on f.trace_id = s.trace_id
                    where f.trace_id is null
                    """,
                    [TARGET_REPORT_DATE, TARGET_REPORT_DATE],
                ).fetchone()[0]
            )
            extra_formal_trace_count = int(
                conn.execute(
                    f"""
                    select count(*)
                    from (select distinct trace_id from "{balance_table}" where cast(report_date as varchar) = ?) f
                    left join (select distinct trace_id from "{snapshot_table}" where cast(report_date as varchar) = ?) s
                      on s.trace_id = f.trace_id
                    where s.trace_id is null
                    """,
                    [TARGET_REPORT_DATE, TARGET_REPORT_DATE],
                ).fetchone()[0]
            )
            _require(
                (
                    snapshot_duplicate_count,
                    invalid_formal_pair_count,
                    missing_formal_trace_count,
                    extra_formal_trace_count,
                )
                == (0, 0, 0, 0),
                f"{family} snapshot/formal balance trace tie-out failed: "
                f"snapshot_duplicates={snapshot_duplicate_count}, invalid_pairs={invalid_formal_pair_count}, "
                f"missing={missing_formal_trace_count}, extra={extra_formal_trace_count}",
            )
            balance_trace_checks[family] = {
                "snapshot_duplicate_trace_count": snapshot_duplicate_count,
                "invalid_native_cny_pair_count": invalid_formal_pair_count,
                "missing_formal_trace_count": missing_formal_trace_count,
                "extra_formal_trace_count": extra_formal_trace_count,
            }

        non_issuance_count = int(
            conn.execute(
                """
                select count(*) from zqtz_bond_daily_snapshot
                where cast(report_date as varchar) = ?
                  and not coalesce(is_issuance_like, false)
                """,
                [TARGET_REPORT_DATE],
            ).fetchone()[0]
        )
        snapshot_duplicate_traces = int(
            conn.execute(
                """
                select count(*) from (
                  select trace_id
                  from zqtz_bond_daily_snapshot
                  where cast(report_date as varchar) = ?
                    and not coalesce(is_issuance_like, false)
                  group by trace_id having count(*) <> 1
                )
                """,
                [TARGET_REPORT_DATE],
            ).fetchone()[0]
        )
        bond_duplicate_traces = int(
            conn.execute(
                """
                select count(*) from (
                  select trace_id
                  from fact_formal_bond_analytics_daily
                  where cast(report_date as varchar) = ?
                  group by trace_id having count(*) <> 1
                )
                """,
                [TARGET_REPORT_DATE],
            ).fetchone()[0]
        )
        missing_bond_traces = int(
            conn.execute(
                """
                select count(*)
                from zqtz_bond_daily_snapshot s
                left join fact_formal_bond_analytics_daily b
                  on cast(b.report_date as varchar) = ? and b.trace_id = s.trace_id
                where cast(s.report_date as varchar) = ?
                  and not coalesce(s.is_issuance_like, false)
                  and b.trace_id is null
                """,
                [TARGET_REPORT_DATE, TARGET_REPORT_DATE],
            ).fetchone()[0]
        )
        extra_bond_traces = int(
            conn.execute(
                """
                select count(*)
                from fact_formal_bond_analytics_daily b
                left join zqtz_bond_daily_snapshot s
                  on cast(s.report_date as varchar) = ?
                 and not coalesce(s.is_issuance_like, false)
                 and s.trace_id = b.trace_id
                where cast(b.report_date as varchar) = ? and s.trace_id is null
                """,
                [TARGET_REPORT_DATE, TARGET_REPORT_DATE],
            ).fetchone()[0]
        )
        _require(
            non_issuance_count
            == EXPECTED_TARGET_COUNTS["fact_formal_bond_analytics_daily"],
            f"Non-issuance snapshot count does not match expected bond population: {non_issuance_count}",
        )
        _require(
            (
                snapshot_duplicate_traces,
                bond_duplicate_traces,
                missing_bond_traces,
                extra_bond_traces,
            )
            == (0, 0, 0, 0),
            "Bond/non-issuance snapshot trace tie-out failed: "
            f"snapshot_duplicates={snapshot_duplicate_traces}, bond_duplicates={bond_duplicate_traces}, "
            f"missing={missing_bond_traces}, extra={extra_bond_traces}",
        )

        bond_aggregate = conn.execute(
            """
            select count(*), sum(market_value), sum(dv01), sum(spread_dv01)
            from fact_formal_bond_analytics_daily
            where cast(report_date as varchar) = ?
            """,
            [TARGET_REPORT_DATE],
        ).fetchone()
        risk_row = conn.execute(
            """
            select bond_count, total_market_value, portfolio_dv01, cs01
            from fact_formal_risk_tensor_daily
            where cast(report_date as varchar) = ?
            """,
            [TARGET_REPORT_DATE],
        ).fetchone()
        _require(risk_row is not None, "Risk tensor target-date row is missing.")
        risk_pairs = {
            "bond_count": (int(risk_row[0]), int(bond_aggregate[0])),
            "total_market_value": (
                Decimal(str(risk_row[1])),
                Decimal(str(bond_aggregate[1])),
            ),
            "portfolio_dv01": (
                Decimal(str(risk_row[2])),
                Decimal(str(bond_aggregate[2])),
            ),
            "cs01": (Decimal(str(risk_row[3])), Decimal(str(bond_aggregate[3]))),
        }
        _require(
            risk_pairs["bond_count"]
            == (
                EXPECTED_TARGET_COUNTS["fact_formal_bond_analytics_daily"],
                EXPECTED_TARGET_COUNTS["fact_formal_bond_analytics_daily"],
            ),
            f"Risk bond_count mismatch: {risk_pairs['bond_count']}",
        )
        for metric_name in ("total_market_value", "portfolio_dv01", "cs01"):
            _require(
                risk_pairs[metric_name][0] == risk_pairs[metric_name][1],
                f"Risk {metric_name} does not tie exactly to bond facts: {risk_pairs[metric_name]}",
            )

        fx_rows = conn.execute(
            """
            select upper(base_currency), upper(quote_currency), mid_rate,
                   source_name, source_version, vendor_name, vendor_version,
                   vendor_series_code, cast(observed_trade_date as varchar),
                   is_business_day, is_carry_forward
            from fx_daily_mid
            where cast(trade_date as varchar) = ?
            order by 1, 2
            """,
            [TARGET_REPORT_DATE],
        ).fetchall()
        _require(
            len(fx_rows) == 5,
            f"Expected exactly five frozen FX rows, got {len(fx_rows)}.",
        )
        observed_pairs = {(str(row[0]), str(row[1])) for row in fx_rows}
        _require(
            observed_pairs == {(currency, "CNY") for currency in EXPECTED_FX},
            f"Frozen FX grain mismatch: {sorted(observed_pairs)}",
        )
        fx_receipt: list[dict[str, object]] = []
        for row in fx_rows:
            currency = str(row[0])
            rate = Decimal(str(row[2]))
            contract = EXPECTED_FX[currency]
            _require(
                rate.is_finite() and rate > 0,
                f"Frozen {currency}/CNY FX rate must be positive and finite.",
            )
            _require(
                rate == contract["rate"], f"Frozen {currency}/CNY rate mismatch: {rate}"
            )
            _require(
                tuple(str(value or "") for value in row[3:8]) == contract["lineage"],
                f"Frozen {currency}/CNY lineage mismatch.",
            )
            _require(
                str(row[8]) == TARGET_REPORT_DATE
                and bool(row[9])
                and not bool(row[10]),
                f"Frozen {currency}/CNY observed-date/business-day flags mismatch.",
            )
            fx_receipt.append(
                {
                    "base_currency": currency,
                    "quote_currency": "CNY",
                    "mid_rate": str(rate),
                    "source_name": row[3],
                    "source_version": row[4],
                    "vendor_name": row[5],
                    "vendor_version": row[6],
                    "vendor_series_code": row[7],
                    "observed_trade_date": str(row[8]),
                    "is_business_day": bool(row[9]),
                    "is_carry_forward": bool(row[10]),
                }
            )

        fx_rates = {str(row[0]): _decimal_q8(row[2]) for row in fx_rows}
        fx_rates["CNY"] = Decimal("1.00000000")
        balance_amount_checks: dict[str, dict[str, object]] = {}
        for family, snapshot_table, balance_table, source_fields, formal_fields in (
            (
                "zqtz",
                "zqtz_bond_daily_snapshot",
                "fact_formal_zqtz_balance_daily",
                (
                    "face_value_native",
                    "market_value_native",
                    "amortized_cost_native",
                    "accrued_interest_native",
                ),
                (
                    "face_value_amount",
                    "market_value_amount",
                    "amortized_cost_amount",
                    "accrued_interest_amount",
                ),
            ),
            (
                "tyw",
                "tyw_interbank_daily_snapshot",
                "fact_formal_tyw_balance_daily",
                ("principal_native", "accrued_interest_native"),
                ("principal_amount", "accrued_interest_amount"),
            ),
        ):
            snapshot_rows = conn.execute(
                f"""
                select trace_id, upper(currency_code), {", ".join(source_fields)}
                from "{snapshot_table}"
                where cast(report_date as varchar) = ?
                """,
                [TARGET_REPORT_DATE],
            ).fetchall()
            formal_rows = conn.execute(
                f"""
                select trace_id, currency_basis, {", ".join(formal_fields)}
                from "{balance_table}"
                where cast(report_date as varchar) = ?
                """,
                [TARGET_REPORT_DATE],
            ).fetchall()
            formal_by_trace_basis = {
                (str(row[0]), str(row[1])): row[2:] for row in formal_rows
            }
            mismatch_examples: list[dict[str, object]] = []
            comparison_count = 0
            for snapshot_row in snapshot_rows:
                trace_id = str(snapshot_row[0])
                currency = str(snapshot_row[1])
                _require(
                    currency in fx_rates,
                    f"{family} trace {trace_id} has no frozen FX rate for {currency}.",
                )
                source_values = snapshot_row[2:]
                for basis in ("native", "CNY"):
                    formal_values = formal_by_trace_basis[(trace_id, basis)]
                    multiplier = (
                        Decimal("1") if basis == "native" else fx_rates[currency]
                    )
                    for source_field, formal_field, source_value, formal_value in zip(
                        source_fields,
                        formal_fields,
                        source_values,
                        formal_values,
                        strict=True,
                    ):
                        expected_value = _decimal_q8(
                            _decimal_q8(source_value) * multiplier
                        )
                        observed_value = _decimal_q8(formal_value)
                        comparison_count += 1
                        if observed_value != expected_value:
                            mismatch_examples.append(
                                {
                                    "trace_id": trace_id,
                                    "currency_basis": basis,
                                    "source_field": source_field,
                                    "formal_field": formal_field,
                                    "expected": str(expected_value),
                                    "observed": str(observed_value),
                                    "residual": str(observed_value - expected_value),
                                }
                            )
            _require(
                not mismatch_examples,
                f"{family} snapshot/formal balance Decimal amount tie-out failed: {mismatch_examples[:3]}",
            )
            balance_amount_checks[family] = {
                "comparison_count": comparison_count,
                "mismatch_count": 0,
                "max_absolute_residual": "0.00000000",
                "mismatch_examples": [],
            }

        zqtz_snapshot_amounts = {
            str(row[0]): row[1]
            for row in conn.execute(
                """
                select trace_id, market_value_native
                from zqtz_bond_daily_snapshot
                where cast(report_date as varchar) = ?
                  and not coalesce(is_issuance_like, false)
                """,
                [TARGET_REPORT_DATE],
            ).fetchall()
        }
        zqtz_cny_balances = {
            str(row[0]): row[1:]
            for row in conn.execute(
                """
                select trace_id, face_value_amount, market_value_amount,
                       amortized_cost_amount, accrued_interest_amount
                from fact_formal_zqtz_balance_daily
                where cast(report_date as varchar) = ? and currency_basis = 'CNY'
                """,
                [TARGET_REPORT_DATE],
            ).fetchall()
        }
        bond_rows = conn.execute(
            """
            select trace_id, face_value, market_value, amortized_cost,
                   accrued_interest, market_value_native
            from fact_formal_bond_analytics_daily
            where cast(report_date as varchar) = ?
            """,
            [TARGET_REPORT_DATE],
        ).fetchall()
        bond_mismatches: list[dict[str, object]] = []
        bond_comparison_count = 0
        bond_fields = (
            "face_value",
            "market_value",
            "amortized_cost",
            "accrued_interest",
        )
        for bond_row in bond_rows:
            trace_id = str(bond_row[0])
            expected_cny = zqtz_cny_balances[trace_id]
            for field_name, observed, expected in zip(
                bond_fields,
                bond_row[1:5],
                expected_cny,
                strict=True,
            ):
                observed_value = _decimal_q8(observed)
                expected_value = _decimal_q8(expected)
                bond_comparison_count += 1
                if observed_value != expected_value:
                    bond_mismatches.append(
                        {
                            "trace_id": trace_id,
                            "field": field_name,
                            "expected": str(expected_value),
                            "observed": str(observed_value),
                            "residual": str(observed_value - expected_value),
                        }
                    )
            observed_native = _decimal_q8(bond_row[5])
            expected_native = _decimal_q8(zqtz_snapshot_amounts[trace_id])
            bond_comparison_count += 1
            if observed_native != expected_native:
                bond_mismatches.append(
                    {
                        "trace_id": trace_id,
                        "field": "market_value_native",
                        "expected": str(expected_native),
                        "observed": str(observed_native),
                        "residual": str(observed_native - expected_native),
                    }
                )
        _require(
            not bond_mismatches,
            f"Bond/formal-balance/snapshot Decimal amount tie-out failed: {bond_mismatches[:3]}",
        )
        bond_amount_check = {
            "comparison_count": bond_comparison_count,
            "mismatch_count": 0,
            "max_absolute_residual": "0.00000000",
            "mismatch_examples": [],
        }

        anchor_rows = conn.execute(
            """
            with anchors(anchor_date) as (
              values (date '2026-06-30'), (date '2026-07-01'), (date '2026-07-31')
            ), curve_types(curve_type) as (
              values ('treasury'), ('cdb'), ('aaa_credit')
            )
            select a.anchor_date, c.curve_type,
                   max(cast(y.trade_date as date)) filter (
                     where cast(y.trade_date as date) <= a.anchor_date
                       and cast(y.trade_date as date) >= a.anchor_date - interval 40 day
                   ) as resolved_trade_date
            from anchors a
            cross join curve_types c
            left join fact_formal_yield_curve_daily y on y.curve_type = c.curve_type
            group by a.anchor_date, c.curve_type
            order by a.anchor_date, c.curve_type
            """
        ).fetchall()
        _require(
            len(anchor_rows) == 9
            and {str(row[2]) for row in anchor_rows} == {"2026-06-30"},
            f"Curve anchors do not resolve exactly to 2026-06-30: {anchor_rows}",
        )

        curve_receipt: list[dict[str, object]] = []
        for curve_type, contract in CURVE_CONTRACTS.items():
            rows = conn.execute(
                """
                select tenor, cast(rate_pct as varchar), vendor_name, vendor_version,
                       source_version, rule_version
                from fact_formal_yield_curve_daily
                where cast(trade_date as varchar) = '2026-06-30' and curve_type = ?
                order by tenor
                """,
                [curve_type],
            ).fetchall()
            _require(
                len(rows) == contract["points"],
                f"Frozen {curve_type} curve point count mismatch: {len(rows)}",
            )
            lineage = {
                (str(row[2]), str(row[3]), str(row[4]), str(row[5])) for row in rows
            }
            expected_lineage = {
                (
                    str(contract["vendor_name"]),
                    str(contract["vendor_version"]),
                    str(contract["source_version"]),
                    "rv_yield_curve_formal_materialize_v1",
                )
            }
            _require(
                lineage == expected_lineage,
                f"Frozen {curve_type} curve lineage mismatch: {lineage}",
            )
            _require(
                all(row[1] not in {None, ""} for row in rows),
                f"Frozen {curve_type} curve contains null rates.",
            )
            digest = (
                hashlib.sha256(
                    json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode(
                        "utf-8"
                    )
                )
                .hexdigest()
                .upper()
            )
            _require(
                digest == contract["sha256"],
                f"Frozen {curve_type} curve SHA256 mismatch: {digest}",
            )
            curve_receipt.append(
                {
                    "curve_type": curve_type,
                    "trade_date": "2026-06-30",
                    "point_count": len(rows),
                    "vendor_name": contract["vendor_name"],
                    "vendor_version": contract["vendor_version"],
                    "source_version": contract["source_version"],
                    "rule_version": "rv_yield_curve_formal_materialize_v1",
                    "canonical_row_sha256": digest,
                }
            )
    finally:
        conn.close()

    return {
        "schema_migrations": {
            "required": list(REQUIRED_SCHEMA_MIGRATIONS),
            "applied": sorted(applied_versions),
            "missing": [],
        },
        "target_counts": counts,
        "business_tie_outs": {
            "required_lineage_blank_counts": lineage_checks,
            "snapshot_to_formal_balance_trace": balance_trace_checks,
            "snapshot_to_formal_balance_amounts": balance_amount_checks,
            "bond_snapshot_trace": {
                "non_issuance_snapshot_count": non_issuance_count,
                "snapshot_duplicate_trace_count": snapshot_duplicate_traces,
                "bond_duplicate_trace_count": bond_duplicate_traces,
                "missing_bond_trace_count": missing_bond_traces,
                "extra_bond_trace_count": extra_bond_traces,
            },
            "bond_to_balance_and_snapshot_amounts": bond_amount_check,
            "risk_to_bond": {
                metric_name: {
                    "risk": str(pair[0]),
                    "bond": str(pair[1]),
                    "residual": "0",
                }
                for metric_name, pair in risk_pairs.items()
            },
        },
        "fx": fx_receipt,
        "curve_anchors": [
            {
                "anchor_date": str(row[0]),
                "curve_type": str(row[1]),
                "resolved_trade_date": str(row[2]),
            }
            for row in anchor_rows
        ],
        "curves": sorted(curve_receipt, key=lambda item: str(item["curve_type"])),
    }


def _validate_database_stage_contract(
    duckdb_path: Path,
    *,
    through_stage: str,
) -> dict[str, object]:
    """Validate only the materialized stage prefix; risk remains the full contract."""

    _require(
        through_stage in STAGE_TABLES,
        f"Unknown database validation stage: {through_stage!r}",
    )
    if through_stage == "risk":
        return {
            "validation_scope": "full_chain",
            "validated_through_stage": "risk",
            **_validate_database_contract(duckdb_path),
        }

    stage_names = tuple(STAGE_TABLES)
    stage_index = stage_names.index(through_stage)
    included_tables = tuple(
        table
        for stage_name in stage_names[: stage_index + 1]
        for table in STAGE_TABLES[stage_name]
    )
    expected_counts = {
        table: EXPECTED_TARGET_COUNTS[table] for table in included_tables
    }

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        table_names = {
            str(row[0])
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        _require(
            "_schema_migrations" in table_names,
            "DuckDB is missing _schema_migrations; refusing task-side DDL.",
        )
        applied_versions = {
            int(row[0])
            for row in conn.execute("select version from _schema_migrations").fetchall()
        }
        missing_versions = sorted(set(REQUIRED_SCHEMA_MIGRATIONS) - applied_versions)
        _require(
            not missing_versions,
            f"DuckDB is missing required schema migrations: {missing_versions}",
        )

        counts = {
            table: int(
                conn.execute(
                    f'select count(*) from "{table}" where cast(report_date as varchar) = ?',
                    [TARGET_REPORT_DATE],
                ).fetchone()[0]
            )
            for table in included_tables
        }
        _require(
            counts == expected_counts,
            f"{through_stage} stage-prefix target counts mismatch: {counts}",
        )

        lineage_checks: dict[str, dict[str, int]] = {}
        for table in included_tables:
            field_checks: dict[str, int] = {}
            for field_name in REQUIRED_LINEAGE_FIELDS[table]:
                missing_count = int(
                    conn.execute(
                        f"""
                        select count(*) from "{table}"
                        where cast(report_date as varchar) = ?
                          and coalesce(trim(cast("{field_name}" as varchar)), '') = ''
                        """,
                        [TARGET_REPORT_DATE],
                    ).fetchone()[0]
                )
                _require(
                    missing_count == 0,
                    f"{table}.{field_name} has {missing_count} blank target-date values.",
                )
                field_checks[field_name] = missing_count
            lineage_checks[table] = field_checks

        snapshot_trace_checks: dict[str, dict[str, int]] = {}
        for family, table in (
            ("zqtz", "zqtz_bond_daily_snapshot"),
            ("tyw", "tyw_interbank_daily_snapshot"),
        ):
            trace_ids = [
                str(row[0])
                for row in conn.execute(
                    f"""
                    select trace_id from "{table}"
                    where cast(report_date as varchar) = ?
                    """,
                    [TARGET_REPORT_DATE],
                ).fetchall()
            ]
            duplicate_trace_count = sum(
                count != 1 for count in Counter(trace_ids).values()
            )
            _require(
                duplicate_trace_count == 0,
                f"{family} snapshot contains {duplicate_trace_count} duplicate trace grains.",
            )
            snapshot_trace_checks[family] = {
                "duplicate_trace_count": duplicate_trace_count
            }

        business_tie_outs: dict[str, object] = {
            "required_lineage_blank_counts": lineage_checks,
            "snapshot_trace_uniqueness": snapshot_trace_checks,
        }
        fx_receipt: list[dict[str, object]] = []
        if through_stage == "snapshot":
            return {
                "validation_scope": "stage_prefix",
                "validated_through_stage": through_stage,
                "schema_migrations": {
                    "required": list(REQUIRED_SCHEMA_MIGRATIONS),
                    "applied": sorted(applied_versions),
                    "missing": [],
                },
                "target_counts": counts,
                "business_tie_outs": business_tie_outs,
                "fx": fx_receipt,
                "curve_anchors": [],
                "curves": [],
            }

        fx_rows = conn.execute(
            """
            select upper(base_currency), upper(quote_currency), mid_rate,
                   source_name, source_version, vendor_name, vendor_version,
                   vendor_series_code, cast(observed_trade_date as varchar),
                   is_business_day, is_carry_forward
            from fx_daily_mid
            where cast(trade_date as varchar) = ?
            order by 1, 2
            """,
            [TARGET_REPORT_DATE],
        ).fetchall()
        _require(
            len(fx_rows) == 5,
            f"Expected exactly five frozen FX rows, got {len(fx_rows)}.",
        )
        _require(
            {(str(row[0]), str(row[1])) for row in fx_rows}
            == {(currency, "CNY") for currency in EXPECTED_FX},
            "Frozen FX grain mismatch during balance stage validation.",
        )
        fx_rates = {"CNY": Decimal("1.00000000")}
        for row in fx_rows:
            currency = str(row[0])
            rate = _decimal_q8(row[2])
            contract = EXPECTED_FX[currency]
            _require(
                rate.is_finite() and rate > 0 and rate == contract["rate"],
                f"Frozen {currency}/CNY rate mismatch: {rate}",
            )
            _require(
                tuple(str(value or "") for value in row[3:8]) == contract["lineage"],
                f"Frozen {currency}/CNY lineage mismatch.",
            )
            _require(
                str(row[8]) == TARGET_REPORT_DATE
                and bool(row[9])
                and not bool(row[10]),
                f"Frozen {currency}/CNY observed-date/business-day flags mismatch.",
            )
            fx_rates[currency] = rate
            fx_receipt.append(
                {
                    "base_currency": currency,
                    "quote_currency": "CNY",
                    "mid_rate": str(rate),
                    "source_name": row[3],
                    "source_version": row[4],
                    "vendor_name": row[5],
                    "vendor_version": row[6],
                    "vendor_series_code": row[7],
                    "observed_trade_date": str(row[8]),
                    "is_business_day": bool(row[9]),
                    "is_carry_forward": bool(row[10]),
                }
            )

        balance_trace_checks: dict[str, dict[str, int]] = {}
        balance_amount_checks: dict[str, dict[str, object]] = {}
        for family, snapshot_table, balance_table, source_fields, formal_fields in (
            (
                "zqtz",
                "zqtz_bond_daily_snapshot",
                "fact_formal_zqtz_balance_daily",
                (
                    "face_value_native",
                    "market_value_native",
                    "amortized_cost_native",
                    "accrued_interest_native",
                ),
                (
                    "face_value_amount",
                    "market_value_amount",
                    "amortized_cost_amount",
                    "accrued_interest_amount",
                ),
            ),
            (
                "tyw",
                "tyw_interbank_daily_snapshot",
                "fact_formal_tyw_balance_daily",
                ("principal_native", "accrued_interest_native"),
                ("principal_amount", "accrued_interest_amount"),
            ),
        ):
            snapshot_rows = conn.execute(
                f"""
                select trace_id, upper(currency_code), {", ".join(source_fields)}
                from "{snapshot_table}"
                where cast(report_date as varchar) = ?
                """,
                [TARGET_REPORT_DATE],
            ).fetchall()
            formal_rows = conn.execute(
                f"""
                select trace_id, currency_basis, {", ".join(formal_fields)}
                from "{balance_table}"
                where cast(report_date as varchar) = ?
                """,
                [TARGET_REPORT_DATE],
            ).fetchall()
            snapshot_trace_counts = Counter(str(row[0]) for row in snapshot_rows)
            basis_by_trace: dict[str, list[str]] = {}
            for row in formal_rows:
                basis_by_trace.setdefault(str(row[0]), []).append(str(row[1]))
            snapshot_duplicates = sum(
                count != 1 for count in snapshot_trace_counts.values()
            )
            invalid_pairs = sum(
                sorted(bases) != ["CNY", "native"] for bases in basis_by_trace.values()
            )
            snapshot_traces = set(snapshot_trace_counts)
            formal_traces = set(basis_by_trace)
            missing_traces = snapshot_traces - formal_traces
            extra_traces = formal_traces - snapshot_traces
            _require(
                not snapshot_duplicates
                and not invalid_pairs
                and not missing_traces
                and not extra_traces,
                f"{family} snapshot/formal balance trace tie-out failed: "
                f"snapshot_duplicates={snapshot_duplicates}, invalid_pairs={invalid_pairs}, "
                f"missing={len(missing_traces)}, extra={len(extra_traces)}",
            )
            formal_by_trace_basis = {
                (str(row[0]), str(row[1])): row[2:] for row in formal_rows
            }
            mismatch_examples: list[dict[str, object]] = []
            comparison_count = 0
            for snapshot_row in snapshot_rows:
                trace_id = str(snapshot_row[0])
                currency = str(snapshot_row[1])
                _require(
                    currency in fx_rates,
                    f"{family} trace {trace_id} has no frozen FX rate for {currency}.",
                )
                for basis in ("native", "CNY"):
                    multiplier = (
                        Decimal("1") if basis == "native" else fx_rates[currency]
                    )
                    formal_values = formal_by_trace_basis[(trace_id, basis)]
                    for source_field, formal_field, source_value, formal_value in zip(
                        source_fields,
                        formal_fields,
                        snapshot_row[2:],
                        formal_values,
                        strict=True,
                    ):
                        expected_value = _decimal_q8(
                            _decimal_q8(source_value) * multiplier
                        )
                        observed_value = _decimal_q8(formal_value)
                        comparison_count += 1
                        if observed_value != expected_value:
                            mismatch_examples.append(
                                {
                                    "trace_id": trace_id,
                                    "currency_basis": basis,
                                    "source_field": source_field,
                                    "formal_field": formal_field,
                                    "expected": str(expected_value),
                                    "observed": str(observed_value),
                                    "residual": str(observed_value - expected_value),
                                }
                            )
            _require(
                not mismatch_examples,
                f"{family} snapshot/formal balance Decimal amount tie-out failed: {mismatch_examples[:3]}",
            )
            balance_trace_checks[family] = {
                "snapshot_duplicate_trace_count": snapshot_duplicates,
                "invalid_native_cny_pair_count": invalid_pairs,
                "missing_formal_trace_count": len(missing_traces),
                "extra_formal_trace_count": len(extra_traces),
            }
            balance_amount_checks[family] = {
                "comparison_count": comparison_count,
                "mismatch_count": 0,
                "max_absolute_residual": "0.00000000",
                "mismatch_examples": [],
            }
        business_tie_outs["snapshot_to_formal_balance_trace"] = balance_trace_checks
        business_tie_outs["snapshot_to_formal_balance_amounts"] = balance_amount_checks

        if through_stage == "balance":
            return {
                "validation_scope": "stage_prefix",
                "validated_through_stage": through_stage,
                "schema_migrations": {
                    "required": list(REQUIRED_SCHEMA_MIGRATIONS),
                    "applied": sorted(applied_versions),
                    "missing": [],
                },
                "target_counts": counts,
                "business_tie_outs": business_tie_outs,
                "fx": fx_receipt,
                "curve_anchors": [],
                "curves": [],
            }

        snapshot_rows = conn.execute(
            """
            select trace_id, market_value_native
            from zqtz_bond_daily_snapshot
            where cast(report_date as varchar) = ?
              and not coalesce(is_issuance_like, false)
            """,
            [TARGET_REPORT_DATE],
        ).fetchall()
        bond_rows = conn.execute(
            """
            select trace_id, face_value, market_value, amortized_cost,
                   accrued_interest, market_value_native
            from fact_formal_bond_analytics_daily
            where cast(report_date as varchar) = ?
            """,
            [TARGET_REPORT_DATE],
        ).fetchall()
        snapshot_trace_counts = Counter(str(row[0]) for row in snapshot_rows)
        bond_trace_counts = Counter(str(row[0]) for row in bond_rows)
        snapshot_duplicates = sum(
            count != 1 for count in snapshot_trace_counts.values()
        )
        bond_duplicates = sum(count != 1 for count in bond_trace_counts.values())
        missing_bond_traces = set(snapshot_trace_counts) - set(bond_trace_counts)
        extra_bond_traces = set(bond_trace_counts) - set(snapshot_trace_counts)
        _require(
            len(snapshot_rows)
            == EXPECTED_TARGET_COUNTS["fact_formal_bond_analytics_daily"],
            f"Non-issuance snapshot count does not match expected bond population: {len(snapshot_rows)}",
        )
        _require(
            not snapshot_duplicates
            and not bond_duplicates
            and not missing_bond_traces
            and not extra_bond_traces,
            "Bond/non-issuance snapshot trace tie-out failed: "
            f"snapshot_duplicates={snapshot_duplicates}, bond_duplicates={bond_duplicates}, "
            f"missing={len(missing_bond_traces)}, extra={len(extra_bond_traces)}",
        )
        zqtz_snapshot_amounts = {str(row[0]): row[1] for row in snapshot_rows}
        zqtz_cny_balances = {
            str(row[0]): row[1:]
            for row in conn.execute(
                """
                select trace_id, face_value_amount, market_value_amount,
                       amortized_cost_amount, accrued_interest_amount
                from fact_formal_zqtz_balance_daily
                where cast(report_date as varchar) = ? and currency_basis = 'CNY'
                """,
                [TARGET_REPORT_DATE],
            ).fetchall()
        }
        bond_fields = (
            "face_value",
            "market_value",
            "amortized_cost",
            "accrued_interest",
        )
        bond_mismatches: list[dict[str, object]] = []
        bond_comparison_count = 0
        for row in bond_rows:
            trace_id = str(row[0])
            for field_name, observed, expected in zip(
                bond_fields,
                row[1:5],
                zqtz_cny_balances[trace_id],
                strict=True,
            ):
                observed_value = _decimal_q8(observed)
                expected_value = _decimal_q8(expected)
                bond_comparison_count += 1
                if observed_value != expected_value:
                    bond_mismatches.append(
                        {
                            "trace_id": trace_id,
                            "field": field_name,
                            "expected": str(expected_value),
                            "observed": str(observed_value),
                            "residual": str(observed_value - expected_value),
                        }
                    )
            observed_native = _decimal_q8(row[5])
            expected_native = _decimal_q8(zqtz_snapshot_amounts[trace_id])
            bond_comparison_count += 1
            if observed_native != expected_native:
                bond_mismatches.append(
                    {
                        "trace_id": trace_id,
                        "field": "market_value_native",
                        "expected": str(expected_native),
                        "observed": str(observed_native),
                        "residual": str(observed_native - expected_native),
                    }
                )
        _require(
            not bond_mismatches,
            f"Bond/formal-balance/snapshot Decimal amount tie-out failed: {bond_mismatches[:3]}",
        )
        business_tie_outs["bond_snapshot_trace"] = {
            "non_issuance_snapshot_count": len(snapshot_rows),
            "snapshot_duplicate_trace_count": snapshot_duplicates,
            "bond_duplicate_trace_count": bond_duplicates,
            "missing_bond_trace_count": len(missing_bond_traces),
            "extra_bond_trace_count": len(extra_bond_traces),
        }
        business_tie_outs["bond_to_balance_and_snapshot_amounts"] = {
            "comparison_count": bond_comparison_count,
            "mismatch_count": 0,
            "max_absolute_residual": "0.00000000",
            "mismatch_examples": [],
        }
        return {
            "validation_scope": "stage_prefix",
            "validated_through_stage": through_stage,
            "schema_migrations": {
                "required": list(REQUIRED_SCHEMA_MIGRATIONS),
                "applied": sorted(applied_versions),
                "missing": [],
            },
            "target_counts": counts,
            "business_tie_outs": business_tie_outs,
            "fx": fx_receipt,
            "curve_anchors": [],
            "curves": [],
        }
    finally:
        conn.close()


def _actor_fn(actor: object) -> Callable[..., dict[str, object]]:
    candidate = getattr(actor, "fn", actor)
    _require(
        callable(candidate), f"Task actor does not expose a callable .fn: {actor!r}"
    )
    return candidate


def _load_actors() -> BackfillActors:
    from backend.app.tasks.balance_analysis_materialize import (
        materialize_balance_analysis_facts,
    )
    from backend.app.tasks.bond_analytics_materialize import (
        materialize_bond_analytics_facts,
    )
    from backend.app.tasks.risk_tensor_materialize import materialize_risk_tensor_facts
    from backend.app.tasks.snapshot_materialize import materialize_standard_snapshots

    return BackfillActors(
        snapshot=_actor_fn(materialize_standard_snapshots),
        balance=_actor_fn(materialize_balance_analysis_facts),
        bond=_actor_fn(materialize_bond_analytics_facts),
        risk=_actor_fn(materialize_risk_tensor_facts),
    )


def _acquire_apply_lock(paths: BackfillPaths):
    from backend.app.governance.locks import LockDefinition, acquire_lock

    return acquire_lock(
        LockDefinition(key=GLOBAL_REFRESH_LOCK_KEY, ttl_seconds=7_200),
        base_dir=paths.duckdb_path.parent,
    )


def _validate_stage_result(stage: str, result: object) -> dict[str, object]:
    _require(isinstance(result, dict), f"{stage} actor returned a non-object payload.")
    _require(
        result.get("status") == "completed",
        f"{stage} actor returned non-completed status={result.get('status')!r}.",
    )
    _require(
        bool(str(result.get("run_id") or "").strip()),
        f"{stage} actor returned an empty run_id.",
    )

    if stage == "snapshot":
        _require(
            bool(str(result.get("snapshot_run_id") or "").strip()),
            "snapshot actor returned an empty snapshot_run_id.",
        )
        _require(
            result.get("zqtz_rows") == 1_872 and result.get("tyw_rows") == 3_128,
            f"snapshot result count mismatch: {result}",
        )
        _require(
            result.get("ingest_batch_ids") == [TARGET_INGEST_BATCH_ID],
            f"snapshot selected unexpected batches: {result.get('ingest_batch_ids')!r}",
        )
        return result

    contract = FORMAL_STAGE_CONTRACTS[stage]
    _require(
        result.get("report_date") == TARGET_REPORT_DATE,
        f"{stage} result report_date mismatch.",
    )
    for field_name in ("source_version", "rule_version", "cache_version", "cache_key"):
        _require(
            bool(str(result.get(field_name) or "").strip()),
            f"{stage} result has empty {field_name}.",
        )
    _require(
        result.get("cache_key") == contract["cache_key"], f"{stage} cache_key mismatch."
    )
    _require(
        result.get("rule_version") == contract["rule_version"],
        f"{stage} rule_version mismatch.",
    )
    _require(
        result.get("cache_version") == contract["cache_version"],
        f"{stage} cache_version mismatch.",
    )
    for count_name, expected in dict(contract["counts"]).items():
        _require(
            result.get(count_name) == expected,
            f"{stage} {count_name} mismatch: {result.get(count_name)!r}",
        )

    payload = result.get("payload")
    _require(
        isinstance(payload, dict), f"{stage} result is missing formal runtime payload."
    )
    run = payload.get("run")
    lineage = payload.get("lineage")
    nested_result = payload.get("result")
    _require(
        isinstance(run, dict) and run.get("status") == "completed",
        f"{stage} runtime terminal is not completed.",
    )
    _require(
        run.get("run_id") == result["run_id"]
        and run.get("report_date") == TARGET_REPORT_DATE,
        f"{stage} runtime run identity mismatch.",
    )
    _require(isinstance(lineage, dict), f"{stage} runtime lineage is missing.")
    for field_name in (
        "run_id",
        "report_date",
        "source_version",
        "rule_version",
        "cache_version",
        "cache_key",
    ):
        _require(
            lineage.get(field_name) == result.get(field_name),
            f"{stage} runtime lineage {field_name} mismatch.",
        )
    _require(
        payload.get("error") is None, f"{stage} runtime payload contains an error."
    )
    _require(isinstance(nested_result, dict), f"{stage} nested result is missing.")
    for count_name, expected in dict(contract["counts"]).items():
        _require(
            nested_result.get(count_name) == expected,
            f"{stage} nested {count_name} mismatch.",
        )
    return result


def _validate_governance_terminal(
    *,
    stage: str,
    result: dict[str, object],
    paths: BackfillPaths,
    settings: object | None,
    production_gate: bool,
) -> dict[str, object]:
    if stage == "snapshot":
        build_rows = [
            row
            for row in _read_jsonl(paths.governance_dir / "snapshot_build_run.jsonl")
            if str(row.get("run_id") or "") == str(result["run_id"])
        ]
        _require(
            [row.get("status") for row in build_rows] == ["completed"],
            f"snapshot governance terminal mismatch: {build_rows}",
        )
        expected_snapshot_source_version = "__".join(
            sorted(
                str(SOURCE_CONTRACTS[family]["source_version"])
                for family in TARGET_SOURCE_FAMILIES
            )
        )
        _require(
            build_rows[0].get("source_version") == expected_snapshot_source_version,
            "snapshot build terminal source_version mismatch.",
        )
        manifest_rows = [
            row
            for row in _read_jsonl(paths.governance_dir / "snapshot_manifest.jsonl")
            if str(row.get("snapshot_run_id") or "") == str(result["snapshot_run_id"])
        ]
        _require(
            len(manifest_rows) == 2
            and all(row.get("status") == "completed" for row in manifest_rows),
            "snapshot must persist exactly two completed manifests.",
        )
        links = [row.get("source_linkage") for row in manifest_rows]
        _require(
            all(isinstance(link, dict) for link in links),
            "snapshot manifest source linkage is missing.",
        )
        by_family = {
            str(link["source_family"]): link for link in links if isinstance(link, dict)
        }
        _require(
            set(by_family) == set(TARGET_SOURCE_FAMILIES),
            "snapshot manifests do not cover exactly zqtz and tyw.",
        )
        for family, link in by_family.items():
            _require(
                link.get("ingest_batch_id") == TARGET_INGEST_BATCH_ID,
                f"snapshot {family} manifest batch mismatch.",
            )
            _require(
                link.get("source_version")
                == SOURCE_CONTRACTS[family]["source_version"],
                f"snapshot {family} manifest source_version mismatch.",
            )
            _require(
                not str(link.get("archived_path") or "").startswith("locf://"),
                "snapshot LOCF is forbidden for this backfill.",
            )
        manifest_by_family = {
            str(row["source_linkage"]["source_family"]): row for row in manifest_rows
        }
        for family, manifest in manifest_by_family.items():
            expected_table = (
                "zqtz_bond_daily_snapshot"
                if family == "zqtz"
                else "tyw_interbank_daily_snapshot"
            )
            _require(
                manifest.get("target_table") == expected_table,
                f"snapshot {family} manifest target_table mismatch.",
            )
            _require(
                manifest.get("produced_row_count")
                == SOURCE_CONTRACTS[family]["raw_rows"],
                f"snapshot {family} manifest produced_row_count mismatch.",
            )
            _require(
                manifest.get("rule_version") == "rv_snapshot_zqtz_tyw_v1",
                f"snapshot {family} manifest rule_version mismatch.",
            )
            _require(
                manifest.get("schema_version") == "snapshot.schema.v1",
                f"snapshot {family} manifest schema_version mismatch.",
            )
            _require(
                manifest.get("canonical_grain_version") == "cgv_v1",
                f"snapshot {family} manifest canonical_grain_version mismatch.",
            )
            archived_path = Path(
                str(manifest["source_linkage"].get("archived_path") or "")
            ).resolve()
            _require(
                _is_within(archived_path, paths.archive_root)
                and archived_path.name == SOURCE_CONTRACTS[family]["file_name"],
                f"snapshot {family} manifest archive linkage mismatch.",
            )
        return {
            "run_id": result["run_id"],
            "snapshot_run_id": result["snapshot_run_id"],
            "terminal_statuses": ["completed"],
            "manifest_count": 2,
            "authority": "jsonl_only_repository_contract",
            "sql_jsonl_parity": "not_applicable_stream_not_sql_supported",
        }

    run_id = str(result["run_id"])
    mirror_runs = [
        row
        for row in _read_jsonl(paths.governance_dir / "cache_build_run.jsonl")
        if str(row.get("run_id") or "") == run_id
    ]
    mirror_manifests = [
        row
        for row in _read_jsonl(paths.governance_dir / "cache_manifest.jsonl")
        if str(row.get("run_id") or "") == run_id
    ]
    _require(
        [row.get("status") for row in mirror_runs]
        == ["queued", "running", "completed"],
        f"{stage} JSONL governance state sequence mismatch.",
    )
    for run_row in mirror_runs:
        _require(
            run_row.get("cache_key") == result.get("cache_key")
            and run_row.get("cache_version") == result.get("cache_version")
            and run_row.get("report_date") == result.get("report_date"),
            f"{stage} JSONL build-run cache/date identity mismatch.",
        )
    terminal_run = mirror_runs[-1]
    _require(
        terminal_run.get("source_version") == result.get("source_version")
        and terminal_run.get("rule_version") == result.get("rule_version"),
        f"{stage} JSONL completed build-run lineage mismatch.",
    )
    _require(
        len(mirror_manifests) == 1,
        f"{stage} must persist exactly one JSONL cache manifest.",
    )
    manifest = mirror_manifests[0]
    for field_name in (
        "cache_key",
        "cache_version",
        "source_version",
        "rule_version",
        "report_date",
        "run_id",
    ):
        _require(
            manifest.get(field_name) == result.get(field_name),
            f"{stage} JSONL manifest {field_name} mismatch.",
        )
    contract = FORMAL_STAGE_CONTRACTS[stage]
    _require(
        manifest.get("basis") == "formal",
        f"{stage} JSONL manifest basis must be formal.",
    )
    _require(
        tuple(manifest.get("fact_tables") or ()) == tuple(contract["fact_tables"]),
        f"{stage} JSONL manifest fact_tables mismatch.",
    )
    manifest_lineage = manifest.get("lineage")
    _require(
        isinstance(manifest_lineage, dict),
        f"{stage} JSONL manifest lineage is missing.",
    )
    for field_name in ("run_id", "report_date", "source_version", "rule_version"):
        _require(
            manifest_lineage.get(field_name) == result.get(field_name),
            f"{stage} JSONL manifest lineage {field_name} mismatch.",
        )
    _require(
        manifest.get("cache_key") == result.get("cache_key"),
        f"{stage} JSONL cache identity mismatch.",
    )
    _require(
        manifest.get("cache_version") == result.get("cache_version"),
        f"{stage} JSONL cache version mismatch.",
    )

    authority_parity = "not_checked_library_mode"
    if production_gate:
        from backend.app.repositories.governance_repo import (
            CACHE_BUILD_RUN_STREAM,
            CACHE_MANIFEST_STREAM,
            GovernanceRepository,
        )

        _require(
            settings is not None,
            "Production SQL-authority validation requires resolved settings.",
        )
        authority = GovernanceRepository(
            base_dir=paths.governance_dir,
            sql_dsn=str(getattr(settings, "governance_sql_dsn", "")),
            backend_mode="sql-authority",
        )
        authority_runs = [
            row
            for row in authority.read_all(CACHE_BUILD_RUN_STREAM)
            if str(row.get("run_id") or "") == run_id
        ]
        authority_manifests = [
            row
            for row in authority.read_all(CACHE_MANIFEST_STREAM)
            if str(row.get("run_id") or "") == run_id
        ]
        _require(
            authority_runs == mirror_runs,
            f"{stage} SQL-authority/cache_build_run JSONL parity failed.",
        )
        _require(
            authority_manifests == mirror_manifests,
            f"{stage} SQL-authority/cache_manifest JSONL parity failed.",
        )
        authority_parity = "passed"

    return {
        "run_id": run_id,
        "terminal_statuses": ["queued", "running", "completed"],
        "manifest_count": 1,
        "sql_jsonl_parity": authority_parity,
        "lineage": {
            key: result[key]
            for key in (
                "cache_key",
                "cache_version",
                "source_version",
                "rule_version",
                "report_date",
            )
        },
    }


def _run_verifier(
    *,
    paths: BackfillPaths,
    verifier: Callable[..., dict[str, object]],
) -> dict[str, object]:
    result = verifier(
        paths.baseline_db_path,
        paths.duckdb_path,
        report_date=TARGET_REPORT_DATE,
        temp_dir=paths.verifier_temp_dir,
    )
    _require(isinstance(result, dict), "Strong verifier returned a non-object payload.")
    _require(
        result.get("status") == "pass" and result.get("verdict") == "PASS",
        f"Strong verifier failed: {result.get('errors')!r}",
    )
    _require(
        result.get("errors") == [],
        f"Strong verifier PASS receipt contains errors: {result.get('errors')!r}",
    )
    source_sha256 = result.get("verifier_source_sha256")
    _require(
        isinstance(source_sha256, str)
        and re.fullmatch(r"[0-9A-Fa-f]{64}", source_sha256) is not None,
        "Strong verifier source SHA256 must be a nonblank 64-hex digest.",
    )
    _require(
        type(result.get("schema_version")) is int and result.get("schema_version") == 1,
        "Strong verifier schema_version must be integer 1.",
    )
    _require(
        result.get("verifier_version") == "1",
        "Strong verifier verifier_version must be '1'.",
    )
    _require(
        result.get("report_date") == TARGET_REPORT_DATE,
        f"Strong verifier report_date must be {TARGET_REPORT_DATE}.",
    )
    expected_lists = {
        "allowed_target_date_tables": list(VERIFIER_ALLOWED_TARGET_DATE_TABLES),
        "allowed_target_date_table_keys": list(VERIFIER_ALLOWED_TARGET_DATE_TABLE_KEYS),
        "frozen_tables": list(VERIFIER_FROZEN_TABLES),
        "frozen_table_keys": list(VERIFIER_FROZEN_TABLE_KEYS),
    }
    for field_name, expected in expected_lists.items():
        _require(
            result.get(field_name) == expected,
            f"Strong verifier {field_name} policy mismatch: {result.get(field_name)!r}",
        )
    _require(
        result.get("all_other_base_tables_policy") == VERIFIER_OTHER_TABLES_POLICY,
        "Strong verifier all-other-base-tables policy mismatch.",
    )
    algorithm = result.get("algorithm")
    _require(
        isinstance(algorithm, dict),
        "Strong verifier algorithm contract is missing.",
    )
    for field_name, expected in VERIFIER_ALGORITHM_MARKERS.items():
        _require(
            algorithm.get(field_name) == expected,
            f"Strong verifier algorithm {field_name} policy mismatch.",
        )

    baseline_evidence = result.get("baseline")
    current_evidence = result.get("current")
    inventory_keys: dict[str, set[str]] = {}
    inventories: dict[str, list[object]] = {}
    for side_name, side_evidence in (
        ("baseline", baseline_evidence),
        ("current", current_evidence),
    ):
        _require(
            isinstance(side_evidence, dict),
            f"Strong verifier {side_name} evidence is missing.",
        )
        _require(
            side_evidence.get("fingerprint_stable") is True,
            f"Strong verifier {side_name} fingerprint is not stable.",
        )
        inventory = side_evidence.get("inventory")
        _require(
            isinstance(inventory, list) and inventory,
            f"Strong verifier {side_name} inventory is missing or empty.",
        )
        keys: list[str] = []
        for entry in inventory:
            _require(
                isinstance(entry, dict)
                and bool(str(entry.get("schema") or "").strip())
                and bool(str(entry.get("table") or "").strip())
                and entry.get("table_type") == "BASE TABLE"
                and isinstance(entry.get("columns"), list)
                and bool(entry["columns"]),
                f"Strong verifier {side_name} inventory contains an invalid table entry: {entry!r}",
            )
            keys.append(f"{entry['schema']}.{entry['table']}")
        _require(
            len(keys) == len(set(keys)),
            f"Strong verifier {side_name} inventory contains duplicate table keys.",
        )
        inventories[side_name] = inventory
        inventory_keys[side_name] = set(keys)

    _require(
        inventories["baseline"] == inventories["current"],
        "Strong verifier baseline/current inventory evidence differs despite PASS.",
    )
    required_inventory_keys = set(VERIFIER_ALLOWED_TARGET_DATE_TABLE_KEYS) | set(
        VERIFIER_FROZEN_TABLE_KEYS
    )
    _require(
        required_inventory_keys <= inventory_keys["baseline"],
        "Strong verifier inventory omits required target-date or frozen tables.",
    )

    checks = result.get("checks")
    _require(isinstance(checks, dict), "Strong verifier checks evidence is missing.")
    fingerprint_check = checks.get("fingerprint")
    _require(
        isinstance(fingerprint_check, dict)
        and fingerprint_check.get("status") == "pass"
        and fingerprint_check.get("errors") == []
        and fingerprint_check.get("baseline_stable") is True
        and fingerprint_check.get("current_stable") is True,
        f"Strong verifier fingerprint check is not an internally consistent PASS: {fingerprint_check!r}",
    )
    inventory_check = checks.get("inventory")
    _require(
        isinstance(inventory_check, dict)
        and inventory_check.get("status") == "pass"
        and inventory_check.get("errors") == [],
        f"Strong verifier inventory check is not an internally consistent PASS: {inventory_check!r}",
    )
    table_checks = checks.get("tables")
    _require(
        isinstance(table_checks, dict)
        and set(table_checks) == inventory_keys["baseline"],
        "Strong verifier table comparisons do not exactly cover the verified BASE TABLE inventory.",
    )

    def require_digest_summary(value: object, *, label: str) -> dict[str, object]:
        _require(
            isinstance(value, dict)
            and type(value.get("row_count")) is int
            and value["row_count"] >= 0
            and isinstance(value.get("table_sha256"), str)
            and re.fullmatch(r"[0-9A-Fa-f]{64}", value["table_sha256"]) is not None,
            f"Strong verifier {label} digest summary is invalid: {value!r}",
        )
        return value

    target_keys = set(VERIFIER_ALLOWED_TARGET_DATE_TABLE_KEYS)
    for table_key, comparison in table_checks.items():
        _require(
            isinstance(comparison, dict)
            and comparison.get("allowed") is True
            and type(comparison.get("full_changed")) is bool,
            f"Strong verifier comparison for {table_key} is not an allowed result.",
        )
        expected_policy = (
            "target_date_only" if table_key in target_keys else "table_unchanged"
        )
        _require(
            comparison.get("delta_policy") == expected_policy,
            f"Strong verifier comparison policy mismatch for {table_key}.",
        )
        before = comparison.get("before")
        after = comparison.get("after")
        _require(
            isinstance(before, dict) and isinstance(after, dict),
            f"Strong verifier comparison snapshots are missing for {table_key}.",
        )
        before_full = require_digest_summary(
            before.get("full"), label=f"{table_key} baseline full"
        )
        after_full = require_digest_summary(
            after.get("full"), label=f"{table_key} current full"
        )
        _require(
            comparison["full_changed"] == (before_full != after_full),
            f"Strong verifier full_changed contradicts table digests for {table_key}.",
        )
        if expected_policy == "target_date_only":
            before_target = require_digest_summary(
                before.get("target_date"), label=f"{table_key} baseline target-date"
            )
            after_target = require_digest_summary(
                after.get("target_date"), label=f"{table_key} current target-date"
            )
            _require(
                before_target.get("date") == TARGET_REPORT_DATE
                and after_target.get("date") == TARGET_REPORT_DATE,
                f"Strong verifier target-date comparison date mismatch for {table_key}.",
            )
            before_non_target = require_digest_summary(
                before.get("non_target"), label=f"{table_key} baseline non-target"
            )
            after_non_target = require_digest_summary(
                after.get("non_target"), label=f"{table_key} current non-target"
            )
            _require(
                before_non_target == after_non_target,
                f"Strong verifier PASS contains a non-target-date delta for {table_key}.",
            )
        else:
            _require(
                before_full == after_full and comparison["full_changed"] is False,
                f"Strong verifier PASS contains a frozen-table delta for {table_key}.",
            )
    return {
        "receipt_sha256": _canonical_json_sha256(result),
        "verifier_source_sha256": source_sha256,
        "result": result,
    }


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    payload = (
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        + "\n"
    )
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def run_decimal_precision_backfill(
    *,
    report_date: str,
    ingest_batch_id: str,
    duckdb_path: str | Path,
    governance_dir: str | Path,
    archive_root: str | Path,
    baseline_db_path: str | Path,
    receipt_path: str | Path,
    verifier_temp_dir: str | Path | None,
    approved_commit: str | None,
    maintenance_window_ref: str | None = None,
    dba_backup_ref: str | None = None,
    dry_run: bool = False,
    verify_only: bool = False,
    apply_changes: bool = False,
    production_gate: bool = True,
    settings_loader: Callable[[], object] | None = None,
    git_probe: Callable[[Path], dict[str, object]] | None = None,
    actor_loader: Callable[[], BackfillActors] | None = None,
    source_input_validator: Callable[[BackfillPaths], dict[str, object]] | None = None,
    database_validator: Callable[[Path], dict[str, object]] | None = None,
    terminal_validator: Callable[..., dict[str, object]] | None = None,
    verifier: Callable[..., dict[str, object]] | None = None,
    execution_lock_factory: Callable[[BackfillPaths], object] | None = None,
) -> dict[str, object]:
    """Run the fixed-date backfill; dependency hooks are library-test only."""

    mode = (
        "dry_run"
        if dry_run
        else "verify_only"
        if verify_only
        else "apply"
        if apply_changes
        else "unspecified"
    )
    receipt: dict[str, object] = {
        "schema_version": 1,
        "runner_version": RUNNER_VERSION,
        "status": "running",
        "verdict": "FAIL",
        "mode": mode,
        "run_id": f"decimal_precision_backfill:{TARGET_REPORT_DATE}:{_utc_now()}",
        "report_date": str(report_date),
        "ingest_batch_id": str(ingest_batch_id),
        "source_families": list(TARGET_SOURCE_FAMILIES),
        "count_contract": dict(RECEIPT_COUNT_CONTRACT),
        "started_at": _utc_now(),
        "stages": [],
        "known_source_warnings": list(KNOWN_SOURCE_WARNINGS),
        "authorization": {
            "runbook_status_changed": False,
            "production_approval_granted_by_script": False,
            "external_references_independently_verified": False,
            "maintenance_window_ref": str(maintenance_window_ref or "").strip() or None,
            "dba_backup_ref": str(dba_backup_ref or "").strip() or None,
        },
        "safety": {
            "automatic_ingest": False,
            "automatic_fx_materialization": False,
            "automatic_curve_materialization": False,
            "network_fetch": False,
        },
        "write_executed": False,
        "write_completed": False,
        "stage_writes_completed": False,
    }
    active_step = "preflight"
    resolved_paths: BackfillPaths | None = None
    raw_receipt_path = Path(receipt_path)
    verify_fn: Callable[..., dict[str, object]] | None = None
    lock_context: object | None = None
    lock_entered = False
    write_started = False
    completed_stage_count = 0
    backup_baseline_fingerprint: dict[str, object] | None = None

    try:
        _require(
            str(report_date) == TARGET_REPORT_DATE,
            f"Only report_date={TARGET_REPORT_DATE} is permitted.",
        )
        _require(
            str(ingest_batch_id) == TARGET_INGEST_BATCH_ID,
            f"Only ingest_batch_id={TARGET_INGEST_BATCH_ID} is permitted.",
        )
        _require(
            sum((bool(dry_run), bool(verify_only), bool(apply_changes))) == 1,
            "Exactly one execution mode is required: dry_run, verify_only, or apply_changes.",
        )
        _require(
            verifier_temp_dir is not None or mode == "dry_run",
            "Apply and verify-only modes require an explicit --verifier-temp-dir.",
        )
        effective_verifier_temp_dir = verifier_temp_dir or Path(receipt_path).parent
        if mode == "apply":
            _require(
                bool(str(maintenance_window_ref or "").strip()),
                "Write mode requires --maintenance-window-ref.",
            )
            _require(
                bool(str(dba_backup_ref or "").strip()),
                "Write mode requires --dba-backup-ref.",
            )

        resolved_paths = _resolve_paths(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            archive_root=archive_root,
            baseline_db_path=baseline_db_path,
            receipt_path=receipt_path,
            verifier_temp_dir=effective_verifier_temp_dir,
        )
        receipt["paths"] = {
            "duckdb_path": str(resolved_paths.duckdb_path),
            "governance_dir": str(resolved_paths.governance_dir),
            "archive_root": str(resolved_paths.archive_root),
            "baseline_db_path": str(resolved_paths.baseline_db_path),
            "receipt_path": str(resolved_paths.receipt_path),
            "verifier_temp_dir": str(resolved_paths.verifier_temp_dir),
        }

        resolved_settings: object | None = None
        if production_gate:
            resolved_settings = (settings_loader or get_settings)()
            receipt["production_gate"] = _validate_production_gate(
                paths=resolved_paths,
                approved_commit=approved_commit,
                settings=resolved_settings,
                git_probe=git_probe or _probe_git,
            )
        else:
            receipt["production_gate"] = {
                "status": "disabled_for_explicit_library_test",
                "cli_exposes_bypass": False,
            }

        using_default_source_validator = source_input_validator is None
        validate_sources = source_input_validator or _validate_source_inputs
        using_default_database_validator = database_validator is None
        validate_database = database_validator or _validate_database_contract
        input_before = validate_sources(resolved_paths)
        database_before = validate_database(resolved_paths.duckdb_path)
        current_baseline_fingerprint = _file_fingerprint(resolved_paths.duckdb_path)
        backup_baseline_fingerprint = _file_fingerprint(resolved_paths.baseline_db_path)
        baseline_same_point = (
            current_baseline_fingerprint["bytes"]
            == backup_baseline_fingerprint["bytes"]
            and current_baseline_fingerprint["sha256"]
            == backup_baseline_fingerprint["sha256"]
        )
        receipt["preflight"] = {
            "status": "passed",
            "immutable_inputs": input_before,
            "database_contract": database_before,
            "baseline_same_point": {
                "status": "matched" if baseline_same_point else "mismatch",
                "current": current_baseline_fingerprint,
                "baseline": backup_baseline_fingerprint,
            },
        }

        verify_fn = verifier
        if verify_fn is None:
            from scripts.verify_decimal_precision_backfill import verify_databases

            verify_fn = verify_databases

        if mode == "dry_run":
            receipt.update(
                {
                    "status": "dry_run",
                    "verdict": "PASS",
                    "finished_at": _utc_now(),
                    "planned_stages": [
                        "snapshot",
                        "balance",
                        "bond",
                        "risk",
                        "verifier",
                    ],
                }
            )
            _write_receipt(resolved_paths.receipt_path, receipt)
            return receipt

        if mode == "verify_only":
            if using_default_source_validator:
                _require_snapshot_archive_tieout(input_before)
            active_step = "baseline_pre_verifier"
            receipt["pre_verifier_baseline_recheck"] = {
                "status": "passed",
                "baseline": _require_unchanged_fingerprint(
                    resolved_paths.baseline_db_path,
                    backup_baseline_fingerprint,
                    label="Baseline DuckDB",
                ),
            }
            active_step = "verifier"
            receipt["verifier"] = _run_verifier(
                paths=resolved_paths, verifier=verify_fn
            )
            active_step = "immutable_input_postcheck"
            input_after = validate_sources(resolved_paths)
            _require(
                _immutable_source_evidence(input_after)
                == _immutable_source_evidence(input_before),
                "Immutable source_manifest/archive inventory changed during verify-only mode.",
            )
            if using_default_source_validator:
                _require_snapshot_archive_tieout(input_after)
            receipt["postflight"] = {
                "immutable_inputs": input_after,
                "database_contract": validate_database(resolved_paths.duckdb_path),
            }
            receipt.update(
                {
                    "status": "verified",
                    "verdict": "PASS",
                    "finished_at": _utc_now(),
                }
            )
            _write_receipt(resolved_paths.receipt_path, receipt)
            return receipt

        _require(
            baseline_same_point,
            "Write mode requires baseline/current DuckDB byte length and SHA256 to match before any actor runs.",
        )
        lock_context = (execution_lock_factory or _acquire_apply_lock)(resolved_paths)
        enter = getattr(lock_context, "__enter__", None)
        _require(
            callable(enter), "Execution lock factory did not return a context manager."
        )
        enter()
        lock_entered = True
        receipt["execution_lock"] = {
            "key": GLOBAL_REFRESH_LOCK_KEY,
            "base_dir": str(resolved_paths.duckdb_path.parent),
            "status": "acquired",
            "scope": "apply stages plus postflight and strong verifier",
            "maintenance_window_replaced": False,
        }
        current_recheck = _file_fingerprint(resolved_paths.duckdb_path)
        baseline_recheck = _require_unchanged_fingerprint(
            resolved_paths.baseline_db_path,
            backup_baseline_fingerprint,
            label="Baseline DuckDB",
        )
        _require(
            current_recheck == current_baseline_fingerprint,
            "Current DuckDB changed between preflight and locked pre-write static-point recheck.",
        )
        _require(
            current_recheck["bytes"] == baseline_recheck["bytes"]
            and current_recheck["sha256"] == baseline_recheck["sha256"],
            "Current DuckDB no longer matches the approved baseline at locked pre-write recheck.",
        )
        receipt["pre_write_static_point_recheck"] = {
            "status": "passed",
            "current": current_recheck,
            "baseline": baseline_recheck,
            "maintenance_window_replaced": False,
        }

        actors = (actor_loader or _load_actors)()
        validate_terminal = terminal_validator or _validate_governance_terminal
        outer_run_id = str(receipt["run_id"])

        stage_calls: list[tuple[str, Callable[[], dict[str, object]]]] = [
            (
                "snapshot",
                lambda: actors.snapshot(
                    duckdb_path=str(resolved_paths.duckdb_path),
                    governance_dir=str(resolved_paths.governance_dir),
                    ingest_batch_id=TARGET_INGEST_BATCH_ID,
                    source_families=list(TARGET_SOURCE_FAMILIES),
                    report_date=TARGET_REPORT_DATE,
                    local_archive_path=str(resolved_paths.archive_root),
                ),
            ),
            (
                "balance",
                lambda: actors.balance(
                    report_date=TARGET_REPORT_DATE,
                    duckdb_path=str(resolved_paths.duckdb_path),
                    governance_dir=str(resolved_paths.governance_dir),
                    run_id=f"{outer_run_id}:balance",
                    ingest_batch_id=TARGET_INGEST_BATCH_ID,
                    use_existing_fx_only=True,
                ),
            ),
            (
                "bond",
                lambda: actors.bond(
                    report_date=TARGET_REPORT_DATE,
                    duckdb_path=str(resolved_paths.duckdb_path),
                    governance_dir=str(resolved_paths.governance_dir),
                    run_id=f"{outer_run_id}:bond",
                    use_existing_curves_only=True,
                ),
            ),
            (
                "risk",
                lambda: actors.risk(
                    report_date=TARGET_REPORT_DATE,
                    duckdb_path=str(resolved_paths.duckdb_path),
                    governance_dir=str(resolved_paths.governance_dir),
                    run_id=f"{outer_run_id}:risk",
                ),
            ),
        ]

        stage_receipts = receipt["stages"]
        assert isinstance(stage_receipts, list)
        for stage, execute in stage_calls:
            active_step = stage
            started_at = _utc_now()
            started = perf_counter()
            snapshot_source_contract: dict[str, object] | None = None
            try:
                write_started = True
                result = _validate_stage_result(stage, execute())
                governance = validate_terminal(
                    stage=stage,
                    result=result,
                    paths=resolved_paths,
                    settings=resolved_settings,
                    production_gate=production_gate,
                )
                database_after_stage = (
                    _validate_database_stage_contract(
                        resolved_paths.duckdb_path,
                        through_stage=stage,
                    )
                    if using_default_database_validator
                    else validate_database(resolved_paths.duckdb_path)
                )
                target_counts = database_after_stage.get("target_counts")
                _require(
                    isinstance(target_counts, dict),
                    f"{stage} database validator omitted target_counts.",
                )
                observed_stage_counts = {
                    table: target_counts.get(table) for table in STAGE_TABLES[stage]
                }
                expected_stage_counts = {
                    table: EXPECTED_TARGET_COUNTS[table]
                    for table in STAGE_TABLES[stage]
                }
                _require(
                    observed_stage_counts == expected_stage_counts,
                    f"{stage} persisted target counts mismatch: {observed_stage_counts}",
                )
                if stage == "snapshot" and using_default_source_validator:
                    snapshot_source_contract = validate_sources(resolved_paths)
                    _require(
                        _immutable_source_evidence(snapshot_source_contract)
                        == _immutable_source_evidence(input_before),
                        "source_manifest or archive namespace changed during snapshot materialization.",
                    )
                    _require_snapshot_archive_tieout(snapshot_source_contract)
            except Exception as exc:
                stage_receipts.append(
                    {
                        "name": stage,
                        "status": "failed",
                        "started_at": started_at,
                        "finished_at": _utc_now(),
                        "elapsed_seconds": round(perf_counter() - started, 3),
                        "failure_category": "stage_contract_failure",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                raise
            stage_receipts.append(
                {
                    "name": stage,
                    "status": "completed",
                    "started_at": started_at,
                    "finished_at": _utc_now(),
                    "elapsed_seconds": round(perf_counter() - started, 3),
                    "result": result,
                    "governance_terminal": governance,
                    "database_contract": database_after_stage,
                    "snapshot_source_contract": snapshot_source_contract,
                    "persisted_target_counts": observed_stage_counts,
                }
            )
            completed_stage_count += 1

        active_step = "immutable_input_postcheck"
        input_after = validate_sources(resolved_paths)
        _require(
            _immutable_source_evidence(input_after)
            == _immutable_source_evidence(input_before),
            "source_manifest or archive namespace changed during backfill.",
        )
        if using_default_source_validator:
            _require_snapshot_archive_tieout(input_after)
        database_after = validate_database(resolved_paths.duckdb_path)
        receipt["postflight"] = {
            "immutable_inputs": input_after,
            "database_contract": database_after,
        }

        active_step = "baseline_pre_verifier"
        receipt["postflight"]["baseline_pre_verifier"] = {
            "status": "passed",
            "baseline": _require_unchanged_fingerprint(
                resolved_paths.baseline_db_path,
                backup_baseline_fingerprint,
                label="Baseline DuckDB",
            ),
        }
        active_step = "verifier"
        receipt["verifier"] = _run_verifier(paths=resolved_paths, verifier=verify_fn)
        receipt.update(
            {
                "status": "completed",
                "verdict": "PASS",
                "finished_at": _utc_now(),
                "write_executed": True,
                "write_completed": True,
                "stage_writes_completed": True,
            }
        )
        exit_lock = getattr(lock_context, "__exit__", None)
        assert callable(exit_lock)
        exit_lock(None, None, None)
        lock_entered = False
        assert isinstance(receipt["execution_lock"], dict)
        receipt["execution_lock"]["status"] = "released"
        _write_receipt(resolved_paths.receipt_path, receipt)
        return receipt
    except Exception as exc:
        if write_started and resolved_paths is not None and verify_fn is not None:
            try:
                _require(
                    backup_baseline_fingerprint is not None,
                    "Preflight baseline fingerprint is unavailable for failure forensics.",
                )
                forensic_baseline = _require_unchanged_fingerprint(
                    resolved_paths.baseline_db_path,
                    backup_baseline_fingerprint,
                    label="Baseline DuckDB before failure forensics",
                )
                forensic_result = verify_fn(
                    resolved_paths.baseline_db_path,
                    resolved_paths.duckdb_path,
                    report_date=TARGET_REPORT_DATE,
                    temp_dir=resolved_paths.verifier_temp_dir,
                )
                receipt["failure_forensics"] = {
                    "status": "captured",
                    "overall_run_remains_failed": True,
                    "pass_meaning": "a PASS proves only allowed database delta scope; it does not rescue the failed stage",
                    "baseline": forensic_baseline,
                    "receipt_sha256": _canonical_json_sha256(forensic_result),
                    "strong_verifier": forensic_result,
                }
            except Exception as forensic_exc:
                receipt["failure_forensics"] = {
                    "status": "capture_failed",
                    "overall_run_remains_failed": True,
                    "error_type": type(forensic_exc).__name__,
                    "error_message": str(forensic_exc),
                }
        if lock_entered and lock_context is not None:
            try:
                exit_lock = getattr(lock_context, "__exit__", None)
                if callable(exit_lock):
                    exit_lock(type(exc), exc, exc.__traceback__)
                if isinstance(receipt.get("execution_lock"), dict):
                    receipt["execution_lock"]["status"] = "released_after_failure"
            except Exception as lock_exc:
                receipt["execution_lock_release_error"] = (
                    f"{type(lock_exc).__name__}: {lock_exc}"
                )
            lock_entered = False
        receipt.update(
            {
                "status": "failed",
                "verdict": "FAIL",
                "failed_step": active_step,
                "failure_category": (
                    "production_gate_failure"
                    if active_step == "preflight" and production_gate
                    else "verification_failure"
                    if active_step == "verifier"
                    else "immutable_input_failure"
                    if active_step == "immutable_input_postcheck"
                    else "baseline_evidence_failure"
                    if active_step == "baseline_pre_verifier"
                    else "stage_failure"
                    if active_step in STAGE_TABLES
                    else "preflight_failure"
                ),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "finished_at": _utc_now(),
                "write_executed": write_started,
                "write_completed": False,
                "stage_writes_completed": completed_stage_count == len(STAGE_TABLES),
            }
        )
        target_receipt = (
            resolved_paths.receipt_path
            if resolved_paths is not None
            else raw_receipt_path
        )
        if target_receipt.is_absolute() and target_receipt.parent.is_dir():
            try:
                _write_receipt(target_receipt, receipt)
            except Exception as write_exc:
                receipt["receipt_write_error"] = (
                    f"{type(write_exc).__name__}: {write_exc}"
                )
        raise DecimalPrecisionBackfillFailed(receipt) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-date", required=True)
    parser.add_argument("--ingest-batch-id", required=True)
    parser.add_argument("--duckdb-path", required=True, type=Path)
    parser.add_argument("--governance-dir", required=True, type=Path)
    parser.add_argument("--archive-root", required=True, type=Path)
    parser.add_argument(
        "--baseline-db", dest="baseline_db_path", required=True, type=Path
    )
    parser.add_argument("--receipt-path", required=True, type=Path)
    parser.add_argument("--verifier-temp-dir", type=Path)
    parser.add_argument("--approved-commit", required=True)
    parser.add_argument("--maintenance-window-ref")
    parser.add_argument("--dba-backup-ref")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--apply", dest="apply_changes", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        receipt = run_decimal_precision_backfill(
            report_date=args.report_date,
            ingest_batch_id=args.ingest_batch_id,
            duckdb_path=args.duckdb_path,
            governance_dir=args.governance_dir,
            archive_root=args.archive_root,
            baseline_db_path=args.baseline_db_path,
            receipt_path=args.receipt_path,
            verifier_temp_dir=args.verifier_temp_dir,
            approved_commit=args.approved_commit,
            maintenance_window_ref=args.maintenance_window_ref,
            dba_backup_ref=args.dba_backup_ref,
            dry_run=args.dry_run,
            verify_only=args.verify_only,
            apply_changes=args.apply_changes,
        )
    except DecimalPrecisionBackfillFailed as exc:
        print(
            json.dumps(
                exc.receipt,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        )
        return 1
    print(
        json.dumps(
            receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
