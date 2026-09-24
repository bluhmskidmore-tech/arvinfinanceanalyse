from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.snapshot_repo import repair_zqtz_snapshot_coupon_rates
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.tasks.broker import register_actor_once

REPAIR_NAME = "risk_tensor_negative_coupon_window_repair"
REPAIR_SOURCE = "sv_negative_coupon_window_repair_20260809_v1"
REPAIR_RULE = "rv_snapshot_negative_coupon_window_repair_v1"
REPAIR_STREAM = "data_quality_remediation"
REPAIR_LOCK = LockDefinition(
    key="lock:duckdb:formal:risk-coupon-window-repair",
    ttl_seconds=600,
)
WINDOW_START = date(2025, 10, 20)
WINDOW_END = date(2025, 11, 2)
EXPECTED_COUPONS = {
    "2089281": Decimal("2.87"),
    "2089307": Decimal("2.95"),
    "2089512": Decimal("3.00"),
    "2089517": Decimal("3.15"),
    "2189002": Decimal("3.25"),
    "2189170": Decimal("2.85"),
}
EXPECTED_FIRST_NEGATIVE_DATE = {
    "2089281": date(2025, 10, 20),
    "2089307": date(2025, 10, 27),
    "2089512": date(2025, 10, 27),
    "2089517": date(2025, 10, 27),
    "2189002": date(2025, 10, 27),
    "2189170": date(2025, 10, 27),
}
EXPECTED_NEGATIVE_OFFSET = Decimal("3.60")
EXPECTED_TARGET_COUNT = 49


def _date_range(start: date, end: date) -> tuple[str, ...]:
    return tuple(
        (start + timedelta(days=offset)).isoformat()
        for offset in range((end - start).days + 1)
    )


TARGET_REPORT_DATES = _date_range(WINDOW_START, WINDOW_END)


def _append_version(existing: object, version: str) -> str:
    parts = [part for part in str(existing or "").split("__") if part]
    if version not in parts:
        parts.append(version)
    return "__".join(parts)


def _append_rule(existing: object, rule: str) -> str:
    parts = {part for part in str(existing or "").split("__") if part}
    parts.add(rule)
    return "__".join(sorted(parts))


def _target_keys() -> tuple[tuple[str, str], ...]:
    keys: list[tuple[str, str]] = []
    for instrument_code, first_negative_date in EXPECTED_FIRST_NEGATIVE_DATE.items():
        keys.extend(
            (report_date, instrument_code)
            for report_date in _date_range(first_negative_date, WINDOW_END)
        )
    return tuple(sorted(keys))


EXPECTED_TARGET_KEYS = _target_keys()


def _load_repair_plan(duckdb_path: str) -> dict[str, object]:
    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        rows = conn.execute(
            """
            select cast(report_date as varchar), cast(instrument_code as varchar),
                   bond_type, coupon_rate, source_version, rule_version, ingest_batch_id, trace_id
            from zqtz_bond_daily_snapshot
            where cast(report_date as varchar) between '2025-10-01' and '2025-11-30'
              and cast(instrument_code as varchar) in (?, ?, ?, ?, ?, ?)
            order by instrument_code, report_date
            """,
            list(EXPECTED_COUPONS),
        ).fetchall()
    finally:
        conn.close()

    by_key: dict[tuple[str, str], tuple[object, ...]] = {}
    for row in rows:
        key = (str(row[0]), str(row[1]))
        if key in by_key:
            raise RuntimeError(
                "Coupon remediation target key is duplicated in the snapshot: "
                f"report_date={key[0]}, instrument_code={key[1]}."
            )
        by_key[key] = row
    to_update: list[dict[str, object]] = []
    already_repaired: list[dict[str, object]] = []
    for report_date, instrument_code in EXPECTED_TARGET_KEYS:
        row = by_key.get((report_date, instrument_code))
        if row is None:
            raise RuntimeError(
                "Coupon remediation target is missing from the snapshot: "
                f"report_date={report_date}, instrument_code={instrument_code}."
            )
        if str(row[2] or "").strip() != "资产支持证券":
            raise RuntimeError(
                "Coupon remediation target is outside the governed ABS scope: "
                f"report_date={report_date}, instrument_code={instrument_code}, "
                f"bond_type={row[2]!r}."
            )
        coupon_rate = Decimal(str(row[3]))
        expected_coupon = EXPECTED_COUPONS[instrument_code]
        previous_rows = [
            candidate
            for (candidate_date, candidate_code), candidate in by_key.items()
            if candidate_code == instrument_code
            and candidate_date < report_date
            and Decimal(str(candidate[3])) >= 0
        ]
        next_rows = [
            candidate
            for (candidate_date, candidate_code), candidate in by_key.items()
            if candidate_code == instrument_code
            and candidate_date > report_date
            and Decimal(str(candidate[3])) >= 0
        ]
        previous_coupon = Decimal(str(previous_rows[-1][3])) if previous_rows else None
        next_coupon = Decimal(str(next_rows[0][3])) if next_rows else None
        evidence = {
            "report_date": report_date,
            "instrument_code": instrument_code,
            "before_coupon_rate": str(coupon_rate),
            "previous_coupon_rate": str(previous_coupon) if previous_coupon is not None else None,
            "next_coupon_rate": str(next_coupon) if next_coupon is not None else None,
            "after_coupon_rate": str(expected_coupon),
            "source_version_before": str(row[4] or ""),
            "rule_version_before": str(row[5] or ""),
            "ingest_batch_id": str(row[6] or ""),
            "trace_id_before": str(row[7] or ""),
        }
        if (
            coupon_rate == expected_coupon
            and REPAIR_SOURCE in str(row[4] or "").split("__")
            and REPAIR_RULE in str(row[5] or "").split("__")
        ):
            already_repaired.append(evidence | {"already_repaired": True})
            continue
        if previous_coupon != expected_coupon or next_coupon != expected_coupon:
            raise RuntimeError(
                "Coupon remediation lacks matching before/after neighbor evidence: "
                f"report_date={report_date}, instrument_code={instrument_code}, "
                f"previous={previous_coupon}, next={next_coupon}, expected={expected_coupon}."
            )
        if expected_coupon - coupon_rate != EXPECTED_NEGATIVE_OFFSET:
            raise RuntimeError(
                "Coupon remediation target does not match the governed negative offset: "
                f"report_date={report_date}, instrument_code={instrument_code}, "
                f"before={coupon_rate}, expected={expected_coupon}."
            )
        trace_id_after = str(
            uuid5(
                NAMESPACE_URL,
                f"moss:{REPAIR_NAME}:{report_date}:{instrument_code}:{row[7]}",
            )
        )
        to_update.append(
            evidence
            | {
                "before_coupon_rate": coupon_rate,
                "after_coupon_rate": expected_coupon,
                "source_version_after": _append_version(row[4], REPAIR_SOURCE),
                "rule_version_after": _append_rule(row[5], REPAIR_RULE),
                "trace_id_after": trace_id_after,
                "already_repaired": False,
            }
        )

    if len(to_update) + len(already_repaired) != EXPECTED_TARGET_COUNT:
        raise RuntimeError("Coupon remediation target count does not match the governed contract.")
    return {
        "target_count": EXPECTED_TARGET_COUNT,
        "to_update": to_update,
        "already_repaired": already_repaired,
        "report_dates": list(TARGET_REPORT_DATES),
    }


def _rematerialize_downstream(
    *,
    report_dates: list[str],
    duckdb_path: str,
    governance_dir: str,
    run_id: str,
) -> list[dict[str, object]]:
    from backend.app.tasks.bond_analytics_materialize import materialize_bond_analytics_facts
    from backend.app.tasks.risk_tensor_materialize import materialize_risk_tensor_facts

    results: list[dict[str, object]] = []
    for report_date in report_dates:
        bond_kwargs: dict[str, object] = {
            "report_date": report_date,
            "duckdb_path": duckdb_path,
            "governance_dir": governance_dir,
            "run_id": f"{run_id}:{report_date}:bond",
            "use_existing_curves_only": True,
        }
        bond = materialize_bond_analytics_facts.fn(**bond_kwargs)
        if bond.get("status") != "completed":
            raise RuntimeError(f"Bond Analytics rematerialization failed for {report_date}.")
        risk = materialize_risk_tensor_facts.fn(
            report_date=report_date,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            run_id=f"{run_id}:{report_date}:risk",
        )
        if risk.get("status") != "completed":
            raise RuntimeError(f"Risk Tensor rematerialization failed for {report_date}.")
        results.append(
            {
                "report_date": report_date,
                "bond_source_version": bond.get("source_version"),
                "risk_source_version": risk.get("source_version"),
                "risk_rule_version": risk.get("rule_version"),
                "risk_cache_version": risk.get("cache_version"),
            }
        )
    return results


def _repair_risk_coupon_window(
    *,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
    dry_run: bool = True,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    governance_path = Path(governance_dir or settings.governance_path)
    resolved_run_id = run_id or f"risk-coupon-window-repair:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    plan = _load_repair_plan(str(duckdb_file))
    public_plan = {
        "target_count": plan["target_count"],
        "change_count": len(plan["to_update"]),
        "already_repaired_count": len(plan["already_repaired"]),
        "report_dates": plan["report_dates"],
        "targets": [
            {
                key: str(value) if isinstance(value, Decimal) else value
                for key, value in target.items()
            }
            for target in [*plan["to_update"], *plan["already_repaired"]]
        ],
    }
    if dry_run:
        return {"status": "dry_run", "run_id": resolved_run_id, **public_plan}

    governance = GovernanceRepository(governance_path)
    started = {
        "run_id": resolved_run_id,
        "repair_name": REPAIR_NAME,
        "repair_source": REPAIR_SOURCE,
        "repair_rule": REPAIR_RULE,
        "status": "started",
        "created_at": datetime.now(UTC).isoformat(),
        **public_plan,
    }
    governance.append(REPAIR_STREAM, started)
    try:
        changed_count = 0
        if plan["to_update"]:
            with acquire_lock(REPAIR_LOCK, base_dir=duckdb_file.parent):
                conn = duckdb.connect(str(duckdb_file), read_only=False)
                try:
                    with repository_task_write_scope(__name__):
                        changed_count = repair_zqtz_snapshot_coupon_rates(
                            conn,
                            plan["to_update"],
                        )
                finally:
                    conn.close()
        downstream = _rematerialize_downstream(
            report_dates=list(plan["report_dates"]),
            duckdb_path=str(duckdb_file),
            governance_dir=str(governance_path),
            run_id=resolved_run_id,
        )
        completed = started | {
            "status": "completed",
            "changed_count": changed_count,
            "downstream": downstream,
            "finished_at": datetime.now(UTC).isoformat(),
        }
        governance.append(REPAIR_STREAM, completed)
        return completed
    except Exception as exc:
        governance.append(
            REPAIR_STREAM,
            started
            | {
                "status": "failed",
                "error": str(exc),
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )
        raise


repair_risk_coupon_window = register_actor_once(
    "repair_risk_coupon_window",
    _repair_risk_coupon_window,
)
