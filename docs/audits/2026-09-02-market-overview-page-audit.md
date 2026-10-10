# 审计报告：`/market-overview` 市场总览页及其 6 个子页面

- 状态：**只读审计，未修改任何生产代码、数据或契约**
- 审计日期：2026-09-02
- 环境：前端 `http://127.0.0.1:5888`（Vite dev，real 数据源）／后端 `http://127.0.0.1:7888`（`/health` 200）
- 审计范围：
  - **主页面** `PAGE-MARKET-HOME-001` `/market-overview`：`MarketHomePage` → `MarketHomeLayout` → `MarketOverviewDenseFirstScreen` / `MarketFinancialChartsWorkbench` / `MarketBackendDataWorkbench`，以及 `useMarketHomeQueries` 的 6 条读链路与 `moduleHomeModel` / `marketOverviewDenseModel` / `marketDeskIntelModel` / `marketFinancialChartsModel` 的前端派生计算（§1–§6）
  - **子页面** 市场工作台子页导航（`getMarketWorkbenchNav()`）下的 6 条路由：`/market-data`、`/cross-asset`、`/macro-observation`、`/macro-toolkit`、`/stock-analysis`、`/news-events`，附带 `/stock-analysis/portfolio`（§7）
  - **跨页共享层**：`WorkbenchShell` 顶部行情条与 `/ui/macro/choice-series/latest` 的多处重复读（§7.2）
- 证据留存：`.tmp-agent/market-overview-audit/`
  - 主页面浏览器取证：`report.json`、`report2.json`、`shots/`（1920 / 1440 全页 / 1280 / 1024 / 390 及展开态）
  - 子页面浏览器取证：`subpages/subpages.json`、`subpages/timing.json`、`subpages/shots/`
  - 取证脚本（Playwright，需从 `frontend/` 目录执行以解析 `@playwright/test`）：`audit.mjs`、`audit2.mjs`、`audit3.mjs`、`subpages.mjs`、`timing.mjs`、`reload.mjs`、`spotcheck.mjs`
  - 后端取证脚本（从仓库根执行）：`probe_market_overview.py`、`payload_weight.py`、`detail_cost.py`、`meta.py`、`slow_endpoints.py`、`contention.py`、`dup_reads.py`、`summarize_subpages.py`

**一句话结论**：这一组页面的工程底子是健康的（lint / typecheck 干净，主页面门禁 175/176、子页面门禁 493/494 通过，7 条路由 FCP 均在 168–188 ms，无一路由横向溢出或触发错误边界），但**主页面首屏的核心判断位在真实数据下长期处于「暂停判断」，且它把后端已经给出的、更具体的诊断替换成了更笼统的说法——而同一屏下方 40px 处的「焦点解读」卡片又原样打印了那段被声称"不展示"的摘要**。除此之外，主页面有 4 个可复现的功能缺陷、1.85 MB 需前端解析的首屏 JSON（约 1.1 MB 从不渲染）、以及一批本应由后端契约承担、目前靠前端正则猜测的指标身份解析；子页面侧另有 2 个 P0（`/news-events` 移动端 176,515 px 高、`/stock-analysis` 治理门禁红灯）和一条影响全组的跨页重复读。

全部发现：主页面 25 条（F1–F25），子页面 11 条（S1–S11）。

---

## 0. 先说结论：分级清单

| 级别 | 编号 | 问题 | 证据位置 |
| --- | --- | --- | --- |
| P0 | F1 | 首屏判断位自相矛盾：hero 声称"不展示来源结论摘要"，焦点解读卡原样展示该摘要 | §2.1 |
| P0 | F2 | 行情带数值与自身 tooltip 精度不一致（1.6988% vs 1.7%） | §2.2 |
| P0 | F3 | USD/CNY 变动渲染为 `-0CNY/USD` | §2.2 |
| P0 | F4 | 03 区「金融图表 · 12 张」默认态渲染 0 张图；`最新一期跨资产变动` 全页重复绘制两次 | §2.3 |
| P0 | F5 | 03 区「重点」模式下 6 个「收起/展开」按钮全部失效 | §2.4 |
| P1 | F6 | 首屏解析 1.85 MB JSON（传输 241 KB），其中约 1.1 MB 页面从不渲染 | §3.1 |
| P1 | F7 | `history_limit=430` 拉取的 221 点 Crisis 历史在本路由无任何消费方 | §3.2 |
| P1 | F8 | `detail=full` 与 `detail=core` 返回同样 23 个顶层键，体积 3× | §3.2 |
| P1 | F9 | 宏观分析冷缓存 3.2–3.3 s 阻塞首屏判断位 | §3.3 |
| P1 | F10 | `strategy_summaries` 被两条读链路重复返回且 `as_of_date` 不一致（08-28 / 08-24），前端合并成一个对象 | §3.4 |
| P1 | F11 | 新闻 `compare` 分析块 48 KB 每次拉取，除 04 区原始转储外无任何呈现 | §3.5 |
| P1 | F12 | 头部指标身份由前端正则在 211 条序列上匹配，无 MTR 绑定、无血缘 | §4.1 |
| P1 | F13 | 事件热力图按 `received_at` 的 UTC 小时分桶，坐标轴无时区标注 | §4.2 |
| P1 | F14 | 工具栏声明单一「行情 2026-08-28」，行情带实际横跨 08-25 ~ 08-28 | §4.3 |
| P1 | F15 | 新闻样本已停更 6 天，首屏不披露 | §4.3 |
| P2 | F16–F25 | 搜索名不副实、106 处仅 title 可见的信息、04 区单页 25k DOM 节点等 | §5 |

---

## 1. 页面结构与读链路（审计已确认的事实）

路由 `/market-overview` → `routes.tsx:178` → `MarketHomePage`，页根 `data-moss-theme-scope="market-overview"`，深色 Nocturne scope 由 `ThemedRouteBoundary` 独占。

四个章节：

| 章节 | 组件 | 锚点 |
| --- | --- | --- |
| 01 分析观察 | `MarketOverviewDenseFirstScreen` | `#market-overview-judgment` |
| 02 市场证据 | 同上 | `#market-overview-evidence` |
| 03 金融图表 12 | `MarketFinancialChartsWorkbench` | `#market-financial-charts-all` |
| 04 数据核验 6 | `MarketBackendDataWorkbench` | `#market-backend-data-all` |

`useMarketHomeQueries` 并发发起 6 条读，全部 `retry: false` / `staleTime: 5min`：

| query | 端点 | 实测 |
| --- | --- | --- |
| `choiceLatest` | `/ui/macro/choice-series/latest` | 200，133 条序列，473 KB |
| `marketRates` | `/ui/market-data/rates` | 200，78 条序列，306 KB |
| `marketCatalog` | `/ui/market-data/catalog` | 200，78 条序列，40 KB |
| `macroToolkitAnalysis` | `/ui/macro/toolkit/analysis?detail=full&history_limit=430` | 200，23 个顶层键，156 KB，**冷缓存 3.3 s** |
| `macroToolkitStrategySummaries` | `/ui/macro/toolkit/analysis/strategy-summaries` | 200，55 KB |
| `newsEvents` | `/ui/news/choice-events/latest?limit=500&offset=0&include_payload_json=false` | 200，1,075 条中取 500，816 KB |

04 区的新闻页另起一条 `limit=50 / include_payload_json=true` 的分页读，`enabled: activeKey === "news"`，惰性加载生效——这一点做得对，未与共享的 500 条样本互相污染。

---

## 2. P0 缺陷

### 2.1 F1 — 首屏判断位自相矛盾，且吞掉了后端更具体的诊断

后端 `result_meta.quality_flag = "warning"`，根因是刷新回执卡死：

```
refresh_receipt.status   = "blocked"
refresh_receipt.ready    = false
refresh_receipt.run_status = "running"
refresh_receipt.generated_at = 2026-08-27T10:50:15Z   ← 已 6 天
missing_fields = [receipt.status, receipt.exit_code,
                  receipt.result.steps.choice_policy_rate_7d, ... 共 17 项]
```

后端据此给出的 `conclusion` 本身就是一条安全的「不下结论」：

- `stance = "数据不足"`，`tone = "missing"`
- `summary = "最近一次定时数据刷新未通过完整性校验，当前指标仅可作未验证观察证据。"`
- `recommended_action = "请完成后端数据刷新并通过回执校验，再形成分析性判断。"`

前端 `buildMacroObservationGate` 把任何 `quality_flag !== "ok"` 一律判为 blocked（`MarketOverviewDenseFirstScreen.tsx:206`），于是 hero 渲染为：

> 暂停形成今日判断
> 因**数据质量预警**，本页**不展示来源结论摘要**。请先核验来源证据，再形成判断。

**问题有两层。**

第一层：被替换掉的原文比替换后的文案信息量更大。后端说清了「哪一步失败（刷新回执完整性校验）」和「怎么恢复（跑完刷新并通过回执校验）」；前端替换成了「数据质量预警」这种不可执行的表述。gate 的设计目的是防止把观察性结论误读为正式结论，但 `tone: "missing"` 的结论恰恰**不是**结论，压制它只损失信息、不降低风险。

第二层，也是更硬的：**同一屏往下 40px，「焦点解读」的第 4 张卡原样打印了那段"不展示"的摘要**——

> 宏观工具｜数据不足：最近一次定时宏观刷新未通过完整性校验，当前指标仅作未验证观察证据。｜先完成宏观数据刷新并通过回执校验，再形成方向性判断。（工具口径，非正式经营结论）

同一屏内一处声明「不展示」、另一处展示同一内容，是可直接观察到的自相矛盾。这条路径来自 `view.briefings`（`moduleHomeModel`），不经过 `macroObservationGate`，两条渲染链没有共享同一个 gate 判定。

证据：`.tmp-agent/market-overview-audit/report.json → dom.observation`；`audit3.mjs → focus[3]`；`shots/mo-1920.png`。

**2026-09-02 review 补充（上游根因）**：回执之所以六天卡在 `running`，是因为日更调度器 `MOSS-DailyDataRefresh` 自 08-28 起每天在第一步就退出——`scripts/scheduling/daily_data_refresh.ps1` 在 `$ErrorActionPreference = "Stop"` 下用 `2>&1` 捕获子进程输出，PowerShell 5.1 会把子进程的第一行 stderr 当成终止错误；`choice_stock_daily_refresh.py:267` 撞 DuckDB 写锁时正好向 stderr 打印重试提示。机制已用五行脚本复现，`scripts/scheduling/logs/20260828.log` 起每日日志均为 499 字节且截断在 `START` 行。完整链条与修法见 `docs/plans/2026-09-02-market-overview-module-compute-plan.md` §1 R1。这意味着 F1 的前端矛盾要修，但"暂停判断"本身会在调度器恢复后自行消失。

### 2.2 F2 / F3 — 行情带的数值渲染缺陷

`buildDenseTapeMetrics` 用 `compactNumber`（<10 取 4 位小数）生成可见值，`title` 走 `formatChoiceMacroValue`（另一套精度）。同一个读数在格子里和它自己的悬浮说明里不一致：

| 格子可见 | 自身 title |
| --- | --- |
| `10Y国债 1.6988%` | `中债国债到期收益率:10年 · 1.7% · 2026-08-27` |
| `USD/CNY 6.7811 CNY/USD` | `中间价:美元兑人民币 · 6.78 CNY/USD · 2026-08-28` |
| `铜主力 108,900 CNY/t` | `铜主力期货收盘价 · 108900 CNY/t · 2026-08-28` |

用户拿 tooltip 复核可见值时会看到两个数。

同一区域另有三处渲染问题：

- **`-0CNY/USD`**：USD/CNY 的变动格渲染出负零。`normalizeTapeTone` 只把色调改成中性，文本仍是 `-0`。
- **`沪深300 4,590.79 index 0.85%`**：`index` 作为英文单位直接透出到中文标签旁；且变动 `0.85%` 没有其他格子都有的 `+/-` 符号——因为 CSI300 走 `changePoint` 分支（`formatChoiceMacroValue`）而非 `formatChoiceMacroDelta`。
- ~~`USD/CNY` 标的是「美元兑人民币」，单位却是 `CNY/USD`~~ **（2026-09-02 review 撤回）**：`6.7811` 的单位 `CNY/USD` 意为"每 1 美元多少人民币"，量纲正确；报价对名 `USD/CNY` 与单位 `CNY/USD` 本就互为倒写。仅剩展示冗余（格子里 `USD/CNY 6.7811 CNY/USD`），不是数据问题。

### 2.3 F4 — 03 区默认渲染 0 张图，且有一张图全页画了两次

`MarketFinancialChartsWorkbench` 默认 `expandedKeys = new Set([SECTION_KEYS[0]])`，即只展开 `rates` 组。而 `rates` 组的两张图（`yield-curve`、`key-rate-trend`）正好都在 `DENSE_FIRST_SCREEN_CHART_KEYS` 里，被 `ChartReferenceCard` 替换成了「该图已在上方市场证据区渲染」的指路卡。

实测（`report2.json → chartRender`）：

```
beforeExpand:    canvas = 0
afterExpandAll:  canvas = 10
perSection: rates 0 / cross 2 / macro 2 / strategy 2 / news 2 / coverage 2
referenceNotices: 2
```

即：标题写「金融图表 · 12 张」，**打开页面看到 0 张**，手动展开全部 5 个折叠组后是 10 张 + 2 张指路卡。

同时，`selectedDenseCharts` 在 02 区选的是 `rates[0]`、`rates[1]`、`cross[1]`，而去重集合 `DENSE_FIRST_SCREEN_CHART_KEYS` 只登记了前两张。结果 `cross[1]`（`最新一期跨资产变动`）在 02 区和 03 区各画一遍。重复标题实测：

```
duplicateHeadings: [国债与国开期限结构 ×2, 关键利率近 20 期走势 ×2, 最新一期跨资产变动 ×2]
```

前两组是「实图 + 指路卡」（预期内），第三组是**两张真画布**（非预期）。去重集合与选图列表没有同一个来源，改一处不会同步另一处。

### 2.4 F5 — 「重点」模式下 6 个展开/收起按钮全部失效

`MarketFinancialChartsWorkbench.tsx:429`：

```ts
const isExpanded = viewMode === "focus" || expandedKeys.has(section.key);
```

进入「重点」模式后 `isExpanded` 恒为 true，6 个按钮标签全部锁死在「收起」；CSS 又把非 active 分组整体隐藏，于是 5 个按钮不可见、不可点。对唯一可见的那个点击后实测无任何变化：

```
focusActiveKey: "rates"
beforeToggle: 332.78px  →  afterToggle: 332.78px
beforeLabel: "收起"     →  afterLabel: "收起"
```

`handleSectionToggle` 仍在改 `expandedKeys` state，只是被 `viewMode === "focus"` 完全覆盖——一个会触发重渲染但没有可观察效果的死控件。

---

## 3. P1：数据负载与读链路

### 3.1 F6 — 首屏 1.85 MB 解压后 JSON，约 1.1 MB 从不渲染

先厘清两个不同的量，避免误读：**传输量**（gzip 后，走带宽）与**解压后 JSON 量**（走解析、内存与前端聚合）。

- 传输量：浏览器 Resource Timing 实测首屏 6 条读合计 **241 KB**（`encodedBodySize`）。带宽不是瓶颈。
- 解压后：`payload_weight.py` 实测合计 **1.85 MB**。这才是需要 JS 解析、驻留内存并被前端逐条聚合的量。

字段级权重（解压后）：

| 端点 | 解压后 | 传输 | 最大项 |
| --- | --- | --- | --- |
| `newsEvents` | 816 KB | 160 KB | `events` 781 KB、`compare` 48 KB |
| `choiceLatest` | 473 KB | 26 KB | `series` 493 KB（含 `recent_points`） |
| `marketRates` | 306 KB | 17 KB | `series` 319 KB |
| `macroToolkitAnalysis` | 156 KB | 29 KB | `capability_results` 83 KB、`model_readiness` 18 KB、`capabilities` 14 KB |
| `strategySummaries` | 55 KB | 11 KB | `shadow_portfolio_report` 34 KB |
| `marketCatalog` | 40 KB | 4 KB | — |
| **合计** | **1.85 MB** | **241 KB** | |

首屏对这 1.85 MB 的实际消费：500 条新闻 → 7 主题 × 12 个两小时桶的热力图 + 3 条最新事件 + 2 张分布图；211 条序列 → 8 个行情格 + 4 张图。其余大部分只在 04 区「数据核验」被原样转储。

所以本条的实质不是带宽，而是：**前端在主线程上解析并遍历约 1.85 MB 的 JSON，只为产出一个 7×12 的计数矩阵和 8 个数字**。另外 `choiceLatest.result_meta` 单独占 6.3 KB，几乎全是拼接的 `source_version` / `vendor_version` 哈希串。

首屏读的时间线是健康的：6 条读在 767–774 ms 之间同时发出，最后一条在 **1,114 ms** 完成，FCP 184 ms。

### 3.2 F7 / F8 — `history_limit=430` 与 `detail=full` 都在为没人看的数据付费

`MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT = 430` 的唯一去向是 `buildMarketCrisisExplain` → `crisisHistoryDelta`，而后者只用了首尾两点：

```84:88:frontend/src/features/workbench/module-home/marketDeskIntelModel.ts
  const first = history[0];
  const last = history[history.length - 1];
  const scoreDelta =
    first && last && Number.isFinite(first.crisisScore) && Number.isFinite(last.crisisScore)
```

实际返回 221 个点、15 KB。而 `scoreDelta` / `percentileDelta` / `scoreHistory` 三者在本路由**没有任何渲染方**：唯一消费 `scoreHistory` 的组件是 `MarketCrossAssetGapBlock`，全仓 grep 显示它只被自己的测试引用，不在 `MarketHomeLayout` 的渲染树里。首屏 Crisis 位只显示 `crisisScore.toFixed(2)` 和 `regime`。

`detail_cost.py` 实测 `detail=core` 与 `detail=full` 返回**完全相同的 23 个顶层键**，只有体积差：

```
detail=core                       51,188 B
detail=full&history_limit=430    156,002 B
```

也就是说 `full` 没有多给任何一个业务分区，只是把各分区里的历史铺开。

### 3.3 F9 — 宏观分析冷缓存 3.2–3.3 s，且它卡在首屏判断位上

同一 URL 连续请求实测：

```
detail=full&history_limit=430   → 3,321 ms   (首次，页面加载路径)
detail=full&history_limit=430   →   137 ms   (立即重放)
detail=full&history_limit=60    → 3,267 ms   (换参数 → 重新计算)
detail=full&history_limit=430   →   125 ms
```

结论：后端按 `(detail, history_limit)` 组合做记忆化，未命中时重算约 3.2 s。这条读同时供给 hero 的 stance / summary / action、口径面板、指标变动表和 03 区两张图，所以每次冷启动首屏判断位都要空 3 秒以上。其余 5 条读都在 600 ms 内返回。

审计过程中还观察到一次后端瞬时拒连（`WinError 10061`），几秒后自行恢复，未能复现，仅作记录。

### 3.4 F10 — `strategy_summaries` 双份返回，`as_of_date` 不一致

两条读都返回同一组 4 个策略（`moving_average` / `mean_reversion_momentum` / `multi_factor_selection` / `low_crowding_regime_multifactor`，各 9.8 KB），但 `result_meta.as_of_date` 不同：

- `/ui/macro/toolkit/analysis` → `2026-08-28`
- `/ui/macro/toolkit/analysis/strategy-summaries` → `2026-08-24`

前端 `mergeMacroToolkitAnalysis` 把两份合成一个对象：

```1974:1981:frontend/src/features/workbench/module-home/moduleHomeModel.ts
  return {
    ...analysis,
    strategy_summaries: analysis.strategy_summaries.length
      ? analysis.strategy_summaries
      : strategyPayload.strategy_summaries,
    shadow_portfolio_report:
      analysis.shadow_portfolio_report ?? strategyPayload.shadow_portfolio_report,
  };
```

于是合成对象里 `strategy_summaries` 来自 08-28 的读，`shadow_portfolio_report`（analysis 侧没有这个键）来自 08-24 的读，而 `buildMacroToolkitStrategyRows` 给所有策略行统一盖 `analysis.as_of_date`（08-28）。当 analysis 侧的数组为空走 fallback 时，08-24 的数据会被盖上 08-28 的日期戳——这是一条会静默产生错误日期标注的路径。

### 3.5 F11 — 48 KB 的 `compare` 分析每次拉取、首屏零呈现

`newsEvents` 返回 `compare = { same_direction: 1, conflicting: 0, review_needed: 5, candidate_scenarios: 5 }`，共 48 KB。实测 01/02 区文本中不含「事件比较 / 同向 / 冲突 / 待复核」任一关键词（`report2.json → compareUsage.firstScreenMentionsCompare: false`）。这是后端已经算好的冲突/待复核判断，页面付了带宽却没有使用它——而首屏恰恰有一个「P0 - P2 核验队列」面板在做类似的事，且当前只产出 P1/P2 三条。

---

## 4. P1：前端在做后端该做的计算

### 4.1 F12 — 头部指标身份靠正则匹配，无契约、无血缘

`buildDenseTapeMetrics` 在合并后的 211 条序列上用正则挑出 8 个头条指标：

```437:468:frontend/src/features/workbench/module-home/marketOverviewDenseModel.ts
  const tenYear = merged.find(isChinaTenYearPoint);
  const dr007 = findPoint(merged, (text) => /dr\s*0?07/i.test(text));
  const csiClose = findPoint(
    latestPoints,
    (text) => /沪深\s*300|csi\s*300|hs300/i.test(text) && /收盘|close/i.test(text),
  );
```

匹配文本是 `series_id + series_name` 的小写拼接。`isChinaTenYearPoint` 还要再叠一层「含 10Y 提示 且 不含境外主权提示 且（`^cn[._-]` 或含中国主权提示）」的启发式。`buildDenseLedgerRows`（12 条优先级正则）和 `buildDenseMacroPulseRows`（CPI/PPI/PMI/社融 4 条正则 + 兜底取前 N 条）是同一套做法。

风险是具体的：供应方改一次 `series_name`，首屏「10Y国债」就可能静默换成另一条序列，而页面契约 §E 明确写着「None. This module home has no standalone `MTR-*` binding」——没有指标绑定意味着这层解析不在任何血缘或金标准的覆盖范围内，改动不会有任何测试变红。

### 4.2 F13 — 事件热力图按 UTC 小时分桶，坐标轴无时区标注

`bucketableNewsTime` 直接从 `received_at` 字符串正则取小时位：

```283:289:frontend/src/features/workbench/module-home/marketOverviewDenseModel.ts
  const match = /^(\d{4})-(\d{2})-(\d{2})T?(\d{2})/.exec(receivedAt);
```

后端返回的是带偏移量的 UTC 时间：

```
2026-08-27T12:29:46+00:00 | tushare.news.sina
```

于是热力图横轴 `00 02 04 … 22` 是 UTC 小时，脚注只写「按接收时间两小时分桶」，没有时区标注。一条北京时间 20:29 收到的新闻会落在 `12:00` 桶里。单元格 tooltip 写的是 `received_at 12:00–13:59`，就字段而言自洽，但对中国市场的读者，无标注的小时轴默认会被读成北京时间——「事件流入密度」的峰值位置因此整体错位 8 小时。

**2026-09-02 review 补充**：对 `choice_news_event` 全表统计（`.tmp-agent/market-overview-audit/news_tz.py`），1,075 行全部为 `+00:00`（列为 `TIMESTAMPTZ`，DuckDB 按 UTC 序列化，时刻本身正确），但其中 **701 行（65%）是日粒度记录**（`tushare_research` 669 行、`tushare_cctv` 32 行，时间戳全为 `T00:00:00`）。它们被现有算法整体塞进 `00` 桶——热力图最密的那一格是数据结构的产物，不是接收密度。这比时区错位更严重：修时区只是把假峰值挪到 `08` 桶。

### 4.3 F14 / F15 — 日期口径

- 工具栏声明「行情 **2026-08-28** ／ 正式序列 **2026-08-28**」，但行情带 8 个格子各自的日期是 `08-25`（Brent）、`08-26`（沪深300）、`08-27`（10Y国债、7D逆回购）、`08-28`（DR007、SHIBOR 3M、USD/CNY、铜主力）。逐格日期是对的，页头的单一日期高估了其中一半格子的新鲜度。
- 新闻样本最新事件是 `2026-08-27`，而信封 `as_of_date = 2026-09-02`（后端按查询日生成的 `received_at` 过滤截止）。03 区已经用事件 `received_at` 最大值披露了真实样本日（代码注释明确说明了这个设计，做得对），但**首屏和工具栏没有任何地方提示新闻已停更 6 天**。

---

## 5. P2：交互、可访问性与规模

| 编号 | 问题 | 实测 |
| --- | --- | --- |
| F16 | 搜索名不副实：placeholder 承诺「指标 / 图表 / 事件 / 代码」，实际只有 10 张卡参与，且只把不匹配项降到 `opacity: 0.34`，不过滤、不计数、无空结果态；03/04 区完全不响应 | 输入无效词后 `dimmed 10 / matched 0 / hidden 0 / totalSearchable 10` |
| F17 | 106 处非交互元素的信息只存在于 `title` 属性中（键盘与触屏不可达），包括行情带全部 8 格的序列全名与日期、信号卡的历史分位等 | `titleOnlyCount: 106` |
| F18 | axe 唯一违规：`.chartReadingGuide > span` 对比度不足（serious） | `wcag2aa` 扫描 |
| F19 | 04 区「宏观全量」单个 tab pane 渲染 25,156 个 DOM 节点 / 643 个 `<details>`；antd Tabs 默认保留已访问 pane，走完 6 个 tab 后页面多挂约 57k 节点 | `backendTabs[].nodes` |
| F20 | 「最新追踪」连续两行是同一则「王毅会见庞德伟」新闻的长短两版，无去重 | `shots/mo-1920.png` |
| F21 | 信号卡把整句话塞进 label 槽：「Crisis Score 依赖未通过，原始计算仅作审阅证据」，value 槽是「历史分位 4.52%」，title 又重复一遍已可见的历史分位 | `audit3.mjs → signals[0]` |
| F22 | 「刷新数据」直接发起 30 天回填 POST，无二次确认；权限不足只能从错误响应中发现（`formatChoiceMacroRefreshError` 有专门分支）；轮询窗口 120 × 3 s = 6 分钟 | `MarketHomePage.tsx:199-209` |
| F23 | 「焦点解读」的「事件状态」卡把约 300 字的新闻正文（截断）塞进一个结论槽 | `audit3.mjs → focus[2]` |
| F24 | 利率格「下行」与「零变动」都渲染成中性 muted（`rateDirectionTone` 只给上行上琥珀），4 个利率格因此丢失方向的视觉表达 | 这是 DESIGN.md §11 的既定决议，仅作可读性记录 |
| F25 | 03 区 `sectionNav` 的 `position: sticky; top: -18px` 会有一小段被 `z-index: 40` 的章节导航压住 | `report2.json → stickyChrome` |

---

## 6. 结论良好的部分（不要在后续改动中弄坏）

- `npm run lint` 与 `npm run typecheck` 均为空输出。
- 文档化门禁 `ModuleWorkbenchHomePage MarketFinancialChartsWorkbench MarketBackendDataWorkbench marketFinancialChartsModel marketOverviewDenseModel marketOverviewDenseLiquidityModel MarketOverviewDenseFirstScreen LiveRouteReadiness` → **175 / 176 通过**；唯一失败项 `keeps /stock-analysis tied to real page anchors` 属于 `/stock-analysis`，与本页无关。
- 加载全程 0 条 console error / pageerror。
- 1920 / 1440 / 1280 / 1024 / 390 五档视口均无文档级横向溢出；04 区宽表的 2,835 px 溢出被限制在自己的横向滚动容器内，符合「横向滚动查看全部字段」的设计。
- 四个章节锚点跳转后目标顶边均落在 52 px，高于 45 px 的吸顶章节导航，无遮挡。
- 页面内仅 2 个无可访问名的可聚焦元素，且都是 antd 内部控件（`ant-tabs-nav-more`、`ant-pagination-item-link`）。
- 04 区新闻分页读与首屏共享的 500 条样本正确分离（`enabled: activeKey === "news"`，不同 cache key），这是页面契约 §C 明确要求的行为。
- 03 区新闻分组用事件 `received_at` 最大值而非信封 `as_of_date` 披露样本日期，代码注释写明了原因——这是本页处理日期口径最严谨的一处。

---

## 7. 子页面审计

市场工作台子页导航共 7 项，第 1 项是主页面自身，其余 6 项为子页面。全部逐一实测。

### 7.0 分级清单（子页面）

| 级别 | 编号 | 页面 | 问题 |
| --- | --- | --- | --- |
| P0 | S1 | `/news-events` | 390px 视口下文档高 **176,515 px**，单行表格行高 5,520 px |
| P0 | S2 | `/stock-analysis` | 治理门禁**红灯**：readiness 契约要求的锚点 `stock-analysis-toolbar` 已不存在，且与另一条契约测试互相矛盾 |
| P1 | S3 | `/market-data` | `/api/external-data/watermarks` 返回 **403**，页面降级为「读取失败」而非「无权限」，每次加载抛控制台错误 |
| P1 | S4 | `/stock-analysis` | `/api/data-health` 单次 **3.2 s**，页面每次加载发 2–4 次，且绕过 react-query 无任何缓存 |
| P1 | S5 | 跨页 | `/ui/macro/choice-series/latest` 在全应用注册了 **6 个不同 cache key**；`/market-data`、`/cross-asset` 单页各拉两次 |
| P1 | S6 | `/macro-toolkit` | 同一端点同时以 `detail=core`（202 ms）与 `detail=full`（3,752 ms）各拉一次 |
| P1 | S7 | `/stock-analysis` | 业务日期 `2026-08-24`，与主页面声明的 `2026-08-28` 差 4 天，两页无交叉提示 |
| P2 | S8 | `/cross-asset` | 单页 **两个 `<h1>`**；axe `nested-interactive` |
| P2 | S9 | 跨页 | 壳层行情条 `data-tone="down"` 的对比度不足，出现在每一个市场页 |
| P2 | S10 | 治理 | 6 个子页面中 **2 个没有 PAGE 契约**（只有 GAP 占位），却被主页面契约列为「Primary downstream pages」 |
| P2 | S11 | `/macro-toolkit` | `MacroToolkitPage.test.tsx` 单文件跑 **205 s**，并行执行时会超时假红 |

### 7.1 逐页实测基线

计时口径统一为浏览器 Resource Timing（`responseEnd - requestStart`），观察窗口 30 s；字节为解压后 `encodedBodySize` 之和。

| 路由 | FCP | 最后一条后端读完成于 | 后端读次数 | 传输 | DOM 节点 | axe | 治理状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/market-overview` | 184 ms | 1,114 ms | 6 | 241 KB | — | 1 | live / governed-mixed-source / PAGE-MARKET-HOME-001 |
| `/market-data` | 172 ms | 1,835 ms | 10 | 79 KB | 888 | 2 | live / governed-mixed-source / PAGE-MKT-001 |
| `/cross-asset` | 180 ms | 959 ms | 4 | 60 KB | 1,301 | 3 | temporary-exception / PAGE-CROSS-ASSET-001 |
| `/macro-observation` | 168 ms | 852 ms | 2 | 20 KB | 766 | 1 | live / candidate / PAGE-MACRO-OBS-001 |
| `/macro-toolkit` | 172 ms | 6,240 ms | 5 | 62 KB | 1,805 | 1 | live / candidate / PAGE-MACRO-TOOLKIT-001 |
| `/stock-analysis` | 176 ms | 7,700–8,062 ms | 9 | 56 KB | 1,637 | 1 | temporary-exception / **GAP-STOCK-ANALYSIS-PAGE** |
| `/news-events` | 188 ms | 454 ms | 2 | 50 KB | 736 | 1 | temporary-exception / **GAP-NEWS-EVENTS-PAGE** |
| `/stock-analysis/portfolio` | — | — | 1 | 10 KB | 388 | 1 | 随 `/stock-analysis` |

首屏渲染在所有路由上都是健康的（FCP 168–188 ms，load 事件 85–129 ms），无一路由出现横向溢出，无一路由触发错误边界，控制台仅 `/market-data` 有 1 条（即 S3 的 403）。

**一处测量结论的两次反转（以 15:55 的结论为准）**：首轮扫描记录 `/cross-asset` 19.8 s、`/stock-analysis` 27.6 s。我随后用"直连 27 ms / 代理 15 ms / 二次加载 568 ms"把 `/cross-asset` 的 19.8 s 判为 Vite dev server 冷启动假象——**这个判断是错的**：当时测的是刚被页面请求过、已进 TTL 缓存的同一个键。15:55 用从未请求过的键直连后端复测（`.tmp-agent/market-overview-audit/cold_vs_warm.py`）：

```
/api/macro-bond-linkage/analysis?report_date=2026-09-02          43 ms   (warm)
/api/macro-bond-linkage/analysis?report_date=2026-08-26       27,849 ms   (cold key)
/ui/market-data/livermore/signal-confluence?as_of_date=2026-08-24  28 ms   (warm)
/ui/market-data/livermore/signal-confluence?as_of_date=2026-08-21 23,426 ms (cold key)
```

即这两条读的**冷计算真实耗时 23–28 s**，只有命中按参数分键的 TTL 缓存时才快。缓存键含业务日期，所以每个新交易日、每次后端重启、每次 TTL 过期后的第一个访客都要等 20 s 以上；而 `market_home_warmup_service` 的预热清单不含这两条（它预热的是 stock-analysis *workbench*，不是 *signal-confluence*）。这是 S12（新增）：需要把两条读按页面实际请求的键加入预热，或改为物化。`/stock-analysis` 的 7.7–8.1 s 里，`data-health`（S4）与 `signal-confluence` 冷计算是两个独立成因。

### 7.2 S5 — `/ui/macro/choice-series/latest` 的六份 cache key（跨页）

同一个 473 KB（解压后）载荷在全应用注册了 6 个互不相通的 react-query key：

| 消费方 | queryKey |
| --- | --- |
| `WorkbenchShellMarketTicker`（壳层，几乎所有页面） | `["workbench-shell", "choice-macro-latest", mode]` |
| `useMarketHomeQueries`（`/market-overview`） | `["module-home", "choice-latest", mode]` |
| `useMarketDataPageData`（`/market-data`） | `["market-data", "choice-macro-latest", mode]` |
| `useCrossAssetViewModel`（`/cross-asset`） | `["workbench-shell", "choice-macro-latest", mode]` |
| `BondAnalyticsInstitutionalCockpit` | `["bond-analytics-institutional", "choice-macro-latest", mode]` |
| `BondAnalyticsOverviewRateChart` | `[...bondAnalyticsQueryKeyRoot, "choice-macro-latest", mode]` |
| `OperationsAnalysisPage` | `["operations-entry", "macro-latest", mode]` |

实测后果（Resource Timing）：

- `/market-data`：`queued@256ms` 与 `queued@706ms` 各拉一次 → key 不同，必然双拉。
- `/cross-asset`：`queued@268ms` 与 `queued@486ms` 各拉一次 → key 与壳层**相同**，但 `useCrossAssetViewModel` 设了 `refetchOnMount: "always"`（`useCrossAssetViewModel.ts:117`），强制在壳层刚取完之后再取一遍。

跨页导航时同样无法复用：从 `/market-overview` 走到 `/market-data`，同一份数据要重新解析一遍。

### 7.3 S3 — `/market-data` 的 403 被降级成「读取失败」

```
GET /api/external-data/watermarks
403 {"detail":"User is not allowed to read external_data."}
```

页面确实做了降级，显示「宏观序列最新读面已返回数据。外部数据水位读取失败，无法判断输入年龄。」——但全页文本不含「权限 / 无权 / 受限」任一词（实测 `mentionsPermission: false`）。把一个**权限边界**呈现为**读取失败**，会把「这个角色本来就看不到」误导成「后端坏了」，运维方向完全相反。同时它每次加载都在控制台留一条 `Failed to load resource: 403 (Forbidden)`。

需要裁决的是：这个读到底该不该在当前角色下发起？若不该，应由能力开关前置拦截；若该，文案必须说清是权限而非故障。

### 7.4 S4 — `/stock-analysis` 的 `/api/data-health`

`StockAnalysisDataHealthCard`（`StockAnalysisPageImpl.tsx:2772`）自述「自包含加载：挂载即拉 GET /api/data-health」，用裸 `useState` + `useEffect` + `fetchDataHealth` 实现，**完全绕过 react-query**——没有 cache、没有 dedup、没有 staleTime。

实测：

- 直连后端单发：**3,216 ms / 3,203 ms**（两次一致，是真实的后端慢路径）
- 页内：3,573–4,274 ms，且**一次加载发起 2–4 次**
- 4 路并发时每条退化到 4,863–5,460 ms

其中「多次」有一部分是 `main.tsx` 的 `React.StrictMode` 在 dev 下双跑 effect 所致，生产构建不会翻倍；但**绕过查询缓存**这个设计问题与环境无关：任何一次重新挂载都会重新付一次 3.2 s，而它是全页最慢的一条读。

### 7.5 S1 — `/news-events` 移动端 176,515 px

390×844 视口下实测：

```
document.scrollHeight = 176,515 px
table  高 172,184 px  /  50 行
第一行 tbody tr 高 5,520 px
```

即 50 行新闻表把页面撑到约 **209 屏**。表格在窄视口没有做响应式收敛（不折叠、不横滚、不虚拟化），每个单元格竖直折行堆叠。桌面端 1440 视口下同页仅 8,025 px，属正常范围——问题完全出在窄视口。

### 7.6 S2 — `/stock-analysis` 的治理门禁红灯（两条契约互相矛盾）

`LiveRouteReadiness.test.tsx > keeps /stock-analysis tied to real page anchors and verification files` **失败**：

```
AssertionError: stock-analysis-toolbar should remain in
  src/features/stock-analysis/pages/StockAnalysisPage.tsx,
  src/features/stock-analysis/pages/StockAnalysisPageImpl.tsx
```

根因是两份治理契约要求相反：

- `liveRouteReadinessContracts.ts:158` 要求锚点 `stock-analysis-toolbar` **必须存在**。
- `StockAnalysisPageChromeContract.test.ts:139-142` 断言 `stock-analysis-toolbar-*` 系列 testid **必须不存在**（页面已重构为 compact chrome，改用 `stock-analysis-page-toolbar-owner`）。

`StockAnalysisPage.tsx` 现在只有一行 `export { default } from "./StockAnalysisPageImpl";`，而 impl 里 `stock-analysis-toolbar` 确已删除。重构时更新了 chrome 契约，漏了 readiness 契约。这是**主页面审计里那条唯一失败项的根因**——它不属于 `/market-overview`，但属于本次子页面范围。

### 7.7 其余子页面观察

- **S6 `/macro-toolkit` 双档拉取**：同一次加载里 `detail=core` 于 670 ms 发出（202 ms 返回）、`detail=full&history_limit=430` 于 2,487 ms 发出（**3,752 ms** 返回）。§3.2 已证明两档返回同样 23 个顶层键，这里是同一端点在一页内被拉两遍不同档位，也再次复现了冷计算 3.7 s 的量级。
- **S7 日期错位**：`/stock-analysis` 全页以 `as_of_date=2026-08-24` 取数（workbench、stock-detail、kline、signal-confluence 均带此参），而 `/market-overview` 首屏声明「行情 2026-08-28」。两页在同一导航条上并列，互相之间没有任何日期差提示。该页自身标题写着「证据读取就绪 2/8」，已在自我披露就绪度不足。
- **S8 `/cross-asset` 结构**：单页出现**两个 `<h1>`**（「跨资产驱动」与「宏观债券联动分析」），违反单一主标题；axe 另报 `nested-interactive`（`.tcg__svg` 内嵌交互元素）与 2 处 `scrollable-region-focusable`。
- **S9 壳层行情条对比度**：`.workbench-market-ticker-delta[data-tone="down"]` 对比度不足，在 `/market-data`（4 节点）、`/cross-asset`（9 节点）、`/news-events`（2 节点）重复出现。这是壳层组件缺陷，影响每一个市场页，修一处即可全线收敛。
- **S10 治理缺口**：`/stock-analysis` 与 `/news-events` 至今只有 `GAP-STOCK-ANALYSIS-PAGE` / `GAP-NEWS-EVENTS-PAGE` 占位，没有 PAGE 契约；而 `docs/page_contracts.md` §14.6-A 把这两条路由列为 `/market-overview` 的「Primary downstream pages」。主页面把用户导向了两个无契约页面。
- **`/macro-observation` 是全组最干净的一页**：2 条读、20 KB、852 ms 收敛、1 条 axe 告警，且它使用 `detail=core` 而非 `detail=full`——同一端点，只读它真正需要的档位。**这正是 `/market-overview` 应当照抄的范式**（见 §3.2 / H3）。
- **`/stock-analysis/portfolio`**：1 条读、10 KB、388 节点，含 3 个 StateSurface 空/阻断态，结构健康，无独立发现。

### 7.8 子页面测试门禁基线

`npm run test -- MarketDataPage CrossAssetPage MacroToolkitPage MacroObservationPage StockAnalysisPage NewsEventsPage`：

```
Test Files  1 failed | 16 passed (17)
     Tests  1 failed | 493 passed | 194 skipped (688)
```

唯一失败项 `MacroToolkitPage > opens artifact-backed acceptance actions for each core model signal` 是 **15 s 超时假红**：单独重跑通过（19.9 s，`1 passed | 119 skipped`）。但 `MacroToolkitPage.test.tsx` 单文件耗时 **205 s**，并行执行时挤占资源就会翻红——这是需要处理的测试性能问题（S11），不是功能缺陷。

`/stock-analysis` 的 readiness 红灯（S2）不在这批文件里，它由 `LiveRouteReadiness.test.tsx` 覆盖，见 §7.6。

---

## 8. 建议的处置分工

- **前端可自闭环**：F1（让 gate 与 briefings 共用同一判定，并保留后端 `tone: "missing"` 的原文）、F2/F3（统一格子与 tooltip 的格式化函数）、F4（把 `DENSE_FIRST_SCREEN_CHART_KEYS` 与 `selectedDenseCharts` 收敛到同一个来源；默认展开一个真的有图的分组）、F5（focus 模式下隐藏或禁用折叠按钮）、F16–F25；子页面侧 S1（窄视口表格收敛）、S2（同步 readiness 契约锚点）、S5（统一 `choice-series/latest` 的 cache key 并去掉 `refetchOnMount: "always"`）、S8、S9、S11。
- **需要后端 / 数据计算裁决**：F6–F15 与 F12 的指标契约化，加上子页面侧 S3（403 的权限语义）、S4（`/api/data-health` 3.2 s + 无缓存）、S6（`detail` 双档）、S7（跨页 as_of 错位）、S10（两个子页面缺 PAGE 契约）。这部分已整理为独立交接单：`docs/audits/2026-09-02-market-overview-backend-compute-handoff.md`。
