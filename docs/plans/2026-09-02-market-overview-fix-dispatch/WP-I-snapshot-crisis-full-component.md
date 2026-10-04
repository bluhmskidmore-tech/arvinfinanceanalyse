# WP-I · `market.snapshot` 的 `crisis` 分区读 `full` 组件（WP-H 的硬前置）

- 泳道：L1 后端，第二批第 1 个
- 层：Python + pytest
- 难度：低
- 前置：WP-G、WP-B2 已合入（都已落地）
- 后续：WP-H

## 问题

`GET /ui/macro/toolkit/analysis?detail=core` 返回的 `capability_results` 是**空数组**（实测 `capability_results=0`）。`market_overview_service.py:125-130` 的组件清单只有 `macro_analysis_core`，于是 `_build_crisis()`（`:758`）永远走到 `"macro_analysis_core does not include crisis_score_cn in capability_results"` → `status: degraded`，`score/regime/percentile` 全 `null`。同一根因也让 WP-B 一度把首屏「曲线」「Crisis」打成"待返回"，已通过改回 `detail=full` 修复。

`full` 档已由 WP-B2 进入预热（`market_home_warmup_service.py` 的 `macro_analysis_full` 步），键 `market_home_macro_analysis_cache_key(duckdb, "full", history_limit=DEFAULT_CRISIS_SCORE_HISTORY_LIMIT, freshness_fingerprint=…)`，热态 ~130 ms。

## 改动（推荐方案，最小）

`backend/app/services/market_overview_service.py`：

1. `_COMPONENT_ORDER` 增加 `"macro_analysis_full"`；`_load_components()`（`:280-333`）按上面的键从 `market_home_response_cache` 取，未命中时用与预热器**相同**的 builder 构建（`build_macro_toolkit_analysis("full", history_limit=DEFAULT_CRISIS_SCORE_HISTORY_LIMIT, refresh_receipt_health=…)`）。
2. `_required_component_names()`（`:267`）：`crisis` 与 `actions` 需要 `macro_analysis_full`；`gate` / `pulse` / `signals` **继续用 core**（`conclusion`、`indicators`、`signal_cards` 在 core 里都有，别把整页绑到 full 上）。
3. `_build_crisis(components.get("macro_analysis_full"))`；分区 `reason` 文案里的 `macro_analysis_core` 字样同步改。
4. `dates` 分区的 `macro_analysis` 面仍取 core 的 `as_of_date`（两档日期相同，不要多出一个面）。
5. `result_meta.tables_used` / lineage 聚合会多一个组件，确认 `_aggregate_lineage_value` 的长度上限逻辑仍生效。

**不推荐**改 `core` 档去携带 `capability_results`：那会改动 `/macro-observation` 等页的契约，且 `core` 202 ms 的响应时间是靳靠不算能力结果换来的。若 Fable 判断长期应当如此，另立包，本包不做。

## 不得触碰

`macro_toolkit_read_service.py` 与 `detail` 语义；前端；`tape/pulse/gate/signals` 的现有行为与测试。

## 验收

`tests/test_market_overview_snapshot_api.py` 新增：用含 `crisis_score_cn`（带 `score_history`）的 full fixture 与空 `capability_results` 的 core fixture 同时注入，断言 `crisis.status == "ok"`、`score/regime/percentile` 非空、`delta.window_points == len(score_history)`、`delta.score_delta == last - first`；再断言 `gate`/`pulse` 未读 full（对 full 组件缺失的情况 `gate` 仍 `ok`）。

```bash
python -m pytest tests/test_market_overview_snapshot_api.py tests/test_market_home_warmup.py -q
```

后端在线：`curl "http://127.0.0.1:7888/ui/market-overview/snapshot?include=crisis"` → `status: ok`，`score` 与 `/market-overview` 首屏 Crisis 位一致（当前 -1.02 · 宽松）。

## 报告要求

根因、改动文件、验证结果、剩余风险（snapshot 现在依赖 full 的预热；若预热失效，冷计算 3.3 s 会落到 snapshot 上——键与预热一致是唯一防线）。对 `core_finance/` 的影响：无。
