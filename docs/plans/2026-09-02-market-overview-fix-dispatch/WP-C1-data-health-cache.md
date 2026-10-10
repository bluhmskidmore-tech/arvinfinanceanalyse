# WP-C1 · `/api/data-health` 每次请求 shell 出 `schtasks`

- 泳道：L1 后端/运维，第 4 个（与 A1/A2/B2 无共同文件，可与它们并行）
- 层：Python + pytest
- 难度：低
- 前置：无
- 配套：WP-C2 修前端调用侧，两包独立

## 目标

`GET /api/data-health` 热态响应 < 500 ms。当前直连后端连续两次实测 3,216 ms / 3,203 ms（`.tmp-agent/market-overview-audit/slow_endpoints.py`），4 路并发退化到 5.4 s。

## 根因

`backend/app/services/data_health_service.py:602-609` 的 `_run_schtasks_query()` 每次请求 `subprocess.run(["schtasks", "/query", "/fo", "csv", "/v"])`，本机该命令实测 2.8–2.9 s（全量 verbose 列出所有计划任务再由 `_parse_schtasks_csv` 过滤 `MOSS-*`）。其余七个 DuckDB 检查项合计不到 0.4 s。`schtasks` 反映的是每天跑一次的计划任务状态，没有理由每次请求都重新查。

## 改动范围

`backend/app/services/data_health_service.py`：

1. 给 `_scheduled_tasks_section()`（`:536`）的结果加进程内 TTL 缓存。**复用现有 helper**：`from backend.app.observability.response_cache import TTLResponseCache`，模块级 `_SCHEDULED_TASKS_CACHE = TTLResponseCache(default_ttl_seconds=120.0)`，键固定为 `"data-health/scheduled-tasks"`，用 `get_or_build` 包住现有构建逻辑。不要自己写 `time.monotonic()` 字典。
2. 缓存的是**section dict**（含 status/metric/detail），不是原始 CSV——这样 `_parse_schtasks_csv` 的开销也省掉，且 `_safe_section` 的降级语义不变（异常也会被构建函数转成 `error` section 后缓存 120 s；这是可接受的，报告里点明）。
3. TTL 允许环境变量覆盖 `MOSS_DATA_HEALTH_SCHTASKS_TTL_SECONDS`（照 `response_cache.resolve_default_ttl` 的写法），设 `0` 时退化为每次执行，方便排障。
4. `result_meta` 语义不变：`as_of_date`/`generated_at` 仍按请求时计算；仅 `scheduled_tasks` 一项可能滞后 ≤ 120 s，在该 section 的 `detail` 末尾追加 `（缓存 ≤120 s）` 说明，或在 `filters_applied` 加 `scheduled_tasks_cache_ttl_seconds`。二选一，倾向后者（不改用户可见文案）。

`tests/test_data_health.py`：

- 新增 `test_scheduled_tasks_section_is_cached_within_ttl`：monkeypatch `_run_schtasks_query` 为计数器函数，连续调用 `data_health_envelope()` 两次，计数为 1；用 `TTLResponseCache(clock=fake_clock)` 或 `monkeypatch.setattr(data_health_service, "_SCHEDULED_TASKS_CACHE", TTLResponseCache(default_ttl_seconds=…, clock=…))` 推进时钟后第三次调用计数为 2。
- 现有用例（`:186-413`）大量 monkeypatch `_run_schtasks_query` 并各自构造不同 CSV——**它们之间会互相命中缓存**。在 `conftest` 级或每个用例开头清缓存：最简单是新增 fixture（autouse，仅本文件）调用 `data_health_service._SCHEDULED_TASKS_CACHE.invalidate()`。这一步不做，现有测试会串味。

## 不得触碰

- 不改 DuckDB 七项检查的 SQL 与阈值（`_freshness_status` 等），不改 `overall_status` 的计算。
- 不改路由 `backend/app/api/routes/data_health.py`。
- 不把整个 envelope 缓存——`as_of_date` 与 DuckDB 项要保持实时，只缓存 `schtasks` 那一项。
- 不改 `_SCHTASKS_TIMEOUT_SECONDS` 等常量。

## 验收

```bash
python -m pytest tests/test_data_health.py -q        # 全绿，含新增缓存用例
```

后端起着时（`:7888`）：`python .tmp-agent/market-overview-audit/slow_endpoints.py`，`/api/data-health` 第一次 ≈ 3 s（冷）、第二次 < 500 ms；`python .tmp-agent/market-overview-audit/contention.py` 的 stock-analysis 组里 4 路 `data-health` 并发全部 < 500 ms（首个冷命中除外）。

## 报告要求

根因、改动文件、验证命令与结果、剩余风险（`schtasks` 失败也会被缓存 120 s；首个请求仍 3 s——若要彻底消除，需预热或改为后台刷新，本包不做）。对 `core_finance/` 的影响：无。
