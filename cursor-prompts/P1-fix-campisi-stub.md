# P1 修复：Campisi spread/selection STUB（Phase 3 集成准备）

## 背景

**文件**：`backend/app/core_finance/pnl_attribution/workbench.py`，第 762-764 行：

```python
spread = 0.0  # STUB: requires credit curve data, not yet implemented
total_ret = income + tre + spread
sel = 0.0     # STUB: depends on spread, not yet implemented
```

`build_campisi_attribution()` 函数中，信用利差效应和选择效应硬编码为 0，
导致信用类资产的归因不完整，`selection_effect` 吸收了所有利差变动。

## 当前数据流

函数签名（约第 700 行附近）：
```python
def build_campisi_attribution(
    bond_rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    report_date: date,
    period_start: date,
    period_end: date,
    dy: float,  # benchmark yield change（小数，如 0.001 = 1bp）
) -> dict[str, Any]:
```

`summaries` 中每条记录包含 `asset_class`、`market_value`、`duration`、`weight`。
`bond_rows` 中每条记录包含单券数据，包括 `asset_class_std`、`market_value`、`coupon_rate`、`ytm`、`credit_spread`（如果有）。

## 修复要求

### 步骤 1：从 bond_rows 提取加权利差变动

在 STUB 位置，尝试从 `bond_rows` 中计算该资产类别的加权平均利差变动：

```python
# 从 bond_rows 提取该 asset_class 的利差数据
rows = [r for r in bond_rows if str(r.get("asset_class_std") or "") == ac]
spread_change_rows = [r for r in rows if r.get("credit_spread_change") is not None]

if spread_change_rows and mv > 0:
    # 市值加权平均利差变动（单位：小数，如 0.001 = 10bp）
    weighted_ds = sum(_f(r.get("market_value")) * _f(r.get("credit_spread_change")) for r in spread_change_rows)
    total_mv_with_spread = sum(_f(r.get("market_value")) for r in spread_change_rows)
    ds = weighted_ds / total_mv_with_spread if total_mv_with_spread > 0 else 0.0
    spread = -mv * d * ds  # 与 treasury_effect 同口径：-MV * Duration * Δspread
    coverage_pct = total_mv_with_spread / mv * 100.0
    if coverage_pct < 80.0:
        logger.warning(
            "Campisi spread: asset_class=%s, spread coverage=%.1f%% (<80%%), result may be unreliable",
            ac, coverage_pct,
        )
else:
    spread = 0.0
    ds = 0.0
```

### 步骤 2：selection_effect 改为残差

```python
# selection = total_actual_return - income - treasury - spread
# 需要从 bond_rows 获取实际 total_return
actual_return_rows = [r for r in rows if r.get("total_return") is not None]
if actual_return_rows:
    actual_total = sum(_f(r.get("total_return")) for r in actual_return_rows)
    sel = actual_total - income - tre - spread
else:
    sel = 0.0
```

### 步骤 3：更新 warnings 字段

- 如果所有资产类别都有利差数据：移除 STUB warning
- 如果部分有：warning 改为 "spread_effect 基于 X% 市值覆盖率计算，未覆盖部分归入 selection_effect"
- 如果完全没有：保留原 warning

### 步骤 4：在返回 dict 中新增 `spread_data_coverage_pct` 字段

```python
"spread_data_coverage_pct": round(overall_coverage, 2),  # 0-100
```

## 约束

- 不改函数签名
- 不改返回 dict 的现有 key（只新增 `spread_data_coverage_pct`）
- `_f()` 辅助函数已存在（第 29 行），直接使用
- 如果 `credit_spread_change` 字段在 bond_rows 中不存在（字段名可能不同），
  先搜索 bond_rows 的实际字段名（grep `credit_spread` 在整个 backend 目录），
  使用正确的字段名

## 验证

修改后确认：
1. 当 bond_rows 中有 `credit_spread_change` 时，spread 不为 0
2. `sel = actual_total - income - tre - spread` 是残差，不是 0
3. warnings 字段根据覆盖率动态生成
