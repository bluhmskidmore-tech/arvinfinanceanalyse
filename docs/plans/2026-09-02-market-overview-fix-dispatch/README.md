# 市场工作台修复 · 子代理工作包总览

- 日期：2026-09-02
- 来源：`docs/audits/2026-09-02-market-overview-page-audit.md`（F1–F25、S1–S11）、`docs/plans/2026-09-02-market-overview-module-compute-plan.md`（R1–R7、§2 `market.snapshot`）
- 用法：每个 `WP-*.md` 是一份自包含的任务书，直接作为一个独立会话的首条指令投递（"请阅读并执行 `docs/plans/2026-09-02-market-overview-fix-dispatch/WP-A1-scheduler-driver.md`"）。任务书里写了范围、根因、文件行号、不得触碰、验收、验证命令与报告要求，接手方不需要读审计全文。

## 0. 先说清楚的三件事

1. **同一泳道内的包必须顺序执行，不同泳道可以并行。** 泳道按文件所有权划分（§2 矩阵），保证并行的包之间没有共同文件，不会产生合并冲突。
2. **所有包共享同一条基线**：主页面 vitest 175/176（唯一红灯属 `/stock-analysis`，由 WP-E 修）、子页面 vitest 493/494（唯一红灯是并行超时假红）、`npm run lint` / `npm run typecheck` 干净。任何包都不得让基线变差；修红灯是 WP-E 的职责，其他包不要顺手碰。
3. **有四件事代理做不了，需要人**：见 §4。其中"手动触发一次日更任务"是让页面从"暂停判断"恢复的必要动作，代理修完 WP-A1 后只能等 18:45 的定时触发，人可以立刻跑。

## 1. 工作包与泳道

| 泳道 | 顺序 | 包 | 一句话 | 层 | 难度 | 建议承接 |
| --- | --- | --- | --- | --- | --- | --- |
| L1 后端/运维 | 1 | [WP-A1](WP-A1-scheduler-driver.md) | 日更调度驱动脚本被子进程 stderr 杀死，修一处 | PowerShell | 低 | Fable 5.1（用户指定后端归它） |
| L1 | 2 | [WP-A2](WP-A2-receipt-liveness.md) | 刷新回执 `running` 六天仍被当作"正在跑"，加年龄判定 | Python | 中 | Fable 5.1 |
| L1 | 3 | [WP-B2](WP-B2-warmup-key-alignment.md) | 预热器补 `detail=full` 键，`/macro-toolkit` 不再吃 3.7 s 冷计算 | Python | 低 | Fable 5.1 |
| L1 | 4 | [WP-C1](WP-C1-data-health-cache.md) | `/api/data-health` 每次请求 shell 出 `schtasks`（2.9 s），加 TTL 缓存 | Python | 低 | Fable 5.1 |
| L1 | 5 | [WP-G](WP-G-market-snapshot-backend.md) | 模块级读 `GET /ui/market-overview/snapshot`（方案 §2） | Python | 高 | Fable 5.1 |
| L2 前端·市场页 | 1 | [WP-B](WP-B-market-page-queries.md) | 市场总览改请求 `detail=core`、去 `history_limit`、与壳层共享 `choice-latest` 缓存 | TS | 低 | 前端代理 |
| L2 | 2 | [WP-D](WP-D-first-screen-render-fixes.md) | 首屏 5 个 P0 渲染缺陷（gate 自相矛盾、tooltip 精度、`-0`、0 张图、死按钮） | TS/TSX | 中 | 前端代理 |
| L3 前端·子页面 | 1 | [WP-E](WP-E-subpage-frontend.md) | `/news-events` 移动端 176k px、`/stock-analysis` 契约锚点红灯、壳层行情条对比度 | TS/CSS | 中 | 前端代理 |
| L3 | 2 | [WP-F](WP-F-cross-page-choice-latest-reads.md) | `/cross-asset`、`/market-data` 对同一序列读两遍 | TS | 低 | 前端代理 |
| L4 前端·股票页 | 1 | [WP-C2](WP-C2-data-health-card-query.md) | `StockAnalysisDataHealthCard` 绕过 react-query，一页发 2–4 次请求 | TSX | 低 | 前端代理 |
| 阻塞 | — | [WP-H](WP-H-frontend-switch.md) | 前端切到 `market.snapshot`（方案 Phase 2） | TS/TSX | 高 | **等 WP-G 完成再派** |

### 第二批（2026-09-02 16:20 起，第一批全部验收通过后）

| 泳道 | 顺序 | 包 | 一句话 | 层 | 难度 | 前置 |
| --- | --- | --- | --- | --- | --- | --- |
| OPS | 2 | [WP-OPS](WP-OPS-rerun-daily-refresh.md) | 重跑日更任务、核三份回执、确认 hero 离开「暂停判断」（**唯一允许 `schtasks /run` 的包**） | 运维 | 低 | **WP-J 合入后**（用户 16:30 裁决：先修锁重试再重跑），且仓库里没有 pytest 在跑 |
| L1 后端 | 1 | [WP-I](WP-I-snapshot-crisis-full-component.md) | snapshot 的 `crisis` 分区改读 `full` 组件（`core` 的 `capability_results` 为空） | Python | 低 | — |
| L1 | 2 | [WP-J](WP-J-policy-rate-step-lock-retry.md) | `choice_policy_rate_7d` 撞 Windows 文件锁不重试（中文错误文本不匹配 + 错误被吞进返回值） | Python | 低 | — |
| L1 | 3 | [WP-K](WP-K-cold-reads-warmup.md) | `macro-bond-linkage` / `signal-confluence` 冷计算 23–28 s 进预热（H16） | Python | 中 | WP-I（同文件） |
| L2 前端 | 1 | [WP-H](WP-H-frontend-switch.md) | 前端切到 `market.snapshot`，删派生代码，03/04 惰性 | TS/TSX | 高 | **WP-I 合入** |
| 收尾 | — | [WP-COMMIT](WP-COMMIT-scoped-commits.md) | 按 10 组显式路径提交，严禁 `git add -A` | git | 低 | 所有包停手 + 另一个会话已停手 |

WP-J 与 WP-I/K 无共同文件，可另开会话并行；WP-K 与 WP-I 共用 `market_home_warmup_service.py`，同会话先后。WP-H 只能在 WP-I 合入后派。WP-COMMIT 最后。

L1–L4 四条泳道可同时开工。L1 内 A1→A2→B2→C1 都很小，G 最大；如果想再并行，A1/A2 与 C1 没有共同文件，可以拆成两个会话，但 B2 与 G 都碰 `market_home_warmup_service.py`，必须同一会话或先后。

## 2. 文件所有权矩阵（并行安全的依据）

| 文件 | 所属包 |
| --- | --- |
| `scripts/scheduling/daily_data_refresh.ps1` | A1 |
| `backend/app/services/macro_toolkit_refresh_receipt_service.py`、`tests/test_macro_toolkit_refresh_receipt_service.py` | A2 |
| `backend/app/services/market_home_warmup_service.py` | B2，随后 G |
| `backend/app/services/data_health_service.py`、`tests/test_data_health.py` | C1 |
| `backend/app/services/market_overview_service.py`（新）、`backend/app/api/routes/market_overview.py`（新）、`backend/app/api/__init__.py`、`tests/test_market_overview_snapshot_api.py`（新）、`scripts/shadow_compare_market_snapshot.py`（新） | G |
| `frontend/src/features/workbench/module-home/useMarketHomeQueries.ts`、`frontend/src/test/ModuleWorkbenchHomeModel.test.ts` | B |
| `frontend/src/test/ModuleWorkbenchHomePage.test.tsx` | B（查询键断言），随后 D（首屏文案断言）——**同一泳道顺序执行，不并行** |
| `frontend/src/features/workbench/module-home/MarketOverviewDenseFirstScreen.tsx`、`marketOverviewDenseModel.ts`、`MarketFinancialChartsWorkbench.tsx`、`marketFinancialChartsModel.ts` 及各自 `.test.*` | D |
| `frontend/src/features/news-events/NewsEventsPage.tsx`、`NewsEventsPage.css`、`frontend/src/test/liveRouteReadinessContracts.ts`、`frontend/src/styles/workbenchDeferredChrome.css` | E |
| `frontend/src/features/cross-asset/hooks/useCrossAssetViewModel.ts`、`frontend/src/features/market-data/hooks/useMarketDataPageData.ts` 及相关测试 | F |
| `frontend/src/features/stock-analysis/components/StockAnalysisDataHealthCard.tsx`、`.test.tsx` | C2 |

不在表里的文件，任何包都不得修改；确有必要时在报告里说明并停下来等裁决，不要越界。

## 3. 集成与收口

各包合入后，由一个会话（或人）跑一次全量门禁并复测数字：

```bash
# 前端
cd frontend
npm run lint && npm run typecheck
npm run test -- ModuleWorkbenchHomePage MarketFinancialChartsWorkbench MarketBackendDataWorkbench \
  marketFinancialChartsModel marketOverviewDenseModel marketOverviewDenseLiquidityModel \
  MarketOverviewDenseFirstScreen LiveRouteReadiness
npm run test -- MarketDataPage CrossAssetPage MacroToolkitPage MacroObservationPage StockAnalysisPage NewsEventsPage
npx playwright test tests/playwright/market-overview-smoke.spec.mjs -c playwright.config.mjs

# 后端
python -m pytest tests/test_macro_toolkit_refresh_receipt_service.py tests/test_data_health.py \
  tests/test_live_route_page_contract_completeness.py tests/test_choice_news_routes.py -q
# WP-G 合入后追加
python -m pytest tests/test_market_overview_snapshot_api.py -q
```

复测数字（脚本在 `.tmp-agent/market-overview-audit/`，浏览器脚本需在 `frontend/` 下执行）：

| 指标 | 修前 | 目标 | 脚本 |
| --- | --- | --- | --- |
| 首屏 `analysis` 读（热态） | 3,321 ms 冷 / 137 ms 热，冷命中每 5 min 一次 | < 500 ms，预热命中 | `timing.mjs` |
| `/api/data-health` | 3,216 ms | < 500 ms 热态 | `slow_endpoints.py` |
| `/stock-analysis` 最后一条读完成 | 7.7–8.1 s | < 3 s | `timing.mjs` |
| `/news-events` @390 文档高 | 176,515 px | < 12,000 px | `spotcheck.mjs` |
| `/market-data`、`/cross-asset` `choice-series/latest` 次数 | 2 | 1 | `dup_reads.py` |
| 主页面 vitest | 175/176 | 176/176 | 门禁 |
| 首屏 hero | 暂停形成今日判断 | 回执恢复后显示后端结论；未恢复时两条链文案一致 | `audit3.mjs` |

## 4. 需要人做的事

1. **WP-A1 合入后手动触发一次日更任务**：`schtasks /run /tn MOSS-DailyDataRefresh`，然后看 `scripts/scheduling/logs/<今天>.log` 是否出现 `-- summary --`，以及 `data/logs/macro_toolkit_freshness_refresh_receipt.json` 的 `status` 是否离开 `running`。这一步会写 DuckDB，代理不应自行执行。
2. **WP-G 的两个 `series_id`**：Brent 现货与 USD/CNY 变动的稳定 `series_id` 要从目录表核出来填进别名注册表（任务书里给了查法）。
3. **口径裁决**（交接单 H2 / H6 / H12 / H15）：`warning` 是否阻断、`strategy_summaries` 双份 `as_of_date` 谁是权威、viewer 角色该不该看到外部数据水位、两个子页面的 PAGE 契约谁补。这些不是代理能拍的板。
4. **合并顺序**：L1 内部 A1→A2→B2→C1→G；L2 内部 B→D；其余任意。全部合入后跑 §3。

## 5. 2026-09-02 15:40 验收记录（Codex 五个并行会话交付后的复核）

| 包 | 结果 | 备注 |
| --- | --- | --- |
| A1 | 通过 | 改法与任务书一致；13:31 的真实运行产出完整 `-- summary --`（08-28 以来首次）。**Codex 违反了「不得自行运行 `schtasks /run`」**，结果无害但需知晓 |
| A2 | 通过 | 3 个新用例；当前生产回执已是真实终态 `failed`，分类 `blocked / refresh_execution_failure` |
| B2 | 通过 | `macro_analysis_full` 与 `market_overview_snapshot` 两步已进预热 |
| C1 | 通过 | `TTLResponseCache` 复用，含清缓存 fixture |
| G | 通过 | 路由/服务/测试/预热/影子比对齐全；影子比对 **8/8 一致**（WP-H 闸门已开）。`crisis` 分区因读 `core` 组件而 `degraded`，见下 |
| B | **通过但有回归，已修** | `detail=core` 的 `capability_results` 是空数组，首屏「曲线」「Crisis」退成"待返回"。任务书假设错误（只比了顶层键）。已改回 `detail: "full"`（不传 `history_limit`，命中 B2 预热键），三处测试与契约同步，实测 `analysis` 读 446 ms、Crisis 位恢复 |
| D | 通过 | D1–D5 实测：hero 与焦点解读同文；tooltip 与格子同精度；`持平`/`指数`/带符号变动；03 区默认 1 张真画布；focus 模式无死按钮 |
| E | 通过 | 主页面门禁 176/176；E3 用既有 token `--dh-api-soft` |
| F | 通过 | 两处各改一行 |
| C2 | 通过 | `useQuery` + StrictMode 单次调用用例 |

门禁：后端 238/238；前端 17 文件 372/372；lint/typecheck 干净；`market-overview-smoke` 2/2；`/ui/market-overview/snapshot` 热态 20 ms、15 KB。

**WP-H 开工前必须先解决的后端问题**：`detail=core` 不含 `capability_results`，导致 snapshot 的 `crisis` 分区永远 `degraded`。二选一：让 `core` 携带能力结果的最新值（不带 `score_history`），或让 snapshot 服务改读 `macro_analysis_full` 组件。这是 Fable 的裁决，应作为 WP-H 的前置项写进任务书。

**数据侧现状**：13:31 那次运行让 `tushare_news_backup`、`tushare_ncd_shibor`、`commodity_daily_ingest`、`public_cross_asset_headlines` 全部成功——新闻、DR007、SHIBOR、USD/CNY 已到 09-02，10Y/CSI300/铜到 09-01。唯一失败的是 `choice_policy_rate_7d`：`IO Error: Cannot open file moss.duckdb: 另一个程序正在使用此文件`（写锁与在线的 API / 同时跑的 pytest 冲突）。所以首屏仍是「暂停判断」，但理由已是真实的后端原文。**再跑一次 `schtasks /run /tn MOSS-DailyDataRefresh`（确保当时没有 pytest 在跑）即可**；该步骤缺少 `choice_stock_daily_refresh.py:267` 那样的写锁重试，建议作为 Fable 后续项。
