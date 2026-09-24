"""Persist realtime Livermore market-gate labels into ``livermore_gate_history``.

Why (governance finding G-1, High): the market-gate state label is not
reproducible over time — breadth / limit-up supply revisions shift the replayed
state for past dates (12/38 factor_screen signal dates drifted; recorded OFF
days replayed 0/16 consistent), and none of the persisted exposure tables that
:mod:`backend.app.core_finance.gate_exposure_series` prefers ever existed, so
official backtest exposure was 100% replayed with no anchor. This task writes
the gate evaluation of the day it actually happened (``source='realtime'``);
once written the row freezes and later replays are only compared against it.

Write policy (no historical backfill):

- only the freshest supplement date of the current refresh run is written
  (idempotent delete+insert, so same-day re-runs refresh it just like the
  supplement inputs themselves refresh their latest date);
- a target older than ``MAX_PERSIST_AGE_DAYS`` calendar days is never written
  (``skipped_historical_target``) — replaying the past with today's supply is
  exactly the fabrication this table exists to prevent, so historical backfill
  runs (e.g. ``scripts/backfill_livermore_gate_supplement.py``) leave the table
  untouched;
- a target in the future of the run's reference date is never written
  (``skipped_future_target``) — a not-yet-happened date cannot carry a
  realtime label;
- a target older than the newest persisted row is never written
  (``skipped_stale_target``) — the table only accumulates forward from its
  landing day. Dates without a row fall back to replay on the read side.

Consistency self-check: after the write, the persisted row is read back and
compared against the same-run replay (``write_consistency`` healthy /
inconsistent). Drift detection runs over an independent historical observation
window: the latest ``drift_scan_limit`` (default
``DRIFT_SCAN_LIMIT_DEFAULT`` = 10) persisted trade dates already in the table,
deliberately decoupled from this run's supplement dates — a mature daily
refresh only carries the newest date, which is also the one being written, so
a window derived from the run itself would never check any historical anchor.
Each scanned row (excluding the date just written this run) is compared
against the current replay and every mismatch is reported (and WARN-logged) as
label drift without touching the stored row — this is the drift detector. The
replay for the target date and the scan window shares a single load.

The replay used here is :func:`replay_market_gate_payloads`, the same
evaluation the official backtest replays through
``load_gate_exposure_by_date``, so "persisted vs replayed" is an
apples-to-apples comparison.

API-safe callers must not use this module (DuckDB write path). Writes happen
via :func:`backend.app.tasks.livermore_gate_supplement.materialize_livermore_gate_supplement_daily`,
which calls :func:`persist_livermore_gate_history_for_run` on its own
connection while holding ``LIVERMORE_GATE_SUPPLEMENT_LOCK``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, date, datetime

import duckdb
from backend.app.core_finance.gate_exposure_series import replay_market_gate_payloads
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

logger = logging.getLogger(__name__)

TABLE_NAME = "livermore_gate_history"
RULE_VERSION = "rv_livermore_gate_history_v1"
SOURCE_REALTIME = "realtime"
# A gate label only counts as realtime while the evaluation happens close to
# the trade date itself (same evening, or the next runs across a weekend /
# holiday gap). Anything older is a replay of the past, not a realtime label.
MAX_PERSIST_AGE_DAYS = 3
# Drift scan window: how many of the newest persisted trade dates are replayed
# and compared on every run. Independent from the run's own supplement dates.
DRIFT_SCAN_LIMIT_DEFAULT = 10
_EXPOSURE_TOLERANCE = 1e-9
_MAX_REPORTED_DRIFT_DATES = 20


def ensure_livermore_gate_history_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "41_livermore_gate_history.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def persist_livermore_gate_history_for_run(
    conn: duckdb.DuckDBPyConnection,
    *,
    supplement_dates: list[str],
    run_id: str,
    vendor_version_by_date: dict[str, str] | None = None,
    reference_date: date | None = None,
    drift_scan_limit: int = DRIFT_SCAN_LIMIT_DEFAULT,
) -> dict[str, object]:
    """Persist the freshest gate label of this run and drift-check history.

    Never raises: the supplement write this piggybacks on must not be
    jeopardized by the label anchor, so every failure degrades to a
    ``status='failed'`` payload plus a WARN log.
    """
    try:
        return _persist_for_run(
            conn,
            supplement_dates=supplement_dates,
            run_id=run_id,
            vendor_version_by_date=vendor_version_by_date or {},
            reference_date=reference_date or date.today(),
            drift_scan_limit=drift_scan_limit,
        )
    except Exception as exc:
        logger.warning(
            "Livermore gate-history persistence failed; the supplement write is unaffected.",
            exc_info=True,
        )
        _rollback_quietly(conn)
        return {
            "status": "failed",
            "table": TABLE_NAME,
            "rule_version": RULE_VERSION,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _persist_for_run(
    conn: duckdb.DuckDBPyConnection,
    *,
    supplement_dates: list[str],
    run_id: str,
    vendor_version_by_date: dict[str, str],
    reference_date: date,
    drift_scan_limit: int,
) -> dict[str, object]:
    dates = sorted({str(value)[:10] for value in supplement_dates if str(value).strip()})
    base: dict[str, object] = {
        "table": TABLE_NAME,
        "rule_version": RULE_VERSION,
        "run_id": run_id,
    }
    if not dates:
        return {**base, "status": "skipped_no_dates"}

    ensure_livermore_gate_history_schema(conn)
    target = dates[-1]
    base.update({"window_start": dates[0], "window_end": dates[-1], "target_trade_date": target})

    # Independent drift observation window: the newest N persisted trade dates
    # in the anchor table (before this run writes anything). A mature daily
    # refresh only carries the newest supplement date, so deriving the scan
    # window from the run's own dates would leave every historical anchor
    # unchecked forever.
    scan_labels = _load_latest_persisted_labels(conn, limit=drift_scan_limit)
    max_persisted = max(scan_labels) if scan_labels else None

    # One replay load covers both the write target and the drift scan window.
    replay_bounds = sorted([*dates, *scan_labels])
    replayed = replay_market_gate_payloads(
        conn,
        date.fromisoformat(replay_bounds[0]),
        date.fromisoformat(replay_bounds[-1]),
    )

    gate = replayed.get(target)
    target_age_days = (reference_date - date.fromisoformat(target)).days
    if gate is None:
        write_status = "skipped_not_replayable"
    elif target_age_days < 0:
        write_status = "skipped_future_target"
    elif target_age_days > MAX_PERSIST_AGE_DAYS:
        write_status = "skipped_historical_target"
    elif max_persisted is not None and max_persisted > target:
        write_status = "skipped_stale_target"
    else:
        write_status = "written"

    drift_dates, checked_count = _detect_drift(
        existing=scan_labels,
        replayed=replayed,
        exclude_date=target if write_status == "written" else None,
    )
    if drift_dates:
        logger.warning(
            "Livermore gate label drift detected on %d of %d checked date(s) (%s): the current replay "
            "no longer matches the persisted realtime label; persisted rows are kept as the anchor.",
            len(drift_dates),
            checked_count,
            ", ".join(str(entry["trade_date"]) for entry in drift_dates[:_MAX_REPORTED_DRIFT_DATES]),
        )

    write_consistency: str | None = None
    if write_status == "written":
        assert gate is not None
        _replace_gate_row(
            conn,
            trade_date=target,
            gate=gate,
            run_id=run_id,
            vendor_version=vendor_version_by_date.get(target) or "vv_livermore_gate_inputs_unrecorded",
        )
        write_consistency = _verify_written_row(conn, trade_date=target, gate=gate)
        if write_consistency != "healthy":
            logger.warning(
                "Livermore gate-history write self-check failed for %s: the persisted row does not "
                "match the same-run replay.",
                target,
            )

    return {
        **base,
        "status": write_status,
        "write_consistency": write_consistency,
        "drift_status": "detected" if drift_dates else "clean",
        "drift_count": len(drift_dates),
        "drift_dates": drift_dates[:_MAX_REPORTED_DRIFT_DATES],
        "checked_persisted_dates": checked_count,
        "drift_scan_limit": int(drift_scan_limit),
    }


def _load_latest_persisted_labels(
    conn: duckdb.DuckDBPyConnection,
    *,
    limit: int,
) -> dict[str, tuple[str, float]]:
    """Newest ``limit`` persisted anchor rows, keyed by trade date."""
    rows = conn.execute(
        f"""
        select trade_date, state, exposure
        from {TABLE_NAME}
        order by cast(trade_date as date) desc
        limit ?
        """,
        [max(int(limit), 0)],
    ).fetchall()
    return {str(row[0])[:10]: (str(row[1]), float(row[2])) for row in rows}


def _detect_drift(
    *,
    existing: dict[str, tuple[str, float]],
    replayed: dict[str, dict[str, object]],
    exclude_date: str | None,
) -> tuple[list[dict[str, object]], int]:
    """Compare stored realtime labels against the current replay.

    The date being (re)written this run is excluded: refreshing the freshest
    date with completed same-day inputs is the intended write semantics, not
    drift. Dates persisted earlier are never rewritten, only compared.
    """
    drift_dates: list[dict[str, object]] = []
    checked_count = 0
    for date_key in sorted(existing):
        if date_key == exclude_date:
            continue
        gate = replayed.get(date_key)
        if gate is None:
            continue
        checked_count += 1
        persisted_state, persisted_exposure = existing[date_key]
        replayed_state = _gate_state(gate)
        replayed_exposure = _gate_exposure(gate)
        if (
            persisted_state == replayed_state
            and abs(persisted_exposure - replayed_exposure) <= _EXPOSURE_TOLERANCE
        ):
            continue
        drift_dates.append(
            {
                "trade_date": date_key,
                "persisted_state": persisted_state,
                "persisted_exposure": persisted_exposure,
                "replayed_state": replayed_state,
                "replayed_exposure": replayed_exposure,
            }
        )
    return drift_dates, checked_count


def _replace_gate_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_date: str,
    gate: dict[str, object],
    run_id: str,
    vendor_version: str,
) -> None:
    state = _gate_state(gate)
    exposure = _gate_exposure(gate)
    passed = _coerce_int(gate.get("passed_conditions"))
    available = _coerce_int(gate.get("available_conditions"))
    required = _coerce_int(gate.get("required_conditions"))
    digest = hashlib.sha256(
        json.dumps(
            {
                "trade_date": trade_date,
                "state": state,
                "exposure": exposure,
                "passed_conditions": passed,
                "available_conditions": available,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    conditions = gate.get("conditions")
    conditions_json = json.dumps(conditions if isinstance(conditions, list) else [], ensure_ascii=False)

    conn.execute("begin transaction")
    try:
        conn.execute(f"delete from {TABLE_NAME} where trade_date = ?", [trade_date])
        conn.execute(
            f"""
            insert into {TABLE_NAME} (
              trade_date, state, exposure,
              passed_conditions, available_conditions, required_conditions,
              conditions_json, source, source_version, vendor_version,
              rule_version, run_id, persisted_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                trade_date,
                state,
                exposure,
                passed,
                available,
                required,
                conditions_json,
                SOURCE_REALTIME,
                f"sv_livermore_gate_history_{digest}",
                str(vendor_version),
                RULE_VERSION,
                run_id,
                datetime.now(UTC).isoformat(),
            ],
        )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise


def _verify_written_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_date: str,
    gate: dict[str, object],
) -> str:
    row = conn.execute(
        f"select state, exposure, source from {TABLE_NAME} where trade_date = ?",
        [trade_date],
    ).fetchone()
    if row is None:
        return "inconsistent"
    same_state = str(row[0]) == _gate_state(gate)
    same_exposure = abs(float(row[1]) - _gate_exposure(gate)) <= _EXPOSURE_TOLERANCE
    realtime_source = str(row[2]) == SOURCE_REALTIME
    return "healthy" if (same_state and same_exposure and realtime_source) else "inconsistent"


def _gate_state(gate: dict[str, object]) -> str:
    value = gate.get("state")
    return str(value).strip() if value is not None else "UNKNOWN"


def _gate_exposure(gate: dict[str, object]) -> float:
    value = gate.get("exposure")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


def _rollback_quietly(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("rollback")
    except duckdb.Error:
        logger.debug("No active gate-history transaction to roll back.")
