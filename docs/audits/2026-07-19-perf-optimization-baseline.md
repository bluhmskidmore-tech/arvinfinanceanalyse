# API 性能优化基线（2026-07-19，阶段 0 采集）

环境：`scripts/dev-api.ps1` 启动（含 home/market 预热），`data/moss.duckdb` 约 1.5GB。
方法：每端点连续请求 2 次（round1 = 冷/首次，round2 = 热），本机 127.0.0.1:7888 直连。

| endpoint | round1 ms | round2 ms | status | bytes |
| --- | --- | --- | --- | --- |
| /ui/home/snapshot | 165 | 33 | 200 | 6,285 |
| /ui/home/overview | 646 | 33 | 200 | 5,148 |
| /api/bond-dashboard/dates | 68 | 32 | 200 | 7,613 |
| /api/bond-dashboard/bundle（6 sections, 2026-06-30） | 804 | 594 | 200 | 10,024 |
| /ui/balance-analysis/dates | 99 | 29 | 200 | 7,954 |
| /ui/balance-analysis/overview?report_date=2026-06-30 | 576 | 683 | 503 | -（Formal balance-analysis storage is unavailable） |
| /ui/market-data/livermore | 116 | 84 | 200 | 89,157 |
| /ui/market-data/livermore/signal-confluence | 410 | 37 | 200 | 7,960 |
| /ui/market-data/livermore/candidate-history | 63,357 | 618 | 200 | 812,261 |
| /ui/market-data/stock-analysis/workbench | 111 | 127 | 200 | 109,318 |
| /ui/macro/toolkit/analysis?detail=full | 2,559 | 140 | 200 | 115,265 |

bundle 完整参数：`sections=headline-kpis,risk-indicators,yield-distribution,asset-structure,spread-analysis,maturity-structure&report_date=2026-06-30`。

## 观察

1. `livermore/candidate-history` 冷路径 63s、热 0.6s：冷路径现算最严重端点，是阶段 1「冷路径补缓存/物化」的首要目标。
2. `bond-dashboard/bundle` 热请求仍约 600ms：单请求内多 section、多连接、多查询，无请求级连接复用。
3. `macro toolkit analysis` 冷 2.5s，热 140ms。
4. 常规轻端点热请求约 30–140ms：包含每请求 `duckdb.connect` 与鉴权 scope 查询的固定开销。
5. `balance-analysis` 正式存储在本地 dev 数据中不可用（503），本轮未纳入对比，优化验证时跳过。

## 阶段 1 优化后复测（同日）

改动：鉴权 allow 决策 30s TTL 缓存（`backend/app/security/auth_context.py`）+ DuckDB 目录探测（table/column exists）按文件 mtime 缓存（`backend/app/repositories/duckdb_repo.py`、`bond_analytics_repo.py`）。

| endpoint | round1 ms | round2 ms | 基线 round2 |
| --- | --- | --- | --- |
| /ui/home/snapshot | 183 | 31 | 33 |
| /ui/home/overview | 566 | 21 | 33 |
| /api/bond-dashboard/dates | 57 | 26 | 32 |
| /api/bond-dashboard/bundle（6 sections） | 203 | 131 | 594 |
| /ui/balance-analysis/dates | 98 | 26 | 29 |
| /ui/market-data/livermore | 123 | 88 | 84 |
| /ui/market-data/livermore/signal-confluence | 382 | 36 | 37 |
| /ui/market-data/stock-analysis/workbench | 82 | 105 | 127 |
| /ui/macro/toolkit/analysis?detail=full | 3489 | 96 | 140 |

重点：bundle 热请求 594ms → 131ms（约 4.5x），冷请求 804ms → 203ms。

## 用途

后续阶段（前端、数据任务）完成后，用同样方法复测本表做前后对比。剩余机会：pnl_repo 等仓库的每方法 connect 收敛、candidate-history 冷构建 63s 的预热/物化。
