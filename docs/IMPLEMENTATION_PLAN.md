# IMPLEMENTATION_PLAN.md

## 总原则

- 先搭边界，再写公式。
- 先让 repo 和依赖能启动，再接正式计算。
- 先让前端、报表、Agent 共用一套服务链路，再补深钻能力。
- 每一阶段都必须可验证、可停止、可回归。

## Phase 1：系统骨架与运行底座

### 目标
建立可启动、可连接、可导入 demo 数据、可跑 smoke tests 的最小系统。

### 必做项
- 建立 repo 目录骨架
- 建立 FastAPI 应用入口与基础路由
- 建立 React/Vite 前端壳层
- 建立 PostgreSQL / DuckDB / Redis / MinIO 连接与配置加载
- 建立 `backend/app/tasks/` worker 骨架
- 建立基础 `result_meta` schema
- 建立 demo 数据导入脚本
- 建立 smoke tests

### 禁止项
- 不得实现正式金融公式
- 不得实现深钻 cube query
- 不得跨到 Phase 2

### 完成标准
- FastAPI 可启动
- `/health` 返回 200
- 前端可启动
- PG / DuckDB / Redis / MinIO 连接路径可验证
- 至少一组 demo 数据可导入
- smoke tests 通过

## Phase 2：正式计算层

### 目标
建立 `core_finance/` 的正式金融计算唯一入口。

### 必做项
- H/A/T -> AC/FVOCI/FVTPL
- 债券月均金额
- 发行类债券剔除
- USD 资产按当日中间价折算 CNY
- Formal PnL（514/516/517）
- 516 标准化有符号金额
- `result_meta` 的版本与质量字段
- 对应测试

### 完成标准
- 所有正式计算只出现在 `core_finance/`
- 相关 API 只调用 service
- 验收测试通过

## Phase 3：深度分析与桥接

### 目标
让系统具备可下钻、可解释、可桥接的分析能力。

### 必做项
- cube-query 协议
- PnL bridge
- formal / analytical / ledger bridge
- risk tensor
- drill paths
- 证据链字段

## Phase 4：前端工作台与 Agent

### 目标
建立 Claude 风格安静工作台，并把 Agent 接到同一分析服务层。

### 必做项
- 首页总览
- 债券 / 同业工作台
- 正式损益 / 非标损益
- 风险 / 对账与治理
- Agent 工作台
- 证据面板
- 报表导出

## Phase 5：治理、审计与观测

### 目标
把系统补齐到可持续运行的治理状态。

### 必做项
- 审计日志
- 缓存治理
- 任务编排
- 告警与观测
- 权限与范围裁剪
- vendor_version / source_version / rule_version 全链路刷新

## 当前执行要求

当前默认只执行 `Phase 1`。

执行口径解释如下：

- `Phase 1 closeout` 仍按 `Phase 1` 处理，只用于完成已打开的骨架、预览、占位、验证与治理收口。
- `.omx/plans/` 中的 `next-slice`、`closeout`、`execution-plan` 文档是计划材料，不是自动执行授权。
- 只有 dated execution update 才能对被点名工作流临时 lifted stop line；该 lifted stop line 也只作用于该工作流。
- 当前有效 scoped overrides 包括：
  - `docs/CURRENT_EXECUTION_UPDATE_2026-04-09.md` 定义的 macro-data stream
  - `docs/CURRENT_EXECUTION_UPDATE_2026-04-11.md` 定义的 `zqtz / tyw` formal-balance-compute stream
- 上述 overrides 都不放开通用 `Phase 2` 正式计算，不放开 Agent MVP，不放开无关工作流的 next slice，也不放开 broad frontend rollout。
- 若未被 dated execution update 点名，`zqtz / tyw` 之外的相关工作仍按原 `Phase 1` / `Phase 1 closeout` 解释。
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-11.md` 只放开 `zqtz / tyw` formal-balance-compute stream，不构成仓库整体 `Phase 2` cutover。

Agent 补充约束：

- 当前仅允许保留 Agent skeleton 预留
- `POST /api/agent/query` 可作为 disabled stub 存在，但不得开放真实查询能力
- `/agent` 可作为 hidden placeholder route 存在，但不得包装为已上线 Agent 工作台
- Agent closeout 完成后暂停，等待系统 `Phase 2` + `Phase 3` 前置能力完成，再进入真实 Agent Phase 4A / 4B

完成后必须输出：

- 变更文件清单
- 新增或修改的测试列表
- 测试结果
- 风险说明
- 未完成项
- 下一轮建议
