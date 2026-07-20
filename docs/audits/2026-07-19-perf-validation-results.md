# 2026-07-19 性能优化实测验证报告

验证对象：分支 `codex/V1` 上的三个性能提交
`0cb23b1ab`（API 开销 + vendor 体积）、`c7e0e017c`（Market Data 预热延迟 + pnlCore mock 隔离）、`94030ef8c`（热路径 TTL 缓存 + 并行测试 + 渲染 memo）。

## 测量环境

- Windows 10（win32 10.0.26200），本地 DuckDB `data/moss.duckdb`
- 后端：`.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 7899`（干净新进程，测完即关）
- 鉴权头：`X-User-Id: perf-validate` / `X-User-Role: admin`
- HTTP 计时：PowerShell `Invoke-WebRequest` + Stopwatch，含本地回环网络与序列化开销

## 结果 A：HTTP 端到端（干净进程，冷 = 进程内首次请求）

| 端点 | 冷请求 | 热请求（后续 5 次） |
|------|--------|---------------------|
| `GET /api/bond-analytics/yield-curve-term-structure?report_date=2026-03-31` | 233 ms | 20–29 ms |
| `GET /api/dashboard/core_metrics` | 24 ms | 21–134 ms（一次 134ms 抖动，其余 ~22ms） |

热请求同时受益于两层缓存：
1. 鉴权 allow 决策进程内 TTL 缓存（默认 30s，`MOSS_AUTH_SCOPE_CACHE_TTL_SECONDS`）——省去每次请求的 Postgres scope 查询；
2. 服务层 300s TTL 结果缓存（key 含 DuckDB mtime+size+WAL mtime，写入后自动失效）。

对照：一台**优化前代码**的旧后端进程（7888，启动早于 `94030ef8c`）上同一期限结构端点热请求稳定在 148–229 ms，即热路径缓存带来约 **7–10 倍**的热请求提速。

## 结果 B：服务层直接计时（`time.perf_counter`，绕过 HTTP）

| 服务函数 | 冷（首次计算） | 热（缓存命中） |
|----------|----------------|----------------|
| `liability_yield_metrics_payload`（负债收益指标） | 5069 ms | 0.7–1.0 ms |
| `get_yield_curve_term_structure`（treasury,cdb，payload≈5KB） | 541 ms | 0.3–0.4 ms |

负债 yield_metrics 是本轮收益最大的路径：单次冷计算约 5 秒，TTL 窗口内后续请求近乎免费。

## 结果 C：鉴权路径

- `/api/analysis/yield_metrics` 经 HTTP 返回 403：scope 存储（Postgres `user_role_scope` 表）中**没有** `liability_analytics:read` 授权行（现有授权覆盖 bond_analytics、dashboard、macro_toolkit 等 22 个 resource/action）。这是数据配置问题，不是本轮改动引入；服务层直测已覆盖该路径的性能验证。
- 未带任何头的 `/api/dashboard/core_metrics` 返回 200（development 环境 anonymous/viewer 授权生效），行为与优化前一致。

## 结论

1. 三个热路径 TTL 缓存按预期生效，热请求延迟从数百 ms～数秒降到 ~1ms（服务层）/ ~20ms（HTTP 端到端）。
2. 鉴权 TTL 缓存消除了每请求的 scope 查询，未观察到权限行为变化（deny 不缓存，403 仍即时）。
3. 缓存 key 折叠 DuckDB `mtime+size+WAL`，任务链路写库后下一次请求自动重算，无陈旧数据风险窗口超出 TTL 设计。

## 残余风险 / 未验证项

- `liability_analytics:read` 缺授权行导致该端点对所有角色 403——如需前端页面可用，需运维补授权（`UserScopeRepository.grant_scope`）。
- 前端 bundle 体积与 Market Data 预热延迟未在本报告重复测量（提交时已有 build 输出对比：ag-grid vendor 1067KB→812KB）。
- 冷请求延迟不变（首次计算本身未优化），负债 yield_metrics 冷计算 ~5s 仍是后续优化候选。
