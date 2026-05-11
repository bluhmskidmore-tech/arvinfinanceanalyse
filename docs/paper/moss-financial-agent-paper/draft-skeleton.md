# 论文正文骨架

本文档是可直接交给 5.5PRO 扩写的正文骨架。每章结尾保留“证据来源说明”，用于提醒模型和作者不要脱离项目材料。

## 题目

可治理金融 Agent 分析系统设计与验证：基于固定收益业务的证据链、指标契约与正式计算隔离框架

## 摘要

随着大模型和 Agent 技术进入金融分析场景，金融机构面临的核心问题不再只是模型是否能够生成自然语言答案，而是答案能否与正式金融计算、指标口径、数据血缘和审计证据保持一致。针对金融 Agent 在幻觉、口径漂移、不可复核和不可审计方面的风险，本文提出一种可治理金融 Agent 分析系统 MOSS。该系统以固定收益和经营分析为主要场景，采用模块化单体与分层分析栈架构，将正式金融计算集中于受控计算层，并通过 `result_meta` 审计元数据契约、evidence 证据链、Formal/Scenario/Analytical 结果隔离和只读 Agent 工具边界，实现前端、管理报表与 Agent 的同源事实层访问。本文进一步设计基于黄金样本和业务任务集的验证方案，从指标正确率、口径一致性、证据完整率、审计通过率和幻觉率等维度评估系统有效性。

关键词：金融科技；金融 Agent；固定收益分析；数据治理；指标血缘；可审计人工智能

## 1 引言

### 1.1 研究背景

写作要点：

- 大模型和 Agent 正在进入金融分析、投研、风险管理和中后台经营分析。
- 金融场景对答案的要求不仅是“语义合理”，还包括数值正确、口径一致、来源可追溯、可审计。
- 普通 LLM 或简单 RAG 在金融业务中可能出现幻觉、日期口径混淆、单位错误、引用不可复核等风险。

### 1.2 问题定义

写作要点：

- 定义金融 Agent 的关键风险：自由生成正式指标、混淆 formal/scenario/analytical、缺少来源、缺少规则版本。
- 提出本文关注的问题：如何让 Agent 在金融分析中被正式计算和治理证据约束。

### 1.3 本文方法与贡献

写作要点：

- 提出 MOSS 作为 governance-bound financial Agent analytics system。
- 贡献包括架构、`result_meta`、basis 隔离、golden sample 验证体系。

证据来源说明：

- `prd-moss-agent-analytics-os.md`
- `README.md`
- NIST AI RMF、FSB、IOSCO 外部文献坐标

## 2 相关研究

### 2.1 金融智能分析系统

写作要点：

- 金融分析系统从报表和 BI 发展到交互式工作台。
- 传统系统强在结构化指标，弱在自然语言交互和跨模块解释。

### 2.2 LLM/Agent 在金融领域的应用

写作要点：

- 金融 Agent benchmark 正在关注真实金融研究、工具调用和中文金融场景。
- 现有研究更重视任务完成率，较少讨论正式金融计算边界和审计元数据绑定。

### 2.3 金融数据治理与指标血缘

写作要点：

- 金融指标需要统一口径、计算规则、数据来源和变更记录。
- MOSS 的指标字典、页面契约、黄金样本可被放入这个研究脉络。

### 2.4 AI 风险管理与可审计性

写作要点：

- NIST、FSB、IOSCO 均强调 AI 风险管理、治理、监督、数据质量和模型风险。
- 本文把这些原则落实为系统级机制。

证据来源说明：

- 外部文献坐标见 `material-pack.md`
- 项目证据见 `docs/metric_dictionary.md`、`docs/golden_sample_catalog.md`

## 3 MOSS 系统架构设计

### 3.1 系统定位

写作要点：

- MOSS 是 Agent 可调用的分析操作系统。
- 前端驾驶舱、管理层报表、研究员分析页是消费层，不是系统本体。

### 3.2 分层架构

写作要点：

- `frontend -> api -> services -> core_finance/governance -> storage`。
- `core_finance` 是正式金融计算唯一入口。
- 前端不补算正式金融指标。

### 3.3 数据与存储职责

写作要点：

- PostgreSQL：治理、任务、审计、配置。
- DuckDB：分析事实表、宽表、物化缓存。
- Redis：缓存、锁、队列。
- MinIO/S3：文件、归档、快照。

### 3.4 REST/MCP 双接口

写作要点：

- REST 服务前端和常规系统消费。
- MCP 作为 Agent 证据查询和工具调用接口。
- 两者都不能绕过正式计算和治理边界。

证据来源说明：

- `prd-moss-agent-analytics-os.md`
- `docs/MCP_RUNBOOK.md`
- `README.md`

## 4 可治理 Agent 关键机制

### 4.1 `result_meta` 审计元数据契约

写作要点：

- 说明字段：trace_id、basis、result_kind、formal_use_allowed、source_version、rule_version、quality_flag、tables_used、evidence_rows。
- 解释它如何服务复核、审计和错误定位。

### 4.2 evidence 与 lineage

写作要点：

- 说明 evidence tables、filters、SQL trace、evidence rows。
- 强调答案不是孤立文本，而是绑定证据链。

### 4.3 Formal / Scenario / Analytical 隔离

写作要点：

- 三类 basis 的语义。
- 不同 fact/cache namespace。
- 防止模拟分析污染正式结果。

### 4.4 只读 Agent 与受控 workflow

写作要点：

- Agent 不执行客户端 SQL，不触发写入，不刷新任务。
- workflow 是受控意图编排，不是外部 Agent runtime。

证据来源说明：

- `docs/AGENT_MVP_RUNBOOK.md`
- `docs/agent_financial_workflows.md`
- `docs/acceptance_tests.md`

## 5 系统实现

### 5.1 固定收益与 balance analysis

写作要点：

- 资产负债、投资类型、会计分类、币种口径、头寸范围。
- 强调计算在 `core_finance`，展示层不补算。

### 5.2 Formal PnL 与 PnL Bridge

写作要点：

- 514、516、517、manual adjustment 的 formal 语义。
- Bridge 的 carry、roll-down、curve、credit spread、FX translation、residual。

### 5.3 Risk Tensor 与久期/DV01

写作要点：

- portfolio DV01、regulatory DV01、KRD 等风险指标。
- quality flag 对风险结论的约束。

### 5.4 Agent Workbench

写作要点：

- intent routing。
- portfolio review、pnl review、risk memo、market brief。
- answer、cards、evidence、result_meta 同屏呈现。

### 5.5 指标字典、页面契约和黄金样本

写作要点：

- 指标 ID、权威来源、消费面、展示规则、测试锚点。
- 黄金样本用于冻结 request/response/assertions/approval。

证据来源说明：

- `docs/metric_dictionary.md`
- `docs/golden_sample_catalog.md`
- `tests/golden_samples/**`

## 6 实验验证与案例分析

### 6.1 实验设计

写作要点：

- 对比普通 LLM、RAG、MOSS Agent。
- 30-50 个金融分析问题。
- 指标：正确率、口径、单位/日期、证据、幻觉、审计通过、复核耗时。

### 6.2 案例一：组合概览

写作要点：

- 使用 `GS-BAL-OVERVIEW-A` 或对应正式 API。
- 展示总市值、总摊余成本、总应计利息和 result_meta。

### 6.3 案例二：PnL Bridge

写作要点：

- 使用 `GS-BRIDGE-A` 或 warning profile。
- 展示分解项和质量标记。

### 6.4 案例三：久期/DV01 风险分析

写作要点：

- 使用 `GS-RISK-A` 或 warning profile。
- 展示 DV01、KRD、quality flag 和 evidence rows。

### 6.5 结果讨论

写作要点：

- 如果实验数据尚未完成，只写实验方案和预期评价方式。
- 如果实验数据已完成，只基于记录结果讨论。

证据来源说明：

- `experiment-plan.md`
- `docs/golden_sample_catalog.md`
- 实验记录表

## 7 结论与展望

写作要点：

- 总结本文提出的 governance-bound Agent 架构。
- 强调价值在于正式计算绑定、证据链和审计能力，而非单纯生成能力。
- 局限性：样本规模、脱敏数据、外部模型依赖、Agent 尚未纳入首批 golden sample。
- 未来工作：更多金融 workflow、多模型评测、报告生成、监管审计接口。

证据来源说明：

- 全文证据汇总
