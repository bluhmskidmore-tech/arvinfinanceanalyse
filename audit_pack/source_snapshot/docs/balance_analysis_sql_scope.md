# balance-analysis：后端取数范围与 SQL 口径

本文描述 governed **formal** 资产负债只读面（`balance-analysis.*`）在 **DuckDB 仓库层** 的取数范围与聚合语义，供与 Excel/其他系统对账。金额在事实表内为 **人民币元**；API 不换算「亿」，仅前端展示时换算。

**权威实现**：`backend/app/repositories/balance_analysis_repo.py`
**HTTP 入参**：`backend/app/api/routes/balance_analysis.py`（`/ui/balance-analysis/...`）

---

## 1. 事实表与报告日

| 表 | 含义 |
|----|------|
| `fact_formal_zqtz_balance_daily` | ZQTZ 正式日余额（债券/投资侧正式物化） |
| `fact_formal_tyw_balance_daily` | TYW 正式日余额（同业等） |

**可选 `report_date` 列表**：两表 `distinct report_date` 的**并集**，降序。实现见 `list_report_dates`：

```81:86:backend/app/repositories/balance_analysis_repo.py
    def list_report_dates(self) -> list[str]:
        return sorted(
            set(self._list_report_dates("fact_formal_zqtz_balance_daily"))
            | set(self._list_report_dates("fact_formal_tyw_balance_daily")),
            reverse=True,
        )
```

---

## 2. API 与 SQL 过滤条件

以下接口共用同一套「正式 filters」：
`GET /ui/balance-analysis/overview`、`/summary`、`/detail`、`/summary-by-basis` 等（各 handler 的 Query 定义一致；路径以 `balance_analysis.py` 为准）。

| 参数 | 枚举 | 默认 | 作用 |
|------|------|------|------|
| `report_date` | `YYYY-MM-DD` | 必填 | 两表均 `report_date = ?` |
| `position_scope` | `asset` \| `liability` \| `all` | **`all`** | 非 `all` 时两表加 `position_scope = ?` |
| `currency_basis` | `native` \| `CNY` | **`CNY`** | 两表均 `currency_basis = ?` |

路由默认值示例：

```87:101:backend/app/api/routes/balance_analysis.py
@router.get("/overview")
def overview(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return balance_analysis_overview_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
```

`where` 子句的拼装（overview 与 summary CTE 同源）见 `zqtz_where_parts` / `tyw_where_parts`：

```610:618:backend/app/repositories/balance_analysis_repo.py
        zqtz_where_parts = ["report_date = ?", "currency_basis = ?"]
        tyw_where_parts = ["report_date = ?", "currency_basis = ?"]
        zqtz_params: list[object] = [report_date, currency_basis]
        tyw_params: list[object] = [report_date, currency_basis]
        if position_scope != "all":
            zqtz_where_parts.append("position_scope = ?")
            tyw_where_parts.append("position_scope = ?")
            zqtz_params.append(position_scope)
            tyw_params.append(position_scope)
```

---

## 3. `/overview` 合计（`total_*_amount` 与 `asset_*` / `liability_*`）

实现：`fetch_formal_overview`（`with zqtz` / `tyw` 两子查询，再 `cross join` 汇总）。

**`position_scope = all`（全头寸）** 时：在仅按 `report_date`、`currency_basis` 过滤的前提下，对 ZQTZ/TYW 用 `sum(case when position_scope = 'asset' then ... end)` / `... 'liability' ...` **分别**累加，得到 `asset_total_*_amount` 与 `liability_total_*_amount`（元）。`total_*_amount` 仍为 **资产端+负债端** 代数和（兼容与对账），**不得**把资产与负债混成无标签的单一 KPI 误导为「一侧规模」。

**`position_scope` 为 `asset` 或 `liability`** 时：SQL 仅保留该侧行；`total_*` 即该侧合计；`asset_total_*` / `liability_total_*` 中无效侧为 0，有效侧等于 `total_*`。

### 3.1 ZQTZ 子查询（单端筛选时；`all` 时为按 `position_scope` 分支的 CASE 汇总）

- 来源：`fact_formal_zqtz_balance_daily`，条件见上。
- **总市值（单端）**：`coalesce(sum(market_value_amount), 0)`
- **摊余成本（单端）**：`coalesce(sum(amortized_cost_amount), 0)`
- **应计利息（单端）**：`coalesce(sum(accrued_interest_amount), 0)`

单端筛选时实现形态与下述类似（行号以仓库最新 `fetch_formal_overview` 为准）：

```text
backend/app/repositories/balance_analysis_repo.py — fetch_formal_overview
  with zqtz as ( select ... coalesce(sum(market_value_amount), 0) ... from fact_formal_zqtz_balance_daily where ... position_scope = ? ... )
```

### 3.2 TYW 子查询

- 来源：`fact_formal_tyw_balance_daily`，条件见上。
- **注意**：`total_market_value_amount` 与 `total_amortized_cost_amount` 在 TYW 侧 **均** 为 `coalesce(sum(principal_amount), 0)`；应计为 `sum(accrued_interest_amount)`。
- `position_scope = all` 时同样按 `asset` / `liability` 做 CASE 或等价拆分后再与 ZQTZ 相加。

### 3.3 最终加总

- ZQTZ 与 TYW 子查询做 `cross join` 后：各金额列均为 **两来源相加**；`all` 时另产出 `asset_total_*` / `liability_total_*`。

**对账提示**：与「仅 ZQTZ / 仅债券台帐」的 Excel 对比时，若本 API 为 **ZQTZ+TYW 全量** 且 TYW 用 **本金** 同时计入「市值」「摊余」两列，数值不会与单一来源表 1:1 相同，需按上表拆分核对。

---

## 4. `/summary` 正式汇总表（`summary_rows` CTE）

实现：`_formal_summary_table_cte`：同一 `where`，按 **ZQTZ / TYW 不同 grain** 分组后 `UNION ALL`。

- **ZQTZ**：`group by instrument_code, portfolio_name, cost_center, position_scope, currency_basis, invest_type_std, accounting_basis`；金额为 `sum(market_value_amount)` 等。
- **TYW**：`group by position_id, counterparty_name, product_type, position_scope, currency_basis, invest_type_std, accounting_basis`；**市值/摊余**均为 `sum(principal_amount)`。

见：

```858:899:backend/app/repositories/balance_analysis_repo.py
        cte_sql = f"""
            with summary_rows as (
              select
                'zqtz:' || instrument_code || ':' || portfolio_name || ':' || cost_center || ':' || currency_basis || ':' || position_scope || ':' || invest_type_std || ':' || accounting_basis as row_key,
                ...
                coalesce(sum(market_value_amount), 0) as market_value_amount,
                coalesce(sum(amortized_cost_amount), 0) as amortized_cost_amount,
                coalesce(sum(accrued_interest_amount), 0) as accrued_interest_amount
              from fact_formal_zqtz_balance_daily
              where {' and '.join(zqtz_where_parts)}
              group by instrument_code, portfolio_name, cost_center, position_scope, currency_basis,
                       invest_type_std, accounting_basis

              union all

              select
                'tyw:' || position_id || ':' || ...
                coalesce(sum(principal_amount), 0) as market_value_amount,
                coalesce(sum(principal_amount), 0) as amortized_cost_amount,
                coalesce(sum(accrued_interest_amount), 0) as accrued_interest_amount
              from fact_formal_tyw_balance_daily
              where {' and '.join(tyw_where_parts)}
              group by position_id, counterparty_name, product_type, position_scope, currency_basis,
                       invest_type_std, accounting_basis
            )
        """
```

在 **相同** `report_date` / `currency_basis` / `position_scope` 下，对 `summary` 全部行（无 `limit/offset` 截断时）的 `market_value_amount` 等求和，应与 `/overview` 的 `total_*` **一致**；若只拉一页 `limit/offset`，表内加总可小于 overview。

---

## 5. `/summary-by-basis`（`fetch_formal_basis_breakdown`）

同一两表、同一 `where` 条件；按 `invest_type_std`、`accounting_basis` 等 **会计口径** 聚合（ZQTZ 与 TYW 分别为一段 `UNION ALL`）。TYW 仍用 `principal` 作市值/摊余聚合。见同文件 `fetch_formal_basis_breakdown` 内 SQL（约 790–826 行）。

---

## 6. 与数据契约总览

事实表结构、物化边界与受治理 read surface 的约束仍以 **`docs/data_contracts.md`** 及 **`docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`** 为准；本文仅钉死 **本仓库 `BalanceAnalysisRepository` 当前 SQL 行为**，若迁移或改列需同步改本文与契约测试（如 `tests/test_balance_analysis_*.py`）。

---

## 7. 对账检查清单（简）

1. 同一 `report_date`、`currency_basis`（多为 `CNY`）、`position_scope`（是否含负债侧）。
2. 全量加总时是否应 **ZQTZ + TYW**；与仅 ZQTZ/仅 Excel 范围是否一致。
3. TYW 侧 **principal** 同时进入「市值」「摊余」两列的语义。
4. 金额为 **元**；展示「亿元」= 元 / 10⁸，由前端/报表层换算，**非** 本 SQL 内换算。
