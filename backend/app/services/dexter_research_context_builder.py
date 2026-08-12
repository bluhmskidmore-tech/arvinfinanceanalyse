from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.repositories.market_read_repo import (
    RELATION_CHOICE_MARKET_SNAPSHOT,
    RELATION_CHOICE_NEWS_EVENT,
    RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
    RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT,
    RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP,
    RELATION_FACT_CHOICE_MACRO_DAILY,
    RELATION_PHASE1_MACRO_VENDOR_CATALOG,
    RELATION_VW_EXTERNAL_MACRO_DAILY,
    MarketReadRepository,
)

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

        repo = MarketReadRepository(str(db_path), guard_path_exists=True)
        with repo.scoped_connection() as conn:
            if conn is None:
                context["quality_flag"] = "missing"
                context["limitations"].append("DuckDB database could not be opened read-only.")
                return context
            tables = repo.available_relations(conn=conn)
            if domain == "stock":
                _build_stock_context(repo=repo, conn=conn, tables=tables, context=context)
            elif domain == "macro":
                _build_macro_context(repo=repo, conn=conn, tables=tables, context=context)

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
        "sql_executed": [],
        "evidence_rows": 0,
        "quality_flag": "ok",
        "limitations": [],
        "stock": {},
        "macro": {},
    }


def _build_stock_context(
    *,
    repo: MarketReadRepository,
    conn: Any,
    tables: set[str],
    context: dict[str, Any],
) -> None:
    stock_code = str(context["filters_applied"].get("stock_code") or "").strip().upper()
    as_of_date = str(context.get("as_of_date") or "").strip()
    if not stock_code:
        context["limitations"].append("Stock research requires stock_code from filters or selected_rows.")
        return

    stock: dict[str, Any] = {}
    if RELATION_CHOICE_STOCK_DAILY_OBSERVATION in tables:
        context["tables_used"].append(RELATION_CHOICE_STOCK_DAILY_OBSERVATION)
        row, has_vendor_version = repo.fetch_dexter_stock_daily(
            stock_code=stock_code,
            as_of_date=as_of_date,
            sql_executed=context["sql_executed"],
            conn=conn,
        )
        if not has_vendor_version:
            # docs/data_contracts.md §4.10 fail-closed: 缺失 vendor_version 列时无法定标,
            # amount/volume 一律置空,禁止原始值透传进入 Dexter 语料。
            context["limitations"].append(
                "choice_stock_daily_observation missing vendor_version column; "
                "amount/volume cannot be calibrated and were set to null (fail-closed)."
            )
        if row:
            volume_scale_unknown = bool(row.pop("_volume_scale_unknown", False))
            amount_scale_unknown = bool(row.pop("_amount_scale_unknown", False))
            if volume_scale_unknown:
                row["volume_unit"] = "unknown"
                context["limitations"].append(
                    "Daily observation volume is non-null but vendor_version is null; "
                    "normalized volume was left null."
                )
            if amount_scale_unknown:
                row["amount_unit"] = "unknown"
                context["limitations"].append(
                    "Daily observation amount is non-null but vendor_version is null; "
                    "normalized amount was left null."
                )
            stock["daily_observation"] = row
            context["evidence_rows"] += 1
        else:
            context["limitations"].append(f"No Choice stock daily observation matched {stock_code}.")
    else:
        context["limitations"].append("choice_stock_daily_observation is not landed.")

    if RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT in tables:
        context["tables_used"].append(RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT)
        row = repo.fetch_dexter_stock_factor(
            stock_code=stock_code,
            as_of_date=as_of_date,
            sql_executed=context["sql_executed"],
            conn=conn,
        )
        if row:
            stock["factor_snapshot"] = row
            context["evidence_rows"] += 1
        else:
            context["limitations"].append(f"No Choice stock factor snapshot matched {stock_code}.")
    else:
        context["limitations"].append("choice_stock_factor_snapshot is not landed.")

    if RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP in tables:
        context["tables_used"].append(RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP)
        row = repo.fetch_dexter_stock_sector(
            stock_code=stock_code,
            as_of_date=as_of_date,
            sql_executed=context["sql_executed"],
            conn=conn,
        )
        if row:
            stock["sector_membership"] = row
            context["evidence_rows"] += 1
        else:
            context["limitations"].append(f"No Choice stock sector membership matched {stock_code}.")
    else:
        context["limitations"].append("choice_stock_sector_membership is not landed.")

    if RELATION_CHOICE_NEWS_EVENT in tables:
        context["tables_used"].append(RELATION_CHOICE_NEWS_EVENT)
        rows = repo.fetch_dexter_stock_news(
            stock_code=stock_code,
            sql_executed=context["sql_executed"],
            conn=conn,
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
    repo: MarketReadRepository,
    conn: Any,
    tables: set[str],
    context: dict[str, Any],
) -> None:
    series_ids = _resolve_macro_series_ids(context["filters_applied"])
    as_of_date = str(context.get("as_of_date") or "").strip()
    macro: dict[str, Any] = {"series_ids": series_ids}

    if RELATION_FACT_CHOICE_MACRO_DAILY in tables:
        context["tables_used"].append(RELATION_FACT_CHOICE_MACRO_DAILY)
        rows = repo.fetch_dexter_choice_macro_series(
            series_ids=series_ids,
            as_of_date=as_of_date,
            sql_executed=context["sql_executed"],
            conn=conn,
        )
        macro["choice_series"] = rows
        context["evidence_rows"] += len(rows)
    else:
        context["limitations"].append("fact_choice_macro_daily is not landed.")

    if RELATION_CHOICE_MARKET_SNAPSHOT in tables:
        context["tables_used"].append(RELATION_CHOICE_MARKET_SNAPSHOT)
        rows = repo.fetch_dexter_choice_market_snapshots(
            series_ids=series_ids,
            as_of_date=as_of_date,
            sql_executed=context["sql_executed"],
            conn=conn,
        )
        macro["choice_snapshots"] = rows
        context["evidence_rows"] += len(rows)
    else:
        context["limitations"].append("choice_market_snapshot is not landed.")

    if RELATION_PHASE1_MACRO_VENDOR_CATALOG in tables:
        context["tables_used"].append(RELATION_PHASE1_MACRO_VENDOR_CATALOG)
        macro["catalog"] = repo.fetch_dexter_macro_catalog(
            series_ids=series_ids,
            sql_executed=context["sql_executed"],
            conn=conn,
        )
        context["evidence_rows"] += len(macro["catalog"])
    else:
        context["limitations"].append("phase1_macro_vendor_catalog is not landed.")

    if RELATION_VW_EXTERNAL_MACRO_DAILY in tables:
        context["tables_used"].append(RELATION_VW_EXTERNAL_MACRO_DAILY)
        macro["tushare_series"] = repo.fetch_dexter_external_macro_series(
            series_ids=series_ids,
            as_of_date=as_of_date,
            sql_executed=context["sql_executed"],
            conn=conn,
        )
        context["evidence_rows"] += len(macro["tushare_series"])
    else:
        context["limitations"].append("vw_external_macro_daily is not landed.")

    context["macro"] = macro


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
