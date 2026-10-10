# 给 Codex 的启动指令（每个工作包一条，直接粘贴）

前提：Codex 的工作目录必须是仓库根 `F:\MOSS-V3`（任务书里的验证命令、`.tmp-agent/` 取证脚本都是仓库相对路径）。任务书的**权威副本在仓库内** `docs/plans/2026-09-02-market-overview-fix-dispatch/`，桌面上的是给人看的拷贝；指令里一律写仓库内的绝对路径。

派发顺序与并行约束见同目录 `README.md` §1；泳道内顺序执行、泳道间可并行。所有包共用的收尾要求已经写进每份任务书的「报告要求」，这里不再重复。

---

## L1 后端/运维（Fable 5.1）

### WP-A1

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-A1-scheduler-driver.md。
只改任务书「改动范围」列出的文件；「不得触碰」清单里的任何一项都不要动，尤其不要运行 schtasks /run 或非 DryRun 的 daily_data_refresh.ps1。
先用 .tmp-agent\market-overview-audit\ps_stderr_probe.ps1 复现问题，再改，再用同一脚本证明修复。
文件含中文注释，写回必须走 Node fs 或编辑器，不得用 PowerShell 文本 cmdlet / 重定向。
完成后按任务书「报告要求」输出：根因、改动文件、验证命令与结果、剩余风险、对 core_finance 的影响。
```

### WP-A2

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-A2-receipt-liveness.md。
先补任务书列出的 3 个 pytest 用例并确认它们红，再改实现让它们绿；现有用例一条都不能变红。
「不得触碰」清单里的校验常量与前端文件不要动；核对前端字面量分支那一步只看不改，结果写进报告。
完成后按「报告要求」输出。
```

### WP-B2（在 WP-G 之前）

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-B2-warmup-key-alignment.md。
只在 market_home_warmup_service.py 追加一步预热，不改缓存键函数、不重构 steps 结构。
完成后按「报告要求」输出。
```

### WP-C1

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-C1-data-health-cache.md。
复用 backend/app/observability/response_cache.py 的 TTLResponseCache，不要自写缓存；现有测试之间会互相命中缓存，按任务书加清缓存 fixture。
完成后按「报告要求」输出。
```

### WP-G（在 WP-A2、WP-B2 之后）

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-G-market-snapshot-backend.md，
字段级定义以 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-module-compute-plan.md §2 为准。
G0 需要人工确认两个 series_id：核不出来就把槽位标 unresolved，不要用名称匹配兜底。
组件只从 market_home_response_cache 取，键用 response_cache.py 的既有函数；不写任何金融公式，对 core_finance/ 的影响必须为无。
按 G1→G2→G3→G4→G5 顺序做，G5 影子比对表 8 行必须每行有结论，它是 WP-H 能否开工的依据。
不改前端、不改 schema、不改 RBAC。完成后按「报告要求」输出，附影子比对表。
```

## L2 前端·市场页（同一会话先 B 后 D）

### WP-B

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-B-market-page-queries.md。
注意任务书列出的三处源码字符串断言测试必须同步改；docs/page_contracts.md 只改 §14.6-C 那一句，:1617/:1634 是 /macro-toolkit 页的条目不要动。
不改 /macro-toolkit 页的 detail:"full"，不改 ModuleWorkbenchHomePage.tsx 的键。
完成后按「报告要求」输出。
```

### WP-D（WP-B 合入后，同一会话继续）

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-D-first-screen-render-fixes.md，D1–D5 逐条做、逐条验收。
这是过渡期修法，只求不自相矛盾、数字不撒谎、控件不失效，不做重构；D1 只改 hero 侧，若判断必须改 moduleHomeModel.ts 的 briefings 就停下写进报告，不要顺手改。
跑完任务书里的 vitest 组与 market-overview-smoke.spec.mjs，再复跑 .tmp-agent\market-overview-audit\audit2.mjs 与 audit3.mjs（复制到 frontend\.tmp-audit\ 下执行）对照验收字段。
完成后按 D1–D5 逐条输出「报告要求」。
```

## L3 前端·子页面（同一会话先 E 后 F）

### WP-E

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-E-subpage-frontend.md，E1–E3 逐条做。
E2 只改 liveRouteReadinessContracts.ts:158 一行，不改 StockAnalysisPageImpl.tsx；E3 改色前先读 DESIGN.md，不新增色值、不改字号，把你对 §11 决议是否适用壳层的判断写进报告。
主页面 vitest 组要从 175/176 变成 176/176。完成后按「报告要求」输出。
```

### WP-F（WP-E 之后）

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-F-cross-page-choice-latest-reads.md。
改键前先核 CrossAssetPage.test.tsx 与 MarketDataPage.test.tsx 里对 getChoiceMacroLatest 调用次数的断言；useMarketDataPageData.ts:253-256 的 getQueryData 键要一起改。
完成后按「报告要求」输出，写明轮询叠加到壳层行情条这一行为变化。
```

## L4 前端·股票页

### WP-C2

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-C2-data-health-card-query.md。
保留 loadHealth 注入口与四态语义；测试要包 QueryClientProvider（照 StockPortfolioConstructionPage.test.tsx:159-179 的 Wrapper），并新增 StrictMode 下只调用一次的用例。
完成后按「报告要求」输出。
```

---

# 第二批（第一批已于 2026-09-02 15:40 全部验收通过，见 README §5）

## OPS（**WP-J 合入后再派**——用户裁决先修锁重试再重跑；派时仓库里不能有 pytest 在跑）

### WP-OPS

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-OPS-rerun-daily-refresh.md。
本包是唯一允许运行 schtasks /run /tn MOSS-DailyDataRefresh 的包；先做前置检查（没有 pytest / release suite / 刷新任务在跑，receipt 里没有 running），任何一项不满足就停下报告。
读日志与 JSON 一律用 Node fs 或 Python，不用 PowerShell 文本 cmdlet。
不改任何代码。完成后按「报告要求」输出：summary 全文、三份回执关键字段、gate 状态、hero 文案。
```

## L1 后端（Fable 5.1；I → K 同会话，J 可另开）

### WP-I

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-I-snapshot-crisis-full-component.md。
只改 market_overview_service.py 与 tests/test_market_overview_snapshot_api.py；gate/pulse/signals 继续读 core，只有 crisis（及 actions 对 crisis 的依赖）改读 full；full 组件的键与 builder 必须与 market_home_warmup_service 的 macro_analysis_full 步完全一致。
不改 detail 语义、不改前端。完成后按「报告要求」输出，附 curl 结果。
```

### WP-J

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-J-policy-rate-step-lock-retry.md。
根因有两层（锁文本不匹配 + 错误被吞进返回值），两层都要修；先补三条 pytest 用例并确认红，再改实现让它们绿。
不改 backfill_crisis_score_inputs.py、不改 REQUIRED_STEPS、不触发 schtasks /run。完成后按「报告要求」输出。
```

### WP-K（WP-I 之后）

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-K-cold-reads-warmup.md。
核心约束只有一条：预热的缓存键必须与页面实际请求的键逐字符相同——signal-confluence 的 as_of_date 取 Livermore strategy 解析后的 as_of_date，macro-bond-linkage 的 report_date 取 choice_latest 里跨资产头条槽位的最大 trade_date；推导不出来就不预热并打日志，不要猜。
键函数与 builder 从路由模块导入或下沉到 route_support，不要复制实现。不改两条读的计算口径。
完成后按「报告要求」输出，并给 H16 第 2 问一个粗结论（23–28 s 花在哪一层）。
```

## L2 前端（WP-I 合入后才派）

### WP-H

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-H-frontend-switch.md。
开工前先做「开工前必核」三项，crisis.status 不是 ok 就停下。
响应契约以 backend/app/services/market_overview_service.py 的 _build_* 返回结构为准，不凭方案文档臆测字段名；新方法要按 ApiClientCompositionBoundary.test.ts 的守卫登记进正确的域集合。
按 H1→H6 顺序做；H5 每删一个函数先 rg 确认无第二消费方；不改后端、不改壳层行情条、不改 DESIGN 决议。
完成后按 H1–H6 逐条输出「报告要求」，附 timing.mjs / hero-facts.mjs 复测数字。
```

## 收尾（所有包停手、且用户确认另一个 Cursor 会话已停手之后）

### WP-COMMIT

```
阅读并执行 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\WP-COMMIT-scoped-commits.md。
这个工作树里有几百个与本次无关的历史未提交改动：只用 git add -- <任务书表格里的显式路径>，每组一个 commit，提交前 git diff --cached --stat 的文件数必须等于该组路径数；严禁 git add -A / git add . / commit -a / stash / checkout -- / reset / --no-verify，不动 .git/ 里任何文件。
某文件 diff 里混着与该组主题无关的改动时，把它移出本组并在报告里列出，不要拆 hunk。
每组提交前跑该组门禁，红了停下。完成后按「报告要求」输出每组哈希与文件数。
```

## 收口复测（WP-H 合入后，一个会话或人）

```
阅读 F:\MOSS-V3\docs\plans\2026-09-02-market-overview-fix-dispatch\README.md §3，跑全部集成门禁并用 .tmp-agent\market-overview-audit\ 下的脚本复测 §3 表格里的每个指标，输出修前/修后对照表。任何门禁变红先停下报告，不要自行修改。
```
