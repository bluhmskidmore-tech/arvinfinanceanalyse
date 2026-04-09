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

当前只执行 `Phase 1`。

完成后必须输出：

- 变更文件清单
- 新增或修改的测试列表
- 测试结果
- 风险说明
- 未完成项
- 下一轮建议
