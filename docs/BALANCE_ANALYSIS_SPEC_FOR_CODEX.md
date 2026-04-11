# Balance / 产品类别余额与规模口径（Codex 读取用）

## 0. 文档用途

- **读者**：Codex / 自动化代理在实现、审查或重构「余额、月均、年日均、规模折算、FTP、加权收益率」相关逻辑时使用。
- **约束**：正式金融计算**唯一实现位置**为 `backend/app/core_finance/`（见 `docs/calc_rules.md` 总则）。API与前端只做编排与展示，不得复制公式。
- **环境说明**：若本地前端使用 `http://localhost:3888/balance-analysis`，本仓库当前**已有**该路由；其 governed formal 路径由 `backend/app/core_finance/balance_analysis.py`、`backend/app/tasks/balance_analysis_materialize.py`、`backend/app/services/balance_analysis_service.py`、`backend/app/api/routes/balance_analysis.py` 与 `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` 共同构成。与之并行的 **产品类别损益** 工作台仍是 `/product-category-pnl`，两条线不可混用。本文档以**后端与 core_finance 真值**为准。

## 1. 权威引用顺序（摘录）

完整列表见 `docs/DOCUMENT_AUTHORITY.md`。与本页口径强相关：

1. `docs/calc_rules.md` — 总则、**第 5 节日均金额**、**第 8 节 CNX/CNY**。
2. `docs/data_contracts.md` — 标准化层级与字段语义。
3. 本文 +下文所列源码路径。

## 2. 代码映射（单一真值）

| 语义 | 路径 |
|------|------|
| 读模型（规模字段选取、QTD 合并、FTP、加权收益率、层级汇总） | `backend/app/core_finance/product_category_pnl.py` |
| 源文件 → 规范事实行（总账 + 日均表） | `backend/app/services/product_category_source_service.py` |
| HTTP 编排、DuckDB 读写、手工调整持久化 | `backend/app/services/product_category_pnl_service.py` |
| API | `backend/app/api/routes/product_category_pnl.py`（前缀 `/ui/pnl/product-category`） |
| 前端展示与调整表单 | `frontend/src/features/product-category-pnl/` |

## 3. 规范事实行 `CanonicalFactRow`

每条事实对应 `(report_date, account_code, currency)` 粒度（合并键以 core逻辑为准）。

| 字段 | 含义 | 来源（导入阶段） |
|------|------|------------------|
| `beginning_balance` | 期初余额 | 总账对账 xlsx：列映射见 `product_category_source_service._parse_ledger_workbook`（约第 7 行起，列 3） |
| `ending_balance` | 期末余额 | 总账：列 6 |
| `monthly_pnl` | 月度损益（期间） | `derive_monthly_pnl(period_debit, period_credit)` = **贷方 − 借方**（列 4、5） |
| `daily_avg_balance` | **月**日均余额（表内命名；业务展示可为「月日均」） | 「日均」xlsx **第二张工作表**（`worksheets[1]`）解析结果 |
| `annual_avg_balance` | **年**日均余额（1 月报表语义见下） | 「日均」xlsx **第一张工作表**（`worksheets[0]`） |
| `days_in_period` | 当月日历天数 | `monthrange(year, month)` |

源文件配对规则：`product_category_source_service.discover_source_pairs` — 同月 `总账对账*.xlsx` 与 `日均*.xlsx`（文件名含 `YYYYMM`）各一；`report_date` 为该月**月末**日期。

## 4. 视图 `view` 与输入行集合

API 允许：`monthly` | `qtd` | `ytd` | `year_to_report_month_end`（见 `product_category_pnl_service.AVAILABLE_VIEWS`）。

`_build_report_rows`（`product_category_pnl.py`）行为摘要：

- **`monthly`**：使用 `report_date` 当月事实列表，不做跨月合并。
- **`qtd`**：将本季度内**已存在事实的月份**按 `(account_code, currency)` 合并：对每月 `daily_avg_balance` 按**当月天数**加权累加，再除以总天数，得到季度内**加权平均的月日均**；`ending_balance`、`annual_avg_balance` 取合并迭代中**最后一月**的值；`beginning_balance`、`monthly_pnl` 在合并结果中置零（见实现）。
- **`ytd` / `year_to_report_month_end`**：与 `monthly` 相同，直接使用 `report_date` 当月事实，**不**做 YTD 多月合并（若产品语义需要「真·年初至今合并」，当前实现未做，属 gap，改前须更 PRD/规则文档）。

## 5. 规模（Scale）用哪一列：`_scale_field`

读模型里 FTP 与展示用「规模」来自 `scale_accounts` 列表，对 **CNX**、**CNY** 分别精确匹配科目求和。

| view | `_scale_field` 返回值 |
|------|------------------------|
| `monthly` 且 `report_date.month == 1` | `annual_avg_balance` |
| `monthly` 且非 1 月 | `daily_avg_balance` |
| `qtd` | `daily_avg_balance` |
| `ytd` / `year_to_report_month_end` | `annual_avg_balance` |

外币规模（展示用）：`foreign_scale = scale_cnx - scale_cny`（综本减人民币账，与 `calc_rules.md` 第 8 节一致）。

## 6. 现金 / 损益侧（叶子类别）：`cash_field` 与符号

对**无子节点**的类别：

- **`view == "monthly"`**：`cash_field = "monthly_pnl"`，`sign = +1`（对 `pnl_accounts` 模式匹配求和后再乘符号）。
- **非 monthly**：`cash_field = "ending_balance"`，`sign = -1`。

科目匹配：`exact=True` 用于 scale；`exact=False` 时 `account_code.startswith(target)`。模式前缀 `-` 表示该模式贡献为减项。

CNX/CNY 分开求和；`foreign_cash = cnx_cash - cny_cash`。

## 7. FTP 与加权收益率

- **FTP**：`_calculate_ftp(scale, ftp_rate, days) = scale * ftp_rate * days / 365`，其中 `ftp_rate = baseline_ftp_rate_pct / 100`，`days = _days_for_view(report_date, view)`（月视图为当月末日；QTD 为季初到报告月末；YTD 类为年初到报告月末）。
- **净收入**：`cny_net = cny_cash - cny_ftp`，`foreign_net = foreign_cash - foreign_ftp`，`business_net_income = cny_net + foreign_net`。
- **加权收益率**（叶子）：`weighted_yield = (pnl_ending / days_for_view) * 365 / scale_cnx * 100`，若 `scale_cnx == 0` 或 `days_for_view <= 0` 则为 `None`。此处 `pnl_ending` 传入的是 **cnx_cash**（见 `_calculate_weighted_yield` 调用）。

## 8. 层级汇总与合计行

- 有 `children` 的类别：`cnx_cash` / `cny_cash` / `foreign_cash` / `cny_ftp` / `foreign_ftp` 等由**子节点结果相加**；FTP **不再**按父级 scale 重算（与叶子路径不同）。
- **资产端合计** `asset_total`：规模侧排除 `ASSET_SCALE_EXCLUSIONS`；损益侧排除 `ASSET_PNL_EXCLUSIONS`（常量见 `product_category_pnl.py`）。
- **负债端合计** `liability_total`：无上述排除。
- **grand_total**：仅 `business_net_income = asset_total.business_net_income + liability_total.business_net_income`。

## 9. 手工调整（仅已批准）

-仅 `approval_status == "approved"` 的调整参与 `apply_manual_adjustments`。
- 运算符：`ADD`（插入新键，已存在则跳过）、`DELTA`（逐项加总）、`OVERRIDE`（非空字段覆盖）。

## 10. Scenario（分析口径）

`apply_scenario_to_rows`：按比例缩放 FTP（`scenario_rate_pct / baseline_ftp_rate_pct`），重算 `cny_net` / `foreign_net` / `business_net_income`。Scenario 结果不得写入 formal 事实表（见 `calc_rules.md` 禁止事项）。

## 11. Codex 工作清单（实现 / Code Review）

- [ ] 任意金额公式是否只出现在 `core_finance/product_category_pnl.py`（及源解析 `product_category_source_service.py` 的导入变换）？
- [ ] API/前端是否仅传递 `report_date`、`view`、`scenario_rate_pct` 与展示字段？
- [ ] 修改 `_scale_field`、QTD 合并、FTP 天数或 `derive_monthly_pnl` 时，是否同步更新本文件与 `calc_rules.md` 第 5 节（若影响日均语义）？
- [ ] 新增视图或「真 YTD 合并」前，是否先更新 PRD / 本 spec，再改代码？

## 12. 相关测试入口（便于回归）

- `tests/test_product_category_pnl_flow.py`
- `tests/test_pnl_core_finance_contract.py`（若涵盖 product category）

---

**版本提示**：`product_category_source_service.RULE_VERSION = "rv_product_category_pnl_v1"`；源结构变更时应递增规则版本并在 `result_meta` / 治理字段中可追溯（若适用）。

## 13. ZQTZ / TYW Formal Balance Analysis Boundary

本节只用于划清 `product-category-pnl` 与当前已落地的 `zqtz / tyw formal balance-analysis` 的边界，避免把两条线混成同一个实现面。

### 13.1 产品类别损益已实现面

- 当前仓库中，`product-category-pnl` 仍是独立的“余额 / 日均 / 规模”正式读模型，不与 `zqtz / tyw balance-analysis` 复用实现面。
- 它的真值仍是：
  - `backend/app/core_finance/product_category_pnl.py`
  - `backend/app/services/product_category_pnl_service.py`
  - `backend/app/api/routes/product_category_pnl.py`

### 13.2 当前已落地的 ZQTZ / TYW governed formal balance path

当前已落地且后续不得破坏的输入边界是：

```text
zqtz_bond_daily_snapshot / tyw_interbank_daily_snapshot
-> module registry / formal materialize runtime
-> core_finance formal derivation
-> fact_formal_zqtz_balance_daily / fact_formal_tyw_balance_daily
-> governed service / API
-> workbench consumer
```

当前实现中的受控接入骨架为：

- `backend/app/core_finance/module_registry.py`
- `backend/app/tasks/formal_compute_runtime.py`
- `backend/app/services/formal_result_runtime.py`

其中：
- formal module 通过 registry 登记 runtime identity 与 fact 边界
- materialize 继续只在 `tasks/` 路径写 DuckDB
- service 复用 shared formal result helper 组装 `result_meta`
- API 路由保持显式定义，不因为模块注册而自动暴露新路由

禁止：
- `phase1_*preview*` 直接进入 formal balance read model
- snapshot 直接冒充 formal fact
- 在 service / API / 前端层补写 H/A/T、FX、发行类排除、月均正式逻辑

### 13.3 当前状态

- 截至当前仓库状态，`zqtz / tyw` 已有正式 `balance-analysis` core_finance 派生、materialize task、governed service / API 路由与首个 workbench 页面：
  - `backend/app/core_finance/balance_analysis.py`
  - `backend/app/tasks/balance_analysis_materialize.py`
  - `backend/app/services/balance_analysis_service.py`
  - `backend/app/api/routes/balance_analysis.py`
  - `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- 本文档与 [data_contracts.md](data_contracts.md)、[calc_rules.md](calc_rules.md) 现在既约束已交付路径，也保留 contract / boundary 约束；但不宣称超出上述实现面的更多能力。
