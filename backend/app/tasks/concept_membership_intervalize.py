"""Intervalize concept-membership snapshots into a point-in-time SCD table.

``choice_stock_concept_membership`` stores per-snapshot-date captures of the
*current* concept memberships (e.g. ``tushare_ths_current``); using its latest
snapshot for historical replay backfills today's memberships into the past
(look-ahead bias). This task derives the point-in-time read model
``choice_stock_concept_membership_interval`` (stock x concept x
``[valid_from, valid_to)``) so consumers can as-of join on a signal date.

Algorithm (per ``(stock_code, concept_source)``):

- A stock's observation dates are the snapshot dates on which it has at least
  one concept row. Snapshots are probe-based, so a stock absent from a
  snapshot was *not observed* that day; absence must not be read as "exited
  all concepts".
- Fold observation dates in ascending order. Memberships first seen at
  observation date ``d`` open an interval ``[d, NULL)``. Memberships present
  at the previous observation date but absent at ``d`` close their interval
  at ``d`` (``valid_to = d``, exclusive). Memberships present at both simply
  extend ``last_observed_date``. Re-entry after an exit opens a new interval
  row (SCD type 2).
- Nothing is extended backwards before a stock's first observation date:
  historical replay for earlier dates finds no rows and the consumer stays on
  its existing fail-closed fallback (proxy path).

The build is a deterministic pure function of the full snapshot set, persisted
with delete-then-insert in one transaction. Re-running on the same snapshot
set is a no-op in content (idempotent); appending a new snapshot date and
re-running closes/opens intervals exactly as the fold dictates.

Operational contract (see also docs/data_contracts.md §4.11): run this task
after every concept-membership snapshot ingest —
``backend.app.tasks.choice_stock_materialize.materialize_choice_stock_inputs``
(Choice css path or the Tushare THS fallback) is the only writer of the
snapshot table today. API-safe callers must not use this module (DuckDB write
path).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

RULE_VERSION = "rv_concept_membership_intervalize_v1"
SNAPSHOT_TABLE = "choice_stock_concept_membership"
INTERVAL_TABLE = "choice_stock_concept_membership_interval"
CONCEPT_MEMBERSHIP_INTERVALIZE_LOCK = LockDefinition(
    key="lock:duckdb:concept-membership-intervalize",
    ttl_seconds=600,
)


@dataclass(frozen=True)
class MembershipSnapshotRow:
    as_of_date: str
    stock_code: str
    concept_code: str
    concept_name: str
    concept_source: str
    field_key: str = ""
    source_version: str = ""
    vendor_version: str = ""


@dataclass(frozen=True)
class MembershipIntervalRow:
    stock_code: str
    concept_code: str
    concept_name: str
    concept_source: str
    valid_from: str
    valid_to: str | None
    last_observed_date: str
    field_key: str = ""
    source_version: str = ""
    vendor_version: str = ""


def ensure_concept_membership_interval_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "44_choice_stock_concept_membership_interval.sql").read_text(
        encoding="utf-8"
    )
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def build_membership_intervals(
    snapshot_rows: list[MembershipSnapshotRow],
) -> list[MembershipIntervalRow]:
    """Pure snapshot-diff fold; deterministic for a given snapshot set."""
    by_track: dict[tuple[str, str], dict[str, dict[str, MembershipSnapshotRow]]] = {}
    for row in snapshot_rows:
        stock_code = row.stock_code.strip()
        concept_key = row.concept_code.strip() or row.concept_name.strip()
        as_of_date = row.as_of_date.strip()
        if not stock_code or not concept_key or not as_of_date:
            continue
        track = by_track.setdefault((stock_code, row.concept_source.strip()), {})
        track.setdefault(as_of_date, {})[concept_key] = row

    intervals: list[MembershipIntervalRow] = []
    for (stock_code, concept_source), snapshots_by_date in sorted(by_track.items()):
        observation_dates = sorted(snapshots_by_date)
        open_intervals: dict[str, dict[str, object]] = {}
        for observed_date in observation_dates:
            members = snapshots_by_date[observed_date]
            for concept_key, state in list(open_intervals.items()):
                if concept_key not in members:
                    intervals.append(
                        _finalize_interval(
                            stock_code=stock_code,
                            concept_source=concept_source,
                            concept_key=concept_key,
                            state=state,
                            valid_to=observed_date,
                        )
                    )
                    del open_intervals[concept_key]
            for concept_key, row in members.items():
                state = open_intervals.get(concept_key)
                if state is None:
                    open_intervals[concept_key] = {
                        "valid_from": observed_date,
                        "last_observed_date": observed_date,
                        "row": row,
                    }
                else:
                    state["last_observed_date"] = observed_date
                    state["row"] = row
        for concept_key, state in open_intervals.items():
            intervals.append(
                _finalize_interval(
                    stock_code=stock_code,
                    concept_source=concept_source,
                    concept_key=concept_key,
                    state=state,
                    valid_to=None,
                )
            )
    intervals.sort(
        key=lambda item: (item.stock_code, item.concept_source, item.concept_code, item.valid_from)
    )
    return intervals


def _finalize_interval(
    *,
    stock_code: str,
    concept_source: str,
    concept_key: str,
    state: dict[str, object],
    valid_to: str | None,
) -> MembershipIntervalRow:
    row = state["row"]
    assert isinstance(row, MembershipSnapshotRow)
    return MembershipIntervalRow(
        stock_code=stock_code,
        concept_code=row.concept_code.strip() or concept_key,
        concept_name=row.concept_name.strip(),
        concept_source=concept_source,
        valid_from=str(state["valid_from"]),
        valid_to=valid_to,
        last_observed_date=str(state["last_observed_date"]),
        field_key=row.field_key,
        source_version=row.source_version,
        vendor_version=row.vendor_version,
    )


def intervalize_concept_membership(
    *,
    duckdb_path: str,
    run_id: str | None = None,
) -> dict[str, object]:
    """Rebuild the interval table from the full snapshot set.

    Returns a summary dict. ``status`` is ``no_snapshots`` when the snapshot
    table is missing or empty; in that case existing intervals are left
    untouched so a partially unavailable source cannot wipe the read model.
    """
    path = Path(duckdb_path)
    if not path.is_file():
        return {
            "status": "no_snapshots",
            "message": f"DuckDB file not found: {path}",
            "table": INTERVAL_TABLE,
            "rule_version": RULE_VERSION,
            "interval_row_count": 0,
        }
    effective_run = run_id or f"concept_membership_intervalize:{uuid.uuid4().hex[:12]}"

    with acquire_lock(CONCEPT_MEMBERSHIP_INTERVALIZE_LOCK, base_dir=path.parent):
        conn = duckdb.connect(str(path), read_only=False)
        try:
            snapshot_rows = _load_snapshot_rows(conn)
            if not snapshot_rows:
                return {
                    "status": "no_snapshots",
                    "message": f"{SNAPSHOT_TABLE} is missing or has no usable rows.",
                    "table": INTERVAL_TABLE,
                    "rule_version": RULE_VERSION,
                    "interval_row_count": 0,
                }
            intervals = build_membership_intervals(snapshot_rows)
            ensure_concept_membership_interval_schema(conn)
            _replace_interval_rows(conn, intervals, run_id=effective_run)
        finally:
            conn.close()

    snapshot_dates = sorted({row.as_of_date for row in snapshot_rows})
    open_count = sum(1 for row in intervals if row.valid_to is None)
    return {
        "status": "completed",
        "run_id": effective_run,
        "table": INTERVAL_TABLE,
        "rule_version": RULE_VERSION,
        "snapshot_date_count": len(snapshot_dates),
        "snapshot_dates": snapshot_dates,
        "interval_row_count": len(intervals),
        "open_interval_count": open_count,
        "closed_interval_count": len(intervals) - open_count,
        "coverage_first_date": snapshot_dates[0],
        "coverage_last_snapshot_date": snapshot_dates[-1],
    }


def _load_snapshot_rows(conn: duckdb.DuckDBPyConnection) -> list[MembershipSnapshotRow]:
    exists = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        limit 1
        """,
        [SNAPSHOT_TABLE],
    ).fetchone()
    if exists is None:
        return []
    rows = conn.execute(
        f"""
        select
          cast(as_of_date as varchar),
          stock_code,
          concept_code,
          concept_name,
          concept_source,
          field_key,
          source_version,
          vendor_version
        from {SNAPSHOT_TABLE}
        order by as_of_date asc, stock_code asc, concept_code asc
        """
    ).fetchall()
    return [
        MembershipSnapshotRow(
            as_of_date=str(row[0] or ""),
            stock_code=str(row[1] or ""),
            concept_code=str(row[2] or ""),
            concept_name=str(row[3] or ""),
            concept_source=str(row[4] or ""),
            field_key=str(row[5] or ""),
            source_version=str(row[6] or ""),
            vendor_version=str(row[7] or ""),
        )
        for row in rows
    ]


def _replace_interval_rows(
    conn: duckdb.DuckDBPyConnection,
    intervals: list[MembershipIntervalRow],
    *,
    run_id: str,
) -> None:
    # DuckDB ART unique indexes see deleted keys as still present inside the
    # same transaction, so a delete-then-insert rebuild of unchanged rows would
    # falsely violate the natural-key constraint (the in-transaction drop is
    # not visible to the insert either). Drop the index outside the write
    # transaction and recreate it after commit; the data rewrite itself stays
    # atomic, and a crash between commit and recreate is healed by the
    # ``create unique index if not exists`` in the schema ensure / next run.
    conn.execute("drop index if exists uq_concept_membership_interval_natural_key")
    conn.execute("begin transaction")
    try:
        conn.execute(f"delete from {INTERVAL_TABLE}")
        if intervals:
            conn.executemany(
                f"""
                insert into {INTERVAL_TABLE} (
                  stock_code, concept_code, concept_name, concept_source,
                  valid_from, valid_to, last_observed_date,
                  field_key, source_version, vendor_version, rule_version, run_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.stock_code,
                        row.concept_code,
                        row.concept_name,
                        row.concept_source,
                        row.valid_from,
                        row.valid_to,
                        row.last_observed_date,
                        row.field_key,
                        row.source_version,
                        row.vendor_version,
                        RULE_VERSION,
                        run_id,
                    )
                    for row in intervals
                ],
            )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    conn.execute(
        f"""
        create unique index if not exists uq_concept_membership_interval_natural_key
        on {INTERVAL_TABLE} (stock_code, concept_code, concept_source, valid_from)
        """
    )
