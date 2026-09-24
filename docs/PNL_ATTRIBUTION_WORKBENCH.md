# 损益归因工作台：内部设计说明（`core_finance/pnl_attribution/workbench.py`）

本文档说明正式口径 **PnL 归因 API**（`/api/pnl-attribution/*`）背后、集中在 `backend/app/core_finance/pnl_attribution/workbench.py` 中的**数学假设与单位约定**。服务层仅做只读取数与封装 `result_meta`；可复用的组合风险聚合统一调用 `bond_analytics/read_models.py`（如 `summarize_portfolio_risk`、`build_krd_distribution`、`build_asset_class_risk_summary`），避免在 service 中复制桶聚合逻辑。

---

## 1. 单位与符号

| 含义 | 约定 |
|------|------|
| 曲线 `rate_pct` / 10Y 国债点位 | **百分数点**（如 2.35 表示 2.35%），与 `fact_formal_yield_curve_daily` 及前端 TPL 图表一致。 |
| 债券 `ytm`、`coupon_rate`（事实表） | **小数**（如 0.0285 表示 2.85%）；在展示或与其它百分数混算时，工作台内会按需换算。 |
| `yield_change`、`treasury_change`、`spread_change`（Spread/KRD 条目字段） | **基点（bp）**，由小数收益率差 × 10000 得到，与前端 mock 量级一致。 |
| 价格效应近似 | 使用 **一阶久期近似**：\(\Delta P \approx -D_{mod} \cdot MV \cdot \Delta y\)，其中 \(\Delta y\) 为**小数形式**的全收益率变动（例如 8bp → 0.0008）。 |

---

## 2. 利差归因（`build_spread_attribution`）

### 2.1 目的

在观察窗口内，将组合估值变动粗分为 **国债曲线平移** 与 **利差（含个券特异性）** 两部分，并按 `asset_class_std` 输出分项，供瀑布图与解释文案使用。

### 2.2 输入

- **期末**、**期初**（锚定日由服务层选取：报告日及「不晚于 lookback 起点的最近可用债券快照日」）两套 `fact_formal_bond_analytics_daily` 行集。
- **国债10Y**：起、止两个交易日的点位（百分数点），由 `YieldCurveRepository` 取 `treasury` 曲线 `10Y`（或兼容 `10` / `10y`）。

### 2.3 组合层分解逻辑

1. **国债变动（小数）**  
   \(\Delta t_{dec} = (t_{end} - t_{start}) / 100\)，其中 \(t\) 为百分数点。  
   接口字段 `treasury_10y_change` 使用 **bp**：\(\Delta t_{bp} = (t_{end} - t_{start}) \times 100\)。

2. **组合加权到期收益率（小数）**  
   对期初、期末债券行分别做市值加权平均 YTM，得到 \(y_{start}, y_{end}\)，\(\Delta y_{bond} = y_{end} - y_{start}\)。

3. **利差变动（小数，组合层残差）**  
   \(\Delta s_{portfolio} = \Delta y_{bond} - \Delta t_{dec}\)（平行国债假设下，全价收益率变动相对国债的部分）。

### 2.4 按资产类的分项

- 对每个 `asset_class_std`：用**期末**持仓计算市值加权 **修正久期** \(D\) 与加权 YTM \(y_e\)；用**期初**同类的行计算 \(y_s\)。
- **展示用**变动（bp）：`yield_change = (y_e - y_s) × 10000`；`treasury_change` 与组合层 \(\Delta t_{bp}\) 一致；`spread_change = yield_change - treasury_change`（在数据齐全时）。
- **效应（金额）**（小数变动回代）：  
  - **国债效应**：\(-MV \cdot D \cdot \Delta t_{dec}\)（若缺曲线则该项为 0）。  
  - **利差效应**：\(-MV \cdot D \cdot \Delta s_{row}\)，其中 \(\Delta s_{row}\) 优先用 \((y_e - y_s) - \Delta t_{dec}\)（与 bp 一致），否则回退到组合层 \(\Delta s_{portfolio}\)。

### 2.5 已知局限（后续可增强）

- **非平行移动**：仅用 10Y 点位代表整条曲线，**牛陡/牛平** 无法在 Spread 模块内区分，需配合 KRD 与曲线形状标签。
- **信用/品种久期**：未单独拆出 OAS；`spread_effect` 在实务上混合了信用利差、流动性溢价与个券择券。
- **期初/期末组合不一致**：未做仓位重连或现金流再投资假设，归因残差可能偏大。

---

## 3. Campisi 四效应（`campisi_attribution`）

### 3.1 目的

按 **Campisi 框架** 的语义（收入、国债、利差、选择）向工作台提供逐券、资产类别和组合三级闭合拆分。当前实现使用起止两期债券快照、多期限国债曲线和评级 3Y 利差，不再是单一 10Y 曲线或利差占位口径。

### 3.2 分桶

- 服务层先按业务持仓键合并起止两期债券快照，再由 `campisi_attribution` 逐券计算。
- `num_days = max((period_end - period_start).days, 1)`；逐券结果按 `asset_class_start` 和期限桶汇总，组合 totals 由逐券 Decimal 金额求和后在输出边界转为 float。

### 3.3 曲线、久期与评级输入

- 国债基准使用起止两期共同存在且为正的 `1Y / 3Y / 5Y / 7Y / 10Y / 30Y` 期限点。共同期限不少于 3 个时拟合三次样条，恰为 2 个时使用分段线性曲线；在单券剩余期限处分别求值后，以 `(end_pct - start_pct) / 100` 转为小数收益率变动。
- 单券先计算 Macaulay 久期，再通过 `modified_duration_from_macaulay` 转为**修正久期**。修正久期的收益率输入依次取正的期初 YTM、正的票息，二者均不可用时取 0；不再使用任意的 1% 代理。
- 信用评级由期初资产类别推断为 `GOV / AAA / AA+ / AA`。`GOV` 利差变动为 0；其余评级读取对应的期初、期末 3Y 利差 BP，并以 `(end_bp - start_bp) / 10000` 转为小数。

### 3.4 四效应与闭合

| 效应 | 当前计算 |
|------|----------|
| **收入（Income）** | `coupon_decimal × face_value_start × num_days / 365`。 |
| **国债（Treasury / 利率）** | `-modified_duration × benchmark_yield_change_decimal × market_value_start`。 |
| **利差（Spread）** | `-modified_duration × rating_spread_change_decimal × market_value_start`。 |
| **选择（Selection）** | 闭合残差：`total_return - income_return - treasury_effect - spread_effect`；不是独立估计的选券 alpha。 |
| **总回报（Total）** | 两端应计利息齐全时，`dirty_change + inferred_coupon_cash`，其中 `inferred_coupon_cash = income_return - (ai_end - ai_start)`；否则退化为 `market_value_end - market_value_start + income_return`。 |

单券、资产类别和组合 totals 均满足 `total_return = income_return + treasury_effect + spread_effect + selection_effect`。AC 人口按会计边界仅保留收入效应，国债、利差和选择效应均归零，`total_return = income_return`。

### 3.5 降级与披露语义

- 起止曲线共同正期限少于 2 个时，国债收益率变动退化为 0；2 个期限点明确使用线性回退；缺少部分期限但仍可拟合时使用共同期限子集，并由服务层输出覆盖不足 warning。
- 评级 3Y 利差任一端缺失、不可解析或非正时，该券利差变动退化为 0，并输出覆盖不足 warning；不得把该 0 解读为观测到“利差未变”。
- 到期日缺失或不可解析时修正久期为 0，利率与利差金额随之为 0，并记录 `mod_dur_fallback_zero` 等 diagnostics。
- 应计利息仅单端存在或两端都缺失时，退化到净价变动加收入的口径，并记录 `accrued_interest_partial` / `accrued_interest_missing`；不使用单端应计利息拼接全价。
- 无可用持仓时，服务层返回 totals 全 0、空明细和 `quality_flag=warning`。零值与 warning / diagnostics 必须一起消费，API 或前端不得静默补算。

---

## 4. 相关代码索引

| 能力 | 函数 | read_models 依赖 |
|------|------|------------------|
| 利差归因 | `build_spread_attribution` | `summarize_portfolio_risk` |
| KRD 桶 | `build_krd_attribution` | `summarize_portfolio_risk`、`build_krd_distribution` |
| Campisi | `campisi_attribution` / `compute_bond_four_effects` | 起止两期债券快照、多期限国债曲线、评级 3Y 利差 |
| Carry / Roll | `build_carry_roll_down` | 无（按类市值加权票息、久期与 FTP） |

---

## 5. 与 API 行为的对应关系

- **缺数**：服务层不抛错，返回空表结构 + `result_meta.quality_flag = warning` 与 `warnings` 文案（见 `pnl_attribution_service.py`）。  
- **金额序列化**：本工作台输出经 Pydantic 校验后以 **JSON number（float）** 出参，与债券分析部分接口的 **string金额** 刻意区分，以匹配前端 `contracts.ts` 的 PnL 归因类型。

---

*文档版本：与 `rv_pnl_attribution_workbench_v1` 对齐；若核心公式变更，请同步更新本文与 `RULE_VERSION` 变更说明。*
