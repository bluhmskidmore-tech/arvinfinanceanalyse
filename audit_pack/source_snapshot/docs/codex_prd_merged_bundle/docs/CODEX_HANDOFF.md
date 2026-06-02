# CODEX_HANDOFF.md

## 1. 你正在构建的是什么

这是一个银行固定收益领域的生产级内部系统。

系统本体是：

`Agent 可调用的分析操作系统`

前端工作台、管理报表和 Agent 查询，只是同一个分析底座的不同消费层。

## 2. 目标形态

采用：

`模块化单体 + 分层分析栈`

暂不拆微服务。

固定调用方向：

`frontend -> api -> services -> (repositories / core_finance / governance) -> storage`

## 3. 非谈判边界

- 正式金融计算只能在 `backend/app/core_finance/` 实现一次。
- `backend/app/api/` 只允许做参数校验、鉴权、调用 service、返回响应。
- `frontend/` 不允许补算正式金融指标。
- `Scenario` 不得污染 `Formal`。
- DuckDB API 常态只读；写入只能走 `backend/app/tasks/`。
- 所有正式结果必须带 `result_meta`。
- 前端、管理报表、Agent 必须共用同一分析服务层。
- 不得删功能，只允许补齐、纠错、重构。

## 4. 文档优先级

阅读顺序如下：

1. `AGENTS.md`
2. `prd-moss-agent-analytics-os.md`
3. `docs/MOSS-V2 系统架构说明`
4. `docs/DOCUMENT_AUTHORITY.md`
5. `docs/IMPLEMENTATION_PLAN.md`
6. `docs/calc_rules.md`
7. `docs/data_contracts.md`
8. `docs/CACHE_SPEC.md`
9. `docs/acceptance_tests.md`
10. `MOSS 系统：取值逻辑、计算层与规则总览`

## 5. 技术栈冻结

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
- PostgreSQL：配置、权限、治理、任务、审计、映射、人工调整
- DuckDB：分析事实表、宽表、物化分析缓存
- Redis：队列、热缓存、锁
- Dramatiq：异步任务
- MinIO / S3：原始文件、导出文件、快照归档

数据源：
- 内部：`zqtz`、`tyw`
- 文件：FI 损益、非标 `514 / 516 / 517`、日均、FX 中间价
- 外部：Choice、AkShare

## 6. 目标目录

```text
repo/
  AGENTS.md
  prd-moss-agent-analytics-os.md
  .codex/
    config.toml
  docs/
    DOCUMENT_AUTHORITY.md
    CODEX_HANDOFF.md
    IMPLEMENTATION_PLAN.md
    CACHE_SPEC.md
    calc_rules.md
    data_contracts.md
    acceptance_tests.md
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

## 7. 正式计算一期能力

`backend/app/core_finance/` 一期至少包含：

- H/A/T -> AC/FVOCI/FVTPL 映射
- 债券月均金额
- 发行类债券剔除
- USD 资产按当日中间价折算 CNY
- Formal PnL（514/516/517）
- Formal / Analytical / Ledger bridge
- risk tensor（DV01 / KRD / CS01 / convexity）
- maturity bucket / pricing bucket / currency basis

## 8. 一期必须保留的工作台

- 首页总览
- 债券头寸工作台
- 同业工作台
- 正式损益工作台
- 非标损益工作台
- 风险工作台
- 对账与治理工作台
- Agent 工作台

## 9. 当前执行边界

当前只允许执行 `Phase 1`：

- repo 骨架
- FastAPI 可启动
- React 前端可启动
- PostgreSQL / DuckDB / Redis / MinIO 连接
- demo 数据导入
- 基础 `result_meta` 契约
- 基础 `tasks/worker` 框架
- smoke tests

完成后停止，不得跨到 Phase 2。

## 10. 每轮必须交付

- 变更文件清单
- 测试结果
- 未完成项
- 下一轮建议
- 风险说明
