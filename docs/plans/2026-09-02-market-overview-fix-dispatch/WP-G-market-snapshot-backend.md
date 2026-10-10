# WP-G · 模块级后端读 `GET /ui/market-overview/snapshot`（方案 Phase 1）

- 泳道：L1 后端/运维，第 5 个（WP-B2 之后；两包都改 `market_home_warmup_service.py`）
- 层：Python + pytest + OpenAPI 导出
- 难度：高（新服务、新路由、新测试；但**没有新金融口径**，全部是组合与选择）
- 前置：WP-A2（本包 `gate` 分区直接消费其 `abandoned` 状态），WP-B2
- 后续：WP-H（前端切换）在本包合入并完成影子比对后才派
- 设计全文：`docs/plans/2026-09-02-market-overview-module-compute-plan.md` §2（分区字段、聚合规则、注册表）、§3 Phase 1（任务清单）。本任务书是执行摘要，字段级定义以方案 §2.4 为准，冲突时以方案为准并在报告里指出。

## 目标

把 `/market-overview` 首屏（01 分析观察、02 市场证据）所需的全部派生计算收进一个后端读，前端只做格式化。具体是：gate 判定、逐数据面日期、8 个头条行情槽位、4 个指标变动槽位、Crisis 摘要、信号卡分类、新闻密度与摘要、P0–P2 核验队列。它替代的是前端 `moduleHomeModel.ts` / `marketOverviewDenseModel.ts` / `marketDeskIntelModel.ts` / `marketActionQueueModel.ts` 中的市场分支，以及三处并存的序列身份猜测（后端别名表、壳层 `series_id` 白名单、市场总览正则）。

## 为什么这样做（一段话）

首屏现在拉 6 条通用读、解压后 1.85 MB，在浏览器主线程上用正则挑序列、算变动、分桶、判 gate；身份解析、gate 判定、日期口径三件治理性质的事都落在展示层，且两条渲染链没有同一个真值来源（审计 F1）。仓库里已有两个成熟的组合读模式可照抄：`home.snapshot`（`executive_service.py:3701`，跨域日期上下文 + 子信封质量聚合）与 `stock-analysis/workbench`（`market_data_livermore_route_support.py:119`，`include=` 分区 + 指纹缓存键）。

## 任务清单

### G0 · 人工输入（阻塞 G3）

Brent 现货与 USD/CNY 变动的稳定 `series_id`。从 `macro_vendor_service.py` 读取目录所用的表（`_catalog_column_expr` 那条 SQL 指向的目录表）只读查询：`series_name ILIKE '%brent%'` / `'%美元兑人民币%'` / `'%usdcny%'`，列出 `series_id, series_name, unit, refresh_tier, vendor_name`，选 `refresh_tier = stable` 的稳定码。核不出来就把槽位标 `unresolved` 上线，不要用名称匹配兜底。

### G1 · 服务 `backend/app/services/market_overview_service.py`

- 入口 `build_market_snapshot(*, include: frozenset[str], duckdb_path: str, refresh_receipt_health) -> dict`，返回 `build_result_envelope(basis="analytical", result_kind="market.snapshot", formal_use_allowed=False, …)`（`formal_result_runtime.py:485`）。
- 组件来源**只**从 `market_home_response_cache` 取，键用 `response_cache.py` 里的既有函数：`market_home_choice_latest_cache_key`、`market_home_rates_cache_key`、`market_home_macro_analysis_cache_key(duckdb, "core", freshness_fingerprint=…)`、`market_home_strategy_summaries_cache_key`；缓存未命中时用与预热器相同的 builder 构建（`market_home_warmup_service.py:107-140` 的 lambda 就是标准答案，不要另写一套）。新闻直接调 `choice_news_service.choice_news_latest_envelope(limit=500, …)`。
- 任一组件缺失或 `quality_flag != ok` **不中断**：对应分区 `status: unavailable | degraded` + `reason`，顶层 `components` 表记录（对应 `home.snapshot` 的 `domains_missing` / `degraded_components`）。
- 分区与字段按方案 §2.4：`gate`、`dates`、`tape`、`pulse`、`crisis`、`signals`、`news`、`actions`；`charts` 第一版不做。
- slot 注册表 `MARKET_OVERVIEW_TAPE_SLOTS` 放本文件顶部；初始别名合并三处：`macro_vendor_service.py:82-87 _CHOICE_TERM_SPREAD_SERIES_IDS`、`frontend/src/layouts/workbenchShellTicker.ts:92-100 shellTickerSeriesIdsByKey`、审计实测命中（`E1000180 / CA.DR007 / EMM00088132 / NCD.SHIBOR.3M / CA.CSI300 / CA.COPPER`）。解析复用 `_latest_choice_macro_point()` 的语义（最新落地日上的首选别名，不做过期回退）——把该函数改为可传入别名表的通用形式并从 `macro_vendor_service` 导出，**不要复制一份**。
- `crisis.delta` 在后端算首尾差（`score_history` 来自 `core` 档是否可得，先核实；不可得则本分区标 `degraded` 并在报告里说明，不要为此把组件读切回 `full`）。
- `news.density`：先按 `group_id ∈ {tushare_research, tushare_cctv}` 且 Asia/Shanghai 时刻为 `00:00:00` 判 `date_only`，剔出小时桶单独计数；其余按 Asia/Shanghai 两小时分桶（时刻本身正确，只是 UTC 序列化）。规则写进 `result_meta.filters_applied`。
- `result_meta` 聚合按方案 §2.5：`as_of_date` **不填单一值**，`date_basis = "per_surface"`；`source_version` / `vendor_version` 超过 8 段时收为 `sha256[:12]` 指纹 + `filters_applied.lineage_segments`。
- **不写公式**：任何数值口径（利差、变动）调用 `core_finance/market_derived.py` 既有函数。

### G2 · 路由与注册

- `backend/app/api/routes/market_overview.py`：`APIRouter(prefix="/ui/market-overview", tags=["market-overview"])`，`GET /snapshot`，参数 `include: str | None`（逗号分隔，默认全部首屏分区）。授权复用 `ensure_read_allowed(auth, "macro_toolkit", …)`（`macro_toolkit.py:1134` 的写法），不新增资源名。路由保持薄：解析 `include`、取 `refresh_receipt_health`、调服务、返回。
- 缓存：`market_home_response_cache.get_or_build_with_status`，键 `market-overview/snapshot::{sorted include}::{receipt_fingerprint}::{duckdb}`，TTL 默认。
- `backend/app/api/__init__.py` 注册 router。
- `python scripts/api_contract_check.py export-openapi --surface default --output .codex-tmp/openapi.json` 后 `cd frontend && npm run lint:openapi` 通过。

### G3 · 预热

`market_home_warmup_service.py` steps **末尾**追加 `market_overview_snapshot`（默认 `include`），放在所有组件之后。WP-B2 已在同一函数加了 `macro_analysis_full`，注意合并。

### G4 · 测试 `tests/test_market_overview_snapshot_api.py`

用 `tmp_path` DuckDB 与假回执文件（参考 `tests/test_macro_toolkit_refresh_receipt_service.py` 的 `_scheduled_receipt` 与 `tests/test_data_health.py` 的建库方式）：

1. 分区完整性与 `include` 过滤；
2. `gate` 三级各一条：回执 `ready` → `ok`；`ready` 但组件 `warning` → `review`；回执 `abandoned`（WP-A2）→ `blocked`，且 `human_reason` 等于回执服务的 `analysis_warnings()[0]`，`conclusion.tone` 原样透出；
3. slot 解析：多源同日取首选别名；无匹配 → `unresolved` 且**不**名称回退；`prefer="rates"` 的槽位 `basis == "formal"`；
4. `dates.tape_span` 与逐槽 `trade_date` 一致；
5. 新闻：`2026-08-27T12:29:46+00:00` 落在 `20` 桶；`tushare_research` 的 `T00:00:00` 行计入 `date_only_rows` 且不进任何桶；
6. 组件缺失：删掉 `choice_latest` 组件后 `tape` 全 `unavailable`、顶层 `quality_flag == "warning"`；`choice_latest` 与 `market_rates` 双缺 → `error`；
7. `result_meta.source_version` 长度上限；
8. `actions` 规则表逐条（方案 §2.4 表格）。

### G5 · 影子比对（切换闸门，WP-H 的前置）

`scripts/shadow_compare_market_snapshot.py`：对当前 DuckDB 同时产出新 `tape` 与旧前端逻辑的选择结果，逐槽比对 `series_id` 与 `trade_date`。旧逻辑取法二选一：把 `marketOverviewDenseModel.ts:437-468` 的正则移植成 Python，或用 Playwright 读现页 `[aria-label="市场行情带"] article` 的 `title`（`.tmp-agent/market-overview-audit/audit3.mjs` 已有现成读法）。输出一张 8 行表：槽位 / 旧 `series_id` / 新 `series_id` / 是否一致 / 结论。**任何不一致都要给出结论**（旧正则错了，还是别名表漏了），写进报告；这张表是 WP-H 能否开工的依据。

## 不得触碰

- schema（`time_granularity` 列另议）、RBAC、`core_finance/`（本包对正式金融路径的影响必须是**无**）。
- `home.snapshot`、`stock-analysis/workbench`、其他页的读；`choice_news_service` 只调用不修改。
- 前端任何文件（WP-H 的事）。`docs/page_contracts.md` §14.6 与 `docs/metric_dictionary.md` 的更新也放 WP-H，与前端切换同批。
- 不改 `_CHOICE_TERM_SPREAD_SERIES_IDS` 的内容与 `derived_spreads` 的计算位置；只把解析函数通用化并导出。

## 验收

```bash
python -m pytest tests/test_market_overview_snapshot_api.py tests/test_macro_toolkit_scripts.py \
  tests/test_choice_news_routes.py tests/test_live_route_page_contract_completeness.py -q
python scripts/api_contract_check.py export-openapi --surface default --output .codex-tmp/openapi.json
cd frontend && npm run lint:openapi
```

后端在线时：`curl http://127.0.0.1:7888/ui/market-overview/snapshot` 热态 < 300 ms、解压后 < 120 KB；`include=tape` 时 < 20 KB。预热日志出现 `market_home_prewarm_step ok step=market_overview_snapshot`。影子比对表 8/8 有结论。

## 报告要求

根因（引用方案 §2.1 的三个结构性问题即可）、改动文件、验证命令与结果、影子比对表、剩余风险（至少：别名表初版可能漏 Brent/USDCNY；`abandoned` 阈值 6 h 待 owner 确认；`actions` 阈值是首版常量，需在 WP-H 写进页面契约）。对 `core_finance/` 的影响：无（明确写出）。
