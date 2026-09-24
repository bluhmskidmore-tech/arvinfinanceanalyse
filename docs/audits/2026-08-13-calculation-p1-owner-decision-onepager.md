# 2026-08-13 计算口径 P1 业务拍板一页纸

- 这是什么：8 项挂起的 P1 计算口径决策（P1-01~06、P1-10、P1-11）的压缩拍板清单，自 `2026-06-10-calculation-p1-owner-decision-matrix.md`、`-packet.md`、`-snapshot.json`（2026-08-06 刷新）与 `post-owner-execution-plan.md` 提炼，并已对照 `docs/calc_rules.md` 与现行代码核实。
- 怎么用：owner 逐条回复"P1-XX 选 A/B/C"即可；标"疑似已解决"的项只需回复"确认"或"改选 X"。正式留痕须按决策包契约写成 `Option <字母> - <选项原文>`。
- 拍板后由谁落地：工程按 post-owner-execution-plan 各切片落地到 `docs/calc_rules.md`、capture 模板（`2026-06-10-owner-decision-capture-template.zh.md`）与对应实现/测试，再重跑 `python scripts\refresh_calculation_p1_owner_decision_snapshot.py` 与系统审计完成度校验。
- 关键发现：8 项中 7 项的工程实现已在 2026-07~08 的提交中按单一口径落地并有回归测试，但治理登记（capture 模板）仍全部 pending；本次拍板多数是"确认既成口径"，仅 P1-11 需要真实改造。

## P1-01 Campisi 票息收入的票面利率单位

- 一句话问题：源表 `coupon_rate` 是"2.85 表示 2.85%"还是"0.0285"？单位认错，票息收入差 100 倍（出处：decision-matrix P1-01 行）。
- 备选口径：A 源值为小数；B 源值为百分数、计算须 ÷100；C 源必须带显式单位元数据、缺失即失败。
- 推荐：**B**（新建议，证据：2026-07-19 系统计算审计"取证 1"裁决落库单位为百分数，单体版与包版 Campisi 实现均已按 ÷100 统一并有双实现一致性回归；原材料推荐 C）。
- 影响面：Campisi 票息收入/利差收入、余额分析工作簿的两条实现路径。
- 拍板后动作：补 `docs/calc_rules.md` 单位条目 + capture 模板补记；实现与测试已在位（`balance_analysis_workbook.py`、`balance_workbook/_analysis_tables.py`、`tests/test_balance_workbook_campisi_rate.py`）。
- 状态：**疑似已解决，待确认**。证据：commit `fa074e13`（2026-07-19）；测试文件头注明"落库单位裁决为百分数（2.85 = 2.85%）"。

## P1-02 债券分析引擎的利率单位（进久期/DV01 之前）

- 一句话问题：`ytm_value` 与票面利率进 DV01/久期计算前按什么单位读？0.85 这类低利率被当成 85% 会毁掉久期、凸性、DV01（出处：decision-matrix P1-02 行）。
- 备选口径：A 全部源利率为小数；B 全部源利率为百分数；C 源提供显式单位元数据。
- 推荐：**B**（新建议，证据：`bond_analytics/engine.py` 已依据 2026-07-19 审计取证 1 无条件 ÷100（经 `rate_units.normalize_percent_rate_to_decimal`），>20% 拒为脏值；旧 `>2 → 当小数` 启发式已删除——它曾把每日约 550 只低票息券读错；原材料推荐 C）。
- 影响面：正式 Bond Analytics 物化全链路——久期、凸性、DV01、风险张量、情景损益。
- 拍板后动作：补 `calc_rules.md` 源单位条目 + capture 补记；保留 sub-1% 利率回归。若改选 C，需把无条件 ÷100 改成显式元数据 fail-closed（属重做）。
- 状态：**疑似已解决，待确认**。证据：`engine.py::_normalize_rate_decimal` 现行实现与注释。

## P1-03 曲线滚动（roll-down）收益的正负号

- 一句话问题：同一段曲线变动，PnL 桥接和日度归因曾给出相反符号的 roll-down，管理层叙事互相打架。
- 备选口径：A `attribution_daily` 约定 `-MD * (y_realized - y_prior) * MV`；B 当时的 `pnl_bridge` 约定；C 两套并报、显式标注。
- 推荐：**A**（沿用原推荐）。上行曲线产生正 roll-down，三处实现同一符号。
- 影响面：PnL 桥接、日度归因、bond_analytics read_models 三处口径一致性。
- 拍板后动作：仅需 capture 模板补记；`calc_rules.md` 第 9 节已写符号 + 时间锚约定（2026-07-03 owner 决策 Gate 1 Option A、Gate 2 三处对齐），`tests/test_pnl_bridge_roll_down_sign.py` 已冻结正确方向。
- 状态：**疑似已解决，待确认**。证据：三处实现均为 `(current − rolled)/100 × MD × MV`（`pnl_bridge.py`、`attribution_daily.py`、`bond_analytics/read_models.py`）；规则入库 commit `72c1b410`（2026-07-06）。

## P1-04 QDB 头寸-总账对账：控制还是诊断

- 一句话问题：现有"头寸 vs 总账"对账两边同源、差异恒为 0，是虚假保证——要么接独立源当真控制，要么明确降级为诊断。
- 备选口径：A 要求独立的头寸与总账源锚；B 保留同源比较但标注"非控制"。
- 推荐：**B**（新建议，证据：`qdb_gl_monthly_analysis.py` 已把该检查改名为"总账聚合公式自检占位（不具备独立对账能力）"，告警类型 `ledger_self_check_placeholder`；该模块被 `tests/AGENTS.md` 限定为 analytical-only，低成本接独立源不可行。原材料推荐 A 仅针对"要作控制主张"的场景——若未来要作控制主张再升级 A）。
- 影响面：QDB 总账月度分析页的对账告警语义；治理层面不得再出现"控制"表述。
- 拍板后动作：capture 补记 + 确认 UI/报告沿用"自检占位"措辞；QDB GL core/API 测试证明标注路径。若改选 A 需另立阶段接独立头寸源。
- 状态：**疑似已解决（按 B 落地），待确认**。证据：commit `332da7f4`（2026-07-06）。

## P1-05 季度/年度收益率的分母

- 一句话问题：期间收益率分母用什么规模？把月末快照直接求和当规模，季度收益被低估约 3 倍、年度视图约 12 倍（出处：decision-matrix P1-05 行）。
- 备选口径：A 期间平均规模；B 月末快照求和；C 有日度事实时用加权日均。
- 推荐：**A**（沿用原推荐；原推荐为 A/C 二选一，已落地 A）。
- 影响面：`yield_by_period` / 负债分析期间收益率的月、季、年全部桶。
- 拍板后动作：仅需 capture 补记；`calc_rules.md` 已有专门条目"Period Yield Denominator（P1-05，2026-07-19）"，实现（`_avg_scale_across_report_dates`，快照日规模算术平均）与 `tests/test_yield_by_period_core.py` 已在位。
- 状态：**疑似已解决，待确认**。证据：commit `fa074e13`（2026-07-19）同时落规则与实现。

## P1-06 实际盈亏为零时的残差质量标志

- 一句话问题：`actual_pnl=0` 但解释项非零时，对账质量还能标"ok"吗？按 B 会把重大残差藏在 `quality_flag=ok` 后面。
- 备选口径：A 零 actual + 非零解释/残差 → warning/未定义；B 强制 ratio=0 并标 ok。
- 推荐：**A**（沿用原推荐，与 fail-loud 控制原则一致）。
- 影响面：PnL 桥接 `residual_ratio` / `quality_flag` 的可信度与下游对账展示。
- 拍板后动作：capture 补记 + `calc_rules.md` 补一行质量规则；实现已是 A（actual=0 且 explained≠0 → ratio=None → warning），`tests/test_pnl_bridge_core.py` 的两条零 actual 用例已冻结该行为。
- 状态：**疑似已解决，待确认**。证据：commit `9ccb4dc2`（2026-07-03）；`_calculate_residual_ratio` 现行实现。

## P1-10 正式聚合算在前端还是后端

- 一句话问题：正式 PnL/收益率/日均余额的聚合数字允许前端自己算吗？前端 float 化、类目树复制会漂移出治理口径。
- 备选口径：A 只用后端 DTO；B 前端可派生展示聚合；C 前端只派生明确标注的非正式 UI helpers。
- 推荐：**A（正式指标）+ C（标注的非正式 helpers）**（沿用原推荐）。
- 影响面：PnL 相关页面正式数字与后端治理值的一致性。
- 拍板后动作：capture 补记；`zqtzAdbAvgRollup.ts` 已改为消费后端 `/api/pnl/by-business-ytd` 父级 `avg_balance`、不再前端拼合（commit `6b9314d8`，2026-08-12），未接线的 yieldAnalysisAggregates 已随死代码删除（commit `559de28d`，2026-08-12）；选 C 部分需给非正式 helper 定标注约定 + 对应 vitest。
- 状态：**疑似已按 A 方向落地，待确认边界**。

## P1-11 信用利差"评级 × 期限"矩阵的归属

- 一句话问题：信用利差页的评级 × 期限热力图由谁聚合？前端硬编码桶会与后端期限/评级规则漂移且无检测。
- 备选口径：A 后端提供治理矩阵；B 前端聚合明细行并拥有桶映射。
- 推荐：**A**（沿用原推荐）。
- 影响面：信用利差页评级-期限热力图；桶边界口径一致性（单页展示层）。
- 拍板后动作：选 A：新增评级-期限矩阵 API 契约，`CreditSpreadView.tsx` 改为仅渲染后端矩阵，更新 `frontend/src/test/CreditSpreadView.test.tsx` 桶边界与缺矩阵回归；选 B：在页面契约显式记录前端拥有桶映射并补同样回归。
- 状态：**未解决**，8 项中唯一仍需真实工程改造的项。现状即 B 行为（`buildRatingTenorHeatmapData` 仍从 `bond_details` 明细行前端聚合）。注意：`calc_rules.md` 2026-07-20 的"Credit-spread benchmark tenor"条目是逐券基准插值口径，不解决本项矩阵归属。

## 汇总表

| P1 | 一句话问题 | 推荐 | 影响面级别 |
| --- | --- | --- | --- |
| P1-01 | Campisi 票面利率单位（百分数还是小数） | B 百分数 ÷100（确认既成） | 高 |
| P1-02 | 债券分析引擎利率单位（进久期/DV01 前） | B 百分数（确认既成） | 高 |
| P1-03 | 曲线滚动收益正负号约定 | A attribution_daily 约定（确认既成） | 中 |
| P1-04 | QDB 同源对账是控制还是诊断 | B 标注非控制（确认既成） | 中 |
| P1-05 | 季/年收益率分母 | A 期间平均规模（确认既成） | 高 |
| P1-06 | 零 actual 残差质量标志 | A warning/未定义（确认既成） | 中 |
| P1-10 | 正式聚合前端还是后端 | A 后端 DTO + C 标注 helpers（确认既成） | 中 |
| P1-11 | 评级×期限矩阵归属 | A 后端治理矩阵（需实施） | 低 |

## 边界

本文件是只读调研产物：不选择或批准任何口径、不修改代码或 `calc_rules.md`、不写治理记录、不认证页面。"疑似已解决"仅指工程实现与规则文档已按某选项落地，正式生效仍以 owner 拍板 + capture 模板补记 + 快照刷新为准。
