# Architecture

## 1. 文档定位

本文档用于固化 MOSS Agent Analytics OS 当前阶段的总体架构与一期技术栈选型。

如与更高优先级文档冲突，以以下文档为准：

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. 其余受控设计与交接文档

本文档不放宽现有阶段边界，仅将当前已确认的架构约束与技术选型整理为便于评审和执行的正式表述。

## 2. 系统总体形态

系统采用“模块化单体 + 分层分析栈”架构，不在一期提前拆分微服务。

固定调用方向如下：

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

必须遵守以下非谈判约束：

- 所有正式金融计算只能实现于 `backend/app/core_finance/`
- `backend/app/api/` 只负责参数校验、鉴权、调用 service、返回响应
- `frontend/` 不允许补算正式金融指标
- DuckDB 在 API/service 路径中只读，写入只能通过 `backend/app/tasks/` / worker
- `Scenario` 与 `Formal` 必须在语义、表、缓存和 `result_meta` 上隔离
- 所有正式结果必须返回 `result_meta`

## 3. 一期技术栈总览

### 3.1 前端层

- `React`
- `TypeScript`
- `Vite`
- `TanStack Query`
- `Ant Design`
- `AG Grid`
- `ECharts`

选型原则：

- 面向高信息密度的分析型工作台，而非轻量营销站点
- 优先保证组件成熟度、交互一致性和开发效率
- 支持总览、头寸、损益、风险、对账与治理等多工作台并存

### 3.2 后端应用层

- `Python 3.11+`
- `FastAPI`
- `Pydantic v2`
- `SQLAlchemy 2.0`

选型理由：

- `Python 3.11+` 适合小团队快速迭代，金融、数据、脚本和 AI 协作生态成熟
- `FastAPI` 类型友好、支持异步 I/O、自动生成 OpenAPI，适合薄 API 层与 Agent 调用面
- `Pydantic v2` 适合做配置管理、请求校验、响应契约与 `result_meta` 结构约束
- `SQLAlchemy 2.0` 成熟稳定，适合承载 PostgreSQL 的事务、治理、审计与映射模型

约束说明：

- `SQLAlchemy 2.0` 主要服务于 `PostgreSQL` 治理与事务层
- 大型分析读路径优先使用 repository + SQL/Core，避免把大查询过度 ORM 化

### 3.3 数据处理层

- `Polars` 作为默认批处理与台账处理引擎
- `Pandas` 作为兼容性回退工具

选型理由：

- `Polars` 更适合大台账、标准化清洗、批量聚合、物化前转换和 schema 更严格的处理流程
- 在导入、转换、对账、物化等链路中，`Polars` 应作为默认实现
- `Pandas` 保留在第三方兼容、历史脚本衔接和少量临时分析场景中使用

本系统不采用“全面禁用 Pandas”的表述，而采用“`Polars` 默认、`Pandas` 回退”的策略。

### 3.4 异步任务与缓存层

- `Dramatiq`
- `Redis`

选型理由：

- 一期任务主要包括导入、物化、外部抓取、报表导出、缓存刷新和重试控制
- `Dramatiq` 足以覆盖上述任务场景，且配置与运维负担低于更重型的任务框架
- `Redis` 同时承担 broker、热缓存与分布式锁职责

明确结论：

- 一期不采用“`Celery + Redis 或 Dramatiq`”的悬空写法
- 一期直接采用 `Dramatiq + Redis`

### 3.5 存储与分析层

- `PostgreSQL`
- `DuckDB`
- `MinIO / S3`

选型理由：

- `PostgreSQL` 用于治理账本、权限、任务、审计、映射、人工调整和版本登记
- `DuckDB` 用于分析事实表、宽表和物化分析缓存，是一期分析读主载体
- `MinIO / S3` 用于原始文件、标准化中间产物、导出报表和快照归档

关键约束：

- `DuckDB` 在 API 路径只读
- `DuckDB` 写入只能通过任务链路完成
- `Redis` 只做缓存、队列和锁，不得作为分析仓

## 4. 上游数据接入定位

上游接入包括：

- 银行现有 `Oracle / DB2`
- 内部业务底层数据源 `zqtz`、`tyw`
- 文件源，如 FI 损益、非标 514/516/517、日均、FX 中间价
- 外部供应商源 `Choice`、`AkShare`

定位说明：

- `Oracle / DB2` 是上游明细台账源，不是本系统新增主存储
- 本系统自身的治理账本以 `PostgreSQL` 为主
- 所有正式结果都必须经过标准化、版本化、规则化处理，并通过 `core_finance` 进入正式链路

## 5. 一期不纳入正式技术栈的项目

一期不将以下组件纳入正式建设目标：

- `Celery`
- `ClickHouse`
- `TimescaleDB`
- `Doris`
- `StarRocks`
- `Greenplum`

原因如下：

- 当前阶段若同时引入上述组件，会明显增加系统复杂度、运维面和分层重复度
- 一期已有 `PostgreSQL + DuckDB + Redis + MinIO/S3` 足以支撑最小闭环
- 当数据量、并发和查询时延证明 `DuckDB` 不再满足需求时，再评估把部分高并发分析面迁移到 `ClickHouse`

## 6. 部署与演进口径

### 6.1 开发环境

- `1 x frontend`
- `1 x api`
- `1 x worker`
- `1 x PostgreSQL`
- `1 x Redis`
- `1 x MinIO`
- `1 x DuckDB volume`

### 6.2 生产一期

- 保持模块化单体与固定调用方向不变
- 保持 `FastAPI / core_finance / 前端协议` 不变
- 保持单写者 DuckDB 约束，不允许多个写路径并发写入

### 6.3 后续演进

仅在出现明确的容量或并发证据时，才评估以下演进：

- 将部分高并发分析面从 `DuckDB` 迁移到 `ClickHouse`
- 将原始与标准化数据进一步对象存储化
- 在不破坏前后端与 `core_finance` 契约的前提下演进物化层

## 7. 当前阶段执行边界

当前仓库默认边界仍为 `Phase 1`，仅在已授权的 scoped override 工作流中放开指定能力。

因此，本文档中的技术栈选型说明：

- 用于固化架构方向和实施边界
- 不构成自动放开 `Phase 2+` 的授权
- 不允许据此提前实现未获授权的正式金融计算或广泛前端 rollout
