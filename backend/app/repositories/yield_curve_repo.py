"""
Yield curve DuckDB access.

`YieldCurveRepository.fetch_curve_snapshot` is the **governed snapshot-lineage read surface**
for materialized curves (`fact_formal_yield_curve_daily`): consumers must use it when they
need vendor/source/rule lineage together with tenor points. Read-only views such as
`yield_curve_daily` omit `rule_version` and are not a substitute for lineage-aware reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import duckdb
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.task_write_guard import require_repository_task_write_scope
from backend.app.schemas.yield_curve import YieldCurveSnapshot

FORMAL_FACT_TABLE = "fact_formal_yield_curve_daily"
READ_VIEW = "yield_curve_daily"
FX_TABLE = "fx_daily_mid"

# Token embedded in user-visible fallback warnings (PnL bridge, bond analytics). Keep stable for tests.
YIELD_CURVE_LATEST_FALLBACK_PREFIX = "YIELD_CURVE_LATEST_FALLBACK"
FX_LATEST_FALLBACK_PREFIX = "FX_LATEST_FALLBACK"


def format_yield_curve_latest_fallback_warning(
    *,
    curve_type: str,
    resolved_trade_date: str,
    requested_trade_date: str,
) -> str:
    """Exact-date snapshot missing; consumer used `resolved_trade_date` (must surface as warning, not silent)."""
    return (
        f"{YIELD_CURVE_LATEST_FALLBACK_PREFIX}: Using latest available {curve_type} curve "
        f"from trade_date={resolved_trade_date} for requested_trade_date={requested_trade_date}."
    )


@dataclass(slots=True)
class YieldCurveRepository:
    path: str

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, Decimal]:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return {}
        try:
            if not _relation_exists(conn, READ_VIEW):
                return {}
            rows = conn.execute(
                f"""
                select tenor, rate_pct
                from {READ_VIEW}
                where trade_date = ?
                  and curve_type = ?
                order by tenor
                """,
                [trade_date, curve_type],
            ).fetchall()
            return {str(tenor): Decimal(str(rate_pct)) for tenor, rate_pct in rows}
        finally:
            conn.close()

    def fetch_latest_trade_date(self, curve_type: str) -> str | None:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return None
        try:
            if not _relation_exists(conn, READ_VIEW):
                return None
            row = conn.execute(
                f"""
                select max(cast(trade_date as varchar))
                from {READ_VIEW}
                where curve_type = ?
                """,
                [curve_type],
            ).fetchone()
            if row is None or row[0] in (None, ""):
                return None
            return str(row[0])
        finally:
            conn.close()

    def fetch_latest_trade_date_on_or_before(self, curve_type: str, trade_date: str) -> str | None:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return None
        try:
            if not _relation_exists(conn, READ_VIEW):
                return None
            row = conn.execute(
                f"""
                select max(cast(trade_date as varchar))
                from {READ_VIEW}
                where curve_type = ?
                  and cast(trade_date as varchar) <= ?
                """,
                [curve_type, trade_date],
            ).fetchone()
            if row is None or row[0] in (None, ""):
                return None
            return str(row[0])
        finally:
            conn.close()

    def fetch_tenor_on_or_before_many(
        self,
        *,
        curve_type: str,
        tenor: str,
        trade_dates: list[str],
    ) -> dict[str, tuple[Decimal | None, str | None]]:
        requested = [str(trade_date) for trade_date in dict.fromkeys(trade_dates) if str(trade_date or "")]
        if not requested:
            return {}
        empty: dict[str, tuple[Decimal | None, str | None]] = {
            trade_date: (None, None) for trade_date in requested
        }
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return empty
        try:
            if not _relation_exists(conn, READ_VIEW):
                return empty
            requested_sql = " union all ".join("select ? as requested_trade_date" for _ in requested)
            rows = conn.execute(
                f"""
                with requested as (
                  {requested_sql}
                ), ranked as (
                  select
                    r.requested_trade_date,
                    y.rate_pct,
                    cast(y.trade_date as varchar) as resolved_trade_date,
                    row_number() over (
                      partition by r.requested_trade_date
                      order by cast(y.trade_date as varchar) desc
                    ) as row_num
                  from requested r
                  left join {READ_VIEW} y
                    on y.curve_type = ?
                   and y.tenor = ?
                   and cast(y.trade_date as varchar) <= r.requested_trade_date
                )
                select requested_trade_date, rate_pct, resolved_trade_date
                from ranked
                where row_num = 1
                """,
                [*requested, curve_type, tenor],
            ).fetchall()
        finally:
            conn.close()
        out = dict(empty)
        for requested_trade_date, rate_pct, resolved_trade_date in rows:
            out[str(requested_trade_date)] = (
                Decimal(str(rate_pct)) if rate_pct is not None else None,
                str(resolved_trade_date) if resolved_trade_date not in (None, "") else None,
            )
        return out

    def list_trade_dates(self, curve_type: str) -> list[str]:
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return []
        try:
            if not _relation_exists(conn, READ_VIEW):
                return []
            rows = conn.execute(
                f"""
                select distinct cast(trade_date as varchar)
                from {READ_VIEW}
                where curve_type = ?
                order by cast(trade_date as varchar) desc
                """,
                [curve_type],
            ).fetchall()
            return [str(row[0]) for row in rows]
        finally:
            conn.close()

    def fetch_prior_trade_date(self, curve_type: str, trade_date: str) -> str | None:
        """Latest ``trade_date`` strictly before ``trade_date`` for ``curve_type`` (same read surface as snapshots)."""
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return None
        try:
            if not _relation_exists(conn, READ_VIEW):
                return None
            row = conn.execute(
                f"""
                select max(cast(trade_date as varchar))
                from {READ_VIEW}
                where curve_type = ?
                  and cast(trade_date as varchar) < ?
                """,
                [curve_type, trade_date],
            ).fetchone()
            if row is None or row[0] in (None, ""):
                return None
            return str(row[0])
        finally:
            conn.close()

    def fetch_prior_trade_dates_many(self, requests: list[tuple[str, str]]) -> dict[tuple[str, str], str | None]:
        normalized = [
            (str(curve_type).strip(), str(trade_date).strip())
            for curve_type, trade_date in dict.fromkeys(requests)
            if str(curve_type or "").strip() and str(trade_date or "").strip()
        ]
        if not normalized:
            return {}
        out: dict[tuple[str, str], str | None] = {key: None for key in normalized}
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return out
        try:
            if not _relation_exists(conn, READ_VIEW):
                return out
            requested_sql = " union all ".join("select ? as curve_type, ? as trade_date" for _ in normalized)
            params: list[object] = []
            for curve_type, trade_date in normalized:
                params.extend([curve_type, trade_date])
            rows = conn.execute(
                f"""
                with requested as (
                  {requested_sql}
                )
                select
                  r.curve_type,
                  r.trade_date,
                  max(cast(y.trade_date as varchar)) as prior_trade_date
                from requested r
                left join {READ_VIEW} y
                  on y.curve_type = r.curve_type
                 and cast(y.trade_date as varchar) < r.trade_date
                group by r.curve_type, r.trade_date
                """,
                params,
            ).fetchall()
            for curve_type, trade_date, prior_trade_date in rows:
                out[(str(curve_type), str(trade_date))] = (
                    str(prior_trade_date) if prior_trade_date not in (None, "") else None
                )
            return out
        finally:
            conn.close()

    def fetch_fx_rates(self, trade_date: str) -> dict[str, Decimal]:
        rates, _warning = self.fetch_fx_rates_with_fallback_warning(trade_date)
        return rates

    def fetch_fx_rates_with_fallback_warning(self, trade_date: str) -> tuple[dict[str, Decimal], str | None]:
        """Return FX map for ``trade_date``; emit a stable warning when LOCF-on-or-before is used."""
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return {}, None
        try:
            if not _relation_exists(conn, FX_TABLE):
                return {}, None
            rows = conn.execute(
                f"""
                select upper(base_currency) as base_currency, mid_rate
                from {FX_TABLE}
                where cast(trade_date as varchar) = ?
                  and upper(quote_currency) = 'CNY'
                order by upper(base_currency)
                """,
                [trade_date],
            ).fetchall()
            warning: str | None = None
            if not rows:
                latest_row = conn.execute(
                    f"""
                    select max(cast(trade_date as varchar))
                    from {FX_TABLE}
                    where cast(trade_date as varchar) <= ?
                      and upper(quote_currency) = 'CNY'
                    """,
                    [trade_date],
                ).fetchone()
                resolved_date = str(latest_row[0]) if latest_row and latest_row[0] is not None else None
                rows = conn.execute(
                    f"""
                    with ranked as (
                      select
                        upper(base_currency) as base_currency,
                        mid_rate,
                        row_number() over (
                          partition by upper(base_currency)
                          order by cast(trade_date as varchar) desc
                        ) as row_num
                      from {FX_TABLE}
                      where cast(trade_date as varchar) <= ?
                        and upper(quote_currency) = 'CNY'
                    )
                    select base_currency, mid_rate
                    from ranked
                    where row_num = 1
                    order by base_currency
                    """,
                    [trade_date],
                ).fetchall()
                if rows and resolved_date and resolved_date != trade_date:
                    warning = (
                        f"{FX_LATEST_FALLBACK_PREFIX}: Using latest available FX rates "
                        f"from trade_date={resolved_date} for requested_trade_date={trade_date}."
                    )
            return {
                str(base_currency): Decimal(str(mid_rate))
                for base_currency, mid_rate in rows
                if base_currency not in (None, "") and mid_rate is not None
            }, warning
        finally:
            conn.close()

    def fetch_curve_snapshot(self, trade_date: str, curve_type: str) -> dict[str, object] | None:
        """
        Snapshot-lineage read surface for one `(trade_date, curve_type)` grain in `fact_formal_yield_curve_daily`.

        Returns ``None`` when there is no snapshot, or when lineage fields disagree across tenors
        (data corruption). On success, the mapping includes:

        - ``trade_date``, ``curve_type``
        - ``curve``: tenor -> ``Decimal`` rate
        - ``vendor_name``, ``vendor_version``, ``source_version``, ``rule_version`` (uniform across tenors)
        """
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return None
        try:
            if not _relation_exists(conn, FORMAL_FACT_TABLE):
                return None
            rows = conn.execute(
                f"""
                select tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
                from {FORMAL_FACT_TABLE}
                where trade_date = ?
                  and curve_type = ?
                order by tenor
                """,
                [trade_date, curve_type],
            ).fetchall()
            if not rows:
                return None
            first = rows[0]
            vendor_name = str(first[2] or "")
            vendor_version = str(first[3] or "")
            source_version = str(first[4] or "")
            rule_version = str(first[5] or "")
            for row in rows[1:]:
                if (
                    str(row[2] or "") != vendor_name
                    or str(row[3] or "") != vendor_version
                    or str(row[4] or "") != source_version
                    or str(row[5] or "") != rule_version
                ):
                    return None
            curve = {
                str(tenor): Decimal(str(rate_pct))
                for tenor, rate_pct, _vn, _vv, _sv, _rv in rows
            }
            return {
                "trade_date": trade_date,
                "curve_type": curve_type,
                "curve": curve,
                "vendor_name": vendor_name,
                "vendor_version": vendor_version,
                "source_version": source_version,
                "rule_version": rule_version,
            }
        finally:
            conn.close()

    def fetch_curve_snapshots_many(
        self,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, object] | None]:
        normalized = [
            (str(trade_date).strip(), str(curve_type).strip())
            for trade_date, curve_type in dict.fromkeys(keys)
            if str(trade_date or "").strip() and str(curve_type or "").strip()
        ]
        if not normalized:
            return {}
        out: dict[tuple[str, str], dict[str, object] | None] = {key: None for key in normalized}
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return out
        try:
            if not _relation_exists(conn, FORMAL_FACT_TABLE):
                return out
            out.update(_fetch_curve_snapshots_on_connection_many(conn, normalized))
            return out
        finally:
            conn.close()

    def resolve_curve_snapshot(
        self,
        requested_trade_date: str,
        curve_type: str,
    ) -> tuple[dict[str, object] | None, str | None]:
        """
        Resolve exact-or-latest snapshot in one read connection.

        Preserves the public ``resolve_curve_snapshot`` semantics: exact match
        returns no warning, fallback emits the stable latest-curve warning, and
        formal lineage mismatches still raise instead of silently falling back.
        """
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}."
        try:
            if not _relation_exists(conn, READ_VIEW):
                return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}."
            if not _relation_exists(conn, FORMAL_FACT_TABLE):
                if _curve_rows_exist(conn, requested_trade_date, curve_type):
                    raise RuntimeError(
                        f"Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date={requested_trade_date}."
                    )
                return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}."

            resolved_trade_date = _latest_trade_date_on_or_before(
                conn,
                curve_type=curve_type,
                requested_trade_date=requested_trade_date,
            )
            if resolved_trade_date is None:
                return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}."

            snapshot = _fetch_curve_snapshot_on_connection(
                conn,
                trade_date=resolved_trade_date,
                curve_type=curve_type,
            )
            if snapshot is None:
                if _curve_rows_exist(conn, resolved_trade_date, curve_type):
                    raise RuntimeError(
                        f"Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date={resolved_trade_date}."
                    )
                return None, f"No {curve_type} curve available for requested trade_date={requested_trade_date}."

            if resolved_trade_date == requested_trade_date:
                return snapshot, None
            return (
                snapshot,
                format_yield_curve_latest_fallback_warning(
                    curve_type=curve_type,
                    resolved_trade_date=resolved_trade_date,
                    requested_trade_date=requested_trade_date,
                ),
            )
        finally:
            conn.close()

    def resolve_curve_snapshots_many(
        self,
        requests: list[tuple[str, str]],
    ) -> dict[tuple[str, str], tuple[dict[str, object] | None, str | None]]:
        normalized = [
            (str(trade_date).strip(), str(curve_type).strip())
            for trade_date, curve_type in dict.fromkeys(requests)
            if str(trade_date or "").strip() and str(curve_type or "").strip()
        ]
        if not normalized:
            return {}
        empty: dict[tuple[str, str], tuple[dict[str, object] | None, str | None]] = {
            key: (None, f"No {key[1]} curve available for requested trade_date={key[0]}.")
            for key in normalized
        }
        conn = _connect(self.path, read_only=True)
        if conn is None:
            return empty
        try:
            if not _relation_exists(conn, READ_VIEW):
                return empty
            if not _relation_exists(conn, FORMAL_FACT_TABLE):
                for requested_trade_date, curve_type in normalized:
                    if _curve_rows_exist(conn, requested_trade_date, curve_type):
                        raise RuntimeError(
                            f"Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date={requested_trade_date}."
                        )
                return empty

            resolved_dates = _latest_trade_dates_on_or_before_many(conn, normalized)
            snapshots = _fetch_curve_snapshots_on_connection_many(
                conn,
                [(resolved, curve_type) for resolved, curve_type in resolved_dates.values() if resolved],
            )
            out = dict(empty)
            for key in normalized:
                requested_trade_date, curve_type = key
                resolved_trade_date, _ = resolved_dates.get(key, (None, curve_type))
                if resolved_trade_date is None:
                    continue
                snapshot = snapshots.get((resolved_trade_date, curve_type))
                if snapshot is None:
                    if _curve_rows_exist(conn, resolved_trade_date, curve_type):
                        raise RuntimeError(
                            f"Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date={resolved_trade_date}."
                        )
                    continue
                if resolved_trade_date == requested_trade_date:
                    out[key] = (snapshot, None)
                else:
                    out[key] = (
                        snapshot,
                        format_yield_curve_latest_fallback_warning(
                            curve_type=curve_type,
                            resolved_trade_date=resolved_trade_date,
                            requested_trade_date=requested_trade_date,
                        ),
                    )
            return out
        finally:
            conn.close()

    def replace_curve_snapshots(self, *, trade_date: str, snapshots: list[YieldCurveSnapshot], rule_version: str) -> None:
        require_repository_task_write_scope("replace_curve_snapshots")
        conn = duckdb.connect(self.path, read_only=False)
        try:
            conn.execute("begin transaction")
            ensure_yield_curve_tables(conn)
            curve_types = sorted({snapshot.curve_type for snapshot in snapshots})
            if curve_types:
                conn.executemany(
                    f"delete from {FORMAL_FACT_TABLE} where trade_date = ? and curve_type = ?",
                    [(trade_date, curve_type) for curve_type in curve_types],
                )
            rows: list[tuple[object, ...]] = []
            for snapshot in snapshots:
                for point in snapshot.points:
                    rows.append(
                        (
                            snapshot.trade_date,
                            snapshot.curve_type,
                            point.tenor,
                            point.rate_pct,
                            snapshot.vendor_name,
                            snapshot.vendor_version,
                            snapshot.source_version,
                            rule_version,
                        )
                    )
            if rows:
                conn.executemany(
                    f"""
                    insert into {FORMAL_FACT_TABLE} (
                      trade_date,
                      curve_type,
                      tenor,
                      rate_pct,
                      vendor_name,
                      vendor_version,
                      source_version,
                      rule_version
                    ) values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()


def ensure_yield_curve_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


def _connect(path: str, *, read_only: bool) -> duckdb.DuckDBPyConnection | None:
    try:
        return duckdb.connect(path, read_only=read_only)
    except duckdb.Error:
        return None


def resolve_curve_snapshot(
    repo: YieldCurveRepository,
    *,
    requested_trade_date: str,
    curve_type: str,
) -> tuple[dict[str, object] | None, str | None]:
    """
    Exact ``fetch_curve_snapshot`` for ``(requested_trade_date, curve_type)``; otherwise LOCF-on-or-before
    via ``fetch_latest_trade_date_on_or_before`` with a stable warning. Raises if the view has points but
    formal lineage is inconsistent (same contract as credit spread analysis).
    """
    return repo.resolve_curve_snapshot(requested_trade_date, curve_type)


def _fetch_curve_snapshot_on_connection(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_date: str,
    curve_type: str,
) -> dict[str, object] | None:
    rows = conn.execute(
        f"""
        select tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
        from {FORMAL_FACT_TABLE}
        where trade_date = ?
          and curve_type = ?
        order by tenor
        """,
        [trade_date, curve_type],
    ).fetchall()
    if not rows:
        return None
    first = rows[0]
    vendor_name = str(first[2] or "")
    vendor_version = str(first[3] or "")
    source_version = str(first[4] or "")
    rule_version = str(first[5] or "")
    for row in rows[1:]:
        if (
            str(row[2] or "") != vendor_name
            or str(row[3] or "") != vendor_version
            or str(row[4] or "") != source_version
            or str(row[5] or "") != rule_version
        ):
            return None
    return {
        "trade_date": trade_date,
        "curve_type": curve_type,
        "curve": {
            str(tenor): Decimal(str(rate_pct))
            for tenor, rate_pct, _vn, _vv, _sv, _rv in rows
        },
        "vendor_name": vendor_name,
        "vendor_version": vendor_version,
        "source_version": source_version,
        "rule_version": rule_version,
    }


def _fetch_curve_snapshots_on_connection_many(
    conn: duckdb.DuckDBPyConnection,
    keys: list[tuple[str, str]],
) -> dict[tuple[str, str], dict[str, object] | None]:
    normalized = [
        (str(trade_date).strip(), str(curve_type).strip())
        for trade_date, curve_type in dict.fromkeys(keys)
        if str(trade_date or "").strip() and str(curve_type or "").strip()
    ]
    if not normalized:
        return {}
    requested_sql = " union all ".join("select ? as trade_date, ? as curve_type" for _ in normalized)
    params: list[object] = []
    for trade_date, curve_type in normalized:
        params.extend([trade_date, curve_type])
    rows = conn.execute(
        f"""
        with requested as (
          {requested_sql}
        )
        select
          cast(y.trade_date as varchar) as trade_date,
          y.curve_type,
          y.tenor,
          y.rate_pct,
          y.vendor_name,
          y.vendor_version,
          y.source_version,
          y.rule_version
        from {FORMAL_FACT_TABLE} y
        join requested r
          on cast(y.trade_date as varchar) = r.trade_date
         and y.curve_type = r.curve_type
        order by cast(y.trade_date as varchar), y.curve_type, y.tenor
        """,
        params,
    ).fetchall()
    grouped: dict[tuple[str, str], list[tuple[object, ...]]] = {key: [] for key in normalized}
    for trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version in rows:
        grouped.setdefault((str(trade_date), str(curve_type)), []).append(
            (tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version)
        )
    return {
        key: _curve_snapshot_from_rows(
            trade_date=key[0],
            curve_type=key[1],
            rows=value,
        )
        for key, value in grouped.items()
    }


def _curve_snapshot_from_rows(
    *,
    trade_date: str,
    curve_type: str,
    rows: list[tuple[object, ...]],
) -> dict[str, object] | None:
    if not rows:
        return None
    first = rows[0]
    vendor_name = str(first[2] or "")
    vendor_version = str(first[3] or "")
    source_version = str(first[4] or "")
    rule_version = str(first[5] or "")
    for row in rows[1:]:
        if (
            str(row[2] or "") != vendor_name
            or str(row[3] or "") != vendor_version
            or str(row[4] or "") != source_version
            or str(row[5] or "") != rule_version
        ):
            return None
    return {
        "trade_date": trade_date,
        "curve_type": curve_type,
        "curve": {
            str(tenor): Decimal(str(rate_pct))
            for tenor, rate_pct, _vn, _vv, _sv, _rv in rows
        },
        "vendor_name": vendor_name,
        "vendor_version": vendor_version,
        "source_version": source_version,
        "rule_version": rule_version,
    }


def _curve_rows_exist(
    conn: duckdb.DuckDBPyConnection,
    trade_date: str,
    curve_type: str,
) -> bool:
    if not _relation_exists(conn, READ_VIEW):
        return False
    row = conn.execute(
        f"""
        select 1
        from {READ_VIEW}
        where trade_date = ?
          and curve_type = ?
        limit 1
        """,
        [trade_date, curve_type],
    ).fetchone()
    return row is not None


def _latest_trade_date_on_or_before(
    conn: duckdb.DuckDBPyConnection,
    *,
    curve_type: str,
    requested_trade_date: str,
) -> str | None:
    row = conn.execute(
        f"""
        select max(cast(trade_date as varchar))
        from {READ_VIEW}
        where curve_type = ?
          and cast(trade_date as varchar) <= ?
        """,
        [curve_type, requested_trade_date],
    ).fetchone()
    if row is None or row[0] in (None, ""):
        return None
    return str(row[0])


def _latest_trade_dates_on_or_before_many(
    conn: duckdb.DuckDBPyConnection,
    requests: list[tuple[str, str]],
) -> dict[tuple[str, str], tuple[str | None, str]]:
    normalized = [
        (str(trade_date).strip(), str(curve_type).strip())
        for trade_date, curve_type in dict.fromkeys(requests)
        if str(trade_date or "").strip() and str(curve_type or "").strip()
    ]
    if not normalized:
        return {}
    requested_sql = " union all ".join("select ? as requested_trade_date, ? as curve_type" for _ in normalized)
    params: list[object] = []
    for trade_date, curve_type in normalized:
        params.extend([trade_date, curve_type])
    rows = conn.execute(
        f"""
        with requested as (
          {requested_sql}
        )
        select
          r.requested_trade_date,
          r.curve_type,
          max(cast(y.trade_date as varchar)) as resolved_trade_date
        from requested r
        left join {READ_VIEW} y
          on y.curve_type = r.curve_type
         and cast(y.trade_date as varchar) <= r.requested_trade_date
        group by r.requested_trade_date, r.curve_type
        """,
        params,
    ).fetchall()
    return {
        (str(requested_trade_date), str(curve_type)): (
            str(resolved_trade_date) if resolved_trade_date not in (None, "") else None,
            str(curve_type),
        )
        for requested_trade_date, curve_type, resolved_trade_date in rows
    }


def _relation_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        union all
        select 1
        from information_schema.views
        where table_name = ?
        limit 1
        """,
        [relation_name, relation_name],
    ).fetchone()
    return row is not None
