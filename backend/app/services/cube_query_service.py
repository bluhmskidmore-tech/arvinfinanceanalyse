from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Sequence

from backend.app.repositories.cube_query_repo import CubeQueryRepository
from backend.app.schemas.cube_query import CubeQueryRequest, CubeQueryResponse, DrillPath
from backend.app.services.formal_result_runtime import build_formal_result_meta


_MEASURE_RE = re.compile(r"^(?P<func>[a-z]+)\((?P<field>\*|[a-zA-Z_][a-zA-Z0-9_]*)\)$")


@dataclass(frozen=True)
class _MeasureSpec:
    alias: str
    sql: str


class CubeQueryService:
    ALLOWED_FACT_TABLES = {
        "bond_analytics": "fact_formal_bond_analytics_daily",
        "pnl": "fact_formal_pnl_fi",
        "balance": "fact_formal_zqtz_balance_daily",
        "product_category": "product_category_pnl_formal_read_model",
    }
    ORDERED_MEASURES = ["sum", "avg", "count", "min", "max"]
    ALLOWED_MEASURES = set(ORDERED_MEASURES)
    ALLOWED_DIMENSIONS = {
        "bond_analytics": [
            "asset_class_std",
            "accounting_class",
            "tenor_bucket",
            "rating",
            "bond_type",
            "issuer_name",
            "industry_name",
            "portfolio_name",
            "cost_center",
        ],
        "pnl": ["invest_type_std", "accounting_basis", "portfolio_name", "cost_center"],
        "balance": [
            "asset_class",
            "invest_type_std",
            "accounting_basis",
            "position_scope",
            "bond_type",
            "rating",
        ],
        "product_category": ["category_id", "category_name", "side", "view"],
    }
    ALLOWED_MEASURE_FIELDS = {
        "bond_analytics": {"market_value": "market_value", "duration": "modified_duration"},
        "pnl": {"total_pnl": "total_pnl"},
        "balance": {
            "market_value": "market_value_amount",
            "amortized_cost": "amortized_cost_amount",
            "accrued_interest": "accrued_interest_amount",
        },
        "product_category": {"business_net_income": "business_net_income"},
    }
    CACHE_VERSIONS = {
        "bond_analytics": "cv_cube_query_bond_analytics_v1",
        "pnl": "cv_cube_query_pnl_v1",
        "balance": "cv_cube_query_balance_v1",
        "product_category": "cv_cube_query_product_category_v1",
    }
    DEFAULT_SOURCE_VERSIONS = {
        "bond_analytics": "sv_cube_bond_analytics_empty",
        "pnl": "sv_cube_pnl_empty",
        "balance": "sv_cube_balance_empty",
        "product_category": "sv_cube_product_category_empty",
    }

    def __init__(
        self,
        *,
        repo_factory: Callable[[str], CubeQueryRepository] | None = None,
    ) -> None:
        self._repo_factory = repo_factory or CubeQueryRepository

    @classmethod
    def table_name_for(cls, fact_table: str) -> str:
        try:
            return cls.ALLOWED_FACT_TABLES[fact_table]
        except KeyError as exc:
            raise ValueError(f"Unsupported fact_table={fact_table}") from exc

    @classmethod
    def describe_fact_table(cls, fact_table: str) -> dict[str, object]:
        if fact_table not in cls.ALLOWED_FACT_TABLES:
            raise ValueError(f"Unsupported fact_table={fact_table}")
        return {
            "fact_table": fact_table,
            "dimensions": list(cls.ALLOWED_DIMENSIONS[fact_table]),
            "measures": list(cls.ORDERED_MEASURES),
            "measure_fields": list(cls.ALLOWED_MEASURE_FIELDS[fact_table]),
        }

    def execute(self, request: CubeQueryRequest, duckdb_path: str) -> CubeQueryResponse:
        if request.basis != "formal":
            raise ValueError("Cube query currently supports basis=formal only.")

        table_name = self.table_name_for(request.fact_table)
        dimensions = self._validate_dimensions(request)
        filters = self._validate_filters(request)
        measure_specs = self._parse_measures(request)
        where_sql, where_params = self._build_where_clause(request.report_date, filters)
        repo = self._repo_factory(duckdb_path)
        matching_row_count = self._matching_row_count(repo, table_name, where_sql, where_params)

        if matching_row_count == 0:
            rows: list[dict[str, object]] = []
            total_rows = 0
        else:
            total_rows = self._total_rows(repo, table_name, dimensions, where_sql, where_params)
            rows = self._fetch_rows(
                repo,
                table_name,
                dimensions,
                measure_specs,
                where_sql,
                where_params,
                request.order_by,
                request.limit,
                request.offset,
            )

        source_version, rule_version = self._fetch_lineage(
            repo,
            fact_table=request.fact_table,
            table_name=table_name,
            where_sql=where_sql,
            where_params=where_params,
            has_rows=matching_row_count > 0,
        )
        drill_paths = self._build_drill_paths(
            repo,
            request=request,
            table_name=table_name,
            dimensions=dimensions,
            filters=filters,
        )
        return CubeQueryResponse(
            report_date=request.report_date,
            fact_table=request.fact_table,
            measures=list(request.measures),
            dimensions=list(dimensions),
            rows=rows,
            total_rows=total_rows,
            drill_paths=drill_paths,
            result_meta=build_formal_result_meta(
                trace_id=f"tr_cube_query_{uuid.uuid4().hex[:12]}",
                result_kind=f"cube_query.{request.fact_table}",
                source_version=source_version,
                rule_version=rule_version,
                cache_version=self.CACHE_VERSIONS[request.fact_table],
                quality_flag="ok" if matching_row_count > 0 else "warning",
            ),
        )

    def _validate_dimensions(self, request: CubeQueryRequest) -> list[str]:
        allowed_dimensions = set(self.ALLOWED_DIMENSIONS[request.fact_table])
        invalid_dimensions = [dimension for dimension in request.dimensions if dimension not in allowed_dimensions]
        if invalid_dimensions:
            raise ValueError(
                "Unsupported dimensions for "
                f"{request.fact_table}: {', '.join(invalid_dimensions)}"
            )
        return list(request.dimensions)

    def _validate_filters(self, request: CubeQueryRequest) -> dict[str, list[str]]:
        allowed_dimensions = set(self.ALLOWED_DIMENSIONS[request.fact_table])
        invalid_filters = [name for name in request.filters if name not in allowed_dimensions]
        if invalid_filters:
            raise ValueError(
                "Unsupported filters for "
                f"{request.fact_table}: {', '.join(invalid_filters)}"
            )
        normalized: dict[str, list[str]] = {}
        for name, raw_values in request.filters.items():
            values = [str(value) for value in raw_values if str(value) != ""]
            if values:
                normalized[name] = list(dict.fromkeys(values))
        return normalized

    def _parse_measures(self, request: CubeQueryRequest) -> list[_MeasureSpec]:
        allowed_fields = self.ALLOWED_MEASURE_FIELDS[request.fact_table]
        aliases: set[str] = set()
        specs: list[_MeasureSpec] = []
        for raw_measure in request.measures:
            match = _MEASURE_RE.fullmatch(raw_measure.strip())
            if match is None:
                raise ValueError(f"Unsupported measure syntax={raw_measure!r}")
            func = match.group("func").lower()
            field = match.group("field")
            if func not in self.ALLOWED_MEASURES:
                raise ValueError(f"Unsupported aggregation={func}")
            if field == "*":
                if func != "count":
                    raise ValueError(f"Only count(*) is allowed, got {raw_measure!r}")
                alias = "count"
                sql = "count(*)"
            else:
                physical_field = allowed_fields.get(field)
                if physical_field is None:
                    raise ValueError(
                        f"Unsupported measure field={field!r} for fact_table={request.fact_table}"
                    )
                alias = field
                sql = f"{func}({physical_field})"
            if alias in aliases:
                raise ValueError(f"Duplicate measure alias={alias!r}")
            aliases.add(alias)
            specs.append(_MeasureSpec(alias=alias, sql=sql))
        return specs

    def _build_where_clause(
        self,
        report_date: str,
        filters: dict[str, list[str]],
        *,
        skip_dimension: str | None = None,
    ) -> tuple[str, list[object]]:
        clauses = ["report_date = ?"]
        params: list[object] = [report_date]
        for dimension, values in filters.items():
            if dimension == skip_dimension or not values:
                continue
            placeholders = ", ".join("?" for _ in values)
            clauses.append(f"{dimension} in ({placeholders})")
            params.extend(values)
        return " where " + " and ".join(clauses), params

    def _matching_row_count(
        self,
        repo: CubeQueryRepository,
        table_name: str,
        where_sql: str,
        where_params: Sequence[object],
    ) -> int:
        row = repo.fetchall(f"select count(*) from {table_name}{where_sql}", where_params)[0]
        return int(row[0])

    def _total_rows(
        self,
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
            ) as cube_groups
            """,
            where_params,
        )[0]
        return int(row[0])

    def _fetch_rows(
        self,
        repo: CubeQueryRepository,
        table_name: str,
        dimensions: list[str],
        measure_specs: list[_MeasureSpec],
        where_sql: str,
        where_params: Sequence[object],
        order_by: Sequence[str],
        limit: int,
        offset: int,
    ) -> list[dict[str, object]]:
        select_parts = list(dimensions) + [f"{spec.sql} as {spec.alias}" for spec in measure_specs]
        group_sql = f" group by {', '.join(dimensions)}" if dimensions else ""
        order_sql = self._build_order_by(order_by, dimensions, measure_specs)
        rows = repo.fetchall(
            f"""
            select {", ".join(select_parts)}
            from {table_name}{where_sql}{group_sql}{order_sql}
            limit ? offset ?
            """,
            [*where_params, limit, offset],
        )
        columns = dimensions + [spec.alias for spec in measure_specs]
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _build_order_by(
        self,
        order_by: Sequence[str],
        dimensions: Sequence[str],
        measure_specs: Sequence[_MeasureSpec],
    ) -> str:
        if not order_by:
            return ""
        valid_fields = set(dimensions) | {spec.alias for spec in measure_specs}
        order_parts: list[str] = []
        for raw_token in order_by:
            token = raw_token.strip()
            descending = token.startswith("-")
            field = token[1:] if descending else token
            if field not in valid_fields:
                raise ValueError(f"Unsupported order_by field={field!r}")
            order_parts.append(f"{field} {'desc' if descending else 'asc'}")
        return " order by " + ", ".join(order_parts)

    def _build_drill_paths(
        self,
        repo: CubeQueryRepository,
        *,
        request: CubeQueryRequest,
        table_name: str,
        dimensions: list[str],
        filters: dict[str, list[str]],
    ) -> list[DrillPath]:
        drill_paths: list[DrillPath] = []
        for dimension in dimensions:
            where_sql, where_params = self._build_where_clause(
                request.report_date,
                filters,
                skip_dimension=dimension,
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

    def _fetch_lineage(
        self,
        repo: CubeQueryRepository,
        *,
        fact_table: str,
        table_name: str,
        where_sql: str,
        where_params: Sequence[object],
        has_rows: bool,
    ) -> tuple[str, str]:
        if not has_rows:
            return self.DEFAULT_SOURCE_VERSIONS[fact_table], "rv_cube_query_v1"
        source_rows = repo.fetchall(
            f"""
            select distinct source_version
            from {table_name}{where_sql}
            and source_version is not null
            and source_version <> ''
            order by source_version
            """,
            where_params,
        )
        rule_rows = repo.fetchall(
            f"""
            select distinct rule_version
            from {table_name}{where_sql}
            and rule_version is not null
            and rule_version <> ''
            order by rule_version
            """,
            where_params,
        )
        source_version = "__".join(str(row[0]) for row in source_rows) or self.DEFAULT_SOURCE_VERSIONS[fact_table]
        rule_version = "__".join(str(row[0]) for row in rule_rows) or "rv_cube_query_v1"
        return source_version, rule_version
