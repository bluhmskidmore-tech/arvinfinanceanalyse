# Cursor Prompt: Phase 2 缺口 P0 — 后端四个端点

> 粘贴到 Cursor chat 执行。后端先行，前端另有单独 prompt。

---

## 任务目标

在 `F:\MOSS-V3` 中补齐以下四个 P0 阻塞端点的后端实现：

| # | 端点 | 现状 | 目标 |
|---|------|------|------|
| 1 | `GET /api/dashboard/core_metrics` | 不存在 | 新建，返回债券投资/同业资产/同业负债三张 KPI 卡 |
| 2 | `GET /api/dashboard/daily-changes` | 不存在 | 新建，返回 day/week/month 三个周期的余额变动 |
| 9 | `GET /api/positions/counterparty/bonds` | 已存在但缺 `cr10_ratio` | 在 CounterpartyStatsResponse 补 cr10_ratio 字段 |
| 10 | `GET /api/bond-dashboard/business-type-metrics` | 不存在 | 挂到 bond_dashboard_service，返回业务类型加权指标 |

**先读以下文件再动手：**
- `AGENTS.md`
- `CLAUDE.md`
- `backend/app/AGENTS.md`（如存在）
- `docs/handoff/2026-04-18-backend-endpoint-handoff.md`

---

## 执行前必做

```bash
git status --short
```

仓库有无关脏文件，**只改本任务列出的文件**。

---

## 端点 #10：`/api/bond-dashboard/business-type-metrics`（最简单，先做）

### 数据来源

与现有 bond-dashboard 同源：`fact_formal_bond_analytics_daily` 表，通过 `BondAnalyticsRepository`。

### 新建文件

无需新建文件，挂到现有模块。

### 修改文件

**`backend/app/repositories/bond_analytics_repo.py`**

新增方法：

```python
def fetch_business_type_metrics(self, report_date: str) -> list[dict]:
    """按 bond_type 聚合：market_value、weighted_avg_ytm、weighted_avg_duration。"""
```

SQL 参考（按现有 repo 风格写，用 DuckDB）：

```sql
SELECT
    bond_type                                          AS name,
    SUM(market_value)                                  AS market_value,
    SUM(market_value * ytm) / NULLIF(SUM(market_value), 0)        AS weighted_avg_ytm,
    SUM(market_value * modified_duration) / NULLIF(SUM(market_value), 0) AS weighted_avg_duration,
    MAX(duration_source)                               AS duration_source
FROM fact_formal_bond_analytics_daily
WHERE report_date = ?
GROUP BY bond_type
ORDER BY market_value DESC
```

字段名以实际表结构为准，先 `DESCRIBE fact_formal_bond_analytics_daily` 确认列名。

**`backend/app/services/bond_dashboard_service.py`**

新增函数：

```python
def get_bond_dashboard_business_type_metrics(report_date: date) -> dict:
    """返回 formal result envelope，result 包含 report_date + items 列表。"""
```

每个 item：
```python
{
    "name": str,
    "market_value": str,          # Decimal 字符串，单位元
    "weighted_avg_ytm_pct": str,  # 百分数字符串，如 "2.55"
    "weighted_avg_duration": str, # 年，如 "3.21"
    "duration_source": str,
}
```

用现有 `_amt()` / `_rate()` 格式化，用 `build_formal_result_envelope_from_lineage` 包装，lineage 走 `_facts_lineage()`。

**`backend/app/api/routes/bond_dashboard.py`**

新增路由：

```python
@router.get("/business-type-metrics")
def business_type_metrics(report_date: date = Query(...)):
    return get_bond_dashboard_business_type_metrics(report_date)
```

**`tests/test_bond_dashboard_api_contract.py`**

新增测试：

```python
def test_business_type_metrics_returns_envelope():
    # mock repo，断言 result.items 非空，每项有 name/market_value/weighted_avg_ytm_pct
```

### 验证

```bash
python -m pytest tests/test_bond_dashboard_api_contract.py -q
```

---

## 端点 #9：`/api/positions/counterparty/bonds` 补 cr10_ratio

### 现状

`CounterpartyStatsResponse` 已存在，`aggregate_counterparty_bonds` 已实现，但缺 CR10 集中度字段。

### 修改文件

**`backend/app/schemas/positions.py`**

在 `CounterpartyStatsResponse` 中新增：

```python
cr10_ratio: str | None = None   # CR10 集中度，如 "68.50%"，无数据时 None
```

**`backend/app/repositories/positions_repo.py`**（或实际 repo 文件，先确认）

在 `aggregate_counterparty_bonds` 中补充 CR10 计算：

```python
# CR10 = top 10 对手方市值 / 总市值
# 在现有聚合结果基础上计算，不需要额外 SQL
top10_mv = sum(item["market_value"] for item in rows[:10])
total_mv = sum(item["market_value"] for item in rows)
cr10_ratio = f"{top10_mv / total_mv * 100:.2f}%" if total_mv else None
```

在返回的 dict 中加入 `cr10_ratio`。

**`tests/test_positions_api_contract.py`**（如存在）或新建测试

断言 `cr10_ratio` 字段存在且格式正确。

### 验证

```bash
python -m pytest tests/ -k "counterparty" -q
```

---

## 端点 #1：`GET /api/dashboard/core_metrics`

### 契约形状（对齐 V1）

```python
class CoreMetricsCardData(BaseModel):
    total_amount: Numeric
    weighted_avg_rate: Numeric
    change_amount: Numeric
    change_pct: Numeric
    top_3_details: list[dict]   # [{"name": str, "amount": str, "rate": str}]

class CoreMetricsResponse(BaseModel):
    report_date: str
    bond_investments: CoreMetricsCardData
    interbank_assets: CoreMetricsCardData
    interbank_liabilities: CoreMetricsCardData
```

### 数据来源

- 债券投资：`fact_formal_bond_analytics_daily`（已有，BondAnalyticsRepository）
- 同业资产/负债：`fact_formal_tyw_balance_daily` 或 `position_interbank`（先确认 V3 实际表名）

**实现前先运行：**

```bash
python - <<'PY'
import duckdb, os
db_path = os.environ.get("DUCKDB_PATH", "data/moss_v3.duckdb")
con = duckdb.connect(db_path, read_only=True)
print(con.execute("SHOW TABLES").fetchall())
PY
```

确认表名后再写 SQL。

### 新建文件

- `backend/app/services/dashboard_service.py`
- `backend/app/api/routes/dashboard.py`
- `backend/app/schemas/dashboard.py`（放 CoreMetricsCardData / CoreMetricsResponse）
- `tests/test_dashboard_api_contract.py`

### `dashboard_service.py` 实现要求

```python
def get_core_metrics(report_date: str | None = None) -> dict:
    # 1. resolve report_date（None → 最新可用日期）
    # 2. 查询前一个可用日期（用于 change_amount / change_pct）
    # 3. 组装三张卡
    # 4. 用 build_result_envelope 包装（basis="analytical"）
```

- `change_amount` = 当日 - 前日，`change_pct` = change_amount / 前日
- `top_3_details` = 按 market_value 排序前三条（债券按 bond_type，同业按 counterparty）
- 所有金额用 `Numeric`，利率用 `Numeric`（unit="percent"）

### `dashboard.py` 路由

```python
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/core_metrics")
def core_metrics(report_date: str | None = None) -> dict:
    return get_core_metrics(report_date)
```

### 注册路由

在 `backend/app/main.py` 中注册：

```python
from backend.app.api.routes.dashboard import router as dashboard_router
app.include_router(dashboard_router)
```

### 测试

```python
def test_core_metrics_returns_three_cards():
    # mock repo，断言 result 有 bond_investments/interbank_assets/interbank_liabilities
    # 断言每张卡有 total_amount/weighted_avg_rate/change_amount/change_pct/top_3_details

def test_core_metrics_resolves_latest_date_when_none():
    # report_date=None 时返回最新可用日期
```

### 验证

```bash
python -m pytest tests/test_dashboard_api_contract.py -q
```

---

## 端点 #2：`GET /api/dashboard/daily-changes`

### 契约形状

```python
class DailyChangePeriod(BaseModel):
    period: Literal["day", "week", "month"]
    bond_investments_change: Numeric
    interbank_assets_change: Numeric
    interbank_liabilities_change: Numeric
    net_change: Numeric

class DailyChangesResponse(BaseModel):
    report_date: str
    periods: list[DailyChangePeriod]   # day / week / month 三条
```

### 实现

在 `dashboard_service.py` 新增：

```python
def get_daily_changes(report_date: str | None = None) -> dict:
    # 对 day/week/month 三个周期分别计算变动
    # day = 当日 vs 前1个可用日
    # week = 当日 vs 前5个可用日（或自然周起始）
    # month = 当日 vs 当月第一个可用日
```

在 `dashboard.py` 新增路由：

```python
@router.get("/daily-changes")
def daily_changes(report_date: str | None = None) -> dict:
    return get_daily_changes(report_date)
```

### 测试

```python
def test_daily_changes_returns_three_periods():
    # 断言 result.periods 有三条，period 分别为 day/week/month
```

### 验证

```bash
python -m pytest tests/test_dashboard_api_contract.py -q
```

---

## 最终回归验证

```bash
python -m pytest tests/test_dashboard_api_contract.py tests/test_bond_dashboard_api_contract.py -k "business_type or core_metrics or daily_changes or counterparty" -q
python -m pytest tests/test_agent_api_contract.py tests/test_agent_intent_routing.py -q
```

期望：全部 passed，无回归。

---

## 绝对禁止

- 不改 database schema（不加新表，不改现有表结构）
- 不改 auth / queue / global SDK
- 不在 API 层做金融计算（计算逻辑放 service 或 core_finance）
- 不引入新的外部依赖
- 不碰无关脏文件

---

## 完成后输出格式

```
Implemented Phase 2 gap P0 backend endpoints.

Changed files:
- ...

What changed:
- ...

Validation:
- command -> result

Known risks / follow-up:
- ...
```
