# WP-B2 · 预热器补 `detail=full` 键

- 泳道：L1 后端/运维，第 3 个（与 WP-G 共用 `market_home_warmup_service.py`，必须在 G 之前、同一会话或先后）
- 层：Python
- 难度：低
- 前置：无（但与 WP-B 是一对：B 让市场总览改请求 `core`，本包让仍需 `full` 的 `/macro-toolkit` 命中预热）

## 目标

`/macro-toolkit` 页面请求 `GET /ui/macro/toolkit/analysis?detail=full&history_limit=430`（`frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx:166-170`，它渲染 Crisis 走势，确实需要历史），而预热器只预热 `detail=core`，这个键每个 TTL 窗口（默认 300 s）第一次命中都要冷算 3.3–3.7 s。把 `full/430` 加进预热步骤，让它和 `core` 一样在后台周期重刷。

## 根因

`backend/app/services/market_home_warmup_service.py:123-134` 只有 `macro_analysis_core` 一步；`backend/app/api/routes/macro_toolkit.py:431-447` 按 `market_home_macro_analysis_cache_key(duckdb, detail, history_limit=… if detail=="full" else None, freshness_fingerprint=…)` 取缓存，`full` 与 `core` 是不同键。`.tmp-agent/market-overview-audit/detail_cost.py` 实测：`full/430` 冷 3,321 ms、热 137 ms；`full/60` 换参数即重算 3,267 ms。

## 改动范围

`backend/app/services/market_home_warmup_service.py` 的 `warm_market_home_read_caches()`：在 `macro_analysis_core` 之后追加一步

```python
(
    "macro_analysis_full",
    market_home_macro_analysis_cache_key(
        duckdb_path,
        "full",
        history_limit=DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
        freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
    ),
    lambda: build_macro_toolkit_analysis(
        "full",
        history_limit=DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
        refresh_receipt_health=refresh_receipt_health,
    ),
),
```

`DEFAULT_CRISIS_SCORE_HISTORY_LIMIT` 从 `backend/app/core_finance/macro/crisis_score.py:12` 导入（值 430，与前端 `MACRO_TOOLKIT_CRISIS_SCORE_HISTORY_LIMIT` 一致；两者若哪天分叉，预热就会再次失配，请在步骤旁加一行注释指明这条耦合）。保持顺序：`core` 先、`full` 后，`full` 的构建可能复用 `core` 的中间结果与 DuckDB 页缓存。

如果 `build_macro_toolkit_analysis` 的签名不接受 `history_limit`，以 `backend/app/api/routes/macro_toolkit.py:456-469` 的调用方式为准。

## 不得触碰

- 不改缓存键函数 `market_home_macro_analysis_cache_key` 的格式（路由与预热双方都依赖它）。
- 不改 `detail` 的语义、不改 `_build_macro_toolkit_full_analysis_blocks`。
- 不改 dashboard-home 那几步（`_dashboard_home_formal_steps`）。
- WP-G 会在同一函数末尾再追加 snapshot 步骤；本包不要预留、不要重构 steps 结构。

## 验收

1. 现有预热相关测试全绿：`python -m pytest tests -q -k "warmup or prewarm"`（若没有专门测试，至少 `python -c "import backend.app.services.market_home_warmup_service"` 可导入且 `python -m pytest tests/test_macro_toolkit_scripts.py -q` 通过）。
2. 若有条件起后端（`scripts/dev-api.ps1`，`MOSS_MARKET_HOME_PREWARM_ENABLED=1` 默认开）：等日志出现 `market_home_prewarm_step ok step=macro_analysis_full`，随后 `python .tmp-agent/market-overview-audit/detail_cost.py` 第二行（`full&history_limit=430`）首个请求 < 500 ms。
3. `git diff` 只含 `market_home_warmup_service.py`。

## 报告要求

根因、改动文件、验证命令与结果、剩余风险（预热多一步约 3–4 s 的后台开销，每 TTL×ratio 周期一次；`history_limit` 默认值在前后端各有一份常量）。对 `core_finance/` 的影响：仅导入常量，无逻辑改动。
