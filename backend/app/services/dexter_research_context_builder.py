from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from backend.app.agent.schemas.agent_request import AgentQueryRequest

DEFAULT_MACRO_SERIES_IDS = (
    "legacy.yield.choice.treasury.10Y",
    "tushare.macro.cn_cpi.monthly",
    "tushare.macro.cn_ppi.monthly",
    "tushare.macro.cn_money.monthly",
)


class ResearchContextBuilder:
    def __init__(self, *, duckdb_path: str) -> None:
        self._duckdb_path = duckdb_path

    def build(self, request: AgentQueryRequest) -> dict[str, Any]:
        domain = _resolve_research_domain(request)
        context = _base_context(request=request, domain=domain)
        if domain is None:
            return context

        db_path = Path(str(self._duckdb_path or ""))
        if not db_path.exists():
            context["quality_flag"] = "missing"
            context["limitations"].append(
                "DuckDB database is not available; use the manual refresh path before Dexter research."
            )
            return context

        try:
            conn = duckdb.connect(str(db_path), read_only=True)
        except duckdb.Error as exc:
            context["quality_flag"] = "missing"
            context["limitations"].append(f"DuckDB database could not be opened read-only: {exc}")
            return context

        try:
            tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
            if domain == "stock":
                _build_stock_context(conn=conn, tables=tables, context=context)
            elif domain == "macro":
                _build_macro_context(conn=conn, tables=tables, context=context)
        finally:
            conn.close()

        if context["evidence_rows"] <= 0 and context["quality_flag"] == "ok":
            context["quality_flag"] = "missing"
            context["limitations"].append("No landed Choice/TuShare research rows matched the request.")
        elif context["limitations"] and context["quality_flag"] == "ok":
            context["quality_flag"] = "warning"
        return context


def build_dexter_research_context(
    *,
    request: AgentQueryRequest,
    duckdb_path: str,
) -> dict[str, Any]:
    return ResearchContextBuilder(duckdb_path=duckdb_path).build(request)


def _base_context(*, request: AgentQueryRequest, domain: str | None) -> dict[str, Any]:
    filters_applied = _non_empty_dict(request.filters)
    as_of_date = _resolve_as_of_date(request)
    stock_code = _resolve_stock_code(request)
    if as_of_date:
        filters_applied["as_of_date"] = as_of_date
    if stock_code:
        filters_applied["stock_code"] = stock_code
    if domain:
        filters_applied["research_domain"] = domain

    return {
        "domain": domain,
        "as_of_date": as_of_date,
        "tables_used": [],
        "filters_applied": filters_applied,
        "evidence_rows": 0,
        "quality_flag": "ok",
        "limitations": [],
        "stock": {},
        "macro": {},
    }


def _build_stock_context(
    *,
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    context: dict[str, Any],
) -> None:
    stock_code = str(context["filters_applied"].get("stock_code") or "").strip().upper()
    as_of_date = str(context.get("as_of_date") or "").strip()
    if not stock_code:
        context["limitations"].append("Stock research requires stock_code from filters or selected_rows.")
        return

    stock: dict[str, Any] = {}
    if "choice_stock_daily_observation" in tables:
        context["tables_used"].append("choice_stock_daily_observation")
        row = _fetch_one(
            conn,
            """
            select trade_date, stock_code, open_value, high_value, low_value, close_value,
                   volume, amount, pctchange, turn, amplitude, tradestatus,
                   highlimit, lowlimit, source_version, vendor_version, rule_version, run_id
            from choice_stock_daily_observation
            where stock_code = ?
              and (? = '' or trade_date <= ?)
            order by trade_date desc
            limit 1
            """,
            [stock_code, as_of_date, as_of_date],
        )
        if row:
            stock["daily_observation"] = row
            context["evidence_rows"] += 1
        else:
            context["limitations"].append(f"No Choice stock daily observation matched {stock_code}.")
    else:
        context["limitations"].append("choice_stock_daily_observation is not landed.")

    if "choice_stock_factor_snapshot" in tables:
        context["tables_used"].append("choice_stock_factor_snapshot")
        row = _fetch_one(
            conn,
            """
            select as_of_date, stock_code, pe, pb, ps, roe, gross_margin,
                   three_month_return, twelve_month_return, volatility, dividend_yield,
                   industry, source_version, vendor_version, rule_version, run_id
            from choice_stock_factor_snapshot
            where stock_code = ?
              and (? = '' or as_of_date <= ?)
            order by as_of_date desc
            limit 1
            """,
            [stock_code, as_of_date, as_of_date],
        )
        if row:
            stock["factor_snapshot"] = row
            context["evidence_rows"] += 1
        else:
            context["limitations"].append(f"No Choice stock factor snapshot matched {stock_code}.")
    else:
        context["limitations"].append("choice_stock_factor_snapshot is not landed.")

    if "choice_stock_sector_membership" in tables:
        context["tables_used"].append("choice_stock_sector_membership")
        row = _fetch_one(
            conn,
            """
            select as_of_date, stock_code, sw2021, sw2021code, field_key,
                   source_version, vendor_version, rule_version, run_id
            from choice_stock_sector_membership
            where stock_code = ?
              and (? = '' or as_of_date <= ?)
            order by as_of_date desc
            limit 1
            """,
            [stock_code, as_of_date, as_of_date],
        )
        if row:
            stock["sector_membership"] = row
            context["evidence_rows"] += 1
        else:
            context["limitations"].append(f"No Choice stock sector membership matched {stock_code}.")
    else:
        context["limitations"].append("choice_stock_sector_membership is not landed.")

    if "choice_news_event" in tables:
        context["tables_used"].append("choice_news_event")
        rows = _fetch_all(
            conn,
            """
            select event_key, received_at, group_id, content_type, topic_code,
                   item_index, payload_text, payload_json, error_code, error_msg
            from choice_news_event
            where topic_code = ?
               or payload_text ilike ?
            order by received_at desc, item_index asc
            limit 5
            """,
            [stock_code, f"%{stock_code}%"],
        )
        stock["news_events"] = rows
        context["evidence_rows"] += len(rows)
        if not rows:
            context["limitations"].append(f"No Choice/TuShare news event matched {stock_code}.")
    else:
        context["limitations"].append("choice_news_event is not landed.")

    context["stock"] = stock


def _build_macro_context(
    *,
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    context: dict[str, Any],
) -> None:
    series_ids = _resolve_macro_series_ids(context["filters_applied"])
    as_of_date = str(context.get("as_of_date") or "").strip()
    macro: dict[str, Any] = {"series_ids": series_ids}

    if "fact_choice_macro_daily" in tables:
        context["tables_used"].append("fact_choice_macro_daily")
        rows = _latest_rows_by_series(
            conn=conn,
            table_name="fact_choice_macro_daily",
            select_columns=(
                "series_id",
                "series_name",
                "trade_date",
                "value_numeric",
                "frequency",
                "unit",
                "source_version",
                "vendor_version",
                "rule_version",
                "quality_flag",
                "run_id",
            ),
            series_ids=series_ids,
            as_of_date=as_of_date,
        )
        macro["choice_series"] = rows
        context["evidence_rows"] += len(rows)
    else:
        context["limitations"].append("fact_choice_macro_daily is not landed.")

    if "choice_market_snapshot" in tables:
        context["tables_used"].append("choice_market_snapshot")
        rows = _latest_rows_by_series(
            conn=conn,
            table_name="choice_market_snapshot",
            select_columns=(
                "series_id",
                "series_name",
                "trade_date",
                "value_numeric",
                "frequency",
                "unit",
                "source_version",
                "vendor_version",
                "rule_version",
                "run_id",
            ),
            series_ids=series_ids,
            as_of_date=as_of_date,
        )
        macro["choice_snapshots"] = rows
        context["evidence_rows"] += len(rows)
    else:
        context["limitations"].append("choice_market_snapshot is not landed.")

    if "phase1_macro_vendor_catalog" in tables:
        context["tables_used"].append("phase1_macro_vendor_catalog")
        macro["catalog"] = _fetch_macro_catalog(conn=conn, series_ids=series_ids)
        context["evidence_rows"] += len(macro["catalog"])
    else:
        context["limitations"].append("phase1_macro_vendor_catalog is not landed.")

    if "vw_external_macro_daily" in tables:
        context["tables_used"].append("vw_external_macro_daily")
        macro["tushare_series"] = _latest_rows_by_series(
            conn=conn,
            table_name="vw_external_macro_daily",
            select_columns=(
                "series_id",
                "vendor_name",
                "domain",
                "trade_date",
                "value_numeric",
                "frequency",
                "unit",
                "source_version",
                "vendor_version",
                "rule_version",
                "ingest_batch_id",
                "raw_zone_path",
            ),
            series_ids=series_ids,
            as_of_date=as_of_date,
        )
        context["evidence_rows"] += len(macro["tushare_series"])
    else:
        context["limitations"].append("vw_external_macro_daily is not landed.")

    context["macro"] = macro


def _fetch_macro_catalog(
    *,
    conn: duckdb.DuckDBPyConnection,
    series_ids: list[str],
) -> list[dict[str, Any]]:
    where_sql, params = _series_filter_sql(series_ids)
    return _fetch_all(
        conn,
        f"""
        select series_id, series_name, vendor_name, vendor_version, frequency, unit,
               vendor_series_code, catalog_version, theme, is_core, refresh_tier,
               fetch_mode, fetch_granularity, policy_note
        from phase1_macro_vendor_catalog
        {where_sql}
        order by series_id
        limit 20
        """,
        params,
    )


def _latest_rows_by_series(
    *,
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    select_columns: tuple[str, ...],
    series_ids: list[str],
    as_of_date: str,
) -> list[dict[str, Any]]:
    where_sql, params = _series_filter_sql(series_ids, as_of_date=as_of_date)
    columns = ", ".join(select_columns)
    return _fetch_all(
        conn,
        f"""
        select {columns}
        from (
          select {columns},
                 row_number() over (partition by series_id order by trade_date desc) as rn
          from {table_name}
          {where_sql}
        )
        where rn = 1
        order by series_id
        limit 20
        """,
        params,
    )


def _series_filter_sql(series_ids: list[str], *, as_of_date: str = "") -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if not series_ids:
        placeholders = ""
    else:
        placeholders = ", ".join(["?"] * len(series_ids))
        conditions.append(f"series_id in ({placeholders})")
        params.extend(series_ids)
    if as_of_date:
        conditions.append("trade_date <= ?")
        params.append(as_of_date)
    if not conditions:
        return "", []
    return f"where {' and '.join(conditions)}", params


def _resolve_research_domain(request: AgentQueryRequest) -> str | None:
    explicit = str(request.filters.get("research_domain") or "").strip().lower()
    if explicit in {"stock", "macro"}:
        return explicit
    page_id = str(request.page_context.page_id if request.page_context else "").strip().lower()
    if page_id == "stock-analysis":
        return "stock"
    question = request.question.lower()
    if any(token in question for token in ("股票", "个股", "stock", "ticker")):
        return "stock"
    if any(token in question for token in ("宏观", "利率", "通胀", "cpi", "ppi", "gdp", "macro")):
        return "macro"
    return None


def _resolve_as_of_date(request: AgentQueryRequest) -> str:
    for value in (
        request.filters.get("as_of_date"),
        request.filters.get("report_date"),
        request.page_context.current_filters.get("as_of_date") if request.page_context else None,
        request.page_context.current_filters.get("report_date") if request.page_context else None,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _resolve_stock_code(request: AgentQueryRequest) -> str:
    for value in (request.filters.get("stock_code"), request.filters.get("ticker")):
        text = str(value or "").strip().upper()
        if text:
            return text
    if request.page_context:
        for row in request.page_context.selected_rows:
            for key in ("stock_code", "ticker", "code"):
                text = str(row.get(key) or "").strip().upper()
                if text:
                    return text
    return ""


def _resolve_macro_series_ids(filters: dict[str, Any]) -> list[str]:
    raw = filters.get("macro_series_ids") or filters.get("series_ids")
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
        if values:
            return values[:20]
    single = str(filters.get("macro_series_id") or filters.get("series_id") or "").strip()
    if single:
        return [single]
    return list(DEFAULT_MACRO_SERIES_IDS)


def _non_empty_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "")}


def _fetch_one(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    params: list[Any],
) -> dict[str, Any] | None:
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row, strict=False))


def _fetch_all(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    params: list[Any],
) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, params)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
