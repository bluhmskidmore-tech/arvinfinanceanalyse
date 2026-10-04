# `/stock-analysis` D6a 前置证据包（只读）

- 日期：2026-08-21
- 页面：`/stock-analysis`
- 当前边界：`observational_only`、`formal_use_allowed=false`
- 本文性质：只读审计，不授权 schema 变更、不授权数据库写入、不修改任何代码

证据源：

- [PRD：`/stock-analysis` 生产数据证据闭环与信用周期指标治理](/F:/MOSS-V3/docs/plans/2026-08-21-stock-analysis-production-data-closure-prd.md)
- [评估：`/stock-analysis` 生产数据证据闭环与信用周期指标治理 PRD](/F:/MOSS-V3/docs/audits/2026-08-21-stock-analysis-production-data-closure-prd-evaluation.md)
- [`/stock-analysis` M1-A cohort 持久化设计（只读设计稿，未执行）](/F:/MOSS-V3/docs/plans/2026-08-21-stock-analysis-m1a-cohort-persistence-design.md)
- [484 日 current-rule selection 只读 runner](/F:/MOSS-V3/scripts/stock_analysis_current_rule_replay_dry_run.py)
- [runner 回归测试](/F:/MOSS-V3/tests/test_stock_analysis_current_rule_replay_dry_run.py)
- [既有验收矩阵](/F:/MOSS-V3/docs/audits/2026-07-18-stock-analysis-final-acceptance-matrix.md)

## 1. 最终结论

**D6a：NO-GO。**

原因不是“样本不够”，而是认证边界还没闭合：

1. 日历 authority 没有可持久化的认证源。
2. 484 日 current-rule selection diagnostic 已得到 `283 rows / 159 signal dates`，但认证结果仍是 `0 rows / 0 dates`。
3. 旧批次 `778` 只能留作诊断，不可并入 current-rule certified cohort。
4. snapshot freshness / carry-forward 语义未签字。
5. `283` 是 selection 诊断精确量，不是 certified row estimate 或交付承诺。
6. matched baseline 可重放，但缺持久化 entry / exit / evaluation / source proof，不能认证。
7. D6a 会进入受保护的 schema / 全局启动链；若没有其他迁移先落地，最小边界是编号 `45` 的新 SQL、schema manifest、`v46` migration registration 和 schema tests，影响风险为 `HIGH`。

## 2. 未授权边界

本轮不做以下事项：

- 不改前端页面。
- 不改后端业务代码。
- 不写 DuckDB。
- 不新建或修改 schema 迁移。
- 不回退、不覆盖已有 PRD / 评估 / 设计稿。
- 不把诊断结果伪装成 certified result。

## 3. 四路只读结果

### 3.1 日历 authority

| 项目 | 结果 | 含义 |
| --- | --- | --- |
| 观测交易日 | 484 天 | 已完成日历对账 |
| 可持久化 authority | 未建立 | 不能作为 certified source |
| strict coverage | 5 天 | 过窄，不能支撑连续认证 |
| 最长连续串 | 1 | 连续性证据不足 |

本次只读 live 对账中，Tushare `trade_cal(exchange='SSE')` 在 `2024-08-18..2026-08-18` 返回 731 个自然日和 484 个开市日；开市日集合与 `choice_stock_daily_observation`、`fact_market_breadth_daily`、`fact_choice_macro_daily.CA.CSI300` 的 484 个日期双向差集均为 0。但 DuckDB 内没有命名的 A 股交易日历表，live 结果也没有持久化 receipt / SHA。因此这只能证明“本次外部对账一致”，不能作为库内可重放 authority。

5 个 strict 日期为：`2026-04-30`、`2026-05-28`、`2026-07-10`、`2026-08-11`、`2026-08-18`，在权威交易日轴上全部孤立。其余日期包括 440 个没有正向 required-item audit 的日期、36 个 fallback-only 日期和 3 个 partial 日期。另有 `2025-09-21` 周日出现正向 audit，进一步证明 request audit 和 landed date 都不能代替交易日历。

结论：日历对账成立，但还没有可持续复用的 authority。即使 owner 接受本次 Tushare 来源，strict 连续覆盖仍只有 1 天，依然不形成 governed era。

### 3.2 current-rule replay

冻结 tuple 为：

```text
candidate history rule     rv_livermore_candidate_history_v1
candidate outcome formula  fv_livermore_candidate_forward_close_dual_adjust_v2
selection formula          rv_livermore_stock_candidates_bundle_v7
selection policy           exp3b
execution formula           fv_livermore_candidate_execution_dual_adjust_v5
baseline formula            fv_livermore_matched_baseline_v3
metric basis                net_next_open_adj
```

| 项目 | 结果 | 含义 |
| --- | --- | --- |
| 冻结 tuple | 已收敛 | 说明对象已定义 |
| 已物化 current-rule candidate rows | `0` | 没有可认证样本 |
| 已物化 current-rule dates | `0` | 没有可认证日期 |
| 只读 selection diagnostic rows | `283 / 159 signal dates` | 已得到精确诊断量，不等于 certified cohort |
| 只读日期 receipt | `484` | 329 个 WARM/HOT 执行日、155 个 OFF/OVERHEAT policy-inactive 日 |
| 旧批次 `778` | 仅诊断 | 不能混入 current-rule |
| snapshot freshness / carry-forward | 未签字 | 不能进入认证口径 |
| certified row estimate | 不可用 | 诊断精确量为 283；认证量仍取决于治理门 |

旧批次的 `778 rows / 209 dates` 虽然外层 policy 为 `exp3b` 且 selection formula 为 v7，但 outcome formula 全部仍是 v1，并且大部分嵌套 evidence policy 为 `default`，不能混入 current-rule cohort。现有 execution v5 有 `811 rows / 231 dates`，其中双期限可用且截至 evaluation 不含未来值的有 `473 rows / 146 dates`；它们也不能在缺 current-rule candidate key 证明时单独升级为 certified replay。

2026-08-21 已完成完整 484 日只读 selection diagnostic replay。冻结 selection tuple 在 329 个 WARM/HOT 日期均成功执行：159 个日期产生 283 行候选，170 个日期为零候选；另外 155 个 OFF/OVERHEAT 日期由 `exp3b` policy-inactive receipt 单独披露。规则版本、候选计数、重复逻辑键和 requested/resolved date 均未发现不一致。旧批次为 778 rows / 209 dates，与新 selection 结果仅重叠 114 rows / 66 dates，进一步证明旧批次不能当 current-rule 替代物。

输入侧仍没有闭合：行情表覆盖 636 个交易日，但 universe / membership / limit 只有 42 个快照日，factor 只有 27 个快照日。按“表内最新可用日期、并非 certified loader lineage”计算，universe / membership / limit 各有 209 天超过 30 天、33 天超过 90 天；factor 则有 292 天超过 30 天、116 天超过 90 天。宏观三分项共 1452 个 date-component 状态，其中 1192 个 missing、260 个 ready；从 data-gap evidence 结构化并去重后发现 380 条 future-availability 违规，覆盖 262 个日期。`livermore_gate_history` 仅 1 行，历史 market state 需要重算；carry-forward 最大年龄、缺失模块和 mixed lineage 的 fail-closed 规则仍未获批。

结论：484 日 current-rule **selection 诊断重放已完成**，但 replay maturity、pending-tail / blocking-pending、T+5/T+20、matched-entry 20/100 和 baseline PIT 在本 runner 中均明确为 `not_evaluated`。因此 current-rule 仍没有“可落地的认证样本”；283 是 selection diagnostic 精确量，不是预计物化量或交付承诺。

### 3.3 matched baseline PIT

| 项目 | 结果 | 含义 |
| --- | --- | --- |
| baseline v3 总行数 | `115520` | 说明原始 control 体量存在 |
| 持久化 entry / exit / evaluation / source proof | 缺失 | 不能认证 matched baseline |
| 双期限可证明 control rows | `28331` | 只证明一部分 control 覆盖 |
| 同时具备 20/20 双期限 control 的 candidate | `0` | 不能满足认证门槛 |

只读重放在 evaluation=`2026-08-18` 下证明：115,520 行的 entry executable 可全部重算并与存量标记一致；T+5 有 39,589 行、T+20 有 29,440 行能用现有复权因子重算且收益完全一致，双期限同时可证明的为 28,331 行。但现表没有 control entry / exit 日期价格、evaluation cutoff、调整因子、成本/调整模式、source/run lineage 和明确 failure reason；单个 candidate 最多只有 `17/20` 个 control 同时具备双期限证明。

上述 `115520 / 28331` 是全 signal-kind control 口径。与页面 replay 门槛直接相关的 stock-candidate 子集为 `15420 rows / 228 dates`，其中现有双期限收益字段非空为 `3710 rows / 150 dates`；这仍不是 PIT proof，也不得与全表数量混写成 `matched_entry_count`。

结论：算法可复现，不等于当时 PIT 截面已被持久化证明。没有 proof receipt，就不能把 replay 容量升级成 matched alpha 认证结论。

### 3.4 影响边界

| 项目 | 结果 | 结论 |
| --- | --- | --- |
| D6a 风险级别 | HIGH | 不适合直接跳到 D6b / M1-C |
| 新 SQL | `45_stock_analysis_current_rule_cohort.sql`（若无其他迁移抢先） | `45` 是文件编号，不是触点数量 |
| migration | `duckdb_migrations.py` 注册 `v46` | 会进入全局 schema startup 路径 |
| 其他最小触点 | schema manifest + schema registry / migration tests | D6a 不需要 task / service / API / frontend |

`register_all()` 的生产下游包括 API lifespan 的 schema upgrade、worker bootstrap 和二十余个 `apply_pending` 调用方，所以风险按 `HIGH` 管理。D6a 只审 schema；M1-B 应另建隔离 task / CLI，不改现有 Livermore materialize 主链；M1-C 再以新增只读 repository / service 接入现有 signal-confluence endpoint，前端不得传 `cohort_id`。

## 4. D6a / D6b / M1-C 分期

### D6a

只解决 schema 对象是否该被批准。

- 输出：三对象 schema、约束/索引、migration/manifest 登记和 schema tests
- 不输出：数据库写入
- 当前结论：`NO-GO`

### D6b

只解决受控写入是否可以开始。

- 前提：D6a 先通过
- 必需：独立 task / CLI、备份、全日历 dry-run、精确 planned row counts、幂等、receipt、hash 校验和 rollback drill
- 当前结论：`NO-GO`

### M1-C

只解决 API / 页面如何消费已认证结果。

- 前提：D6a / D6b 后存在且仅存在一个 active certified cohort
- 最小读路径：新增 cohort repository / service，切入现有 `livermore_signal_confluence_envelope`；不先重写 workbench 或页面主查询
- 当前结论：`WAIT`

## 5. owner 必须决策

| 决策项 | 需要 owner 明确什么 | 当前建议 |
| --- | --- | --- |
| calendar authority | 批准 `tushare.trade_cal:SSE` 的 realized calendar receipt，还是要求接入 SSE 一手源 | 未决定前 fail closed |
| calendar semantics | 是否接受 `realized_calendar_as_certified`，还是要求逐历史日期的 ex-ante 发布快照 | 未决定前 fail closed |
| strict coverage | 5 个孤立日期是否足以形成 governed era | 事实性不足，不可通过签字豁免 |
| carry-forward | universe / membership / limit / factor 的最大可沿用年龄，以及超限语义 | 必须给出逐模块上限；未签字前 fail closed |
| old 778 | 旧批次 778 是否可进入 current-rule 认证链路 | 不可 |
| mixed lineage / missing module | 是否允许 fallback 或混合 run/source 进入 certified | 默认不允许；若要改变须单独指标治理批准 |
| matched baseline proof | 是否要求每个 candidate 固定 20 个 control 均具备双期限 entry/exit/evaluation/source proof | 建议作为硬门；未满足不认证 matched alpha |
| D6a schema | 是否批准 D6a schema 对象 | 暂不批准 |
| D6b write | 是否授权后续受控写入 | 暂不授权 |
| M1-C | 是否允许页面消费未认证结果 | 不允许 |

## 6. 验收矩阵

| 验收项 | 结果 | 说明 |
| --- | --- | --- |
| 观测日期轴与 live 日历 484 日对账 | OBSERVED PASS / AUTHORITY BLOCKED | 当次集合一致；无持久化 calendar receipt，不能作为库内可重放 authority |
| strict coverage 5 个日期 | FAIL | 最长连续串仅 1 |
| current-rule 冻结 tuple | PASS | 但认证结果为 `0 rows / 0 dates` |
| 484 日 current-rule selection dry-run | PASS | `283 rows / 159 signal dates`，仅 diagnostic |
| 旧 778 混用 | FAIL | 只能做诊断 |
| snapshot freshness / carry-forward | BLOCKED | 未签字 |
| certified planned row estimate | BLOCKED | selection 诊断精确量为 283；认证 manifest/fact/certificate 计数仍不可用 |
| matched baseline 算法复现 | PASS | entry 全量一致，部分双期限收益可重算一致 |
| matched baseline proof 链 | FAIL | 缺 entry / exit / evaluation / source proof |
| 20/20 双期限 control | FAIL | candidate 数为 `0` |
| D6a 影响边界 | PASS | 已识别 HIGH 风险、SQL 编号 45 与 migration v46 切线 |
| owner 决策 | BLOCKED | 需明确签字 |

## 7. 主代理复核与验证结果

- `\.venv\Scripts\python.exe -m ruff check scripts\stock_analysis_current_rule_replay_dry_run.py scripts\stock_analysis_replay_gap_ledger.py tests\test_stock_analysis_current_rule_replay_dry_run.py tests\test_stock_analysis_replay_gap_ledger.py`：通过
- `\.venv\Scripts\python.exe -m pytest tests\test_stock_analysis_current_rule_replay_dry_run.py tests\test_stock_analysis_replay_gap_ledger.py -q -p no:cacheprovider`：`25 passed`
- 真实库 6 日串行 / 4 并发对比：date results、summary、plan digest 完全一致，哈希不变
- 真实库 484 日 dry-run（修复前已完成，本轮未重跑 selection）：`283 rows / 159 signal dates`，170 个 selection zero-signal、155 个 policy-inactive，future availability `380 violations / 262 dates`；原运行 receipt 的 v1 plan digest 为 `C38E722F41C385EA1E0ED3CB34ADF7E623CA8E0DB04A3304582718943F715835`
- 本轮把 plan digest 升级为 `stock_analysis_current_rule_replay_plan_v2`。对同一 484 日观测日期轴只重算计划身份（未调用逐日 selection loader），得到 v2 plan digest `6F18068FBD3029391259A002364110F7C714BCC34A3B5C37E21A0D5A82906ADA`、catalog content SHA256 `3EB8BF51BD739196F3EE5B0701B5928360051B00979D15E72EBEB747C72543A5`、observed-date-axis SHA256 `5E48AAE725C281CE03CD3BF4183E215CB57485AE4908B667E4531A42CD0BB497`；该 v2 digest 是当前执行计划身份，不冒充新的 484 日运行 receipt
- 独立 code review 与架构复审：本轮 runner / gap-ledger 增量均为 `PASS / APPROVE`，无 scoped blocking finding；duplicate strict window 已收紧到 exact current candidate keys。该结论不得外推为 outcome / baseline / certified closure 通过
- 主代理只读 SQL 复核：current outcome v2 精确 tuple `0 rows / 0 dates`；execution v5 `811 rows / 231 dates`、双期限 `473 rows / 146 dates`；baseline v3 总计 `115520 rows`，stock-candidate 子集 `15420 rows / 228 dates`，已有双期限字段 `3710 rows`，但缺 PIT exit/evaluation proof
- 主代理只读 SQL 复核：观测日期轴 `484`（`2024-08-19..2026-08-18`）；旧 v7 + 外层 exp3b `778 rows / 209 dates`；已物化 current tuple `0 rows / 0 dates`
- DuckDB 校验：`data/moss.duckdb` 哈希不变，仍为 `896FB0AB723ABF2044F80155919443314D82B759F53DEEB83BB7C9B690DC3E2F`
- 本轮只新增独立只读 runner、隔离测试并更新本审计；未改 schema、task 写链、service/API/frontend
- 本轮未写库

## 8. 结论摘要

进入 D6a 前还必须完成：

1. owner 冻结 calendar authority / semantics，以及逐模块 carry-forward 上限；5 天 strict coverage 不得通过签字豁免成连续时期。
2. 以获批 calendar / carry-forward / coverage 规则把本轮 484 日 selection receipt 升格为可认证 date certificate；当前 diagnostic receipt 不得直接 promotion。
3. 补跑同一 candidate keys 的 outcome maturity / execution / matched-baseline PIT，形成 pending-tail、blocking-pending、T+5/T+20 和 20/100 可审计进度。
4. 为 matched baseline 固化 control entry / exit / evaluation / source proof 字段与 receipt，并证明认证门槛所需的 control coverage。
5. 独立复核 mixed lineage、future availability 处置、certified row estimate 和回滚方案后，再单独请求 D6a schema 批准。
6. D6a 通过后才可请求 D6b；D6b 完成且 promotion 成功后才接 M1-C。

在这些决策完成前，`/stock-analysis` 的 D6a 结论保持 **NO-GO**。
