"""choice_stock_daily_observation 两代 vendor 的 amount/volume 单位归一化 SQL 表达式。

单位契约(权威定义见 docs/data_contracts.md §4.10):

- tushare 单位代际(``vendor_version`` 含 ``tushare``):``amount`` = 千元、
  ``volume`` = 手(100 股)。覆盖主摄入模式 ``vv_choice_tushare_stock_*``
  (2024-01-02 ~ 2025-12-31)与盘后补充模式 ``vv_livermore_supplement_tushare_sina_*``
  (数据来自 Tushare pro.daily,同为千元/手口径)。
- choice_native 代际(``vv_choice_stock_*`` 前缀,2026-01-05 起):``amount`` = 元、
  ``volume`` = 股。
- ``vendor_version`` 为 NULL 或空白(空字符串/纯空格):无法定标,fail-closed 输出
  NULL,调用方应统计并告警,不得猜测单位。

第三代/未知 vendor fail-closed:非空但不匹配上述任一已知代际模式的 vendor_version
同样无法定标,``amount`` / ``volume`` 一律输出 NULL(禁止按 native 透传猜测单位)。
若未来引入新数据源,必须同步登记:本模块显式匹配、摄入侧白名单
(backend/app/tasks/choice_stock_materialize.py 的
DAILY_OBSERVATION_VENDOR_VERSION_PATTERNS)与 docs/data_contracts.md §4.10。

消费方必须经本模块表达式读取"元 / 股"口径;禁止对原始列做绝对阈值比较或跨代际
时序计算(均线、量比等)。价格类列(open/high/low/close_value)与百分点列
(turn/pctchange/amplitude)两代口径一致,不适用本换算。
"""

from __future__ import annotations

TUSHARE_VENDOR_LIKE = "%tushare%"
# choice_native 主摄入模式前缀(vv_choice_stock_{yyyymmdd}_{hash});escape 下划线避免
# LIKE 单字符通配误匹配。
NATIVE_VENDOR_LIKE = r"vv\_choice\_stock\_%"

_TUSHARE_AMOUNT_MULTIPLIER = "1000.0"  # 千元 -> 元
_TUSHARE_VOLUME_MULTIPLIER = "100.0"  # 手 -> 股


def _prefixed(column: str, table_alias: str) -> str:
    return f"{table_alias}.{column}" if table_alias else column


def _vendor_norm_sql(table_alias: str) -> str:
    """空白 vendor_version(空字符串/纯空格)与 NULL 同等视为无法定标。"""

    vendor = _prefixed("vendor_version", table_alias)
    return f"nullif(trim({vendor}), '')"


def _normalized_sql(column: str, multiplier: str, *, table_alias: str, alias: str | None) -> str:
    value = _prefixed(column, table_alias)
    vendor = _vendor_norm_sql(table_alias)
    expr = (
        f"case when {vendor} is null then cast(null as double) "
        f"when lower({vendor}) like '{TUSHARE_VENDOR_LIKE}' then {value} * {multiplier} "
        f"when lower({vendor}) like '{NATIVE_VENDOR_LIKE}' escape '\\' then {value} "
        f"else cast(null as double) end"
    )
    return f"{expr} as {alias}" if alias else expr


def amount_rmb_sql(*, table_alias: str = "", alias: str | None = "amount_rmb") -> str:
    """归一化为"元"口径的成交额表达式;alias=None 返回裸表达式。"""

    return _normalized_sql("amount", _TUSHARE_AMOUNT_MULTIPLIER, table_alias=table_alias, alias=alias)


def volume_shares_sql(*, table_alias: str = "", alias: str | None = "volume_shares") -> str:
    """归一化为"股"口径的成交量表达式;alias=None 返回裸表达式。"""

    return _normalized_sql("volume", _TUSHARE_VOLUME_MULTIPLIER, table_alias=table_alias, alias=alias)


def scale_unknown_sql(column: str, *, table_alias: str = "", alias: str | None = None) -> str:
    """值非空但 vendor_version 无法定标(NULL/空白/未知模式)的布尔表达式,供调用方统计告警。

    括号包裹整个表达式,避免 SQL ``NOT`` 优先级高于 ``AND`` 导致调用方拼接
    ``where not <expr>`` 时被错误解析为 ``(not a) and b``。
    """

    value = _prefixed(column, table_alias)
    vendor = _vendor_norm_sql(table_alias)
    expr = (
        f"({value} is not null and ({vendor} is null or ("
        f"lower({vendor}) not like '{TUSHARE_VENDOR_LIKE}' "
        f"and lower({vendor}) not like '{NATIVE_VENDOR_LIKE}' escape '\\')))"
    )
    return f"{expr} as {alias}" if alias else expr
