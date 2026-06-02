# Phase 2: 驾驶舱页重构

> 前置依赖: Phase 0 + Phase 1 已完成
> 主规格文档: `docs/moss-fixed-income-platform-spec.md` 第六节第 1 项
> Mockup: `.omx/mockups/dashboard_overview_hd.png`

## 目标

将现有 `DashboardPage.tsx`（~216 行）增量重构为 mockup 所示的总览+分流首页。

## 现状

**现有文件**: `src/features/workbench/pages/DashboardPage.tsx`
**现有能力**:
- 多路 `useQuery`: `getOverview`, `getSummary`, `getPnlAttribution`, `getRiskOverview`, `getContribution`, `getAlerts`
- 使用 `executive-dashboard` 的 Overview/Summary/Alerts 组件
- `FixedIncomeDashboardHub` 的模块快照与 teaser
- Mock 任务日历 (`DashboardTasksAndCalendar`)
- Lazy 加载的 `PnlAttributionSection` / `ContributionSection`

**后端已有**: `/ui/home/*` 系列接口（overview, summary, pnl-attribution, risk, contribution, alerts），支持 `report_date` 参数但前端未传。

## 实施要求

### 文件拆分结构
```
src/features/workbench/
├── pages/
│   └── DashboardPage.tsx              # 精简为布局编排
├── dashboard/
│   ├── DashboardKpiRow.tsx            # 8 个 KPI 卡片
│   ├── GlobalJudgment.tsx             # 全局判断摘要
│   ├── ModuleSnapshots.tsx            # 4 个模块快照卡片
│   ├── AlertCenter.tsx                # 预警中心
│   ├── StructureAndMaturity.tsx       # 结构与期限总览
│   ├── TodayTodos.tsx                 # 今日待办
│   ├── KeyCalendar.tsx                # 关键日历
│   └── ModuleEntryCards.tsx           # 模块联动入口（4 大卡片）
├── hooks/
│   └── useDashboardQueries.ts         # 集中 useQuery
└── mocks/
    └── dashboardMock.ts               # 增强现有 dashboardHubMock
```

### Mockup 对照要求

**顶部: 筛选栏**
- 区间: 金融市场条线 (固定)
- 口径: 摊余成本
- 币种: 全部
- 部门: 全部
- 形式: 总监 (可选)
- 右侧: 管理经理角色 + 刷新 + 导出

**KPI 卡片行（8 张）** — 使用 Phase 0 的增强 `KpiCard`:
1. 市场资产 `3,525.0 亿`（债券+买入）
2. 市场负债 `1,817.9 亿`（发行+买入）
3. 资产负债差额 `1,707.1 亿`（静态存量差）
4. 静态利差 `29.5 bp`（资产收益-负债成本）
5. 1年内净缺口 `-373.0 亿`
6. 债券资产浮盈 `+68.48 亿`
7. 发行负债占比 `66.3%`（同业占比 81.8%）
8. 重大预警 `4 项`（缺口/滚续/集中度/集中度），有红色趋势指示

**全局判断** (`GlobalJudgment`):
- 一段管理语言（从后端 `getSummary` 获取或 mock）
- 关键词标签: 资产端主导, 负债端, 短端缺口, 高位配置
- 要点条列

**模块快照** (`ModuleSnapshots`):
- 4 张小卡片: 债券分析 / 跨资产驱动 / 资产负债分析 / 市场数据
- 每张卡片: 一句判断 + 状态标签
- 点击跳转到对应页面

**预警中心** (`AlertCenter`):
- 使用 `AlertList` 组件
- 红色: 短端缺口预警, 1年内净缺口 -373.0 亿
- 橙色: 大额负债到期 03-02 到期 114.54 亿
- 黄色: 发行负债集中度
- 绿色: 异常资产跟踪

**结构与期限总览** (`StructureAndMaturity`):
- 左: 资产/负债结构水平条 (债券资产 vs 同业资产; 发行负债 vs 同业负债)
- 右: 期限净缺口条 (各期限桶的正负缺口)

**今日待办** (`TodayTodos`):
- 来自各专题页的动作摘要列表
- 每项有来源标签和优先级

**关键日历** (`KeyCalendar`):
- 使用 Phase 0 的 `CalendarList` 组件
- 显示近期负债到期 + 事件

**模块联动入口** (`ModuleEntryCards`):
- 4 张较大卡片:
  1. 债券分析 — "回答什么？利率、曲线、信用利差怎么走，组合该买卖什么。输出: 中段优于长端，信用以票息为主"
  2. 跨资产驱动 — "回答什么？中美利率、原油、A股、商品对债券定价怎么传导。输出: 外部约束增强/风险偏好趋于稳定"
  3. 资产负债分析 — "回答什么？期限缺口、成本压力、滚续安排、风险指标。输出: 1年内缺口 -373.0 亿 / 浮盈 68.5 亿"
  4. 市场数据 — "回答什么？现、资金、期货、存单和信用成交在盘中怎么变化。输出: DR007 1.82% / AAA 3Y 45bp / 10Y 国债 1.94%"
- 每张卡片可点击跳转

### 关键约束
- Dashboard 是**总览+导航+优先级**，不做深度分析
- 不要把各专题页内容全部塞进来
- 后端 `report_date` 参数应开始传递（从筛选栏获取）
- Mock 数据从 seed values 生成

## 验证

```bash
npm run lint && npm run typecheck && npm run build
```

视觉对比 `dashboard_overview_hd.png`。
