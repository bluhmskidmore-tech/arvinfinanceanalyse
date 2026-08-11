"""choice_stock_daily_observation 两代 vendor 的 amount/volume 单位归一化 SQL 表达式。

单位契约(权威定义见 docs/data_contracts.md §4.10):

- tushare 代际(``vendor_version`` 含 ``tushare``,2024-01-02 ~ 2025-12-31):
  ``amount`` = 千元、``volume`` = 手(100 股)。
- choice_native 代际(2026-01-05 起):``amount`` = 元、``volume`` = 股。
- ``vendor_version`` 为 NULL 或空白(空字符串/纯空格):无法定标,fail-closed 输出
  NULL,调用方应统计并告警,不得猜测单位。

消费方必须经本模块表达式读取"元 / 股"口径;禁止对原始列做绝对阈值比较或跨代际
时序计算(均线、量比等)。价格类列(open/high/low/close_value)与百分点列
(turn/pctchange/amplitude)两代口径一致,不适用本换算。

第三代 vendor 注意:非空且不含 ``tushare`` 的未知 vendor_version 会按 choice_native
(元/股)透传——若未来引入第三代数据源,必须同步回改本模块与 docs/data_contracts.md
§4.10,并在摄入侧守卫 distinct vendor_version 全部匹配已知代际模式。
"""

from __future__ import annotations

TUSHARE_VENDOR_LIKE = "%tushare%"

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
        f"else {value} end"
    )
    return f"{expr} as {alias}" if alias else expr


def amount_rmb_sql(*, table_alias: str = "", alias: str | None = "amount_rmb") -> str:
    """归一化为"元"口径的成交额表达式;alias=None 返回裸表达式。"""

    return _normalized_sql("amount", _TUSHARE_AMOUNT_MULTIPLIER, table_alias=table_alias, alias=alias)


def volume_shares_sql(*, table_alias: str = "", alias: str | None = "volume_shares") -> str:
    """归一化为"股"口径的成交量表达式;alias=None 返回裸表达式。"""

    return _normalized_sql("volume", _TUSHARE_VOLUME_MULTIPLIER, table_alias=table_alias, alias=alias)


def scale_unknown_sql(column: str, *, table_alias: str = "", alias: str | None = None) -> str:
    """值非空但 vendor_version 缺失或空白(无法定标)的布尔表达式,供调用方统计告警。

    括号包裹整个表达式,避免 SQL ``NOT`` 优先级高于 ``AND`` 导致调用方拼接
    ``where not <expr>`` 时被错误解析为 ``(not a) and b``。
    """

    value = _prefixed(column, table_alias)
    vendor = _vendor_norm_sql(table_alias)
    expr = f"({value} is not null and {vendor} is null)"
    return f"{expr} as {alias}" if alias else expr
