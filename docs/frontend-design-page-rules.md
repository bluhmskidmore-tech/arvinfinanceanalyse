# Frontend Design Page Rules

本文保留 [DESIGN.md](../DESIGN.md) 的页面锁定、已批准例外及适用边界。仅在触及对应路由、IB 兼容或特定指标着色时读取相关节；全站规则与开发验收仍以 DESIGN 和 [frontend/AGENTS.md](../frontend/AGENTS.md) 为准。

<a id="dark-routes"></a>
## 已锁定的深色路由

`/product-category-pnl`、经营日报首页、组合首页、债券分析、股票分析已锁定 Nocturne 深色。`/macro-toolkit`、`/macro-observation`（共用 `macro-toolkit` scope）、`/market-data`、`/risk-overview`、`/risk-tensor`、`/pnl-by-business` 同样保持 Nocturne；旧 IB 浅色、深色岛或钢蓝对照页定位不再适用。不得用历史快照/提交覆盖已确认深色版本。

<a id="ib-light"></a>
## IB 浅色兼容

仅适用于未迁移存量或批准例外。新增使用须记录路由、原因、批准人、批准日期和退出条件；缺记录时按深色默认处理。业务修复/功能增补可沿用存量主题，整页重做/恢复才整页迁移。

| Token | 值 | 用途 |
|---|---|---|
| `--ib-paper` | `#f4f3f0` | 应用底 |
| `--ib-surface` / `--ib-surface-muted` | `#ffffff` / `#f7f6f3` | 卡片 / 次级面 |
| `--ib-hairline` | `#e2e0da` | 细分隔线 |
| `--ib-ink` / `--ib-ink-secondary` / `--ib-ink-muted` | `#16191d` / `#5c6370` / `#8a8f98` | 文字三级 |
| `--ib-accent` | `#14366b` | 主强调 |
| `--ib-up` / `--ib-down` / `--ib-warn` | `#1f7a4d` / `#b42318` / `#b54708` | 语义色 |
| `--ib-rail-*` | `#10161f` 系 + `#c9a85c` 金条 | 深色导航 |
| `--ib-radius` | `2px` | 锐角卡片 |
| `--ib-serif` | Georgia / Noto Serif SC 栈 | 仅标题/刊头 |

浅色 `designTokens` 锚点为 `primary[600] #1850a1`、`info[500] #3b82f6`；`semantic.profit/up #2d8a5e`、`loss/down #ef4444` 不直接用于深色页。同一页同一语义只允许一种色值。

<a id="agent-radius"></a>
## `/agent` 会话圆角例外

2026-09-19 登记任务用户要求的 Gemini 风格独立会话页例外。批准方为该任务用户；依据为用户要求将 `/agent` 改为 Gemini 风格，并要求子代理接手剩余未完成或存疑事项。本记录不追认未记载的历史批准日期或人员。

| 项目 | 范围或取值 |
|---|---|
| 作用域 | 仅独立 `/agent` 的 `[data-moss-theme-scope="agent"]` |
| 输入框 | `--agent-radius-composer: 28px` |
| 气泡、弹层、排队草稿框 | `--agent-radius-bubble: 24px` |
| 卡片 | `--agent-radius-card: 16px` |
| 胶囊控件 | `--agent-radius-pill: 999px` |
| 小控件 | canonical `var(--dh-api-radius)`（8px） |
| 实现依据 | `frontend/src/features/agent/AgentModelComposer.css` |

仅调整圆角，继续沿用 Nocturne 色彩；不适用于业务抽屉、嵌入态 `AgentPanel` 或其它路由，不改变全局 token。独立工作台恢复 canonical 圆角时，移除本例外及页面圆角变量。

<a id="metric-colors"></a>
## 特定指标着色边界

市场利率变动规则适用于国债收益率、DR007、OMO 操作利率、SHIBOR 等市场利率序列：上行警示琥珀，下行/零值中性 muted，符号表示方向，不套盈亏色。组合 DV01/久期变化以及 `/market-data` 资金利率表“偏多/偏空”策略取向色未纳入统一，仍需单独决议。

现金流预测页久期正缺口不代表经营利好，默认中性次级墨色，仅结构偏离需强调时用警示色；负缺口可用跌色，但只表达方向。

<a id="bond-home"></a>
## 债券分析 / 组合工作台首页顺序锁

依次呈现宏观市场条、本日判断（结论文本和轻装饰）、组合 KPI 横带；接着三列曲线与波动/四象策略/收益归因，三列结构/风险/今日焦点，最后双列事件日历/重点券表。未经产品确认不调整顺序。

<a id="daily-home"></a>
## 经营日报首页顺序与动效

2026-09-28 用户要求首页恢复到此前日常入口的版本，以 2026-09-26 已登记构建所附源码为视觉基准。当前入口为 `frontend/src/features/workbench/dashboard-home/DashboardHomePage.tsx`；[概览组件](../frontend/src/features/workbench/dashboard-home/DashboardHomeOptionTwoOverview.tsx)和[页面样式](../frontend/src/features/workbench/dashboard-home/dashboardHomeOptionTwo.module.css)恢复原有区块顺序、字号和留白。首屏依次呈现“今日需处理”、产品分类摘要和“组合变化”，组合变化区先展示归因摘要，再展示债券资产规模、年度损益（不含 FTP）、净息差、DV01 四项指标。

本次回退仅恢复首页呈现。保留后续数据读取、缺值提示、报告日和延迟加载修复，以及既有操作入口；业务口径、筛选、日期和数据链路沿用现有契约。治理待办、数据质量限制和关键缺口仍须可见，无依据不生成可执行判断。

2026-10-02 用户批准审美合规决策 D-D：经营日报首页的业务数字改用比例字体加等宽数字（`fontFamily.tabular` 与 `tabular-nums`），不再使用等宽代码字体；本项只改字体族，保留已确认的字号、留白和区块顺序。依据为 [DESIGN §3](../DESIGN.md#3-typography) 与 [审美合规方案决策记录](frontend-aesthetic-compliance-plan.md#6-决策2026-10-02-用户已批准全部同意)。

2026-09-28 后续首页排版任务沿用上述区块顺序，调整产品摘要与核心指标的字号、标签换行和区块内距；持仓、风险与组合透视按内容确定高度，报告日差异说明允许完整换行。本地源码预览 `5896` 已在 1440、1280、1024 和 390 CSS 像素宽度核对，无页面横向溢出；手机端完整说明保留，核心指标需滚动查看。另核对了 2026-08-17 的部分可用与缺值状态。`5888` 尚未发布本轮改动。

2026-09-24 在源码预览 `127.0.0.1:5894` 核对过的“经营概览”新布局已由本次用户决定撤回，其区块顺序、字号及留白不再作为首页当前样板。后续交付须核对 `5888` 实际加载的版本，避免重新发布已撤回的布局。

首页 hero 环境呼吸光 `dhAmbientCanvasBreathe`（约 6.4s 缓慢透明度呼吸）为唯一无限循环装饰动效豁免，业主于 2026-07-19 确认保留。它不携带数据语义，豁免不扩散；`prefers-reduced-motion` 下必须完全静态或隐藏。

<a id="ledger-pnl"></a>
## 总账损益 `/ledger-pnl`

01 首屏保持经营结论优先，包含当期、环比与资产负债三格；审计五格及判断链默认折叠。账面总览卡治理脚注保留 DOM 可见，可收敛成单行 ellipsis。换肤和降噪不改变此顺序。
