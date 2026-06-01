# Cursor Prompt: Phase 2 P1 — PnL by-business 契约对齐

> 粘贴到 Cursor chat 执行。

---

## 背景

V3 的 `/api/pnl/by-business`、`/api/pnl/by-business-ytd`、`/api/pnl/yearly-summary` 路由已存在，
但契约形状与 V1 有差异，前端无法直接消费。本任务对齐契约，不重写业务逻辑。

**先读以下文件再动手：**
- `AGENTS.md`
- `CLAUDE.md`
- `backend/app/AGENTS.md`（如存在）
- `backend/app/api/routes/pnl.py`
- `backend/app/services/pnl_service.py`（或实际 pnl by-business 服务文件）
- `backend/app/schemas/`（grep PnLByBusiness 相关 schema）

---

## V1 契约（目标形状）

### `GET /api/pnl/by-business?report_date=YYYY-MM-DD`

```python
class BusinessTypePnLItem(BaseModel):
    business_type: str
    interest_income: float      # 利息收入（元）
    fair_value_change: float    # 公允价值变动（元）
    capital_gain: float         # 资本利得（元）
    total_pnl: float            # 合计（元）
    proportion: float | None    # 占比（0~1）
    assets_count: int           # 持仓数量

class PnLByBusinessResponse(BaseModel):
    report_date: str
    total_pnl: float
    items: list[BusinessTypePnLItem]
```

### `GET /api/pnl/by-business-ytd?year=2026`

同 `PnLByBusinessResponse`，`report_date` 改为 `period_label`（如 "2026 年累计"）。

### `GET /api/pnl/yearly-summary?year=2026&business_type=利率债`

```python
class YearlyBusinessSummaryPoint(BaseModel):
    ym: str                     # "2026-01"
    interest_income: float
    fair_value_change: float
    capital_gain: float
    total_pnl: float

class YearlyBusinessSummaryResponse(BaseModel):
    year: int
    business_type: str
    points: list[YearlyBusinessSummaryPoint]
```

---

## 任务

### Step 1：确认 V3 现状

先运行：

```bash
cd F:/MOSS-V3
grep -n "by.business\|yearly.summary\|PnLByBusiness\|YearlySummary" \
  backend/app/api/routes/pnl.py \
  backend/app/schemas/*.py \
  backend/app/services/pnl_by_business_service.py 2>/dev/null | head -60
```

确认：
- 路由是否已挂载
- 现有 schema 字段与 V1 目标的差距
- 服务层返回的实际字段名

### Step 2：对齐 schema

**修改文件：** `backend/app/schemas/pnl.py`（或实际 schema 文件）

确保以下类型存在且字段完整：
- `BusinessTypePnLItem`：`business_type / interest_income / fair_value_change / capital_gain / total_pnl / proportion / assets_count`
- `PnLByBusinessResponse`：`report_date / total_pnl / items`
- `YearlyBusinessSummaryPoint`：`ym / interest_income / fair_value_change / capital_gain / total_pnl`
- `YearlyBusinessSummaryResponse`：`year / business_type / points`

所有金额字段用 `Numeric`（对齐 V3 规范），同时保留 `float` 兼容路径（用 `_coerce` validator，参考 `executive_dashboard.py` 模式）。

### Step 3：对齐服务层返回

**修改文件：** `backend/app/services/pnl_by_business_service.py`（或实际文件）

确保服务层返回的 dict 键名与 schema 字段一致：
- `business_type`（不是 `name` 或 `type`）
- `interest_income / fair_value_change / capital_gain / total_pnl`（不是缩写）
- `proportion`（可为 None）
- `assets_count`（不是 `count`）

用 `build_result_envelope` 包装，`basis="analytical"`。

### Step 4：对齐路由响应

**修改文件：** `backend/app/api/routes/pnl.py`

确认三个路由返回 `{ result_meta, result }` 信封，`result` 字段符合上述 schema。

### Step 5：测试

**新建或修改：** `tests/test_pnl_by_business_contract.py`

```python
def test_pnl_by_business_response_shape():
    # mock service，断言 result 有 report_date / total_pnl / items
    # 断言 items[0] 有 business_type / interest_income / total_pnl / assets_count

def test_pnl_yearly_summary_response_shape():
    # 断言 result 有 year / business_type / points
    # 断言 points[0] 有 ym / total_pnl

def test_pnl_by_business_ytd_response_shape():
    # 断言 result 有 total_pnl / items
```

### 验证

```bash
python -m pytest tests/test_pnl_by_business_contract.py -q
cd frontend && npm run typecheck
```

---

## 绝对禁止

- 不重写 pnl_by_business_service 的业务逻辑（只改字段名对齐）
- 不改 DuckDB 表结构
- 不碰无关路由（pnl/bridge、pnl/data 等）
- 不引入新依赖

---

## 完成后输出格式

```
Aligned pnl by-business contract.

Changed files:
- ...

What changed:
- ...

Validation:
- command -> result
```
