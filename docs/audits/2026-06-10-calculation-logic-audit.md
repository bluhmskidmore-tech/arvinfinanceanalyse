# 2026-06-10 系统计算逻辑与展示逻辑审计

## 审计范围与方法

- 审计对象：`backend/app/core_finance/` 全部正式与分析计算模块、前端展示链路（API client -> adapter/formatter/selector -> component -> chart/table）。
- 审计方式：5 条并行只读审计线（PnL 域、债券风险域、余额/ADB/负债域、前端展示链路、宏观/策略域），全程未修改任何业务代码。
- 口径权威依据：`docs/calc_rules.md`、`docs/metric_dictionary.md`、`tests/golden_samples/`、页面契约文档与既有测试断言。
- 边界说明：本会话未暴露 `moss-metric-contracts` / `moss-lineage-evidence` / `moss-data-catalog` / `gitnexus` 的直连 MCP 工具，口径核对使用本地文档与测试作为替代证据。大文件（`balance_analysis_workbook.py`、`qdb_gl_monthly_analysis.py`、`macro_bond_linkage.py` 等）为抽样精读，覆盖范围见各附录。本审计不构成业务 owner 签批，不改变任何页面的审批门状态。

## 测试验证证据

| 测试组 | 命令 | 结果 |
|---|---|---|
| 后端 core_finance 单元测试 | `python -m pytest backend/tests -q` | 79 通过 |
| 核心口径切片（PnL 物化/产品分类损益/FX 中间价/正式计算血缘/日均余额 API/债券分析服务/会计资产变动） | `python -m pytest tests/test_pnl_materialize_flow.py tests/test_product_category_pnl_flow.py tests/test_materialize_flow.py tests/test_fx_mid_materialize.py tests/test_formal_compute_lineage.py tests/test_adb_analysis_api.py tests/test_bond_analytics_service.py tests/test_accounting_asset_movement_service.py -q` | 172 通过 / 1 跳过 |
| 前端全量单元测试 | `cd frontend && npm run test -- --run` | 2438 通过 / 99 跳过；3 个失败文件单独重跑 135 个全部通过（并发负载与测试隔离问题，非产品 bug） |

注意：测试全绿不等于计算全对。下列多个 P1 正是"两套互相矛盾的口径各有测试冻结"，测试在互相背书。

## 总体结论

**正式金融计算主干可信**：正式 PnL 归属矩阵（514/516/517）、债券正式主链（DV01 面值口径、久期分母、风险张量）、正式余额事实（FX 先逐日折算后平均、发行类剔除）、会计资产变动双源对账，均与口径文档一致、Decimal 全程、缺数据 fail-closed。**未发现 P0**。

原审计发现 **11 项 P1**；其中 P1 #8（bond-dashboard 缺失值/假环比）已由当前工作区代码与测试证据关闭，剩余 **10 个 P1** 仍开放。开放项集中在三类根因：

1. 同一口径在仓库内有两套实现/两种符号约定，且各有测试冻结（缺业务裁决，不是缺代码）。
2. 前端违规补算正式聚合、把缺数据画成 0。
3. 个别对账检查为同源自比对，形同虚设。

## P1 问题清单（按建议处理顺序）

| # | 层 | 位置 | 问题 |
|---|---|---|---|
| 1 | 后端 | `balance_analysis_workbook.py:1215-1226` vs `balance_workbook/_analysis_tables.py:262-272` | Campisi 票息收入两套实现单位互斥（小数 vs 百分数），必有一个金额错 100 倍，且两侧各有测试冻结；`coupon_rate` 全链路无单位归一 |
| 2 | 后端 | `bond_analytics/engine.py:304-310` | 正式路径利率单位启发式 `abs>1 -> /100` 在 <1% 区间有盲区（0.85% 百分数形式会被当 85% 小数），久期/凸性/DV01 数量级全错的暴露面 |
| 3 | 后端 | `pnl_bridge.py:235-258` vs `attribution_daily.py:90-98` | roll_down（曲线滚动收益）符号在两个模块相反，各有测试锁定；calc_rules §9 未定义符号 |
| 4 | 后端 | `qdb_gl_monthly_analysis.py:292-302, 532-568` | position-vs-ledger 对账两侧同源同公式，diff 恒为 0，永不报警，虚假安全感 |
| 5 | 后端 | `yield_by_period.py:107-128, 148-164` | 季/年聚合把多个月末规模快照直接求和作年化分母，年化收益疑似被低估约 3 倍（年视图约 12 倍）；缺数值测试 |
| 6 | 后端 | `pnl_bridge.py:151` | `actual_pnl=0` 时 residual_ratio 强制 0、质量标记静默 "ok"，与 `attribution_core` 同场景（WARN）不一致 |
| 7 | 后端 | `macro_bond_linkage.py:442-447` | composite_score 中流动性分项符号极性与其余分项相反，资金宽松反而推高"宏观偏紧、缩短久期"结论 |
| 8 | 前端（已验证关闭） | `bond-dashboard/utils/format.ts:6-59`; `PortfolioTable.tsx:7-14`; `BondDashboardPage.test.tsx`; `format.test.ts` | 当前工作区已改为 null 感知：缺失 governed numeric 显示 "—"/"暂无数据"，当前值缺失时不产生假 "-100.00%" 环比，表格汇总遇缺失也 fail-closed；`npm.cmd test -- src/features/bond-dashboard/utils/format.test.ts src/test/BondDashboardPage.test.tsx` -> 2 files / 16 tests passed |
| 9 | 前端 | `BalanceMovementAnalysisPage.tsx:660-671` | 占比优先前端重算，后端 `current_balance_pct` 反成兜底；算不出时画 0% |
| 10 | 前端 | `pnl/yieldAnalysis/yieldAnalysisAggregates.ts:67-81`、`pnl/zqtzAdbAvgRollup.ts:7-49` | 前端补算正式 PnL 聚合与日均 rollup（违反"前端不得补算正式指标"铁律），浮点累加 + 与后端分类树行号级耦合 |
| 11 | 前端 | `CreditSpreadView.tsx:164-230` | 评级×期限热力图在前端聚合，桶映射硬编码在前端，与后端口径漂移无人察觉 |

## 各域可信度总览

| 域 | 可信度 | 说明 |
|---|---|---|
| 正式 PnL 归属（514/516/517、H/A/T、FX fail-closed） | 高 | Decimal 全程、缺汇率即报错、契约测试密集 |
| 债券正式主链（engine -> risk_tensor/read_models） | 高 | 与 calc_rules §10 逐条一致，残差全显式 |
| 正式余额事实（FX 折算顺序、发行类剔除） | 高 | 符合规则且有测试锚定 |
| 会计资产变动对账 | 高 | 真实双源比对，容差 0.01，能拦住不平 |
| 宏观/策略评分 | 中 | 1 个符号问题（P1 #7）；已确认未混入正式口径（module_registry 无注册、仅只读 fact_formal_*） |
| 前端 macro-toolkit / market-data / pnl-by-business | 高 | 缺失显式标注、合计来自后端、stale/fallback 承载完整 |
| PnL 桥接归因、季/年收益聚合 | 低 | P1 #3、#5、#6 |
| Workbook 展示层（Campisi/利率分布/利差 bp） | 低 | P1 #1，单位定案前不可信 |
| 前端 bond-dashboard、balance-movement-analysis | 低 | P1 #8、#9 |
| 前端 pnl yield-analysis 聚合、zqtz 日均 rollup | 低 | P1 #10 |

## 共性根因与处理原则

多数 P1 不是"算错"，而是**同一口径两套实现、两套测试各自锁定**（Campisi 单位、roll_down 符号、KRD 三义、凸性双公式、`get_credit_spread` 单位相反）。缺的是业务 owner 裁决并写入 `docs/calc_rules.md` 这一步。

处理顺序必须是：**业务裁决口径 -> 修订 calc_rules.md -> 统一实现 -> 修订错误一侧的测试**。先改代码只会把矛盾换方向。

## 下一步建议

1. 将 10 个剩余开放 P1 提交业务 owner 逐条裁决（每条给两个候选口径与影响范围）。
2. 裁决后逐条最小改动修复，并修订被冻结的矛盾测试。
3. 前端 #8 已在当前工作区验证关闭：`nativeToNumber`/bond-dashboard 展示链路已 null 感知，formatter + 页面测试通过。下一步不再为该项等待 owner 口径会，只需保持回归测试。
4. P2 级"口径待确认"项（各附录约 30 条：517 direct 翻号、KRD 三义、凸性双公式、缺到期日归最短桶、factor 阈值单位等）按附录清单登记到口径文档后逐步收敛。
5. 待 MCP 工具可用的会话中，用 `moss-metric-contracts` / `moss-data-catalog` 复核本报告中所有标注"口径待确认"的单位与字段契约（特别是 `coupon_rate`/`ytm_value` 落库单位）。

---

# 附录一：PnL 域审计明细

**结论**：正式 PnL 核心（`pnl.py` 的 514/516/517 归属矩阵）口径清晰、Decimal 全程、测试锁定充分，可信。但 PnL Bridge 和期间收益率聚合存在 3 个 P1 级实质疑点。

## 1. `pnl.py` — 可信，1 项口径待确认

全程 Decimal（`_coerce_decimal` 经 `str` 构造）；formal 归属矩阵（`_recognized_pnl_components`，555-567 行）与 calc_rules §3.3 逐条一致；FVTPL 517 防重复计 guard（570-576 行）与「PR-2」一致且有 `tests/test_pnl_formal_semantics_contract.py` 锁定；manual_adjustment 审批用状态字段精确匹配。

- [P2 口径待确认] pnl.py:35-37, 443-447 — direct_* 标志下 517 也翻符号，但 calc_rules §4.2 只写了 516 翻号；`tests/test_caliber_migration_subject_514_516_517_merge.py:37-48` 已把该行为锁为契约。建议补写 §4 或业务确认。
- [P3 口径待确认] pnl.py:506-507 — `currency_basis="CNX"` 时即使带 `fx_base_currency` 也静默取 rate=1。建议文档化。
- 加分项：FX 缺汇率直接 raise（509-516 行），符合 §7.1，无静默降级。

## 2. `pnl_bridge.py` — P1 级符号与质量标记疑点

- **[P1] pnl_bridge.py:235-258 — roll_down 符号与 `attribution_daily.py:90-98` 相反**。本文件向上倾斜曲线产出负 roll_down（`tests/test_pnl_bridge_roll_down_sign.py:48-57` 断言 `-450000`）；attribution_daily 同场景为正（业界标准口径）。calc_rules §9 未定义符号——口径待确认。
- **[P1] pnl_bridge.py:151 — `actual_pnl==0` 时 residual_ratio 强制 0 -> quality_flag="ok"**，即使 explained_pnl 很大；对照 `attribution_core.calculate_reconciliation:122-128` 同场景给 WARN + 诊断。`tests/test_pnl_bridge_core.py:478-502` 锁定了 ok 行为。违反 §14"不允许静默降级且不打标记"。
- [P2] pnl_bridge.py:244-252 — roll_down 时间锚点用当期剩余期限向未来滚，与桥接解释 prior->current 区间的回溯口径不一致。
- [P2 口径待确认] pnl_bridge.py:324-346 — fx_translation 用面值不用市值/脏价，且 FX 缺失静默回 0 不进诊断（`tests/test_pnl_bridge_fx_translation.py:80-113` 锁定）。
- [P2 口径待确认] pnl_bridge.py:73, 339-341 — `currency_basis` 被当 ISO 币种做 FX 查找，与 `pnl.py` 的 CNY/CNX 语义冲突，同名字段两套语义。
- [P3] pnl_bridge.py:494-500 — 质量阈值 0.05/0.10 与 attribution_core 的 0.05/0.15 不一致。

## 3. `pnl_yield_display.py` — 薄包装，承接上游隐患

- [P2 口径待确认] classification_rules.py:175（经本文件 52-77 行调用）— H/A/T 末位字符启发式作用于 portfolio_label，组合名 `FIOA` 末位 'A' 会被推成可供出售，与 calc_rules §12.6"FIOA 等组合名不得驱动 H/A/T"冲突（仅 V1 展示路径；正式路径 `pnl.py:_normalize_fi_invest_type` 只传 invest_type_raw，无此问题）。

## 4. `product_category_pnl.py` — 基本可信，2 项 P2

- [P2 口径待确认] :204-208 — qtd 视图叶子现金 = `-ending_balance`（疑似 YTD 口径）而非季度内流量求和，配季度天数年化，分子分母期间可能不匹配；`tests/test_product_category_pnl_flow.py:837-877` 只断言 monthly≠qtd 未断言数值。
- [P2] :304-329 — 情景重算 `ratio = scenario/baseline`，baseline FTP 为 0 时 ratio=0，情景 FTP 恒为 0，静默低估。
- [P3 口径待确认] :489-491 — monthly 视图 1 月用 `annual_avg_balance` 的特殊分支无文档。
- [P3 口径待确认] :13-18, 621-636 — 合计行 scale 与 pnl 的剔除集不一致（中收/衍生品计收益不计规模），需确认为有意口径。
- Formal/Scenario 隔离良好：`apply_scenario_to_rows` 纯函数，测试断言 formal 结果不变。

## 5. `product_category_pnl_attribution.py` — 可信

三因素分解（188-201 行）代数闭合精确；未解释项显式；合计层强制对账到实际差额。P3：`_days_in_month` 恒取整月天数（流程上 report_date 为月末，风险低）。

## 6. `attribution_core.py` — 基本可信

`calculate_reconciliation` 对 actual=0 的处理（122-128 行）是全仓正确范本。

- [P2 口径待确认] :202-203 — 无到期日合成默认久期 3.0 年，与 §10"无到期行不得赋合成到期"精神冲突（分析层）。
- [P3] :157-158 — `THIRTY_360` 恒返回 30/360 忽略实际期间；:152-156 — ACT_ACT 跨年区间近似。

## 7. `campisi.py` — 分析层可信，依赖两个启发式

四效应核心经查正确（income=coupon×face×days/365、treasury/spread=-MD×Δy×MV、AC 类市场效应归零、缺应计利息显式 diagnostics）；`tests/test_campisi_formula_golden.py` 黄金样本闭合通过。

- [P2 口径待确认] :117-128 — 评级推断靠资产类别关键词（含「银行」->AA+、兜底 AA），无治理映射表。
- [P2] :138-143 — 缺到期日合成 3.0 年期限。
- [P3] :9-11 — docstring 过期（实际阈值 `max >= 0.5`，rate_units.py:57-79，已正确覆盖低利率环境）。
- [P3] :283-305 — by_bond/totals 用 float 汇总（效应核心仍 Decimal），分析层可接受。

## 8. `campisi_decision_grade.py` — 结构好，1 项 P2

- [P2] :162 — `decimal_value(...) or Decimal("3")`：`Decimal("0")` 为假值，剩余期限恰为 0（已到期）或缺失都落到合成 3 年。应显式判 None。
- [P3] :28-34 — `decimal_value` 异常静默归 0 无诊断。
- 加分项：spread_dv01 路径单位换算正确；凸性二阶项 `0.5·C·MV·Δy²` 标准。

## 9. `benchmark_excess.py` — 分析层代理模型

- [P2 口径待确认] :84-93 — `dy` 取曲线值差无单位防护，若注入百分数形曲线会放大 100 倍。建议入口断言或复用 rate_units 启发式。
- 加分项：空载荷 + warning；恒带 `BENCHMARK_RETURN_CURVE_PROXY_NOT_WIND_INDEX` 警示。

## 10. `attribution_daily.py` — 本身正确，放大与 pnl_bridge 的矛盾

rolldown（90-98 行）`-MD×(y_re−y_pe)×MV` 为标准口径，与 pnl_bridge 相反（见 P1）。AC 类 rolldown 归零与四效应一致；residual 显式闭合到 `fact_pnl_daily.total_pnl`。P3：输出 float。

## 11. `yield_by_period.py` — 季/年聚合分母存疑（P1）

- **[P1 口径待确认] :107-128, 148-164 — 季/年桶把多个 report_date 的 `scale_amount`（当日市值快照，pnl_repo.py:1441）直接累加作分母**，再用区间天数年化：一季 3 个月末快照时分母约 3 倍平均规模，年化收益低估约 3 倍（年视图约 12 倍）。`tests/test_yield_by_period_core.py` 只覆盖 monthly。建议业务确认分母口径（应为期间平均规模）并补数值测试。
- [P3] :124-125 — `weighted_portfolio_yield` 与 `overall_yield` 同值占位。
- 除零保护良好（返回 None 而非 0）。

## 五项高风险口径核对（PnL 域）

| 口径 | 结论 |
|---|---|
| H/A/T 映射 | 正式路径与 §2 一致 ✅；末位字符启发式与 §12.6 FIOA 禁令相抵（V1 展示路径，P2 待确认） |
| 发行类债券剔除 | 经 `fact_formal_zqtz_balance_daily` + `position_scope='asset'` 完成 ✅ |
| FX 中间价折算 | pnl.py 缺汇率即抛错 ✅；pnl_bridge fx_translation 缺汇率静默 0 且基数用面值（P2） |
| 514/516/517 归并 | 运行时 assert 锁定 ✅；516 符号符合 §4.2 ✅；517 direct 翻号无文档（P2 待确认） |
| Formal/Scenario 隔离 | 纯函数不触事实表，测试断言隔离 ✅ |

---

# 附录二：余额 / 日均 / 负债 / 总账域审计明细

**覆盖说明**：全文精读 adb_analytics / adb_rate_normalize / adb_interbank_labels / balance_analysis / balance_calibration / liability_analytics_compat / liability_cockpit / accounting_asset_movement / accounting_basis_constants / zqtz_asset_bond_category / qdb_gl_monthly_analysis（约 2145 行）及全部基础工具；`balance_analysis_workbook.py`（1659 行）约 70% 行覆盖抽样；链路核对 materialize 任务、adb_analysis_service、snapshot_row_parse。

## P1（2 项）

### [P1] balance_analysis_workbook.py:1215-1226 + balance_workbook/_analysis_tables.py:262-272 — Campisi 票息口径两套实现单位互斥，主链实现内部自相矛盾

生产路径版本 `coupon_income = face_value × coupon_rate`（按小数假设）；拆分包版本 `× coupon_rate / 100`（按百分数假设），必有一个错 100 倍。主链同函数内 `spread_value = (加权利率 − 基准利率) × 100` 标注 bp，只有百分数假设才成立——与票息的小数假设**不可能同时正确**。证据：`tests/test_balance_workbook_campisi_rate.py:53,60` 冻结小数口径；`tests/test_balance_analysis_workbook_contract.py:846-883` 冻结百分数口径；源头 `snapshot_row_parse.py:34,168` 直接取 ZQTZ"利率"列原值，全链路无单位归一；`adb_rate_normalize.py:14` 在 ADB 域将同名 `coupon_rate` 显式声明为 percent。同时 `_RATE_BUCKETS`（1.5%~4.0% 百分数刻度）与"加权利率(%)"列也依赖百分数假设。**口径待确认**：必须先用真实 ZQTZ 数据确认"利率"列单位，再统一实现并修订其中一个被冻结的测试。

### [P1] qdb_gl_monthly_analysis.py:292-302, 532-568 — position vs ledger 对账为同源自比对，永不报警

两侧都来自同一个 m3 行集、同样的"科目前缀 1/2 求和"公式（:461-474 与 :552-563 逐字相同），diff 恒为 0，`threshold_yuan=0.01` 永不触发。真正的头寸源（ZQTZ/TYW formal facts）从未参与对账。建议接入独立头寸源，或删除该检查并标注"position 对账未接入"。

## P2 摘要

- [P2] adb_analysis_service.py:92-97, 1317-1332 + adb_analytics.py:178-181 — 单日窗口"日均"由 MD5 哈希 stable_factor（0.85~1.15）伪造，虽带 `simulated:true` 标记，但与页面契约"不得回填演示值"和 §14 冲突。口径待确认。
- [P2] adb_analytics.py:21-43 — 30 日移动平均把缺失日按 0 计入分子和窗口长度，与 summary 的 observed 分母语义在同一 DTO 内并存且未披露。
- [P2] adb_rate_normalize.py:12-17 — `coupon_rate` 声明 percent 与 Campisi 测试小数假设矛盾（见 P1）。
- [P2] classification_rules.py:169-175 — 尾字母启发式过宽（"CASH"->H、"FIOA"->A），`liability_analytics_compat.zqtz_asset_yield_weight:143` 把 portfolio 传入用于收益权重判 H，与 §12.6 张力。口径待确认。
- [P2] classification_rules.py:167-168 — 非标按 `interest_income > 0 -> H else T` 推断，未登记于 §2.2。口径待确认。
- [P2] liability_analytics_compat.py:169-175 — `normalize_bond_rate_decimal` 启发式 `>0.5 且 ≤100 才 /100`：百分数形式低票息（0.45 表示 0.45%）会被当 45% 小数。
- [P2] liability_analytics_compat.py:201-244 — 到期日缺失归入"3个月以内"最短桶，被 liability_cockpit MTR-LIAB-004 计入 1 年内到期压力，缺失数据静默放大短期压力。
- [P2] liability_analytics_compat.py:549 — `weighted_rate(...) or liability_cost` 把 Decimal("0") 当缺失短路回退。
- [P2] workbook 整体 — 单体与 `balance_workbook/` 包双份并行业务逻辑，Campisi 已实际分叉。
- [P2] balance_analysis_workbook.py:1024-1026 — 币种"汇率敏感性"=折算后余额×0.01，若行已是 CNY 口径会放大约 7 倍。口径待确认。
- [P2] qdb_gl_monthly_analysis.py:1441-1465, 1774-1780 — 11 位科目级损益归并硬编码且无"分项之和=总科目"行内对账。口径待确认。
- [P2] fx_rates.py:50-58 — 非营业日 carry-forward 回看窗口仅 3 天，长假（春节）会 fail-closed 误失败，与 §7.1 允许范围不符。口径待确认。
- [P2] reconciliation_checks.py — 全 float 实现（阈值 1 元），1e16 量级临界值附近判定可能抖动，与 Decimal 纪律不符。

## P3 摘要

balance_analysis.py 逾期天数全记本金利息恒 0（与源一致但字段名误导）；期限缺口主列不含发行类负债（卡片已披露）；两个剩余期限函数 365 vs 365.25；利率债缺评级默认 AAA；qdb 年化恒用 365；多张 sheet 硬编码 `startswith("2026")`（时间炸弹）；accounting_asset_movement OCI 桶只认 `1440101` 前缀；field_normalization 空 basis 默认 CNY、CNH 并入 CNY；decimal_utils 宽松版异常归 0；zqtz 单标签与多匹配函数并存（直接 sum 多匹配会双计）；liability_cockpit 阈值为内置常量。

## 核对通过项（重点）

- FX 顺序正确：materialize 逐行按 report_date 查当日中间价先折算再入 fact（§12.4）✅；`get_usd_cny_rate` formal 路径 fail-closed ✅。
- 发行类剔除：asset scope 下剔除 `is_issuance_like` ✅。
- 月均分母 = 当月去重 report_date（observed 口径，§5.2）✅。
- accounting_asset_movement 对账是真实双源比对（matched/mismatch/zqtz_only/gl_only，容差 0.01）✅。
- qdb：CNX−CNY=外币符合 §8 ✅；量价归因分解自洽 ✅；Decimal 全程 ✅。

---

# 附录三：宏观联动与策略评分域审计明细

**覆盖说明**：16 个目标文件全部通读（含 `macro_bond_linkage.py` 全文 1696 行）；`macro/` 目录抽样 equity_strategies / helpers / credit_spread_percentile。`docs/calc_rules.md` 与 metric_dictionary 中均无本域评分公式条目。

## P1（1 项）

### [P1] macro_bond_linkage.py:442-447 — composite_score 流动性分项符号极性与其余分项相反

`_score_liquidity`(L1107) 为"宽松=正"（资金利率上行 -> 负，`tests/test_macro_bond_linkage.py:681` 锁定），与轴判定和 `estimate_macro_impact` 一致；但 `composite_score = 0.4*rate + 0.3*liquidity + 0.2*growth + 0.1*inflation` 中其余分项均为"偏紧压力=正"，`+0.3*liquidity` 使资金宽松反而推高"宏观偏紧、缩短久期"结论。现有测试因利率分量饱和未覆盖该符号。**口径待确认**：若按"偏紧压力=正"，应为 `-0.3*liquidity_score`。直接影响页面久期建议文案方向。

**2026-07-03 remediation note**：按 Option B 修复，保留 `liquidity_score` 字段"宽松=正、偏紧=负"的既有语义；`composite_score` 统一为"对债不利/偏紧压力=正"，聚合时使用 `liquidity_tightness_score = -liquidity_score`，等价于 `0.4*rate - 0.3*liquidity + 0.2*growth + 0.1*inflation`。`environment_score` 直接输出 `composite_formula_version`；`build_macro_context_v1` 继续原样输出 `liquidity_score`，并新增 `score_polarity`、`composite_formula`、`composite_formula_version` 说明，避免下游把同名字段误解为偏紧分项。相关 rule/cache version 已提升；生产或历史物化输出需要按新版本刷新后才可视为不含旧公式污染。回归覆盖：隔离流动性时宽松不再触发"缩短久期"，偏紧会提高综合偏紧压力。

## P2 摘要

- cycle_macro_score.py:46-51 — `compute_price_spread_signal` pe<=0 分支返回标量、正常分支返回元组，类型不一致；:60-72 vs 189-193 — 缺分量重归一但 lineage formula 永远写满式权重；:88-98 — 无发布滞后/stale 检查。
- macro_bond_linkage.py:716-735 — market_timing 模式 LOCF 无最大滞后限制；:702-714 — conservative 模式月度宏观×日度收益率要求日期精确相等，月度序列实际被静默废弃。
- livermore_stock_candidates.py:366-403 — 基本面 overlay 缺数据股票整体剔除且 item 级无标记，去留取决于同日截面其他股票。口径待确认。
- livermore_theme_breakout.py:177-179, 215-218 — advance_ratio 在入口过滤后的强势股中计算，几乎恒接近 1，"广度"门失效。口径待确认。
- factor_screen_candidates.py:13-15, 183-189 — `MAX_ABS_ROE=0.60` 等过滤阈值按小数假设，若 factor_snapshot 按百分数落库会剔除几乎全部正常股票，字段单位无契约证据。口径待确认。
- hybrid_fusion_candidates.py:444-453 — lifecourt 正向权重和为 0.84（非 1），与 [0,1] cycle_score 融合量纲含混；:153-157 + hybrid_fusion_config.py:30-41 — evidence 公式串硬编码、YAML 权重无校验。
- source_preview_parsers.py:92, 106-108, 202-213 — 数值格式单元格 `str()` 后产生 `"110059.0"` 式代码污染，无数值->文本规整。口径待确认。

## P3 摘要

cycle M2 fallback 常量未用；速率方向归一 delta/level-std 量纲混合（已自标 v1）；`_MAX_LEAD_LAG_DAYS` 未引用；缺指标分项 score=0 进 composite（有 warnings）；livermore exposure 固定分母 4；仅识别 `stale` flag；z-score 缺失因子按 0 填充；`_gap_norm` 无 EPS；atu 区间开闭靠 `max==2.0` 魔数；hybrid 非 factor_screen 名单股票 factor_rank_score=0（缺数据当最差）；百分位阈值小截面粗化；action_attribution `total_pnl_from_actions` 字段名误导、mv<=0 存续持仓静默跳过；表头重名列静默覆盖、表头行位置硬编码；helpers `to_decimal_safe` 失败回 0；中位数取上中位。

## Formal / Scenario 隔离确认

**隔离成立**：module_registry / module_contracts 中无任何本域模块注册，`FormalComputeModuleDescriptor` 强制 `basis="formal"` 且 fact 表必须 `fact_formal_` 前缀；services 层对 `fact_formal_*` 仅 SELECT；页面均标 `formal_use_allowed=false`（metric_dictionary:436/438 样本真值）。P3 命名注意：macro_bond_linkage_service.py:235 复用 `build_formal_result_envelope` 作信封构造，basis 未越界但命名易误读。

## 核对通过项（重点）

权重和=1（cycle 0.40+0.35+0.25、sector 0.5+0.3+0.2、factor 五权重、fusion 0.65/0.35）✅；Pearson 相关 winsorize/除零/clamp 正确 ✅；突破/均量窗口均不含当日 ✅；回测防前视（昨日持仓结算今日收益）✅；alert_engine 阈值 Decimal、未知算子抛异常 fail-loud ✅；利差统一 ×100 BP 与 M9/M16 一致 ✅。

---

# 附录四：债券分析与风险域审计明细

**结论**：正式主链路（`bond_analytics/engine.py` -> fact 行 -> `risk_tensor.py` / `read_models.py` / `credit_spread_analysis.py`）的核心公式与 calc_rules 的 DV01 面值口径、久期分母规则、流动性缺口规则一致，未发现 P0。主要风险：单位启发式在 <1% 利率区间的盲区、同名指标多义（KRD 三义、凸性双口径、两个 `get_credit_spread` 单位相反）、大量 V1/V2 迁移模块未接线仅测试存活。

## bond_duration.py

- [P2] :232-251 — 凸性双口径且 ytm<=0 分支有任意系数：`estimate_convexity_bond` 分子 `D² + D(1+1/n)`、ytm<=0 返回 `×1.1`；`bond_analytics/common.py:254-262` 的 `estimate_convexity` 为 `D(D+1)/(1+y/m)²`、ytm<=0 返回 `D²`。docs 未定义凸性公式——口径待确认。
- [P3] :95-98 — ytm≈0 近似 factor 无文献出处；:101 — `n_periods` 银行家舍入吞碎期；:51-53, 191-192 — `SA`/`SCP` 前缀硬编码 0.25 年代理久期。
- ✅ Macaulay 闭式公式与 `modified = D/(1+y/m)` 正确。

## krd.py（未接线 legacy）

- [P2] 整体 — 仅测试引用，无 service/api 调用；线上 KRD 页走 `read_models.build_krd_distribution`，两者 KRD 定义不同（见"KRD 三义"）。建议标注 legacy 或删除。
- [P2] :385 — 桶分配为全额归属单桶，无相邻关键期限点权重拆分；KRD 之和=组合修正久期由构造保证但非真正 KRD（无局部曲线扰动重定价）。口径待确认。
- [P3] :276-279 — mv<=0 行计入 total 但跳过归属，权重和 <1；:219-232 — face 缺失静默回退 MV 无 warning。

## credit_spread.py（未接线）

- [P2] :173-181 — spread 曲线命中时当**小数**用，评级兜底是 bp/10000；`market_derived.py:81-112` 同名 `get_credit_spread` 约定曲线值为 **BP**。同名函数单位约定相反，误用放大 10000 倍。口径待确认。
- [P2] :251 vs 281-287 — `dv01 = face×SD/10000`（面值口径 ✅）但情景 PnL 用 `market_value×SD`，同一 payload 自相矛盾。口径待确认。
- [P3] :181 — 评级不在表内兜底 80bp 无质量标记。

## credit_spread_analysis.py（live）

- [P2] :192-196 — YTM 单位启发式 `abs<1 -> ×100` 在 <1% 区间有盲区（百分比形式 0.95 会被 ×100 -> 95%），与 engine 的反向启发式构成同类盲区。口径待确认（需上游单位契约证据）。
- [P3] :102 — spread_duration 直接取 modified_duration（近似合理，docs 未固化）。
- ✅ 利差 bp 换算、分位数、spread_dv01 面值口径正确。

## bond_four_effects.py

- ✅ 分解恒等式成立（selection 吸收残差，分解项之和恒等于 total_return）；六效应二阶项展开严格一致；AC 类归零符合 §3.2；income ACT/365 符合 guardrails；无应计利息退化路径显式 diagnostics。
- [P3] :139-140 — 效应基数为净价 MV，建议 guardrails 补注；:36 — 循环内 import pandas。

## cashflow_projection.py

- [P2] :361 — `modified_duration_gap = duration_gap`，名为修正久期缺口实为 Macaulay/期限代理缺口，从未除以 (1+y)。口径待确认。
- [P3] :493-503 — bullet 债缺起息日按一年票息兜底，多年期低估利息现金流；:565-567 — GBK 乱码 token 靠转义兜底，源文件编码已损坏；:584-589 — `_coerce_date` 非法日期直接抛错；:306-354 — 资产市值/tyw 本金混合（docstring 已说明）。
- ✅ 票息日期回推、权益久期 `gap × A/E`、1bp 敏感度、除零保护正确。

## risk_tensor.py / risk_tensor_regulatory_scope.py

- ✅ 与 §10 逐条一致：portfolio_dv01/cs01 求和、久期分母排除规则 + warning、流动性缺口、optionality 不并入；GS-RISK-A 覆盖 `regulatory_dv01 == portfolio_dv01` ✅；regulatory_scope 默认 include-all 与 MTR-RSK-001R 一致 ✅。
- [P2] risk_tensor.py:39-49 + common.py:278-295 — tenor 分桶双标准：common 无 15Y 桶（<=25 年归 20Y）、attribution_core 有 15Y 桶，同一只 13 年债两路径相差 20 年桶位（有 remap warning，但桶边界本身口径待确认）。建议统一 `get_tenor_bucket` 唯一实现。
- [P3] 30/90 天窗口边界含 T+0 与第 30 天 docs 未明确；`_estimate_coupon_cashflows` 等死代码；face 缺失回退 MV 不进 warnings 输出。

## var_engine.py（未接线、无专属测试）

- [P2] 整体 — 无任何 import；docs 无 VaR 口径。公式核对：z 值、√252、√10 缩放正确，但默认 `annual_yield_vol_bp=80` 硬编码、正态/完全相关加总未文档化。**在补齐口径定义与校准治理前不得接入页面**。

## risk_metrics.py / market_derived.py / curve_engine/

- [P2] risk_metrics.py:35 vs risk_tensor.py:304-307 — HHI 双标度（0–10000 vs 0–1），若 risk_metrics 被接入而未换算，集中度告警全失效。口径待确认。
- ✅ market_derived 利差/曲线/FTP 插值正确，启发式有 WARNING ✅。[P3] >4 年一律按 5Y 取利差期限。
- ✅ interpolation.py 自然三次样条（Thomas 算法）逐行核对正确，clamp 平推外推已声明；[P3] 非保形样条可能过冲，方法选择 docs 未记录。
- ✅ bootstrapper.py par->zero 自举与 DF log-线性插值正确；[P3] 首点 >1Y 也按零息率直读；bootstrap/NS/Svensson 仅测试引用未接线。
- ✅ nelson_siegel.py NS/Svensson 公式与 Nelder-Mead 实现核对无误。

## bond_analytics/（engine / common / read_models / dv01）

- ✅ engine 正式 fact 生产路径核心正确：`dv01 = CNY face × modD / 10000` ✅；发行类排除 ✅；无到期日 -> 久期/凸性/DV01 全零 ✅；report_date 不匹配抛错 ✅。
- **[P1] engine.py:304-310 — 利率单位启发式 `abs>1 -> /100` 在 <1% 处盲区，位于正式计算路径**。0.85%（百分比形式存 0.85）不会被除，按 85% 小数进入久期/凸性/DV01，数量级全错。需用数据目录证据确认 `ytm_value`/`coupon_rate` 落库单位，改为显式单位契约（rate_units 显式转换），消灭启发式。本域最高优先级。
- [P2] engine.py:127-148, 287-292 — 非 CNY 金额缺 CNY 字段时静默回退原币聚合，与 MTR-RSK-001"非 CNY 原币不直接入总"冲突，应打 warning/治理异常。
- [P2] common.py:161-213 vs bond_duration.py:67-127 — 同名 `compute_macaulay_duration` 两套实现且参数顺序不同、ytm<=0 行为不同，极易误用。
- [P2] read_models.py:408-420 — KRD 第三种语义（见下）。
- [P3] common.py:274-275 — 未知 tenor 静默返回 5.0；read_models benchmark 久期假设（国债 6/国开 5/AAA 4）硬编码 docs 未定义；同一 payload 百分数与 bp 双单位字段名不带单位；`days = (end−start).days + 1` 双端含与 bond_four_effects 调用方口径可能不一致；dv01.py classification_change 计 ΔDV01 全额驱动标签偏宽。
- ✅ read_models 曲线情景、roll-down 符号（上斜为正）、久期分母与 risk_tensor 一致 ✅；dv01.py 移动归因残差显式 ✅。

## 跨文件 — "KRD" 三义性（本域第二优先级）

| 路径 | 定义 | 量纲 | 桶值之和 |
|---|---|---|---|
| `risk_tensor.py:184-225`（/risk-tensor 页，formal） | 桶内 Σ DV01 | 金额（CNY/bp） | = portfolio_dv01 |
| `read_models.py:408-420`（KRD 曲线风险页，live） | 桶内市值加权平均 modD | 年 | ≠ 组合久期 |
| `krd.py:355-393`（未接线 legacy） | Σ(组合权重×modD) | 年 | = 组合修正久期 |

metric_dictionary 只定义了第一种（MTR-RSK-002~007）。用户在两个页面看到的"KRD 1Y"数量级与含义都不同。[P2] 口径待确认：建议为 bond-analytics KRD 页补 metric contract，并重命名 read_models 的 `krd` 字段（如 `bucket_avg_modified_duration`）或改为贡献口径。

---

# 附录五：前端展示链路审计明细

## 一、共享层（utils / api 基础设施）

**结论**：治理化 `Numeric`（raw+unit+display）链路设计良好，但各 feature 自带的"宽松取数函数"把 null 静默变 0，是全仓最大的系统性风险源。

- **[P1 closed] `bond-dashboard/utils/format.ts:6-59` — 缺数据渲染成 0 与假环比已关闭**：`nativeToNumber` 对 null/缺失/非有限值返回 null；`formatYi / formatRatePercent / formatDv01Wan / formatYears` 显示 "—"；`formatMomRatio` 在当前值、上期值缺失或上期为 0 时返回 null。`BondDashboardPage.test.tsx` 还覆盖缺失 governed numeric 不会生成 0-exposure 业务结论。
- **[P1] `bond-analytics/adapters/bondAnalyticsAdapter.ts:4-16` — 同样的 null->0 取数器**：`bondNumericRaw` 被图表直接消费（`CreditSpreadView.tsx:463/473` 饼图缺市值画 0、`:626-628` 情景损益缺失画 0 柱、`:707` credit_weight 缺失显示 "(0.0%)"）。同文件 `bondNumericRawOrNull` 才是正确范式，两者混用。
- [P2] `bond-analytics/utils/formatters.ts:50-62` — 同一页面两种字符串百分比约定（`formatPct` ratio×100 vs `formatPctPoint` 按已是百分数），靠调用方记忆字段语义，存在 ×100 双重换算风险。
- [P2] `backend/app/schemas/common_numeric.py:105-108`（跨边界）— pct 用 `abs(raw)>1 才 /100` 启发式：0~1% 区间百分数原值会被当成比率放大。建议后端消除启发式。
- [P3] `frontend/src/utils/format.ts`、`api/numeric.ts` 设计良好（null->"—"、单位感知、有测试）；`formatYuanAmountAsYiPlain:163` 非有限值 `return String(raw)` 会漏脏字符串到 UI。

## 二、average-balance（日均余额）

**结论**：null 处理纪律较好（大量显式 "—"），但偏离度/同比是前端派生计算，且分母异常时落 0。

- [P2] `AverageBalanceView.tsx:543-550` — 偏离度无数据时取 0，卡片显示 "+0.00%" 而非 "—"，`>5%` 预警静默失效；`adbComparisonMetrics.ts:6` 同样。建议返回 null。
- [P2] `AverageBalanceView.tsx:125-134, 561` — 前端计算同比%与偏离度（派生展示计算，有 null 保护与公式披露），与页面契约"missing 必须 surfaced"有张力，建议在契约登记这两个前端派生指标。
- [P2] `liabilityAdbClient.ts:92-107` — `requestEnvelopeOrPlainJson` 丢弃 `result_meta`，多个端点的 stale/fallback/quality 证据传不到页面（comparison/monthly 用 `...WithMeta` 保留，应统一）。
- [P2] `liabilityAdbClient.ts:169-171, 196, 210-215` — `Number(raw.x ?? 0)` 缺字段补 0，与同函数 null 保留字段不一致。
- [P3] AdbAccountingBasisSection/TrendChart 仅做 /1e8 换算与 "—" 处理，注释明确不重算正式口径——可信。

## 三、bond-analytics（债券分析）

- **[P1] `CreditSpreadView.tsx:196-230` — 前端聚合评级×期限市值占比（铁律边界）**：前端逐行 sum 市值出热力图占比，`:164-193` 期限桶映射（4Y->3Y 桶、15Y->10Y 桶）与评级桶硬编码在前端，与后端 `tenor_bucket` 口径漂移无人察觉。建议后端给聚合矩阵，前端只渲染。
- [P2] `TopHoldingsView.tsx:70-73, 120-128` — 前端 reduce 求 Top N 权重合计，缺失权重当 0 掺入。建议后端给 `top_weight_sum`。
- [P2] `BondAnalyticsInstitutionalCockpit.tsx:1539-1541` — creditWeight 双来源静默切换（risk 端点 `credit_ratio` 缺失回退 headline `credit_weight`），两端点过滤口径未必一致且 UI 不提示（`:1736` 同样）；`:1641-1662` 前端聚合评级分布面值。
- [P3] `toBp`（`bondAnalyticsHomeCalculations.ts:29-41`）单位换算与 raw=比率约定一致，正确。

## 四、pnl 相关 features

- **[P1] `pnl/yieldAnalysis/yieldAnalysisAggregates.ts:67-81` — 前端汇总正式 PnL 明细**：sum 利息收入/公允变动/资本利得/总损益并算占比，Decimal 字符串 -> Number -> 浮点累加。亮点：`addMoney` 遇 null 让整组变 NaN（不假装精确），但正确做法是后端提供聚合 DTO。
- [P2] `pnl/zqtzAdbAvgRollup.ts:7-49` — 前端复制后端分类树做父级日均求和，注释自述与 `zqtz_asset_bond_category.py` "sort_order 83–88 行一致"（行号级耦合）；子类部分解析即返回部分和，父级日均静默低估无降级标记。
- [P3] `pnlByBusinessPageModel.ts` 合计取后端 `summary.total_pnl`（好）；`formatAnalysisYieldPct`（raw 已是 %）与 `formatRatioPct`（×100）双约定并存靠命名区分；`pnlAttributionAdapter.ts` 的 stale/fallback/explicit_miss 状态推导是全仓最佳实践。

## 五、balance-movement-analysis（余额变动）

- **[P1] `BalanceMovementAnalysisPage.tsx:660-671` — 占比优先前端重算，后端值反成 fallback**：优先用前端 sum 的 total 重算占比，后端 `current_balance_pct` 反而兜底（方向应反过来）；算不出时落 0，缺桶画成 0%。

**2026-07-16 remediation note**：按 Option A 修复，`MTR-BMV-005` 将后端 `AccountingAssetMovementRowPayload.current_balance_pct` 记为正式展示唯一来源；`resolveBucketSharePct` 不再使用可见余额/合计重复计算，后端缺失或无效值保持 `null`。页面将缺失占比显示为 `—`，并在结构占比不完整时 fail-closed 隐藏结构图，不再展示由前端推导的 0% 或可比结论。回归覆盖 backend value precedence、missing-share display 与 chart suppression；残余边界是本修复不认证上游占比计算、来源血缘/新鲜度、页面 owner approval 或其他余额合计逻辑。

- [P2] 同文件 `:466-476, 635-643` — 矩阵合计前端求和且非有限值静默跳过（缺数据按 0 计入合计），无"含缺失"标记。
- [P2] 同文件 `:2979, 2987` — `shareDelta ?? 0` 把缺失占比变动显示成 "+0.00pp"。

## 六、bond-dashboard（债券仪表盘）

- **[P1] `PortfolioTable.tsx:17-19` — 汇总行前端求和 + 双口径混排**：市值/DV01/只数合计由前端 reduce（基于 null->0），同一汇总行 YTM/久期取自后端 headline KPI——同行两数据来源，组合缺数时合计偏小且与 KPI 不一致。
- [P2] `RiskIndicatorsPanel.tsx:13-15` — 久期/凸性 null -> "0.00"（共享层问题落点）。
- [P3] `CreditRatingBlocks.tsx:46` `|| 1` — 仅影响色块宽度，占比标签用后端值，可接受。

## 七、macro-toolkit / market-data

**结论：这两块纪律最好。** 缺失统一显示"缺失/无可比/暂无"（`MacroToolkitPage.tsx:1116-1137, 9216-9220, 10269-10281`），`?? 0` 基本只用于计数；as_of/stale/fallback（`freshness_status`、`fallback_date`、`stale_days`）在 DTO 和 UI 显式承载。mock 数据已验证只存在于 demo 工厂段内（`bondAnalyticsClient.ts:1071` 在 demo 工厂、真实工厂 `:1311` 起不含），envelope 正确标 `basis:"analytical" / formal_use_allowed:false`，未发现 mock 泄漏进真实路径。

## 前端总体结论

| 页面/链路 | 可信度 | 主要风险 |
|---|---|---|
| macro-toolkit、market-data | 高 | 无显著问题（P3） |
| pnl-by-business、pnl-attribution | 高 | 合计来自后端，状态推导规范 |
| average-balance | 中高 | 偏离度/同比前端派生 + 分母异常落 0（P2） |
| bond-analytics | 中 | 热力图前端聚合、桶映射硬编码、null->0 取数器（P1/P2） |
| balance-movement-analysis | 中低 | 占比前端重算优先于后端值、缺失计 0（P1） |
| bond-dashboard | 低 | 系统性 null->"0.00"、假 -100% 环比、汇总行前端求和（P1） |
| pnl yield-analysis 聚合、zqtz 日均 rollup | 低 | 前端补算正式 PnL/日均聚合，违反铁律方向（P1/P2） |

**优先修复建议（按收益排序）**：
1. 保持 P1 #8 的 formatter/page 回归测试，防止 bond-dashboard null-aware 展示倒退。
2. `BalanceMovementAnalysisPage` 占比改为优先消费后端 `current_balance_pct`。
3. `yieldAnalysisAggregates` 与 `zqtzAdbAvgRollup` 的聚合下沉到后端 DTO。
4. `liabilityAdbClient` 统一保留 `result_meta`，补齐 stale/fallback 展示。
