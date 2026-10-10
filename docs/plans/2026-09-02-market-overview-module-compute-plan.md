# 市场工作台模块级后端计算方案（`market.snapshot`）

- 日期：2026-09-02
- 性质：**方案与 review，只读；未改任何生产代码**
- 上游：`docs/audits/2026-09-02-market-overview-page-audit.md`（F1–F25、S1–S11）、`docs/audits/2026-09-02-market-overview-backend-compute-handoff.md`（H1–H15）
- 目标读者：Fable 5.1（后端实施）、前端接手人、市场模块 owner

## 0. 一句话

先修一条调度脚本的 stderr 处理让数据重新流起来（这是"暂停判断"六天的真正根因，五行脚本可复现），再把 `/market-overview` 首屏所需的全部派生计算收进一个后端模块级读 `GET /ui/market-overview/snapshot`，按 `home.snapshot` 的组合模式实现；前端删掉三套并存的"序列身份猜测"代码，只做格式化。交接单原来的 H1–H15 里，有 4 条的性质在本次 review 中被改写，见 §1。

---

## 1. Review 结论：交接单里需要改写的判断

我把交接单 H1–H15 逐条对着后端代码与运行痕迹复核了一遍。以下是**新增或改写**的事实，每条都有可复跑的证据。

### R1（P0，改写 H1 / H14 / F15 的性质）日更调度器自 2026-08-28 起每天死在第一步，所有下游数据面因此冻结

事实链：

1. `scripts/scheduling/logs/20260828.log` … `20260901.log` **每一天都是 499 字节、4 行**，最后一行永远是 `[choice_stock_daily_refresh] START …`，没有 `OK` / `FAILED` / `summary`。
2. `schtasks /query /tn MOSS-DailyDataRefresh` 显示上次结果 **1**，运行时间 18:45:01。
3. `data/logs/choice_stock_daily_refresh_receipt.json` 是 09-01 18:45:07 写入的 **`status: "running"`** 存根，398 字节，之后再无更新。
4. `data/logs/macro_toolkit_freshness_refresh_receipt.json` 是 08-27 18:50:15 的 `running` 存根（445 字节，`steps: []`）；08-27 的日志在 `[macro_toolkit_freshness] START` 之后同样戛然而止。
5. 三个专用的旧计划任务（`MOSS-ChoiceStockDailyRefresh` / `MOSS-MacroToolkitFreshness` / `MOSS-MacroToolkitDailyChain`）`Next Run Time = N/A`，最后一次运行是 08-24——它们已被合并进 `MOSS-DailyDataRefresh`，所以 DailyDataRefresh 死了就没有任何东西在刷宏观数据。

机制（已复现）：`scripts/scheduling/daily_data_refresh.ps1:67` 设 `$ErrorActionPreference = "Stop"`，`:317` 用 `$output = & $PythonExe @stepArgs 2>&1` 运行子进程。Windows PowerShell 5.1 下，`2>&1` 会把子进程 stderr 的**每一行**包成 `NativeCommandError` 写入错误流，在 `Stop` 偏好下第一行就终止脚本、退出码 1、不再写日志。复现脚本 `.tmp-agent/market-overview-audit/ps_stderr_probe.ps1`（本机 PS 5.1.26100）：

```
before-call
python.exe : stderr-line
    + FullyQualifiedErrorId : NativeCommandError
driver-exit=1
```

触发源：`scripts/choice_stock_daily_refresh.py:267-269` 在 DuckDB 写锁争用时向 **stderr** 打印 `DuckDB writer contention … retrying`。API 进程（`:7888`）自 08-28 起持续在线并持有 DuckDB 连接，任务一启动就撞锁、打一行 stderr、驱动脚本立刻死亡——时间点（18:45:05–07）与 receipt 写入时间完全吻合。

后果就是页面上看到的一切：宏观刷新回执六天卡 `running` → `refresh_receipt.status = blocked` → `quality_flag = warning` → 首屏"暂停形成今日判断"（H1）；新闻停在 08-27（F15）；股票分析停在 08-24（H14）；模块内并存 4 个业务日期。

**改写**：H1 不是后端计算问题，是一条 `scripts/scheduling` 的驱动脚本缺陷，加一个回执服务的活性漏洞（`macro_toolkit_refresh_receipt_service.py` 对 `status=running` 没有任何"跑了多久"的判断，六天前的 `running` 与六秒前的 `running` 得到同样的 `blocked`）。修法见 §3 Phase 0。

### R2（P1，改写 H3 / H5 / H13）预热器预热的是 `detail=core`，页面请求的是 `detail=full&history_limit=430`——键永远对不上

`backend/app/services/market_home_warmup_service.py:123-134` 预热 `market_home_macro_analysis_cache_key(duckdb, "core", freshness_fingerprint=…)`；`backend/app/main.py` 的后台线程按 TTL（默认 300 s）× ratio 周期重刷。而 `/market-overview` 与 `/macro-toolkit` 请求的键是 `macro-toolkit/analysis::full::430::{fingerprint}::{duckdb}`——**预热器从不构建这个键**。于是每个 TTL 窗口内第一个打开页面的用户都吃一次 3.3–3.7 s 的冷计算，且这个 3 s 卡在首屏判断位上。

这和 `market_home_warmup_service.py:222-231` 那段注释描述的 dashboard-home 事故是同一个模式："Warming any other date builds cache keys the page never asks for, so the whole prewarm silently misses"。

**改写**：H5 的"3.2 s 花在哪"仍值得回答，但页面侧的正确修法不是加速 `full`，而是**像 `/macro-observation` 一样请求 `core`**（该页 2 条读、20 KB、852 ms 收敛）。`detail=core` 与 `detail=full` 返回同样 23 个顶层键（H3 已证），差异只在 `capability_results` 内的历史数组，而本页对那些历史数组零消费（H4 已证）。这样 H3 / H4 / H5 / H13 四条合并为一个改动。

### R3（P1，补齐 H11 的根因）`/api/data-health` 的 3.2 s 是 `schtasks /query /fo csv /v` 子进程

`backend/app/services/data_health_service.py:602-609` 每次请求都 `subprocess.run(["schtasks", "/query", "/fo", "csv", "/v"])`。本机实测该命令 **2.8–2.9 s**，与端点 3.2 s 吻合；其余七个 DuckDB 检查项合计不到 0.4 s。这个子进程既没有缓存，也没有和 DuckDB 项并行。

**改写**：H11 的问题 1 已有答案；修法是对 `_scheduled_tasks_section()` 加进程内 TTL 缓存（60–300 s 都可接受，它反映的是每天一跑的计划任务状态），或让它走 `market_home_response_cache`。前端 `StockAnalysisDataHealthCard` 绕过 react-query 的问题独立存在，两边都要修。

### R4（P1，改写 H8 时区项、并修正 F13 的结论）新闻 `received_at` 全为 `+00:00`，且 65% 的记录根本没有日内时间

`.tmp-agent/market-overview-audit/news_tz.py` 对 `choice_news_event` 全表统计（1,075 行）：

| group_id | 行数 | `+00:00` | `+08:00` | 时间分布 |
| --- | --- | --- | --- | --- |
| `tushare_research` | 669 | 669 | 0 | **全部 `T00:00:00`** |
| `tushare_major` | 187 | 187 | 0 | 日内时间 |
| `tushare_news` | 167 | 167 | 0 | 日内时间 |
| `tushare_cctv` | 32 | 32 | 0 | **全部 `T00:00:00`** |
| `tushare_policy` | 20 | 20 | 0 | 日内时间 |

两个结论：

- 写入侧 `backend/app/tasks/tushare_news_ingest.py:194-205` 给 naive 时间戳打的是 `CHOICE_NEWS_VENDOR_TZ = +08:00`，而读出来全是 `+00:00`，说明列是 `TIMESTAMPTZ`、DuckDB 按 UTC 序列化——**时刻本身是对的**，`12:29+00:00` 就是北京 20:29。所以 F13 的"错位 8 小时"成立：前端直接取字符串小时位，坐标轴是 UTC 小时。展示层转 `Asia/Shanghai` 即可，不需要后端改存储。
- 更重要的是：**701 / 1,075（65%）的记录是日粒度**（研报、央视），时间戳是占位的零点。当前热力图把它们全部塞进 `00` 桶，导致"事件流入密度"最密的那一格是**数据结构的产物，不是接收密度**。任何密度计算都必须先把日粒度记录剔出小时分桶，单独计数。

**改写**：H8 的时区项从"后端确认 UTC 还是北京"改为"后端在密度聚合里区分 `date` / `datetime` 粒度并按 Asia/Shanghai 分桶"；F13 的结论从"轴无时区标注"升级为"最密一格是假象"。

### R5（改写 H9 的方向）后端已经有一份序列身份注册表，前端另有两份——现状是三处并存

- 后端 `backend/app/services/macro_vendor_service.py:82-87` 的 `_CHOICE_TERM_SPREAD_SERIES_IDS`：`canonical_field → (series_id 别名…)`，配 `_latest_choice_macro_point()` 的"取最新落地日上的首选别名、不做过期回退"规则，产出 `derived_spreads`（口径归 `core_finance/market_derived.py::calculate_spreads`）。
- 前端 `frontend/src/layouts/workbenchShellTicker.ts:92-100` 的 `shellTickerSeriesIdsByKey`：7 个壳层行情位的 `series_id` 白名单 + `series_name` 兜底。
- 前端 `frontend/src/features/workbench/module-home/marketOverviewDenseModel.ts:437-468` 的正则匹配（H9 原文）。

三处对同一件事（"10Y 国债是哪条序列"）各自维护，且答案已经不一致：后端 10Y 别名 `("E1000180", "EMM00166466", "CA.CN_GOV_10Y")`，壳层 `["CA.CN_GOV_10Y", "E1000180", "EMM00166466"]`（顺序不同 → 多源同日时选中的序列可能不同），市场总览则靠 `/10\s*(?:y|yr|year)|10\s*年/` 加"不含美英日"的启发式。

**改写**：H9 的方向不是"新建一套 slot 契约"，而是**把后端已有的别名注册表扩成模块级 slot 注册表**，并让前端两处都改为消费后端结果。

### R6（撤回）交接单 H8 里"USD/CNY 单位写反了"一条不成立

`中间价:美元兑人民币 = 6.7811`，单位 `CNY/USD` 的含义是"每 1 美元多少人民币"，量纲正确；报价对名称 `USD/CNY` 与单位 `CNY/USD` 本来就是互为倒写的两套记法。撤回该条，审计报告 §2.2 与交接单 H8 已同步更正。`index` 作为沪深300的单位透出属前端映射缺失（`/cross-asset` 已把 `index` 映射为「指数」，见 `CrossAssetPage.test.tsx:985-988`），移出后端交接范围。

### R7（补充证据）`/api/external-data/watermarks` 的 403 是 RBAC 判定，不是故障

`backend/app/api/routes/external_data.py:34` 走 `ensure_user_allowed`；当前身份在开发默认下是 `anonymous/viewer`（`backend/CLAUDE.md`：仓库没有认证层，身份来自 header / 环境变量 / 回退）。H12 的裁决问题保留，但答案的边界已清楚：这是"viewer 角色看不看得到水位"的产品决策，不是后端缺陷。

### 修订后的优先级

| 顺序 | 项 | 性质 | 改动面 |
| --- | --- | --- | --- |
| 1 | R1 驱动脚本 stderr + 回执活性 | 运维 / 脚本 | `daily_data_refresh.ps1` 一处；`macro_toolkit_refresh_receipt_service.py` 一处 |
| 2 | R2 页面改请求 `detail=core` | 前端一行 | `useMarketHomeQueries.ts`；`/macro-toolkit` 同理 |
| 3 | R3 `schtasks` 缓存 | 后端一处 | `data_health_service.py` |
| 4 | §2 模块级读 `market.snapshot` | 后端新增 + 前端切换 | 见 §2、§3 |
| 5 | H2 / H6 / H12 / H15 | 口径与契约裁决 | 文档 + owner |

前三项加起来不超过一天，且在 §2 动工前就能让页面从"暂停判断"回到正常状态。

---

## 2. 模块级后端计算：`market.snapshot`

### 2.1 为什么是"模块级读"，而不是继续修六条读

`/market-overview` 首屏现在的做法是：六条通用读（合计解压后 1.85 MB）拉到浏览器，再由 `moduleHomeModel.ts`（150 KB 源码）、`marketOverviewDenseModel.ts`、`marketDeskIntelModel.ts`、`marketActionQueueModel.ts` 四个文件在主线程上做选序列、算变动、分桶、判 gate、排队列。这层计算有三个结构性问题，修任何单条读都解决不了：

1. **身份解析在前端**（R5）。序列该是哪条、指标该是哪个槽位，是数据治理问题，不该由展示层正则决定。
2. **gate 判定在前端**（F1）。`buildMacroObservationGate` 用 `quality_flag !== "ok"` 一刀切，把后端 `tone: "missing"` 的安全结论也压掉了；同屏另一条渲染链（`briefings`）又不走这个 gate。两条链没有同一个真值来源。
3. **日期口径在前端**（F14 / H14）。页头"行情 2026-08-28"是前端从 211 条序列里取 max 得来的，掩盖了同屏格子横跨 08-25～08-28 的事实。

仓库里已经有两个成熟的模块级组合读可以照抄：

- `home.snapshot`（`backend/app/services/executive_service.py:3701`）：跨域取日期上下文 → 算统一 `report_date` 与 `domains_missing` → 组合子信封 → 聚合子信封的 `quality_flag` / `vendor_status` → 单一 `result_meta`。
- `stock-analysis/workbench`（`backend/app/services/market_data_livermore_route_support.py:119`）：`include=` 分区、`market_home_response_cache.get_or_build_with_status` 带状态缓存、指纹进缓存键。

`market.snapshot` 就是把这两个模式套到市场模块上。

### 2.2 端点与放置

| 项 | 取值 |
| --- | --- |
| 路由 | `GET /ui/market-overview/snapshot`，新文件 `backend/app/api/routes/market_overview.py`，`APIRouter(prefix="/ui/market-overview", tags=["market-overview"])`，在 `backend/app/api/__init__.py` 注册 |
| 参数 | `include`（逗号分隔，默认 `gate,dates,tape,pulse,crisis,signals,news,actions`；`charts` 为可选分区，见 2.4） |
| 授权 | 复用 `macro_toolkit` 的 `_ensure_macro_toolkit_read_allowed` 语义（本页所有源读都在 `macro_toolkit` / `market-data` 读权限之下，不新增资源名） |
| 服务 | 新文件 `backend/app/services/market_overview_service.py`，只做**组合与选择**；任何新的数值口径（利差、变动）都调用 `core_finance/market_derived.py` 既有函数，服务层不写公式 |
| 信封 | `build_result_envelope(basis="analytical", result_kind="market.snapshot", formal_use_allowed=False, …)`；`source_surface` 按 `result_meta.py` 的 governed-prefix 规则填 |
| 缓存 | `market_home_response_cache`，键 `market-overview/snapshot::{include}::{receipt_fingerprint}::{duckdb}`，TTL 沿用默认 300 s；并把它追加到 `warm_market_home_read_caches()` 的 steps 末尾（放在其五个组件之后，组件已热时组合几乎零成本） |
| 数据访问 | 只读组件信封（下节），不直接开 DuckDB 连接；API/service 路径保持只读 |

### 2.3 组件输入

服务从缓存层取五个已有信封（键与预热器完全一致，这是 R2 教训的直接应用）：

| 组件 | 缓存键 | 用途 |
| --- | --- | --- |
| `choice_latest` | `market_home_choice_latest_cache_key(duckdb)` | 分析口径序列（权益、商品、汇率、部分利率） |
| `market_rates` | `market_home_rates_cache_key(duckdb)` | 正式口径利率与曲线 |
| `macro_analysis_core` | `market_home_macro_analysis_cache_key(duckdb, "core", freshness_fingerprint=…)` | 结论、信号卡、指标、`crisis_score_cn` 能力结果、回执健康 |
| `macro_strategy_summaries` | `market_home_strategy_summaries_cache_key(duckdb)` | 仅供 03 区图表；首屏分区不读它 |
| 新闻 | 直接调 `choice_news_service` 的查询函数拿最近 N 条（不经 HTTP 信封），N 与现页一致取 500 | 密度、最新事件、`compare` |

任一组件缺失或 `quality_flag != ok` 时，**不中断**：对应分区输出 `status: "unavailable" | "degraded"` 与 `reason`，并进入顶层 `components` 表（对应 `home.snapshot` 的 `domains_missing` / `degraded_components`）。

### 2.4 输出分区

所有分区都是**观察性**的，顶层 `formal_use_allowed=false`；只有 `tape` 里的单个槽位携带自己来源信封的 `basis`（利率槽位来自 `market_rates` 时为 `formal`），前端据此给格子打"正式/分析"角标。

**`gate`** — 首屏判断位的唯一真值（替代前端 `buildMacroObservationGate` 与 `briefings` 两条链）。

```
{
  level: "ok" | "review" | "blocked",
  reason_code: "none" | "refresh_receipt_abandoned" | "refresh_receipt_blocked"
             | "quality_warning" | "source_unavailable",
  human_reason: string,          // 后端原文，前端不再自造
  recovery_action: string,       // 例："重跑 MOSS-DailyDataRefresh 并确认回执 status=success"
  conclusion: { stance, tone, summary, recommended_action },   // 原样透出，含 tone=missing
  evidence: { receipt_status, receipt_generated_at, receipt_age_hours, missing_field_count }
}
```

判级规则：回执 `running` 且 `age_hours > 6` → `blocked / refresh_receipt_abandoned`；回执 `blocked` → `blocked / refresh_receipt_blocked`；组件 `quality_flag = warning` 但回执 `ready` → `review / quality_warning`（**不阻断**，这是对 H2 的建议答案：`warning` 展示结论并标"需复核"，`error`/回执失败才阻断）。

**`dates`** — 不再给单一"行情日期"。

```
{
  surfaces: [
    { key: "rates_formal",  latest: "2026-08-28", age_days: 5, source: "market_rates" },
    { key: "choice_latest", latest: "2026-08-28", age_days: 5 },
    { key: "macro_analysis", latest: "2026-08-28", age_days: 5 },
    { key: "news",           latest: "2026-08-27", age_days: 6, basis: "received_at" },
    { key: "strategy",       latest: "2026-08-24", age_days: 9 }
  ],
  tape_span: { earliest: "2026-08-25", latest: "2026-08-28" },   // 8 个格子的日期跨度
  computed_on: "2026-09-02"
}
```

`age_days` 用自然日，注明 `date_basis`；不做交易日换算（那是另一个口径问题）。

**`tape`** — 8 个头条槽位，由后端注册表解析。

```
MARKET_OVERVIEW_TAPE_SLOTS = (
  Slot("gov_10y",       "10Y国债",   aliases=("E1000180","EMM00166466","CA.CN_GOV_10Y"), kind="rate",      prefer="rates"),
  Slot("dr007",         "DR007",     aliases=("CA.DR007","M002","EMM00167613"),           kind="rate",      prefer="rates"),
  Slot("omo_7d",        "7D逆回购",  aliases=("EMM00088132","M001"),                      kind="rate",      prefer="rates"),
  Slot("shibor_3m",     "SHIBOR 3M", aliases=("NCD.SHIBOR.3M",),                          kind="rate",      prefer="rates"),
  Slot("csi300_close",  "沪深300",   aliases=("CA.CSI300",),                              kind="equity",    change_from="csi300_pct_chg"),
  Slot("brent",         "Brent原油", aliases=(<待补：当前正则命中的 series_id>,),         kind="commodity"),
  Slot("usd_cny_mid",   "USD/CNY",   aliases=("EMM00058124","CA.USDCNY"),                 kind="fx"),
  Slot("copper_main",   "铜主力",    aliases=("CA.COPPER",),                              kind="commodity"),
)
```

解析规则复用 `_latest_choice_macro_point()` 的语义：在 `prefer` 指定的信封里，取**最新落地日**上的首选别名，不做过期回退；解析不到就输出 `status: "unresolved"`，**不**退回名称匹配（名称匹配正是要淘汰的东西）。每个槽位输出 `value, unit, change, change_unit, trade_date, series_id, series_name, vendor, basis, quality_flag, tone_hint`。`tone_hint` 只区分 `up/down/flat/unavailable`，颜色语义（利率上行=琥珀）留给前端 DESIGN 决议。

别名表的初始值从三处现有来源合并：后端 `_CHOICE_TERM_SPREAD_SERIES_IDS`、壳层 `shellTickerSeriesIdsByKey`、以及本次审计 `source_checks` 实际命中的 `E1000180 / CA.DR007 / EMM00088132 / NCD.SHIBOR.3M / CA.CSI300 / CA.COPPER`。Brent 与 USD/CNY 变动的稳定 `series_id` 需要 Fable 从目录表核出来填上——**这是本方案唯一需要人工确认的数据事实**。

**`pulse`** — 指标变动表 4 槽，按 `indicators[].key` 绑定（CPI / PPI / PMI / 社融的 key 由 `_analysis_indicators` 定义，后端知道），输出 `previous_value, latest_value, change, change_kind: "absolute" | "pct", latest_date, source`。不再用 `/\bcpi\b|居民消费价格/` 猜。

**`crisis`** — `capability_results[key=crisis_score_cn]` 的摘要：`score, regime, percentile, data_status, delta: { window_points, score_delta, percentile_delta }`。差值在后端算，**不输出历史数组**；前端如需 sparkline，另加 `include=crisis_sparkline` 返回 ≤ 20 点。这一项是 H4 的落地。

**`signals`** — `signal_cards` 原样，但每张卡带后端给的 `kind: "market_signal" | "ops_status"`（`outputs` 那张是运维态），前端删掉 `OPS_SIGNAL_PATTERN` 正则。

**`news`** — 密度与摘要（对应 H7 / R4）：

```
{
  sample: { requested: 500, returned: 500, total_rows: 1075, excluded_future_rows: 0,
            latest_received_at: "2026-08-27T20:29:46+08:00", stale_days: 6 },
  granularity: { datetime_rows: 374, date_only_rows: 126 },   // 样本内
  density: { tz: "Asia/Shanghai", bucket_hours: 2,
             topics: [{ key, label, cells: [12 ints] }],       // 仅 datetime_rows
             max_count: 17 },
  latest: [ { event_key, received_at, topic_code, group_id, summary } ×3 ],
  compare: { same_direction: 1, conflicting: 0, review_needed: 5, candidate_scenarios: 5,
             review_items: [ …前 5 条，供核验队列… ] }
}
```

日粒度判定：`received_at` 在 `Asia/Shanghai` 下恰为 `00:00:00` 且所属 `group_id` 为日频源（`tushare_research` / `tushare_cctv`），标 `date_only`。更稳的做法是在 ingest 写入 `time_granularity` 列，但那是 schema 改动、属保护边界，本方案不做，先用服务层推断并在 `result_meta.filters_applied` 里写明规则。

**`actions`** — P0–P2 核验队列，后端生成，规则显式、可测：

| 优先级 | 触发 | 入口 |
| --- | --- | --- |
| P0 | `gate.level = blocked` | `/macro-toolkit`（恢复刷新） |
| P1 | `news.compare.review_needed > 0` | `/news-events` |
| P1 | `tape` 中任一 `rate` 槽位 `abs(change) ≥ 5bp` | `/market-data` |
| P2 | `crisis.regime` 非 `normal` 或 `percentile ≥ 90` | `/macro-toolkit` |
| P2 | `dates.surfaces` 任一 `age_days ≥ 5` | 对应子页 |

这是"核验队列"不是"交易指令"，每条带 `basis: "analytical"` 与证据字段；阈值放在服务层常量，写进 `docs/page_contracts.md` §14.6。

**`charts`（可选分区）** — 02 区 A/B/C/D 四张图的紧凑序列（曲线最新一致日、关键利率 20 期、跨资产最新变动、流动性期限）。第一版**不做**：前端 `marketFinancialChartsModel.ts` 已能从组件信封画图，且 03 区 12 张图仍需全量序列。等 03/04 区改为惰性读之后再评估是否值得下沉。

### 2.5 `result_meta` 聚合规则

照 `home.snapshot`：

- `quality_flag`：任一必需组件 `!= ok` 或 `gate.level != ok` → `warning`；`gate.level = blocked` 且 `reason_code` 为回执类 → 仍是 `warning`（数据在，判断被停），只有 `choice_latest` 与 `market_rates` 双双缺失才 `error`。
- `vendor_status`：组件里最差的一个。
- `as_of_date`：**不填**单一值（避免重蹈页头假日期），改在 `filters_applied.dates` 放 2.4 的 `dates` 分区摘要；`date_basis = "per_surface"`。
- `source_version` / `vendor_version`：用 `_aggregate_lineage_value` 聚合，但**加长度上限**：超过 8 段时收为 `sha256[:12]` 指纹 + `filters_applied.lineage_segments` 计数。这是 H10 里 `result_meta` 6.3 KB 的直接修法，也顺带修了 `choice_latest` 自己的信封。
- `tables_used`：组件并集。
- `cache_key`：填实际缓存键，便于运维核对预热是否命中。

### 2.6 前端切换后的形态

| 区 | 现在 | 切换后 |
| --- | --- | --- |
| 01 分析观察 | 6 条读 + 四个 model 文件派生 | `getMarketOverviewSnapshot()` 一条读；`gate` / `dates` / `tape` / `signals` / `actions` 直接渲染 |
| 02 市场证据 | 同上 | `pulse` / `news` / `crisis` 直接渲染；A–D 图暂仍由 `marketFinancialChartsModel` 基于 `rates` / `latest` 信封绘制（这两条读保留，但改为 `enabled: 进入 02 区视口后`） |
| 03 金融图表 | 同上 | 五条组件读**惰性**（`IntersectionObserver` 到 03 区才 enable），`detail=core` |
| 04 数据核验 | 六条读全量 | 每个 tab 惰性拉自己那条（新闻 tab 已是此模式，照抄） |

删除：`buildDenseTapeMetrics`、`buildDenseMacroPulseRows`、`buildDenseNewsDensity`、`buildMacroObservationGate`、`OPS_SIGNAL_PATTERN`、`buildActionQueue`（`marketActionQueueModel.ts` 整文件）、`marketDeskIntelModel.ts` 里的 `crisisHistoryDelta`。保留：所有纯格式化函数（`formatChoiceMacroValue`、`compactNumber`、tone 映射）。`useMarketHomeQueries` 保留但组件读全部加 `enabled` 门。

壳层 `WorkbenchShellMarketTicker` 第二步再切到 `tape`（它需要的 7 个位里 5 个与 `tape` 重合），本方案不强求。

---

## 3. 实施分期与验收

### Phase 0 — 止血（不涉及 §2，建议今天）

| # | 改动 | 文件 | 验收 |
| --- | --- | --- | --- |
| 0.1 | 子进程调用不再让 stderr 触发终止：把 `& $PythonExe @stepArgs 2>&1` 改为局部 `$ErrorActionPreference = "Continue"` 包裹，或改用 `Start-Process -RedirectStandardError` 分流后再合并进日志 | `scripts/scheduling/daily_data_refresh.ps1:317` | 用 `.tmp-agent/market-overview-audit/ps_stderr_probe.ps1` 的写法改造后 `driver-exit=0` 且 stderr 行进日志；手动触发 `MOSS-DailyDataRefresh` 一次，日志出现 `-- summary --` |
| 0.2 | 回执活性：`load_macro_toolkit_refresh_receipt_health()` 对 `status=running` 增加 `generated_at` 年龄判断，`> 6h` 归为新状态 `abandoned`，`missing_fields` 加 `receipt.abandoned_running`，`blocking_messages()` 文案说明"上次刷新未完成（已 N 小时）" | `backend/app/services/macro_toolkit_refresh_receipt_service.py:96-205` | 新增 `tests/test_macro_toolkit_refresh_receipt_service.py::test_running_receipt_older_than_six_hours_is_abandoned`；现有回执测试全绿 |
| 0.3 | 页面改请求 `detail=core`，删 `history_limit` | `frontend/src/features/workbench/module-home/useMarketHomeQueries.ts:37-51`；`/macro-toolkit` 的 `full` 读同理评估 | `ModuleWorkbenchHomePage.test.tsx:2738-2742` 与 `ModuleWorkbenchHomeModel.test.ts:3204-3208` 两处断言同步改；Resource Timing 下 `analysis` 读 < 500 ms 且命中预热键 |
| 0.4 | `schtasks` 结果进程内缓存（TTL 120 s） | `backend/app/services/data_health_service.py:536-617` | `/api/data-health` 热态 < 500 ms；`tests/test_data_health*.py` 全绿 |
| 0.5 | `StockAnalysisDataHealthCard` 改 `useQuery`（`staleTime: 60s`） | `frontend/src/features/stock-analysis/components/StockAnalysisDataHealthCard.tsx` | 单次加载 `/api/data-health` 请求数 = 1 |

Phase 0 完成后重跑 `.tmp-agent/market-overview-audit/probe_market_overview.py` 与 `timing.mjs`，预期：首屏 hero 不再"暂停判断"（回执恢复后），`analysis` 读 < 500 ms，`/stock-analysis` 收敛 < 3 s。

### Phase 1 — 后端模块级读（不切前端）

1. `market_overview_service.py`：`build_market_snapshot(include, *, duckdb_path, refresh_receipt_health) -> dict`，按 §2.3–2.5 实现；slot 注册表放同文件顶部常量。
2. `api/routes/market_overview.py` + `api/__init__.py` 注册；`scripts/api_contract_check.py export-openapi` 重新导出，`npm run lint:openapi` 通过。
3. `market_home_warmup_service.py` steps 末尾追加 snapshot。
4. 测试 `tests/test_market_overview_snapshot_api.py`：
   - 分区完整性与 `include` 过滤；
   - gate 三级各一条（用假回执文件）；
   - slot 解析：同一 `series_id` 多源同日取首选别名、无匹配为 `unresolved` 且**不**名称回退；
   - `dates.tape_span` 与逐槽 `trade_date` 一致；
   - 新闻密度：日粒度行不进小时桶、桶按 Asia/Shanghai（用一条 `12:29+00:00` 的样本断言落在 `20` 桶）；
   - 组件缺失时分区 `unavailable` 且顶层 `quality_flag` 正确；
   - `result_meta.source_version` 长度上限。
5. **影子比对**（切换前的关键闸门）：一次性脚本 `scripts/shadow_compare_market_snapshot.py`，对当前 DuckDB 同时跑新 `tape` 与旧前端正则（把 `buildDenseTapeMetrics` 的匹配逻辑移植成 Python 或直接读浏览器 DOM），逐槽比对 `series_id` 与 `trade_date`。任何不一致都要在切换前给出结论（是旧正则错了，还是别名表漏了）。

### Phase 2 — 前端切换 + 负载瘦身

1. `marketDataClient.ts` 增 `getMarketOverviewSnapshot(include?)`；mock client 补对应 fixture。
2. 01/02 区改读 snapshot；03/04 区组件读加 `enabled` 门（§2.6）。
3. 删除 §2.6 列出的派生代码及其测试；`MarketOverviewDenseFirstScreen.test.tsx` 改为对 snapshot fixture 渲染断言。
4. 契约文档：`docs/page_contracts.md` §14.6 C（数据链改为 snapshot + 惰性组件读）、D（日期口径改为 per-surface）、E（新增 slot 注册表，标明 analytical、非 `MTR-*`）；`docs/metric_dictionary.md` §12.2 页面级绑定处加一行指向；`docs/live_route_maturity.md` 的验证命令追加新测试文件。
5. 门禁：主页面 vitest 组 + `market-overview-smoke.spec.mjs` + `tests/test_live_route_page_contract_completeness.py` + 新增 API 测试。

验收数字（用现有取证脚本复测）：首屏后端读 ≤ 2 条、解压后 ≤ 200 KB；`analysis` 相关读 < 500 ms 热态；1440 视口 DOM 节点数下降（04 区惰性后应 < 3,000）；axe 不新增违规。

### Phase 3 — 可选

- 壳层行情条切到 `tape`；`/cross-asset` 去掉 `refetchOnMount: "always"`（S5）。
- 若其他页也要新闻密度，把 §2.4 `news` 抽成 `choice_news_service.density()` 复用。
- `DEFAULT_CRISIS_SCORE_HISTORY_LIMIT = 430` 是否仍有消费方，无则收窄。

---

## 4. 边界与不做的事

- **不改 schema**（`time_granularity` 列留待另议）、不改 RBAC、不动 `core_finance/`（本方案对正式金融路径的影响：**无**——所有数值口径调用既有函数，`derived_spreads` 的计算位置不变）。
- 不修改 `home.snapshot`、`stock-analysis/workbench` 或任何其他页的读；壳层行情条切换列为 Phase 3 可选。
- 不发明统一业务日：`dates` 分区逐面披露，页头由前端展示 `tape_span` 的两端。
- 不把 `actions` 写成交易指令：它是核验队列，每条带 `basis` 与证据。
- Phase 1 完成前不切前端；影子比对（Phase 1.5）没有结论前不删任何前端正则。

## 5. 风险

| 风险 | 缓解 |
| --- | --- |
| 别名表漏项，某槽位 `unresolved` | Phase 1.5 影子比对；前端对 `unresolved` 渲染"未绑定"而非空白 |
| 回执 `abandoned` 阈值 6 h 误判长任务 | 阈值进 settings，默认 6 h；`blocking_messages` 明说年龄 |
| snapshot 缓存与组件缓存不同步 | 键含 `receipt_fingerprint`；预热顺序组件先、snapshot 后；`invalidate()` 走同一 generation |
| 日粒度推断误伤真正零点发布的新闻 | 仅对 `tushare_research` / `tushare_cctv` 两个日频源生效，规则写入 `filters_applied` |
| 前端切换期间两套并存 | Phase 2 一次性切换 01/02，不做 feature flag 双跑 |

## 6. 证据与脚本

`.tmp-agent/market-overview-audit/`：`ps_stderr_probe.ps1`（R1 复现）、`news_tz.py`（R4 统计）、`slow_endpoints.py` / `contention.py`（R3、S4 计时）、`detail_cost.py`（R2 键差异）、`payload_weight.py`（H10）。调度证据在 `scripts/scheduling/logs/2026082[8-9].log`、`20260830.log`–`20260901.log` 与 `data/logs/*_receipt.json`。
