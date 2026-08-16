# 金市与计财协同台（/market-finance）P0–P2 优化方案

- 日期：2026-07-20
- 状态：已定稿，待执行
- 范围：`frontend/src/features/market-finance/` 及其定向测试；P2 涉及后端契约（另行开工闸门）
- 决策人：由 AI 按既有证据代为排序，业务口径类决策保留签核闸门

---

## 0. 决策结论（先读这里）

1. **P0 做「首屏实数化」**：把市场 KPI 的「待复核」换成首页行情条已在用的 formal 代表序列读数；把右栏静态「待协调事项」换成 decision-items 真数据。全部复用既有只读链路，不新造口径。
2. **P1 做「证据加深 + 首屏密度」**：对照矩阵的 NIM 行、OCI 行分别接负债分析与余额变动既有读面；压缩首屏纵向节奏让 KPI 带进入 1440×900 首屏；补真实模式验收与审计扩面。
3. **P2 才做「跨域传导正式口径」**：利率→FTP→NIM/OCI 的传导指标必须后端 `core_finance` 契约先行 + 业务 owner 签核，前端只消费。没有签核不动工，资本/RWA 在有正式供数前保持「暂无证据入口」。

三条不可越界约束（延续第一阶段，任何优化不得破坏）：

- 前端不补算任何正式金融指标、不生成综合评分；
- 无契约证据的数字统一「待复核」，不用演示值补位；
- 市场日频、经营报告期、资产负债报告日三条日期各自展示，不合并。

---

## 1. 现状与证据基础

### 1.1 已完成（第一阶段）

- 页面 `MarketFinanceWorkbenchPage.tsx` 挂载于 `/market-finance`（经营日报组，临时开放 + temporary-exception）。
- 15 个定向测试覆盖：五态、质量阻断、依赖查询「未执行」语义、重试仅重发失败链路、可访问性锚点。
- 路由 readiness 契约已登记（`src/test/liveRouteReadinessContracts.ts`）。
- mock 模式 1440×900 截图验收通过，无控制台错误。

### 1.2 已核实的可复用资产（本方案的证据）

| 资产 | 位置 | 用途 |
|---|---|---|
| 市场代表序列白名单（含多 vendor id 回退） | `frontend/src/features/workbench/dashboard-home/dashboardHomeMarket.ts` 的 `MARKET_TICKER_PRIORITY` | P0-1 市场读数实数化的序列选择依据 |
| 决策事项只读接口 | `frontend/src/api/balanceAnalysisClient.ts` 的 `getBalanceAnalysisDecisionItems({reportDate, positionScope, currencyBasis})`，payload 行结构 `BalanceAnalysisDecisionItemStatusRow`（`title / severity / action_label / reason / latest_status`） | P0-2 待协调事项真数据 |
| 负债收益率 / NIM 读面（V1 口径） | `frontend/src/api/liabilityAdbClient.ts` 的 `getLiabilityYieldMetrics(reportDate?)` | P1-1 矩阵「利率 / 资金」财务侧 |
| OCI / AC / TPL 余额变动读面（CNX 控制口径） | `frontend/src/api/balanceMovementClient.ts` 的 `getBalanceMovementAnalysis({reportDate, currencyBasis})` | P1-2 矩阵「OCI / 损益」行 |
| 页面既有三条链路 | market rates / product-category-pnl / balance-analysis overview | 保持不变 |

### 1.3 当前缺口（优化对象）

1. KPI「市场证据状态」是占位「待复核」，首屏没有任何市场读数。
2. 右栏「待协调事项」是静态示例文案，不是数据。
3. 对照矩阵 5 行中「利率/资金」「OCI/损益」的财务侧为占位说明；「资本/RWA」无供数（设计保留）。
4. 真实模式（后端在线）未做浏览器验收。
5. 1440×900 首屏 KPI 带在折叠线以下（hero + 状态条 + 脊柱占满首屏）。

---

## 2. P0：首屏实数化（预计 1–1.5 天）

### P0-1 市场代表读数接入

**决策**：不等业务逐条确认，直接复用首页行情条已在展示的 formal 稳定序列。理由：这些序列已经过首页上线验收、走 `formal` basis、有多 vendor id 回退，属于「复用既有展示口径」而非「新造指标定义」。本页取与资金成本传导最相关的 4 条：

| 展示名 | series_id 回退组（沿用首页） | 与财务侧的关联 |
|---|---|---|
| 10年国债 | `CA.CN_GOV_10Y` / `E1000180` / `EMM00166466` | 资产端定价与 OCI 估值锚 |
| DR007 | `CA.DR007` / `M002` / `EMM00167613` | 资金面与负债成本锚 |
| 人民币汇率 | `CA.USDCNY` / `EMM00058124` | FX 折算与外币头寸 |
| 信用利差 中短票AAA | `CN_CREDIT_AAA_1Y` / `S0059650` / `EMM00166655` | 信用债利差与减值观察 |

**实现要点**：

- 新增页面本地 `marketFinanceModel.ts`：纯函数 `pickRepresentativeSeries(points, whitelist)`，逻辑对齐首页 `pickMarketPoints`（过滤 `refresh_tier === "isolated"`、按 id 组顺序回退），**不合成 sparkline、不算任何派生值**。不共享抽象、不改 dashboard-home。
- KPI 带版式不动（保持 4 卡）：第一卡「市场证据状态」→「10年国债」实数卡（value + unit + latest_change + trade_date + basis）。
- 其余 3 条读数进「市场变化」脊柱节点详情与对照矩阵「利率/资金」行的市场侧单元格。
- 白名单未命中 / isolated / 元数据阻断 → 对应读数显示「—」+「待复核」，不回退任意序列。

**verify**：

1. `marketFinanceModel.test.ts` 单测：命中、缺失、isolated 过滤、多 vendor 回退顺序、不篡改原始值。
2. 页面测试更新：白名单序列上首屏；白名单外序列（如现测试里的 `UNCONFIRMED.001` 9.99）仍不得出现在业务 KPI。
3. `npm run test -- MarketFinanceWorkbenchPage marketFinanceModel`、typecheck、scoped lint、`npm run debt:audit`。
4. mock 模式重截 1440×900。

### P0-2 待协调事项接真数据

- 用页面已解析的 `balanceDate` 调 `getBalanceAnalysisDecisionItems({reportDate: balanceDate, positionScope: "all", currencyBasis: "CNY"})`。
- 展示 `latest_status` 为待处理的前 3 条：`title` + `severity` 色调 + `action_label`，行链接跳 `/decision-items`；面板头显示报告日。
- 查询失败 / 空 / 元数据阻断 → 面板局部五态（复用第一阶段 assess 逻辑），不阻断页面其他区域；删除静态示例文案。
- 只读消费，不接 `updateBalanceAnalysisDecisionStatus` 写链路。

**verify**：页面测试新增 3 例（成功渲染真实条目、空态、失败态且不影响 KPI 区），静态占位文案断言为不存在。

### P0-3 真实模式浏览器验收

- 起后端 + `VITE_DATA_SOURCE=real` dev server，浏览器验收：五态呈现、日期分列、真实 result_meta 的口径标签。
- 后端起不来则记录阻塞原因，P0 不算收口。

**verify**：真实模式 1440×900 截图 + 控制台无错误 + 降级标记与后端实际状态一致。

---

## 3. P1：证据加深与首屏打磨（预计 1–2 天）

### P1-1 矩阵「利率 / 资金」财务侧接 NIM 读面

- 先核对 `LiabilityYieldMetricsPayload` 字段与口径（V1 口径，页面必须标注）；能对上契约则展示付息率 / NIM 读数 + 报告日，接不上保持占位并在方案回执中记录原因。

**verify**：字段核对记录 + 页面测试（读数与口径标签同现）。

### P1-2 矩阵「OCI / 损益」行接余额变动读面

- 核对 `getBalanceMovementAnalysis` 的 OCI 变动汇总字段；注意其口径为 CNX 控制科目，与本页 CNY 读面不同——**原样标注口径差异，不做换算**。

**verify**：字段核对记录 + 页面测试（口径徽标断言）。

### P1-3 首屏密度打磨（Tier 1 视觉）

- 压缩 hero 纵向间距、状态条高度与脊柱节点 `min-height`（目标共省约 48–64px），让 KPI 带上沿进入 1440×900 首屏；不改信息结构与文案。

**verify**：重截 1440×900 对比；`npm run style:audit` 与 `debt:audit` 无增长。

### P1-4 校验扩面

- 本路由纳入 a11y smoke（若 `playwright.config.mjs` 支持按路由追加）；复跑 debt/style/visual token 审计。
- P1 收口后更新导航 `readinessNote`（仍保持「临时开放」，不升级）。

---

## 4. P2：跨域传导正式口径（后端契约先行）

**开工闸门（全部满足才动工）**：

1. 业务 owner 签核传导指标定义（至少 3 条：政策利率/市场利率→FTP 重定价影响、利率变动→OCI 估值影响、资金价格→负债成本影响），收录进 `docs/metric_dictionary.md`；
2. golden sample 备好（含输入行情与期望输出）；
3. `moss-metric-contracts` MCP 恢复或以后端契约测试替代记录。

**实施顺序**：契约文档 → `backend/app/core_finance/` 传导模块 + 单测/黄金样本 → API + `result_meta` → 前端替换矩阵占位与脊柱「待复核」→ UAT。

**边界**：前端始终只消费；资本/RWA 维持「暂无证据入口」直至出现正式供数；本阶段前置于任何「协同评分」类需求。

---

## 5. 不做清单（明确边界）

- 不在前端计算传导、映射、评分、任何派生金融指标；
- P0/P1 不修改 `frontend/src/api/contracts.ts`、`client.ts`、共享 PagePrimitives、AsyncSection/DataSection/Skeletons（并行会话热点文件）；
- 不做 Agent 抽屉（等 Agent 工作台收口后另立任务）;
- 不合并三条日期口径，不把 CNX 与 CNY 读面互相换算；
- 不把导航 readiness 升为「已开放」（需 UAT 后另议）。

---

## 6. 风险与回退

| 风险 | 应对 |
|---|---|
| 真实环境白名单序列缺数，首屏出现多张「—」卡 | 属诚实呈现，保留缺失态；绝不回退演示值 |
| decision-items 报告日与用户预期「最新」有落差 | 面板头显示报告日，跳转后可在 decision-items 页换日期 |
| 并行会话正在修改 contracts.ts / 骨架组件 | P0/P1 只消费既有类型，开工前 `git status` 复核冲突面 |
| `choice_macro_catalog.json` 被并行调整 | 白名单靠运行时返回 + series_id 回退组防御，不静态绑死 catalog 行号 |
| MCP 契约服务不可用 | 以后端契约测试 + config 为证据并记录残余风险；P2 闸门要求恢复或替代记录 |

---

## 7. 每阶段 DoD（验收标准）

- **P0**：新旧测试全绿（15 + 新增 ≥6）；typecheck / scoped lint / debt:audit 通过；mock 与 real 双截图；KPI 带无占位「待复核」（资本/RWA 设计保留项除外）。
- **P1**：矩阵 5 行中 ≥4 行有真读数或有明确的接入阻塞记录；1440×900 首屏含 KPI 带；style/a11y 审计通过。
- **P2**：黄金样本对账通过 + owner UAT 签核后，传导读数才允许上首屏。

## 8. 执行顺序与工作量

P0-1 → P0-2 → P0-3 → P1-3 → P1-1 → P1-2 → P1-4 → （闸门满足后）P2。
前端工作量：P0 约 1–1.5 天，P1 约 1–2 天；P2 前端仅消费约 0.5 天，后端视排期。
