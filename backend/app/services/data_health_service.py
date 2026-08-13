"""数据健康总览（系统级体温计，观察面）。

网络断供期"哪里带病、缺口多大"的信息散落在多处，本服务把它们聚合成
``{sections: [{key, label, status, metric, detail, as_of}]}``：

- ``observation_freshness`` / ``market_breadth_freshness`` /
  ``gate_supplement_freshness``：供数新鲜度，max(trade_date) 距今天数；
- ``adjustment_factor_gap``：执行历史 ``return_*_net`` 非空但 ``*_net_adj``
  空的行数（按 1d/5d/10d/20d 视角分列）+ ``stock_adjustment_factor``
  max(trade_date)（复权因子悬崖）；
- ``stale_formula_rows``：execution / matched_baseline 两表 ``formula_version``
  非当前版本常量的存量行数（当前版本常量 import 自各自模块，直接对表聚合，
  不复用 livermore_candidate_history_service 的窗口披露逻辑）；
- ``concept_interval_staleness``：概念区间表 max(last_observed_date) 距今
  （docs/data_contracts.md §4.11 运维观察点）；
- ``limit_price_backfill``：``stock_limit_price_daily`` 行数（0 = 未回填）；
- ``tradestatus_vocabulary``：tradestatus 非空且不在可交易白名单词表的行数
  与占比（词表 import 自 ``core_finance.field_normalization``，§4.10 "未知
  非空值占比"观察点；显式停牌词值同样不在白名单内、计入本口径）；
- ``scheduled_tasks``：``schtasks /query /fo csv /v`` 查询 MOSS-* 计划任务的
  LastRunTime/LastResult（仅 Windows；非 Windows/无权限/超时降级为
  status=error + 原因，字段缺省）。

状态语义（整体状态取最差项，严重度 ok < warn < stale < missing < error）：

- ``ok``      正常；
- ``warn``    落后 / 存在缺口，可用但需关注；
- ``stale``   落后超过陈旧阈值，或旧公式版本存量待重物化；
- ``missing`` 数据面未构建 / 为空（表缺失、0 行、无计划任务）；
- ``error``   本项检查执行失败（每项独立 try/except，单项失败不拖垮整体）。

新鲜度阈值：落后 > 2 天 warn、> 5 天 stale。无交易日历依赖，用自然日近似
交易日（周末/长假会放大 1~2 天，detail 中注明）。

本服务对 DuckDB 只读（read_only_connection 自带瞬时锁重试）；库文件缺失时
返回 None，由路由映射为 404（前端整面隐藏）。库文件存在但打开失败时，
DB 各 section 统一降级为 error，调度任务 section 不依赖 DB 照常输出。
"""
from __future__ import annotations

import csv
import io
import subprocess
import uuid
from collections.abc import Callable
from datetime import date
from pathlib import Path

import duckdb
from backend.app.core_finance.field_normalization import (
    TRADABLE_STATUS_VALUES,
    tradable_status_sql_condition,
)
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_CURRENT_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import MATCHED_BASELINE_TABLE
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
)

RESULT_KIND = "data_health.overview"
RULE_VERSION = "rv_data_health_v1"
CACHE_VERSION = "cv_data_health_v1"

TABLE_OBSERVATION = "choice_stock_daily_observation"
TABLE_MARKET_BREADTH = "fact_market_breadth_daily"
TABLE_GATE_SUPPLEMENT = "fact_livermore_gate_supplement_daily"
TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
TABLE_ADJ_FACTOR = "stock_adjustment_factor"
TABLE_CONCEPT_INTERVAL = "choice_stock_concept_membership_interval"
TABLE_LIMIT_PRICE = "stock_limit_price_daily"

EXECUTION_HORIZONS = ("1d", "5d", "10d", "20d")

FRESHNESS_WARN_GAP_DAYS = 2
FRESHNESS_STALE_GAP_DAYS = 5
#: 未知非空词值占比预警线：正常停牌基数远低于此，占比跃升提示上游词表换代。
TRADESTATUS_UNKNOWN_WARN_RATIO = 0.05

_FRESHNESS_NOTE = (
    f"阈值：落后 >{FRESHNESS_WARN_GAP_DAYS} 天 warn、>{FRESHNESS_STALE_GAP_DAYS} 天 stale"
    "（自然日近似交易日，周末/长假会放大 1~2 天）"
)

_STATUS_SEVERITY = {"ok": 0, "warn": 1, "stale": 2, "missing": 3, "error": 4}

#: DB 打开整体失败时用于逐项降级的 (key, label) 清单（与 _build_db_sections 对齐）。
_DB_SECTION_SPECS: tuple[tuple[str, str], ...] = (
    ("observation_freshness", "行情观测新鲜度"),
    ("market_breadth_freshness", "市场宽度新鲜度"),
    ("gate_supplement_freshness", "门控补充新鲜度"),
    ("adjustment_factor_gap", "复权因子缺口"),
    ("stale_formula_rows", "策略公式版本"),
    ("concept_interval_staleness", "概念区间陈旧度"),
    ("limit_price_backfill", "涨跌停数值表"),
    ("tradestatus_vocabulary", "tradestatus 词表"),
)

_SCHTASKS_TIMEOUT_SECONDS = 15
#: LastResult 视为健康的取值：0 成功；267009 任务当前正在运行。
_SCHTASKS_OK_RESULTS = frozenset({"0", "0x0", "267009"})
_SCHEDULED_TASK_NAME_PREFIX = "MOSS-"


def data_health_envelope(
    *,
    duckdb_path: str | Path | None = None,
    today: str | None = None,
) -> dict[str, object] | None:
    """读取 + 逐项检查 + 打包 result_meta；库文件缺失时返回 None（路由映射 404）。"""
    path = Path(duckdb_path) if duckdb_path is not None else Path(get_settings().duckdb_path)
    if not path.is_file():
        return None
    today_text = _normalize_date(today) if today else date.today().isoformat()

    try:
        with read_only_connection(str(path), retries=5, retry_delay_seconds=0.2) as conn:
            sections = _build_db_sections(conn, today=today_text)
    except (OSError, duckdb.Error) as exc:
        reason = f"DuckDB 打开失败（可能被写进程短暂独占）：{exc}"
        sections = [_error_section(key, label, reason) for key, label in _DB_SECTION_SPECS]
    sections.append(_safe_section("scheduled_tasks", "调度任务", _scheduled_tasks_section))

    overall_status = _worst_status(sections)
    payload: dict[str, object] = {
        "as_of_date": today_text,
        "overall_status": overall_status,
        "threshold_note": _FRESHNESS_NOTE,
        "sections": sections,
    }
    meta = build_analytical_result_meta(
        trace_id=uuid.uuid4().hex,
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=f"sv_data_health_{today_text}",
        rule_version=RULE_VERSION,
        quality_flag="ok" if overall_status == "ok" else "warning",
        as_of_date=today_text,
        filters_applied={"today": today_text},
        tables_used=[
            TABLE_OBSERVATION,
            TABLE_MARKET_BREADTH,
            TABLE_GATE_SUPPLEMENT,
            TABLE_EXECUTION_HIST,
            MATCHED_BASELINE_TABLE,
            TABLE_ADJ_FACTOR,
            TABLE_CONCEPT_INTERVAL,
            TABLE_LIMIT_PRICE,
        ],
        evidence_rows=len(sections),
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=payload)


def _build_db_sections(conn: duckdb.DuckDBPyConnection, *, today: str) -> list[dict[str, object]]:
    tables = _table_names(conn)
    builders: tuple[tuple[str, str, Callable[[], dict[str, object]]], ...] = (
        (
            "observation_freshness",
            "行情观测新鲜度",
            lambda: _freshness_section(
                conn, tables, key="observation_freshness", label="行情观测新鲜度",
                table=TABLE_OBSERVATION, today=today,
            ),
        ),
        (
            "market_breadth_freshness",
            "市场宽度新鲜度",
            lambda: _freshness_section(
                conn, tables, key="market_breadth_freshness", label="市场宽度新鲜度",
                table=TABLE_MARKET_BREADTH, today=today,
            ),
        ),
        (
            "gate_supplement_freshness",
            "门控补充新鲜度",
            lambda: _freshness_section(
                conn, tables, key="gate_supplement_freshness", label="门控补充新鲜度",
                table=TABLE_GATE_SUPPLEMENT, today=today,
            ),
        ),
        ("adjustment_factor_gap", "复权因子缺口", lambda: _adjustment_gap_section(conn, tables, today=today)),
        ("stale_formula_rows", "策略公式版本", lambda: _stale_formula_section(conn, tables)),
        (
            "concept_interval_staleness",
            "概念区间陈旧度",
            lambda: _concept_interval_section(conn, tables, today=today),
        ),
        ("limit_price_backfill", "涨跌停数值表", lambda: _limit_price_section(conn, tables, today=today)),
        ("tradestatus_vocabulary", "tradestatus 词表", lambda: _tradestatus_section(conn, tables)),
    )
    return [_safe_section(key, label, builder) for key, label, builder in builders]


def _safe_section(key: str, label: str, builder: Callable[[], dict[str, object]]) -> dict[str, object]:
    try:
        return builder()
    except Exception as exc:  # noqa: BLE001 - 单项失败必须降级为 error section，不拖垮整体
        return _error_section(key, label, f"检查失败：{exc}")


def _section(
    key: str,
    label: str,
    *,
    status: str,
    metric: str | None = None,
    detail: str | None = None,
    as_of: str | None = None,
) -> dict[str, object]:
    return {"key": key, "label": label, "status": status, "metric": metric, "detail": detail, "as_of": as_of}


def _error_section(key: str, label: str, reason: str) -> dict[str, object]:
    return _section(key, label, status="error", detail=reason)


def _worst_status(sections: list[dict[str, object]]) -> str:
    worst = "ok"
    for section in sections:
        status = str(section.get("status") or "error")
        if _STATUS_SEVERITY.get(status, _STATUS_SEVERITY["error"]) > _STATUS_SEVERITY[worst]:
            worst = status
    return worst


def _freshness_status(gap_days: int) -> str:
    if gap_days > FRESHNESS_STALE_GAP_DAYS:
        return "stale"
    if gap_days > FRESHNESS_WARN_GAP_DAYS:
        return "warn"
    return "ok"


def _freshness_section(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    *,
    key: str,
    label: str,
    table: str,
    today: str,
) -> dict[str, object]:
    if table not in tables:
        return _section(key, label, status="missing", detail=f"表 {table} 不存在")
    row = conn.execute(f"select max(trade_date), count(*) from {table}").fetchone()
    max_date = _date_text(row[0] if row else None)
    row_count = int(row[1] or 0) if row else 0
    if not max_date:
        return _section(key, label, status="missing", metric="0 行", detail=f"{table} 无数据行")
    gap = _calendar_gap_days(today, max_date)
    if gap is None:
        return _section(key, label, status="error", as_of=max_date, detail=f"{table} 最新日期无法解析：{max_date}")
    detail = f"{table} max(trade_date)={max_date}，距今 {gap} 自然日，共 {row_count:,} 行。{_FRESHNESS_NOTE}"
    return _section(
        key,
        label,
        status=_freshness_status(gap),
        metric=f"{max_date} · 落后 {gap} 天",
        as_of=max_date,
        detail=detail,
    )


def _adjustment_gap_section(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    *,
    today: str,
) -> dict[str, object]:
    key, label = "adjustment_factor_gap", "复权因子缺口"
    if TABLE_EXECUTION_HIST not in tables:
        return _section(key, label, status="missing", detail=f"表 {TABLE_EXECUTION_HIST} 不存在")
    gap_selects = ", ".join(
        f"count(*) filter (where return_{horizon}_net is not null and return_{horizon}_net_adj is null)"
        for horizon in EXECUTION_HORIZONS
    )
    row = conn.execute(f"select {gap_selects} from {TABLE_EXECUTION_HIST}").fetchone()
    counts = {horizon: int(row[index] or 0) for index, horizon in enumerate(EXECUTION_HORIZONS)}
    total = sum(counts.values())

    factor_max: str | None = None
    factor_gap: int | None = None
    if TABLE_ADJ_FACTOR in tables:
        factor_row = conn.execute(f"select max(trade_date) from {TABLE_ADJ_FACTOR}").fetchone()
        factor_max = _date_text(factor_row[0] if factor_row else None) or None
        if factor_max:
            factor_gap = _calendar_gap_days(today, factor_max)

    per_horizon = "、".join(f"{horizon} 视角 {counts[horizon]:,}" for horizon in EXECUTION_HORIZONS)
    factor_text = (
        f"{TABLE_ADJ_FACTOR} 最新 {factor_max}（距今 {factor_gap} 自然日）"
        if factor_max
        else f"{TABLE_ADJ_FACTOR} 缺失/无数据（复权因子悬崖）"
    )
    detail = f"执行历史 return_*_net 非空但 *_net_adj 空：{per_horizon}（各视角独立计数）；{factor_text}"

    if factor_max is None:
        status = "missing"
    elif total == 0:
        status = "ok"
    elif factor_gap is not None and factor_gap > FRESHNESS_STALE_GAP_DAYS:
        # 缺口存在且因子表本身已陈旧：缺口只会随日推移扩大。
        status = "stale"
    else:
        status = "warn"
    return _section(key, label, status=status, metric=f"{total:,} 行缺复权", as_of=factor_max, detail=detail)


def _stale_formula_section(conn: duckdb.DuckDBPyConnection, tables: set[str]) -> dict[str, object]:
    key, label = "stale_formula_rows", "策略公式版本"
    # 延迟导入 tasks 层常量：只读路径导入本模块时不得触发 backend.app.tasks
    # 初始化（与 livermore_candidate_history_service 同一约束）。
    from backend.app.tasks.livermore_candidate_history_materialize import (
        EXECUTION_FORMULA_VERSION,
    )

    targets = (
        ("execution", TABLE_EXECUTION_HIST, EXECUTION_FORMULA_VERSION),
        ("matched_baseline", MATCHED_BASELINE_TABLE, MATCHED_BASELINE_CURRENT_FORMULA_VERSION),
    )
    parts: list[str] = []
    total_stale = 0
    checked = 0
    for name, table, current_version in targets:
        if table not in tables:
            parts.append(f"{name}: 表 {table} 缺失")
            continue
        row = conn.execute(
            f"select count(*), count(*) filter (where coalesce(trim(formula_version), '') <> ?) from {table}",
            [current_version],
        ).fetchone()
        row_count, stale_count = int(row[0] or 0), int(row[1] or 0)
        checked += 1
        total_stale += stale_count
        parts.append(f"{name}: 旧版 {stale_count:,}/{row_count:,}（当前 {current_version}）")
    if checked == 0:
        return _section(key, label, status="missing", detail="；".join(parts))
    detail = "；".join(parts) + "。旧版 = formula_version ≠ 当前版本常量（含缺失版本），待重物化收敛"
    return _section(
        key,
        label,
        status="stale" if total_stale > 0 else "ok",
        metric=f"{total_stale:,} 行旧版",
        detail=detail,
    )


def _concept_interval_section(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    *,
    today: str,
) -> dict[str, object]:
    key, label = "concept_interval_staleness", "概念区间陈旧度"
    if TABLE_CONCEPT_INTERVAL not in tables:
        return _section(key, label, status="missing", detail=f"表 {TABLE_CONCEPT_INTERVAL} 不存在")
    row = conn.execute(
        f"select max(last_observed_date), count(*) from {TABLE_CONCEPT_INTERVAL}"
    ).fetchone()
    max_observed = _date_text(row[0] if row else None)
    row_count = int(row[1] or 0) if row else 0
    if row_count == 0 or not max_observed:
        return _section(
            key,
            label,
            status="missing",
            metric="0 行",
            detail=f"{TABLE_CONCEPT_INTERVAL} 未构建/为空，theme_breakout 真实概念路径回退 proxy（§4.11）",
        )
    gap = _calendar_gap_days(today, max_observed)
    if gap is None:
        return _section(key, label, status="error", as_of=max_observed, detail=f"最新观测日无法解析：{max_observed}")
    detail = (
        f"max(last_observed_date)={max_observed}，距今 {gap} 自然日（§4.11 运维观察点：摄入停摆时"
        f"开放区间陈旧度单调增长），共 {row_count:,} 行。{_FRESHNESS_NOTE}"
    )
    return _section(
        key,
        label,
        status=_freshness_status(gap),
        metric=f"{max_observed} · 落后 {gap} 天",
        as_of=max_observed,
        detail=detail,
    )


def _limit_price_section(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    *,
    today: str,
) -> dict[str, object]:
    key, label = "limit_price_backfill", "涨跌停数值表"
    if TABLE_LIMIT_PRICE not in tables:
        return _section(key, label, status="missing", detail=f"表 {TABLE_LIMIT_PRICE} 不存在")
    row = conn.execute(f"select count(*), max(trade_date) from {TABLE_LIMIT_PRICE}").fetchone()
    row_count = int(row[0] or 0) if row else 0
    max_date = _date_text(row[1] if row else None)
    if row_count == 0:
        return _section(
            key,
            label,
            status="missing",
            metric="0 行",
            detail=f"{TABLE_LIMIT_PRICE} 未回填（0 行）；涨跌停三态判定降级 observation try_cast/布尔位",
        )
    gap = _calendar_gap_days(today, max_date) if max_date else None
    if gap is None:
        return _section(key, label, status="error", detail=f"{TABLE_LIMIT_PRICE} 最新日期无法解析：{max_date or '空'}")
    detail = f"{TABLE_LIMIT_PRICE} 共 {row_count:,} 行，max(trade_date)={max_date}，距今 {gap} 自然日。{_FRESHNESS_NOTE}"
    return _section(
        key,
        label,
        status=_freshness_status(gap),
        metric=f"{row_count:,} 行 · 落后 {gap} 天",
        as_of=max_date,
        detail=detail,
    )


def _tradestatus_section(conn: duckdb.DuckDBPyConnection, tables: set[str]) -> dict[str, object]:
    key, label = "tradestatus_vocabulary", "tradestatus 词表"
    if TABLE_OBSERVATION not in tables:
        return _section(key, label, status="missing", detail=f"表 {TABLE_OBSERVATION} 不存在")
    # 非空且不在可交易白名单 = 共享 SQL 口径的否定（空串折叠进 IN 列表首项，
    # 因此否定天然只命中非空值）。
    unknown_condition = f"not {tradable_status_sql_condition('tradestatus')}"
    row = conn.execute(
        f"select count(*), count(*) filter (where {unknown_condition}) from {TABLE_OBSERVATION}"
    ).fetchone()
    total, unknown = int(row[0] or 0), int(row[1] or 0)
    if total == 0:
        return _section(key, label, status="missing", metric="0 行", detail=f"{TABLE_OBSERVATION} 无数据行")
    ratio = unknown / total
    top_rows = conn.execute(
        f"""
        select lower(trim(cast(tradestatus as varchar))) as word, count(*) as n
        from {TABLE_OBSERVATION}
        where {unknown_condition}
        group by 1
        order by n desc
        limit 3
        """
    ).fetchall()
    top_text = "、".join(f"{row[0]} {int(row[1]):,}" for row in top_rows) or "无"
    detail = (
        f"非空且不在可交易白名单（{'/'.join(TRADABLE_STATUS_VALUES)}，词表 import 自 field_normalization）"
        f"共 {unknown:,} 行，占全表 {ratio:.2%}；Top: {top_text}。显式停牌词值同样不在白名单内、计入本口径"
        f"（fail-closed 判停牌）；占比异常升高提示上游状态词表换代（§4.10 观察点，"
        f"阈值 >{TRADESTATUS_UNKNOWN_WARN_RATIO:.0%} warn）"
    )
    return _section(
        key,
        label,
        status="warn" if ratio > TRADESTATUS_UNKNOWN_WARN_RATIO else "ok",
        metric=f"{unknown:,} 行 · {ratio:.2%}",
        detail=detail,
    )


def _scheduled_tasks_section() -> dict[str, object]:
    key, label = "scheduled_tasks", "调度任务"
    try:
        text = _run_schtasks_query()
    except Exception as exc:  # noqa: BLE001 - 非 Windows/无权限/超时统一降级，字段缺省
        return _section(
            key,
            label,
            status="error",
            detail=f"schtasks 查询失败（非 Windows/无权限/超时时字段缺省）：{exc}",
        )
    tasks = _parse_schtasks_csv(text)
    if not tasks:
        return _section(
            key,
            label,
            status="missing",
            metric="0 个任务",
            detail=f"未发现 {_SCHEDULED_TASK_NAME_PREFIX}* 计划任务（未安装或当前账户查询不到）",
        )
    unhealthy = [task for task in tasks if task["last_result"] not in _SCHTASKS_OK_RESULTS]
    detail = (
        "；".join(
            f"{task['task_name']}: 上次 {task['last_run_time'] or '—'}，LastResult {task['last_result'] or '—'}"
            for task in tasks
        )
        + "。LastResult 0 与 267009（正在运行）视为正常，267011 = 从未运行"
    )
    return _section(
        key,
        label,
        status="ok" if not unhealthy else "warn",
        metric=f"{len(tasks) - len(unhealthy)}/{len(tasks)} 正常",
        detail=detail,
    )


def _run_schtasks_query() -> str:
    """subprocess 调 schtasks（仅 Windows）；输出按控制台代码页解码。"""
    completed = subprocess.run(  # noqa: S603 - 固定参数常量，无用户输入
        ["schtasks", "/query", "/fo", "csv", "/v"],
        capture_output=True,
        timeout=_SCHTASKS_TIMEOUT_SECONDS,
        check=True,
    )
    raw = completed.stdout or b""
    # 中文 Windows 控制台输出为 ANSI 代码页（GBK 等），utf-8 解码失败时回退 mbcs。
    for encoding in ("utf-8-sig", "mbcs"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_schtasks_csv(text: str) -> list[dict[str, str]]:
    """按固定列序解析 verbose CSV，取 MOSS-* 任务。

    列名随系统语言本地化，但列序稳定：1=TaskName、2=Next Run Time、
    3=Status、5=Last Run Time、6=Last Result。表头行的第 1 列不以反斜杠
    开头，天然被过滤；多触发器任务的重复行按任务名去重保首行。
    """
    tasks: dict[str, dict[str, str]] = {}
    for record in csv.reader(io.StringIO(text)):
        if len(record) < 7:
            continue
        task_path = str(record[1] or "").strip()
        if not task_path.startswith("\\"):
            continue
        task_name = task_path.rsplit("\\", 1)[-1]
        if not task_name.startswith(_SCHEDULED_TASK_NAME_PREFIX) or task_name in tasks:
            continue
        tasks[task_name] = {
            "task_name": task_name,
            "next_run_time": str(record[2] or "").strip(),
            "schtasks_status": str(record[3] or "").strip(),
            "last_run_time": str(record[5] or "").strip(),
            "last_result": str(record[6] or "").strip(),
        }
    return list(tasks.values())


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _date_text(value: object) -> str:
    text = str(value or "").strip()
    return text[:10] if text else ""


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
