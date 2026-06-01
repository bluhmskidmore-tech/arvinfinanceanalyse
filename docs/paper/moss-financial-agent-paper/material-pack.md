# 论文材料包

本材料包把 MOSS 当前可用于论文写作的证据压缩成“主张 - 项目证据 - 写作边界”的形式。写正文时优先引用这里的主张，避免把项目文档改写成失真的论文叙述。

## 1. 系统定位

可写主张：

- MOSS 的系统本体不是单一前端页面或普通 BI 看板，而是“Agent 可调用的分析操作系统”。
- 系统面向固定收益、经营分析、风险与损益穿透等内部金融分析场景。
- Agent 的职责是分析、解释和调用受控工具，不是绕过正式金融计算层直接生成正式结论。

项目证据：

- `prd-moss-agent-analytics-os.md`：系统定义为 `Agent 可调用的分析操作系统`。
- `README.md`：仓库定位为以固定收益分析、经营分析和治理追踪为核心的业务系统。
- `docs/AGENT_MVP_RUNBOOK.md`：Agent 通过 `AgentEnvelope` 返回 answer、cards、evidence、result_meta、next_drill、suggested_actions。

写作边界：

- 不能写成对外客户版、移动端、多租户平台。
- 不能写成纯大模型推理系统；当前核心是金融分析服务和治理绑定。

## 2. 系统架构

可写主张：

- MOSS 采用“模块化单体 + 分层分析栈”，避免早期微服务化带来的口径分裂。
- 固定调用方向为 `frontend -> api -> services -> (repositories / core_finance / governance) -> storage`。
- 正式金融计算集中在 `backend/app/core_finance/`，前端不补算正式金融指标。
- 存储职责分离：PostgreSQL 做治理账本，DuckDB 做分析事实与宽表，Redis 做缓存和锁，MinIO/S3 做文件和快照归档。

项目证据：

- `prd-moss-agent-analytics-os.md`：顶层架构决策、技术栈冻结、存储与队列职责。
- `README.md`：系统形态和关键约束。
- `docs/architecture.md`：目录树、分层边界和排除面说明。

写作边界：

- 不把架构写成技术堆栈清单，要解释为什么这样设计能降低金融指标漂移和审计风险。
- 不声称已经完成所有未来扩展，如 ClickHouse 迁移、完整报表生成或外部 MCP 数据接入。

## 3. Agent 工作流

可写主张：

- MOSS Agent 采用受控 intent 和 workflow，而不是开放式任意数据库访问。
- 已定义的金融工作流包括 portfolio review、pnl review、risk memo、market brief。
- Workflow 输出仍保留 `result_meta`、evidence 和 audit 边界，workflow 本身不等于正式金融结果。

项目证据：

- `docs/agent_financial_workflows.md`：workflow ID、slash command、映射的 MOSS intents。
- `docs/AGENT_MVP_RUNBOOK.md`：Agent endpoint、intent 列表、只读边界和响应结构。

写作边界：

- `agent_financial_workflows.md` 明确当前不包含 Claude API、Anthropic Managed Agents、外部金融数据连接器或报告生成。
- Workflow catalog response 是执行计划或执行摘要，不应被写成正式财务报表。

## 4. result_meta 审计契约

可写主张：

- MOSS 将金融分析输出包装为带审计元数据的 governed result。
- `result_meta` 至少覆盖 trace、basis、result kind、scenario flag、source/rule/vendor/cache version、quality flag、tables used、filters、SQL trace、evidence rows 和 next drill。
- 该契约使 Agent、前端和管理报表共享同一可复核事实链。

项目证据：

- `prd-moss-agent-analytics-os.md` 的 `result_meta 契约`。
- `docs/AGENT_MVP_RUNBOOK.md` 的 `AgentEnvelope` 响应示例。
- `docs/acceptance_tests.md` 中多处要求 outward response 必带 `result_meta`。
- `tests/test_formal_compute_result_meta_contract.py`、`tests/test_result_meta_required.py`、`tests/test_result_meta_on_all_ui_endpoints.py` 等测试锚点。

写作边界：

- 不要把 `result_meta` 写成监管认证结论；它是系统内审计和复核契约。
- 不要把 provenance 元字段混入业务指标字典，`docs/metric_dictionary.md` 已明确区分。

## 5. Formal / Scenario / Analytical 隔离

可写主张：

- MOSS 把正式结果、情景推演和探索分析分离，防止 Agent 把模拟结论冒充正式经营结果。
- `basis=formal`、`basis=scenario`、`basis=analytical` 对应不同的 `formal_use_allowed` 和 `scenario_flag` 组合。
- 不同 basis 不应共用 formal fact、cache key 或表命名空间。

项目证据：

- `docs/acceptance_tests.md` 的 `Formal / Scenario / Analytical 隔离`。
- `docs/CACHE_SPEC.md`：basis、formal_use_allowed、scenario_flag 与 cache identity。
- `tests/test_cache_basis_isolation.py` 是当前可引用的缓存隔离测试锚点。
- `docs/acceptance_tests.md` 中还包含 `test_result_meta_basis_contract.py`、`test_pnl_basis_isolation_flow.py` 等建议新增测试设计；论文中只能写作“验证设计依据”，不能写作已落地测试。

写作边界：

- 不能把 analytical 结果写成可用于正式披露的结果。
- 不能把 scenario 结果写回 `fact_formal_*` 命名空间。

## 6. 指标字典、页面契约与黄金样本

可写主张：

- MOSS 用指标字典、页面契约、黄金样本测试连接“指标定义 - 后端计算 - API 输出 - 前端展示 - 审计复核”。
- 首批黄金样本覆盖 balance analysis、formal PnL、PnL bridge、risk tensor、executive consumer 等主链。
- 黄金样本可作为论文实验中的“标准答案”和回归验证依据。

项目证据：

- `docs/metric_dictionary.md`：指标 ID、basis、权威来源、消费面、测试锚点。
- `docs/page_contracts.md`：页面级 contract。
- `docs/golden_sample_catalog.md`：13 个首批 golden sample 目录、状态、surface 和断言。
- `tests/golden_samples/**`：request、response、assertions、approval。

写作边界：

- `docs/golden_sample_catalog.md` 明确 Agent 不纳入首批黄金样本，论文中不能说 Agent 已有 golden sample 全覆盖。
- 对 product-category PnL，只能按已冻结的 truth contract、page contract 和样本断言写，不能声称字段级指标字典已全覆盖。

## 7. 外部文献坐标

这些不是项目能力证据，而是论文“相关研究”和“问题背景”的引用坐标。正式投稿前需要按目标期刊格式补全参考文献。

| 方向 | 可引用来源 | 用途 |
| --- | --- | --- |
| AI 风险管理 | NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework | 支撑“可信 AI、治理、风险管理”背景。 |
| 金融 AI 系统性风险 | FSB, The Financial Stability Implications of Artificial Intelligence: https://www.fsb.org/2024/11/fsb-assesses-the-financial-stability-implications-of-artificial-intelligence/ | 支撑金融 AI 的 model risk、data quality、governance 风险。 |
| 金融机构 AI/ML 治理 | IOSCO Final Report: https://www.iosco.org/library/pubdocs/pdf/IOSCOPD684.pdf | 支撑金融中介和资管机构使用 AI/ML 时的治理、控制、监督要求。 |
| 金融 Agent 评测 | Finance Agent Benchmark: https://arxiv.org/abs/2508.00828 | 支撑“金融 Agent 需要真实任务评测”的研究现状。 |
| 中文金融 Agent 评测 | FinGAIA: https://arxiv.org/abs/2507.17186 | 支撑中文金融场景和多层级金融任务评测。 |
| 金融 MCP 工具调用 | FinMCP-Bench: https://arxiv.org/abs/2603.24943 | 支撑金融 Agent 工具调用与 MCP 评测方向。 |

## 8. 论文可用核心句

可直接扩写：

> 与仅依赖大模型生成答案的金融问答系统不同，MOSS 将 Agent 置于受治理的金融分析操作系统之上。Agent 不直接生成正式金融指标，而是通过受控 intent、正式分析服务和只读证据查询工具获取结果，并在输出中强制携带数据来源、规则版本、质量标记和证据行数。

可直接扩写：

> 本文的核心贡献不在于提出新的大模型算法，而在于提出并实现一种面向金融高风险场景的治理绑定架构，使 Agent 的自然语言分析能够与正式计算、指标契约、血缘证据和人工复核流程形成闭环。
