# 论文蓝图

## 1. 推荐题目

首选：

> 可治理金融 Agent 分析系统设计与验证：基于固定收益业务的证据链、指标契约与正式计算隔离框架

备选：

1. 面向固定收益分析的可审计金融 Agent 操作系统设计与应用
2. 金融 Agent 的治理绑定架构研究：基于 MOSS 系统的设计与验证
3. 面向金融分析的可信 Agent 系统：正式计算、证据链与指标口径治理

## 2. 摘要草案

随着大模型和 Agent 技术进入金融分析场景，金融机构面临的核心问题不再只是模型是否能够生成自然语言答案，而是答案能否与正式金融计算、指标口径、数据血缘和审计证据保持一致。针对金融 Agent 在幻觉、口径漂移、不可复核和不可审计方面的风险，本文提出一种可治理金融 Agent 分析系统 MOSS。该系统以固定收益和经营分析为主要场景，采用模块化单体与分层分析栈架构，将正式金融计算集中于受控计算层，并通过 `result_meta` 审计元数据契约、evidence 证据链、Formal/Scenario/Analytical 结果隔离和只读 Agent 工具边界，实现前端、管理报表与 Agent 的同源事实层访问。本文进一步设计基于黄金样本和业务任务集的验证方案，从指标正确率、口径一致性、证据完整率、审计通过率和幻觉率等维度评估系统有效性。该研究路线旨在说明，可治理绑定架构能够为金融 Agent 从问答辅助走向可复核业务分析提供一种可落地路径。

关键词：

金融科技；金融 Agent；固定收益分析；数据治理；指标血缘；可审计人工智能

## 3. 研究问题

- RQ1：如何将金融 Agent 的自然语言分析绑定到正式金融计算和统一事实层，避免自由生成正式指标？
- RQ2：如何通过审计元数据和证据链提升金融 Agent 输出的可追溯性与可复核性？
- RQ3：Formal / Scenario / Analytical 结果隔离能否降低金融分析中的口径混用风险？
- RQ4：相较普通 LLM 或 RAG，治理绑定 Agent 在指标正确、证据完整和审计通过方面是否更优？

## 4. 创新点

1. 提出面向金融高风险场景的 governance-bound Agent 架构，使 Agent 通过受控服务调用正式金融计算层，而非直接生成正式指标。
2. 设计 `result_meta` 审计元数据契约，将 source version、rule version、quality flag、tables used 和 evidence rows 纳入统一输出结构。
3. 建立 Formal / Scenario / Analytical 隔离机制，防止模拟分析和探索性分析污染正式事实层。
4. 将指标字典、页面契约和黄金样本纳入验证体系，形成从指标定义到页面展示再到 Agent 解释的闭环。
5. 给出面向固定收益场景的应用验证设计，覆盖组合概览、PnL Bridge、久期/DV01、风险张量等业务任务。

## 5. 章节结构

| 章节 | 标题 | 核心内容 | 主要证据 |
| --- | --- | --- | --- |
| 1 | 引言 | 金融 AI 风险、研究问题、贡献 | NIST、FSB、IOSCO；MOSS 系统定位 |
| 2 | 相关研究 | 金融智能分析、金融 Agent、数据治理、AI 风险管理 | 外部文献坐标 |
| 3 | 系统架构设计 | 分层架构、正式计算边界、REST/MCP 双接口 | PRD、README、architecture |
| 4 | 可治理 Agent 机制 | result_meta、evidence、basis 隔离、只读边界 | Agent runbook、acceptance tests |
| 5 | 系统实现 | 固定收益、PnL、risk tensor、Agent Workbench、golden sample | metric dictionary、golden sample catalog |
| 6 | 实验验证与案例 | 三类方法对比、任务集、指标、案例 | 实验记录、golden samples |
| 7 | 结论与展望 | 贡献、限制、未来工作 | 全文归纳 |

## 6. 图表清单

建议图：

1. MOSS 总体架构图：用户层、Agent 层、API 层、服务层、正式计算层、治理层、存储层。
2. Agent 调用链路图：question -> intent/workflow -> analysis service -> result_meta/evidence -> answer。
3. Formal / Scenario / Analytical 隔离图：basis、formal_use_allowed、scenario_flag、fact/cache namespace。
4. 指标治理闭环图：metric dictionary -> page contract -> API response -> frontend -> golden sample。

建议表：

1. MOSS 与普通 LLM/RAG 的能力对比表。
2. `result_meta` 字段说明表。
3. 金融任务集样例表。
4. 实验评价指标表。
5. 三个业务案例结果表：组合概览、PnL Bridge、久期/DV01。

## 7. 需要控制的风险表述

| 风险表述 | 建议改法 |
| --- | --- |
| MOSS 能彻底解决金融 AI 幻觉 | MOSS 通过治理绑定机制降低幻觉和不可追溯风险。 |
| Agent 可以自动生成正式金融报告 | 当前 Agent 输出分析与解释，报告生成属于未来工作。 |
| 黄金样本覆盖所有 Agent 行为 | 黄金样本覆盖首批业务 surface，Agent 尚未纳入首批黄金样本。 |
| 系统已接入完整外部金融数据供应商 | 当前文档定义 Choice/AkShare 等适配边界，具体可用性需按实现证据写。 |
| 实验证明 MOSS 全面优于 LLM | 只能在给定任务集和指标下讨论结果。 |
