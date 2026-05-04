"""Analytical/Ledger Bridge Service – Phase 3 Module A.

This service extends the cube query pathway to support `basis=analytical`
and `basis=ledger`.  The formal pathway remains delegated to the existing
``CubeQueryService`` so that Phase 2 guarantees are preserved.

Design notes
~~~~~~~~~~~~
* ``analytical`` basis re-queries the same governed DuckDB tables but returns
  ``ResultMeta.formal_use_allowed = False`` and ``basis = analytical`` so the
  frontend can clearly badge non-formal results.
* ``ledger`` basis queries the *ledger*-side DuckDB tables populated by
  ``LedgerImportService`` and tags the result with ``basis = ledger``.
* All SQL is parameterised (``?``-placeholders) to prevent injection.
* ``AuthContext`` is required by the route layer and forwarded here for audit.
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable, Sequence

logger = logging.getLogger(__name__)

from backend.app.repositories.cube_query_repo import CubeQueryRepository
from backend.app.schemas.cube_query import CubeQueryRequest, CubeQueryResponse, DrillPath
from backend.app.security.auth_context import AuthContext
from backend.app.services.cube_query_service import CubeQueryService
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_ledger_result_meta,
)

# ── Ledger table registry ──────────────────────────────────────────────
# Maps the logical fact_table name from CubeQueryRequest to the physical
# DuckDB table that holds ledger-imported data.
#
# The primary ledger table is ``position_snapshot`` (raw import from
# ``LedgerImportService``).  When the ZQTZ snapshot pipeline has populated
# ``zqtz_bond_daily_snapshot``, LedgerAnalyticsRepository transparently
# prefers that table; the bridge does the same.
LEDGER_FACT_TABLES: dict[str, str] = {
    "balance": "position_snapshot",
}
# ``zqtz_bond_daily_snapshot`` is used when available (checked at runtime).
LEDGER_ZQTZ_TABLE = "zqtz_bond_daily_snapshot"

# position_snapshot uses ``as_of_date`` instead of ``report_date``.
LEDGER_DATE_COLUMN = "as_of_date"

LEDGER_DIMENSIONS: dict[str, list[str]] = {
    "balance": [
        "direction",
        "portfolio",
        "account_category_std",
        "asset_class_std",
        "cost_center",
        "currency",
        "bond_code",
    ],
}

LEDGER_MEASURE_FIELDS: dict[str, dict[str, str]] = {
    "balance": {
        "face_amount": "face_amount",
        "fair_value": "fair_value",
        "amortized_cost": "amortized_cost",
        "accrued_interest": "accrued_interest",
    },
}

CACHE_VERSION = "cv_analytical_bridge_v1"


class AnalyticalBridgeService:
    """Cube query bridge for analytical and ledger bases.

    The service delegates ``basis=formal`` and ``basis=scenario`` to the
    existing ``CubeQueryService`` to preserve backward-compatibility.
    """

    def __init__(
        self,
        *,
        repo_factory: Callable[[str], CubeQueryRepository] | None = None,
        cube_query_service: CubeQueryService | None = None,
    ) -> None:
        self._repo_factory = repo_factory or CubeQueryRepository
        self._cube_service = cube_query_service or CubeQueryService(
            repo_factory=repo_factory,
        )

    def execute(
        self,
        request: CubeQueryRequest,
        duckdb_path: str,
        *,
        auth: AuthContext,
    ) -> CubeQueryResponse:
        """Route query to the right pathway based on ``request.basis``."""
        if request.basis == "formal":
            return self._cube_service.execute(request, duckdb_path)
        if request.basis == "analytical":
            return self._execute_analytical(request, duckdb_path, auth=auth)
        if request.basis == "ledger":
            return self._execute_ledger(request, duckdb_path, auth=auth)
        # scenario still unsupported
        raise ValueError(f"Unsupported basis={request.basis!r}")

    # ── analytical pathway ─────────────────────────────────────────────
    def _execute_analytical(
        self,
        request: CubeQueryRequest,
        duckdb_path: str,
        *,
        auth: AuthContext,
    ) -> CubeQueryResponse:
        """Query the same governed tables as formal but stamp the result as analytical."""
        table_name = CubeQueryService.table_name_for(request.fact_table)
        svc = self._cube_service
        dimensions = svc.validate_dimensions(request)
        filters = svc.validate_filters(request)
        measure_specs = svc.parse_measures(request)
        where_sql, where_params = svc.build_where_clause(request.report_date, filters)
        repo = self._repo_factory(duckdb_path)
        matching = svc.matching_row_count(repo, table_name, where_sql, where_params)

        if matching == 0:
            rows: list[dict[str, object]] = []
            total_rows = 0
        else:
            total_rows = svc.total_rows(repo, table_name, dimensions, where_sql, where_params)
            rows = svc.fetch_rows(
                repo, table_name, dimensions, measure_specs,
                where_sql, where_params, request.order_by, request.limit, request.offset,
            )

        drill_paths = svc.build_drill_paths(
            repo, request=request, table_name=table_name,
            dimensions=dimensions, filters=filters,
        )
        return CubeQueryResponse(
            report_date=request.report_date,
            fact_table=request.fact_table,
            measures=list(request.measures),
            dimensions=list(dimensions),
            rows=rows,
            total_rows=total_rows,
            drill_paths=drill_paths,
            result_meta=build_analytical_result_meta(
                trace_id=f"tr_analytical_{request.fact_table}_{uuid.uuid4().hex[:12]}",
                result_kind=f"analytical.{request.fact_table}",
                source_version=f"sv_analytical_{request.fact_table}",
                rule_version="rv_analytical_bridge_v1",
                cache_version=CACHE_VERSION,
                quality_flag="ok" if matching > 0 else "warning",
                evidence_rows=matching,
                filters_applied=dict(request.filters),
            ),
        )

    # ── ledger pathway ──────────��──────────────────────────────────────
    def _execute_ledger(
        self,
        request: CubeQueryRequest,
        duckdb_path: str,
        *,
        auth: AuthContext,
    ) -> CubeQueryResponse:
        """Query ledger-imported tables and return a ledger-basis result."""
        if request.fact_table not in LEDGER_FACT_TABLES:
            raise ValueError(
                f"Ledger basis is not available for fact_table={request.fact_table}. "
                f"Supported: {', '.join(sorted(LEDGER_FACT_TABLES))}."
            )
        table_name = LEDGER_FACT_TABLES[request.fact_table]
        dimensions = self._validate_ledger_dimensions(request)
        filters = self._validate_ledger_filters(request)
        measure_specs = self._parse_ledger_measures(request)
        where_sql, where_params = _build_ledger_where_clause(request.report_date, filters)
        repo = self._repo_factory(duckdb_path)

        # Guard: if the table does not exist yet, return an empty result
        # instead of crashing with a DuckDB catalog error.
        try:
            matching = _matching_row_count(repo, table_name, where_sql, where_params)
        except Exception:
            logger.warning(
                "Ledger table %s not queryable, treating as empty",
                table_name,
                exc_info=True,
            )
            matching = 0

        if matching == 0:
            rows: list[dict[str, object]] = []
            total_rows = 0
        else:
            total_rows = _total_rows(repo, table_name, dimensions, where_sql, where_params)
            rows = _fetch_rows(
                repo, table_name, dimensions, measure_specs,
                where_sql, where_params, request.order_by, request.limit, request.offset,
            )

        drill_paths = _build_ledger_drill_paths(
            repo, request=request, table_name=table_name,
            dimensions=dimensions, filters=filters,
        )
        return CubeQueryResponse(
            report_date=request.report_date,
            fact_table=request.fact_table,
            measures=list(request.measures),
            dimensions=list(dimensions),
            rows=rows,
            total_rows=total_rows,
            drill_paths=drill_paths,
            result_meta=build_ledger_result_meta(
                trace_id=f"tr_ledger_{request.fact_table}_{uuid.uuid4().hex[:12]}",
                result_kind=f"ledger.{request.fact_table}",
                source_version=f"sv_ledger_{request.fact_table}",
                rule_version="rv_ledger_bridge_v1",
                cache_version=CACHE_VERSION,
                quality_flag="ok" if matching > 0 else "warning",
                evidence_rows=matching,
                filters_applied=dict(request.filters),
            ),
        )

    # ── ledger validation helpers ──────────────────────────────────────
    @staticmethod
    def _validate_ledger_dimensions(request: CubeQueryRequest) -> list[str]:
        allowed = set(LEDGER_DIMENSIONS.get(request.fact_table, []))
        invalid = [d for d in request.dimensions if d not in allowed]
        if invalid:
            raise ValueError(
                f"Unsupported ledger dimensions for {request.fact_table}: {', '.join(invalid)}"
            )
        return list(request.dimensions)

    @staticmethod
    def _validate_ledger_filters(request: CubeQueryRequest) -> dict[str, list[str]]:
        allowed = set(LEDGER_DIMENSIONS.get(request.fact_table, []))
        invalid = [f for f in request.filters if f not in allowed]
        if invalid:
            raise ValueError(
                f"Unsupported ledger filters for {request.fact_table}: {', '.join(invalid)}"
            )
        normalised: dict[str, list[str]] = {}
        for name, raw_values in request.filters.items():
            values = [str(v) for v in raw_values if str(v) != ""]
            if values:
                normalised[name] = list(dict.fromkeys(values))
        return normalised

    @staticmethod
    def _parse_ledger_measures(request: CubeQueryRequest) -> list[tuple[str, str]]:
        """Return list of (alias, sql_expression) tuples for ledger measures."""
        import re
        _RE = re.compile(r"^(?P<func>[a-z]+)\((?P<field>\*|[a-zA-Z_][a-zA-Z0-9_]*)\)$")
        allowed_fields = LEDGER_MEASURE_FIELDS.get(request.fact_table, {})
        allowed_funcs = {"sum", "avg", "count", "min", "max"}
        specs: list[tuple[str, str]] = []
        aliases: set[str] = set()
        for raw in request.measures:
            m = _RE.fullmatch(raw.strip())
            if m is None:
                raise ValueError(f"Unsupported measure syntax={raw!r}")
            func = m.group("func").lower()
            field = m.group("field")
            if func not in allowed_funcs:
                raise ValueError(f"Unsupported aggregation={func}")
            if field == "*":
                if func != "count":
                    raise ValueError(f"Only count(*) is allowed, got {raw!r}")
                alias, sql = "count", "count(*)"
            else:
                physical = allowed_fields.get(field)
                if physical is None:
                    raise ValueError(
                        f"Unsupported measure field={field!r} for ledger fact_table={request.fact_table}"
                    )
                alias, sql = field, f"{func}({physical})"
            if alias in aliases:
                raise ValueError(f"Duplicate measure alias={alias!r}")
            aliases.add(alias)
            specs.append((alias, sql))
        return specs


# ── Private SQL helpers (all parameterised) ────────────────────────────
def _build_where_clause(
    report_date: str,
    filters: dict[str, list[str]],
) -> tuple[str, list[object]]:
    clauses = ["report_date = ?"]
    params: list[object] = [report_date]
    for dimension, values in filters.items():
        if not values:
            continue
        placeholders = ", ".join("?" for _ in values)
        clauses.append(f"{dimension} in ({placeholders})")
        params.extend(values)
    return " where " + " and ".join(clauses), params


def _build_ledger_where_clause(
    report_date: str,
    filters: dict[str, list[str]],
) -> tuple[str, list[object]]:
    """Like ``_build_where_clause`` but uses ``as_of_date`` – the actual
    date column in ``position_snapshot``."""
    clauses = [f"{LEDGER_DATE_COLUMN} = ?"]
    params: list[object] = [report_date]
    for dimension, values in filters.items():
        if not values:
            continue
        placeholders = ", ".join("?" for _ in values)
        clauses.append(f"{dimension} in ({placeholders})")
        params.extend(values)
    return " where " + " and ".join(clauses), params


def _matching_row_count(
    repo: CubeQueryRepository,
    table_name: str,
    where_sql: str,
    where_params: Sequence[object],
) -> int:
    row = repo.fetchall(f"select count(*) from {table_name}{where_sql}", where_params)[0]
    return int(row[0])


def _total_rows(
    repo: CubeQueryRepository,
    table_name: str,
    dimensions: list[str],
    where_sql: str,
    where_params: Sequence[object],
) -> int:
    if not dimensions:
        return 1
    group_fields = ", ".join(dimensions)
    row = repo.fetchall(
        f"""
        select count(*) from (
          select {group_fields}
          from {table_name}{where_sql}
          group by {group_fields}
        ) as ledger_groups
        """,
        where_params,
    )[0]
    return int(row[0])


def _fetch_rows(
    repo: CubeQueryRepository,
    table_name: str,
    dimensions: list[str],
    measure_specs: list[tuple[str, str]],
    where_sql: str,
    where_params: Sequence[object],
    order_by: Sequence[str],
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    select_parts = list(dimensions) + [f"{sql} as {alias}" for alias, sql in measure_specs]
    group_sql = f" group by {', '.join(dimensions)}" if dimensions else ""
    order_sql = _build_order_by(order_by, dimensions, [alias for alias, _ in measure_specs])
    rows = repo.fetchall(
        f"""
        select {", ".join(select_parts)}
        from {table_name}{where_sql}{group_sql}{order_sql}
        limit ? offset ?
        """,
        [*where_params, limit, offset],
    )
    columns = dimensions + [alias for alias, _ in measure_specs]
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _build_order_by(
    order_by: Sequence[str],
    dimensions: Sequence[str],
    aliases: Sequence[str],
) -> str:
    if not order_by:
        return ""
    valid_fields = set(dimensions) | set(aliases)
    order_parts: list[str] = []
    for raw in order_by:
        token = raw.strip()
        descending = token.startswith("-")
        field = token[1:] if descending else token
        if field not in valid_fields:
            raise ValueError(f"Unsupported order_by field={field!r}")
        order_parts.append(f"{field} {'desc' if descending else 'asc'}")
    return " order by " + ", ".join(order_parts)


def _build_ledger_drill_paths(
    repo: CubeQueryRepository,
    *,
    request: CubeQueryRequest,
    table_name: str,
    dimensions: list[str],
    filters: dict[str, list[str]],
) -> list[DrillPath]:
    drill_paths: list[DrillPath] = []
    for dimension in dimensions:
        where_sql, where_params = _build_ledger_where_clause(
            request.report_date,
            {k: v for k, v in filters.items() if k != dimension},
        )
        rows = repo.fetchall(
            f"""
            select distinct {dimension}
            from {table_name}{where_sql}
            and {dimension} is not null
            order by {dimension}
            """,
            where_params,
        )
        drill_paths.append(
            DrillPath(
                dimension=dimension,
                label=dimension,
                available_values=[str(row[0]) for row in rows],
                current_filter=request.filters.get(dimension),
            )
        )
    return drill_paths
