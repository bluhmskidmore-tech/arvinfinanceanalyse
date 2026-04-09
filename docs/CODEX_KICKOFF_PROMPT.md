# CODEX_KICKOFF_PROMPT.md

你在实现一个银行固定收益领域的“Agent 可调用的分析操作系统”，不是单纯的看板系统。

开始之前，必须完整阅读并遵守以下文档，优先级从高到低：

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明`
4. `docs/DOCUMENT_AUTHORITY.md`
5. `docs/CODEX_HANDOFF.md`
6. `docs/IMPLEMENTATION_PLAN.md`
7. `docs/calc_rules.md`
8. `docs/data_contracts.md`
9. `docs/CACHE_SPEC.md`
10. `docs/acceptance_tests.md`
11. `MOSS 系统：取值逻辑、计算层与规则总览`

必须遵守：

- 系统本体是“Agent 可调用的分析操作系统”
- 总体形态是“模块化单体 + 分层分析栈”
- 固定调用方向：`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`
- 所有正式金融计算只能实现于 `backend/app/core_finance/`
- `backend/app/api/` 只允许做参数校验、鉴权、调用 service、返回响应
- `frontend/` 不允许补算正式金融指标
- `Scenario` 与 `Formal` 必须隔离
- DuckDB API 常态只读；写入只能走 `backend/app/tasks/`
- 前端、报表、Agent 必须共用同一分析服务层
- 所有正式结果必须返回 `result_meta`
- Choice 是生产级外部参考主源，AkShare 是补充源
- 不得删功能，只允许补齐、纠错、重构

关于文档冲突的处理：
- `PRD / V2` 优先于 `V1`
- `V1` 仅作旧系统逻辑与历史公式参考
- 新代码必须以 `core_finance/` 作为正式计算唯一入口

技术栈冻结如下：

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

存储与异步：
- PostgreSQL
- DuckDB
- Redis
- Dramatiq
- MinIO / S3

当前只执行 `Phase 1`：

- repo 骨架
- FastAPI 可启动
- React 前端可启动
- PostgreSQL / DuckDB / Redis / MinIO 连接
- demo 数据导入
- 基础 `result_meta` 契约
- 基础 `tasks/worker` 框架
- smoke tests

Phase 1 完成标准：

- 目录完整
- FastAPI 可启动
- `/health` 返回 200
- 前端可启动
- DuckDB / PostgreSQL / Redis / MinIO 连接可用
- 有 demo 数据
- 有 smoke tests

完成后不要进入下一阶段。

只输出：
- 变更文件清单
- 新增或修改的测试列表
- 测试结果
- 风险说明
- 未完成项
- 下一轮建议
