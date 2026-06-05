# Stock Analysis Stage 4 — Stage 3 三个 MVP 的 P1 升级集合（A 方向）

## 0. 元信息

- **创建日期**：2026-05-08  
- **作者标识**：Stage 4 planning subagent  
- **关联 Stage 3 立项文档（如有）**：`docs/plans/2026-05-08-stock-analysis-stage3-sector-strength-extension.md`、`docs/plans/2026-05-08-stock-analysis-stage3-news-disclosure-events.md`、`docs/plans/2026-05-08-stock-analysis-stage3-candidate-history-replay.md`  
- **关联改造方案（背景）**：`c:\Users\arvin\.cursor\plans\stock_analysis_revamp_plan_d45b33b0.plan.md`  
- **关联代码 commit**：本会话依据的仓库快照 **HEAD：`1e9714a4`**

---

## 1. 背景与动机

- **Stage 1/2/3 已落地的程度（代码事实）**  
  - **个股抽屉 K 线 + 因子**：`GET /ui/market-data/livermore/stock-detail` 由 `backend/app/services/livermore_stock_detail_service.py` 装配 `choice_stock_daily_observation` 与 `choice_stock_factor_snapshot`，路由见 `backend/app/api/routes/market_data_livermore.py`（`livermore_stock_detail`）。前端 `frontend/src/features/stock-analysis/components/StockDetailDrawer.tsx` 通过 `client.getLivermoreStockDetail` 拉取。  
  - **入选历史**：物化任务 `backend/app/tasks/livermore_candidate_history_materialize.py` 中 `materialize_livermore_candidate_history` 写入表 `livermore_candidate_history`（DDL 见 `backend/app/schema_registry/duckdb/28_livermore_candidate_history.sql`）；只读 envelope 在 `backend/app/services/livermore_candidate_history_service.py`，路由 `GET /ui/market-data/livermore/candidate-history`。抽屉内说明「首期不做历史 backfill」见 `StockDetailDrawer.tsx` 中入选历史区块文案。  
  - **板块多日序列**：`backend/app/services/livermore_sector_rank_series_service.py` 在窗口内对每个交易日调用 `compute_sector_rank`，并在 `result_payload` 中返回 `unsupported_notes`，其中含 `momentum_persistence: needs metric definition review (P1)` 与 `sector_money_flow: ... (P1)`。路由 `GET /ui/market-data/livermore/sector-rank-series` 同上 `market_data_livermore.py`。  
  - **新闻**：抽屉用 `client.getChoiceNewsEvents({ limit: 10, offset: 0 })`（`StockDetailDrawer.tsx`），对应 `GET /ui/news/choice-events/latest`（`backend/app/api/routes/choice_news.py`），**未按个股 code 过滤**（query 仅 limit/offset/group/topic 等）。Tushare NPR 摄入路由对保留面返回 503（`_raise_choice_news_reserved_surface`）。  
  - **Agent**：`AgentQueryRequest` 仍含 `context: dict`（`backend/app/agent/schemas/agent_request.py`）；`frontend/src/api/contracts.ts` 标注 `context` **@deprecated**，`AgentPanel.tsx` 只发送 `page_context`。后端 `backend/app/services/agent_service.py` 中审计与 `_requested_report_date` 仍读取 `request.context`。  

- **为什么需要本项（业务价值）**  
  1. P0/P1 分离后，MVP 能「看见」但还不能「按股精查、按日补历史、按口径解释动量」；P1 把证据链闭合，减少误判与反复人工核对。  
  2. 调度与 backfill（A1）让「入选后表现」可纵向对比，而不是仅上线后的增量快照。  
  3. 新闻按代码解析（A2）与公告/财报反封堵（A3）直接降低「抽屉里全是全局头条」的噪音与合规保留面带来的空缺。  
  4. Agent `context` 清理（A4）降低前后端语义分叉导致的审计字段缺失或日期解析失败。  
  5. 动量持续度（A5）落实后，可移除或收窄 `unsupported_notes` 中的占位声明，与 `StockAnalysisPage.tsx` 多日板块展示一致。  

- **不做的成本**  
  历史表现仍断断续续；抽屉新闻与持仓无关；板块多日仍是「有部分已知缺口」状态；Agent 后端仍依赖 legacy `context` 容器，后续改造与排障成本高。  

---

## 2. 业务目标与不做边界

### 必须做

- **A1**：将 `materialize_livermore_candidate_history` 纳入可观测的任务链路（调度集成 + 可选历史交易日 backfill 策略文档化），使 `livermore_candidate_history` 在典型日终窗口内稳定更新。  
- **A2**：`choice_news` 消费路径支持按 **股票代码**（或等价的结构化 payload 字段）解析/过滤，使 `StockDetailDrawer` 能请求「与该代码相关」的事件子集（在现有表结构与授权前提下）。  
- **A3**：对公告/财报类数据源按治理流程单独立项：解除或替换当前 **503 保留面**（见 `choice_news.py`），并明确 vendor / InfoSec 审批步骤。  
- **A4**：后端在完成等价行为前提下收敛对 `AgentQueryRequest.context` 的依赖：以 `page_context` + `filters` 为权威来源，或文档化兼容层并删减负路径。  
- **A5**：对 `momentum_persistence` 给出**评审锁定**的定义并实现（或明确二期），更新 `livermore_sector_rank_series_service.py` 中系列输出与 `unsupported_notes` 策略。  

### 明确不做

- 不新增买卖/下单/调仓语义（延续 `docs/handoff/2026-05-06-stock-analysis-workbench-codex.md` §2）。  
- 不在前端计算正式「板块动量」或收益回测（`AGENTS.md`）。  
- 不在本 P1 包内完成「板块资金流向」全链路（服务层已将其标为 P1 vendor/schema 依赖，见 `UNSUPPORTED_NOTES`）。  
- 不扩大 `frontend/src/api/client.ts` 规模；新增方法继续落在域 client。  

---

## 3. 后端能力差距清单

| 能力 | 现状 | 缺口 | 工作量量级 |
|------|------|------|------------|
| A1 候选历史物化 | 任务函数已实现并可写库（`livermore_candidate_history_materialize.py`） | 与调度器/日终批对齐；可选 backfill 任务与幂等策略 | **M～L** |
| A2 新闻按代码 | `GET /ui/news/choice-events/latest` 无 `stock_code` query；抽屉用全局 limit | 存储侧需可过滤字段或服务侧 join；API 扩展 | **M** |
| A3 公告/财报 | 部分表面 **503 保留**（ingest）；events latest 需权限 `choice_news.data` | 治理评审 + 表/ETL + 路由解封范围对齐 | **L**（含流程） |
| A4 Agent context | schema 含 `context`；`agent_service` 读 `request.context` | 兼容迁移 + 测试 + 审计字段不丢 | **S～M** |
| A5 动量持续度 | `unsupported_notes` 明示待定义 | 口径锁定 + 实现 + 回归测试 | **M** |

---

## 4. 数据契约草案 / 接口设计草案

### A1

- **任务输出**：沿用物化返回字段（`status` / `row_count` / `run_id` / `snapshot_as_of_date` 等，见 `materialize_livermore_candidate_history`）。  
- **可选 backfill**：新增任务入口 **草案** `POST /ui/market-data/livermore/candidate-history/backfill`（或对齐现有 tasks 命名），Query：`from` / `to` ISO 日期、`dry_run`；**仅**在任务链路写库，API 若暴露需鉴权与配额（与 `AGENTS.md` 一致）。  

### A2

- **扩展示例** `GET /ui/news/choice-events/latest?stock_code=600000.SH&limit=20`（`varchar` 股票代码，`integer` limit），响应仍沿用 `build_result_envelope` 家族；若表无代码列则返回 `quality_flag=warning` + `unsupported_outputs` 说明。  

### A3

- 新表或扩展现有 Choice 事件表字段（草案命名对齐小写 + 下划线）：`stock_codes` 存 `varchar` 数组或关联表 `choice_news_event_equity (event_id varchar, stock_code varchar)`。  

### A4

- **契约**：`AgentQueryRequest` 中 `context` 标记弃用后，服务端从 `page_context.current_filters` 合并 `report_date` / `as_of_date`；审计 `user_id` 从正式 auth 上下文注入，而非仅 `context` 字典。  

### A5

- **result 扩展**（草案，与现有 JSON 风格一致）：在 `series[]` 增加 `momentum_persistence double`（0～1 或按评审定义），`formula_version` **varchar** 递增。  

---

## 5. 治理与合规风险

- **vendor**：Choice / Tushare / 公告源均受凭据与用途限制；A2/A3 涉及扩展读取面，需 **InfoSec + 数据负责人** 审批。  
- **保留面**：当前 `_raise_choice_news_reserved_surface` 明示边界；解封须书面变更记录。  
- **Formal / Scenario**：股票与 Agent 链路保持 **analytical** 表述；不在本项混入 formal 投资建议。  
- **Forbidden**：handoff 禁止的措辞与动作不变。  

---

## 6. 实施分解

### A1 候选历史调度 + backfill

1. **后端任务 1**：梳理现有 `materialize_livermore_candidate_history` 入口，对接调度配置（cron / queue 名以仓库现有任务为准）→ **验证**：指定 `as_of_date` 跑任务后 DuckDB 表 `livermore_candidate_history` 出现当日 `snapshot_as_of_date` 行；日志含 `run_id`。  
2. **后端任务 2**：设计 backfill：按交易日列表循环调用或批量 SQL，**幂等**（已有 `delete ... where snapshot_as_of_date = ?` 模式可复用）→ **验证**：pytest 或集成测试覆盖至少 2 个交易日；空快照行为与现逻辑一致。  
3. **运维/配置**：文档化「日终窗口 + 失败重试」→ **验证**：staging 一次全流程。  

**工作量量级**：**M（约 3～5 人日含联调）**

### A2 新闻按 stock_code payload 解析

1. **数据探查**：确认 `choice_news_service` 与表中是否已有股票维度字段 → **验证**：只读查询证据写入立项附录（非代码）。  
2. **后端**：扩展 `choice_news_latest_envelope` 与路由 query；无字段时优雅降级 → **验证**：pytest + 契约类型更新。  
3. **前端**：`StockDetailDrawer.tsx` 传入 `stockCode` 拉新闻；失败时保留现有 warning → **验证**：`StockDetailDrawer.test.tsx` 增量用例。  

**工作量量级**：**M（约 3～4 人日）**  

### A3 公告/财报反封堵立项

1. **流程**：与 Stage 3 新闻立项对齐，列出数据源、保留原因、解封条件 → **验证**：评审纪要。  
2. **后端**：在审批通过后替换 503 占位或为只读 preview → **验证**：集成测试 + 权限 `choice_news.data`。  

**工作量量级**：**L（视审批 1～3 周不等，实施 3～7 人日）**  

### A4 Agent `context` legacy 清理

1. **后端**：`agent_service.py` 中 `_requested_report_date`、`_append_audit` 改为优先 `page_context`；过渡期双读 → **验证**：现有 Agent 集成测 + 审计 jsonl 含 `user_id`。  
2. **契约**：`AgentQueryRequest` 文档字符串说明迁移期；可选 DeprecationWarning（若项目惯例允许）。  
3. **前端**：确认 `AgentPanel.tsx` 不传 `context` 仍全链路通过 → **验证**：端到端 POST `/api/agent/query`。  

**工作量量级**：**S～M（约 2～3 人日）**  

### A5 板块动量持续度口径评审与实现

1. **评审**：从 Rank 稳定性、Δscore、名次变动方差等候选中锁定 1 个定义（含缺失日处理）→ **验证**： signed-off 小文档（可放 `docs/` 由产品归档）。  
2. **后端**：在 `livermore_sector_rank_series_service.py` 计算并写入 `series[]`；缩减或更新 `UNSUPPORTED_NOTES` → **验证**：`tests/` 中 sector series 相关用例 + 边界（窗口 5/20）。  
3. **前端**：`StockAnalysisPage.tsx` 展示新字段或替换「已知缺口」提示 → **验证**：组件测试与截图评审（遵守 `DESIGN.md`）。  

**工作量量级**：**M（约 4～6 人日）**  

---

## 7. 验收清单

- [ ] A1：候选历史在调度环境每日写入；backfill（若启用）可重复执行不产生重复主键。  
- [ ] A2：`stock_code` 有数据时抽屉仅展示相关事件；无数据时有可读空态。  
- [ ] A3：公告/财报路径经治理批准后可用，503 占位与生产行为一致且可审计。  
- [ ] A4：Agent 请求不依赖浏览器发送 `context` 字典仍可取日期与审计。  
- [ ] A5：`momentum_persistence`（或最终命名）有文档定义且与代码一致；`unsupported_notes` 与实现一致。  

---

## 8. 工作量评估与排期建议

- **后端**：约 **14～22 人日**（含 A3 不确定审批等待）  
- **前端**：约 **4～6 人日**  
- **整体**：约 **3～5 周**日历时间（并行 A4/A5 可与 A2 部分重叠）  
- **是否需要 vendor / 外部审批**：**是**（A2/A3 必选；A5 若动量定义依赖新数据亦为「是」）  

---

## 9. 依赖与前置

- **必须先完成**：治理上对新闻/公告读取范围的原则批复；DuckDB 中新闻事件表字段事实确认（支撑 A2）。  
- **可并行**：A4 与 A1；A5 评审可与 A2 数据探查并行。  
