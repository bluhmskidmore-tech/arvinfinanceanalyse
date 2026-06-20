# Stock Analysis Stage 3 — 候选股历史复盘（入选后 1D / 5D / 20D）

## 0. 元信息

- **创建日期**：2026-05-08  
- **作者标识**：Stage 3 planning subagent  
- **关联改造方案**：`c:\Users\arvin\.cursor\plans\stock_analysis_revamp_plan_d45b33b0.plan.md`

---

## 1. 背景与动机

- **Stage 1 / Stage 2 已落地的程度**  
  - **候选来源**：`GET /ui/market-data/livermore` 返回 `stock_candidates.items`（类型见 `frontend/src/api/contracts.ts` `LivermoreStockCandidateItem`）；后端组装入口 `backend/app/services/market_data_livermore_service.py`，候选核心计算在 `backend/app/core_finance/livermore_stock_candidates.py`（改造方案 §1、§4）。  
  - **单日复核**：Stage 2 `GET /ui/market-data/livermore/stock-detail`（`market_data_livermore.py`）+ `livermore_stock_detail_service.py` 提供回望 **K 线窗口**（默认 `lookback` query）与当日因子，但这是「任意时点复盘」，**并不自动锚定「入选当日」**。  
  - **历史入选快照**：仓库全文检索 **`livermore_candidate_history`** **无命中**——确认当前 **无表、无服务、无 API**。改造方案 §5 建议新表 `livermore_candidate_history`。

- **业务价值**  
  1. 回答「入选后短中期价格怎么走」这一研究工作台核心追问，形成 **可审计的回测叙事**（仍非投资建议）。  
  2. 支持策略迭代：统计假阳性 / 假阴性模式（实现期可只做单行展示，不做大盘报表）。  
  3. 与 handoff「P1 候选股复盘」方向一致（handoff §8）。

- **不做的成本**  
  候选卡永远是「当下快照」，无法对齐历史决策日；团队无法复盘 Livermore 信号的 **时间后验**。

---

## 2. 业务目标与不做边界

### 必须做

1. 新建表 **`livermore_candidate_history`**（或评审更名）记录每次候选集中的 `(as_of_date, stock_code, rank, …)` 快照元数据。  
2. **离线或定时任务**：在每日 livermore 策略物化完成后追加写入（与 `choice_stock_materialize_run` 调度对齐方式需在任务书里写明）。  
3. 计算并存储 **入选日后 1 / 5 / 20 个交易日** 的收益指标（定义收盘价来源为 `choice_stock_daily_observation.close_value`，交易日历对齐逻辑必须文档化）。  
4. 新增只读 API：`GET /ui/market-data/livermore/candidate-history`（支持按 `stock_code`、`from`、`to` 过滤）。  
5. 前端：在 `StockDetailDrawer.tsx` 或候选卡扩展区展示「入选记录 + 后续收益」；缺失显示「未快照」而非造假。  
6. 测试：pytest fixture 写入最小 history + API；前端契约测试。

### 明确不做

1. 不做实盘撮合与下单（handoff §2）。  
2. 不把复盘结果改写为「胜率承诺」或投顾话术。  
3. 首期不做横截面全市场回测报表（仅 **事件级 / 股票级** 查询）。  
4. 不在前端用浏览器本地缓存伪造历史（必须以服务端表为准）。  
5. 不引入未经评审的第三方收益指数作为基准（若需沪深300同步扩展，须第二阶段单独立项）。

---

## 3. 后端能力差距清单

| 能力 | 现状 | 缺口 | 工作量量级 |
|------|------|------|------------|
| 候选当日截面 | **已具备**：策略 payload `stock_candidates`（`market_data_livermore_service.py`） | **无持久化入选记录** | **M** |
| 交易日序列 | **已具备**：`choice_stock_daily_observation.trade_date` + OHLC（`21_choice_stock.sql`） | 需 **精确推算** T+1 / T+5 / T+20 **交易日**（跳过停牌策略） | **M** |
| `livermore_candidate_history` | **缺失**（检索无） | DDL + task + read API | **M** |
| 归因分解（alpha / beta） | **缺失** | 首期可不建；列入 unsupported | **L**（后续） |

---

## 4. 数据契约草案

### DDL 草案

```sql
-- MOSS:STMT
create table if not exists livermore_candidate_history (
  snapshot_as_of_date varchar,
  stock_code varchar,
  stock_name varchar,
  candidate_rank integer,
  sector_code varchar,
  sector_name varchar,
  selection_close double,
  forward_trade_date_1d varchar,
  forward_trade_date_5d varchar,
  forward_trade_date_20d varchar,
  return_1d double,
  return_5d double,
  return_20d double,
  data_status varchar,
  formula_version varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
```

说明：`data_status` 可用 `complete` / `partial_halt` / `missing_bar`；停牌处理规则在实现规格书中锁定。

### Endpoint 草案

- **Path**：`GET /ui/market-data/livermore/candidate-history`  
- **Query**：`stock_code`（可选）、`snapshot_from`、`snapshot_to`、`limit`  
- **Envelope**：与其它 livermore UI 一致；`result` 草案：

```json
{
  "items": [
    {
      "snapshot_as_of_date": "2026-04-01",
      "stock_code": "600000.SH",
      "candidate_rank": 1,
      "return_1d": 0.012,
      "return_5d": -0.03,
      "return_20d": 0.08,
      "data_status": "complete"
    }
  ]
}
```

### 前端 TS 草案

```ts
export type LivermoreCandidateHistoryRow = {
  snapshot_as_of_date: string;
  stock_code: string;
  stock_name?: string | null;
  candidate_rank: number;
  return_1d: number | null;
  return_5d: number | null;
  return_20d: number | null;
  data_status: string;
};
```

---

## 5. 治理与合规风险

- **写入路径**：新增任务写入 DuckDB，触碰「API 只读、写入仅任务链路」原则——必须与现有 `choice_stock_materialize_run`、`livermore_position_snapshot` materialize 模式对齐并接受 code review。  
- **AGENTS.md Forbidden**：未经指令不扩全局调度框架；任务实现应保持单一模块（如 `backend/app/tasks/livermore_candidate_history_materialize.py` 草案名）。  
- **正式金融口径**：收益列为 **事后 analytical 指标**，不得与 Formal PnL 混读；不在 `core_finance` 声称估值准确性。  
- **Formal / Scenario**：若存在 Scenario 库副本，需指明 history 表写入 **唯一权威库** 或在 envelope 标注 `basis`。

---

## 6. 实施分解

1. **后端任务 1**：冻结收益定义（总回报、是否含分红、停牌填充规则）。  
   - **验证**：文档评审签字（非代码）+ 单元测试 `tests/test_livermore_candidate_returns_math.py`  
2. **后端任务 2**：DDL + task：从当日 `stock_candidates` 快照写入 history + 回填 forward returns。  
   - **验证**：`uv run --project backend python -m pytest tests/test_market_data_livermore_candidate_history.py -q`  
3. **后端任务 3**：注册 `GET /ui/market-data/livermore/candidate-history`。  
   - **验证**：扩展 `tests/test_market_data_livermore_api.py` 或并行新文件  
4. **前端任务 1**：`marketDataClient.ts` + Drawer 区块；loading / empty / partial。  
   - **验证**：`npm run test -- src/test/StockDetailDrawer.test.tsx`  
5. **全局**：`npm run typecheck` + `npm run debt:audit`

---

## 7. 验收清单

- [ ] 表中存在至少一段连续交易日的样本数据可通过 API 读出。  
- [ ] `return_*` 与手工 SQL 对账抽样一致。  
- [ ] **测试**：`tests/test_market_data_livermore_candidate_history.py`（最终文件名随仓库惯例）  
- [ ] **debt audit**  
- [ ] **回归**：`tests/test_market_data_livermore_stock_detail.py`、`tests/test_livermore_stock_candidates.py`、`frontend/src/test/StockAnalysisPage.test.tsx`

---

## 8. 工作量评估与排期建议

- **后端**：**6～10 人日**（含停牌边界与测试）  
- **前端**：**2～4 人日**  
- **整体周期**：**~2 周**  
- **Vendor 审批**：通常 **不需要**（基于已有 `choice_stock_daily_observation`）；若扩展基准指数则另计。

---

## 9. 依赖与前置

- **必须先完成**：`choice_stock_daily_observation` 对复盘区间的覆盖；策略 `as_of_date` 与 `trade_date` 对齐规则（与 `livermore_stock_detail_service.py` 中 `_resolve_end_trade_date` 一致或可复用）。  
- **可并行**：与新闻立项、板块多日立项并行；**建议在 Stage 2 稳定后**再挂任务（避免候选公式频繁变更导致历史口径抖动）。
