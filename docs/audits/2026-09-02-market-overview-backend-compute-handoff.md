# 交接单：`/market-overview` 及其 6 个子页面 · 后端数据计算专项

> **2026-09-02 review 增补（先读这段）**：本单写完后我对着后端代码与调度日志做了一次复核，四条结论的性质被改写，另有一条撤回。完整的 review 与实施方案在 `docs/plans/2026-09-02-market-overview-module-compute-plan.md`，下面只列结论：
>
> - **H1 的根因不在后端计算**：`MOSS-DailyDataRefresh` 自 08-28 起每天在第一步退出（PS 5.1 `$ErrorActionPreference="Stop"` + `2>&1` 把子进程首行 stderr 当终止错误；`choice_stock_daily_refresh.py:267` 撞 DuckDB 写锁时正好向 stderr 打印重试提示）。宏观刷新自 08-27 起一次都没跑过，回执因此卡 `running`。已用五行脚本复现（`.tmp-agent/market-overview-audit/ps_stderr_probe.ps1`）。**修 `daily_data_refresh.ps1:317` 一处 + 给回执服务加 `running` 年龄判断，比 H1 原文里任何一项都先做。**
> - **H3 / H4 / H5 / H13 合并**：预热器（`market_home_warmup_service.py:123-134`）只预热 `detail=core`，页面却请求 `detail=full&history_limit=430`，键永远不命中。页面改请求 `core`（`/macro-observation` 已是如此）即可，四条一起消失。
> - **H11 根因已定位**：`data_health_service.py:602` 每次请求 `subprocess.run(["schtasks","/query","/fo","csv","/v"])`，本机 2.8–2.9 s。加进程内 TTL 缓存即可。
> - **H8 时区项改写**：`received_at` 时刻正确（`TIMESTAMPTZ` 按 UTC 序列化），但 65% 的记录是日粒度（研报、央视，`T00:00:00`），密度聚合必须先剔除它们再按 Asia/Shanghai 分桶；**H8 单位项撤回**（`CNY/USD` 量纲正确）。
> - **H9 方向改写**：后端已有别名注册表 `macro_vendor_service.py:82-87`，前端另有两份（壳层 `workbenchShellTicker.ts:92-100`、市场总览正则），三处并存且顺序不一致；方案是扩后端这一份为模块级 slot 注册表，不新建。
>
> 修订后顺序：**R1 调度器 → R2 页面改 core → R3 schtasks 缓存 → 方案 §2 `market.snapshot` → H2/H6/H12/H15 口径裁决**。前三项合计不到一天。

- 承接方：**Fable 5.1**
- 出单方：市场工作台完整审计（2026-09-02），完整报告见 `docs/audits/2026-09-02-market-overview-page-audit.md`
- 覆盖路由：`/market-overview`（H1–H10）＋ 子页面 `/market-data`、`/cross-asset`、`/macro-observation`、`/macro-toolkit`、`/stock-analysis`、`/news-events`（H11–H15）
- 边界：本单**只覆盖后端数据计算与读契约**。纯前端渲染缺陷（tooltip 精度、图表去重、focus 模式死按钮、搜索交互、窄视口表格、cache key 统一等）不在本单范围内，由前端另行处置。
- 前置状态：`npm run lint` / `npm run typecheck` 干净；主页面门禁 175/176 通过，子页面门禁 493/494 通过。两条已知红灯都**不是**本单引入、也**不需要**本单先修：
  - `LiveRouteReadiness > keeps /stock-analysis tied to real page anchors` —— 前端契约锚点未同步（详见报告 §7.6）
  - `MacroToolkitPage > opens artifact-backed acceptance actions...` —— 并行执行下的 15 s 超时假红，单独重跑通过

---

## 0. 环境与复现

```powershell
# 后端（本单全部证据基于它）
curl http://127.0.0.1:7888/health          # {"status":"ok"}

# 前端（real 数据源）
http://127.0.0.1:5888/market-overview
```

审计脚本已留在仓库，可直接重跑取证：

| 脚本 | 作用 |
| --- | --- |
| `.tmp-agent/market-overview-audit/probe_market_overview.py` | 6 条读的状态 / 耗时 / 体积 / 结构 |
| `.tmp-agent/market-overview-audit/payload_weight.py` | 每条 payload 的字段级字节权重 |
| `.tmp-agent/market-overview-audit/detail_cost.py` | `detail` 与 `history_limit` 的成本对比 |
| `.tmp-agent/market-overview-audit/meta.py` | `result_meta` / `warnings` / `conclusion` / `source_checks` |

以上 python 脚本从仓库根执行。同目录下的 `audit.mjs` / `audit2.mjs` / `audit3.mjs` 是浏览器侧取证（需从 `frontend/` 执行），本单结论不依赖它们。

页面的 6 条读（全部 `retry: false`、`staleTime: 5min`，定义在 `frontend/src/features/workbench/module-home/useMarketHomeQueries.ts`）：

```
/ui/macro/choice-series/latest                                          473 KB / 26 ms
/ui/market-data/rates                                                   306 KB /  5 ms
/ui/market-data/catalog                                                  40 KB / 16 ms
/ui/macro/toolkit/analysis?detail=full&history_limit=430                156 KB / 3,321 ms(冷)
/ui/macro/toolkit/analysis/strategy-summaries                            55 KB / 122 ms
/ui/news/choice-events/latest?limit=500&offset=0&include_payload_json=false  816 KB / 180 ms
```

---

## H1（最高优先）刷新回执卡在 `blocked`/`running` 已 6 天，页面首屏因此长期"暂停判断"

`/ui/macro/toolkit/analysis` 返回：

```json
"refresh_receipt": {
  "status": "blocked",
  "ready": false,
  "run_status": "running",
  "generated_at": "2026-08-27T10:50:15.620455+00:00",
  "source_version": "macro_toolkit_freshness_refresh_v3",
  "missing_fields": [
    "receipt.status", "receipt.exit_code",
    "receipt.result.steps.choice_policy_rate_7d",
    "receipt.result.steps.commodity_daily_ingest",
    "receipt.result.steps.public_cross_asset_headlines",
    "receipt.result.steps.tushare_ncd_shibor",
    "receipt.result.latest_observation_dates.CA.COPPER",
    "receipt.result.latest_observation_dates.CA.CSI300",
    "…共 17 项"
  ]
}
```

连带 `result.warnings`：

- `刷新回执未通过完整性校验：…；观察性结论已关闭，原始指标仍可作未验证证据。`
- `CFFEX optional step is missing from the receipt`

后果链条：`quality_flag = "warning"` → 前端 gate 判 blocked → 首屏 hero 渲染「暂停形成今日判断」。**这是页面当前最显眼的状态，且已经持续 6 天。**

需要 Fable 5.1 回答：

1. `run_status: "running"` 但 `generated_at` 停在 6 天前——是任务真的挂着，还是回执写入链路断了？
2. `missing_fields` 里那 17 项是刷新步骤没跑，还是跑了但回执 schema 不匹配？（`receipt.status` / `receipt.exit_code` 这两项缺失指向后者）
3. `CFFEX optional step` 标为 optional 却进入 `warnings`，是否应该降级为不影响 `quality_flag` 的信息级提示？
4. 恢复路径是什么？是否需要一次人工重跑 `macro_toolkit_freshness_refresh_v3`？

---

## H2 `quality_flag` 的分级语义：`warning` 是否应当等同于 `error` 地阻断判断

当前前端把 `quality_flag !== "ok"` 一律判 blocked（`MarketOverviewDenseFirstScreen.tsx:206`），`warning` 与 `error` 同权。而后端在 `warning` 状态下其实已经给出了一条安全的「不下结论」结论：

```
stance             = "数据不足"
tone               = "missing"
summary            = "最近一次定时数据刷新未通过完整性校验，当前指标仅可作未验证观察证据。"
recommended_action = "请完成后端数据刷新并通过回执校验，再形成分析性判断。"
```

请裁决并给出契约化的输出，而不是让前端继续用字符串匹配去猜：

1. `warning` / `stale` / `error` 是否应当映射到不同的展示档位？
2. 建议在 `result_meta` 或 `conclusion` 下新增一个**结构化的阻断说明**，例如 `blocking: { level, reason_code, human_reason, recovery_action }`，让前端直接渲染后端原文，不再自造文案。当前前端的中文兜底文案散落在三处（`MarketHomePage.tsx:102-152`、`MarketOverviewDenseFirstScreen.tsx:199-238`、`MarketBackendDataWorkbench.tsx:143-166`），各自用正则匹配英文错误串再翻译，长期一定会漂移。
3. `tone: "missing"` 的 `conclusion` 本身不是结论，压制它只损失信息。请确认这一判断，前端将据此改为原样透出。

---

## H3 `detail=full` 名不副实：与 `detail=core` 返回同样的 23 个顶层键

`detail_cost.py` 实测：

```
/ui/macro/toolkit/analysis?detail=core                     51,188 B
/ui/macro/toolkit/analysis?detail=full&history_limit=430  156,002 B
```

两者顶层键完全一致（23 个，逐一比对无差异）：`a_share_risk, as_of_date, capabilities, capability_results, cffex_member_rank, choice_stock_refresh, conclusion, coverage, data_health, default_data_sources, hason_strategy, indicators, model_readiness, output_files, primary_signal, readiness_summary, report_bundle, runtime_status, signal_cards, source_checks, strategy_data_status, strategy_summaries, warnings`。

即 `full` 不新增任何业务分区，只把各分区内的历史铺开，代价是 3× 体积。请确认 `detail` 参数的设计意图，并明确 `/market-overview` 应当使用哪一档。

---

## H4 `history_limit=430` 拉了 221 个点，只为算首尾差，而这个差值页面不显示

`frontend/src/features/workbench/module-home/useMarketHomeQueries.ts:7` 写死 `MARKET_HOME_CRISIS_SCORE_HISTORY_LIMIT = 430`。唯一去向：

```84:97:frontend/src/features/workbench/module-home/marketDeskIntelModel.ts
  const first = history[0];
  const last = history[history.length - 1];
  const scoreDelta = … (last.crisisScore - first.crisisScore)
  const percentileDelta = … (last.percentile - first.percentile)
```

实测 `capability crisis_score_cn: score_history points=221, bytes=15,293`。而 `scoreDelta` / `percentileDelta` / `scoreHistory` 在本路由**没有渲染方**——唯一消费 `scoreHistory` 的 `MarketCrossAssetGapBlock` 不在 `MarketHomeLayout` 的渲染树里（全仓 grep 仅命中它自己的测试）。首屏 Crisis 位只显示 `crisisScore.toFixed(2)` 与 `regime`。

请给出方案：后端直接返回预先算好的 `crisis_score_delta` / `percentile_delta`（附窗口定义），前端就不需要 `history_limit` 这个参数了。若历史序列确有其他消费方，请说明，我们改为按需拉取。

---

## H5 冷缓存 3.2–3.3 s 阻塞首屏判断位

同一 URL 连续请求：

```
detail=full&history_limit=430   → 3,321 ms   ← 页面加载走的就是这条
detail=full&history_limit=430   →   137 ms
detail=full&history_limit=60    → 3,267 ms   ← 换参数即重算
detail=full&history_limit=430   →   125 ms
```

记忆化按 `(detail, history_limit)` 组合生效，未命中即重算约 3.2 s。这条读同时供给 hero 的 stance/summary/action、口径面板、指标变动表和 03 区两张图，所以每次冷启动首屏判断位都要空 3 秒以上；其余 5 条读都在 600 ms 内返回。

需要的结论：3.2 s 里的时间花在哪个环节（能力计算？DuckDB 扫描？产物文件读取？），是否可预热或拆分为「结论快路径 + 明细慢路径」。

审计期间另观察到一次后端瞬时拒连（`WinError 10061`，紧接在多次 3 s 级请求之后），数秒后自愈，未能复现，仅作线索记录。

---

## H6 `strategy_summaries` 双份返回且 `as_of_date` 不一致，前端把两个日期合成了一个对象

同一组 4 个策略（`moving_average`、`mean_reversion_momentum`、`multi_factor_selection`、`low_crowding_regime_multifactor`，各 9.8 KB）由两条读同时返回，但业务日期不同：

| 读 | `result_meta.as_of_date` |
| --- | --- |
| `/ui/macro/toolkit/analysis?detail=full` | `2026-08-28` |
| `/ui/macro/toolkit/analysis/strategy-summaries` | `2026-08-24` |

前端 `moduleHomeModel.ts:1974-1981` 的 `mergeMacroToolkitAnalysis` 从两份里各取一部分拼成一个对象（`strategy_summaries` 取 analysis 侧、`shadow_portfolio_report` 只有 strategy 侧有），随后 `buildMacroToolkitStrategyRows` 给所有策略行统一盖 `analysis.as_of_date`。当 analysis 侧数组为空走 fallback 时，**08-24 的数据会被盖上 08-28 的日期戳**。

需要裁决：

1. 两条读为什么会对同一批策略给出不同的 `as_of_date`？哪个是权威？
2. 是否应当把 `strategy_summaries` 从 `analysis` 响应中移除（页面的图表只用 `strategy-summaries` 侧的 `shadow_portfolio_report`），让职责单一？
3. 若必须双份，请保证 `as_of_date` 一致，或在每个策略条目上带自己的日期。

---

## H7 新闻读：816 KB 换 7×12 的热力图，且 48 KB 的 `compare` 无人消费

`/ui/news/choice-events/latest?limit=500&offset=0&include_payload_json=false` 返回 816 KB：`events` 781 KB + `compare` 48 KB。

页面对这 816 KB 的全部消费：

- `buildDenseNewsDensity` → 7 个主题 × 12 个两小时桶的计数矩阵（`marketOverviewDenseModel.ts:302-355`）
- 3 条最新事件的标题
- 03 区两张图：新闻主题分布、新闻接收日期分布
- `total_rows`、`excluded_future_rows`

`compare = { same_direction: 1, conflicting: 0, review_needed: 5, candidate_scenarios: 5 }` 实测在 01/02 区完全不出现（关键词扫描 `事件比较|同向|冲突|待复核` 全部未命中），只在 04 区被原样转储。

请求：

1. 提供一个聚合读（例如 `/ui/news/choice-events/density`），直接返回主题 × 时间桶的计数、样本区间与 Top-N 事件，把 816 KB 压到 KB 级。
2. `compare` 是已经算好的冲突/待复核判断——首屏有一个「P0 - P2 核验队列」面板正在做类似的事且当前只产出 3 条 P1/P2。请评估把 `compare` 接进这个队列，而不是继续白拉 48 KB。

---

## H8 时区与单位口径

**时区**：`received_at` 返回带偏移量的 UTC：

```
2026-08-27T12:29:46+00:00 | tushare.news.sina | tushare_news
```

前端 `bucketableNewsTime`（`marketOverviewDenseModel.ts:283`）用正则直接取字符串里的小时位分桶，热力图横轴渲染为 `00 02 04 … 22`，脚注只写「按接收时间两小时分桶」，无时区标注。一条北京时间 20:29 的新闻落在 `12:00` 桶。请确认：热力图应当按 UTC 还是 Asia/Shanghai 分桶？若按后者，建议由后端直接返回本地化的桶（避免前端各页各自换算）。

**单位**（2026-09-02 review 已更正）：

| 标的 | 返回单位 | 结论 |
| --- | --- | --- |
| 中间价:美元兑人民币 | `CNY/USD` | **撤回**。`6.7811` 的单位"每 1 美元多少人民币"量纲正确，不需要后端改动 |
| 沪深300指数收盘价 | `index` | **移出本单**。`/cross-asset` 已在前端把 `index` 映射为「指数」（`CrossAssetPage.test.tsx:985-988`），市场总览漏做同样的映射，属前端 |

---

## H9 指标身份契约化（本单里最需要产品/数据裁决的一项）

首屏 8 个头条指标的身份，目前是**前端在 211 条序列上用正则猜出来的**：

```437:468:frontend/src/features/workbench/module-home/marketOverviewDenseModel.ts
  const tenYear = merged.find(isChinaTenYearPoint);
  const dr007 = findPoint(merged, (text) => /dr\s*0?07/i.test(text));
  const csiClose = findPoint(
    latestPoints,
    (text) => /沪深\s*300|csi\s*300|hs300/i.test(text) && /收盘|close/i.test(text),
  );
```

匹配文本是 `series_id + series_name` 的小写拼接；`isChinaTenYearPoint` 还叠了一层「含 10Y 提示 且 不含境外主权提示 且（`^cn[._-]` 或含中国主权提示）」的启发式。同样的做法还用在 `buildDenseLedgerRows`（12 条优先级正则）和 `buildDenseMacroPulseRows`（CPI/PPI/PMI/社融 4 条正则 + 兜底取前 N 条）。

页面契约 `docs/page_contracts.md` §14.6-E 明确写着「None. This module home has no standalone `MTR-*` binding」——也就是说这层身份解析**不在任何血缘、指标字典或金标准的覆盖范围内**。供应方改一次 `series_name`，首屏「10Y国债」就可能静默换成另一条序列，且没有任何测试会变红。

请求：为这 8 个头条指标（10Y国债、DR007、7D逆回购、SHIBOR 3M、沪深300、Brent、USD/CNY、铜主力）以及指标变动表的 4 个槽位，给出后端侧的稳定标识绑定（`series_id` 白名单或新的 `slot` 字段），并接入 `docs/metric_dictionary.md`。前端改为按 slot 读取，删除全部正则匹配。

参考：当前实际命中的序列（取自 `source_checks`）为 `E1000180`(10Y)、`CA.DR007`、`EMM00088132`(7D逆回购)、`NCD.SHIBOR.3M`、`CA.CSI300`、`CA.COPPER`。

---

## H10 payload 瘦身（汇总）

**先明确这条不是带宽问题**：浏览器 Resource Timing 实测首屏 6 条读传输量合计仅 **241 KB**（gzip 后）。下表全部是**解压后**的量，也就是需要 JS 在主线程解析、驻留内存、并被前端逐条聚合的量。

| 项 | 解压后现状 | 目标 |
| --- | --- | --- |
| 首屏 6 条读合计 | **1.85 MB**（传输 241 KB） | 页面实际渲染约 18k 字符文本 + 4 张图 |
| `newsEvents.events` | 781 KB | 见 H7，聚合后应为 KB 级 |
| `choiceLatest.series` | 493 KB（133 条，含 `recent_points`） | 首屏只用 8 个点位 + 4 张图 |
| `marketRates.series` | 319 KB（78 条） | 同上 |
| `macroToolkitAnalysis.capability_results` | 83 KB / 156 KB | 见 H3、H4 |
| `choiceLatest.result_meta` | **6.3 KB**（几乎全是拼接的 `source_version`/`vendor_version` 哈希串） | 建议改为版本指纹 + 可选明细端点 |

所以优先级排在 H1/H11/H5 之后：它影响的是解析耗时与内存，不是首屏可见时间（FCP 184 ms、6 条读 1,114 ms 收敛，都是健康的）。

注意 04 区「数据核验」的设计目标就是「保留全部返回字段」，所以瘦身方案需要区分**首屏读**与**核验读**，不能一刀切裁字段。可行方向是首屏走精简读、04 区按 tab 惰性拉全量读（该区的新闻 tab 已经是这个模式，可作范式）。

---

# 子页面部分（H11–H15）

先更正一条我之前写错的**排除项**：我曾把 `/cross-asset` 的 19.8 s 判为 Vite 冷启动假象并写"不要立项"。**撤回。** 15:55 用从未请求过的键直连后端复测（`.tmp-agent/market-overview-audit/cold_vs_warm.py`）：`/api/macro-bond-linkage/analysis?report_date=<新键>` **27,849 ms**、`/ui/market-data/livermore/signal-confluence?as_of_date=<新键>` **23,426 ms**；同键第二次 13–43 ms。之前那组"27 ms / 15 ms / 13 ms"全是命中缓存的同一个键。

## H16 两条子页面读冷计算 23–28 s，且不在预热清单里

缓存键含业务日期（`report_date` / `as_of_date`），所以**每个新交易日、每次后端重启、每次 TTL 过期后的第一个访客**都要等 20 s 以上：`/cross-asset` 等 `macro-bond-linkage`，`/stock-analysis` 等 `signal-confluence`。`market_home_warmup_service.warm_market_home_read_caches()` 预热了 stock-analysis *workbench*，没有预热 *signal-confluence*，也没有 *macro-bond-linkage*。

请求：

1. 两条读按页面实际请求的键加入预热（`/cross-asset` 的 `report_date` 取自 `useCrossAssetViewModel.ts:121-126` 的 `maxCrossAssetHeadlineTradeDate`，即 choice latest 头条序列的最大 `trade_date`；`/stock-analysis` 的 `as_of_date` 取自 Livermore strategy 的 `resolved as_of_date`）。注意 dashboard-home 那段注释的教训（`market_home_warmup_service.py:222-231`）：预热键与页面键差一天就白热。
2. 回答 23–28 s 花在哪一层（DuckDB 扫描？Python 逐日循环？），是否有物化空间。这两条读的口径本身不在本单范围，只问耗时。

## H11 `/api/data-health` 单次 3.2 s，是全组最慢的一条读

直连后端实测（`slow_endpoints.py`，连续两次）：

```
/api/data-health   run1=3,216ms  run2=3,203ms  bytes=5,297
```

两次一致，说明**不是冷缓存，是稳定的 3.2 s 计算**。返回体只有 5.3 KB。

并发下继续退化（`contention.py`，4 路并发）：

```
sibling 4,863ms / 5,323ms / 5,359ms / 5,460ms   /api/data-health
```

页面侧：`/stock-analysis` 一次加载会发起 **2–4 次**该请求，Resource Timing 实测 3,573–4,274 ms 不等，是该页 7.7–8.1 s 收敛时间的唯一主因。

调用方是 `StockAnalysisDataHealthCard`（`StockAnalysisPageImpl.tsx:2772`），自述「挂载即拉」，用裸 `useState` + `useEffect` 实现，**绕过 react-query，无缓存无 dedup**。多次调用里有一部分是 dev 环境 `React.StrictMode` 双跑 effect，生产不会翻倍——但无缓存这一点与环境无关。

需要你回答：

1. 3.2 s 花在哪？后端 `backend/app/services/data_health_service.py` 聚合了供数新鲜度、复权因子缺口、公式版本存量、概念区间陈旧度、涨跌停回填、tradestatus 词表、调度任务状态七项检查——是某一项拖慢，还是七项串行？
2. 这是一个系统级体温计，天然适合缓存。后端能否加 TTL 缓存或物化？目标：**亚秒**。
3. 若无法加速，请确认前端改为 react-query（带 staleTime）是可接受的口径——健康面数据滞后几分钟是否影响它的用途？

## H12 `/api/external-data/watermarks` 对当前角色返回 403，页面降级成「读取失败」

```
GET /api/external-data/watermarks
403 {"detail":"User is not allowed to read external_data."}
```

`/market-data` 每次加载都会发这个请求，每次都在浏览器控制台留一条 `Failed to load resource: 403 (Forbidden)`。页面文案降级为「外部数据水位读取失败，无法判断输入年龄」，全页不含「权限 / 无权 / 受限」任一词。

这是把**权限边界**呈现成了**系统故障**，会把运维引向完全相反的方向。需要裁决：

1. `/market-data` 在当前角色下**应不应该**发起这个读？若不应该，请提供能力开关（如 `capabilities.external_data.read`）让前端前置拦截，而不是靠 403 兜底。
2. 若应该发起，403 需要一个可区分的结构化标识（而不是只靠 `detail` 文案做正则），前端据此渲染「无权限」而非「读取失败」。
3. 顺带确认：`external_data` 这个权限当前是按什么粒度授予的？页面契约里没有描述。

## H13 `/macro-toolkit` 在一次加载里把同一端点的两个档位都拉了

Resource Timing 实测：

```
queued@  670ms  server=  202ms   9,134B   /ui/macro/toolkit/analysis?detail=core
queued@2,487ms  server=3,752ms  28,724B   /ui/macro/toolkit/analysis?detail=full&history_limit=430
```

两件事：

1. 同一端点在一页内被拉两遍不同档位。结合 H3（两档返回**同样 23 个顶层键**），请确认这两次读是否可以合并为一次。
2. 这里再次复现了 H5 的冷计算量级：`detail=full` **3,752 ms**。它是 `/macro-toolkit` 6,240 ms 收敛时间的主因，也和 `/market-overview` 首屏那 3.3 s 是同一条路径。**H5 与本条建议一起处理。**

顺带一提：`/macro-observation` 只拉 `detail=core`（202 ms）和 `strategy-summaries`，全页 2 条读、20 KB、852 ms 收敛，是全组最干净的一页。它证明了 `core` 档足够支撑一个宏观观察面——**这就是 H3 想要的那个答案的现成样例**。

## H14 跨页 `as_of_date` 错位：`/stock-analysis` 停在 08-24，主页面声明 08-28

`/stock-analysis` 全页读都带 `as_of_date=2026-08-24`：

```
/ui/market-data/stock-analysis/workbench?top_k=10
/ui/market-data/livermore/stock-detail?stock_code=300313.SZ&as_of_date=2026-08-24&lookback=60
/ui/market-data/stock-analysis/kline-analysis?stock_code=300313.SZ&as_of_date=2026-08-24
/ui/market-data/livermore/signal-confluence?as_of_date=2026-08-24
```

而 `/market-overview` 首屏声明「行情 2026-08-28 / 正式序列 2026-08-28」，两页并列在同一条子页导航上，互相之间没有任何日期差提示。`/stock-analysis` 自己的标题已经写着「证据读取就绪 2/8」，在自我披露就绪度不足。

加上主页面内部已有的错位（报告 §3.4：`analysis` 08-28 vs `strategy-summaries` 08-24；§4.3：行情带横跨 08-25~08-28；新闻样本停在 08-27），整个市场工作台目前**至少并存 4 个业务日期**。

需要的结论：这些差异中哪些是数据本身的正常节奏（月频指标本就滞后），哪些是刷新链路掉队？能否由后端给出一个统一的「本模块各数据面最新业务日」的读，让导航层可以标注哪个子页面的数据更旧？

## H15 两个子页面没有 PAGE 契约，却被主页面契约列为主要下游

`docs/live_route_maturity.md` 现状：

| 路由 | contract_id |
| --- | --- |
| `/stock-analysis` | **GAP-STOCK-ANALYSIS-PAGE**（占位，非契约） |
| `/news-events` | **GAP-NEWS-EVENTS-PAGE**（占位，非契约） |

而 `docs/page_contracts.md` §14.6-A 把这两条路由都写进了 `/market-overview` 的「Primary downstream pages」。也就是说主页面正在把用户导向两个没有读契约、没有指标边界、没有 owner 签字的页面。

这不是代码问题，是治理缺口。请与相应 owner 确认补契约的时间点，或在导航层显式标注这两个入口的 `temporary-exception` 状态（当前子页导航只在 `title` 悬浮里带 `statusLabel`，视觉上与 live 页面无差别）。

---

## 交付期望

1. 对 H1–H16 逐条给出结论：**接受修复 / 需要业务裁决 / 判定为预期行为**。2026-09-02 15:40 起 H1（回执活性）、H3/H4/H5/H13（预热键对齐）、H7 部分（新闻密度进 snapshot）、H8 时区项、H9（slot 注册表）、H11（`schtasks` 缓存）已由 Codex 工作包落地，见 `docs/plans/2026-09-02-market-overview-fix-dispatch/README.md` §5；**新增两条前置项**：`detail=core` 不含 `capability_results`（snapshot `crisis` 分区因此 `degraded`，WP-H 开工前必须解决），以及 `choice_policy_rate_7d` 写入步骤缺写锁重试（当天回执因此 `failed`）。
2. H1、H2、H6、H8、H9、H12、H14、H15 属于口径与契约问题，改动前请按仓库规范同步 `docs/page_contracts.md` §14.6 与 `docs/metric_dictionary.md`。
3. 建议的处理顺序（2026-09-02 review 后修订）：**R1 调度器止血 → R2 页面改 `detail=core` → R3 `schtasks` 缓存 → 方案 §2 `market.snapshot` → H2 / H6 / H12 / H15 口径裁决**。R1–R3 的具体改动、文件行号与验收写在 `docs/plans/2026-09-02-market-overview-module-compute-plan.md` §3 Phase 0；`market.snapshot` 的端点、分区、缓存键、测试与前端切换在同文件 §2–§3。H1 原文里的四个问题仍需回答，但答案的前提已变：回执不是"校验失败"，是"任务从没跑完"。
4. 任何后端改动完成后，请复跑相关门禁（命令来自 `docs/live_route_maturity.md`）：

```bash
# 主页面
npm run test -- ModuleWorkbenchHomePage MarketFinancialChartsWorkbench MarketBackendDataWorkbench \
  marketFinancialChartsModel marketOverviewDenseModel marketOverviewDenseLiquidityModel LiveRouteReadiness
npx playwright test tests/playwright/market-overview-smoke.spec.mjs -c playwright.config.mjs

# 子页面
npm run test -- MarketDataPage CrossAssetPage MacroToolkitPage MacroObservationPage \
  StockAnalysisPage NewsEventsPage

python -m pytest tests/test_live_route_page_contract_completeness.py tests/test_choice_news_routes.py \
  tests/test_macro_toolkit_scripts.py tests/test_stock_analysis_workbench_api.py -q
```

**基线（改动前，请勿把这两条当成本单引入的回归）**：

| 门禁 | 结果 | 已知红灯 |
| --- | --- | --- |
| 主页面 vitest | 175 / 176 | `LiveRouteReadiness > keeps /stock-analysis tied to real page anchors`：readiness 契约锚点未随页面重构同步，属前端契约问题（报告 §7.6） |
| 子页面 vitest | 493 / 494（另 194 skipped） | `MacroToolkitPage > opens artifact-backed acceptance actions...`：并行下 15 s 超时假红，单独重跑 19.9 s 通过 |
