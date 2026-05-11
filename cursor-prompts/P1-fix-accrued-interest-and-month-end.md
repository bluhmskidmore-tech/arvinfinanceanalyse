# P1 修复：应计利息静默归零 + 月末截断不可复现

## 任务 1：应计利息缺失时的处理（`bond_four_effects.py`）

**文件**：`backend/app/core_finance/bond_four_effects.py`

**问题**：`has_accrued = ai_start_raw is not None and ai_end_raw is not None`（第 85 行）。
当应计利息字段缺失时，`ai_start` 和 `ai_end` 静默归零，导致 `total_return` 用净价变动代替全价变动，
对折溢价债券产生 5-10% 的系统性误差（代码注释第 71 行已承认）。

**当前行为**：
```python
has_accrued = ai_start_raw is not None and ai_end_raw is not None
ai_start = safe_decimal(ai_start_raw) if has_accrued else Decimal("0")
ai_end = safe_decimal(ai_end_raw) if has_accrued else Decimal("0")
```

**修复要求**：
1. 逻辑不变，但在 `diagnostics` 中区分两种情况：
   - 两个字段都有：`has_accrued = True`，正常全价计算
   - 只有一个字段有值：追加 `"accrued_interest_partial"` 到 diagnostics，并用 WARNING 记录（含 bond_code），`has_accrued = False`
   - 两个都没有：追加 `"accrued_interest_missing"`（比现在的 `"accrued_interest_fallback_to_zero"` 更精确）
2. 将现有的 `"accrued_interest_fallback_to_zero"` 改为 `"accrued_interest_missing"`（保持向后兼容，调用方检查 diagnostics 的地方一并更新）
3. WARNING 日志中加入 `ai_start_raw` 和 `ai_end_raw` 的值，方便排查数据问题

**不要改**：函数签名、返回类型、`has_accrued` 在返回 dict 中的 key。

---

## 任务 2：月末截断导致历史数据不可复现（`adb_analytics.py`）

**文件**：`backend/app/core_finance/adb_analytics.py`

**问题**：`month_date_range()` 第 261 行：
```python
return month_start, min(month_end, date.today())
```
历史月份的月末被 `date.today()` 截断，导致同一历史查询在不同日期返回不同结果，不可复现。

**修复要求**：
1. 移除 `min(month_end, date.today())` 的截断逻辑
2. 改为：直接返回 `(month_start, month_end)`，不做截断
3. 调用方如果需要"不超过今天"的语义，应在调用处自行处理
4. 搜索 `month_date_range` 的所有调用点（在 `adb_analytics.py` 内及其他文件），
   确认是否有调用方依赖截断行为——如果有，在调用处加 `min(..., date.today())`，
   并加注释说明为什么需要截断

**验证**：修改后，`month_date_range(2024, 1)` 应始终返回 `(date(2024, 1, 1), date(2024, 1, 31))`，
无论今天是什么日期。
