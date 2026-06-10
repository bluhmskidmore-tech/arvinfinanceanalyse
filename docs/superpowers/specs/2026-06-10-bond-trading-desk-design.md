# 单券交易分析台（Bond Trading Desk）

**日期：** 2026-06-10
**页面：** `/bond-trading-desk`（`PAGE-BOND-DESK-001`）
**状态：** MVP 实施中（契约对齐 + 只读拼装，无交易指令）

## 目标

在选定 `bond_code` 与 `report_date` 下，回答：**本券在组合中的身份、估值读数与可审计证据是什么**；对参考图里尚无后端契约的模块，**显式标注 API 待返回**，不在前端编造盘口、约束红绿灯或投资建议。

## 范围

### 做（Wave 1 MVP）

1. 路由 `/bond-trading-desk?bond_code=&report_date=`（`bond_code` 必填）。
2. 从既有只读 API **拼装**单券快照：`top-holdings`、`positions/bonds`、`credit-spread-analysis/detail`。
3. 首屏：身份条 + 主结论 + KPI + 缺口面板 + 决策侧栏（链回 `/bond-analysis` 模块）。
4. 重仓券表增加「单券台」深钻链接。
5. 页面契约写入 `docs/page_contracts.md` §13.9；单元测试覆盖 model 与页面空/有数据态。

### 不做

- 新建后端 `GET /api/bond-analytics/instrument/{code}`（记入差距表，后续迭代）。
- 五档盘口、约束校验表、相似券、情景压力、组合冲击的**假数据**或前端推导正式指标。
- 交易指令、买卖建议、红绿灯合规结论。

## API 差距表

| 参考图模块 | 现有 API | MVP 处理 |
| --- | --- | --- |
| 券身份 / 估值 / 久期 / 权重 | `GET /api/bond-analytics/top-holdings`；`GET /api/positions/bonds`；`GET /api/credit-spread-analysis/detail` 行内字段 | **拼装展示**；查找上限 500 条，未命中则空态 |
| 持仓变动 | `GET /api/bond-analytics/position-changes` | 命中则展示变动行，否则缺口说明 |
| 信用利差 / 基准 | `credit-spread-analysis/detail` 行 | 命中则展示，否则「待返回」 |
| 五档盘口 / 报价 | 无 | **缺口面板** `api_pending` |
| 约束校验（限额/集中度） | 无单券契约 | **缺口面板** |
| 相似券对比 | 无 | **缺口面板** |
| 情景压力 / 组合冲击 | 无单券契约（组合级见 bond-analytics） | **缺口面板** + 链到 `/bond-analysis` |

## 验收

- 无 `bond_code`：页面提示选择或输入，不发无目标拼装请求。
- 有 `bond_code` 且在 top-holdings 命中：首屏结论含代码与市值读数；`bond-trading-desk-conclusion` 可见。
- 未命中：空态说明「不在当前查找范围」，不展示随机演示数。
- `npm run test -- BondTradingDeskPage` 与 model 测试通过；`debt:audit` 不抬升基线。

## 风险

- 单券查找依赖列表扫描（≤500），超大持仓表可能漏券——须在 UI 标注查找范围。
- 信用利差列表仅 top/bottom 子集，多数券无 spread 行属预期空态，非 bug。
