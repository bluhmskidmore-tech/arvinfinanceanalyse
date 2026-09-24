"""今日盘前操作清单（观察面裁剪，不构成交易指令）。

回答"今天开盘我该做什么"：把散在 `scripts/export_livermore_pretrade_check.py`
的盘前检查页面化。组装口径：

- 候选取数：``livermore_candidate_history`` 中 ``signal_kind='factor_screen'``
  的最近 ``snapshot_as_of_date``（可显式指定），按 ``candidate_rank`` 取前
  ``top_n``（默认 10）；
- 停牌口径：共享 ``core_finance.field_normalization.is_tradestatus_halted``
  （非空非可交易词值一律停牌，fail-closed）；
- 涨跌停三态：共享 ``core_finance.portfolio_paths.resolve_limit_prices`` ——
  ``stock_limit_price_daily`` 数值价（stk_limit）优先；新表无行/半缺失降级
  observation 列 try_cast（observation_cast，tushare 代际旧数值）；两者皆无
  再降级为观测表/候选表布尔位（observation_flag，choice 代际"是/否"标志与
  ``closed_up_limit``）；全部缺失为 unknown（fail-open，不硬造拦截）；
- 金额门槛：docs/data_contracts.md §4.10 人民币元口径（``amount_rmb_sql``），
  缺 ``vendor_version`` 定标时 fail-closed 输出 NULL（missing_amount）；
- 仓位建议：直接透传 ``core_finance.position_sizing.
  build_stock_candidate_position_size_hint`` 的输出结构（close=selection_close、
  ema10 取候选历史行；门控敞口可用时传入以计算等权主口径），不复制公式；
- 门控敞口：``core_finance.gate_exposure_series.load_gate_exposure_by_date``
  轻读（持久化点位优先、缺失回放），读取失败降级为门控字段缺省 + 注明；
  不 import ``market_data_livermore_service``；
- stale 语义：信号日距 today 超过 ``stale_calendar_days`` 个自然日（沿用盘前
  脚本 DEFAULT_STALE_CALENDAR_DAYS=5 的自然日口径）时 ``checklist_status``
  标记 stale；请求的信号日无候选行时标记 empty。

本服务对 DuckDB 只读；库文件缺失、候选历史表缺失或库无法打开时返回 None，
由路由映射为 404（前端整面隐藏）。
"""
from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import duckdb
from backend.app.core_finance.field_normalization import is_tradestatus_halted
from backend.app.core_finance.gate_exposure_series import load_gate_exposure_by_date
from backend.app.core_finance.portfolio_paths import (
    LIMIT_PRICE_SOURCE_MISSING,
    resolve_limit_prices,
)
from backend.app.core_finance.position_sizing import (
    build_stock_candidate_position_size_hint,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_units import amount_rmb_sql
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
)

RESULT_KIND = "pretrade_checklist.today"
RULE_VERSION = "rv_pretrade_checklist_v1"
CACHE_VERSION = "cv_pretrade_checklist_v1"

TABLE_HIST = "livermore_candidate_history"
TABLE_DAILY = "choice_stock_daily_observation"
TABLE_LIMIT_PRICE = "stock_limit_price_daily"
TABLE_ADJ_FACTOR = "stock_adjustment_factor"
SIGNAL_KIND = "factor_screen"

DEFAULT_TOP_N = 10
DEFAULT_MIN_AMOUNT = 0.0
DEFAULT_STALE_CALENDAR_DAYS = 5

#: 布尔位降级来源标记（choice 代际观测标志 / 候选表 closed_up_limit）。
LIMIT_SOURCE_OBSERVATION_FLAG = "observation_flag"

GATE_MISSING_NOTE = "门控敞口在该信号日无持久化点位且不可回放，字段缺省，不代表门控放行。"
GATE_DEGRADED_NOTE = "门控敞口读取失败，字段缺省，不代表门控放行。"
DISCLAIMER = "观察面输出：盘前检查仅供复核参考，不构成交易指令。"

# 与 scripts/export_livermore_pretrade_check.py 同口径的布尔位词表。
_FALSE_FLAGS = {"", "0", "false", "n", "no", "否"}
_TRUE_FLAGS = {"1", "true", "y", "yes", "是", "涨停", "跌停"}


def pretrade_checklist_envelope(
    *,
    duckdb_path: str | Path | None = None,
    as_of_date: str | None = None,
    top_n: int = DEFAULT_TOP_N,
    min_amount: float = DEFAULT_MIN_AMOUNT,
    stale_calendar_days: int = DEFAULT_STALE_CALENDAR_DAYS,
    today: str | None = None,
) -> dict[str, object] | None:
    """读取 + 组装 + 打包 result_meta；数据面不可用时返回 None（路由映射 404）。"""
    path = Path(duckdb_path) if duckdb_path is not None else Path(get_settings().duckdb_path)
    if not path.is_file():
        return None
    try:
        with read_only_connection(str(path)) as conn:
            tables = _table_names(conn)
            if TABLE_HIST not in tables:
                return None
            resolved_as_of = _resolve_as_of_date(conn, as_of_date=as_of_date)
            if not resolved_as_of:
                return None
            candidates = _load_candidates(conn, as_of_date=resolved_as_of)[: max(1, int(top_n))]
            codes = [str(row["stock_code"]) for row in candidates if row.get("stock_code")]
            daily_by_code = _load_daily_rows(conn, tables=tables, as_of_date=resolved_as_of, codes=codes)
            limit_by_code = _load_limit_price_rows(conn, tables=tables, as_of_date=resolved_as_of, codes=codes)
            adj_codes = _load_adj_factor_codes(conn, tables=tables, as_of_date=resolved_as_of, codes=codes)
            gate = _load_gate_status(conn, as_of_date=resolved_as_of)
    except (OSError, duckdb.Error):
        return None

    payload = build_pretrade_checklist(
        as_of_date=resolved_as_of,
        candidates=candidates,
        daily_by_code=daily_by_code,
        limit_by_code=limit_by_code,
        adj_codes=adj_codes,
        gate=gate,
        top_n=max(1, int(top_n)),
        min_amount=float(min_amount),
        stale_calendar_days=int(stale_calendar_days),
        today=today,
    )
    quality_flag = "ok"
    if payload["checklist_status"] != "ok" or gate.get("status") != "available":
        quality_flag = "warning"
    meta = build_analytical_result_meta(
        trace_id=uuid.uuid4().hex,
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=f"sv_pretrade_checklist_{resolved_as_of}",
        rule_version=RULE_VERSION,
        quality_flag=quality_flag,
        as_of_date=resolved_as_of,
        filters_applied={
            "requested_as_of_date": as_of_date,
            "as_of_date": resolved_as_of,
            "signal_kind": SIGNAL_KIND,
            "top_n": max(1, int(top_n)),
            "min_amount": float(min_amount),
        },
        tables_used=[TABLE_HIST, TABLE_DAILY, TABLE_LIMIT_PRICE, TABLE_ADJ_FACTOR],
        evidence_rows=len(payload["items"]) if isinstance(payload.get("items"), list) else 0,
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload)


def build_pretrade_checklist(
    *,
    as_of_date: str,
    candidates: list[dict[str, object]],
    daily_by_code: dict[str, dict[str, object]],
    limit_by_code: dict[str, dict[str, object]],
    adj_codes: set[str],
    gate: dict[str, object],
    top_n: int,
    min_amount: float,
    stale_calendar_days: int,
    today: str | None,
) -> dict[str, object]:
    """纯组装（不触 DuckDB），便于合成行级测试。"""
    # 门控敞口可用时传入，等权主口径（equal_weight = 敞口/候选数）由
    # position_sizing 当前函数自行计算；门控缺省时 equal_weight 为 None。
    gate_exposure = gate.get("exposure") if gate.get("status") == "available" else None
    hint_block = build_stock_candidate_position_size_hint(
        [
            {
                "stock_code": row.get("stock_code"),
                "close": row.get("selection_close"),
                "ema10": row.get("ema10"),
            }
            for row in candidates
        ],
        market_gate_exposure=gate_exposure,
    )
    hint_items = hint_block.get("items")
    hint_by_code = {
        str(item.get("stock_code")): item
        for item in (hint_items if isinstance(hint_items, list) else [])
    }

    items = [
        _build_item(
            row,
            daily=daily_by_code.get(str(row.get("stock_code") or ""), {}),
            limit_price=limit_by_code.get(str(row.get("stock_code") or ""), {}),
            has_adj_factor=str(row.get("stock_code") or "") in adj_codes,
            position_hint=hint_by_code.get(str(row.get("stock_code") or "")),
            min_amount=min_amount,
        )
        for row in candidates
    ]

    today_text = _normalize_date(today) if today else date.today().isoformat()
    calendar_gap = _calendar_gap_days(today_text, as_of_date)
    stale = calendar_gap is not None and calendar_gap > stale_calendar_days
    checklist_status = "empty" if not items else ("stale" if stale else "ok")

    status_counts: dict[str, int] = {}
    for item in items:
        key = str(item["buyable_status"])
        status_counts[key] = status_counts.get(key, 0) + 1

    return {
        "as_of_date": as_of_date,
        "signal_kind": SIGNAL_KIND,
        "checklist_status": checklist_status,
        "candidate_count": len(candidates),
        "top_n": top_n,
        "staleness": {
            "status": "stale" if stale else "ok",
            "today": today_text,
            "calendar_gap_days": calendar_gap,
            "stale_calendar_days": stale_calendar_days,
        },
        "gate": gate,
        "position_size_hint": hint_block,
        "items": items,
        "summary": {
            "buyable_count": status_counts.get("buyable", 0),
            "blocked_count": status_counts.get("blocked_suspended", 0)
            + status_counts.get("blocked_limit", 0),
            "review_count": status_counts.get("review", 0),
            "data_missing_count": status_counts.get("data_missing", 0),
        },
        "disclaimer": DISCLAIMER,
    }


def _build_item(
    row: dict[str, object],
    *,
    daily: dict[str, object],
    limit_price: dict[str, object],
    has_adj_factor: bool,
    position_hint: dict[str, object] | None,
    min_amount: float,
) -> dict[str, object]:
    has_daily = bool(daily)
    trade_status = str(daily.get("tradestatus") or "").strip()
    is_suspended = is_tradestatus_halted(trade_status)
    close_value = _optional_float(daily.get("close_value"))
    amount = _optional_float(daily.get("amount"))
    limit_check = _limit_check(
        closed_up_limit=row.get("closed_up_limit"),
        observation_highlimit=daily.get("highlimit"),
        observation_lowlimit=daily.get("lowlimit"),
        table_up_limit=limit_price.get("up_limit"),
        table_down_limit=limit_price.get("down_limit"),
        close_value=close_value,
    )

    block_reasons: list[str] = []
    data_flags: list[str] = []
    if not has_adj_factor:
        data_flags.append("adj_factor_missing")
    if limit_check["status"] == "unknown":
        data_flags.append("limit_price_missing")

    if not has_daily:
        block_reasons.append("missing_daily_observation")
        status = "data_missing"
    elif is_suspended:
        block_reasons.append("suspended")
        status = "blocked_suspended"
    elif limit_check["status"] in {"limit_up", "limit_down"}:
        block_reasons.append(str(limit_check["status"]))
        status = "blocked_limit"
    elif amount is None:
        block_reasons.append("missing_amount")
        status = "data_missing"
    elif amount <= 0:
        block_reasons.append("non_positive_amount")
        status = "data_missing"
    elif min_amount > 0 and amount < min_amount:
        block_reasons.append("low_liquidity")
        status = "review"
    else:
        status = "buyable"

    return {
        "candidate_rank": _optional_int(row.get("candidate_rank")),
        "stock_code": row.get("stock_code"),
        "stock_name": row.get("stock_name"),
        "sector_name": row.get("sector_name"),
        "selection_close": _optional_float(row.get("selection_close")),
        "close_value": close_value,
        "trade_status": trade_status or None,
        "is_suspended": is_suspended,
        "limit_check": limit_check,
        "amount_rmb": amount,
        "adj_factor_missing": not has_adj_factor,
        "buyable_status": status,
        "block_reasons": block_reasons,
        "data_flags": data_flags,
        "position_hint": position_hint,
    }


def _limit_check(
    *,
    closed_up_limit: object,
    observation_highlimit: object,
    observation_lowlimit: object,
    table_up_limit: object,
    table_down_limit: object,
    close_value: float | None,
) -> dict[str, object]:
    """涨跌停三态判定：数值价（共享 resolve_limit_prices）→ 布尔位 → unknown。"""
    up_limit, down_limit, price_source = resolve_limit_prices(
        observation_highlimit=observation_highlimit,
        observation_lowlimit=observation_lowlimit,
        table_up_limit=table_up_limit,
        table_down_limit=table_down_limit,
    )
    if price_source != LIMIT_PRICE_SOURCE_MISSING and close_value is not None:
        # 数值口径与盘前脚本一致：贴板容差 0.1%。
        if up_limit is not None and close_value >= up_limit * 0.999:
            status = "limit_up"
        elif down_limit is not None and close_value <= down_limit * 1.001:
            status = "limit_down"
        else:
            status = "none"
        return {
            "status": status,
            "price_source": price_source,
            "up_limit": up_limit,
            "down_limit": down_limit,
        }

    # 表空/数值不可解析：降级为布尔位（choice 代际观测标志 + 候选表 closed_up_limit）。
    if _truthy_flag(closed_up_limit) or _truthy_flag(observation_highlimit):
        return {
            "status": "limit_up",
            "price_source": LIMIT_SOURCE_OBSERVATION_FLAG,
            "up_limit": None,
            "down_limit": None,
        }
    if _truthy_flag(observation_lowlimit):
        return {
            "status": "limit_down",
            "price_source": LIMIT_SOURCE_OBSERVATION_FLAG,
            "up_limit": None,
            "down_limit": None,
        }
    if price_source != LIMIT_PRICE_SOURCE_MISSING:
        # 有数值价但当日 close 缺失：无法比较，维持 fail-open 的 unknown。
        return {
            "status": "unknown",
            "price_source": price_source,
            "up_limit": up_limit,
            "down_limit": down_limit,
        }
    return {
        "status": "unknown",
        "price_source": LIMIT_PRICE_SOURCE_MISSING,
        "up_limit": None,
        "down_limit": None,
    }


def _load_gate_status(conn: duckdb.DuckDBPyConnection, *, as_of_date: str) -> dict[str, object]:
    """门控敞口轻读；任何失败降级为字段缺省 + 注明（不硬造门控放行）。"""
    try:
        points = load_gate_exposure_by_date(conn, as_of_date, as_of_date)
    except Exception:  # noqa: BLE001 - 门控降级路径必须兜住任意读取失败
        return {"status": "degraded", "state": None, "exposure": None, "source": None, "note": GATE_DEGRADED_NOTE}
    point = points.get(as_of_date)
    if point is None or point.source == "missing":
        return {"status": "missing", "state": None, "exposure": None, "source": None, "note": GATE_MISSING_NOTE}
    return {
        "status": "available",
        "state": point.state,
        "exposure": point.exposure,
        "source": point.source,
        "note": None,
    }


def _resolve_as_of_date(conn: duckdb.DuckDBPyConnection, *, as_of_date: str | None) -> str | None:
    if as_of_date:
        return _normalize_date(as_of_date)
    row = conn.execute(
        f"select max(snapshot_as_of_date) from {TABLE_HIST} where signal_kind = ?",
        [SIGNAL_KIND],
    ).fetchone()
    resolved = str(row[0] or "").strip()[:10] if row else ""
    return resolved or None


def _load_candidates(conn: duckdb.DuckDBPyConnection, *, as_of_date: str) -> list[dict[str, object]]:
    rows = conn.execute(
        f"""
        select
          candidate_rank,
          stock_code,
          stock_name,
          sector_name,
          selection_close,
          ema10,
          market_state,
          data_status,
          closed_up_limit
        from {TABLE_HIST}
        where snapshot_as_of_date = ?
          and signal_kind = ?
        order by candidate_rank nulls last, stock_code
        """,
        [as_of_date, SIGNAL_KIND],
    ).fetchall()
    keys = [
        "candidate_rank",
        "stock_code",
        "stock_name",
        "sector_name",
        "selection_close",
        "ema10",
        "market_state",
        "data_status",
        "closed_up_limit",
    ]
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _load_daily_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str,
    codes: list[str],
) -> dict[str, dict[str, object]]:
    if TABLE_DAILY not in tables or not codes:
        return {}
    columns = _table_columns(conn, TABLE_DAILY)
    # docs/data_contracts.md §4.10：金额统一人民币元口径；缺 vendor_version 列
    # 无法定标，fail-closed 输出 NULL（该行落入 missing_amount，不参与门槛比较）。
    amount_select = (
        amount_rmb_sql(alias="amount")
        if "vendor_version" in columns
        else "cast(null as double) as amount"
    )
    placeholders = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"""
        select stock_code, close_value, {amount_select}, tradestatus, highlimit, lowlimit
        from {TABLE_DAILY}
        where trade_date = ?
          and stock_code in ({placeholders})
        """,
        [as_of_date, *codes],
    ).fetchall()
    keys = ["stock_code", "close_value", "amount", "tradestatus", "highlimit", "lowlimit"]
    return {str(row[0]): dict(zip(keys, row, strict=True)) for row in rows}


def _load_limit_price_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str,
    codes: list[str],
) -> dict[str, dict[str, object]]:
    if TABLE_LIMIT_PRICE not in tables or not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"""
        select stock_code, up_limit, down_limit
        from {TABLE_LIMIT_PRICE}
        where trade_date = ?
          and stock_code in ({placeholders})
        """,
        [as_of_date, *codes],
    ).fetchall()
    return {str(row[0]): {"up_limit": row[1], "down_limit": row[2]} for row in rows}


def _load_adj_factor_codes(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str,
    codes: list[str],
) -> set[str]:
    if TABLE_ADJ_FACTOR not in tables or not codes:
        return set()
    placeholders = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"""
        select distinct stock_code
        from {TABLE_ADJ_FACTOR}
        where trade_date = ?
          and stock_code in ({placeholders})
          and adj_factor is not null
        """,
        [as_of_date, *codes],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {
        str(row[1]).lower()
        for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()
    }


def _truthy_flag(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _FALSE_FLAGS:
        return False
    return text in _TRUE_FLAGS


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_date(value: str | None) -> str:
    text = str(value or "").strip()[:10]
    if not text:
        raise ValueError("date value cannot be blank.")
    date.fromisoformat(text)
    return text


def _calendar_gap_days(today_text: str, as_of_text: str) -> int | None:
    try:
        return (date.fromisoformat(today_text) - date.fromisoformat(as_of_text)).days
    except ValueError:
        return None
