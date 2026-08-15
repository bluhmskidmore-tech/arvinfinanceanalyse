# calc_rules.md

## 1. 总则

本文件定义正式金融口径的核心计算规则。所有规则只允许实现于 `backend/app/core_finance/`，前端、API、Agent 不得重复实现。

## 2. H / A / T 映射

### 2.1 业务含义

| invest_type_std | 业务含义 | accounting_basis |
|---|---|---|
| H | 持有至到期 | AC |
| A | 可供出售 | FVOCI |
| T | 交易性 | FVTPL |

### 2.2 推导规则

优先顺序：
1. 直接读取源字段（若已给出 H/A/T）
2. 由资产分类文字推导：
   - 包含 `可供出售` / `AFS` → `A`
   - 包含 `交易` / `Trading` → `T`
   - 包含 `持有至到期` / `HTM` → `H`
3. 仍无法推导时，标记治理异常

## 3. Formal PnL

### 3.1 基础公式

```text
standardized_total_pnl = interest_income_514 + fair_value_change_516 + capital_gain_517 + manual_adjustment
```

`standardized_total_pnl` 只是标准化组件汇总，不直接等于 formal-recognized `total_pnl`；formal-recognized `total_pnl` 由 3.3 的归属矩阵判定。

### 3.2 会计口径

- `H / AC`：正式利润只保留利息与相关 realized 项，不将公允价值波动计入当期利润
- `A / FVOCI`：公允价值波动进入 OCI，不进入 formal PnL；分析口径可单列展示
- `T / FVTPL`：公允价值变动计入当期损益

### 3.3 Formal 归属矩阵

- `AC`：`514` 计入 formal；`516` 不计入 formal `total_pnl`；`517` 仅限 realized 且符合 formal 事件；`manual_adjustment` 仅限已批准 formal adjustment。
- `FVOCI`：`514` 计入 formal；`516` 不计入 formal `total_pnl`；`517` 仅计入已实现损益；OCI 变化不进 formal `total_pnl`。
- `FVTPL`：`514`、`516` 可进入 formal `total_pnl`；`517` 仍需满足 realized component / formal event semantics 才能进入 formal `total_pnl`；`manual_adjustment` 同样要求已批准。
- `manual_adjustment` 的批准判定必须来自治理/审批状态字段（如 `approval_status` / `governance_status`），不得由自由文本解释；未批准 adjustment 不进入 formal `total_pnl`。
- 当前 `backend/app/core_finance/pnl.py` 承担 standardized input normalization、formal recognition matrix 与 formal fact projection；对外 formal read surface 的 lineage 仍必须以 `report_date` 对应 build record 优先、manifest 回退的规则解释。

## 4. 516 规则

### 4.1 正式口径

- 正式层使用有符号金额 `signed_amount` 或 ETL 后的 `fair_value_change_516`
- 不允许在正式计算层再根据借贷标识拼符号

### 4.2 当前导入约定

- 若源表给出 `T损益516`，标准化时执行 `* -1` 形成统一口径
- 若源表给出 `金额 + 借贷标识`，必须在标准化阶段合成 `signed_amount`

## 5. 日均金额

### 5.1 basis

- `observed`：仅使用实际观测到的快照日
- `locf`：缺失日使用前一有效日沿用
- `calendar_zero`：缺失日按 0 处理

### 5.2 公式

```text
monthly_avg = sum(daily_value) / valid_day_count
```

其中：
- `observed`：`valid_day_count = observed_days`
- `locf`：`valid_day_count = calendar_days`
- `calendar_zero`：`valid_day_count = calendar_days`

### 5.3 正式与分析

- Formal：优先使用总账日均或正式定义的 `observed`
- Analytical：允许使用 `locf` / `calendar_zero`

## 6. 发行类债券排除规则

### 6.1 资产口径

债券资产月均、市值、摊余成本、应计利息默认排除发行类债券。

### 6.2 scope

- `asset`：排除发行类债券
- `liability`：仅看发行类债券 / 负债类债券
- `all`：全量审计视图

### 6.3 判断

优先使用标准化布尔字段 `is_issuance_like`，禁止散落 `LIKE '%发行%'` 作为长期正式规则。

## 7. FX 中间价折算

### 7.1 正式规则

- 使用当日官方中间价
- USD/CNY 正式口径来源为官方中间价源
- 周末/节假日允许沿用前一营业日中间价
- 缺失营业日中间价时，formal 失败

### 7.2 逐日换算公式

```text
market_value_cny_daily = market_value_native * fx_mid_rate
amortized_cost_cny_daily = amortized_cost_native * fx_mid_rate
accrued_interest_cny_daily = accrued_interest_native * fx_mid_rate
```

## TYW Missing Source LOCF

- If a TYW report date has no source manifest but the same report date has a ZQTZ
  materialization run, the formal snapshot materializer may carry forward the
  previous available TYW snapshot.
- LOCF rows must be explicit:
  - `rule_version = rv_snapshot_zqtz_tyw_v1__locf`
  - `source_version` starts with `sv_tyw_locf_`
  - `ingest_batch_id = locf:<prior_report_date>`
  - `trace_id` starts with `locf:<report_date>:from:<prior_report_date>`

### 7.3 月均人民币值

```text
monthly_avg_market_value_cny = average(market_value_cny_daily)
```

禁止：
- 先算原币月均，再乘月均汇率

## 8. CNX / CNY 规则

- `CNX`：综本
- `CNY`：人民币账
- 外币展示值：`CNX - CNY`

禁止把 `CNX` 当成 ISO 币种代码。

## 9. 桥接归因

PnL Bridge 结构（互斥分解，2026-08 审计 PNL-01 后口径）：

```text
explained_pnl =
  carry
+ roll_down
+ treasury_curve
+ credit_spread
+ fx_translation
+ realized_trading
+ manual_adjustment
```

- `unrealized_fv`（516 公允价值变动）不计入 `explained_pnl`：市场效应（骑乘/曲线/利差/汇兑）本身就是对 516 的解释项，二者同时相加会使 residual 在代数上恒等于市场效应之和的相反数。
- `residual = actual_pnl - explained_pnl`，代数上即 516 − 市场效应，表示模型未能解释的公允价值变动；非 FVTPL 行两侧均为 0，残差自然闭合。
- `unrealized_fv` 仍作为桥接行字段单独披露（期初/期末脏市值同理），只是不参与 `explained_pnl` 求和。

FX translation base (2026-07-19)：
- `fx_translation = exposure_native * (fx_mid_current - fx_mid_prior)`。
- `exposure_native` 优先用期末脏市值原币（`market_value + accrued_interest`），与桥接期初/期末脏市值及 `read_models.fx_effect` 的市值基数对齐；仅在无市值字段时回退 `face_value_native`。

Sign convention:
- `roll_down = ((current_curve_rate - rolled_curve_rate) / 100) * modified_duration * market_value`.
- Upward-sloping curves (`current_curve_rate > rolled_curve_rate`) produce positive roll-down return.
- The three implementations (`pnl_bridge`, `bond_analytics read_models`, and `attribution_daily`) must use the same sign convention.

Time-anchor convention:
- Owner decision 2026-07-03 selected Gate 1 Option A for formal `MTR-BRG-004`.
- `current_curve_rate` uses the period-end/report-date curve at current/end remaining tenor.
- `rolled_curve_rate` uses the same period-end/report-date curve at `current_remaining_tenor - elapsed_days / 365`.
- `elapsed_days` is exclusive (`period_end - period_start`), matching `pnl_bridge` current/prior balance date difference.
- `modified_duration` and `market_value` use current/end exposure.
- Gate 2 decision: `bond_analytics read_models` and `attribution_daily` follow the same roll-down sign and time-anchor convention.

要求：
- `explained_pnl`
- `actual_pnl`
- `residual`
- `residual_ratio`
- `quality_flag`

## 10. 风险张量

最少输出：
- `dv01`
- `krd_1y`
- `krd_3y`
- `krd_5y`
- `krd_7y`
- `krd_10y`
- `krd_30y`
- `cs01`
- `convexity`
- `issuer_concentration`
- `liquidity_gap`

DV01 口径：
- 全局正式 DV01 使用面值口径：`face_value * modified_duration / 10000`。信用债 `spread_dv01` 与明细 `dv01` 同口径，按信用债明细行的面值与利差久期计算。
- 正式事实表优先使用 CNY 面值字段；仅在旧的内存计算路径缺少面值字段时允许临时回退 `market_value`，不得把该回退解释为正式口径。

Duration denominator rules:
- `total_market_value` remains the full bond analytics market value.
- `portfolio_modified_duration` is weighted only by rows with `maturity_date > report_date`, positive `modified_duration`, and non-zero `market_value`.
- Duration exclusions are classified in priority order: `no_maturity` when `maturity_date is null`; `matured_or_expired_outstanding` when `maturity_date <= report_date` and market value is non-zero; then `nonpositive_duration` only for future-dated rows whose modified duration is null or non-positive. A maturity date equal to the report date is treated as matured.
- Reclassifying an excluded row does not change `total_market_value`, `rate_risk_market_value`, `portfolio_dv01`, KRD, or the aggregate `duration_excluded_*` bridge. No class may receive a synthetic date, duration, DV01, market value, or `6M` bucket.
- Fund-like or other no-maturity rows must not receive a synthetic maturity date. They are excluded from the duration denominator and disclosed through `duration_excluded_market_value` / `duration_excluded_count` in the risk tensor API.
- `rate_risk_market_value`, `rate_risk_dv01`, and `rate_risk_modified_duration` expose the denominator used for the rate-risk duration view; `rate_risk_modified_duration` must reconcile to `portfolio_modified_duration`.
- `rate_risk_market_value`, `rate_risk_dv01`, `rate_risk_modified_duration`, `duration_excluded_market_value`, and `duration_excluded_count` must be computed by the Risk Tensor materializer and persisted in `fact_formal_risk_tensor_daily`; the formal read path must not recompute or silently backfill them from Bond Analytics.
- Risk Tensor materialization must persist the upstream Bond Analytics `source_version`, `rule_version`, and `cache_version`; a mismatch in any member of that lineage tuple blocks formal reads until rematerialization.
- Rollout order is schema migration v33, full-date Risk Tensor v3 rematerialization and lineage tie-out, then read-traffic cutover; legacy rows with NULL materialized metrics are blocked by design.

流动性缺口规则：
- `liquidity_gap_30d` / `liquidity_gap_90d` 必须按未来 30 / 90 天现金流口径计算，不得再按 `maturity_date` 对 `market_value` 做简单过滤。
- 到期本金现金流：`maturity_date` 落入窗口时计入 `face_value`。
- 票息现金流：按 `coupon_rate` 与 `interest_mode` 估算下一次付息；`annual` 计全年票息，`semi-annual` 计半年度票息，`quarterly` 计季度票息。
- 付息日估算锚点为 `maturity_date` 的月日（半年 / 季度按固定月间隔回推）；只计从 `report_date` 起最近一次付息日是否落入窗口。
- `bullet`（到期一次还本付息）只允许在到期日同时计入本金与票息现金流。
- 若同业负债 formal facts 可用，`liquidity_gap_30d` / `liquidity_gap_90d` 必须按 `资产现金流入 - 负债现金流出` 计算，不得只报资产侧毛额。
- 负债侧到期还本与资金成本现金流必须来自 `fact_formal_tyw_balance_daily` 的 `position_side=liability` 读面；资金成本按到期一次性付息的简化规则估算。
- 回售权 / 提前偿还现金流当前不进入 formal 风险张量；若输入行显式带有相关可选性字段，必须输出 warning，且不得静默并入口径。

## 11. result_meta

所有正式结果必须返回：
- `basis`
- `formal_use_allowed`
- `source_version`
- `rule_version`
- `generated_at`
- `trace_id`

## 12. ZQTZ / TYW Formal Balance

命名映射约定：
- `TYWL` 指源文件命名（例如 `TYWLSHOW-*.xls`）。
- `tyw` 指系统内部 source family / 表名命名（例如 `tyw_interbank_daily_snapshot`、`fact_formal_tyw_balance_daily`）。
- 本节出现 `TYW` / `tyw` 时默认指系统内部同一语义域，不表示另一套独立规则。

### 12.1 输入边界

`zqtz / tyw` 正式资产负债分析只允许读取：
- `zqtz_bond_daily_snapshot`
- `tyw_interbank_daily_snapshot`
- `fx_daily_mid`
- 治理 / 审批 / mapping 输入

禁止：
- 直接读取任何 `phase1_*preview*` 表
- 在 API / service / frontend 中重新实现正式规则

### 12.2 zqtz formal fact 规则

- `fact_formal_zqtz_balance_daily` 的金额事实来自 `zqtz_bond_daily_snapshot` 的正式投影。
- `invest_type_std` / `accounting_basis` / `position_scope` / `currency_basis` 必须在 `core_finance/` 中派生。
- `position_scope=asset` 时，默认排除 `is_issuance_like=true` 的发行类债券。
- `position_scope=liability` 时，只允许保留发行类 / 负债侧债券语义行。
- `position_scope=all` 时保留全量，用于审计与对账。

### 12.3 tyw formal fact 规则

- `fact_formal_tyw_balance_daily` 的金额事实来自 `tyw_interbank_daily_snapshot` 的正式投影。
- `principal_amount` 与 `accrued_interest_amount` 是正式读模型的基础金额字段；是否进入某个读模型口径，必须在 `core_finance/` 判定。
- `position_scope` 必须由 `position_side` 与治理映射共同确定，不允许 UI 临时解释。
- `funding_cost_rate` 是正式属性，不是展示层现算字段。

### 12.4 月均与汇率顺序

- 必须先生成逐日 formal amount，再按所选 basis 求月均。
- 当 `currency_basis=CNY` 时，必须先按每日 FX 中间价换算，再进入逐日 formal amount，再求月均。
- 不允许“先原币月均，后乘汇率”。
- 不允许用 preview rows 直接代替 formal daily facts。

### 12.5 当前状态说明

- 本节是当前 `zqtz / tyw` formal balance-analysis 的规则来源之一。
- 当前仓库已落地 governed formal compute / materialize、service / API 与首个 workbench consumer；已落地面以 `backend/app/core_finance/balance_analysis.py`、`backend/app/tasks/balance_analysis_materialize.py`、`backend/app/services/balance_analysis_service.py`、`backend/app/api/routes/balance_analysis.py` 与 `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` 为准。
- 本节不宣称超出上述已落地面的更多分析能力；后续扩展仍必须遵守 `backend/app/core_finance/` 唯一正式计算入口原则。

### 12.6 Liability Yield / NIM CNY Weighting

- `/api/analysis/yield_metrics` and executive NIM keep the existing formula: `nim = asset_yield - market_liability_cost`.
- ZQTZ yield rows must prefer `fact_formal_zqtz_balance_daily` with `currency_basis='CNY'` and `position_scope in ('asset', 'liability')` so foreign-currency bond assets are weighted on the same CNY basis as formal balance analytics.
- If formal CNY rows are unavailable for a requested date, the service may fall back to `zqtz_bond_daily_snapshot` for backward compatibility.
- Direct `invest_type_std` from formal balance rows must be used for H/A/T weighting decisions; portfolio names such as `FIOA` must not drive H/A/T inference.

## 13. Livermore 股票输入（观测层）

本节只约束 Choice/Tushare 落地到 DuckDB 的股票**观测**字段如何读，不扩展正式损益口径；字段清单与探针证据以 `config/choice_stock_catalog.json` 与 `docs/choice_stock_catalog.md` 为准。

- **涨跌幅、换手率、振幅（`daily_return_turnover_amplitude`）**：`PCTCHANGE`、`TURN`、`AMPLITUDE` 统一按**百分点**（percentage points）解释，例如 1.2 表示 1.2%；Tushare 回退路径与 `pct_chg`、换手率及由高低价与昨收计算的振幅标度一致。
- **涨跌停列（`daily_limit_flags`）**：Choice 的 `HIGHLIMIT` / `LOWLIMIT` 为涨跌停**标志**，不是限价价格。Tushare `stk_limit` 回退将限价**价格**写入同名观测列时，用途是支撑 `limit_ratio` 等由价格派生的指标，不得与 Choice 标志语义混读。

## 14. 禁止事项

- 不允许在 endpoint 或前端实现任何正式公式
- 不允许 Scenario 结果写入 Formal 事实表
- 不允许静默降级为 0 且不打标记
- 不允许未经测试修改 H/A/T、FX、516、发行类排除规则

## PR-2 Formal PnL FVTPL 517 Guard

- For `FVTPL`, `516` is the formal fair-value PnL component.
- `517` is excluded from formal `total_pnl` by default to avoid double-counting prior `516`.
- `FVTPL 517` may enter formal `total_pnl` only when `realized_flag=true` and `event_semantics` explicitly proves non-overlap with prior `516`, currently `realized_incremental` or `realized_no_prior_516`.

## Bond Analysis Fixed-Income Convention Guardrails

These guardrails document the current recommended owner-review convention set
for `PAGE-BOND-ANALYSIS-001`. They do not replace business-owner sign-off.

- `market_value_basis=clean`.
- `dirty_market_value = market_value + accrued_interest`.
- `accrued_interest_usage=dirty_price`.
- `carry and action attribution do not directly consume accrued_interest`.
- `day_count=ACT/365_approximation`.
- `yield_compounding=nominal_annual_with_coupon_frequency`（**已实证，2026-08-13**，非仅约定；证据见下方"YTM 复利口径实证"小节）.
- `duration_convexity_scope=vanilla_fixed_rate_only`.
- `DV01 = CNY face_value * modified_duration / 10000`.
- `dv01_unit=CNY_per_1bp`.
- `dv01_base=CNY_face_value`.
- `market_value/dirty_value DV01 is not the current formal DV01 convention`.

YTM 复利口径实证（2026-08-13，`.tmp-agent/ytm-compounding-empirical.md`）：

- 上条 `yield_compounding=nominal_annual_with_coupon_frequency` 已由真实账本实证，从"owner-review convention"升级为"已实证"。`bond_analytics/common.py` 的 `(1 + ytm/f)` 折现除数与源报价惯例一致，**付息频率 `f` 同时决定现金流时点与折现除数是正确行为**，不得拆成两个参数。
- 关键证据：源字段 `到期收益率` 不是市场收益率，而是账面实际利率 EIR——用它折现复现"摊余成本"中位残差 0.0123 元/百元，复现"公允价值"差 63 倍（0.7741），因此检验走会计恒等式、噪声底仅 0.006~0.032。在 63 只由应收/应付利息独立反推为半年付的券上（不含价格信息，无循环论证）：按 `f` 复利 RMSE 0.0100、63/63 全胜，年复利 RMSE 0.2621。反解隐含收益率，年复利口径实测偏移 +2.77bp，与"名义半年复利被误按年复利解读"的理论偏移 `(1+y/2)²−1−y ≈ y²/4 = +2.96bp` 在中位/均值/标准差三个矩上吻合。8 个报告日、6 个券种、4 个期限段、56 只零噪声平价券、以及一个价格侧独立倒推样本（250/252 选按 f 复利）全部一致。
- 局限（结论不外推到这些范围）：判别集仅占当日全簿公允价值 4.3%（63 只 / 193.6 亿），券种 76% 集中在地方政府债券（山东/青岛为主），有效独立样本量约 81 只券，只覆盖 2026-03 单月 8 天，`f=4` / `f=12` 未被非 ABS 样本覆盖，且乙口径仍有未解释的 −0.010 元/百元稳定小负偏。

Coupon-frequency authority（2026-07-20）：
- 正式 Bond Analytics 物化以 `interest_mode.coupon_frequency_per_year` 为唯一频率解析权威；`bond_analytics.engine` 必须把解析结果显式传入 Macaulay 久期、修正久期与凸性计算。
- `bond_four_effects`、`bond_duration` 与 `bond_analytics.common` 的默认参数仅为兼容入口，不构成正式业务口径；正式调用链必须显式传入频率。
- Campisi 正式归因当前尚未接入该权威：`merge_positions` 未保留 `interest_mode`，`campisi._coupon_freq` 仍按资产类别启发式取 1/2。切换该路径会改变历史归因结果，须经 owner 裁决并安排全期回归/重算；在此之前不得宣称 Campisi 与 Bond Analytics 已统一频率口径。

## Convexity single-caliber baseline（2026-08-12 建立；2026-08-13 P3 收敛口径 B、P4 升级为标准现金流凸性）

仓库内**只保留一套**凸性实现，且自 W-fi-2026-08 P4 起即为**标准现金流凸性**（按现金流对收益率求二阶导），不再是基于久期的近似式：

`C = Σ[CF_k × k(k+1) / (1+y/f)^(k+2)] / (P × f²)`，等价写作 `C = (D² + D/f + M²) / (1+y/f)²`，其中 `M²` 是现值加权付息时点方差（年²）。折现按 `f` 复利，与源 `到期收益率` 的报价惯例一致（见上文"YTM 复利口径实证"）。`C` 单位为年²，`y` 为名义年利率。

- **唯一在用口径**：`bond_analytics/common.py::estimate_convexity`。传入 `coupon_rate` 与 `years_to_maturity` 时走标准现金流路径（与 Macaulay 久期共用同一次遍历，见 `compute_macaulay_duration_and_convexity`）；缺现金流入参、零息或 `y<=0` 时退化为单笔现金流闭式解 `t(t + 1/f) / (1+y/f)²`——该式对零息券精确（`M²=0`）。
- **`y<=0` 不再特判 `D²`**：标准式在 `y=0` 处连续（旧实现 `y→0⁺` 给 `D(D+1)`、`y=0` 给 `D²`，跳变 `D`）。live 库 2026-07-31 有 18 笔 / 65.98 亿走该分支。
- **调用方**：`bond_analytics/engine.py::compute_bond_analytics_rows`（正式物化）直接调用一次遍历原语；`bond_duration.py::estimate_convexity_bond` 是委托薄封装（保留 Wind 覆盖分支：外部观测凸性优先），其下游 `bond_four_effects.py::compute_bond_six_effects`（→ `campisi.py::campisi_enhanced`）与 `krd.py::build_krd_position_metrics` 均已改为传入现金流入参。
- **`f` 敏感性**：改 `f` 会**同时**改变现金流时点与折现除数，这是正确行为。par 网格实测 `f=1→2`：Macaulay −0.74%~−1.41%、修正久期 +0.51%~+0.73%、凸性 −23.5%（1Y）~ +0.2%（30Y）。

已下线口径（仅作历史记录，`tests/test_convexity_caliber_baseline.py` 显式钉死不得复活）：

- **口径 A**（W-fi-2026-08 P4 下线）：`C = D(D+1)/(1+y/f)²`，`y<=0` 回退 `D²`。零息近似族：单笔现金流且 `f=1` 时与 `C_std` 精确一致，付息债系统性低估 `M²/(1+y/f)²`；且分子 `D(D+1)` 与 `f` 无关，而零息恒等式要求 `D² + D/f`，故 `f=2` 短端反而高估 `D/f`。par 3% 网格偏差 −20.4%（30Y f=1）~ +33.2%（1Y f=2）。
- **口径 B**（P3 下线）：`bond_duration.py::estimate_convexity_bond` 原有独立实现 `[D² + D(1+1/f)]/(1+y/f)²`（`y<=0` 时另乘 `1.1`）。相对 `C_std` 等价于强行假设 `M² = D`，无任何教科书近似族与之对应；`1.1` 系数同样无出处。偏差 −23.4% ~ +66.6%。

P4 的业务影响（live 库 2026-07-31 只读实测，1,750 行）：

- 组合层 `portfolio_convexity`（MTR-RSK-009）：29.79（当前代码旧口径）→ 33.20，**+11.42%**；相对库内持久化值 30.13 为 **+10.19%**。`portfolio_modified_duration` / `portfolio_dv01` **逐位不变**。
- 逐券：1,220 上调 / 2 下调 / 395 不变；中位 +1.18%，p95 +7.74%。按期限桶中位：2Y +0.59%、3Y +1.66%、5Y +2.71%、7Y +4.74%、10Y +5.38%、20Y +15.87%、30Y +19.25%。
- KRD 页曲线情景 `convexity_contribution` 全档 **+11.42%**（+100bp：4.424 亿 → 4.929 亿，占同档利率项 −109.76 亿的 4.49%）。
- Campisi 六效应（`campisi.py::campisi_enhanced` 分支）：`convexity_effect` +4.29%（2026-04）/ +8.21%（2026-06）/ +13.40%（2026-03），`cross_effect` −5.99%（2026-03），等额反向进入 `selection_effect`，`total_return` 与逐券闭合恒等式不变。注意 live 请求当前走 `_formal_bridge_to_enhanced_result` 直通分支，该分支不计算凸性，故线上 Campisi 输出实际不变。
- 规则版本：`bond_analytics` v1→v2、`risk_tensor` v5→v6（含对应 `cache_version`）。**需要一次全史重物化**（`fact_formal_bond_analytics_daily` 578 个报告日 / 874,367 行 → `fact_formal_risk_tensor_daily`），须独占写窗口，另行安排。

Credit-spread benchmark tenor（2026-07-20）：
- 信用利差逐券基准优先按 `years_to_maturity` 在同日国债曲线上线性插值。
- `years_to_maturity` 缺失、非有限或非正时，才回退 `tenor_bucket` 兼容口径。
- 评级利差 policy bucket 与本条国债基准期限插值是两套不同用途，不得互相替代。

## Period Yield Denominator（P1-05，2026-07-19）

`yield_by_period` / `liability_analytics.yield_by_period` 的期间收益率分母：

- 输入 `scale_amount` 为各 `report_date`（月末）市值快照。
- **同日**多业务种类：先按日求和得到当日组合规模。
- **跨日**季/年桶：分母 = 各日组合规模的算术平均（期间平均规模），不得对月末快照直接求和。
- 分子 = 桶内 `total_pnl` 之和；年化 = `(pnl / avg_scale) * (365 / num_days) * 100`。
- 单月桶仅一日快照时，平均退化为其本身，与历史月度行为一致。

## Curve-risk bucket field naming（2026-07-19）

`/api/bond-analytics/krd-curve-risk` 的 `krd_buckets[]`：

- 权威字段：`avg_modified_duration` = 桶内市值加权平均修正久期。
- `krd` 为同值弃用别名（过渡期保留）。
- 该字段**不是** `core_finance/krd.py` 的 key-rate duration 贡献，也**不是** `risk_tensor` 的桶内 ΣDV01。

## Fractional-period duration dual caliber（2026-08-12）

同一只碎期券（结算/报告日落在两个付息日之间）在仓库内有两套 Macaulay 久期实现，数值不同。两者并存，但**用途不可互换**：

- **正式口径 = 引擎街市惯例**：`bond_analytics/common.py::compute_macaulay_duration`。首期按碎期天数做分数幂折现（`(1+y) ** period_number`，`period_number` 带小数），期数按 `ROUND_CEILING` 取整。正式 Bond Analytics 物化（`bond_analytics/engine.py`）、`pnl_bridge.py` 走该实现，其结果即正式 DV01、修正久期与情景损益的来源。
- **近似口径 = 整期闭式**：`bond_duration.py::compute_macaulay_duration`。期数 `N = to_integral_value(years × frequency)`（Decimal 默认 `ROUND_HALF_EVEN`），不做碎期折现、不扣应计，等价于"恰好剩 N 个完整付息期"；另有两处上限保护：`剩余年限 ≤ 0.25 → 久期 = 剩余年限`、`Macaulay > 剩余年限 → 回退为剩余年限`。

误差量级（实测：coupon 4% / ytm 5% / 半年付，report_date `2026-03-20`，逐日扫 200–11000 天）：

| 剩余期限 | 两套实现最大相对差 | 最差点（引擎 vs 闭式，年） |
|---|---|---|
| 整期券（`years × frequency` 为整数） | ≈ 0.0002% | 4.5695 vs 4.5695，差异仅来自 1e-4 量化 |
| ≤ 3Y | 47.6% | 0.748 年：0.7381 vs 0.5000（闭式取整到 1 期并触发上限保护） |
| 3–7Y | 6.7% | 3.249 年：3.0461 vs 2.8543 |
| 7–15Y | 3.8% | 7.252 年：6.2675 vs 6.5154 |
| > 15Y | 2.3% | 30.005 年：16.2238 vs 16.6020 |

基准参考案例（`tests/test_bond_duration_goldens.py` 券5 同一组参数）：剩余 1000 天、票息 4% / ytm 5% / 半年付 → Macaulay `2.5940` 年（引擎）vs `2.4025` 年（闭式），相对差 `+7.97%`；修正久期 `2.5308` vs `2.3439`。

适用边界：

- 正式披露、正式 DV01、正式久期、情景损益一律以引擎街市惯例为准；闭式结果不得写入正式事实表，也不得与引擎结果混入同一汇总。
- 闭式仅适用于休眠模块（`krd.py`、`credit_spread.py`）与明确标注为估算的非出账路径。接线任一休眠模块前，必须先按本条确认久期来源。
- 误差由碎期驱动：整期券两套一致到量化精度，剩余期限越短、`years × frequency` 距离整数越远，闭式偏差越大；剩余期限 < 1 年时闭式不可用于任何对外数值。
- 两套实现的黄金测试各自独立锁定，不得互相引用对方的期望值来"对齐"。

## 15. Business Type Insights（批准口径，2026-07-15）

本节定义 `MTR-PNLBIZ-001`~`MTR-PNLBIZ-007` 的正式口径。Owner 为`组合管理/固收业务分析`，Approver 为`财务管理/资产负债管理`。定义自 `2026-07-15` 起生效，并由 `GET /api/pnl/by-business-insights` 的后端正式计算、DTO 与 `result_meta` 实现；`PAGE-PNL-BY-BUSINESS-001` 消费该结果。绑定 golden sample 证明公式和 DTO 一致性，不证明底层源 PnL、余额或汇率事实已经独立审计无误。

### 15.1 共同输入与父级行范围

- 报告范围：所选 `year` 年初至 `as_of_date` 的 YTD 区间；份额漂移的比较期见 15.4。
- 金额基础：人民币等值（CNY-equivalent）日均余额；外币资产必须先按治理汇率链路折算为人民币等值，再参与分子、分母及排序。
- 粒度：ZQTZ 父级业务种类，以稳定 `row_key` 对齐。
- 排除：`row_key` 含 `_detail_`、`business_type` 以“其中”开头、或 `source_note` 含“其中项”的明细/子项行。
- 仅 `avg_balance_cny_equiv > 0` 的父级行进入日均余额份额分母。
- 百分比统一以百分数值返回，例如 `12.34` 表示 `12.34%`；`pp` 表示百分点，不得再次乘以 100。
- 正式实现必须返回真实 requested/resolved cutoff、上游 source/rule/trace、quality/fallback 和 section availability；`result_version=v2` 还必须逐项披露 current YTD、baseline YTD 与各跨年月度组件证据。不得把请求日直接冒充为实际数据截止日，也不得把组件 fallback/vendor 异常包装成外层 `ok/none`。

### 15.2 集中度（MTR-PNLBIZ-001 / 002）

对合格父级业务 `i`：

```text
balance_share_i = avg_balance_cny_equiv_i / sum(avg_balance_cny_equiv)
MTR-PNLBIZ-001 HHI_pct = sum(balance_share_i ^ 2) * 100
MTR-PNLBIZ-002 top3_share_pct = sum(top 3 balance_share_i) * 100
```

- 排序按未舍入的 `balance_share_i` 降序；最终输出保留 2 位小数。
- 合格行不足 3 行时，Top 3 为全部合格行之和。
- 本指标是业务结构分析，不是监管或内部集中度限额；本次批准不设置 HHI 红黄线。
- 分母为 0 或无合格父级行时返回 `null`，不得返回 0。

### 15.3 负 FTP 持续性（MTR-PNLBIZ-003 / 004）

- 窗口：以 `as_of_date` 所在月为终点、向前包含 12 个自然月。
- 负 FTP 月：该月父级业务 `ftp_net_pnl < 0`；0、正数与 `null` 均不是负月。
- `months_observed` 只统计 `ftp_net_pnl` 非空的月份；缺失月不进分母，并中断连续月份。

```text
MTR-PNLBIZ-003 negative_ftp_month_share_pct
  = negative_month_count / months_observed * 100

MTR-PNLBIZ-004 negative_ftp_longest_streak_months
  = rolling_12m_window 内连续 ftp_net_pnl < 0 的最长自然月数
```

- 正式判断至少需要 `months_observed >= 6`。少于 6 个有效月时返回 `eligible=false`、`status=insufficient_observations`，比例和最长连续月数均为 `null`，正式指标显示为 `--`，不得触发提示。
- 当 `months_observed >= 6` 且 `negative_ftp_month_share_pct >= 50%` 时显示“负 FTP 持续性提示”。该提示只说明历史频率，不构成考核、退出、压降或限额结论。
- 跨年按 `month_key` 对齐；任何缺年或缺月必须进入 availability/quality 说明，不能静默补 0 或 forward-fill。

### 15.4 份额漂移（MTR-PNLBIZ-005）

- 当前期：所选 `year` 年初至 `as_of_date` 的 YTD 人民币等值日均余额份额。
- 比较期：上一自然年年初至同期间截止日的 YTD 人民币等值日均余额份额，不再使用上一年 `12-31` 全年口径。
- 对齐集合：当前期与上年同期间父级 `row_key` 的并集。
- 新进入业务：上年同期间侧份额按 0 处理；退出业务：当前期侧份额按 0 处理。两类业务都必须保留在输出中。

```text
MTR-PNLBIZ-005 drift_pp_i
  = current_ytd_balance_share_pct_i
  - prior_year_same_period_ytd_balance_share_pct_i
```

- 正值表示份额上升，负值表示份额下降；最终输出保留 2 位小数。
- 漂移必须由两期未舍入的原始余额/有效总分母相减，只在最终输出时舍入；不得先舍入两期份额再相减。
- 若任一期间没有可用总日均余额分母，该指标整体不可用并显式返回比较期缺失状态，不得把整个期间补 0。
- 上年同期间的 requested/resolved 截止日必须单独披露；若日历日不存在或数据未发布，不得静默改用上一年末。

### 15.5 规模—FTP后收益相对象限（MTR-PNLBIZ-007）

- X 轴：本节 15.2 同口径的 YTD 人民币等值日均余额份额（`balance_share_pct`）。
- Y 轴：同一 YTD 区间、同一父级业务的 `ftp_net_annualized_yield_pct`。
- 只有 X/Y 两轴均非空的父级行进入分割线与分类；合格行至少 6 行，否则不生成正式象限。
- X/Y 分割线分别为当期合格父级行的中位数；偶数行时取中间两值的算术平均。

```text
x >= median_x and y >= median_y -> large_high
x >= median_x and y <  median_y -> large_low
x <  median_x and y >= median_y -> small_high
x <  median_x and y <  median_y -> small_low
```

- 该象限仅描述当期业务相对位置。正式文案不得输出或暗示增配、压降、退出、考核或限额建议。
- 中位数会随当期业务集合变化，不得将不同期间的象限标签直接解释为绝对门槛变化。
- 正式分类必须由后端正式计算链路返回；前端只负责格式化和展示，不得自行重算中位数或象限。

### 15.6 未追溯趋势（MTR-PNLBIZ-006，diagnostic-only）

`MTR-PNLBIZ-006` 保持独立的 formal 对账健康度诊断：

```text
untraced_share_pct = untraced_formal_fi_row_count / total_formal_fi_row_count * 100
```

- `total_formal_fi_row_count = 0` 时返回 `null`。
- 诊断摘要必须返回 `available` 与 `availability_reason`：底层存储或查询失败为 `source_unavailable`；查询成功但滚动窗口没有 formal FI 观测为 `no_observations`。两者都返回空 `rows`，但不得解释为未追溯占比为 0；外层质量至少标记为 `warning`。
- 该指标必须使用 `metric_kind=diagnostic_only`，与业务分析指标分区展示。
- 它不得进入集中度、负 FTP、份额漂移或相对象限计算，也不得形成业务贡献、拖累、增配或压降结论。
