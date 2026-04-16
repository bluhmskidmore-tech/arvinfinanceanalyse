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

## 3. Campisi 四效应（`build_campisi_attribution`）

### 3.1 目的

按 **Campisi 框架** 的语义（收入、国债、利差、选择）向工作台提供**可解释的拆分**；当前实现为 **显式简化版**，便于在仅有「债券日频快照 + 国债 10Y 起止」时也能跑通链路，并与前端 `CampisiAttributionPayload` 字段对齐。

### 3.2 分桶

- 使用 `build_asset_class_risk_summary(bond_rows)`，按 **`asset_class_std`** 聚合市值、久期（Macaulay，来自 read_models 约定）、权重。

### 3.3 各效应定义（当前版本）

| 效应 | 计算要点 |
|------|----------|
| **收入（Income）** | 每类：`MV × coupon_dec × (num_days / 365)`，其中 `coupon_dec` 为市值加权平均票息（小数）。近似**应计票息/持有期收入**，非完整现金流折现。 |
| **国债（Treasury /利率）** | 每类：`-MV × D × Δy_treas`，其中 `Δy_treas` 由服务层传入 **`treasury_dy_decimal`**（10Y 百分数点之差 / 100，即小数收益率变化）。仍为一阶近似，且 **D 用 Macaulay** 与 Spread 模块的修正久期不完全一致，属已知口径差异。 |
| **利差（Spread）** | **当前常量0**（占位）。完整版应对每类或每只券估计 OAS/利差变动或相对基准的超额。 |
| **选择（Selection）** | **当前常量 0**（占位）。完整版应用组合相对基准的残差或 Brinson 式选择项。 |

### 3.4 合计与主驱动

- 每类 `total_return = income + treasury + spread + selection`（后两项现为 0）。  
- 组合层 `primary_driver` 取 **绝对金额最大** 的一类效应名（`income` / `treasury` / `spread` / `selection`）。

### 3.5 演进方向（与 read_models 对齐）

- 利差：可接入 `summarize_return_decomposition` 或 Phase 3 曲线 + 个券利差输入，在 **core_finance** 内扩展，仍避免在 API 层写公式。  
- 选择：需 **基准全价序列** 或 **组合/基准持仓对齐** 后的残差定义。  
- 久期口径：可在全模块统一为 **修正久期** 或明确文档化「Campisi 块用 Macaulay」的原因与偏差量级。

---

## 4. 相关代码索引

| 能力 | 函数 | read_models 依赖 |
|------|------|------------------|
| 利差归因 | `build_spread_attribution` | `summarize_portfolio_risk` |
| KRD 桶 | `build_krd_attribution` | `summarize_portfolio_risk`、`build_krd_distribution` |
| Campisi | `build_campisi_attribution` | `build_asset_class_risk_summary` |
| Carry / Roll | `build_carry_roll_down` | 无（按类市值加权票息、久期与 FTP） |

---

## 5. 与 API 行为的对应关系

- **缺数**：服务层不抛错，返回空表结构 + `result_meta.quality_flag = warning` 与 `warnings` 文案（见 `pnl_attribution_service.py`）。  
- **金额序列化**：本工作台输出经 Pydantic 校验后以 **JSON number（float）** 出参，与债券分析部分接口的 **string金额** 刻意区分，以匹配前端 `contracts.ts` 的 PnL 归因类型。

---

*文档版本：与 `rv_pnl_attribution_workbench_v1` 对齐；若核心公式变更，请同步更新本文与 `RULE_VERSION` 变更说明。*
