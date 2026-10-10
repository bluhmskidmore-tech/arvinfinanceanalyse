# 市场数据页信息架构重构：PRD 与融合方案

日期：2026-08-27 · 状态：融合定稿（待产品确认后实施）
来源：三模型方案融合——内容归属裁决主要采 Claude 版（基于代码实测的"退役优先"），迁移工程与测试骨架主要采 GPT 版，视觉系统主要采 Gemini 版（按需求方指定"前端多参考 Gemini"）。原始方案与 PRD 存于 `.tmp-agent/market-data-ia/`（`PRD.md`、`proposal-gemini.md`、`proposal-gpt.md`、`proposal-claude.md`），实施前如需细节请回读原文。

---

## 第一部分：问题与目标（PRD 摘要）

`/market-data` 经三轮修复（格式/分轴/清洗名、布局语法统一、密度减层）后仍"乱"，根因是结构性的：

1. 一页承载四个产品：正式利率行情、133 条宏观序列库、Livermore 策略回测、数据治理仪表盘；
2. 治理元数据与业务读数未分层；
3. 密度节奏不均（大卡/长图/短折叠条/全宽表交替）；
4. 视觉演化为四代叠加（CSS 峰值 13618 行 / 996 个 `!important`，现 4697 / 437）。

目标：首屏成为"正式口径驾驶舱"（1–1.5 屏）；每个滚动位置只回答一个问题；治理信息正常态静默、异常态亮灯；密度节奏单一化；为 CSS 单层重写（约 1200 行、`!important` 趋零）铺路。

硬约束：PAGE-MKT-001 契约（mixed-source 身份、`basis`/`formal_use_allowed` 标注、testid 锚点）；治理披露（stale/fallback/proxy/pending 折叠可及、不可删除）；既有 Vitest 50 用例 + Playwright 两条冒烟同步维护；CSS ratchet 只降不升；`designTokens` 与 `--dh-api-*` 主题链；懒加载不回退（9 个 warm-only 查询保持 0 初始请求）。

---

## 第二部分：融合裁决

### 0. 关键事实（Claude 版实测发现，改变方案方向）

`/cross-asset`（跨资产驱动页）**已经原生消费同一批端点**（`getMacroBondLinkageAnalysis`、`getLivermoreSignalConfluence`、`getLivermoreSectorRankSeries`、`getLivermoreCandidateHistory`）并渲染完整读面（`cross-asset-zone-linkage`、Livermore 面板）。`/market-data` 的联动折叠区、02 区 spreads/linkage tab、Livermore 折叠区大部分**不是待迁移的孤儿内容，而是别处已存在的重复内容**。

因此总原则改写为：**能退役就退役，退役不了才迁移，迁移不了才留。**

### 1. IA 结构与内容归属（裁决表）

```
/market-data（不新增顶级路由）
├── Hero：状态条 + 操作行 + KPI 带（formal 片段驱动）
├── 数据状态面板（details，唯一治理入口，吸收右栏证据轨 + 3 个 source-pending 面板摘要）
├── 01 正式利率（表 + 曲线 + 关键利率）
├── 02 资金市场与存单（原 03，DR007/回购/Shibor + NCD proxy 从属位）
├── 03 外汇正式（升级：首屏 3–5 行简表常显，完整列 details 展开）
├── 联动摘要卡（1 行 KPI + 跳转 /cross-asset）        ← 替代 02 区 spreads/linkage tab + 联动折叠区
├── 策略证据卡（1 行摘要 + 跳转 /cross-asset）        ← 替代 Livermore 折叠区
├── 分析上下文摘要（新闻/事件 3 条，延迟加载，详见契约裁决 §6-阶段0）
├── 序列浏览器入口（"稳定 78 · 降级 55 · 按需查看"）
└── 补充数据 Tushare（折叠原位保留，读数后续并入序列浏览器 domain=supplement）

序列浏览器：同路由 `?view=explorer` 全宽子视图（React.lazy 分包）
├── 左目录 280px（主题/链路等级/来源） + 右单表 minmax(0,1fr)
├── URL query：view/domain/theme/tier/q/series（可书签、可前进后退）
└── 单序列钻取：走势 + display_name/原始名/unit/日期/质量/result_meta
```

| # | 现状区块 | 裁决 | 说明 |
| --- | --- | --- | --- |
| 1 | Hero KPI+操作行 | 保留 | KPI 仅取 formal 片段，禁 analytical/proxy 静默回填；blocked 时显式 `EM_DASH`/警示 |
| 2 | 数据状态入口条 | 保留+升级 | 成为全页唯一治理入口，内分"线路状态 / 口径证据 / 数据运维"三组（GPT 结构） |
| 3 | 01 正式利率 | 保留 | 驾驶舱主体；关键利率列表与 KPI 带去重逻辑保留 |
| 4 | 02 宏观深度 tabs | 拆解 | 曲线 tab 序列选择器并入序列浏览器；spreads/linkage tab **退役**（与 /cross-asset 重复），换联动摘要卡 |
| 5 | 03 资金与存单 | 保留 | NCD 明确 Shibor proxy 从属语义，不与真实 NCD 矩阵并列权威 |
| 6 | 外汇正式 | 保留+上提 | 折叠改为简表常显（Gemini/GPT 共识） |
| 7 | 扩展终端 3 表（source-pending） | 降级 | 空态即治理信息：摘要进数据状态面板"未接入"清单，主列留一个入口 chip；国债期货有数时按需展开 |
| 8 | 04 宏观与外汇序列 | 迁移 | 进序列浏览器；不再平铺，初始只渲染当前主题/分页 |
| 9 | Livermore 六件套 | **退役** | 换策略证据卡跳 /cross-asset；market-data 不再挂任何 Livermore 查询 observer；策略评分/优化/回测五个暖查询的 UI 落点（/macro-toolkit）列为 P2 独立任务，本次只退役不落地 |
| 10 | 宏观-债市联动 | **退役** | 换联动摘要卡（保留 PAGE-MKT-001 要求的 report_date、环境/组合摘要、analytical 警示） |
| 11 | Tushare 补充 | 保留原位 | 折叠形态已达标；读数并入序列浏览器为后续项 |

净效果预估：主列"大卡片"从 11 个降到 4 个（01/02 资金/03 外汇/Tushare）+ 4 个单行摘要卡；全展开高度 6850px → 约 3000–3500px；settled DOM 目标 ≤ 现状 60%；初始请求 ≤6 个。

### 2. 导航与路由

- 不动一级 7 页导航、不新增 `PAGE-*` 契约 ID；`RouteRegistry` 不加实页条目。
- 驾驶舱 ↔ 序列浏览器用 **同路由 query（`?view=explorer`）** 切换主列视图：兼得 Claude 版"不动路由注册"与 GPT 版"可书签、可前进后退、独立 chunk（React.lazy）"。数据状态面板支持 `panel=data-status` 深链。
- Hash 兼容：`#market-data-macro-series` → 打开序列浏览器；`#market-data-linkage-correlation` → 跳 `/cross-asset` 对应锚点（阶段 0 先核实目标锚点存在）；`#market-data-term-structure`、`#market-data-liquidity-deck` 不变。兼容层保留一个发布周期，凭零使用证据删除。
- 职责边界一句话：market-overview=聚合入口；market-data=可审计行情值+序列浏览+来源状态；cross-asset=宏观→债券/组合的传导解释（承接联动+Livermore 读面，现状已有）；macro-observation=只读宏观信号；macro-toolkit=工具/脚本/策略运行结果（Livermore 评分回测 UI 的 P2 候选落点）。

### 3. 组件收编（目标原语六件）

1. 一个 L1 区头：`PageSectionLead`（退役 `market-data-formal-rates-head` 手写结构、supplementary 头、extended label 头）；
2. 一个卡壳：`MarketDataSeriesCategoryCard` 血缘重命名为 `MarketDataPanel`，业务/治理仅以背景 token 区分；
3. 一个主题面板：`MarketDataMacroThemeCard` 泛化为 `MarketDataThemePanel`，FX 组经统一 view model 映射（删 `MarketDataFxThemeCard`）；
4. 一种折叠：原生 `details/summary`，新增 page-local `MarketDataDisclosure`（`persistent`/`deferred` 两种挂载策略：契约锚点常驻 vs 首开挂载）；market-data 域内 antd Collapse 全退役；
5. 一种表格：统一列宽/行高规格（见 §4），退役"原生 table 与 antd Table 双皮肤并存"；
6. 一种图表壳：`MarketDataChartShell` + Nocturne 主题，色值取 `nocturneTokens` 不读 CSS 变量。

最终删除清单（GPT 版 §3.7，阶段 5 执行）：`MarketDataMacroDepthTabs`、`MarketDataSupplementarySeriesSection`、`MarketDataFxThemeCard`、`MarketDataLivermoreSection`、`MarketDataLinkageSection`（cross-asset 接稳后）、`MARKET_DATA_SHOW_*` 开关、9 个 warm-only 查询声明、hashchange 手工滚动、beforeprint/Ctrl+F 强制展开 hack、孤儿查询 `macroToolkitAnalysisQuery`（Claude 版实测：定义后无消费方）。

### 4. 视觉系统（Gemini 版为主）

字号/字重三档：

| 档 | 规格 | 用途 |
| --- | --- | --- |
| L1 | 15px / 700 | 区块头（现状 800 统一降 700，与 L2 单级差） |
| L2 | 13px / 600 | 卡头、表头 |
| L3 | 12px / 400（数据可 600） | 表格正文、说明、元数据；数字一律 `tabular-nums` |

- 行高：表头 32px、数据行 32px（紧凑型统一，消除表间密度跳变）；cell padding 横 8 竖 4。
- 间距：4px 基数，语义 token `s[1]=4 / s[2]=8 / s[3]=12 / s[4]=16`；区块间距 16px、卡内 12px（映射 `designTokens.space`，禁止散值）。
- 卡壳两层：L1 主 panel（panel 底 + 1px 边框 + 8px 圆角、无阴影）、L2 inset（panel-2 底或分隔线）；禁止第三层卡套卡；抽屉/弹窗允许阴影以区分空间层。
- 色彩：语义色只给状态与涨跌（利率上行琥珀、下行中性，沿用 DESIGN 现行结论；stale/fallback/proxy 琥珀；error/blocked 红；绿仅表"通过/可用"）；强调蓝紫只用于导航/链接/主操作；装饰性背景色趋零。
- sparkline 配额：01 区核心表保留图形 sparkline（高 24px），次要表文本化（`+3bp` 式）；驾驶舱可见 sparkline ≤8、ECharts canvas 首屏 ≤2；少于 2 个有效点不画线。
- 1600px：非对称栅格——正式利率 8 列，资金+外汇右侧 4 列纵排；1280px：不缩字号，按"供应商→观测日→周变动"顺序隐藏低优先列，表格允许横滚；KPI 保持覆盖三域。
- CSS 预算防转移（GPT 版）：`MarketDataPageCssBudget.test.ts` 改为汇总 `features/market-data/**/*.css` 生产样式；迁移首日总量不得超过现值；每删除阶段下调至实测值；终态目标总量 ≤1500 行、`!important` ≤20（趋零方向），剩余逐条登记退出条件。

### 5. 治理分层（Claude 版 L0–L3 矩阵为骨架）

| 层 | 触发 | 首屏 | 卡内 | 数据状态面板 | 色 |
| --- | --- | --- | --- | --- | --- |
| L0 静默 | formal/analytical 且 quality ok 且无降级 | 无 | 无角标（面板边界一次口径词） | 计入桶计数 | 无 |
| L1 结构性披露 | proxy（NCD）、source-pending（设计使然的长期态） | 不进首屏 | 一行小字说明，不告警 | "代理/未接入"清单 | 灰/灰蓝 |
| L2 运行时异常 | stale / fallback / vendor_unavailable / error | 入口条计数亮灯（"延迟 N / 不可用 N"仅 >0 时出现） | 卡头黄/红角标 + 诊断展开 | 置顶"下一步动作" | 琥珀/红 |
| L3 契约强制首屏 | `basis=formal` 且 `formal_use_allowed=false` | Hero 结论行必须可见（契约 H.3） | — | 同步计入 | 红 |

补充规则（GPT 版）：同一事实全页最多出现两处（首屏或受影响区块一次 + 抽屉一次）；抽屉内分"线路状态 / 口径证据 / 数据运维"三组；刷新按钮文案改为"刷新 Choice 宏观（回填 30 天）"，刷新只 refetch 活跃视图、非活跃 query 仅 invalidate。开放问题：若 blocked 属长期口径限制而非临时故障，应评估修订契约 H.3 将其降为 L1（超出本次范围，记录待产品裁决）。

### 6. 迁移步骤（六阶段，每阶段独立 PR、可单独回滚）

| 阶段 | 内容 | 核心验收 | 契约/测试同步 |
| --- | --- | --- | --- |
| 0（2–3 天） | 基线快照（截图/请求数/DOM/高度/锚点全集）+ 契约裁决：GPT 版四项漂移（`market-data-page-title`/`filter-strip`/`active-filter-summary` 锚点缺失、`data-layout-rev` 版本不一致、NewsAndCalendar 契约有实现无、Livermore/联动跨页归属签字）+ Claude 版两项核实（cross-asset 的 report_date 管理是否与本页一致、`cross-asset-zone-linkage` 锚点可跳转）+ 死锚点 `market-data-evidence-gate` 处置 | 每个锚点有"保留/迁移/修订"三选一记录；跨页归属经确认 | 仅文档，现有测试全绿为前提 |
| 1（≤1 周） | 治理面板整合：右栏证据轨 + 3 个 source-pending 摘要并入数据状态面板（三组结构）；L0–L3 矩阵落地 | 治理锚点收起态 DOM 可及；正常态主列无重复"已就绪" | 右栏/扩展终端摘要断言更新 |
| 2（≤1 周） | 退役换卡：spreads/linkage tab + 联动折叠区 → 联动摘要卡；Livermore 折叠区 → 策略证据卡；跨页跳转打通；市场数据侧相关查询 observer 移除 | 本页初始与刷新均不再调 Livermore/联动明细端点；摘要卡日期标注与跳转正确 | 联动/Livermore 用例改写为"摘要卡+跳转"；细节断言确认 cross-asset 侧已覆盖，缺则补 |
| 3（≤1 周） | 序列浏览器：`?view=explorer` 全宽子视图（React.lazy），目录+单表+单序列钻取；04 区从主列退场；hash 兼容适配 | 133 条可搜索可达但不全量挂 DOM；深链 `series=<id>` 可恢复；根视图不再加载 macro/FX 主题 chunk | 两个 deep-link 用例改断言浏览器打开态；Playwright workflow 冒烟改路径 |
| 4（≤1 周） | 驾驶舱视觉独裁：外汇正式上提简表；非对称栅格；表格/字号/卡壳/折叠按 §3§4 收编；恢复阶段 0 裁决的缺失锚点 | 1600 下三域 1–1.5 屏；初始请求 ≤6；1280 不缩字号 | `data-layout-rev` 换新版本并同 PR 修订 PAGE-MKT-001；terminal 冒烟切新首屏 |
| 5（≤1 周） | 删旧代：§3 删除清单执行；CSS 预算改域汇总并下调；历史文档（`BASELINE_AUDIT.md`、`REQUIREMENTS_SNAPSHOT.md`）标注 superseded；契约文档收口 | 全仓搜不到退役组件引用；CSS 总量创新低；`core_finance` 零改动 | 删除仅绑旧布局的断言；跑 debt/style/encoding 全审计 |

进入阶段 5 的决策门（GPT 版收紧）：阶段 2–4 稳定一个发布周期、无 P0/P1、契约修订已合并、旧 hash 兼容测试全绿、请求/DOM/CSS 均不高于基线。

### 7. 测试影响（GPT 版清单为主）

必保语义断言（不可弱化）：formal/analytical/proxy/pending 不混写；blocked 文案精确；缺数据只显 emptyReason 不补 demo；NCD proxy 语义；requested/resolved/as_of/fallback/generated 时间语义；derived spreads 不前端重算；stale/fallback/quality 可见；筛选不改 API 参数；刷新轮询 terminal/partial/degraded/failed 分支；`refetchOnWindowFocus:false`；图表分轴与 Nocturne 色；`EM_DASH`。

重写类别：整页包含性断言 → 按视图拆分；`.ant-collapse-header` 交互 → 原生 summary；FX 默认折叠 → 简表常显；Livermore/联动细节 → 摘要卡+跳转（细节归 cross-asset 侧）；print/Ctrl+F 强制物化 → 删除；hashchange 滚动 → query/hash 适配断言。

新增：查询树预算（初始 ≤6、warm-only 恒 0、浏览器按 domain 启用、inactive 仅 invalidate）；治理矩阵各层可见性；浏览器筛选/深链/前进后退；视觉结构（单一卡壳/区头/折叠家族）。

Playwright：`market-data-terminal-smoke`（新首屏三域 1.5 屏内、退役内容不在 DOM 未发请求、抽屉锚点、键盘展开扩展行情）与 `market-data-workflow-smoke`（筛选进 URL 刷新恢复、浏览器 domain 切换按需加载、旧 hash 跳转、两张摘要卡跨页跳转）重写；dark-theme/a11y 冒烟补 1280、details 键盘、抽屉焦点。

### 8. 风险与开放问题（三家合并，按优先级）

1. **锚点与内容跨结构后契约不同步**（GPT，概率高/影响高）：阶段 0 锚点迁移表 + 每次移动与契约测试同 PR + 目标先落再删来源。
2. **跨页 report_date 口径不一致**（Claude，最可能引发信任问题）：跳转 cross-asset 后若该页 selector 留在历史日期，用户看到与摘要卡不同的数字。阶段 0 核实两页日期管理，摘要卡显式标注日期，跳转携带 `date` query。
3. **formal-first 后首屏"看起来没数"**（GPT）：正式片段空/blocked 时接受显式空态，禁止 analytical 回填；"高置信"晋升标准待产品定义，未定义前不晋升。
4. **序列浏览器测试工作量被低估**（Claude）：Drawer/视图切换引入打开时机、焦点管理等新维度，阶段 3 排期前用原型复核。
5. **CSS 预算转移到新文件**（GPT）：ratchet 改域汇总，首日不许上涨。
6. **Livermore P2 落点可能把乱转移到 macro-toolkit**（Claude）：本次只退役不落地，P2 须与该页 owner 协调。
7. **1280 下三域进不了首屏**（GPT/Gemini）：KPI 恒覆盖三域，详情允许 1.5 屏，减列+横滚不缩字号。
8. 开放问题：高置信读数定义；Livermore 最终 owner（macro-toolkit vs stock-analysis）；blocked 长期态是否修订 H.3；`/macro-analysis` 别名去向（GPT 建议语义迁到浏览器视图，需使用证据）；NewsAndCalendar 契约缺口按阶段 0 裁决（补紧凑摘要 vs 修订契约）。

---

## 附：对正式金融路径影响

无。全部为前端 IA/视觉/查询编排与契约文档改动，`backend/app/core_finance/` 不涉及。
