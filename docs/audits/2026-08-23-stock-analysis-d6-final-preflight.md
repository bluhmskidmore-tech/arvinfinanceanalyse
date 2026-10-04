# `/stock-analysis` D6 最终只读预检

- 日期：2026-08-23
- 页面：`/stock-analysis`
- evaluation date：`2026-08-18`
- requested audit range：`2024-08-18 .. 2026-08-18`（24 个月）
- observed trade-date range：`2024-08-19 .. 2026-08-18`（484 日）
- 本轮授权：只读预检与证据固化
- 明确未授权：live schema 变更、materialize、promote、rollback、PMI/正式信用脉冲 M2

## 1. 审批结论

**D6 live materialize / promote：NO-GO。**

受控 schema 与 task 状态机的代码链可以工作，真实库只读诊断也可以稳定完成；但生产闭环没有可供正式 D6 dry-run 验证的 canonical bundle，因此本轮不能签发 `stock_analysis_current_rule_cohort_dry_run_receipt`，更不能生成 materialize 或 promotion approval。

这不是“再执行一次”能解决的问题。当前缺的是生产证据生产链：approved calendar、source-availability receipts、zero-signal certificates、current-rule outcome/execution、matched-baseline PIT proof，以及把这些证据组装为 canonical bundle 的真实 producer。

## 2. Live 库身份与只读证明

| 项目 | 结果 |
| --- | --- |
| 目标库 | `F:\MOSS-V3\data\moss.duckdb` |
| SHA256 before | `2D076B5ACE4B51AA77C129FF767007DF795127D2C28170B3F4D9573D1F544074` |
| SHA256 after | `2D076B5ACE4B51AA77C129FF767007DF795127D2C28170B3F4D9573D1F544074` |
| 文件是否变化 | 否 |
| 文件最后修改时间 | `2026-08-23 08:56:44` |
| `_schema_migrations` max version | `45` |
| `stock_analysis_current_rule_%` 表数 | `0` |
| `choice_stock_daily_observation` | `2024-01-02 .. 2026-08-18`，636 日 |

预检期间本地前端、API 与后台 worker 仍在运行。只读 runner 自带前后哈希校验，本次未检测到并发改库；但未来正式写入前仍必须停止或隔离潜在写者，并通过 per-database writer lock 获得唯一写入权。

## 3. 484 日 current-rule selection 重跑

执行入口：

```text
.\.venv\Scripts\python.exe scripts\stock_analysis_current_rule_replay_dry_run.py \
  --duckdb-path data\moss.duckdb \
  --start-date 2024-08-19 \
  --end-date 2026-08-18 \
  --stock-candidate-policy exp3b \
  --max-workers 8 \
  --format json \
  --detail summary
```

| 指标 | 本轮结果 | 解释 |
| --- | ---: | --- |
| attempted dates | 484 | 全 observed 交易日已执行 |
| selection with signals | 159 日 | 诊断计数，不是 certified count |
| selection no signals | 170 日 | 未持久化 zero-signal certificate |
| policy inactive | 155 日 | `OFF/OVERHEAT` 日期单列 |
| candidate rows | 283 | current-rule selection 诊断行 |
| duplicate candidate rows | 0 | 本轮 selection 逻辑键无重复 |
| requested/resolved mismatch | 0 | 日期解析一致 |
| future business-date violations | 0 | 未发现 business-date 越界 |
| future availability violations | 380 / 262 日 | 存在 PIT availability 阻断 |

重跑结果与上一轮 `283 rows / 159 signal dates` 完全一致。其身份为：

- `certification_status = diagnostic_only`
- `formal_use_allowed = false`
- `replay_closure_evaluation.status = not_evaluated`
- `plan_digest = 6F18068FBD3029391259A002364110F7C714BCC34A3B5C37E21A0D5A82906ADA`
- `observed_date_axis_sha256 = 5E48AAE725C281CE03CD3BF4183E215CB57485AE4908B667E4531A42CD0BB497`
- `choice_stock_catalog_sha256 = 3EB8BF51BD739196F3EE5B0701B5928360051B00979D15E72EBEB747C72543A5`

因此 `283` 只能证明 selection 可重复执行，不能证明 T+5/T+20、matched alpha、连续 coverage 或 20/100 promotion readiness。

## 4. 24 个月 gap-ledger 的严格容量

| 日期状态 | 数量 |
| --- | ---: |
| `completed_with_signals`（observational） | 16 |
| `completed_no_strategy_signals`（observational） | 4 |
| `pending_tail` | 2 |
| `blocking_pending` | 13 |
| `unsupported` | 444 |
| `proxy_only` | 5 |

上表的 observational completed 合计为 20，但不能直接进入 `current_rule_certified`。严格认证口径为：

| Promotion gate | 当前 | 门槛 | 结果 |
| --- | ---: | ---: | --- |
| completed dates | 0 | 20 | FAIL |
| matched entries | 0 | 100 | FAIL |
| completed potential | 0 | 20 | FAIL |
| matched-entry potential | 0 | 100 | FAIL |

额外质量证据：

- candidate history `as_produced` duplicate logical keys：`14`
- current-rule strict-window candidate duplicate keys：`0`
- candidate history stale formula rows：`5532`
- stock-candidate selection stale formula rows：`10`
- execution stale formula rows：`0`
- matched-baseline stale formula rows：`0`

## 5. 当前硬阻断

1. `current_rule_certified_cohort_not_materialized`
2. `calendar_authority_unavailable`
3. `mixed_run_or_lineage_dates_present`
4. `current_rule_candidate_tuple_unavailable`
5. `matched_baseline_pit_proof_unavailable`
6. `zero_signal_receipt_not_persisted`
7. `insufficient_potential_completed_dates`
8. `insufficient_potential_matched_entries`

selection runner 还单独确认：

- `carry_forward_policy_unapproved`
- `future_availability_date_violation_detected`
- `selection_only_diagnostic_no_replay_maturity`

## 6. 为什么没有正式 dry-run receipt

正式入口 `build_stock_analysis_current_rule_cohort_dry_run()` 必须先收到一个落盘且自哈希正确的 canonical bundle，并逐项验证：

- approved calendar receipt；
- 至少一份 source-availability receipt；
- source key 与每条 fact/certificate 的 PIT 对齐；
- zero-signal certificate；
- T+5/T+20 execution 与 control entry/exit proof；
- 完整 version tuple；
- strict coverage、无 fallback、20/100 和零阻断；
- bundle target database identity；
- duplicate 与 existing-row audit。

仓库当前只有 bundle validator/materialize state machine；未发现从真实历史数据生成 production canonical bundle 的 producer，也未发现可复用的真实 bundle、approval 或 materialize receipt。测试里的 bundle 是隔离 fixture，不能用于 live 审批。

所以正确的 fail-closed 行为是：生成本 NO-GO 预检证据，不伪造正式 `dry_run_completed` receipt。

## 7. 下一轮最短闭环路径

1. 冻结并持久化 owner-approved calendar authority 与逐模块 carry-forward 上限。
2. 建立 production bundle producer：按 certified signal-date range 生成 fact、date certificate、zero-signal certificate、source-availability receipts 和 canonical plan/bundle hash。
3. 对同一 current-rule candidate keys 补齐 outcome maturity、execution 与 matched-baseline PIT control entry/exit/evaluation/source proof。
4. 清理或隔离 mixed lineage、stale formula 与旧 `as_produced` duplicate；旧历史不得混入 current-rule certified cohort。
5. 重新运行 gap-ledger；只有严格容量达到 `20/100` 且 blocking/unsupported/proxy/stale/duplicate 全为 0，才生成正式 D6 dry-run receipt。
6. 再单独请求 live 写入授权；获批后才执行 controlled v46、写前备份、inactive materialize、验收、promote 与 rollback drill。
7. promotion 成功后复核 M1-C 页面从 `schema_unavailable / insufficient` 转为 active certified cohort，并保持 `observational_only / formal_use_allowed=false`。

PMI/正式信用脉冲仍属于 M2：本 D6 路径不会把现有信用代理冒充为正式信用脉冲，也不改变其指标合同。

## 8. 验收摘要

| 验收层 | 结论 |
| --- | --- |
| controlled schema/task 代码链 | PASS（既有实现与隔离测试） |
| live 只读 selection 重跑 | PASS，结果稳定且库哈希不变 |
| 24 个月 gap-ledger | PASS，成功暴露真实阻断 |
| production canonical bundle | FAIL，不存在 |
| formal D6 dry-run receipt | NOT ISSUED，前置不满足 |
| live materialize | NO-GO |
| live promote | NO-GO |
| 页面 production closure | 继续 fail closed |

本轮未修改 `data/moss.duckdb`，未启用 controlled v46，未写入或晋升任何 cohort。
