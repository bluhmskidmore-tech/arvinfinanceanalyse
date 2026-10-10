from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import TypedDict

import duckdb

PNL_BY_BUSINESS_PRECOMPUTE_SCOPE = "pnl_by_business"
PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION = (
    "pnl_by_business_precompute_state_v1"
)


class PnlByBusinessInvalidationReceipt(TypedDict):
    event_revision: int
    affected_years: tuple[int, ...]
    pending_cutoffs: tuple[str, ...]


class PnlByBusinessPendingWork(TypedDict):
    year: int
    dependency_revision: int
    dirty_from_date: str
    target_dates: tuple[str, ...]
    reason: str
    invalidated_at: str | None
    protocol_version: str


class PnlByBusinessPrecomputeState(TypedDict):
    year: int
    as_of_date: str
    dependency_revision: int
    prepared_revision: int | None
    status: str
    source_version: str
    rule_version: str
    effective_ftp_rate_pct: str
    supplemental_source_version: str
    protocol_version: str
    generated_at: str | None
    is_ready: bool


class PnlByBusinessPrecomputeStaleWriteError(RuntimeError):
    """Raised when a build attempts to commit against an obsolete dependency revision."""


def ensure_pnl_by_business_precompute_state_schema(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Create the task-owned invalidation tables on an existing writer connection."""
    conn.execute(
        """
        create table if not exists fact_pnl_by_business_precompute_revision (
            scope_key varchar primary key,
            current_event_revision bigint not null,
            updated_at timestamp not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists fact_pnl_by_business_precompute_invalidation (
            scope_key varchar not null,
            event_revision bigint not null,
            year integer not null,
            dirty_from_date varchar not null,
            reason varchar not null,
            event_key varchar not null,
            invalidated_at timestamp not null,
            primary key (scope_key, event_revision, year)
        )
        """
    )
    conn.execute(
        """
        alter table fact_pnl_by_business_precompute_invalidation
        add column if not exists event_key varchar default ''
        """
    )
    conn.execute(
        """
        create table if not exists fact_pnl_by_business_precompute_cutoff_state (
            scope_key varchar not null,
            year integer not null,
            as_of_date varchar not null,
            required_event_revision bigint not null,
            prepared_event_revision bigint,
            status varchar not null,
            source_version varchar not null,
            rule_version varchar not null,
            effective_ftp_rate_pct varchar not null,
            supplemental_source_version varchar not null,
            protocol_version varchar not null,
            generated_at timestamp,
            updated_at timestamp not null,
            primary key (scope_key, year, as_of_date)
        )
        """
    )


def invalidate_pnl_by_business_precompute_on_connection(
    conn: duckdb.DuckDBPyConnection,
    *,
    changed_report_dates: Iterable[str],
    reason: str,
    supported_cutoffs: Iterable[str] = (),
    idempotency_key: str = "",
) -> PnlByBusinessInvalidationReceipt:
    """Persist invalidation on the caller's fact transaction and writer connection.

    Every non-empty call receives one globally ordered event revision.  The event is
    then scoped by year and dirty-from date, so an event in another year or after a
    requested cutoff does not invalidate that cutoff.
    """
    normalized_dates = _normalize_report_dates(changed_report_dates)
    normalized_supported_cutoffs = _normalize_report_dates(supported_cutoffs)
    if not normalized_dates:
        return {
            "event_revision": current_pnl_by_business_event_revision_on_connection(conn),
            "affected_years": (),
            "pending_cutoffs": (),
        }
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("reason must not be blank")

    ensure_pnl_by_business_precompute_state_schema(conn)
    normalized_event_key = str(idempotency_key or "").strip()
    if normalized_event_key:
        prior_rows = conn.execute(
            """
            select event_revision, year
            from fact_pnl_by_business_precompute_invalidation
            where scope_key = ? and event_key = ?
            order by event_revision, year
            """,
            [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, normalized_event_key],
        ).fetchall()
        if prior_rows:
            prior_revision = max(int(row[0]) for row in prior_rows)
            pending_rows = conn.execute(
                """
                select as_of_date
                from fact_pnl_by_business_precompute_cutoff_state
                where scope_key = ? and required_event_revision = ?
                  and (prepared_event_revision is null or prepared_event_revision < ?)
                order by as_of_date
                """,
                [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, prior_revision, prior_revision],
            ).fetchall()
            return {
                "event_revision": prior_revision,
                "affected_years": tuple(sorted({int(row[1]) for row in prior_rows})),
                "pending_cutoffs": tuple(str(row[0]) for row in pending_rows),
            }
    now = datetime.now(UTC).isoformat()
    current_revision = current_pnl_by_business_event_revision_on_connection(conn)
    event_revision = current_revision + 1
    conn.execute(
        """
        insert into fact_pnl_by_business_precompute_revision
            (scope_key, current_event_revision, updated_at)
        values (?, ?, ?)
        on conflict (scope_key) do update set
            current_event_revision = excluded.current_event_revision,
            updated_at = excluded.updated_at
        """,
        [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, event_revision, now],
    )

    dates_by_year: dict[int, list[str]] = {}
    for report_date in normalized_dates:
        dates_by_year.setdefault(date.fromisoformat(report_date).year, []).append(report_date)
    supported_cutoffs_by_year: dict[int, list[str]] = {}
    for cutoff in normalized_supported_cutoffs:
        supported_cutoffs_by_year.setdefault(date.fromisoformat(cutoff).year, []).append(cutoff)

    pending_cutoffs: set[str] = set()
    for year, report_dates in sorted(dates_by_year.items()):
        dirty_from_date = min(report_dates)
        conn.execute(
            """
            insert into fact_pnl_by_business_precompute_invalidation
                (scope_key, event_revision, year, dirty_from_date, reason, event_key, invalidated_at)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                PNL_BY_BUSINESS_PRECOMPUTE_SCOPE,
                event_revision,
                year,
                dirty_from_date,
                normalized_reason,
                normalized_event_key,
                now,
            ],
        )
        known_cutoffs = {
            cutoff
            for cutoff in supported_cutoffs_by_year.get(year, [])
            if cutoff >= dirty_from_date
        }
        known_cutoffs.update(
            str(row[0])
            for row in conn.execute(
                """
                select as_of_date
                from fact_pnl_by_business_precompute_cutoff_state
                where scope_key = ? and year = ? and as_of_date >= ?
                """,
                [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, year, dirty_from_date],
            ).fetchall()
        )
        if _table_exists(conn, "fact_pnl_by_business_precompute"):
            known_cutoffs.update(
                str(row[0])
                for row in conn.execute(
                    """
                    select distinct as_of_date
                    from fact_pnl_by_business_precompute
                    where year = ? and as_of_date >= ?
                    """,
                    [year, dirty_from_date],
                ).fetchall()
            )
        for as_of_date in sorted(known_cutoffs):
            pending_cutoffs.add(as_of_date)
            conn.execute(
                """
                insert into fact_pnl_by_business_precompute_cutoff_state (
                    scope_key, year, as_of_date, required_event_revision,
                    prepared_event_revision, status, source_version, rule_version,
                    effective_ftp_rate_pct, supplemental_source_version,
                    protocol_version, generated_at, updated_at
                ) values (?, ?, ?, ?, null, 'dirty', '', '', '', '', '', null, ?)
                on conflict (scope_key, year, as_of_date) do update set
                    required_event_revision = greatest(
                        fact_pnl_by_business_precompute_cutoff_state.required_event_revision,
                        excluded.required_event_revision
                    ),
                    status = 'dirty',
                    updated_at = excluded.updated_at
                """,
                [
                    PNL_BY_BUSINESS_PRECOMPUTE_SCOPE,
                    year,
                    as_of_date,
                    event_revision,
                    now,
                ],
            )

    return {
        "event_revision": event_revision,
        "affected_years": tuple(sorted(dates_by_year)),
        "pending_cutoffs": tuple(sorted(pending_cutoffs)),
    }


def current_pnl_by_business_event_revision_on_connection(
    conn: duckdb.DuckDBPyConnection,
) -> int:
    if not _table_exists(conn, "fact_pnl_by_business_precompute_revision"):
        return 0
    row = conn.execute(
        """
        select current_event_revision
        from fact_pnl_by_business_precompute_revision
        where scope_key = ?
        """,
        [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE],
    ).fetchone()
    return int(row[0] if row else 0)


def required_pnl_by_business_revision_on_connection(
    conn: duckdb.DuckDBPyConnection,
    *,
    year: int,
    as_of_date: str,
) -> int:
    normalized = _normalize_cutoff(year=year, as_of_date=as_of_date)
    if not _table_exists(conn, "fact_pnl_by_business_precompute_invalidation"):
        return 0
    row = conn.execute(
        """
        select coalesce(max(event_revision), 0)
        from fact_pnl_by_business_precompute_invalidation
        where scope_key = ? and year = ? and dirty_from_date <= ?
        """,
        [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, year, normalized],
    ).fetchone()
    return int(row[0] if row else 0)


def mark_pnl_by_business_precompute_ready_on_connection(
    conn: duckdb.DuckDBPyConnection,
    *,
    year: int,
    as_of_date: str,
    expected_dependency_revision: int,
    source_version: str,
    rule_version: str,
    effective_ftp_rate_pct: str,
    supplemental_source_version: str,
    generated_at: str,
) -> None:
    """CAS the cutoff state after result rows have been replaced in the same transaction."""
    normalized = _normalize_cutoff(year=year, as_of_date=as_of_date)
    required_revision = required_pnl_by_business_revision_on_connection(
        conn,
        year=year,
        as_of_date=normalized,
    )
    if required_revision != int(expected_dependency_revision):
        raise PnlByBusinessPrecomputeStaleWriteError(
            "Pnl-by-business precompute dependencies changed during the build: "
            f"expected revision {expected_dependency_revision}, current revision {required_revision}."
        )
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        insert into fact_pnl_by_business_precompute_cutoff_state (
            scope_key, year, as_of_date, required_event_revision,
            prepared_event_revision, status, source_version, rule_version,
            effective_ftp_rate_pct, supplemental_source_version,
            protocol_version, generated_at, updated_at
        ) values (?, ?, ?, ?, ?, 'ready', ?, ?, ?, ?, ?, ?, ?)
        on conflict (scope_key, year, as_of_date) do update set
            required_event_revision = excluded.required_event_revision,
            prepared_event_revision = excluded.prepared_event_revision,
            status = excluded.status,
            source_version = excluded.source_version,
            rule_version = excluded.rule_version,
            effective_ftp_rate_pct = excluded.effective_ftp_rate_pct,
            supplemental_source_version = excluded.supplemental_source_version,
            protocol_version = excluded.protocol_version,
            generated_at = excluded.generated_at,
            updated_at = excluded.updated_at
        """,
        [
            PNL_BY_BUSINESS_PRECOMPUTE_SCOPE,
            year,
            normalized,
            required_revision,
            required_revision,
            source_version,
            rule_version,
            effective_ftp_rate_pct,
            supplemental_source_version,
            PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
            generated_at,
            now,
        ],
    )


def fetch_pnl_by_business_precompute_state_on_connection(
    conn: duckdb.DuckDBPyConnection,
    *,
    year: int,
    as_of_date: str,
    expected_rule_version: str,
    effective_ftp_rate_pct: str,
    supplemental_source_version: str,
) -> PnlByBusinessPrecomputeState | None:
    normalized = _normalize_cutoff(year=year, as_of_date=as_of_date)
    if not _table_exists(conn, "fact_pnl_by_business_precompute_cutoff_state"):
        return None
    row = conn.execute(
        """
        select required_event_revision, prepared_event_revision, status,
               source_version, rule_version, effective_ftp_rate_pct,
               supplemental_source_version, protocol_version, generated_at
        from fact_pnl_by_business_precompute_cutoff_state
        where scope_key = ? and year = ? and as_of_date = ?
        """,
        [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, year, normalized],
    ).fetchone()
    if row is None:
        return None
    required_revision = int(row[0] or 0)
    prepared_revision = int(row[1]) if row[1] is not None else None
    state: PnlByBusinessPrecomputeState = {
        "year": year,
        "as_of_date": normalized,
        "dependency_revision": required_revision,
        "prepared_revision": prepared_revision,
        "status": str(row[2] or ""),
        "source_version": str(row[3] or ""),
        "rule_version": str(row[4] or ""),
        "effective_ftp_rate_pct": str(row[5] or ""),
        "supplemental_source_version": str(row[6] or ""),
        "protocol_version": str(row[7] or ""),
        "generated_at": str(row[8] or "") or None,
        "is_ready": False,
    }
    state["is_ready"] = bool(
        state["status"] == "ready"
        and prepared_revision == required_revision
        and state["protocol_version"]
        == PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION
        and state["rule_version"] == expected_rule_version
        and state["effective_ftp_rate_pct"] == effective_ftp_rate_pct
        and state["supplemental_source_version"] == supplemental_source_version
    )
    return state


def list_pending_pnl_by_business_precompute_on_connection(
    conn: duckdb.DuckDBPyConnection,
) -> list[PnlByBusinessPendingWork]:
    """Return durable recovery intents grouped by year and expected revision."""
    work: list[PnlByBusinessPendingWork] = []
    if _table_exists(conn, "fact_pnl_by_business_precompute"):
        legacy_groups: dict[tuple[int, int], list[str]] = {}
        legacy_rows = conn.execute(
            """
            select distinct year, as_of_date
            from fact_pnl_by_business_precompute
            order by year, as_of_date
            """
        ).fetchall()
        has_cutoff_state = _table_exists(
            conn, "fact_pnl_by_business_precompute_cutoff_state"
        )
        for raw_year, raw_cutoff in legacy_rows:
            year = int(raw_year)
            cutoff = str(raw_cutoff)
            if has_cutoff_state:
                state_row = conn.execute(
                    """
                    select status, prepared_event_revision, required_event_revision,
                           protocol_version
                    from fact_pnl_by_business_precompute_cutoff_state
                    where scope_key = ? and year = ? and as_of_date = ?
                    """,
                    [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, year, cutoff],
                ).fetchone()
                if state_row is not None and (
                    str(state_row[0] or "") == "ready"
                    and state_row[1] == state_row[2]
                    and str(state_row[3] or "")
                    == PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION
                ):
                    continue
                if state_row is not None:
                    continue
            revision = required_pnl_by_business_revision_on_connection(
                conn,
                year=year,
                as_of_date=cutoff,
            )
            legacy_groups.setdefault((year, revision), []).append(cutoff)
        for (year, revision), cutoffs in sorted(legacy_groups.items()):
            work.append(
                {
                    "year": year,
                    "dependency_revision": revision,
                    "dirty_from_date": min(cutoffs),
                    "target_dates": tuple(sorted(cutoffs)),
                    "reason": "protocol_upgrade",
                    "invalidated_at": None,
                    "protocol_version": PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
                }
            )

    required_tables = (
        "fact_pnl_by_business_precompute_invalidation",
        "fact_pnl_by_business_precompute_cutoff_state",
    )
    if not all(_table_exists(conn, table_name) for table_name in required_tables):
        return work
    pending_rows = conn.execute(
        """
        select year, required_event_revision, min(as_of_date),
               list(as_of_date order by as_of_date)
        from fact_pnl_by_business_precompute_cutoff_state
        where scope_key = ?
          and (
            prepared_event_revision is null
            or prepared_event_revision < required_event_revision
            or status <> 'ready'
            or protocol_version <> ?
          )
        group by year, required_event_revision
        order by year, required_event_revision
        """,
        [
            PNL_BY_BUSINESS_PRECOMPUTE_SCOPE,
            PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
        ],
    ).fetchall()
    covered_year_revisions: set[tuple[int, int]] = set()
    for year, revision, dirty_from, target_dates in pending_rows:
        event = conn.execute(
            """
            select dirty_from_date, reason, invalidated_at
            from fact_pnl_by_business_precompute_invalidation
            where scope_key = ? and year = ? and event_revision <= ?
            order by event_revision desc
            limit 1
            """,
            [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE, int(year), int(revision)],
        ).fetchone()
        covered_year_revisions.add((int(year), int(revision)))
        work.append(
            {
                "year": int(year),
                "dependency_revision": int(revision),
                "dirty_from_date": str(event[0] if event else dirty_from),
                "target_dates": tuple(str(value) for value in (target_dates or [])),
                "reason": str(event[1] if event else ""),
                "invalidated_at": str(event[2] if event and event[2] else "") or None,
                "protocol_version": PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
            }
        )

    uncovered_events = conn.execute(
        """
        select i.year, i.event_revision, i.dirty_from_date, i.reason, i.invalidated_at
        from fact_pnl_by_business_precompute_invalidation i
        where i.scope_key = ?
          and not exists (
            select 1
            from fact_pnl_by_business_precompute_cutoff_state c
            where c.scope_key = i.scope_key
              and c.year = i.year
              and c.as_of_date >= i.dirty_from_date
          )
        qualify row_number() over (partition by i.year order by i.event_revision desc) = 1
        order by i.year
        """,
        [PNL_BY_BUSINESS_PRECOMPUTE_SCOPE],
    ).fetchall()
    for year, revision, dirty_from, reason, invalidated_at in uncovered_events:
        key = (int(year), int(revision))
        if key in covered_year_revisions:
            continue
        work.append(
            {
                "year": int(year),
                "dependency_revision": int(revision),
                "dirty_from_date": str(dirty_from),
                "target_dates": (),
                "reason": str(reason or ""),
                "invalidated_at": str(invalidated_at or "") or None,
                "protocol_version": PNL_BY_BUSINESS_PRECOMPUTE_STATE_PROTOCOL_VERSION,
            }
        )
    return sorted(work, key=lambda item: (item["year"], item["dependency_revision"]))


def _normalize_report_dates(values: Iterable[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        normalized.add(date.fromisoformat(text).isoformat())
    return tuple(sorted(normalized))


def _normalize_cutoff(*, year: int, as_of_date: str) -> str:
    normalized = date.fromisoformat(str(as_of_date)).isoformat()
    if date.fromisoformat(normalized).year != int(year):
        raise ValueError(f"as_of_date={normalized} is outside requested year={year}.")
    return normalized


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select count(*)
        from information_schema.tables
        where lower(table_name) = lower(?)
        """,
        [table_name],
    ).fetchone()
    return bool(row and row[0])
