# MOSS Agent Analytics OS PRD

## 1. 项目定义

### 1.1 系统本质

系统本体定义为：

`Agent 可调用的分析操作系统`

前端驾驶舱、管理层报表、研究员分析页，都是分析操作系统的消费层，而不是系统本体。

### 1.2 项目目标

基于 `data_input/` 中的业务底层文件以及外部市场数据源，建设一套生产级、内部使用、可治理、可解释、可重建、可供 agent 直接调用的债券金融分析平台。

平台需要同时支持：

- 研究员分析
- 中后台管理层总览与固定口径报表
- 风险与损益穿透
- Agent 直接调用分析能力、解释链路和证据

### 1.3 非目标

- 不做移动端
- 不做多租户
- 不做对外客户版

## 2. 顶层架构决策

### 2.1 总体形态

采用：

`模块化单体 + 分层分析栈`

不要一开始拆微服务。

### 2.2 固定调用方向

必须遵守：

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

并且：

- 所有正式金融计算只允许出现在 `backend/app/core_finance/`
- `backend/app/api/` 只允许做参数校验、鉴权、调用 service、返回响应
- `frontend/` 不允许补算正式金融指标
- DuckDB 常态只读；写入只能走 `backend/app/tasks/`
- `Scenario` 与 `Formal` 必须隔离
- 所有正式结果必须带 `result_meta`

### 2.3 ADR

**Decision**

采用“模块化单体控制面 + FastAPI 服务分层 + Dramatiq 异步任务 + DuckDB 物化分析栈 + PostgreSQL 治理账本 + Redis 热缓存/锁 + MinIO/S3 对象存储 + MCP/REST 双接口”的架构。

**Drivers**

- Agent-first
- 中文环境优先
- 正式金融计算必须集中治理
- DuckDB 单写者
- 多数页面要快
- 正式结果必须可解释、可追溯、可重建

**Alternatives considered**

- 早期微服务化
- 纯看板系统
- 仅导出文件给 agent
- 前端自算部分金融指标

**Why chosen**

- 有利于先把正式金融计算边界钉死
- 有利于统一治理 `Formal` / `Scenario` / `Analytical`
- 有利于前端、管理报表、agent 共用同一事实层
- 有利于在不破坏接口契约的情况下，后续再迁移部分大宽表到 ClickHouse 或对象存储分层

**Consequences**

- 控制面职责偏重，必须用目录和边界严格控权
- 需要架构测试阻止金融公式跑到 endpoint 或前端
- 需要 worker 串行化 DuckDB 写入

**Follow-ups**

- PnL 源数据回归与测试对照表：`docs/pnl/appendix-pnl-fixture-matrix.md`
- 定义 `result_meta` 契约
- 定义 `core_finance` 模块边界
- 定义 `Choice` / `AkShare` 外部适配器边界
- 定义 `Formal` / `Scenario` / `Analytical` 数据隔离方式
- 定义缓存与版本治理契约

## 3. 技术栈冻结

### 3.1 前端

- React
- TypeScript
- Vite
- TanStack Query
- Ant Design
- AG Grid
- ECharts
- Claude 风格 theme layer

说明：

- 风格要求是“安静工作台”，不影响业务能力与信息密度
- AG Grid 只用于大表与 drill 页面
- ECharts 只用于曲线、归因、热力图、风险结构图

### 3.2 后端

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x

固定服务分层：

- `api/`
- `services/`
- `core_finance/`
- `repositories/`
- `tasks/`
- `governance/`

### 3.3 存储与队列

- PostgreSQL
- DuckDB
- Redis
- Dramatiq
- MinIO / S3

职责固定如下：

- PostgreSQL：配置、权限、治理、任务、审计、映射、人工调整
- DuckDB：分析事实表、宽表、物化分析缓存
- Redis：队列、热缓存、锁
- Dramatiq：异步任务执行
- MinIO / S3：原始文件、导出文件、快照归档

### 3.4 数据源接入

内部源：

- `zqtz`
- `tyw`

文件源：

- FI 损益
- 非标 `514 / 516 / 517`
- 日均
- FX 中间价

PnL 源文件的 fixture 布局、`source_family` 与现有测试门禁对照见 `docs/pnl/appendix-pnl-fixture-matrix.md`（不替代本章口径）。

外部源：

- `Choice`
- `AkShare`

外部数据策略：

- `Choice` 作为生产级外部市场/参考数据主供应商
- `AkShare` 作为开放数据补充和部分非关键参考数据适配器
- 任一外部数据都不允许绕过平台直接进入正式结果

## 4. 目标目录结构

目标仓库结构按下述形式收敛：

```text
repo/
  AGENTS.md
  .codex/
    config.toml
  docs/
    architecture.md
    calc_rules.md
    data_contracts.md
    CACHE_SPEC.md
    acceptance_tests.md
    CODEX_HANDOFF.md
    pnl/
      README.md
      appendix-pnl-fixture-matrix.md
  backend/
    app/
      api/
      services/
      core_finance/
      repositories/
      tasks/
      governance/
      schemas/
      models/
      security/
      main.py
  frontend/
    src/
      pages/
      components/
      api/
      hooks/
      theme/
  sql/
  config/
  scripts/
  tests/
  sample_data/
```

## 5. 层级职责

### 5.1 api/

只允许：

- 参数校验
- 鉴权
- service 调用
- DTO 输出
- 错误映射

禁止：

- 写金融公式
- 直接拼 SQL 生成正式结果
- 在 endpoint 中混入 Scenario / Formal 逻辑

### 5.2 services/

职责：

- 读取 DuckDB / PostgreSQL / 外部适配器
- 调用 `core_finance/`
- 组装 `result_meta`
- 协调缓存读取与重建状态

禁止：

- 直接写死正式金融公式

### 5.3 core_finance/

这是唯一正式金融计算入口。

一期至少包含：

- H/A/T -> AC / FVOCI / FVTPL 映射
- 债券月均金额
- 发行类债券剔除
- USD 资产按当日中间价折算 CNY
- formal PnL（514/516/517）
- formal / analytical / ledger bridge
- risk tensor（DV01 / KRD / CS01 / convexity）
- maturity bucket / pricing bucket / currency basis

补充要求：

- `Formal` 和 `Scenario` 代码路径必须分离
- 任何正式结果必须可回溯到 `source_version` / `rule_version`

### 5.4 repositories/

职责：

- DuckDB 只读查询封装
- PostgreSQL ORM / repository 封装
- 外部数据源 adapter

外部 adapter 一期至少包括：

- `choice_adapter`
- `akshare_adapter`

### 5.5 tasks/

职责：

- 导入 `zqtz` / `tyw` / 文件源
- 刷新 DuckDB 事实表
- 构建分析缓存
- 刷新 `source_version` / `rule_version` / `vendor_version`
- 生成导出与管理报表

说明：

- 所有 DuckDB 写入只能在这里发生
- Dramatiq worker 中必须对 materialize 任务加单写者约束

### 5.6 governance/

职责：

- `result_meta`
- `trace_id`
- `source_version`
- `rule_version`
- `vendor_version`
- `quality_flag`
- `cache_manifest`
- `audit_log`

## 6. 数据分层

### 6.1 PostgreSQL：事务与治理

一期至少建设：

- `source_mapping`
- `cost_center_mapping`
- `portfolio_mapping`
- `manual_adjustment`
- `rule_version_registry`
- `source_version_registry`
- `vendor_version_registry`
- `cache_manifest`
- `cache_build_run`
- `cache_invalidation_log`
- `user_role_scope`
- `agent_audit_log`
- `job_run_log`

### 6.2 DuckDB：分析与物化

一期至少建设：

- `dim_instrument`
- `dim_issuer`
- `dim_counterparty`
- `dim_portfolio`
- `dim_cost_center`
- `fact_bond_daily_snapshot`
- `fact_interbank_daily_snapshot`
- `fact_bond_monthly_avg`
- `fact_interbank_monthly_avg`
- `fact_formal_pnl_fi`
- `fact_nonstd_pnl_bridge`
- `fact_formal_analytical_bridge_daily`
- `fact_pnl_bridge_daily`
- `fact_risk_tensor_daily`
- `fact_fx_converted_positions_daily`
- `fact_choice_bond_market_daily`
- `fact_choice_macro_daily`

### 6.3 对象存储

存放：

- 原始 `zip/xls/xlsx`
- 中间标准化 `parquet/csv`
- 导出报表
- 历史快照归档
- 外部供应商原始快照归档

### 6.4 正式真相边界

正式金融结果只能来自：

- 内部业务底层数据和受控外部参考数据
- 经过标准化、版本化、规则化处理
- 经 `core_finance/` 计算
- 物化到 DuckDB
- 再由 API 只读返回

前端禁止：

- 自行补算正式指标
- 组合多个接口自行形成正式口径

外部数据禁止：

- 直接透传 Choice / AkShare 响应作为正式结果

## 7. 缓存栈

### 7.1 分层

- `L0`：前端 TanStack Query
- `L1`：Redis 响应缓存
- `L2`：DuckDB 物化分析缓存
- `L3`：PostgreSQL 缓存治理元数据

### 7.2 失效驱动

缓存失效必须由以下版本对象驱动：

- `source_version`
- `rule_version`
- `cache_version`
- `vendor_version`

TTL 只做兜底，不做正式失效主机制。

### 7.3 强缓存键

统一结构：

```text
{domain}:{view}:{report_date_or_month}:{basis}:{position_scope}:{currency_basis}:{source_version}:{vendor_version}:{rule_version}:{filter_hash}
```

禁止弱键。

### 7.4 DuckDB 单写者

必须遵守：

- DuckDB API 常态只读
- 写入只能通过 `backend/app/tasks/`
- 不能让多个写者并发写 DuckDB

## 8. 外部数据平面

### 8.1 Choice

定位：

- 生产级外部市场数据与参考数据源

一期优先接入：

- 债券收益率 / 估值参考
- 宏观与资金面关键序列
- 发行主体与债券参考字段

### 8.2 AkShare

定位：

- 开放补充数据源
- 非关键参考数据与辅助校验来源

### 8.3 外部数据接入路径

固定路径：

`vendor adapter -> raw snapshot archive -> normalized vendor slice -> service join -> core_finance -> materialized cache`

### 8.4 外部数据降级

当 Choice 不可用时：

- 依赖 Choice 的视图允许返回最近一次成功快照
- 必须显式返回 `vendor_stale` / `vendor_unavailable`
- 不依赖外部供应商的正式结果不得被连带阻塞

## 9. result_meta 契约

所有正式结果必须带 `result_meta`。

至少包含：

- `trace_id`
- `basis`
- `result_kind`
- `scenario_flag`
- `source_version`
- `vendor_version`
- `rule_version`
- `cache_version`
- `quality_flag`
- `tables_used`
- `filters_applied`
- `sql_executed`
- `evidence_rows`
- `next_drill`

建议响应结构：

```json
{
  "result_meta": {
    "trace_id": "tr_xxx",
    "basis": "formal",
    "result_kind": "analysis_view",
    "scenario_flag": false,
    "source_version": "sv_xxx",
    "vendor_version": "vv_choice_xxx",
    "rule_version": "rv_xxx",
    "cache_version": "cv_xxx",
    "quality_flag": "ok",
    "tables_used": ["fact_bond_monthly_avg"],
    "filters_applied": {"report_date": "2026-03-31"},
    "sql_executed": ["SELECT ..."],
    "evidence_rows": 42,
    "next_drill": ["issuer", "portfolio"]
  },
  "result": {}
}
```

## 10. Agent 栈

### 10.1 基本原则

Agent 只做分析与解释，不得绕过正式计算层。

### 10.2 Agent 工具

一期至少提供：

- SQL 只读查询工具
- 图表生成工具
- 报表导出工具
- 证据收集工具
- 正式分析视图调用工具
- 规则命中链路查询工具

### 10.3 Agent 输出硬要求

必须带：

- `tables_used`
- `filters_applied`
- `sql_executed`
- `rule_version`
- `source_version`
- `vendor_version`
- `evidence_rows`
- `quality_flag`
- `next_drill`

## 11. API 与服务面

### 11.1 API 分类

- Slice API
- Analysis API
- Report API
- Lineage API
- Build API

### 11.2 服务面原则

- 前端和 agent 共用同一分析服务层
- 不允许前端一套、agent 一套
- 所有正式结果统一由 `services -> core_finance -> DuckDB` 读取链路返回

## 12. 前端工作台

一期必须保留：

- 首页总览
- 债券头寸工作台
- 同业工作台
- 正式损益工作台
- 非标损益工作台
- 风险工作台
- 对账与治理工作台
- Agent 工作台

UI 风格要求：

- Claude 风格的安静工作台
- 不删专业能力
- 信息密度高但不嘈杂

## 13. 部署栈

### 13.1 开发环境

- Docker Compose
- `1 x frontend`
- `1 x api`
- `1 x worker`
- `1 x PostgreSQL`
- `1 x Redis`
- `1 x MinIO`
- `1 x DuckDB volume`

### 13.2 生产一期

- Nginx / Traefik
- `1~2 x frontend replica`
- `1 x api replica`
- `1 x worker replica`
- Managed PostgreSQL
- Managed Redis
- MinIO / S3
- DuckDB 挂载独立数据卷

说明：

- 一期不要让多个写路径同时碰 DuckDB

### 13.3 生产二期

保持以下契约不变：

- FastAPI / core_finance / 前端协议

允许迁移：

- 部分 DuckDB 大宽表 / 高并发分析 -> ClickHouse
- 原始与标准化数据 -> 对象存储 / Iceberg

## 14. 实施阶段

### Phase 1

- repo 骨架
- FastAPI 可启动
- React 前端可启动
- PG / DuckDB / Redis / MinIO 连接
- demo 数据导入

### Phase 2

- H/A/T
- 日均金额
- FX 中间价折算
- formal PnL
- 发行类债券剔除

### Phase 3

- cube-query
- pnl bridge
- formal-analytical bridge
- risk tensor
- deep drill paths

### Phase 4

- Claude 风格前端
- 证据面板
- 导出报表
- Agent 工作台

### Phase 5

- 审计
- 任务编排
- 缓存治理
- 告警与观测

## 15. 风险与缓解

### 风险 1

正式金融逻辑散落到 endpoint、service 或前端。

缓解：

- 架构测试限制导入边界
- 代码审查强制检查 `core_finance` 唯一性

### 风险 2

DuckDB 被多个写路径破坏一致性。

缓解：

- 所有写入统一走 `tasks/`
- Dramatiq materialize worker 单写者约束

### 风险 3

`Formal` 与 `Scenario` 混表，导致管理口径污染。

缓解：

- 物理隔离或强逻辑隔离
- `result_meta` 强制带 `basis` 和 `scenario_flag`

### 风险 4

Choice / AkShare 断连导致热路径页面整体雪崩。

缓解：

- 外部数据平面独立
- 最近成功快照回退
- `vendor_stale` / `vendor_unavailable` 明示

### 风险 5

前端、报表、agent 看到不同结果。

缓解：

- 共用同一 `services -> core_finance -> DuckDB` 分析链路
- 所有正式结果强制带版本与证据

## 16. 禁止事项

- 不得在前端实现正式金融公式
- 不得在 endpoint 里写金融逻辑
- 不得把 Scenario 写进 Formal 事实表
- 不得把 Redis 当分析仓
- 不得让多个写者并发写 DuckDB
- 不得删功能，只允许补齐、修正、重构

## 17. 当前执行边界

当前默认执行边界已切换为 `repo-wide Phase 2（通用正式计算）`。

边界解释如下：

- 本次 repo-wide `Phase 2` cutover 只覆盖 formal-compute 主链：
  - formal balance
  - formal PnL
  - formal FX
  - formal yield curve
  - PnL bridge
  - risk tensor
  - 核心 bond analytics formal read surfaces
- `Phase 1 closeout` 仍属于历史收口概念；它只用于未纳入本次 cutover 的骨架、预览、占位、验证和治理欠账。
- `.omx/plans/` 中的 `next-slice`、`closeout`、`execution-plan` 等文档属于计划与候选执行面，不是权限来源。
- dated execution update 仍可用于 repo-wide `Phase 2` 已排除模块或未来新工作流的 scoped override；它们不再是 formal-compute 主链的主要授权来源。

本次 cutover 明确不包含：

- `executive.*`
- Agent MVP / `/api/agent/query` / `/agent`
- `source_preview` / `macro-data` / `choice-news` / `market-data` 的 preview/vendor/analytical surface
- `qdb_gl_monthly_analysis`、`liability_analytics_compat` 等 analytical-only / compatibility 模块
- cube-query、broad frontend rollout、以及其他 `Phase 3 / Phase 4` 风格扩张项

默认输出要求如下：

- 变更文件清单
- 测试结果
- 未完成项
- 下一轮建议
