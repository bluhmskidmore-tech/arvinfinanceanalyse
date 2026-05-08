# Stock Analysis Stage 3 — 板块强度扩展（多日累计 / 动量 / 资金流向）

## 0. 元信息

- **创建日期**：2026-05-08  
- **作者标识**：Stage 3 planning subagent  
- **关联改造方案（权威）**：`c:\Users\arvin\.cursor\plans\stock_analysis_revamp_plan_d45b33b0.plan.md`（文中简称「改造方案」）

---

## 1. 背景与动机

- **Stage 1 / Stage 2 已落地的程度（引用改造方案与代码）**  
  - Stage 1：`StockAnalysisPage.tsx` 已实现「本日判断条」、板块强度 **单日** 视图（条形图 / Top-Bottom / `score`·`avg_pctchange`·`avg_turn`·`avg_amplitude` 四 Tab），且页面文案写明「暂不包含 N 日累计强度（需后端 sector_rank 字段扩展）」——见 `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`（与板块说明段落）。数据全部来自 `GET /ui/market-data/livermore` 返回的 `sector_rank.items`（改造方案 §3.6、§5）。  
  - View-model：`frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts` 负责sector 行构建与排序视图（不重算正式指标）。  
  - Stage 2：`GET /ui/market-data/livermore/stock-detail` + `backend/app/services/livermore_stock_detail_service.py` 已提供单股 OHLCV + `choice_stock_factor_snapshot` 因子装配（改造方案 §4）；与「板块多日序列」无直接重叠但共用行情表 `choice_stock_daily_observation`（定义见 `backend/app/schema_registry/duckdb/21_choice_stock.sql`）。  
  - **单日板块打分源头**：`backend/app/core_finance/livermore_sector_rank.py` 中 `compute_sector_rank` 仅聚合 **单个 `as_of_date` 截面** 上的成分股 `pctchange` / `turn` / `amplitude`，产出 `items[].score` 等字段；`backend/app/services/market_data_livermore_service.py` 调用该函数写入策略 envelope。

- **为什么需要本项（业务价值）**  
  1. 单日领涨板块可能是噪声；研究工作台需要「持续走强 / 走弱」与多日累计强度，才能支撑「趋势是否延续」的复核问题。  
  2. 「动量持续度」（例如在若干交易日内排名稳定性或得分变化）无法由单日 `items` 推导而不触碰多日聚合逻辑；按 `AGENTS.md`，不应在前端自行拼装正式意义上的多日合成指标。  
  3. 「资金流向」若作为证据维度，需可溯源的数据落库与 envelope；当前 schema_registry 下未见资金流向相关表（已对 `backend/app/schema_registry/duckdb/` 关键词检索 `资金流向|northbound|money_flow` 无命中）。

- **不做的成本**  
  用户只能依赖单日截面，容易误判短期轮动；与 handoff 中「反证 / 待补证据」里对基本面与事件缺失的提醒类似，会长期缺少「板块层级的时间维度证据」，降低工作台可信度。

---

## 2. 业务目标与不做边界

### 必须做

1. 后端提供 **可追溯的多日板块序列或聚合指标**（至少支持常用窗口如 5 / 20 交易日，具体窗口以评审为准），并与现有 `sector_rank.formula_version`  lineage（`source_version` / `vendor_version` / `rule_version`）风格一致。  
2. 新增或扩展 **只读** `GET` API（`/ui/market-data/...`），返回 `build_result_envelope` 风格 meta + payload，便于前端延续 Stage 1 的 stale / partial 展示习惯。  
3. 明确定义「动量持续度」的计算口径（文档级可先给 1～2 个候选定义，实现前锁定其一），并在 diagnostics / unsupported 中可解释降级原因。  
4. 「资金流向」：**要么** 接入已批准 vendor 数据并入 DuckDB 表 + 文档化字段含义，**要么** 在首期立项中明确列为后续 phase（本立项表格须写清当前缺口）。  
5. 前端只消费后端字段：**表格或小型多序列图**展示多日强度 / 动量标签；不在前端重算板块official合成得分。  
6. 最小 pytest + 前端契约测试：`tests/` 新增专用文件 + `contracts.ts` / `marketDataClient.ts` 类型对齐后的编译与既有页面回归。

### 明确不做（避免范围蔓延）

1. 不引入买卖建议、成交下单或组合调仓指令（延续 `docs/handoff/2026-05-06-stock-analysis-workbench-codex.md` §2）。  
2. 不做「银行股专题」或单一行业定制视图（改造方案明确不做银行股专题）。  
3. 不在 `frontend/src/api/client.ts` 堆砌 endpoint（新客户端方法放在 `frontend/src/api/marketDataClient.ts` 等域客户端，`AGENTS.md` Frontend debt guardrails）。  
4. 首期不把全域主力资金流大屏做成通用框架；仅服务股票分析页证据条目的最小字段集。  
5. 不擅自改动 Formal / Scenario 隔离语义；Livermore 链路保持 **analytical** 口径表述（与现有策略 envelope 一致）。

---

## 3. 后端能力差距清单

| 能力 | 现状 | 缺口 | 工作量量级 |
|------|------|------|------------|
| 单日板块 rank / score / 四均值字段 | **已具备**：`compute_sector_rank` → `sector_rank.items`（`backend/app/core_finance/livermore_sector_rank.py`）；经 `market_data_livermore_service.py` 挂入 `GET /ui/market-data/livermore`（`backend/app/api/routes/market_data_livermore.py`） | 无多日视图 | — |
| 多日 sector 得分序列 | **缺失**：单日函数仅接收当日 `rows`，无历史序列输出 | 需按交易日回溯聚合（新材料化表 **或** 查询时 join 多日 `choice_stock_daily_observation` + sector membership） | **L** |
| 动量持续度（排名稳定性 / Δscore） | **缺失**：无字段 | 需定义口径后在后端计算并版本号递增（新 `formula_version` 或扩展字段） | **M** |
| 板块级资金流向 | **缺失**：`schema_registry/duckdb` 无相关表 | vendor / ETL / 新表（如保留日后命名：`choice_stock_sector_money_flow_daily` 级草案） | **L**（含采购与合规） |
| 成分股 OHLCV | **已具备**：`choice_stock_daily_observation`（`21_choice_stock.sql`） | 多日聚合性能与交易日对齐策略需设计 | **M** |
| 行业归属 | **已具备**：`choice_stock_sector_membership`（`21_choice_stock.sql`） | 与多日行情 join 的正确性与缺失 sector 处理 | **M** |

---

## 4. 数据契约草案

### 新增表（DDL 草案，命名与 `21_choice_stock.sql` / `27_choice_stock_factor_snapshot.sql` 一致：`varchar` 日期、`double` 数值、lineage 列）

```sql
-- MOSS:STMT
-- 按交易日物化板块聚合，供多日窗口查询；formula 变更通过 rule_version 区分。
create table if not exists livermore_sector_rank_daily (
  trade_date varchar,
  sector_code varchar,
  sector_name varchar,
  avg_pctchange double,
  avg_turn double,
  avg_amplitude double,
  constituent_count integer,
  score double,
  rank integer,
  formula_version varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
```

（备选：若坚持「零新表」，则用只读服务运行时聚合；须在验收里写明性能上限与 DuckDB 压力测试结果。）

### 新增 endpoint（草案）

- **Path**：`GET /ui/market-data/livermore/sector-rank-series`  
- **Query**：`as_of_date`（可选 ISO）、`window_days`（如 5 / 20，整数）、`sector_code`（可选，缺省返回全市场 Top-K 板块序列）  
- **响应 envelope**：沿用 `build_result_envelope`（参考 `livermore_stock_detail_service.py` 中 `RESULT_KIND` / `RULE_VERSION` / `CACHE_VERSION` 模式）；`result` 草案：

```json
{
  "as_of_date": "2026-05-08",
  "window_days": 20,
  "formula_version": "rv_livermore_sector_rank_series_v1",
  "series": [
    {
      "trade_date": "2026-05-08",
      "sector_code": "SW801780",
      "sector_name": "银行",
      "score": 0.0123,
      "rank": 1,
      "avg_pctchange": 0.004,
      "momentum_persistence": 0.73
    }
  ],
  "unsupported_notes": []
}
```

- **资金流向（若单独立 sub-endpoint）**：`GET /ui/market-data/livermore/sector-flow-daily?as_of_date=&sector_code=`（仅在表就绪后启用；否则返回 `unsupported_outputs` 理由）。

### 前端 contracts 草案（`frontend/src/api/contracts.ts` 风格）

```ts
export type LivermoreSectorRankSeriesPoint = {
  trade_date: string;
  sector_code: string;
  sector_name: string;
  score: number;
  rank: number;
  avg_pctchange: number;
  avg_turn?: number | null;
  avg_amplitude?: number | null;
  momentum_persistence?: number | null;
  net_flow_amount?: number | null;
};

export type LivermoreSectorRankSeriesPayload = {
  as_of_date: string;
  window_days: number;
  formula_version: string;
  series: LivermoreSectorRankSeriesPoint[];
  unsupported_notes: string[];
};
```

---

## 5. 治理与合规风险

- **凭据 / 配额**：若资金流向来自 Choice / Tushare / 其他 vendor，须走与现有股票落地一致的密钥治理（handoff §2 禁止私自改凭据）；新增 ingest 需登记 `choice_stock_request_audit` 同类审计模式者可类比设计。  
- **AGENTS.md Forbidden**：不改 unrelated 全局架构；若需要新材料化任务，仅限与本功能相连的 tasks 模块，不扩散「通用队列抽象」。  
- **正式金融口径**：板块序列仍属 **Livermore analytical** 展示链路，不冒充 `core_finance` 正式估值或组合损益；若未来与 Formal 报表对齐，须单独评审迁移路径。  
- **Formal / Scenario**：读取 DuckDB 保持 API 只读；写入仅在明确 batch / task 链路（与 `livermore_position_snapshot` POST 不同权限模型——本特性默认 **只读 API + 后台任务写聚合表**）。

---

## 6. 实施分解（任务拆分）

1. **后端任务 1**：定型口径文档（窗口、缺失日处理、rank tie-break 是否与单日一致）；在 `backend/app/core_finance/` 或专用 service 中实现多日聚合纯函数 + 单元测试。  
   - **验证**：`uv run --project backend python -m pytest tests/test_livermore_sector_rank.py tests/<new_sector_series_tests>.py -q`  
2. **后端任务 2**：落地 DDL 至 `backend/app/schema_registry/duckdb/` + migrations 流程（按仓库既有 pattern）；可选 materialize 任务写入 `livermore_sector_rank_daily`。  
   - **验证**：`uv run --project backend python -m pytest tests/test_market_data_livermore_api.py -q`（扩展 case）  
3. **后端任务 3**：在 `market_data_livermore.py` 注册 `GET .../sector-rank-series`，service 层只做 orchestrate + envelope。  
   - **验证**：同上 + 手工 `curl` local `/ui/market-data/livermore/sector-rank-series?window_days=5`  
4. **前端任务 1**：`marketDataClient.ts` 增加 fetch；`contracts.ts` 类型；在 `StockAnalysisPage.tsx` 或子组件增加「多日」折叠区（遵循 `DESIGN.md` 层次）。  
   - **验证**：`cd frontend && npm run test -- src/test/StockAnalysisPage.test.tsx --pool=forks --poolOptions.forks.singleFork=true`  
5. **前端任务 2**：`npm run typecheck` + `npm run debt:audit`  

---

## 7. 验收清单

- [ ] `GET /ui/market-data/livermore/sector-rank-series`（或评审通过的等价路径）返回 envelope，且在无数据时 `quality_flag` / diagnostics 可解释。  
- [ ] 多日口径与 `rv_livermore_sector_rank_provisional_v1` 单日结果可对账（抽样某日重叠截面）。  
- [ ] **测试覆盖**：新增 `tests/test_market_data_livermore_sector_rank_series.py`（命名可按最终实现调整）；扩展 `tests/test_livermore_sector_rank.py` 若核心函数变更。  
- [ ] **debt audit**：`cd frontend && npm run debt:audit`  
- [ ] **Stage 1/2 回归**：`tests/test_market_data_livermore_stock_detail.py`、`frontend/src/test/StockDetailDrawer.test.tsx`、`frontend/src/test/StockAnalysisPageModel.test.ts`

---

## 8. 工作量评估与排期建议

- **后端**：**8～12 人日**（无资金流向下限）；含资金流向 vendor + ETL **+5～10 人日**。  
- **前端**：**3～5 人日**（图表选型复用现有 ECharts/Recharts 栈前提下）。  
- **整体周期建议**：**2～3 周**（不含外部采购评审）；含资金流向则 **4～6 周**。  
- **是否需要 vendor / 外部审批**：资金流向 **需要**；纯多日聚合基于现有 Choice 落地则可内部闭环。

---

## 9. 依赖与前置

- **必须先完成**：`choice_stock_daily_observation` 与 `choice_stock_sector_membership` 对目标交易日的覆盖率可查（现有 readiness 逻辑见 `load_choice_stock_readiness` 调用链）。  
- **可并行**：与「新闻 / 公告」立项无硬顺序依赖；但与共用 DuckDB IO 的 peak 压力建议在 implementation 阶段错峰联调。
