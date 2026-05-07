# acceptance_tests.md

## 1. 验收总则

任何涉及正式金融口径的变更，必须同时通过：
- 单元测试
- 集成测试
- 样例数据回归测试
- 关键 API smoke tests

## 2. Phase 1：骨架验收

### 2.1 目录
- 仓库包含 `backend/app/api/`
- 仓库包含 `backend/app/services/`
- 仓库包含 `backend/app/core_finance/`
- 仓库包含 `backend/app/tasks/`
- 仓库包含 `frontend/src/`
- 仓库包含 `docs/`、`tests/`、`config/`

### 2.2 启动
- FastAPI 可启动
- `/health` 返回 200
- 前端可启动并访问首页
- Docker Compose 可启动基础依赖

### 2.3 连接
- PostgreSQL 连接成功
- DuckDB 文件创建成功
- Redis 连接成功或开发模式显式降级

## 3. Phase 2：正式计算验收

### 3.1 H/A/T
- 输入 `可供出售` → `A/FVOCI`
- 输入 `交易性` → `T/FVTPL`
- 输入 `持有至到期` → `H/AC`
- 不可识别输入进入治理异常

### 3.2 516
- 输入 `T损益516=100` → 统一标准口径 `-100`
- 输入 `金额=100, 借贷标识=贷` → ETL 后 `signed_amount` 正确
- 正式层不得再次根据借贷标识翻转

### 3.3 发行类债券排除
- `position_scope=asset` 排除发行类债券
- `position_scope=liability` 仅保留发行类债券
- `position_scope=all` 保留全量

### 3.4 FX
- USD 债券逐日人民币换算正确
- 周末沿用前一营业日中间价
- 缺失营业日中间价时 Formal 失败
- 不允许先均值后换算

### 3.5 日均金额
- `observed`、`locf`、`calendar_zero` 三种 basis 结果可区分
- Formal 与 Analytical basis 不混淆
- 输出 `coverage_ratio` 与 `missing_dates`

## 4. Phase 3：分析深钻验收

### 4.1 cube query
- 支持 `dimensions`
- 支持 `measures`
- 支持 `filters`
- 支持 `drill`
- 支持 `sort`
- 支持 `pagination`

### 4.2 PnL Bridge
- 输出 carry / roll_down / treasury_curve / credit_spread / fx_translation / realized_trading / unrealized_fv / residual
- `explained_pnl` 与 `actual_pnl` 可比较
- `quality_flag` 生成正确

### 4.3 Risk Tensor
- 输出 DV01 / KRD / CS01 / convexity
- 支持发行人、组合、期限桶分组

## 5. Phase 4：前端验收

- 首页为 Claude 风格工作台
- 头寸页支持深钻到单券 / 单笔
- 损益页支持 Formal / Analytical 切换
- 风险页支持期限桶与发行人维度
- 证据面板显示 tables_used / source_version / rule_version / trace_id

## 6. 缓存验收

- 同参数请求命中 Redis 或 DuckDB 物化缓存
- `source_version` 变化后缓存失效
- `rule_version` 变化后缓存失效
- Scenario 不命中 Formal 缓存
- 人工调整后仅相关缓存失效
- API 路径不发生 DuckDB 写入

## 7. 安全与治理验收

- 没有 endpoint 直接写正式金融公式
- 前端没有实现正式金融公式
- 所有正式结果返回 `result_meta`
- Scenario 结果返回 `formal_use_allowed=false`

## 8. 最低回归样例

### 8.1 FI 2025-12
- Formal PnL 汇总结果稳定
- H/A/T 汇总结果稳定

### 8.2 zqtz 2026-03
- 债券月均市值默认排除发行类债券
- USD 债券人民币折算结果稳定

### 8.3 tyw 2026-03
- 同业月均金额可按 observed / locf / calendar_zero 输出

## 9. 交付要求

每次 Codex 输出必须包含：
- 变更文件清单
- 测试清单与结果
- 未完成项
- 风险点
- 是否影响正式金融口径
