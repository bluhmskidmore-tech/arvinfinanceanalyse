# Stock Analysis Stage 4 — 性能与可观测性（C 方向）

## 0. 元信息

- **创建日期**：2026-05-08  
- **作者标识**：Stage 4 planning subagent  
- **关联 Stage 3 立项文档（如有）**：`docs/plans/2026-05-08-stock-analysis-stage3-sector-strength-extension.md`（多日板块运行时压力）  
- **关联代码 commit**：本会话依据的仓库快照 **HEAD：`1e9714a4`**

---

## 1. 背景与动机

- **Stage 1～3 相关代码事实**  
  - **`GET /ui/market-data/livermore/stock-detail`**：`livermore_stock_detail_envelope` 在成功路径至少执行：`_resolve_end_trade_date` 一次、`choice_stock_daily_observation` 一次 limit 查询、`choice_stock_factor_snapshot` 一次（见 `backend/app/services/livermore_stock_detail_service.py`）。  
  - **`GET /ui/market-data/livermore/candidate-history`**：`livermore_candidate_history_envelope` 在表存在时 `show tables` + 一次 `select ... limit`（`backend/app/services/livermore_candidate_history_service.py`）。  
  - **`GET /ui/market-data/livermore/sector-rank-series`**：`livermore_sector_rank_series_envelope` 对 **每个交易日** 调用 `_load_sector_rank_constituents`（一次较重 join：`choice_stock_sector_membership` ⋈ `choice_stock_daily_observation`）再 `compute_sector_rank`（`backend/app/services/livermore_sector_rank_series_service.py`）；窗口 `window_days` 上限路由默认为 **60**（`market_data_livermore.py` `Query(..., le=60)`）。  
  - **物化任务**：`materialize_livermore_candidate_history` 直接 `duckdb.connect` 写库、循环候选股调用 `_forward_returns_for_candidate`（每支股票多次 `select`，见 `livermore_candidate_history_materialize.py`），属于 **批处理写路径**，与 API 读路径分离。  
  - **前端**：`StockAnalysisPage.tsx` 同时持有 strategy、signal-confluence、sector-rank-series 等 query；`StockDetailDrawer.tsx` 在打开时并行 stock-detail、choice-news、candidate-history。  

- **为什么需要本项**  
  1. `sector-rank-series` 在 **多日 × 全市场成分 join** 下可能成为热点慢查询；若无 **P95/P99** 目标与上限，生产难以判断是否扩容或改物化表。  
  2. 候选历史物化若不 **服务化/可观测**，回溯失败时无法区分「调度未跑」与「行情缺口」。  
  3. 三个新只读 endpoint 无统一 **instrument** 时，无法绘制「热点 API 性能场」。  

- **不做的成本**  
  DuckDB 单文件读写在并发下抖动；页面偶发超时被视为「前端问题」；排障依赖人工 tail 日志。  

---

## 2. 业务目标与不做边界

### 必须做

- 为 **stock-detail / candidate-history / sector-rank-series** 定义 **P95 / P99** 服务侧耗时目标（含冷/热库体积假设见下文）。  
- 明确 **DuckDB 读连接** 在 APIWorkers 上的 **并发上限** 策略（排队 vs 线程池 vs 拒绝）。  
- 将 **DuckDB 查询次数**（或语句计数）与 **endpoint**、**trace_id** 关联打点；热点路由划 **性能预算**「红线」。  
- `materialize_livermore_candidate_history` **任务化**：进程内指标（开始/结束/行数/跳过原因）+ 可选 HTTP 健康检查。  
- 对 **sector-rank-series** 做 **压力上限测试**：在 `window_days=20`、默认 `top_k=10`、全市场板块规模下记录耗时与 CPU。  

### 明确不做

- 不做大规模 DuckDB 集群化改造。  
- 不在本包内强制改写 `sector-rank-series` 算法（除非压测证明必须；算法改造单独立项）。  
- 不接入商业 APM 除非已有 license；优先 **OpenTelemetry 或日志结构化字段**。  

---

## 3. 性能基线现状

| 能力 | 现状（代码依据） | 主要风险 | 工作量量级 |
|------|------------------|----------|------------|
| stock-detail | 3 类 SQL + 连接开销 | lookback=250 时单股行数大 | **低～中** |
| candidate-history | 表缺失短路；否则 1～2 条 SQL | limit 500 时扫描范围 | **低** |
| sector-rank-series | **O(窗口日数 × join 规模)** 循环 | 窗口与 top_k 增大时 **CPU+IO** 陡增 | **高** |
| candidate 物化任务 | 同步循环多股、多次查询 | 批处理时长与锁持有者 | **中** |
| 前端并行请求 | Drawer 开 3 个 query | 浏览器侧瀑布与后端叠加 | **中** |

---

## 4. 数据契约草案 / 接口设计草案

### 指标（日志或 OTel Span 属性草案）

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `md_livermore_endpoint` | string | 固定枚举：`stock_detail` / `candidate_history` / `sector_rank_series` |
| `duckdb_statement_count` | integer | 单次请求执行的 **select** 次数（含 `show tables`） |
| `duckdb_fetch_row_estimate` | integer | 可选：ORM/驱动层行计数 |
| `duration_ms` | float | 服务内耗时（不含网络） |
| `window_days` | integer | 仅 sector-rank-series |
| `lookback` | integer | 仅 stock-detail |
| `trace_id` | string | 与 `build_result_envelope` 已有 trace 对齐 |

### 管理端点（草案，仅内网）

- `GET /ui/health/duckdb-pool`：返回活跃读连接数、队列长度（若实现池）。路径遵循 `/ui/<domain>/...`。  

### P95 / P99 目标（本立项建议值，实施前可按 staging 数据修订）

| endpoint | 假设环境 | P95 目标 | P99 目标 | 单次请求 DuckDB **select** 次数上限（软预算） |
|----------|-----------|----------|----------|-----------------------------------------------|
| `/ui/market-data/livermore/stock-detail` | 生产只读库、lookback≤120 | **≤ 850 ms** | **≤ 1500 ms** | **≤ 5**（含日期解析、蜡烛、因子；与当前 ~3 一致，留余量给重试） |
| `/ui/market-data/livermore/candidate-history` | limit≤100 | **≤ 400 ms** | **≤ 800 ms** | **≤ 4**（含 show tables + select） |
| `/ui/market-data/livermore/sector-rank-series` | window_days=20、top_k=10 | **≤ 4500 ms** | **≤ 9000 ms** | **≤ 2 × window_days + 4**（约每日 2 次：distinct 交易日列表 + constituents join；以 instrument 实测为准） |

> **说明**：sector-rank 目标偏保守；若压测稳定低于阈值的 50%，可收紧 P95。  

### DuckDB **并发读**上限（建议策略）

- **建议值**：同一 API 进程内 **最多 4 个并发只读连接** 同时执行 Livermore 读路径；**第 5 个** 起排队 **≤ 2s** 或返回 **429**（需与产品确认 UX）。  
- **理由**：单文件 DuckDB 读仍受内部锁与 Windows 文件系统影响；股票分析页 + 其它工作台同时刷新时易叠加（与 `MarketDataPage` 等共存）。  

---

## 5. 治理与合规风险

- 指标与日志 **禁止**写入客户持仓明细；仅 endpoint、耗时、表名列表（`tables_used` 已与 envelope 对齐）。  
- Formal / Scenario：性能监控不改变 **basis** 字段语义。  
- 任务健康接口需 **内网 ACL**，避免暴露运行状态给公网。  

---

## 6. 实施分解

1. **后端任务 1**：在 `livermore_stock_detail_service.py` / `livermore_candidate_history_service.py` / `livermore_sector_rank_series_service.py` 外包一层 **计时 + 语句计数**（ DuckDB 层包装或代码路径计数）→ **验证**：单测中断言计数区间；staging 压测日志样例。  
2. **后端任务 2**：FastAPI middleware 或依赖注入记录 `duration_ms` + `trace_id` → **验证**：与现有 `build_result_envelope` trace 对齐 grep。  
3. **后端任务 3**：`materialize_livermore_candidate_history` 增加结构化日志（`row_count`、`skipped_count`、`elapsed_ms`）与退出码；可选封装为 **CLI + systemd/cron** 同一入口 → **验证**：空跑与部分 skip 场景各一条日志。  
4. **压测任务**：脚本化 `window_days ∈ {5,20}` × `top_k ∈ {10,30}`，输出 P95/P99 CSV → **验证**：贴在 CI 或 `tests/perf` 人工门槛。  
5. **前端任务 1**：`StockDetailDrawer` 对三并行 query 设 **stagger** 或合并 loading（避免惊群）→ **验证**：Chrome Performance 录制对比请求瀑布。  

---

## 7. 验收清单

- [ ] 三个 endpoint 均可在日志/APM 中按 trace_id 查到 `duration_ms` 与 `duckdb_statement_count`。  
- [ ] Staging 压测报告：sector-rank-series 在 **window_days=20、top_k=10** 下 P95 **低于** §4 红线或已备案放宽理由。  
- [ ] 物化任务一次运行有可查询的 **row_count + elapsed_ms** 摘要。  
- [ ] 并发策略（4 连接或备选）经文档化并获运维确认。  

---

## 8. 工作量评估与排期建议

- **后端**：**5～8 人日**（instrument + middleware + 压测脚本 + 任务日志）  
- **前端**：**1～2 人日**（请求编排优化）  
- **整体**：**2～3 周**（含一轮 staging 数据收集）  
- **是否需要 vendor / 外部审批**：**否**（纯工程）；若接第三方 APM **可能**  

---

## 9. 依赖与前置

- **必须先完成**：生产/预发 **DuckDB 文件体量** 与部署拓扑确认（单文件路径与只读挂载）。  
- **可并行**：A 方向 P1（物化调度与 C 方向任务观测天然重合）。  
