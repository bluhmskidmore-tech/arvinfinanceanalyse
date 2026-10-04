# WP-K · 两条 23–28 s 冷计算读进预热（H16）

- 泳道：L1 后端，第二批第 3 个（与 WP-I 共用 `market_home_warmup_service.py`，须在 I 之后或同一会话）
- 层：Python + pytest
- 难度：中（难点在"预热的键必须等于页面请求的键"）
- 前置：无

## 现象（`.tmp-agent/market-overview-audit/cold_vs_warm.py`，2026-09-02 15:55 直连后端）

```
/api/macro-bond-linkage/analysis?report_date=2026-09-02          43 ms   (warm)
/api/macro-bond-linkage/analysis?report_date=2026-08-26       27,849 ms   (cold key)
/ui/market-data/livermore/signal-confluence?as_of_date=2026-08-24  28 ms   (warm)
/ui/market-data/livermore/signal-confluence?as_of_date=2026-08-21 23,426 ms (cold key)
```

两条读都按业务日期分键缓存，所以**每个新交易日、每次后端重启、每次 TTL 过期后的第一个访客**要等 20 s 以上：`/cross-asset` 等前者，`/stock-analysis` 等后者。`market_home_warmup_service.warm_market_home_read_caches()` 预热了 stock-analysis *workbench*（`:152-166`），没有这两条。

## 改动

`backend/app/services/market_home_warmup_service.py`，在现有 steps 末尾（WP-G 的 snapshot 步之后）追加两步。**键必须与页面实际请求完全一致**，否则整步白热（`:222-231` 注释记录的 dashboard-home 事故）：

1. **signal-confluence**：页面键是 `_livermore_signal_confluence_cache_key(duckdb_path, catalog_file, as_of_date, theme_overlay_fingerprint)`（`backend/app/api/routes/market_data_livermore.py:199-211`），`as_of_date` 取自 Livermore strategy 信封的**解析后** `result.as_of_date`（前端 `useCrossAssetViewModel.ts:153` / stock-analysis 页同理）。预热时先用与 `_cached_stock_analysis_workbench` 相同的 `settings` 取 strategy 信封拿到 `as_of_date`，再以同一 `catalog_file` 与 `_theme_overlay_fingerprint(theme_overlay_reader)` 拼键，builder 与路由 `:340-355` 完全相同（含 `_with_livermore_workbench_summary(..., summary_kind="signal_confluence")`）。把键函数与 builder 从路由文件挪到 `market_data_livermore_route_support.py` 或直接导入路由模块的私有函数——**二选一，不要复制实现**。
2. **macro-bond-linkage**：服务层已有 `InMemoryTTLCache`（`backend/app/services/macro_bond_linkage_service.py:81-103`，`get_runtime_cache`），预热只需调用 `get_macro_bond_linkage(report_date)` 一次。`report_date` 必须等于页面用的 `maxCrossAssetHeadlineTradeDate(latestSeries)`（`frontend/src/features/cross-asset/lib/crossAssetKpiModel.ts:419`：对 `CROSS_ASSET_KPI_SLOTS` 的 single 槽位取候选 `series_id` 命中点的 `trade_date` 最大值）。后端没有这份槽位表——**从 `choice_latest` 组件里按同一组 `series_id` 取最大 `trade_date`**，把槽位 `series_id` 列表作为常量放进 warmup（并在注释里指向前端常量位置，标明这是第二份拷贝、WP-H 之后应由 `market.snapshot` 的 slot 注册表统一）。日期对不上就退化为不预热并打日志，不要猜。
3. 两步各自 try/except 走现有 `market_home_prewarm_step_failed` 路径，不影响其它步骤。

`tests/test_market_home_warmup.py`（WP-G 已建）：新增用例断言两步存在、键与路由函数产出一致（对同一组输入调用两边函数比较字符串）、`report_date` 推导等于 fixture 里各槽位的最大 `trade_date`。

## 不得触碰

两条读的计算口径与服务实现（本包只问"什么时候算"，不问"怎么算"）；路由签名；前端。

## 验收

```bash
python -m pytest tests/test_market_home_warmup.py -q
```

后端重启后等预热日志出现 `step=livermore_signal_confluence` 与 `step=macro_bond_linkage`，然后从 `frontend/` 跑 `.tmp-agent/market-overview-audit/timing.mjs`（复制到 `frontend/.tmp-audit/`）：`/cross-asset` 与 `/stock-analysis` 的 `lastBackendAt` 都 < 3,000 ms（当前 19–20 s）。

## 报告要求

根因、改动文件、验证结果、剩余风险（每次预热多 ~50 s 后台计算；`report_date` 推导是前端逻辑的第二份拷贝，WP-H 后应收敛；顺带回答 H16 第 2 问——23–28 s 花在哪一层，哪怕只是 profile 一次的粗结论）。对 `core_finance/` 的影响：无。
