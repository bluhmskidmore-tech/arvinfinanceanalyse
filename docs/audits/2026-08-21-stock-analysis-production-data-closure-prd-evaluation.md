# 评估：`/stock-analysis` 生产数据证据闭环与信用周期指标治理 PRD

- 日期：2026-08-21
- 评估对象：`docs/plans/2026-08-21-stock-analysis-production-data-closure-prd.md`
- 评估方式：指标合同、历史回放治理、页面契约和独立可行性四路只读评审
- 总结论：`CONDITIONAL GO`
- 当前执行授权：用户于 2026-08-21 授权 `M1-A read-only only`；M1-B、D6a/D6b、schema 变更、数据库写入和 M2 仍为 `NO-GO`

## 1. 结论

PRD 的问题定义正确，底层能力大部分已经存在，项目具备实施可行性；但必须按两个独立里程碑推进：

- **M1 历史证据生产化：有条件可做。** 先完成只读 gap ledger，证明 current-rule PIT 历史确实可重放，再决定是否进入数据写入。
- **M2 正式信用脉冲：暂不具备开工条件。** 当前只有社融存量同比月差代理，正式公式、GDP 分母、1M/3M 变化窗口和 vintage 规则尚未签字。

不接受把“扩到 24 个月”“混用旧版本数据”或“降低 20/100 门槛”作为收口手段。

## 2. 评审中修正的四个错误方向

### 2.1 否决：机械扩窗到 24 个月

24 个月原始 `stock_candidate` 容量有 816 行，PIT 双期限执行结果有 473 行，但严格回放仍有 444 个 unsupported 日期。扩窗只会放大未认证历史，不能直接得到 ready。

### 2.2 否决：把所有页面状态压成一个枚举

transport、data availability、replay closure 和 refresh workflow 是不同维度。`HTTP success + stale + replay partial` 必须能够同时表达；单一状态会重新制造“看起来正常”的灰区。

### 2.3 否决：旧规则历史直接满足当前规则 ready

历史表已有 `formula_version / rule_version / run_id`，但当前 summary 主要披露 stale version，并未证明 ready 统计排除了旧版本。必须拆成：

- `as_produced`：历史诊断；
- `current_rule_certified`：current-rule ready 的唯一来源。

相关锚点：

- `backend/app/schema_registry/duckdb/28_livermore_candidate_history.sql:24`
- `backend/app/services/livermore_candidate_history_service.py:1364`
- `backend/app/services/livermore_candidate_history_service.py:1414`
- `backend/app/tasks/livermore_candidate_history_materialize.py:1047`

### 2.4 否决：把正式信用脉冲和历史闭环绑成一个实现包

当前代码明确把信用分项标为 proxy/pending product sign-off。M1 可以正确命名并治理该代理，M2 必须在独立指标合同批准后再实现。

相关锚点：

- `backend/app/core_finance/cycle_macro_score.py:44`
- `backend/app/core_finance/cycle_macro_score.py:112`
- `backend/app/services/market_data_livermore_service.py:1087`
- `backend/app/services/livermore_signal_confluence_service.py:716`

## 3. 可行性证据

### 3.1 已存在的可复用能力

| 能力 | 当前状态 | 评估 |
| --- | --- | --- |
| workbench 与 observational 边界 | 已实现 | 可复用 |
| current page gate 与 confluence fail-closed | 已实现 | 可复用 |
| candidate/execution history 版本字段 | 已实现 | 可复用 |
| outcome maturity task | 有锁、事务、run id、冲突仲裁 | 可复用 |
| execution stale formula 定位 | 已实现 | 可扩展 |
| replay date 分类 | completed/pending/unsupported/proxy-only 已存在 | 可提升为 certificate |
| `net_next_open_adj` | 已成为决策优先执行口径 | 可冻结 |
| 20 completed / 100 matched | 服务和测试已有边界 | 不应降低 |
| 日刷新终态 | completed/partial/failed 已实现 | 可串联 receipt |
| 10 个 module states | 已在前端逐项可见 | 无需再造 UI 总账 |

### 3.2 当前真实阻断

| 阻断 | 严重度 | 说明 |
| --- | --- | --- |
| current-rule 与旧版本样本未强制分轨 | High | 可能产生错误 ready |
| 444 个历史日期缺严格覆盖证明 | High | 不能只补有信号日 |
| 历史 PIT 源是否足以重跑 current rule 未证明 | High | 可能迫使项目前向积累 |
| 13 个 blocking pending | High | outcome/execution 仍有非自然尾部缺口 |
| 当前信用分项被命名为 credit impulse | High | 代理可能被误当正式指标 |
| M2/GDP vintage 和月度映射未定义 | High | 存在 look-ahead 风险 |
| 24 个月聚合性能 | Medium | 当前路径有逐日 coverage 调用风险 |
| Livermore 属 excluded analytical surface | Medium | 实现和测试需 scoped authorization |

## 4. 指标评估

### 4.1 PMI

`M0017126`、NBS pinned release、business date 和 freshness 链路已存在。PMI 可在 M1 继续使用，但必须把原始指数水平与归一化得分分开披露。

评估：`GO for M1`。

### 4.2 当前信用分项

当前值是 `M5525763` 社融存量同比的相邻月差，单位 ppt；现行代码仍允许 `M0001385` 广义货币 M2 同比作为 credit fallback。两者适合作为有明确标签的信用扩张代理，不足以称为正式 credit impulse。

评估：

- 更名并继续作为 M1 analytical proxy：`GO`；
- D2 批准后把广义货币 M2 fallback 降为仅展示：`CONDITIONAL GO`；这是 authority 行为变更，D2 未批前不得实施；
- 直接升格为正式信用脉冲：`NO-GO`。

### 4.3 正式信用脉冲

“滚动 12 月社融增量 / 最近已发布的滚动四季度名义 GDP，再取 1M 或 3M 变化”具备研究合理性，但仓库尚无完整 PIT join、GDP vintage、修订和月度对齐合同。

评估：`NO-GO until owner metric sign-off`。

## 5. 数据治理评估

### 5.1 不能只认证 217 个有候选日期

444 个 unsupported 日期中有 217 个出现候选，包含 771 条候选和 440 条 PIT 双期限结果。即使这些行全部补齐，也不能跳过其余日期；否则缺失日期可能隐藏本应出现的候选，形成选择偏差。

### 5.2 24 个月原始容量不等于 current-rule 容量

473 条 PIT 双期限结果可能跨多个规则版本。M1-A 必须先给出当前版本分布和可重放容量。若 current-rule 合法样本不足 100，产品必须接受 `insufficient`，而不是扩大语义或降门槛。

### 5.3 双 cohort 需要独立持久化身份

现有表虽然包含版本、run 和 execution 证据，但没有显式 `cohort_id`；现有 execution 修复还会按日期/逻辑键替换行。仅靠 run-id 前缀或“最新版本”无法同时保证 `as_produced` 不被覆盖和 current-rule 选数可审计。

因此 PRD 已选择专用 cohort manifest、current-rule replay fact 和 date certificate 作为推荐最小对象。M1-A 必须提交具体 DDL/迁移/回滚并获得 schema 受保护边界批准；批准前不得进入 M1-B。

## 6. 架构与页面评估

### 6.1 页面不是本轮主风险

当前首屏、deep trace、刷新、stale/fallback 和 module-state 可见性已经有针对性测试。下一轮只需消费后端认证结果，不应再在前端建立第二套 ready 算法。

### 6.2 权威对象按职责拆分合理

- workbench 决定 review queue；
- confluence 决定闭环/replay/macro authority；
- `firstScreenDecisionGate` 组合既有后端事实并 fail closed；
- 首屏和深研复用同一个 confluence payload。

其中 replay closure 与 macro authority 必须独立输出；只有最终首屏门禁组合二者，不能让当日宏观状态反向改变历史 replay certificate。

评估：`GO`，前提是接口不重复计算和重复请求。

### 6.3 刷新必须继续 task-layer 单写者

读路由不可因“闭环刷新”写库。若需要新 refresh 接口，只能复用现有 `POST + Idempotency-Key + run_id + status` 模式，并由 task 完成实际写入。

评估：`GO with guardrails`。

## 7. 实施规模评估

以下是相对估算，不构成排期承诺：

| 里程碑 | 规模 | 主要不确定性 |
| --- | --- | --- |
| M1-A 合同 + 只读 gap ledger | S–M | current-rule 版本分布与 PIT 源可用性 |
| M1-B current-rule replay + 证据修复 | M–L | 历史源快照能否合法重放、写入批次量 |
| M1-C API/UI/刷新/验收 | M | closure DTO 与现有 confluence 的最小边界 |
| M2 正式信用脉冲 | M–L，独立项目 | GDP vintage、月度映射、1M/3M 决策 |

建议三条并行执行线：数据/task、指标/core-finance、页面/验收；由主代理做合同整合和最终验收。M2 不与 M1-B 共用发布门。

## 8. 开工门禁

### 8.1 M1-A 开工前

- [x] owner 已授权按 PRD 的 D1–D5 边界执行 M1-A；
- [x] 明确这是 excluded Livermore surface 的 scoped implementation；
- [x] 继续保持 observational only；
- [x] 未授权数据库写入。

### 8.2 M1-B 数据写入前

- [x] M1-A gap ledger 完成并通过只读、PIT 和真实库对账；
- [ ] current-rule PIT 重放可行性已证明；
- [ ] `governed_era_start` 由来源覆盖确定；
- [ ] 写入计划、预计行数、批次、目标 DB 绝对路径已确认；
- [ ] 目标 DB 已备份并校验哈希；
- [ ] dry-run、plan digest、idempotency、receipt 和 rollback 通过测试；
- [ ] owner 单独批准 D6a schema 对象；
- [ ] owner 单独批准 D6b 数据写入。

### 8.3 M2 开工前

- [ ] 正式 metric contract 已签字；
- [ ] credit universe、GDP 分母、1M/3M、revision/vintage 规则已冻结；
- [ ] 官方源、发布时间和历史覆盖已验证；
- [ ] proxy/formal 并存与迁移策略已批准。

## 9. 最终 Verdict

| 范围 | Verdict | 原因 |
| --- | --- | --- |
| PRD 作为 M1-A planning basis | `PASS, NOT D6 APPROVAL` | M1-A 边界和验收合同已落地；不构成 schema 或数据写入授权 |
| M1-A 只读 gap ledger | `PASS` | PIT 分类与现有服务逐项对齐；真实 DuckDB 哈希前后不变；current-rule 容量保持 fail closed |
| D6a schema 对象 | `NO-GO NOW` | strict 连续覆盖、fallback 语义、candidate version 分拆和 matched-baseline PIT proof 尚未闭合 |
| D6b 数据写入 | `NO-GO NOW` | D6a 未批准，且预计写入行数、备份、dry-run receipt 与 rollback drill 尚未具备 |
| M1-B 历史写入 | `NO-GO NOW` | 必须先证明 PIT 可重放并单独授权写入 |
| M1-C 页面收口 | `WAIT FOR M1-B CONTRACT` | 页面只消费认证结果 |
| M2 正式信用脉冲 | `NO-GO NOW` | 指标定义与数据合同未签字 |
| 降门槛或混样快速收口 | `REJECT` | 违反业务正确性和可追溯性 |

评审后的推荐顺序是：**批准 PRD → 只读 gap ledger → 评审写入计划 → 分批修复 → API/页面验收；正式信用脉冲另立指标门。**

## 10. M1-A 实施验收记录

- 评估截面：`2026-08-18`
- 最大审计搜索范围：24 个月，`2024-08-18 .. 2026-08-18`
- 观察交易日：484
- PIT 状态：completed `20`（有信号 `16`、零信号 `4`）、pending `15`（自然尾部 `2`、历史阻断 `13`）、unsupported `444`、proxy-only `5`
- 严格覆盖：5 个日期，最长观测连续串 1；缺权威交易日历证明，因此不可认证连续性
- fallback 诊断：41 个 eligible 日期，其中 34 个 fallback-covered；默认不得进入 certified cohort
- current-rule 容量：candidate rows `0`、completed capacity `0/20`、matched capacity `0/100`
- 重复审计：candidate as-produced 逻辑重复键 `14`；current-rule strict window `0`。旧批次重复只作诊断，不阻断当前版本元组
- PIT 缺口：matched baseline 缺少 control exit-date/evaluation proof，不能认证 matched alpha
- 只读证明：`data/moss.duckdb` 运行前后 SHA-256 均为 `896FB0AB723ABF2044F80155919443314D82B759F53DEEB83BB7C9B690DC3E2F`
- 独立复审：目标脚本/测试 `PASS`，无 HIGH/MEDIUM finding

结论：M1-A 交付本身通过；`/stock-analysis` 的 current-rule 历史证据仍是 `NO READY`。D6a、D6b、M1-B 与 M2 均未获放行。

D6a 的后续只读深查（日历 authority、完整 current-rule tuple、matched-baseline PIT control proof、预计物化量与 schema 影响面）见 [D6a 前置证据包](/F:/MOSS-V3/docs/audits/2026-08-21-stock-analysis-d6a-preflight.md)。该证据包的结论仍为 `D6a NO-GO`，不构成 schema 或数据库写入授权。
