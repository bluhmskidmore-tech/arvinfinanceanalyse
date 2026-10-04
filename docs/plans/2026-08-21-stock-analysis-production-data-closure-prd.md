# PRD：`/stock-analysis` 生产数据证据闭环与信用周期指标治理

- 日期：2026-08-21
- 页面：`/stock-analysis`
- 当前页面 ID：`GAP-STOCK-ANALYSIS-PAGE`
- 当前边界：`observational_only`、`formal_use_allowed=false`
- 文档状态：评审通过；用户于 2026-08-21 授权的 **M1-A 只读实现已完成并验收通过**。M1-B、D6a/D6b、schema 变更、数据库写入和 M2 仍未授权
- 评估结论：见 `docs/audits/2026-08-21-stock-analysis-production-data-closure-prd-evaluation.md`

## 1. 一句话结论

下一轮不是继续增加股票页面模块，而是把现有“代码闭环”升级为可审计的“生产数据证据闭环”。项目拆成两个独立里程碑：

1. **M1：历史回放证据生产化**——只让同一 current-rule、PIT 安全、连续覆盖认证的样本进入 ready 判定。
2. **M2：正式信用脉冲治理**——先冻结定义和数据合同，再实现；不得把现有社融同比月差代理冒充正式信用脉冲。

M1 与 M2 分别验收、分别放行。M2 未批准不阻止 M1 进行只读设计和历史缺口预演，但不得借 M1 偷偷固化正式信用脉冲公式。

## 2. 背景与当前基线

### 2.1 已完成的技术闭环

当前系统已具备以下能力：

- `/stock-analysis` 的 workbench 主包和只读观察边界；
- 后端候选队列、市场门控、宏观门控、对抗门、风险退出和信号汇流；
- 前端统一 `firstScreenDecisionGate`，首屏和深研区复用同一结论对象；
- replay 的 `ready / partial`、成熟度、双期限收益、自然 pending tail 与阻断 pending 分类；
- 日刷新 `completed / partial / failed` 终态和页面缓存失效；
- 后端 10 个 Livermore `module_states` 在前端逐项可见；
- PMI 与信用扩张代理已经从同一 PIT 宏观快照进入市场门控和 confluence。

这些能力证明页面已经“能解释”，但不等于历史证据已经可认证。

### 2.2 2026-08-18 真实数据基线

本 PRD 使用 2026-08-21 的只读审计结果作为 planning baseline，不将其视为黄金样本或正式指标批准：

| 项目 | 当前结果 |
| --- | --- |
| resolved as-of | `2026-08-18` |
| PMI | `49.2`，业务日 `2026-07-31` |
| 信用分项 | `0.00 ppt`，当前为社融存量同比月差代理 |
| MacroScore | `0.571667` |
| 宏观 authority | `ready`（现有代理合同） |
| adversarial gate | `block` |
| confluence | `blocked_by_adversarial` |
| 180 日 replay | `partial` |
| 180 日 replay 明细 | completed `11`、pending `10`（其中 blocking `8`）、unsupported `98`、proxy-only `2`、matched `0` |

### 2.3 24 个月容量审计

机械地把窗口从 180 天改成 24 个月不能解决问题：

| 项目 | 24 个月审计结果 |
| --- | ---: |
| 严格窗口日期 | 484 |
| completed | 20 |
| pending | 15 |
| natural pending tail | 2 |
| blocking pending | 13 |
| unsupported | 444 |
| proxy-only | 5 |
| `stock_candidate` 历史行 | 816 |
| PIT 下 T+5/T+20 均可用的执行行 | 473 |
| unsupported 中实际有候选的日期 | 217 |
| 上述日期的候选行 | 771 |
| 上述日期已有双期限执行结果的行 | 440 |

结论：原始样本容量可能足够，但严格证据覆盖远未闭合。更重要的是，上述原始行可能混合多个 `formula_version / rule_version`，只能证明容量，不能直接满足当前策略的 ready 门槛。

## 3. 产品目标

### 3.1 M1：历史回放证据生产化

让研究人员能够回答：

1. 当前策略版本的回放证据是否成熟？
2. 哪一段日期已被连续认证？
3. 每个日期为什么是 completed、自然 pending、阻断 pending、unsupported 或 proxy-only？
4. ready 样本是否全部来自 current-rule、PIT 安全的执行口径？
5. 如果不能继续复核，阻断来自宏观 authority、对抗门、候选有效性，还是 replay 治理？

### 3.2 M2：正式信用脉冲治理

让产品和指标 owner 能够回答：

1. 页面显示的是信用扩张代理还是真正的信用脉冲？
2. 公式、分母、变化窗口、单位、频率和发布时间是什么？
3. 历史 as-of 请求是否只使用当时已经发布的数据？
4. 当正式指标缺失时，代理是否并存、是否降级、是否允许进入 ready gate？

## 4. 不可变边界与非目标

本项目不做：

- 不把 `/stock-analysis` 升级为 `PAGE-STOCK-*` 正式投资决策页；
- 不新增或批准 `MTR-STOCK-*`；
- 不改变 `formal_use_allowed=false`；
- 不生成买入、卖出、调仓、配置或执行批准；
- 不降低 `20 completed dates + 100 matched entries` 门槛；
- 不用静态 fixture、总历史行数或 walk-forward 展示报告冒充生产闭环证据；
- 不只补“有候选”的日期；零信号日期同样需要完整运行证明；
- 不在 API、service 或前端写 DuckDB；所有写入只能通过 `backend/app/tasks/` 或调用 task 的受控脚本；
- 不修改现有 candidate/execution history 表的既有语义或覆盖其 `as_produced` 行；current-rule cohort 若需独立持久化，必须使用第 5.4 节的专用对象并单独通过 schema 受保护边界评审；
- 不重构全局认证、队列、缓存、SDK 或应用状态架构。

## 5. 核心产品决策

### 5.1 首屏权威拆分

页面不再追求一个“万能事实源”，而按业务对象固定权威：

- **候选成员、顺序、数量**：`workbench.first_screen.review_queue`；
- **闭环、宏观、对抗门、replay 成熟度**：同一次 `signal-confluence` 结果；
- **最终首屏门禁**：后端事实进入同一个 `firstScreenDecisionGate`，首屏和深研区复用，前端不得重新计算金融指标；
- `modules.main.result` 仅用于同 `(source_module, stock_code)` 补充详情，不得新增、删除或重排候选；
- confluence 只能请求一次并在首屏、深研和追溯区复用。

### 5.2 回放双轨样本合同

必须把两类样本拆开：

| cohort | 作用 | 能否满足 current-rule ready |
| --- | --- | --- |
| `as_produced` | 还原历史真实生产输出，允许多版本，用于诊断和版本迁移分析 | 否 |
| `current_rule_certified` | 用当前冻结规则对 PIT 历史快照重放，且经过连续覆盖、执行口径和版本认证 | 是 |

旧版本数据不得仅因已有收益结果而进入 current-rule ready。历史补证只能证明来源完整，不能自动证明旧规则与当前规则等价。

### 5.3 治理时期选择

- 24 个月是**最大审计搜索范围**，不是为了凑够 100 条而自动选取的 readiness 窗口。
- `governed_era_start` 必须由数据源可重放性、版本和覆盖证明确定，不得根据收益结果或样本数量反向挑选。
- 从 `governed_era_start` 到 evaluation date 必须是连续交易日覆盖；不得跳过没有候选或结果不理想的日期。
- 如果连续可认证时期内不足 100 条，状态保持 `insufficient`，等待前向积累或完成更早历史的合法认证。

### 5.4 Cohort identity 与持久化合同

现有 candidate/execution history 没有显式 `cohort_id`，且现有修复任务会按日期或逻辑键替换执行行，因此不得把 current-rule replay 写回同一逻辑键后再声称保留了 `as_produced`。

M1 的目标持久化合同冻结为：

- `as_produced` 继续只读现有 candidate/execution history，不改写其身份；
- `current_rule_certified` 使用独立的 DuckDB 物化对象，至少包括：
  - cohort manifest：`cohort_id`、状态、requested/certified 范围、完整 source/rule/formula version tuple、run id、plan digest、receipt hash；
  - current-rule replay fact：以 `(cohort_id, signal_date, stock_code, signal_kind)` 为逻辑键，保存候选身份及 PIT execution outcome；
  - date certificate：以 `(cohort_id, trade_date)` 为逻辑键，保存第 6.3 节的唯一日期状态和原因；
- receipt 可以是 task 生成的不可变 JSON artifact，但 manifest 必须保存 receipt 路径与 SHA-256；
- service 只读取状态为 `certified` 的 active manifest，并按 exact `cohort_id + version tuple` 选数；不存在 active certified manifest 时返回 `insufficient/unsupported`，不得回退到混合历史；
- API 的 `cohort_mode/cohort_id/version tuple` 直接来自 active manifest，不由前端或 service 根据 run-id 前缀猜测；
- active cohort 切换必须是单独、可审计的 task 操作，不能靠“最新 run_id”自动晋升。

上述专用物化对象是 M1-B 的推荐最小方案。M1-A 必须先提交具体 DDL、迁移、回滚和 GitNexus 影响证据；未获得 schema 边界批准前，只能生成只读 gap ledger，不能进入 M1-B。

## 6. M1 指标与状态合同

### 6.1 执行收益唯一口径

current-rule ready 只接受：

- `metric_basis = net_next_open_adj`；
- `stock_candidate`；
- T+5 与 T+20 两个期限均成熟；
- entry/exit 日期不晚于 evaluation as-of；
- 当前 execution formula、matched-baseline formula 与规则版本一致；
- 费用、复权和开盘价口径通过相同 formula version 披露。

原始 `return_5d / return_20d`、adjusted-close proxy 或限制为 500 行的详情结果不得用于 ready。

### 6.2 Replay closure ready 硬门槛

`current_rule_certified` 只有同时满足以下条件才能返回 `ready`：

1. `completed_dates >= 20`；
2. `matched_entry_count >= 100`，且 T+5/T+20 均达到 required horizon；
3. `blocking_pending_date_count == 0`；
4. `unsupported_date_count == 0`；
5. `proxy_only_date_count == 0`；
6. 最近尚未自然成熟的 T+20 tail 单独披露，不计入阻断；
7. execution 与 matched baseline 的 `stale_formula_row_count == 0`；
8. requested、resolved、observed、certified 和 evaluation 日期均可追溯；
9. 所有计数来自窗口级聚合，不受详情 API `limit` 影响。

第 7 项是 M1 拟新增的验收门槛；当前实现只披露 stale version 计数，尚未据此阻断 ready。该状态只回答“历史回放是否成熟”，不包含当日宏观、对抗门或候选门禁。未满足时只能输出 `partial / insufficient / blocked`，不得以总历史行数替代。

### 6.3 日期级 coverage certificate

每个交易日必须且只能落入一种主要状态：

| 状态 | 定义 | 是否计入 completed |
| --- | --- | --- |
| `completed_with_signals` | 完整运行且存在合格 current-rule 候选，所需结果已成熟 | 是 |
| `completed_no_strategy_signals` | 本 cohort 所需市场 universe、来源和策略模块运行证明完整，但没有合格候选 | 是 |
| `pending_tail` | 唯一原因是 evaluation date 下 T+20 尚未自然成熟 | 否；不阻断 |
| `blocking_pending` | 非自然尾部的 outcome、execution 或物化缺口 | 否；阻断 |
| `unsupported` | 必需来源表、全量策略运行或覆盖证明缺失 | 否；阻断 |
| `proxy_only` | 只有代理性主题/兼容证据，不能证明 current-rule 全覆盖 | 否；阻断 |

证书至少披露：trade date、状态、原因码、source/rule/formula/run 版本、候选数、执行数、源表覆盖、生成时间和 receipt 引用。

### 6.4 状态维度不得压成单一枚举

页面和 API 必须保留四个相互独立的状态维度：

| 维度 | 合法状态示例 |
| --- | --- |
| transport | `idle / loading / success / error` |
| data availability | `fresh / stale / fallback / no_data / unsupported` |
| replay closure | `ready / partial / insufficient / blocked` |
| refresh workflow | `running / completed / partial / failed` |

例如“接口成功 + 数据 stale + replay partial”必须能够同时表达，不能被一个 `ready` 或 `error` 覆盖。

## 7. M1 宏观 authority 合同

### 7.1 PMI

- 唯一业务序列：`M0017126` 制造业 PMI；
- 原始展示：指数水平，示例 `49.2`，不得显示为收益率；
- 主来源：受控 NBS 发布物；vendor fallback 必须降级披露；
- 标准化分数沿用版本化公式 `clip((PMI - 47) / 6, 0, 1)`，但原始值与得分必须分开；
- business date、published-at、as-of、source version、freshness 和 fallback 必须可见。

### 7.2 M1 信用分项正式命名

现有值正式命名为：

- 字段语义：`credit_expansion_yoy_delta_proxy`；
- 中文：`社融存量同比月差代理`；
- 首选序列：`M5525763`；
- 公式：`current_month_yoy - prior_adjacent_month_yoy`；
- 单位：百分点（`ppt`）；
- 标准化得分：将 `[-2,+2] ppt` 线性截断映射到 `[0,1]`；
- 目标合同中，`M0001385` 的广义货币 M2 同比月差只允许作为 `degraded_display_proxy`，不得满足 ready-grade authority；
- 页面、DTO 和证据文本不得只显示“信用脉冲”。

当前代码仍把 `M0001385` 当作可接受的 credit fallback。上述降级属于待 D2 批准的行为变更，不是对现状的描述。

### 7.3 M1 宏观 ready-grade 条件

本节是待 D2 批准的目标合同，会收紧当前允许 `M0001385` 作为 authority 候选的行为。D2 未批准前，任何 M1 实现不得改变现行 authority ready 语义。

- PMI 与 `M5525763` 信用代理均存在、相邻、fresh、无未来日期；
- `gate_as_of_date >= business_date`；
- `quality_flag=ok`、`vendor_status=ok`、`fallback_mode=none`；
- price-spread 可作为第三分项，但不能在 PMI 或信用代理缺失时单独把 authority 变为 ready；
- 现有分析合成权重继续版本化披露：`0.40*PMI_score + 0.35*CreditProxy_score + 0.25*PriceSpread_score`；
- 任一必需分项缺失、过期、fallback 或 PIT 不合法，authority 必须 fail closed。

### 7.4 最终首屏门禁组合

`replay_closure_ready` 与 `macro_authority_ready` 是独立状态。最终首屏门禁才组合：

- workbench candidate/review gate；
- replay closure；
- macro authority；
- adversarial gate；
- confluence freshness/as-of alignment。

因此可能合法出现“replay ready，但当日宏观 stale”或“宏观 ready，但 replay insufficient”。页面必须分别显示，不能反向改写 replay certificate。

## 8. M2 正式信用脉冲决策门

现有代理不是标准信用脉冲。IMF/World Bank 的研究语义把 credit impulse 指向“信用流量的变化/信用增长的加速度”，而不是信用存量同比的一次月差。参考：

- [IMF：Credit Growth and Economic Recovery in Europe](https://www.elibrary.imf.org/view/journals/001/2017/256/article-A001-en.xml)
- [World Bank：Anatomy of Credit-Less Recoveries](https://openknowledge.worldbank.org/bitstreams/664cfbb3-54d7-533a-81da-b9a8cfc6ba6e/download)

M2 开发前必须由 owner 冻结：

1. credit universe：社融增量、私人非金融部门信用，或其他明确范围；
2. 分母：最近已发布季度名义 GDP、滚动四季度名义 GDP，或其他口径；
3. 月度映射：季度 GDP 如何在发布日期后映射到月度，不允许回看修订值；
4. 变化窗口：1M 还是 3M；
5. 单位与精度；
6. revision/vintage 政策；
7. 缺失时是否允许 M1 proxy 并存，以及 proxy 能否进入 gate。

研究候选公式可评估为：

`credit_flow_ratio_t = rolling_12m_TSF_increment_t / latest_available_trailing_4q_nominal_GDP_t * 100`

`credit_impulse_t = credit_flow_ratio_t - credit_flow_ratio_(t-k)`，其中 `k ∈ {1M, 3M}`。

该公式只是评审候选，不是本 PRD 已批准的正式定义。M2 未签字前不得删除 proxy 标识或进入正式指标字典。

## 9. 数据生产与刷新工作流

### 9.1 只读预演

任何写入前必须先产生 gap ledger，至少包括：

- 连续交易日范围；
- 每日必需源表和策略模块覆盖；
- current/as-produced 版本分布；
- 零信号日证明；
- outcome maturity；
- execution 与 matched-baseline 缺口；
- 可合法认证的 current-rule 样本容量；
- 预计写入/更新行数和阻断原因。

### 9.2 受控写入

若预演通过，写路径必须：

- 只通过既有 task 层；
- 支持 dry-run、`run_id`、idempotency key、plan digest 和状态查询；
- 写前备份目标 DuckDB，并记录路径/哈希；
- 按月或更小批次执行，单批失败不得污染已认证窗口；
- 校验 source hash、rule/formula version、行数、日期和重复键；
- 生成不可变 receipt，包含 planned/applied/skipped/failed 计数；
- 对历史 as-of 使用当时可得的 observation，严禁未来数据泄漏；
- 不覆盖 `as_produced` 历史，current-rule replay 使用独立 cohort/run identity；
- 支持按 run/manifest 切回前一认证版本；不依赖破坏性删除恢复。

### 9.3 闭环刷新顺序

目标工作流按依赖顺序执行：

1. Choice 股票日数据与策略所需 PIT 源覆盖检查；
2. current-rule 候选重放与零信号日证明；
3. candidate outcome maturity；
4. execution gap/stale formula repair；
5. matched-baseline repair；
6. coverage certificate 与 replay summary；
7. signal-confluence 最终验证；
8. workbench/page cache 失效和刷新终态发布。

读接口不得触发上述写操作。

## 10. API 与页面可见合同

### 10.1 后端必须披露

confluence 或 workbench 的 closure 模块至少包含：

- `cohort_mode`；
- requested/observed/certified/evaluation 日期范围；
- `metric_basis`；
- rule/formula/source/run 版本；
- completed、no-signal、pending-tail、blocking-pending、unsupported、proxy-only 日期数；
- T+5/T+20 usable count；
- matched entry count 与 20/100 阈值；
- stale formula count；
- macro authority 及 PMI/信用代理原始字段；
- primary blocker 和可追溯 reason codes；
- refresh receipt/run id。

旧 mock/cache 客户端可以通过 optional 字段兼容，但真实响应缺少认证字段时必须 fail closed。

### 10.2 页面必须可见

首屏或紧邻首屏必须展示：

- 当前结论及 primary blocker；
- PMI 原始值、日期、source/freshness；
- `社融存量同比月差代理`原始值、单位、当前/上月参考日和 proxy 标签；
- current-rule replay 状态、认证范围、20/100 进度；
- stale/fallback/unsupported/partial；
- 当前 10 个 module states；
- 刷新 `completed / partial / failed` 及 run id。

深研区复用同一 gate、日期和 confluence payload，不重新判级。

## 11. 验收标准

### 11.1 合同与单元测试

- PMI、信用代理原始值/得分、单位、相邻月、missing、future、stale、fallback 测试；
- 广义货币 M2 fallback 不能满足 M1 ready-grade 的测试；
- `as_produced` 与 `current_rule_certified` 不混样；
- stale formula 行不能进入 ready；
- 零信号日只有在 full coverage 时才计 completed；
- 13 个 blocking pending 与 2 个 natural tail 的分类边界有回归用例；
- 100 条、99 条、20/19 completed 的精确阈值测试；
- historical evaluation 不读取未来 entry/exit/return。

### 11.2 数据验收

- gap ledger 与 receipt 可重跑且结果幂等；
- certified window 内 unsupported=0、proxy-only=0、blocking-pending=0；
- 任何 duplicate、hash mismatch、version mismatch 均 fail closed；
- 原 `as_produced` 行不被覆盖；
- 若 current-rule 合法样本不足 100，明确返回 insufficient，不降低门槛。

### 11.3 API/页面/刷新验收

- 后端、首屏、深研区对同一 as-of、cohort、状态和计数一致；
- `null`、0、missing、stale、fallback、no-data 和 error 可区分；
- confluence loading/error/as-of mismatch 时首屏 fail closed；
- 刷新 partial 为 warning 并失效页面缓存；failed 为 negative 且不宣称闭环；
- 真实 `/stock-analysis` 浏览器 smoke 无控制台错误、无横向溢出；
- 页面继续只使用“观察/复核/证据/失效条件”措辞；
- 新增 workbench/confluence closure capture-ready 样本时，必须明确 observational only，不创建 `MTR-STOCK-*`。

### 11.4 性能验收

- backfill/认证在离线 task 中运行，不阻塞页面请求；
- 窗口聚合不得按日期重复打开 DuckDB；
- signal-confluence 暖缓存不得比本轮基线退化超过 20%；
- 冷路径与 backfill 分别记录基准，不以延长 HTTP timeout 掩盖 N+1。

## 12. 分阶段交付

### M1-A：合同和 gap ledger

- 冻结双轨 cohort、ready 门槛和 coverage certificate；
- 只读输出 current-rule 可认证容量及版本分布；
- 提交第 5.4 节专用物化对象的具体 DDL、迁移、回滚和影响评估，等待单独批准；
- 不写数据库。

### M1-B：历史证据修复

- 备份、dry-run、分批 current-rule 重放；
- current-rule 数据只写入获批的专用 cohort 物化对象，不覆盖现有 `as_produced` 逻辑键；
- outcome、execution、matched baseline 和 certificate 收口；
- 保留 as-produced 历史。

### M1-C：API、页面和刷新验收

- 后端 closure 模块；
- 页面只展示、不重算；
- 日刷新终态、receipt、浏览器和黄金样本验收。

### M2：正式信用脉冲

- owner 签字后单独建立 metric contract；
- 物化官方 PIT 信用流量和名义 GDP vintage；
- core-finance 唯一计算；
- proxy/formal shadow 对照与迁移；
- 独立 golden sample、指标字典和页面合同评审。

即使 M2 指标被批准，`/stock-analysis` 仍保持 `observational_only / formal_use_allowed=false`；页面正式用途升级不属于本 PRD。

## 13. 发布、回滚与停止条件

### 发布前置

- PRD 状态改为“已批准实施”；
- M1 proxy 命名、双轨 cohort 和 ready 门槛获得确认；
- gap ledger 证明存在可合法重放的连续时期；
- 数据写入计划、备份和 rollback receipt 获得授权；
- 第 5.4 节的专用物化对象及 schema 迁移获得受保护边界批准；
- excluded Livermore surface 的测试与执行范围有明确 scoped authorization。

### 回滚

- 切回上一 rule/cache/certificate manifest；
- 停用当前 run receipt；
- 保留新增历史证据用于审计但不让其进入 active certified cohort；
- 必要时从写前备份恢复，不做无目标的批量删除。

### 停止条件

遇到以下任一情况立即停止数据写入并维持 fail closed：

- PIT 源快照不存在或无法证明发布时间；
- current-rule 无法在历史日期可重复执行；
- rule/formula/source version 无法对齐；
- 只能通过跳过零信号日或降低门槛达到 ready；
- M2 正式公式仍未签字却要求去掉 proxy 标签；
- schema、全局调度或权限框架成为必要改动但未获单独批准。

## 14. 待 owner 决策

| ID | 决策 | 推荐 |
| --- | --- | --- |
| D1 | 是否接受 M1 将当前值正式更名为“社融存量同比月差代理” | 接受 |
| D2 | `M0001385` 广义货币 M2 同比 fallback 能否满足 ready-grade | 否，仅 degraded display；未批准前不改现行行为 |
| D3 | current-rule ready 是否禁止混入旧版本 as-produced 行 | 是，必须禁止 |
| D4 | 20 completed / 100 matched 门槛是否保持 | 是，不降低 |
| D5 | 治理时期是否按连续源覆盖确定，而非按结果/样本数挑选 | 是 |
| D6a | 是否批准第 5.4 节的专用 current-rule cohort 物化对象及 schema 迁移 | 待 M1-A DDL/影响评估后单独确认 |
| D6b | 是否授权 M1-B 对目标 DuckDB 做备份后的 task-layer 分批写入 | 待 dry-run 后单独确认 |
| D7 | M2 正式 credit impulse 采用何种 credit universe、GDP 分母和 1M/3M 变化窗口 | M2 owner 评审决定 |

## 15. 参考权威

- `AGENTS.md`
- `docs/DOCUMENT_AUTHORITY.md`
- `docs/stock_analysis_workbench_api_contract.md`
- `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`
- `docs/audits/2026-07-18-stock-analysis-final-acceptance-matrix.md`
- `docs/pnl/stock-analysis-sign-off-packet.md`
- `docs/pnl/stock-analysis-owner-evidence-packet.md`
- `backend/app/services/livermore_signal_confluence_service.py`
- `backend/app/services/livermore_candidate_history_service.py`
- `backend/app/services/livermore_candidate_history_window_stats.py`
- `backend/app/core_finance/cycle_macro_score.py`
- `backend/app/tasks/livermore_candidate_history_materialize.py`
- `backend/app/tasks/livermore_candidate_outcome_maturity.py`
