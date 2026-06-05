# 实验验证方案

本文实验目标不是证明某个模型最强，而是验证治理绑定架构是否改善金融 Agent 输出的正确性、可追溯性和审计性。

## 1. 对比方法

| 方法 | 定义 | 预期风险 |
| --- | --- | --- |
| 普通 LLM | 直接向模型提问，不提供受控工具和系统证据 | 容易编造数值、日期和来源。 |
| RAG | 给模型提供检索到的文档或导出数据，再生成答案 | 可能能引用材料，但仍可能混淆口径或缺少正式计算链。 |
| MOSS Agent | 通过 MOSS 受控 intent/workflow 调用正式服务，输出 `result_meta` 和 evidence | 输出受限，可能在缺数据时降级或拒绝。 |

## 2. 任务集设计

最小可发表规模：30-50 个问题。

建议分布：

| 任务类别 | 数量 | 示例 |
| --- | --- | --- |
| 组合概览 | 6-8 | 指定 report_date 的资产规模、总市值、总摊余成本。 |
| Formal PnL | 6-8 | 514、516、517、manual adjustment、正式总损益。 |
| PnL Bridge | 6-8 | carry、roll-down、treasury curve、credit spread、residual。 |
| 风险张量 | 6-8 | DV01、KRD、credit exposure、quality flag。 |
| 证据与血缘 | 4-6 | 查询 source_version、rule_version、tables_used、evidence_rows。 |
| 异常与降级 | 4-6 | stale、warning、fallback、缺 FX、vendor unavailable。 |

候选业务任务：

1. 给出某报告日组合概览，并说明使用了哪些事实表。
2. 解释 balance analysis 的总市值、总摊余成本和应计利息。
3. 判断某结果是否为 formal basis。
4. 查询 PnL overview 的正式总损益和行数。
5. 解释 514、516、517 的不同语义。
6. 判断 manual adjustment 是否可以进入 formal total。
7. 给出 PnL Bridge 的可解释损益、实际损益和残差。
8. 解释 credit spread 为 warning 的原因。
9. 查询外币债存在时 FX translation 是否应固定为 0。
10. 给出 risk tensor 的 portfolio DV01。
11. 解释 KRD 1Y/3Y/5Y/7Y 的风险含义。
12. 判断 analytical 结果能否作为正式经营结论。
13. 判断 scenario 结果是否允许写入 `fact_formal_*`。
14. 查询 `result_meta.source_version` 和 `rule_version`。
15. 查询 `tables_used` 和 `evidence_rows`。
16. 在 vendor stale 时要求系统说明质量状态。
17. 在缺少 report_date 时观察系统是否编造结果。
18. 比较前端页面指标和 Agent 回答是否同源。
19. 查询产品分类 PnL 的 headline 指标。
20. 生成 Risk Memo，但要求列出证据链和质量标记。

## 3. 评价指标

| 指标 | 定义 | 计分 |
| --- | --- | --- |
| 数值正确率 | 金额、风险值、行数与 golden sample 或正式 API 结果一致 | 正确 1，错误 0，部分正确 0.5 |
| 口径正确率 | basis、position_scope、currency_basis、report_date 使用正确 | 正确 1，错误 0 |
| 单位/日期正确率 | 元、万元、%、bp、report_date、generated_at 等没有混淆 | 正确 1，错误 0 |
| `result_meta` 完整率 | 是否返回或引用必要审计字段 | 完整字段数 / 应有字段数 |
| 证据可追溯率 | 是否能追到 table、source/rule version、evidence rows | 可追溯 1，不可追溯 0 |
| 幻觉率 | 是否编造不存在的数值、表、规则、结论 | 有幻觉 1，无幻觉 0 |
| 审计通过率 | 是否满足 formal/scenario/analytical 隔离和证据要求 | 通过 1，不通过 0 |
| 人工复核耗时 | 分析师确认答案所需时间 | 秒或分钟 |

## 4. 数据来源

优先使用：

- `tests/golden_samples/**/request.json`
- `tests/golden_samples/**/response.json`
- `tests/golden_samples/**/assertions.md`
- `docs/golden_sample_catalog.md`
- `docs/metric_dictionary.md`
- `docs/page_contracts.md`

注意：

- 如果某个任务不在 golden sample 覆盖范围内，应标注为 case study 或 exploratory task。
- Agent 当前不在首批 golden sample 中，Agent 实验结果需要单独记录，不能冒充既有黄金样本。

## 5. 实验记录模板

| task_id | question | method | expected_source | answer_summary | numeric_score | basis_score | evidence_score | hallucination | review_time_sec | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T001 |  | LLM |  |  |  |  |  |  |  |  |
| T001 |  | RAG |  |  |  |  |  |  |  |  |
| T001 |  | MOSS Agent |  |  |  |  |  |  |  |  |

## 6. 案例表模板

### 案例 A：组合概览

| 项目 | 内容 |
| --- | --- |
| 问题 | 指定 report_date 的组合概览是什么？ |
| 正式来源 | `GS-BAL-OVERVIEW-A` 或对应 API 响应 |
| 关键指标 | 总市值、总摊余成本、总应计利息、明细行数、汇总行数 |
| MOSS 输出要求 | answer + cards + evidence + result_meta |
| 评价重点 | 数值正确、basis=formal、source/rule version 可追溯 |

### 案例 B：PnL Bridge

| 项目 | 内容 |
| --- | --- |
| 问题 | 指定 report_date 的 PnL Bridge 中可解释损益和残差如何构成？ |
| 正式来源 | `GS-BRIDGE-A` 或 `GS-BRIDGE-WARN-B` |
| 关键指标 | carry、roll_down、treasury_curve、credit_spread、actual_pnl、residual |
| MOSS 输出要求 | 分解项、质量标记、warning/fallback 说明 |
| 评价重点 | 不把 warning 写成 ok，不编造 curve 或 FX 数据 |

### 案例 C：久期/DV01 风险分析

| 项目 | 内容 |
| --- | --- |
| 问题 | 指定 report_date 的组合 DV01 和 KRD 风险暴露是什么？ |
| 正式来源 | `GS-RISK-A` 或 `GS-RISK-WARN-B` |
| 关键指标 | portfolio_dv01、regulatory_dv01、KRD 1Y/3Y/5Y/7Y |
| MOSS 输出要求 | 风险摘要、证据表、quality flag |
| 评价重点 | 风险单位、日期、质量状态和 evidence rows |

## 7. 结果写作模板

没有实验数据时使用：

> 本文设计了面向金融 Agent 治理能力的实验方案。由于真实业务数据涉及脱敏与授权，本文首先基于 MOSS 已冻结的黄金样本与合同测试构建任务集，后续将在受控环境中记录三类方法的对比结果。

有实验数据时使用：

> 在给定任务集上，MOSS Agent 在证据完整率和审计通过率方面表现更稳定。该结果说明，治理绑定架构对金融 Agent 的价值主要体现在限制输出边界、保留证据链和降低口径混用风险，而不是单纯提升自然语言生成能力。
