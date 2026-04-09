# CODEX_KICKOFF_PROMPT.md

你在一个银行固定收益分析系统仓库中工作。

开始之前，必须完整阅读：
1. AGENTS.md
2. docs/CODEX_HANDOFF.md
3. docs/IMPLEMENTATION_PLAN.md
4. docs/architecture.md
5. docs/calc_rules.md
6. docs/data_contracts.md
7. docs/CACHE_SPEC.md
8. docs/acceptance_tests.md

必须遵守：
- 所有正式金融公式只能实现于 `backend/app/core_finance/`
- `backend/app/api/` 只允许做参数校验、调用 service、响应组装
- `frontend/` 不允许补算正式金融指标
- Scenario 结果不得污染 Formal
- DuckDB 常态只读；分析库写入必须走 `tasks/worker`
- 所有正式结果必须返回 `result_meta`
- 不允许删功能，只允许纠错、补齐、重构
- 任何金融口径改动都必须补测试和文档

技术栈冻结如下：
- 前端：React、TypeScript、Vite、TanStack Query、Ant Design、AG Grid、ECharts
- 后端：Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy 2.x
- 存储：PostgreSQL、DuckDB、Redis、MinIO/S3
- 异步：Dramatiq

阶段要求：
- Phase 1：骨架、连接、schema、demo 数据、smoke tests
- Phase 2：H/A/T、日均金额、FX 中间价折算、Formal PnL、516
- Phase 3：cube query、PnL bridge、risk tensor、formal-analytical bridge
- Phase 4：Claude 风格前端工作台
- Phase 5：治理、审计、缓存、任务编排

当前只执行 **Phase 1**。

Phase 1 完成标准：
- 目录完整
- FastAPI 可启动
- DuckDB / PostgreSQL 连接可用
- 有 demo 数据
- 有 smoke tests
- 输出：变更清单、测试结果、未完成项、风险说明

完成后停止，不继续下一阶段，等待人工确认。
