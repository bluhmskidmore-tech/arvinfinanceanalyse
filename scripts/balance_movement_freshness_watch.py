"""Daily freshness guard for the balance-movement read model."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.accounting_asset_movement_repo import (  # noqa: E402
    AccountingAssetMovementRepository,
)
from backend.app.repositories.governance_repo import GovernanceRepository  # noqa: E402
from backend.app.tasks.accounting_asset_movement import (  # noqa: E402
    CACHE_KEY,
    CACHE_VERSION,
    RULE_VERSION,
    refresh_accounting_asset_movement_window_sync,
)


SUCCESS_STATUSES = frozenset({"fresh", "repaired"})
RECEIPT_SCHEMA_VERSION = 1
TASK_NAME = "balance_movement_freshness_watch"


def _safe_error(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    return f"{type(exc).__name__}: {message[:300]}"


def _failed_result(
    *,
    code: str,
    message: str,
    currency_basis: str,
    latest_read_model_before: str | None,
    latest_upstream_control_report_date: str | None,
    latest_read_model_after: str | None = None,
    run_id: str | None = None,
    missing_report_dates_before: list[str] | None = None,
    missing_report_dates_after: list[str] | None = None,
    stale_report_dates_before: list[str] | None = None,
    stale_report_dates_after: list[str] | None = None,
    refreshed_report_dates: list[str] | None = None,
) -> dict[str, object]:
    return {
        "status": "failed",
        "checked_at": datetime.now(UTC).isoformat(),
        "currency_basis": currency_basis,
        "latest_read_model_before": latest_read_model_before,
        "latest_read_model_after": latest_read_model_after or latest_read_model_before,
        "latest_upstream_control_report_date": latest_upstream_control_report_date,
        "missing_report_dates_before": missing_report_dates_before or [],
        "missing_report_dates_after": missing_report_dates_after or [],
        "stale_report_dates_before": stale_report_dates_before or [],
        "stale_report_dates_after": stale_report_dates_after or [],
        "refreshed_report_dates": refreshed_report_dates or [],
        "row_count": 0,
        "run_id": run_id,
        "alert": {
            "active": True,
            "code": code,
            "severity": "high",
            "message": message,
        },
    }


def _version_tokens(value: object) -> frozenset[str]:
    return frozenset(
        token.strip()
        for token in str(value or "").split("__")
        if token.strip()
    )


def _current_dates(
    duckdb_path: str | Path,
    *,
    currency_basis: str,
) -> tuple[list[str], list[str], dict[str, str]]:
    repo = AccountingAssetMovementRepository(str(duckdb_path))
    return (
        repo.list_report_dates(currency_basis=currency_basis),
        repo.list_control_report_dates(currency_basis=currency_basis),
        repo.control_source_versions(currency_basis=currency_basis),
    )


def _stale_manifest_dates(
    *,
    governance_dir: str | Path,
    report_dates: list[str],
    upstream_control_report_dates: list[str],
    control_source_versions: dict[str, str],
    currency_basis: str,
) -> list[str]:
    materialized_dates = set(report_dates)
    governance_repo = GovernanceRepository(base_dir=governance_dir)
    stale_dates: list[str] = []
    for report_date in upstream_control_report_dates:
        if report_date not in materialized_dates:
            continue
        manifest = governance_repo.read_latest_manifest(
            CACHE_KEY,
            report_date=report_date,
        )
        lineage = manifest.get("lineage") if isinstance(manifest, dict) else None
        lineage_currency = (
            str(lineage.get("currency_basis") or "").strip().upper()
            if isinstance(lineage, dict)
            else ""
        )
        manifest_source_version = (
            str(manifest.get("source_version") or "")
            if isinstance(manifest, dict)
            else ""
        )
        current_source_version = control_source_versions.get(report_date, "")
        if (
            not isinstance(manifest, dict)
            or str(manifest.get("cache_version") or "") != CACHE_VERSION
            or str(manifest.get("rule_version") or "") != RULE_VERSION
            or lineage_currency != currency_basis
            or (
                current_source_version
                and _version_tokens(manifest_source_version)
                != _version_tokens(current_source_version)
            )
        ):
            stale_dates.append(report_date)
    return sorted(stale_dates)


def _repair_state(
    *,
    duckdb_path: str | Path,
    governance_dir: str | Path,
    currency_basis: str,
) -> tuple[
    list[str],
    list[str],
    list[str],
    list[str],
]:
    report_dates, upstream_dates, control_source_versions = _current_dates(
        duckdb_path,
        currency_basis=currency_basis,
    )
    missing_dates = sorted(set(upstream_dates).difference(report_dates))
    stale_dates = _stale_manifest_dates(
        governance_dir=governance_dir,
        report_dates=report_dates,
        upstream_control_report_dates=upstream_dates,
        control_source_versions=control_source_versions,
        currency_basis=currency_basis,
    )
    return report_dates, upstream_dates, missing_dates, stale_dates


def reconcile_balance_movement_freshness(
    *,
    duckdb_path: str | Path,
    governance_dir: str | Path,
    currency_basis: str = "CNX",
    product_category_source_dir: str | Path | None = None,
    data_root: str | Path | None = None,
    archive_dir: str | Path | None = None,
) -> dict[str, object]:
    del product_category_source_dir, data_root, archive_dir
    normalized_currency = str(currency_basis or "CNX").strip().upper() or "CNX"
    try:
        (
            report_dates_before,
            upstream_dates_before,
            missing_dates_before,
            stale_dates_before,
        ) = _repair_state(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            currency_basis=normalized_currency,
        )
    except Exception as exc:  # noqa: BLE001 - the watch must emit an actionable receipt
        return _failed_result(
            code="balance_movement_freshness_check_failed",
            message=_safe_error(exc),
            currency_basis=normalized_currency,
            latest_read_model_before=None,
            latest_upstream_control_report_date=None,
        )

    latest_read_model = report_dates_before[0] if report_dates_before else None
    latest_upstream = upstream_dates_before[0] if upstream_dates_before else None
    if latest_upstream is None:
        return {
            "status": "no_upstream_data",
            "checked_at": datetime.now(UTC).isoformat(),
            "currency_basis": normalized_currency,
            "latest_read_model_before": latest_read_model,
            "latest_read_model_after": latest_read_model,
            "latest_upstream_control_report_date": None,
            "missing_report_dates_before": [],
            "missing_report_dates_after": [],
            "stale_report_dates_before": [],
            "stale_report_dates_after": [],
            "refreshed_report_dates": [],
            "row_count": 0,
            "run_id": None,
            "alert": {
                "active": True,
                "code": "balance_movement_upstream_empty",
                "severity": "high",
                "message": (
                    "No governed CNX control-account dates were found in "
                    "product_category_pnl_canonical_fact."
                ),
            },
        }

    refresh_dates = sorted(set(missing_dates_before).union(stale_dates_before))
    if not refresh_dates:
        return {
            "status": "fresh",
            "checked_at": datetime.now(UTC).isoformat(),
            "currency_basis": normalized_currency,
            "latest_read_model_before": latest_read_model,
            "latest_read_model_after": latest_read_model,
            "latest_upstream_control_report_date": latest_upstream,
            "missing_report_dates_before": [],
            "missing_report_dates_after": [],
            "stale_report_dates_before": [],
            "stale_report_dates_after": [],
            "refreshed_report_dates": [],
            "row_count": None,
            "run_id": None,
            "alert": None,
        }

    try:
        refresh_result = refresh_accounting_asset_movement_window_sync(
            report_dates=refresh_dates,
            anchor_report_date=latest_upstream,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            currency_basis=normalized_currency,
            product_category_refreshed_dates=[],
            formal_balance_refreshed_dates=[],
        )
    except Exception as exc:  # noqa: BLE001 - task already records governed failure detail
        return _failed_result(
            code="balance_movement_refresh_failed",
            message=_safe_error(exc),
            currency_basis=normalized_currency,
            latest_read_model_before=latest_read_model,
            latest_upstream_control_report_date=latest_upstream,
            missing_report_dates_before=missing_dates_before,
            stale_report_dates_before=stale_dates_before,
            refreshed_report_dates=refresh_dates,
        )

    run_id = str(refresh_result.get("run_id") or "") or None
    payloads = refresh_result.get("payloads_by_date")
    row_counts = [
        int(payloads.get(report_date, {}).get("row_count") or 0)
        for report_date in refresh_dates
    ] if isinstance(payloads, dict) else []
    row_count = sum(row_counts)
    try:
        (
            report_dates_after,
            upstream_dates_after,
            missing_dates_after,
            stale_dates_after,
        ) = _repair_state(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            currency_basis=normalized_currency,
        )
    except Exception as exc:  # noqa: BLE001
        return _failed_result(
            code="balance_movement_postcheck_failed",
            message=_safe_error(exc),
            currency_basis=normalized_currency,
            latest_read_model_before=latest_read_model,
            latest_upstream_control_report_date=latest_upstream,
            run_id=run_id,
            missing_report_dates_before=missing_dates_before,
            stale_report_dates_before=stale_dates_before,
            refreshed_report_dates=refresh_dates,
        )

    latest_read_model_after = report_dates_after[0] if report_dates_after else None
    latest_upstream_after = upstream_dates_after[0] if upstream_dates_after else None
    if (
        refresh_result.get("status") != "completed"
        or len(row_counts) != len(refresh_dates)
        or any(current_row_count <= 0 for current_row_count in row_counts)
        or missing_dates_after
        or stale_dates_after
    ):
        return _failed_result(
            code="balance_movement_postcondition_failed",
            message=(
                "refresh completed without a fully governed read model: "
                f"status={refresh_result.get('status')}, row_count={row_count}, "
                f"read_model={latest_read_model_after}, upstream={latest_upstream_after}, "
                f"missing={missing_dates_after}, stale={stale_dates_after}"
            ),
            currency_basis=normalized_currency,
            latest_read_model_before=latest_read_model,
            latest_read_model_after=latest_read_model_after,
            latest_upstream_control_report_date=latest_upstream,
            run_id=run_id,
            missing_report_dates_before=missing_dates_before,
            missing_report_dates_after=missing_dates_after,
            stale_report_dates_before=stale_dates_before,
            stale_report_dates_after=stale_dates_after,
            refreshed_report_dates=refresh_dates,
        )

    return {
        "status": "repaired",
        "checked_at": datetime.now(UTC).isoformat(),
        "currency_basis": normalized_currency,
        "latest_read_model_before": latest_read_model,
        "latest_read_model_after": latest_read_model_after,
        "latest_upstream_control_report_date": latest_upstream_after,
        "missing_report_dates_before": missing_dates_before,
        "missing_report_dates_after": [],
        "stale_report_dates_before": stale_dates_before,
        "stale_report_dates_after": [],
        "refreshed_report_dates": refresh_dates,
        "row_count": row_count,
        "run_id": run_id,
        "alert": None,
    }


def _write_receipt_atomic(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(receipt, handle, ensure_ascii=False, default=str, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--duckdb-path")
    parser.add_argument("--governance-dir")
    parser.add_argument("--currency-basis", default="CNX")
    parser.add_argument("--receipt-path", type=Path)
    parser.add_argument(
        "--run-kind",
        choices=("manual", "scheduled"),
        default="manual",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    result = reconcile_balance_movement_freshness(
        duckdb_path=args.duckdb_path or settings.duckdb_path,
        governance_dir=args.governance_dir or settings.governance_path,
        currency_basis=args.currency_basis,
        product_category_source_dir=settings.product_category_source_dir,
        data_root=settings.data_input_root,
        archive_dir=settings.local_archive_path,
    )
    status = str(result.get("status") or "failed")
    exit_code = 0 if status in SUCCESS_STATUSES else 1
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_kind": args.run_kind,
        "task_name": TASK_NAME,
        "status": status,
        "exit_code": exit_code,
        "alert": result.get("alert"),
        "result": result,
    }
    print(json.dumps(receipt, ensure_ascii=False, default=str))
    if args.receipt_path is not None:
        try:
            _write_receipt_atomic(args.receipt_path, receipt)
        except Exception as exc:  # noqa: BLE001 - receipt durability is mandatory
            print(f"receipt write failed: {_safe_error(exc)}", file=sys.stderr)
            return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
