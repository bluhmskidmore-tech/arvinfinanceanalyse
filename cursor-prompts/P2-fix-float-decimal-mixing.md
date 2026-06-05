# P2 修复：float/Decimal 混用 + _f() 静默归零

## 背景

**文件**：`backend/app/core_finance/pnl_attribution/workbench.py`

两个问题：
1. `_f()` 函数（第 29-37 行）把所有 Decimal 转成 float，精度损失不可逆，且转换失败静默返回 `0.0`
2. 归因计算链全程用 float，与 `bond_four_effects.py` 用 Decimal 的口径不一致

## 问题 1：`_f()` 转换失败静默归零

**当前代码**（第 29-37 行）：
```python
def _f(x: object | None) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0  # 静默归零，掩盖数据问题
```

**修复**：转换失败时记录 WARNING，而不是静默归零：
```python
def _f(x: object | None, _field_hint: str = "") -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(x)
    except (TypeError, ValueError):
        logger.warning("_f: cannot convert %r (type=%s) to float%s, using 0.0",
                       x, type(x).__name__,
                       f" [field={_field_hint}]" if _field_hint else "")
        return 0.0
```

注意：`_field_hint` 是可选参数，不改现有调用方，只在新增调用时传入。

## 问题 2：`_weighted_ytm_decimal()` 命名误导

**当前代码**（第 123-128 行）：
```python
def _weighted_ytm_decimal(rows: list[dict[str, Any]]) -> float | None:
    num = sum(_f(r.get("market_value")) * _f(r.get("ytm")) for r in rows)
    den = sum(_f(r.get("market_value")) for r in rows)
    if den <= 0:
        return None
    return num / den
```

函数名叫 `_decimal` 但返回 `float`，误导调用方。

**修复**：重命名为 `_weighted_ytm_float`，并在文件内所有调用处同步更新。

## 问题 3：`build_campisi_attribution` 中 `days / 365.0` 固定年

**当前代码**（第 760 行）：
```python
income = mv * coupon_dec * (days / 365.0)
```

**修复**：改为 `days / 366.0 if _is_leap_year_period(period_start, period_end) else days / 365.0`。

但这个改动较复杂，**先不做**，只在该行加注释：
```python
income = mv * coupon_dec * (days / 365.0)  # TODO: use actual day count convention (ACT/365 vs ACT/366)
```

## 执行顺序

1. 修改 `_f()` 加 WARNING 日志（不改签名，向后兼容）
2. 重命名 `_weighted_ytm_decimal` → `_weighted_ytm_float`，grep 所有调用点一并改
3. 加 `days / 365.0` 的 TODO 注释

## 验证

修改后搜索文件确认：
- `_weighted_ytm_decimal` 已不存在（全部改为 `_weighted_ytm_float`）
- `_f()` 的 except 分支有 `logger.warning`
