# Stock Analysis Stage 3 — 新闻 / 公告 / 财报事件接入

## 0. 元信息

- **创建日期**：2026-05-08  
- **作者标识**：Stage 3 planning subagent  
- **关联改造方案**：`c:\Users\arvin\.cursor\plans\stock_analysis_revamp_plan_d45b33b0.plan.md`

---

## 1. 背景与动机

- **Stage 1 / Stage 2 已落地的程度**  
  - 股票页已在候选证据卡的「反证 / 待补证据」中声明：基本面与估值、**新闻 / 公告 / 财报尚未进入证据链**——见 handoff `docs/handoff/2026-05-06-stock-analysis-workbench-codex.md` §3 Task 3 业务口径与测试断言要求；对应实现应在 `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts` 的文案中延续。  
  - Stage 2：`GET /ui/market-data/livermore/stock-detail`（`backend/app/api/routes/market_data_livermore.py`）提供 **价格 + 因子快照**，不包含事件时间轴。  
  - **新闻接口现状**：`GET /ui/news/choice-events/latest` 在 `backend/app/api/routes/choice_news.py` 内 **无条件** `HTTP 503`，`detail="Choice news surfaces are reserved by the current boundary."`；同文件 `tushare_npr_ingest_*` 亦同样保留。业务读取逻辑实际已在 `backend/app/services/choice_news_service.py` 的 `choice_news_latest_envelope` 中实现（查询表 `choice_news_event`）。  
  - **表现状**：`choice_news_event` DDL 在 `backend/app/schema_registry/duckdb/12_choice_news.sql`（字段含 `event_key`、`received_at`、`topic_code`、`payload_text` / `payload_json` 等）。  
  - **公告 / 财报**：仓库内 **未发现** 专用 DuckDB 表或 `/ui/...` 路由（本次检索未见 `announcement` / `earnings` 类 schema 文件）；立项默认视为 **从零建设**。

- **业务价值**  
  1. 把「价格 + 板块」之外的 **叙事证据** 接入同一工作台，满足 handoff 对候选卡证据闭环的要求。  
  2. 缓解用户在 Stage 2 抽屉中只有 OHLCV/PE/PB 却无法对照同日事件的 **认知断层**。  
  3. 为未来 Agent `page_context`（`frontend/src/features/stock-analysis/lib/buildStockAnalysisAgentPageContext.ts`）扩展「事件摘要」提供结构化素材。

- **不做的成本**  
  候选股仍停留在技术面自洽；重大公告空白会导致误判风险——与 P0「证据优先」定位不一致。

---

## 2. 业务目标与不做边界

### 必须做

1. **解除或分层解除** `choice_news` 503：至少提供一条 **受控只读** UI 路径返回 `choice_news_latest_envelope`（权限 / feature flag / auth 策略需在实现任务书中写死）。  
2. 定义 **按股票代码过滤** 的查询契约（新闻 payload 解析规则、失败降级）；候选股卡 / `StockDetailDrawer.tsx` 可展示「最近 N 条相关资讯」摘要列表。  
3. **公告 / 财报**：新建专用表（或统一 `corporate_event` 表含 `event_kind`）+ ingest 任务设计文档；最小只读 API `/ui/news/...` 或 `/ui/market-data/...` 由评审选定（须符合 `/ui/<domain>/<path>`）。  
4. 所有响应使用 `build_result_envelope`，显式 `quality_flag`、`tables_used`。  
5. **合规文案**：页面继续声明「仅供观察复核，不构成交易指令」（handoff §2）。  
6. 测试：`tests/` 覆盖新路由；前端 `StockAnalysisPage.test.tsx` 或 `StockDetailDrawer.test.tsx` 增加 mock 事件列表渲染断言。

### 明确不做

1. 不做自动交易、下单、跟单（handoff §2）。  
2. 不把未经校验的 LLM 摘要标为事实；若引入生成式摘要须单独评审数据源与免责声明。  
3. 不在首期覆盖全市场实时 streaming；默认 **快照 / 拉取** 模式。  
4. 不修改 `frontend/src/api/client.ts` 违反 debt guardrails。  
5. 不擅自扩容 `choice_news_event` 对外 ingest 权限而不经 security review。

---

## 3. 后端能力差距清单

| 能力 | 现状 | 缺口 | 工作量量级 |
|------|------|------|------------|
| Choice 新闻只读查询 | **部分具备**：`choice_news_service.py` + 表 `choice_news_event`（`12_choice_news.sql`） | **路由人为 503**：`choice_news.py` `choice_events_latest` | **S**（解封 + 鉴权） |
| 新闻按 stock_code 关联 | **部分 / 待验证**：依赖 `payload_json` / `payload_text` 解析 | 解析器 + 索引策略（可能需生成列或侧写表） | **M** |
| 公告（上交所 / 深交所 / 港交所等） | **缺失** | 数据源契约 + 新表 + ingest + API | **L** |
| 财报日历 / 财报披露事件 | **缺失** | 同上 | **L** |
| Tushare NPR ingest | **代码存在但路由 503**：`choice_news.py` `_raise_choice_news_reserved_surface` | 决策是否启用或替换 | **M** |

---

## 4. 数据契约草案

### 新增表（财报 / 公告统一事件表示例）

```sql
-- MOSS:STMT
create table if not exists choice_stock_corporate_event (
  event_key varchar,
  trade_date varchar,
  stock_code varchar,
  event_kind varchar,
  title varchar,
  summary varchar,
  source_system varchar,
  source_doc_url varchar,
  payload_json varchar,
  received_at varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
```

### Endpoint 草案

1. **解封新闻列表（UI）**  
   - `GET /ui/news/choice-events/latest`  
   - **现状**：直接 503；目标改为调用 `choice_news_latest_envelope`（参数保持 `limit`、`offset`、`topic_code` 等，`choice_news_service.py` 已支持）。  

2. **按股聚合（推荐新增，避免前端扫全表）**  
   - `GET /ui/news/stock-events/recent?stock_code=&as_of_date=&limit=`  
   - `result` 草案：`{ "items": [ { "event_key", "received_at", "headline", "event_kind", "payload_excerpt" } ] }`  

3. **财报 / 公告统一读取（表就绪后）**  
   - `GET /ui/news/corporate-events/recent?stock_code=&as_of_date=`  

### 前端 TS 草案

```ts
export type StockNewsEventListItem = {
  event_key: string;
  received_at: string;
  headline: string;
  topic_code?: string | null;
  event_kind?: "news" | "announcement" | "earnings" | string;
};

export type StockNewsEventsPayload = {
  stock_code: string;
  as_of_date: string | null;
  items: StockNewsEventListItem[];
};
```

---

## 5. 治理与合规风险

- **Vendor 凭据**：任何新增 ingest（公告/财报 API）必须对照 `AGENTS.md` 与 handoff「禁止私自改 Choice/Tushare 权限」条款走审批。  
- **503 边界的历史意图**：当前 `choice_news.py` 注释写明 surfaces「reserved」——解封需记录决策人与补偿控制（鉴权、速率限制、内网可见性）。  
- **个人信息 / 内幕信息**：展示字段避免未经脱敏的交易员笔记类文本；仅用公开披露字段。  
- **正式金融口径**：事件列表为 **叙事证据**，不进入 `core_finance` 估值引擎；与 Formal 报表数字不得自动勾稽混淆。  
- **Formal / Scenario**：只读 API；写入仅限任务链路 materialize。

---

## 6. 实施分解

1. **后端任务 1**：治理评审：解除 503 的条件、`ensure_user_allowed` 资源键设计（参考 `choice_news.py` ingest 侧 `choice_news.data`）。  
   - **验证**：pytest 命中新行为 + `tests/test_result_meta_on_all_ui_endpoints.py`（文件已引用 `/ui/news/choice-events/latest`，需更新期望）。  
2. **后端任务 2**：实现 `GET /ui/news/stock-events/recent` + service 层 SQL（duckdb 只读）。  
   - **验证**：`uv run --project backend python -m pytest tests/<new_choice_news_stock_events>.py -q`  
3. **后端任务 3**：`choice_stock_corporate_event` DDL + ingest stub task（可先 seed fixture）。  
   - **验证**：schema_registry 注册校验 + pytest  
4. **前端任务 1**：`marketDataClient.ts` 新方法；在 `StockDetailDrawer.tsx` 显示事件列表（空态显式）。  
   - **验证**：`npm run test -- src/test/StockDetailDrawer.test.tsx`  
5. **前端任务 2**：候选卡可选一行「最近事件摘要」折叠区。  
   - **验证**：`npm run test -- src/test/StockAnalysisPage.test.tsx` + `npm run debt:audit`

---

## 7. 验收清单

- [ ] `/ui/news/choice-events/latest` 在授权环境下返回 200 + envelope（非全局敞开则由集成测试证明）。  
- [ ] 新股事件接口可按 `stock_code` 过滤且性能可接受（.limit 条件下）。  
- [ ] **测试**：新增专用 pytest；更新 `tests/test_result_meta_on_all_ui_endpoints.py` 中对应该路径的断言。  
- [ ] **debt audit**：`npm run debt:audit`  
- [ ] **回归**：`tests/test_market_data_livermore_stock_detail.py`、`frontend/src/test/StockAnalysisPageModel.test.ts`

---

## 8. 工作量评估与排期建议

- **后端**：解封 + 按股查询 **3～5 人日**；公告 + 财报全链路 **15～25 人日**（含 vendor 联调）。  
- **前端**：**3～6 人日**  
- **整体**：MVP（仅新闻解封 + 按股）**~1 周**；含公告财报 **~4～8 周**  
- **外部审批**：**需要**（数据源合同 + InfoSec）

---

## 9. 依赖与前置

- **必须先完成**：503 解除的架构决策记录；`choice_news_event` 实际是否有生产写入（若表空则需先跑 ingest）。  
- **可并行**：与板块多日立项、候选复盘表 **可并行**，注意共用 DuckDB 连接池配置。
