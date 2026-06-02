# Cursor Prompt: Phase 2 P1 — risk-buckets + bonds-monthly

> 粘贴到 Cursor chat 执行。两个端点工作量都较大，按顺序做。

---

## 背景

V3 中：
- `/api/risk/buckets` 路由存在但永远返回 503（`_raise_liability_analytics_not_promoted`）
- `/api/bonds/monthly` 路由不存在

本任务实现这两个端点，复用 V3 已有的 bond_analytics_repo 和 bond_dashboard_service 能力。

**先读以下文件再动手：**
- `AGENTS.md`、`CLAUDE.md`、`backend/app/AGENTS.md`
- `backend/app/api/routes/liability_analytics.py`
- `backend/app/api/routes/bond_dashboard.py`
- `backend/app/services/bond_dashboard_service.py`
- `backend/app/repositories/bond_analytics_repo.py`

---

## 端点 #8：`GET /api/risk/buckets`

### V1 契约（目标形状）

```python
# V1 返回：负债结构 + 债券分布
{
  "report_date": "2026-03-31",
  "bonds_cashflow_buckets": [{"bucket": "7天内", "avg_balance": 1234567.0}, ...],
  "bonds_duration_buckets": [{"bucket": "0-1年", "avg_balance": ...}, ...],
  "bonds_rate_buckets":     [{"bucket": "<2%",  "avg_balance": ...}, ...],
}
```

### V3 实现策略

V3 已有 `bond_analytics_repo` 中的 `fetch_dashboard_maturity_structure`（期限分桶）和
`fetch_dashboard_risk_indicators`（风险指标），可以直接复用。

**不要**复用 V1 的负债桶逻辑（`liability_analytics_repo` 数据面未完全就绪），
只实现债券侧三个桶，负债桶返回空列表并在 `result_meta` 中标注 `fallback_mode="partial"`。

### 实现步骤

**Step 1：在 `bond_analytics_repo.py` 新增两个方法**

```python
def fetch_duration_buckets(self, report_date: str) -> list[dict]:
    """按 modified_duration 分桶：0-1Y / 1-3Y / 3-5Y / 5-7Y / 7-10Y / 10Y+"""
    # SQL: CASE WHEN modified_duration <= 1 THEN '0-1年' ...
    # GROUP BY bucket, ORDER BY min(modified_duration)
    # 返回 [{"bucket": str, "total_market_value": Decimal}]

def fetch_rate_buckets(self, report_date: str) -> list[dict]:
    """按 ytm 分桶：<2% / 2-2.5% / 2.5-3% / 3-3.5% / 3.5-4% / 4-5% / >=5%"""
    # ytm 字段需做单位归一：> 1 时视为百分数 /100
    # 返回 [{"bucket": str, "total_market_value": Decimal}]
```

**Step 2：在 `bond_dashboard_service.py` 新增函数**

```python
def get_risk_buckets(report_date: date) -> dict:
    """
    返回 formal envelope，result 包含：
    - report_date
    - bonds_cashflow_buckets: 复用 fetch_dashboard_maturity_structure 结果
    - bonds_duration_buckets: fetch_duration_buckets 结果
    - bonds_rate_buckets: fetch_rate_buckets 结果
    - liability_buckets: []（暂缺，fallback_mode 标注）
    """
```

**Step 3：修改 `liability_analytics.py`**

找到 `/api/risk/buckets` 路由，将 `_raise_liability_analytics_not_promoted()` 替换为：

```python
from backend.app.services.bond_dashboard_service import get_risk_buckets

@router.get("/api/risk/buckets")
def risk_buckets(report_date: str | None = None) -> dict:
    rd = _resolve_report_date(report_date)  # 参考同文件其他路由的日期解析
    return get_risk_buckets(date.fromisoformat(rd))
```

**Step 4：测试**

新建 `tests/test_risk_buckets_contract.py`：

```python
def test_risk_buckets_returns_three_bond_bucket_lists():
    # mock repo，断言 result 有 bonds_cashflow_buckets / bonds_duration_buckets / bonds_rate_buckets
    # 断言每个桶列表非空，每项有 bucket / total_market_value

def test_risk_buckets_liability_buckets_empty_with_fallback():
    # 断言 result.liability_buckets == []
    # 断言 result_meta.fallback_mode != "none" 或有 warning
```

**验证：**
```bash
python -m pytest tests/test_risk_buckets_contract.py -q
```

---

## 端点 #11：`GET /api/bonds/monthly?year=2026`

### V1 契约（目标形状，简化版）

V1 的 `BondsMonthlyResponse` 非常大，V3 P1 只实现核心字段，其余返回空列表：

```python
class BondsMonthlyItem(BaseModel):
    month: str                          # "2026-01"
    month_label: str                    # "2026年1月"
    avg_market_value_cny: str           # Numeric 字符串
    total_market_value: str             # Numeric 字符串
    num_days: int
    cr10: str                           # CR10 集中度，如 "46.30%"
    counterparty_top10: list[dict]      # [{name, avg_value, proportion}]
    maturity_buckets: list[dict]        # [{bucket, avg_balance}]
    duration_buckets: list[dict]        # [{bucket, avg_balance}]
    rate_buckets: list[dict]            # [{bucket, avg_balance}]
    business_type_metrics: list[dict]   # [{name, avg_balance, weighted_ytm, weighted_duration}]
    # 以下 P1 暂返回空列表
    cashflow_buckets: list[dict]        # []
    by_asset_class: list[dict]          # []
    by_sub_type: list[dict]             # []
    top_holdings: list[dict]            # []

class BondsMonthlyResponse(BaseModel):
    year: int
    months: list[BondsMonthlyItem]
    ytd_avg_market_value_cny: str       # Numeric 字符串
```

### V3 实现策略

V3 的 `fact_formal_bond_analytics_daily` 是日粒度表，需要按月聚合。
复用 `bond_analytics_repo` 的现有方法，新增月聚合查询。

### 实现步骤

**Step 1：在 `bond_analytics_repo.py` 新增月聚合方法**

```python
def list_months_for_year(self, year: int) -> list[str]:
    """返回该年有数据的月份列表，格式 YYYY-MM，降序。"""

def fetch_monthly_summary(self, year: int) -> list[dict]:
    """
    按月聚合：
    SELECT
      strftime(report_date, '%Y-%m') AS month,
      COUNT(DISTINCT report_date) AS num_days,
      AVG(market_value) AS avg_market_value,   -- 日均
      ...
    FROM fact_formal_bond_analytics_daily
    WHERE year(report_date) = ?
    GROUP BY month
    ORDER BY month
    """
    # 返回每月的 avg_market_value（CNY/USD 分离）、num_days

def fetch_monthly_maturity_buckets(self, year: int, month: str) -> list[dict]:
    """该月所有日期的期限分桶日均。"""

def fetch_monthly_duration_buckets(self, year: int, month: str) -> list[dict]:
    """该月所有日期的久期分桶日均。"""

def fetch_monthly_rate_buckets(self, year: int, month: str) -> list[dict]:
    """该月所有日期的利率分桶日均。"""

def fetch_monthly_business_type_metrics(self, year: int, month: str) -> list[dict]:
    """该月业务种类加权指标日均。"""

def fetch_monthly_counterparty_top10(self, year: int, month: str) -> list[dict]:
    """该月 Top10 对手方日均敞口。"""
```

**注意：** DuckDB 日期函数用 `strftime(report_date, '%Y-%m')` 或 `date_trunc('month', report_date)`，
先用 `DESCRIBE fact_formal_bond_analytics_daily` 确认实际列名（currency_code / bond_type 等）。

**Step 2：新建 `backend/app/services/bonds_monthly_service.py`**

```python
def get_bonds_monthly(year: int) -> dict:
    """
    按年返回月度统计，formal result envelope。
    对每个月：
    1. 调用 fetch_monthly_summary 获取基础指标
    2. 调用 fetch_monthly_maturity/duration/rate_buckets
    3. 调用 fetch_monthly_business_type_metrics
    4. 调用 fetch_monthly_counterparty_top10，计算 cr10
    5. 组装 BondsMonthlyItem
    """
```

**Step 3：新建 `backend/app/api/routes/bonds.py`**

```python
router = APIRouter(prefix="/api/bonds", tags=["bonds"])

@router.get("/monthly")
def bonds_monthly(year: int = Query(..., ge=2020, le=2030)) -> dict:
    return get_bonds_monthly(year)
```

**Step 4：注册路由**

在 `backend/app/api/__init__.py` 中：

```python
from backend.app.api.routes.bonds import router as bonds_router
router.include_router(bonds_router)
```

**Step 5：新建 schema**

`backend/app/schemas/bonds_monthly.py`：

```python
class BondsMonthlyItem(BaseModel):
    month: str
    month_label: str
    avg_market_value_cny: str
    total_market_value: str
    num_days: int
    cr10: str
    counterparty_top10: list[dict] = []
    maturity_buckets: list[dict] = []
    duration_buckets: list[dict] = []
    rate_buckets: list[dict] = []
    business_type_metrics: list[dict] = []
    cashflow_buckets: list[dict] = []
    by_asset_class: list[dict] = []
    by_sub_type: list[dict] = []
    top_holdings: list[dict] = []

class BondsMonthlyResponse(BaseModel):
    year: int
    months: list[BondsMonthlyItem]
    ytd_avg_market_value_cny: str
```

**Step 6：测试**

新建 `tests/test_bonds_monthly_contract.py`：

```python
def test_bonds_monthly_returns_year_and_months():
    # mock repo，断言 result 有 year / months
    # 断言 months[0] 有 month / total_market_value / num_days / maturity_buckets

def test_bonds_monthly_cr10_format():
    # 断言 cr10 格式为百分比字符串，如 "46.30%"

def test_bonds_monthly_empty_year_returns_empty_months():
    # 无数据时 months = []，不报错
```

**验证：**
```bash
python -m pytest tests/test_risk_buckets_contract.py tests/test_bonds_monthly_contract.py -q
```

---

## 最终回归验证

```bash
python -m pytest tests/test_risk_buckets_contract.py tests/test_bonds_monthly_contract.py tests/test_bond_dashboard_api_contract.py tests/test_dashboard_api_contract.py -q
cd frontend && npm run typecheck
```

---

## 绝对禁止

- 不改 DuckDB 表结构（不加新表，不改现有表）
- 不在 API 层做聚合计算（计算逻辑放 service / repo）
- 不实现 V1 的负债桶逻辑（`liability_analytics_repo` 数据面未就绪，返回空列表即可）
- 不碰 pnl、balance-analysis、executive 等无关路由
- `bonds_monthly_service.py` 每月数据独立查询，不做跨月 JOIN

---

## 完成后输出格式

```
Implemented Phase 2 P1: risk-buckets and bonds-monthly.

Changed files:
- ...

What changed:
- ...

Validation:
- command -> result

Known risks / follow-up:
- ...
```
