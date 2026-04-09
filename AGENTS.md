# AGENTS.md

## 项目本体

本系统不是单纯的债券看板，也不是只给管理层的报表系统。

系统本体定义为：

`Agent 可调用的分析操作系统`

前端驾驶舱、管理层报表、研究员分析页、Agent 工作台，都是同一分析操作系统的消费层。

## 文档优先级

如果文档冲突，严格按以下顺序执行：

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明`
4. `docs/CODEX_HANDOFF.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/calc_rules.md`
7. `docs/data_contracts.md`
8. `docs/CACHE_SPEC.md`
9. `docs/acceptance_tests.md`
10. `MOSS 系统：取值逻辑、计算层与规则总览`

说明：
- `prd-moss-agent-analytics-os.md` 是系统北极星。
- `docs/MOSS-V2 系统架构说明` 是目标实现架构。
- `MOSS 系统：取值逻辑、计算层与规则总览` 仅作旧系统逻辑与历史公式参考，不再作为目标实现边界。

## 架构铁律

必须遵守固定调用方向：

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

非谈判约束如下：

1. 所有正式金融计算只能实现于 `backend/app/core_finance/`。
2. `backend/app/api/` 只允许做参数校验、鉴权、调用 service、返回响应。
3. `frontend/` 不允许补算正式金融指标。
4. DuckDB 在 API 路径只读；写入只允许通过 `backend/app/tasks/` / worker。
5. `services/` 负责编排，不得散落正式金融公式。
6. `Scenario` 与 `Formal` 必须在语义、表、缓存和 `result_meta` 上隔离。
7. 所有正式结果必须带 `result_meta`。
8. 不得删功能，只允许补齐、纠错、重构。

## 技术栈冻结

前端：
- React
- TypeScript
- Vite
- TanStack Query
- Ant Design
- AG Grid
- ECharts
- Claude 风格 theme layer

后端：
- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x

存储与队列：
- PostgreSQL
- DuckDB
- Redis
- Dramatiq
- MinIO / S3

## 已确认业务规则

- H = AC（持有至到期 / 摊余成本）
- A = FVOCI / OCI（可供出售 / 其他债权投资）
- T = FVTPL / TPL（交易性）
- `CNX` = 综本；`CNY` = 人民币账；外币展示可按 `CNX - CNY`
- 债券资产月均默认剔除发行类债券
- USD 资产按当日 USD/CNY 官方中间价折算为 CNY
- 周末和节假日沿用前一营业日中间价
- 缺失营业日中间价时，formal 直接失败，不静默替代
- `locf` 仅允许分析口径使用，不进入 formal
- 516 正式口径只允许使用标准化后的有符号金额

## 高风险口径区

以下内容一旦修改，必须补测试、补文档、说明影响范围：

- H/A/T 映射
- 发行类债券剔除逻辑
- FX 中间价折算规则
- 514/516/517 归并逻辑
- 月均金额 `observed / locf / calendar_zero`
- Formal / Scenario 隔离
- PnL bridge / risk tensor / KRD / DV01 / CS01 / convexity

## Codex 工作方式

在动手改代码前，必须先阅读：

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明`
4. `docs/CODEX_HANDOFF.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/calc_rules.md`
7. `docs/data_contracts.md`
8. `docs/CACHE_SPEC.md`
9. `docs/acceptance_tests.md`

当前轮次只允许执行 `Phase 1`。

## 每轮输出格式

每一轮提交都必须输出：

- 变更文件列表
- 新增或修改的测试列表
- 测试结果
- 风险点
- 是否影响正式金融口径
- 未完成项
- 下一轮建议
