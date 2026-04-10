# 债券金融分析系统架构栈规范（给 Codex）

## 1. 总体形态

采用**模块化单体 + 分层分析栈**，不要一开始拆微服务。

固定调用方向：

- frontend -> api -> services -> (repositories / core_finance / governance) -> storage
- 所有正式金融计算只允许出现在 `backend/app/core_finance/`
- `backend/app/api/` 只允许做参数校验、鉴权、调用 service、返回响应
- `frontend/` 不允许补算正式金融指标
- DuckDB 常态只读；写入只能走 `backend/app/tasks/`
- Scenario 与 Formal 必须隔离，结果必须带 `result_meta`

## 2. 技术栈冻结

### 前端
- React
- TypeScript
- Vite
- TanStack Query
- Ant Design
- AG Grid（大表）
- ECharts（曲线/归因/热力图）
- Claude 风格 theme layer（安静留白，不改变业务能力）

### 后端
- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- 服务分层：`api/`、`services/`、`core_finance/`、`repositories/`、`tasks/`、`governance/`

### 存储与队列
- PostgreSQL：配置、权限、治理、任务、审计、映射、人工调整
- DuckDB：分析事实表、宽表、物化分析缓存
- Redis：队列、热缓存、锁
- Dramatiq：异步任务
- MinIO / S3：原始文件、导出文件、快照归档

### 数据源接入
- 内部：`zqtz`、`tyw`
- 文件：FI 损益、非标 514/516/517、日均、FX 中间价
- 外部：Choice、AkShare

## 3. 目录结构

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
    pnl/
      README.md
      appendix-pnl-fixture-matrix.md
    CODEX_HANDOFF.md
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

## 4. 层级职责

### api/
- 参数校验
- 鉴权
- service 调用
- DTO 输出
- 错误映射

### services/
- 读取 DuckDB / PostgreSQL / 外部适配器
- 调用 `core_finance/`
- 组装 `result_meta`
- 不允许直接写死金融公式

### core_finance/
唯一正式金融计算入口，至少包括：
- H/A/T -> AC/FVOCI/FVTPL 映射
- 债券月均金额
- 发行类债券剔除
- USD 资产按当日中间价折算 CNY
- formal PnL（514/516/517）
- formal / analytical / ledger bridge
- risk tensor（DV01 / KRD / CS01 / convexity）
- maturity bucket / pricing bucket / currency basis

### repositories/
- DuckDB 只读查询封装
- PostgreSQL ORM / repository 封装
- 外部数据源 adapter

### tasks/
- 导入 zqtz / tyw / 文件源
- 刷新 DuckDB 事实表
- 构建分析缓存
- 刷新 source_version / rule_version
- 生成导出与管理报表

### governance/
- result_meta
- trace_id
- source_version
- rule_version
- quality_flag
- cache manifest
- audit log

## 5. 数据分层

### PostgreSQL（事务与治理）
- source_mapping
- cost_center_mapping
- portfolio_mapping
- manual_adjustment
- rule_version_registry
- source_version_registry
- cache_manifest
- cache_build_run
- cache_invalidation_log
- user_role_scope
- agent_audit_log
- job_run_log

### DuckDB（分析与物化）
- dim_instrument
- dim_issuer
- dim_counterparty
- dim_portfolio
- dim_cost_center
- fact_bond_daily_snapshot
- fact_interbank_daily_snapshot
- fact_bond_monthly_avg
- fact_interbank_monthly_avg
- fact_formal_pnl_fi
- fact_nonstd_pnl_bridge
- fact_formal_analytical_bridge_daily
- fact_pnl_bridge_daily
- fact_risk_tensor_daily
- fact_fx_converted_positions_daily

### 对象存储
- 原始 zip/xls/xlsx
- 中间标准化 parquet/csv
- 导出报表
- 历史快照归档

## 6. 缓存栈

- L0：前端 TanStack Query
- L1：Redis 响应缓存
- L2：DuckDB 物化分析缓存
- L3：PostgreSQL 缓存治理元数据

缓存失效必须由：
- `source_version`
- `rule_version`
- `cache_version`
驱动，TTL 只做兜底。

## 7. Agent 栈

Agent 只做分析与解释，不得绕过正式计算层。

### Agent 工具
- SQL 只读查询工具（受权限和白名单控制）
- 图表生成工具
- 报表导出工具
- 证据收集工具

### Agent 输出必须带
- tables_used
- filters_applied
- sql_executed
- rule_version
- source_version
- evidence_rows
- quality_flag
- next_drill

## 8. 部署栈

### 开发环境
- Docker Compose
- 1 x frontend
- 1 x api
- 1 x worker
- 1 x PostgreSQL
- 1 x Redis
- 1 x MinIO
- 1 x DuckDB volume

### 生产一期
- Nginx / Traefik
- 1~2 x frontend replica
- 1 x api replica（优先）
- 1 x worker replica
- Managed PostgreSQL
- Managed Redis
- MinIO / S3
- DuckDB 挂载独立数据卷

说明：一期不要让多个写路径同时碰 DuckDB。

### 生产二期（数据量/并发上来后）
- 保留 FastAPI / core_finance / 前端协议不变
- 把部分 DuckDB 大宽表/高并发分析迁移到 ClickHouse
- 原始与标准化数据上对象存储 / Iceberg

## 9. 前端工作台

必须保留：
- 首页总览
- 债券头寸工作台
- 同业工作台
- 正式损益工作台
- 非标损益工作台
- 风险工作台
- 对账与治理工作台
- Agent 工作台

UI 风格要求：Claude 风格的安静工作台，但不删专业能力。

## 10. Phase 划分

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

## 11. 禁止事项

- 不得在前端实现正式金融公式
- 不得在 endpoint 里写金融逻辑
- 不得把 Scenario 写进 Formal 事实表
- 不得把 Redis 当分析仓
- 不得让多个写者并发写 DuckDB
- 不得删功能，只允许补齐、修正、重构

## 12. 给 Codex 的首条指令

```md
先完整阅读：
1. AGENTS.md
2. docs/CODEX_HANDOFF.md
3. docs/architecture.md
4. docs/calc_rules.md
5. docs/data_contracts.md
6. docs/CACHE_SPEC.md
7. docs/acceptance_tests.md

必须遵守：
- 正式金融计算只允许在 backend/app/core_finance/
- api 只允许做薄层
- frontend 不允许补算正式指标
- DuckDB 只读查询，写入走 tasks/
- Scenario 与 Formal 隔离
- 所有正式结果返回 result_meta
- 不得删功能

第一轮只做 Phase 1，并输出：
- 变更文件清单
- 测试结果
- 未完成项
- 下一轮建议
```
