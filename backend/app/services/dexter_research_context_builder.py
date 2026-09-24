from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
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

# 上下文体积预算：以注入 prompt 的同一序列化口径（ensure_ascii=False, indent=2）计。
# 16K 字符约 4K token；叠加基础 prompt 后仍远低于 Windows CreateProcess 约 32K 的
# argv 上限（CLI 模式 prompt 直接走命令行参数）。
MAX_CONTEXT_SERIALIZED_CHARS = 16_000
# 单条新闻 payload 字段上限：5 条新闻 × 两个字段 × 400 字符，最坏约 4K 字符。
MAX_NEWS_PAYLOAD_FIELD_CHARS = 400
_TRUNCATION_MARKER = "...[truncated]"
# 体积超限时按证据价值从低到高逐来源丢行：新闻原文最先，宏观目录最后。
_CONTEXT_TRIM_ORDER = (
    ("stock", "news_events"),
    ("macro", "tushare_series"),
    ("macro", "choice_snapshots"),
    ("macro", "choice_series"),
    ("macro", "catalog"),
)

# stale 阈值（自然日）：日频给长假/停牌留缓冲；因子/行业快照按季度更新节奏；
# 新闻按 30 天研究可用窗口。参考日期优先取 as_of_date，缺省用当天（UTC）。
STALE_AFTER_DAYS_DAILY = 14
STALE_AFTER_DAYS_NEWS = 30
STALE_AFTER_DAYS_SNAPSHOT = 120
_STALE_AFTER_DAYS_BY_FREQUENCY = {
    "daily": 14,
    "weekly": 35,
    "monthly": 62,
    "quarterly": 120,
    "yearly": 430,
}
_STALE_AFTER_DAYS_DEFAULT = 62


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
        try:
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
        except (OSError, duckdb.Error) as exc:
            # 研究上下文是增强证据：DuckDB 查询失败（如 schema 漂移的 BinderException）
            # 降级为披露性 limitation，不让异常穿透 provider 链路变成 500。
            context["quality_flag"] = "warning" if context["evidence_rows"] > 0 else "missing"
            context["limitations"].append(
                f"Research context DuckDB queries failed ({exc.__class__.__name__}); "
                "evidence may be partial."
            )

        _apply_stale_disclosures(context)
        _enforce_context_budget(context)

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
    limitations: list[str] = []
    raw_as_of = _resolve_as_of_date(request)
    as_of_date = ""
    if raw_as_of:
        parsed = _parse_iso_date(raw_as_of)
        if parsed is None:
            # 非 ISO 的 as_of 会让下游 varchar 日期比较静默失效：置空禁用锚定并显式披露，
            # 避免"披露声明了锚定、SQL 实际未生效"的分叉。
            limitations.append(
                f"as_of_date '{raw_as_of[:64]}' is not a valid ISO date (YYYY-MM-DD); "
                "date anchoring was disabled for this research context."
            )
            filters_applied.pop("as_of_date", None)
        else:
            as_of_date = parsed.isoformat()
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
        "limitations": limitations,
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
            as_of_date=as_of_date,
            sql_executed=context["sql_executed"],
            conn=conn,
        )
        truncated_fields = 0
        for news_row in rows:
            for field in ("payload_text", "payload_json"):
                value = news_row.get(field)
                if isinstance(value, str) and len(value) > MAX_NEWS_PAYLOAD_FIELD_CHARS:
                    news_row[field] = value[:MAX_NEWS_PAYLOAD_FIELD_CHARS] + _TRUNCATION_MARKER
                    truncated_fields += 1
        if truncated_fields:
            context["limitations"].append(
                f"choice_news_event payload fields truncated to {MAX_NEWS_PAYLOAD_FIELD_CHARS} "
                f"characters for context budget ({truncated_fields} field(s))."
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


def _apply_stale_disclosures(context: dict[str, Any]) -> None:
    """标注证据新鲜度。

    stale 说明写入独立的 ``stale_sources``（并镜像进 ``filters_applied`` 以随
    Envelope evidence/meta 披露），不进 ``limitations``、不改 ``quality_flag``：
    "最新落地行仍偏旧" 与 "证据缺失/不可定标" 是两类信号，前者不应把
    fresh-but-limited 与 stale 混在同一质量降级里。
    """
    reference = _parse_iso_date(context.get("as_of_date")) or datetime.now(UTC).date()
    notes: list[str] = []
    stock = context.get("stock") or {}
    _note_stale_row(
        notes,
        source=RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
        row=stock.get("daily_observation"),
        date_key="trade_date",
        threshold_days=STALE_AFTER_DAYS_DAILY,
        reference=reference,
    )
    _note_stale_row(
        notes,
        source=RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT,
        row=stock.get("factor_snapshot"),
        date_key="as_of_date",
        threshold_days=STALE_AFTER_DAYS_SNAPSHOT,
        reference=reference,
    )
    _note_stale_row(
        notes,
        source=RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP,
        row=stock.get("sector_membership"),
        date_key="as_of_date",
        threshold_days=STALE_AFTER_DAYS_SNAPSHOT,
        reference=reference,
    )
    news_rows = stock.get("news_events") or []
    if news_rows:
        # 新闻按 received_at 倒序取回，首行即最新一条。
        _note_stale_row(
            notes,
            source=RELATION_CHOICE_NEWS_EVENT,
            row=news_rows[0],
            date_key="received_at",
            threshold_days=STALE_AFTER_DAYS_NEWS,
            reference=reference,
        )

    macro = context.get("macro") or {}
    for source, key in (
        (RELATION_FACT_CHOICE_MACRO_DAILY, "choice_series"),
        (RELATION_CHOICE_MARKET_SNAPSHOT, "choice_snapshots"),
        (RELATION_VW_EXTERNAL_MACRO_DAILY, "tushare_series"),
    ):
        stale_series: list[str] = []
        for row in macro.get(key) or []:
            frequency = str(row.get("frequency") or "").strip().lower()
            threshold = _STALE_AFTER_DAYS_BY_FREQUENCY.get(frequency, _STALE_AFTER_DAYS_DEFAULT)
            days = _days_behind(row.get("trade_date"), reference)
            if days is not None and days > threshold:
                row["stale"] = True
                stale_series.append(f"{row.get('series_id')} ({days}d>{threshold}d)")
        if stale_series:
            notes.append(
                f"{source} is stale vs {reference.isoformat()}: {', '.join(stale_series)}."
            )

    if notes:
        context["stale_sources"] = notes
        context["filters_applied"]["research_stale_sources"] = notes


def _note_stale_row(
    notes: list[str],
    *,
    source: str,
    row: Any,
    date_key: str,
    threshold_days: int,
    reference: date,
) -> None:
    if not isinstance(row, dict):
        return
    days = _days_behind(row.get(date_key), reference)
    if days is None or days <= threshold_days:
        return
    row["stale"] = True
    notes.append(
        f"{source} is stale: {date_key} {str(row.get(date_key))[:10]} is {days} days "
        f"behind {reference.isoformat()} (threshold {threshold_days}d)."
    )


def _days_behind(value: Any, reference: date) -> int | None:
    parsed = _parse_iso_date(value)
    if parsed is None:
        return None
    return (reference - parsed).days


def _parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _enforce_context_budget(context: dict[str, Any]) -> None:
    if _serialized_context_chars(context) <= MAX_CONTEXT_SERIALIZED_CHARS:
        return
    dropped: list[str] = []
    for section, key in _CONTEXT_TRIM_ORDER:
        rows = (context.get(section) or {}).get(key)
        if not isinstance(rows, list) or not rows:
            continue
        removed = 0
        while rows and _serialized_context_chars(context) > MAX_CONTEXT_SERIALIZED_CHARS:
            rows.pop()
            removed += 1
        if removed:
            # 被丢弃的行不再注入语料，证据行数同步回减，保持披露口径一致。
            context["evidence_rows"] = max(0, int(context["evidence_rows"]) - removed)
            dropped.append(f"{key} -{removed}")
        if _serialized_context_chars(context) <= MAX_CONTEXT_SERIALIZED_CHARS:
            break
    if dropped:
        context["limitations"].append(
            f"Research context exceeded the {MAX_CONTEXT_SERIALIZED_CHARS}-character budget; "
            f"dropped rows: {', '.join(dropped)}."
        )
    if _serialized_context_chars(context) > MAX_CONTEXT_SERIALIZED_CHARS:
        context["limitations"].append(
            "Research context remains over budget after row trimming; "
            "remaining evidence is kept as-is."
        )


def _serialized_context_chars(context: dict[str, Any]) -> int:
    # 与 dexter_agent_service._build_dexter_prompt 注入 prompt 的序列化口径保持一致。
    return len(json.dumps(context, ensure_ascii=False, default=str, indent=2))


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
