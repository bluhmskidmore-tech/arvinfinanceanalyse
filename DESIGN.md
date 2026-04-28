# Design System — MOSS V3

## Product Context

- **What this is:** 面向机构固收与组合管理的业务工作台（经营分析、债券分析、治理与报表等），强调可读数字、可追踪口径与页面级闭环。
- **Who it's for:** 投资/交易、风控、经营与管理层等需要在统一界面里看结论与下钻证据的用户。
- **Space/industry:** 固定收益组合与信用； peers 为各类资管/自营 OMS-Analytics 一体台。
- **Project type:** 内部业务 Web 应用（重数据仪表与表格，非营销站）。

## Visual Reference Authority

- **Primary layout reference:** 组合工作台下的「债券分析」首页完稿视觉（宏观条 → 本日判断 → 组合 KPI → 三列深度区 → 日历与重点券）。该稿为**唯一版式与层次权威**。
- **Tolerance:** 间距、圆角、区块间距允许在 **±5%** 范围内调整以适配实现与响应式；**不得**在无产品确认下改变信息区块的上下顺序与主结论区（首屏主结论）优先级。
- **Research:** 未单独做公网竞品走查；行内惯例（浅色机构台、细边框、蓝系强调、tabular 数字）与代码内 `designTokens` 已对齐。

## Aesthetic Direction

- **Direction:** Industrial / Utilitarian（功能优先、数据密度高）+ **Intentional** 装饰（仅用于「本日判断」等主结论面板的轻量背景/点缀，不抢数据）。
- **Decoration level:** intentional（全局 minimal；关键总结区可有一条浅渐变或淡纹，与 `BondAnalyticsInstitutionalCockpit` 一类 hero 区一致方向）。
- **Mood:** 冷静、可审计；数字与单位一眼可辨，异常与空态显式，不用装饰掩盖缺失数据。
- **Anti-patterns:** 全屏大渐变、紫色主色、与数据无关的插画主体、可交换的「通用仪表盘」无差别模块堆叠。

## Typography

- **Display/Hero 与 UI/Body:** 与 `frontend/src/theme/designSystem.ts` 中 `fontFamily.sans` 一致：**Plus Jakarta Sans**（拉丁，经 `index.html` Google Fonts 加载）+ 中文回退 `PingFang SC` / `Microsoft YaHei UI` / `Noto Sans SC`。内网若屏蔽外网，浏览器会自然回退中文栈，不破坏可用性。
- **Data/Tables/KPI:** **IBM Plex Mono**（`fontFamily.tabular`）+ `font-variant-numeric: tabular-nums`（见 `tabularNumsStyle`），保证列对齐与变动对比稳定。
- **Code / 等宽:** 仅用于原始代码、JSON、调试；业务金额与比率不用等宽体作正文阅读字体。
- **Scale（与实现一致，单位 px）：** 页内标题 18–20；卡片标题 14–16；正文 13–14；辅助 11–12；KPI 主值可用 20–24 视层级。具体以 Ant Design 主题与局部 `Typography` 为准，但**数据行不小于 12px**（过小便读性优先于「塞满一屏」）。

## Color

- **Approach:** balanced — 单一机构主色阶 + 中性灰面 + 语义色（红涨绿跌等以业务与地区约定为准，与 `semantic` 及债券展示 formatter 一致）。
- **Visual reference（配色权威）:** 「总览工作台 / 驾驶舱」完稿——大背景浅灰蓝、白卡片、主导航/主操作 **深蓝 `#1850a1`**，正向/严格态 **森林绿 `#2d8a5e`**，警示/中优先级 **琥珀橙 `#d97706`**，负向 **红 `#ef4444`**，内链/次强调亮蓝 **`info[500]` `#3b82f6`**；正文 **`neutral[900]` `#1f2937`**、次文 **`neutral[600]` `#6b7280`**。实现以 `frontend/src/theme/designSystem.ts` 为单一数值源。
- **Primary:** 以 `designTokens.color.primary[600]`（`#1850a1`）为锚点——**偏蓝、少青**的机构主色；浅表面用 `primary[50–100]`，悬停/强调用 `400–500`。
- **Info / 链接 / 次强调:** `color.info[400–500]` 系（链接锚点 `#3b82f6`），**不**与主色混用为同一语义的第二套「蓝」；新组件从 info 与 primary 二选一，保持页面不超过两种冷色主调。
- **Neutrals:** `neutral[50]` 作应用底（`#f5f7f9` 系），`neutral[50–900]` 作卡片、边线、次文；表头用 `600–800`，禁用浅灰上叠浅灰致对比不足（WCAG 面向内部大屏仍建议正文对比清晰）。
- **Semantic:** success / warning / danger 使用 token 中对应阶；`semantic.profit/loss/up/down` 与债券涨跌展示函数统一（与总览 KPI 绿/红一致）。
- **Dark mode:** 当前以浅色工作台为主；若增加暗色，需单独立项：降低主色饱和约 10–20%、表面用 `neutral.900+` 而非纯黑、图表坐标轴与网格单独定义。

## Spacing

- **Base unit:** 4px（`designTokens.space` 基于 4 的倍数）。
- **Density:** **compact** 为主（债券分析首页信息量大）；全页垂直节奏用 8/12/16/24 组合，**同一栅格行内**卡片 padding 与 gap 保持一致。
- **Scale:** 与 `designTokens.space.1`–`10` 一致；页面外边距与 shell 已定时，域内区段优先 `space.3`–`space.6`。

## Layout

- **Approach:** grid-disciplined（Ant Design `Row` / `Col`，24 栅格；主内容区常见 **三列 8+8+8** 对齐全参考图中间数行）。
- **Grid:** 大桌面 ≥1280px 时三列 8-8-8；收窄时先折行成 12+12 或单栏，**禁止**为保持三列在窄屏上压缩到不可读字号。
- **Max content width:** 随工作台主内容区（与全局 Layout 一致），不在域内单页设独立 max-width 除非与壳冲突。
- **Border radius:** `radius.sm` / `md` / `lg` 分层；宏观条无卡时可 `border-radius: 0` 或全宽浅底；卡片用 `md` 为主，避免全页大圆角「玩具感」。

## Page: Bond Analysis / Portfolio Workbench Home

- **First screen question:** 今日组合在利率/曲线/信用/流动性下**可执行的判断是什么**；其次才是指标与下钻。
- **Block order (locked):**  
  1) 宏观市场条  
  2) 本日判断（大段结论文本 + 轻装饰）  
  3) 组合 KPI 横带（久期、到期收益、信用利差、DV01、Carry+Roll、月/累计收入等按契约）  
  4) 三列：曲线与波动 | 四象策略标签 | 收益归因（瀑布等）  
  5) 三列：结构/风险/今日焦点  
  6) 双列：事件日历 | 重点券表  
- **States:** 每个区块需可感知 **loading / 空 / 错 /  stale(若契约提供)**；无数据时**不得**用随机演示数冒充正式口径。

## Motion

- **Approach:** minimal-functional — 仅状态切换、折叠、Tab、路由过渡；**禁止**大段入场动画干扰扫数。
- **Easing / Duration:** 使用 `designTokens.motion`：`durationFast` 用于 hover；`durationBase` 用于展开；曲线 `easeOut` / `easeInOut` 如定义。

## Relationship to Code

- **Single source of numeric scales:** `frontend/src/theme/designSystem.ts`；域内可扩展（如 `bondAnalyticsCockpitTokens`）但需与本文件**语义一致**。
- **Formal metrics:** 展示仅消费后端或已约定 adapter 输出，前端不自行推导正式金融指标（与 `AGENTS.md` / `CLAUDE.md` 一致）。

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-27 | 引入根目录 DESIGN.md，债券分析页以提供之完稿为权威 ±5% | 用户选择参考图为唯一视觉稿，统一协作与实现验收 |
| 2026-04-27 | 延续系统字体栈，不强制外联展示字体 | 与现有 `designSystem` 一致，减少内网与加载变量 |
| 2026-04-27 | 配色与「总览工作台」对齐：`primary[600]` #1850a1、success/warning/danger/info 与 neutral 底/字色按完稿重标；壳层 surface/canvas 改为白底 | 用户指定总览为配色参考，单一 token 源便于全站一致 |
