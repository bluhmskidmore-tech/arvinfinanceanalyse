# 市场工作台 Cursor Prompt Pack

本文档用于把低风险外围任务交给 Cursor 执行。Codex 当前保留核心任务：`/market-data` 真实数据链路、静态行情清理、指标来源/单位/日期/fallback 的业务正确性。

## 分工原则

- Cursor 做低风险外围任务：文档、路由、已有接口接线、测试补齐、状态文案。
- Codex 保留核心任务：`/market-data` 的真实数据链路、静态行情清理、指标来源/单位/日期/fallback 的业务正确性。
- 所有任务都必须遵守 `F:\MOSS-V3\AGENTS.md`：不扩张 `frontend/src/api/client.ts`，不加假数据，不做无关重构，不提交代码除非另有要求。

## Cursor Prompt 1：新闻事件页开放

```text
你在 F:\MOSS-V3 工作。请先阅读 AGENTS.md，严格遵守：小改动、不重构、不扩张 frontend/src/api/client.ts、不加 mock 假数据、不提交。

任务：把市场工作台里的 /news-events 从预留页接到已有 NewsEventsPage，但保持 analytical / temporary-exception 定位。

请检查并修改：
- frontend/src/mocks/navigation.ts
- frontend/src/router/routes.tsx
- frontend/src/features/news-events/NewsEventsPage.tsx
- frontend/src/router/__tests__/RouteRegistry.test.tsx 或相邻路由测试
- 现有 news-events 测试文件

要求：
1. navigation 中 news-events 从 placeholder/reserved 调整为 live temporary-exception。
2. /news-events 直接渲染已有 NewsEventsPage，不再显示 reserved placeholder。
3. 保留页面上的空数据、加载失败、分页、筛选行为。
4. 不新增后端接口，不新增全局 client.ts 内容。
5. 补/改测试：访问 /news-events 时能看到新闻事件页核心控件，而不是预留提示。
6. 运行最窄测试，例如：
   npm test -- NewsEventsPage RouteRegistry
7. 最后汇报：改了哪些文件、测试结果、是否还有风险。
```

## Cursor Prompt 2：市场页供给日历接线

```text
你在 F:\MOSS-V3 工作。请先阅读 AGENTS.md，严格遵守：小改动、不重构、不加假数据、不提交。

任务：把 MarketData 页面里的 NewsAndCalendar 日历 tab 接到已有供给日历接口。

请检查：
- frontend/src/features/market-data/components/NewsAndCalendar.tsx
- frontend/src/api/marketDataClient.ts
- frontend/src/features/market-data/pages/MarketDataPage.test.tsx 或组件测试
- 后端已有接口 /ui/calendar/supply-auctions 仅用于理解返回字段，不要改后端

要求：
1. 使用已有 marketDataClient 的 getResearchCalendarEvents / supply-auctions 能力。
2. 日历 tab 显示真实 events：日期、标题/事件名、来源或类型、状态。
3. 处理 loading、error、empty。
4. 不再保留“日历未接入页面 API”这类占位文案。
5. 不改全局 client.ts。
6. 补测试：mock 日历 API 返回 events 时渲染列表；返回空数组时显示 no-data；失败时显示错误状态。
7. 运行最窄测试：
   npm test -- MarketDataPage NewsAndCalendar
8. 最后汇报：改了哪些文件、测试结果、剩余风险。
```

## Cursor Prompt 3：市场合同与 gap 文档补齐

```text
你在 F:\MOSS-V3 工作。请先阅读 AGENTS.md，严格遵守：不要猜指标定义，不要把 analytical/preview 数据写成 formal，不提交。

任务：补齐市场工作台文档中的现状、gap、实施边界。只写事实和明确 gap，不发明业务定义。

请检查：
- docs/page_contracts.md
- docs/metric_dictionary.md
- docs/golden_sample_plan.md
- docs/golden_sample_catalog.md
- docs/DOCUMENT_AUTHORITY.md

要求：
1. PAGE-MKT-001 明确市场页当前是 mixed-source：formal rates + analytical macro/fx/ncd/livermore/linkage。
2. 记录 GAP-MKT-DATA：市场页还缺正式 MTR-* 指标字典和 golden sample。
3. 明确硬编码行情面板必须改为真实数据或 no-data/source-pending。
4. 明确 NCD 当前是 Shibor funding proxy，不是实际 NCD 期限 x 评级矩阵。
5. 明确 Livermore risk_exit 依赖 ACTIVE A 股持仓和 supplement 数据。
6. 明确 /news-events 若开放，只是 analytical temporary-exception，不是 formal metric page。
7. 不新增未经确认的单位、公式、series id、golden sample 数值。
8. 运行可用的文档/测试检查；如果没有文档检查脚本，说明未运行原因。
9. 最后汇报：改了哪些文档、没有确认的风险点。
```

## Cursor Prompt 4：市场页非核心状态测试补齐

```text
你在 F:\MOSS-V3 工作。请先阅读 AGENTS.md，严格遵守：测试优先，小改动，不重构业务逻辑，不提交。

任务：补市场页外围状态测试，不改核心数据映射逻辑。

请检查：
- frontend/src/features/market-data/pages/MarketDataPage.test.tsx
- frontend/src/features/market-data/components/*
- frontend/src/api/marketDataClient.ts

要求：
1. 增加测试覆盖：stale/fallback warning 可见。
2. 增加测试覆盖：NCD proxy 明确显示非实际 NCD 矩阵。
3. 增加测试覆盖：Livermore risk_exit blocked 时展示原因。
4. 增加测试覆盖：macro-bond-linkage warning/fallback 文案可见。
5. 不要修改核心计算逻辑；如果发现逻辑缺口，只记录 TODO 或在最终汇报中说明。
6. 运行：
   npm test -- MarketDataPage marketDataFormat marketDataCategoryStore
7. 最后汇报：新增测试点、测试结果、发现的逻辑缺口。
```

## Cursor Prompt 5：债务审计准备

```text
你在 F:\MOSS-V3 工作。请先阅读 AGENTS.md，严格遵守：只做检查和小修，不做无关重构，不提交。

任务：为市场工作台改造准备 debt audit，不修改业务行为。

请执行：
1. 检查 frontend/src/features/market-data 是否有重复 inline style、明显重复格式化函数、页面内可局部抽出的纯展示常量。
2. 只允许修复低风险问题：重复 className/常量命名、测试描述、死代码 import。
3. 不移动核心逻辑，不改 API shape，不改显示数值。
4. 运行：
   npm run debt:audit
   npm test -- MarketDataPage
5. 如果 debt:audit 失败，记录失败项和涉及文件，不要为了过审大范围重构。
6. 最后汇报：改动、审计结果、不能安全处理的 debt。
```

## 建议执行顺序

1. Cursor 先做 Prompt 3 和 Prompt 4：不会阻塞核心链路，还能把事实和测试护栏立起来。
2. Codex 做核心 MarketData 真实数据链路和硬编码行情清理。
3. Cursor 做 Prompt 1 和 Prompt 2：新闻事件开放、供给日历接线。
4. Cursor 做 Prompt 5：最后外围审计准备。
5. Codex 做最终整体验证：核心测试、路由测试、debt audit、必要的浏览器检查，并汇总剩余业务风险。

## 验收标准

- 市场页不再展示未经来源确认的硬编码行情。
- 有真实来源的市场指标能追到 API、日期、单位、quality/fallback 状态。
- 没有真实来源的板块显示 no-data/source-pending，而不是看似真实的数字。
- `/news-events` 要么按计划开放为 analytical temporary-exception，要么测试清楚说明仍为预留；本方案默认开放。
- 文档明确 `GAP-MKT-DATA`、NCD proxy、Livermore blocked、macro-bond analytical warning。
- 相关测试通过，`npm run debt:audit` 无新增债务。
