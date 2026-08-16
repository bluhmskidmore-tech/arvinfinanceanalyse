# CODEX_KICKOFF_PROMPT.md

你在实现一个银行固定收益领域的“Agent 可调用的分析操作系统”，不是单纯的看板系统。

开始之前，必须完整阅读并遵守以下文档，优先级从高到低（第 3、10 项是**空置槽位**，见列表下方说明）：

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明` — **该文档在当前 checkout 中不存在**，归宿待定
4. `docs/DOCUMENT_AUTHORITY.md`
5. `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
6. `docs/calc_rules.md`
7. `docs/data_contracts.md`
8. `docs/CACHE_SPEC.md`
9. `docs/acceptance_tests.md`
10. `MOSS 系统：取值逻辑、计算层与规则总览` — **该文档在当前 checkout 中不存在**，归宿待定

第 3 项与第 10 项从未并入本仓库，因此「必须完整阅读」对它们不成立：跳过即可，不要去找，也不要以它们
为依据裁决冲突。是否补齐还是正式作废属于 owner 决策；权威说明见
[DOCUMENT_AUTHORITY.md](DOCUMENT_AUTHORITY.md) 的「两个空置槽位（文件从未并入本仓库）」一节，
其中也列出了当前可用的替代文件。

背景 / reference 文档（按需，不作为当前 repo-level 入口）：
- `docs/CODEX_HANDOFF.md`
- `docs/IMPLEMENTATION_PLAN.md`

必须遵守：

- 系统本体是“Agent 可调用的分析操作系统”
- 总体形态是“模块化单体 + 分层分析栈”
- 固定调用方向：`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`
- 所有正式金融计算只能实现于 `backend/app/core_finance/`
- `backend/app/api/` 只允许做参数校验、**授权**、调用 service、返回响应
  - 原文此处写的是「鉴权」。准确说法是**授权**（authorization / RBAC）：仓库**有授权、没有认证**——
    `ensure_user_allowed` 的 RBAC 判定存在，但没有 `HTTPBearer` / `OAuth2` / `APIKeyHeader` / JWT /
    session，调用方身份未经校验。完整边界见 [../README.md](../README.md)「关键约束」一节与
    [SYSTEM_STACK_SPEC_FOR_CODEX.md](SYSTEM_STACK_SPEC_FOR_CODEX.md) 第 1 节；这里只描述 API 层允许做的
    动作类型，不构成安全声明。
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
