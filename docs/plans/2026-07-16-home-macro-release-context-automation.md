# Home Macro Release Context Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让首页“过往数据与变动”由自动采集、可追溯的数据链持续供数；中国 PMI、CPI、PPI、GDP 首批自动展示，美国尚未接通的指标明确显示 `source_pending`，任何故障都不再回退到人工维护的历史数值。

**Architecture:** 保持 `PAGE-DASH-001` 的首页主合同不变，新增页面专用 analytical 读模型 `GET /ui/home/macro-release-context`。后端从现有 DuckDB 自动数据表读取并完成批次去重、前值选择、变动计算、新鲜度和来源状态聚合；前端通过现有首页 Executive 轻量客户端延迟请求，只负责格式化和状态呈现。稳定指标映射可配置，但配置严禁保存观测值、前值、变动值或逐期日期。首版不改数据库结构、权限框架、队列/调度底座和 `/ui/home/snapshot`。

**Tech Stack:** Python 3.12, FastAPI, Pydantic, DuckDB, Dramatiq, React 19, TypeScript, TanStack Query, Vitest, Testing Library, Playwright

---

## 1. 已确认的根因

1. 当前首页历史值来自 `config/dashboard_macro_release_calendar_2026.json`，由 `buildHomeMacroBriefingModel.ts` 直接读取；它不是自动供数链。
2. 自动宏观数据已经部分存在：
   - 中国制造业 PMI：`fact_choice_macro_daily` / `M0017126`；
   - 中国 CPI：`std_external_macro_daily` / `tushare.macro.cn_cpi.monthly`；
   - 中国 PPI：`std_external_macro_daily` / `tushare.macro.cn_ppi.monthly`；
   - 中国 GDP YoY：`std_external_macro_daily` / `tushare.macro.cn_gdp.quarterly`。
3. `run_tushare_macro_ingest_once` 没有向 `TushareMacroIngestService` 注入已有的 `ExternalStdMacroEtlService`，正式入口只落 raw/catalog/manifest，不能保证新批次持续进入 `std_external_macro_daily`。
4. `std_external_macro_daily` 会保留同一 `series_id + trade_date` 的多个采集批次；首页读取前必须选定最新批次，不能直接 `LIMIT 2`。
5. 当前仓库没有美国 ISM、BLS CPI/PPI、非农/失业率、BEA GDP、FOMC 的完整自动采集链。首版必须显式返回 `source_pending`，不能继续显示静态值。
6. `std_tushare_eco_cal_event` 当前存在重复、陈旧、乱码风险，并且没有进入 schema registry，也没有 tracked producer；首版不能把它当历史数值真相。

## 2. 业务与治理边界

- 页面：`/`，合同：`PAGE-DASH-001`。
- 区块：`macro_release_context`，角色始终是 `supplemental`。
- 该区块不进入首屏主判断，不改变 `/ui/home/snapshot`，也不参与首页严格报告日裁决。
- 自然日窗口和首页 `report_date` 必须分开。新接口只使用 `start_date`、`end_date`、`history_limit`，不复用 `report_date`。
- `result_meta.basis = analytical`、`formal_use_allowed = false`、`source_surface = market_data`。
- `release_date`、`observation_date`、`previous_observation_date` 是三个不同语义，禁止互换。
- `previous_value` 不能使用 forecast 代替；未来若展示 forecast，必须单独建字段。
- `null`、`0`、缺失、未接入必须严格区分。
- 数值变动只在后端基于同一序列、同一单位、最近两期有效观察计算；前端不得重复计算。
- 静态配置可以保存稳定的指标语义和数据源绑定，但不得保存：
  - `history`
  - `latest_value`
  - `previous_value`
  - `change_value`
  - 逐期 observation/release 数值记录
- 切换后禁止静态数值 fallback。接口失败时显示“自动数据暂不可用”。

## 3. 交付分层

### Phase A：自动历史值闭环，本计划的主交付

- 打通 Tushare 标准化写入。
- 新增首页专用读模型。
- 中国 PMI、CPI/PPI、GDP 自动展示。
- 美国指标显示 `source_pending`。
- 删除现有 JSON 中所有历史数值。
- 配置并验证自动刷新任务。

### Phase B：自动未来发布日期，需单独批准 schema 治理

- 为 Tushare `eco_cal` 或官方发布日历建立 schema registry 和 tracked producer。
- 自动去重、Unicode 校验、新鲜度校验和稳定 event id。
- 前端未来事项从自动接口切换后，删除年度静态发布日期文件。

Phase B 涉及数据库治理范围；在获得明确批准前，Phase A 只删除静态历史数值，现有未来发布日期元数据可以暂留，但不得被描述为自动供数。

## 4. 首批数据绑定

| 展示组 | 指标 | 自动读取面 | series_id | 单位 | 首版状态 |
|---|---|---|---|---|---|
| 中国 PMI | 制造业 PMI | `fact_choice_macro_daily` | `M0017126` | `index` | `ready/stale/partial` |
| 中国通胀 | CPI YoY | `std_external_macro_daily` | `tushare.macro.cn_cpi.monthly` | `%` | `ready/stale/partial` |
| 中国通胀 | PPI YoY | `std_external_macro_daily` | `tushare.macro.cn_ppi.monthly` | `%` | `ready/stale/partial` |
| 中国增长 | GDP YoY | `std_external_macro_daily` | `tushare.macro.cn_gdp.quarterly` | `%` | `ready/stale/partial` |
| 美国 ISM | 制造业/服务业 | 未接入 | — | `index` | `source_pending` |
| 美国通胀 | CPI/PPI | 未接入 | — | `%` | `source_pending` |
| 美国就业 | 非农/失业率 | 未接入 | — | 人数/% | `source_pending` |
| 美国增长 | GDP | 未接入 | — | `%` | `source_pending` |
| FOMC | 利率决议 | 未接入 | — | `%/bp` | `source_pending` |

机器合同统一使用以下 literal：`display_unit = index | pct | persons`，`change_unit = index_point | pct_point | persons | bp`。前端仅在展示层将 `pct` 格式化为 `%`；配置、后端 schema、API 和 TypeScript contract 禁止使用 `%` 作为 literal。

## 5. API 合同

以下日期是固定、可重复的合同示例，不代表运行时硬编码默认值；生产请求始终按调用当日计算 `today → today+45`。

`GET /ui/home/macro-release-context?start_date=2026-07-16&end_date=2026-08-30&history_limit=8`

推荐响应骨架：

```json
{
  "result_meta": {
    "trace_id": "tr_home_macro_release_context",
    "basis": "analytical",
    "result_kind": "home.macro_release_context",
    "formal_use_allowed": false,
    "source_surface": "market_data",
    "quality_flag": "warning",
    "vendor_status": "ok",
    "fallback_mode": "none",
    "as_of_date": "2026-06-01",
    "date_basis": "macro_observation_period",
    "filters_applied": {
      "start_date": "2026-07-16",
      "end_date": "2026-08-30",
      "history_limit": 8
    },
    "tables_used": [
      "fact_choice_macro_daily",
      "std_external_macro_daily"
    ],
    "evidence_rows": 8
  },
  "result": {
    "window_start_date": "2026-07-16",
    "window_end_date": "2026-08-30",
    "history_items": [
      {
        "indicator_key": "cn_pmi",
        "title": "中国 PMI",
        "region": "CN",
        "category": "activity",
        "importance": "high",
        "reference_period": "2026-06",
        "previous_reference_period": "2026-05",
        "release_date": null,
        "source_status": "ready",
        "source_name": "NBS official PMI release",
        "metrics": [
          {
            "metric_key": "manufacturing_pmi",
            "label": "制造业 PMI",
            "actual_value": 50.3,
            "previous_value": 50.0,
            "change_value": 0.3,
            "display_unit": "index",
            "change_unit": "index_point",
            "precision": 1,
            "direction": "up"
          }
        ],
        "notes": []
      }
    ],
    "coverage": {
      "configured_count": 8,
      "ready_count": 2,
      "partial_count": 0,
      "stale_count": 1,
      "source_pending_count": 5
    },
    "warnings": []
  }
}
```

行级 `source_status`：`ready | partial | stale | fallback | source_pending | error`。

`ResultMeta.fallback_mode` 继续只使用仓库允许的 `none | latest_snapshot`。数据源替代或降级信息放在行级 `source_status/source_name/notes` 和顶层 `warnings`，禁止写入不存在的枚举值。

路由、权限和客户端统一归属首页 Executive family，因此 `result_kind` 使用 `home.macro_release_context`；底层证据仍来自 market data，所以 `source_surface` 保持 `market_data`。不要把 route 放在 home family、却把 result kind 放进另一个 route family。

`coverage` 始终统计第 4 节全部 8 个配置组；`history_items` 按稳定优先级最多返回 `history_limit` 个组，默认 8，不能通过 limit 把未接入状态从 coverage 中隐藏。
自然日窗口权威定义为前端本地日历的 `today → today+45`，由请求显式传给后端；它有意不复用 research calendar 的 `today-7 → today+14` 窗口。后端只有在参数省略时才用服务器当天补默认，并必须把最终窗口回显在 `filters_applied`。

---

### Task 0: 冻结合同、完成影响分析

**Files:**
- Modify: `docs/page_contracts.md`
- Modify: `docs/dashboard_cockpit_contract.md`
- Modify: `docs/MCP_RUNBOOK.md`
- Modify: `tests/test_dashboard_governance_doc_contract.py`
- Create: `docs/handoff/2026-07-16-home-macro-release-context-evidence.md`

**Step 0: 取得业务数据证据**

在决定 DTO 和绑定前，必须使用项目 MCP：

- `moss-metric-contracts`：核对 `PAGE-DASH-001`、PMI/CPI/PPI/GDP 的定义、单位、精度、golden sample，以及 natural-day 与 report-date 边界；
- `moss-lineage-evidence`：核对 source/vendor/rule/cache lineage、fallback/stale 状态和当前有效来源；
- `moss-data-catalog`：只读核对表/视图、series/date/value/lineage 列、最近可用观察期和重复批次；
- 把查询、结论和 unresolved 项写入 `docs/handoff/2026-07-16-home-macro-release-context-evidence.md`。

Expected: 四个中国指标的定义、单位、日期语义和来源均有证据。若 MCP 不可用，记录具体 server、所用本地证据和残余风险；无法证明的指标必须保持 `source_pending`，不能靠猜测进入 ready 状态。

该 evidence gate 必须在 Task 1–5 的代码编辑前完成，不能等到上线 tie-out 才补。

**Step 1: 运行 GitNexus 前置检查**

对计划将修改的既有符号逐一运行 upstream impact：

- `run_tushare_macro_ingest_once`
- `TushareMacroIngestService.ingest_series`
- `backfill_macro_series`
- `CANONICAL_TASK_MODULES`
- `_ensure_executive_read_allowed`
- `ExecutiveClientMethods`
- `createRealHomeExecutiveClient`
- `createDeferredApiClient`
- `useDashboardHomeBodyData`
- `useDashboardHomeViewModel`
- `mapToHomeBodyView`
- `buildHomeMacroBriefingModel`
- `ResearchCalendarSection`

Expected: 记录直接调用者、受影响流程和风险等级。任何 `HIGH/CRITICAL` 结果必须先告知用户，再编辑对应符号。若 GitNexus 仍不可用，记录 unavailable、本地证据和残余风险，不得伪造结果。

**Step 2: 写失败的文档合同测试**

在 `tests/test_dashboard_governance_doc_contract.py` 增加断言：

- `macro_release_context` 属于 supplemental；
- `/ui/home/macro-release-context` 是 supporting API；
- natural-day context 不参与 main judgment；
- stale、fallback、source_pending、error 必须可见；
- 禁止静态历史数值 fallback。

**Step 3: 运行测试确认失败**

Run:

```powershell
pytest tests/test_dashboard_governance_doc_contract.py -q
```

Expected: FAIL，原因是新 section/API 合同尚未写入文档。

**Step 4: 最小更新合同文档**

- 在 `PAGE-DASH-001` optional section/status matrix 加入 `macro_release_context`。
- 在 cockpit first-screen admission 表标明“不进入首屏、不参与主判断”。
- 在 MCP runbook supporting APIs 加入新路径和 analytical 边界。

**Step 5: 运行测试确认通过**

Run: `pytest tests/test_dashboard_governance_doc_contract.py -q`

Expected: PASS。

**Step 6: Commit**

```powershell
git add docs/page_contracts.md docs/dashboard_cockpit_contract.md docs/MCP_RUNBOOK.md docs/handoff/2026-07-16-home-macro-release-context-evidence.md tests/test_dashboard_governance_doc_contract.py
git commit -m "docs: lock homepage macro release context contract"
```

---

### Task 1: 打通 Tushare 自动标准化入口

**Files:**
- Modify: `backend/app/tasks/tushare_macro_ingest.py`
- Modify: `backend/app/services/tushare_macro_ingest_service.py`
- Modify: `backend/app/tasks/worker_bootstrap.py`
- Modify: `tests/test_tushare_macro_ingest_task.py`
- Modify: `tests/test_tushare_macro_ingest_service.py`
- Modify: `tests/test_tushare_macro_ingest_retry.py`
- Modify: `tests/test_worker_bootstrap.py`

**Step 1: 写失败测试**

覆盖：

- 正式任务会把有效 raw 数据 materialize 到 `std_external_macro_daily`；
- 返回每个 series 的 `materialized_rows` 和失败原因；
- 空 payload、无有效日期、NaN/无限值不能登记为成功；
- 单个 series 失败时其他 series 可成功，总体状态为 `partial`；
- `refresh_tushare_macro` actor 已注册并由 `worker_bootstrap` 加载。

**Step 2: 运行测试确认失败**

```powershell
pytest tests/test_tushare_macro_ingest_task.py tests/test_tushare_macro_ingest_service.py tests/test_tushare_macro_ingest_retry.py tests/test_worker_bootstrap.py -q
```

Expected: FAIL，正式任务尚未注入 ETL，actor 尚未进入 bootstrap。

**Step 3: 实现最小修复**

在 `run_tushare_macro_ingest_once` 的同一 DuckDB 写连接内：

1. 应用 pending migrations；
2. 构建 `RawZoneRepository`；
3. 构建 `ExternalDataCatalogRepository(conn=conn)`；
4. 构建 `ExternalStdMacroEtlService(raw_zone_repo, conn)`；
5. 将 `etl_service` 注入 `TushareMacroIngestService`；
6. 全部 series 完成后再关闭连接。

用 `register_actor_once("refresh_tushare_macro", ...)` 暴露 actor，并把 `backend.app.tasks.tushare_macro_ingest` 加入 `CANONICAL_TASK_MODULES`。不修改 `15_external_std_macro.sql`，不删除历史批次。

**Step 4: 运行测试确认通过**

Run: 同 Step 2。

Expected: PASS。

**Step 5: Commit**

```powershell
git add backend/app/tasks/tushare_macro_ingest.py backend/app/services/tushare_macro_ingest_service.py backend/app/tasks/worker_bootstrap.py tests/test_tushare_macro_ingest_task.py tests/test_tushare_macro_ingest_service.py tests/test_tushare_macro_ingest_retry.py tests/test_worker_bootstrap.py
git commit -m "fix: materialize automated macro ingest batches"
```

---

### Task 2: 建立不含数值的首页指标绑定

**Files:**
- Create: `config/home_macro_release_bindings.json`
- Create: `tests/test_home_macro_release_bindings_contract.py`

**Step 1: 写失败测试**

测试递归扫描配置并拒绝以下 key：

```text
history
latest_value
previous_value
change_value
observation_date
release_date
```

同时断言：

- 每个 group 有稳定 `indicator_key`；
- 每个自动 metric 有明确 `table/series_id/cadence/display_unit/change_unit/precision`；
- 未接入美国指标明确声明 `source_pending`；
- 配置版本固定为 `rv_home_macro_release_context_v1`。

**Step 2: 运行测试确认失败**

Run: `pytest tests/test_home_macro_release_bindings_contract.py -q`

Expected: FAIL，配置文件尚不存在。

**Step 3: 创建最小配置**

只写入第 4 节的数据源绑定和展示语义。禁止复制当前 JSON 的任何历史数值或逐期日期。

**Step 4: 运行测试确认通过**

Run: `pytest tests/test_home_macro_release_bindings_contract.py -q`

Expected: PASS。

**Step 5: Commit**

```powershell
git add config/home_macro_release_bindings.json tests/test_home_macro_release_bindings_contract.py
git commit -m "feat: define governed homepage macro bindings"
```

---

### Task 3: 新增页面专用 schema 与读仓库

**Files:**
- Create: `backend/app/schemas/home_macro_release_context.py`
- Create: `backend/app/repositories/home_macro_release_context_repo.py`
- Create: `tests/test_home_macro_release_context_schema.py`
- Create: `tests/test_home_macro_release_context_repository.py`

**Step 1: 写 schema 失败测试**

断言：

- envelope 严格包含 `result_meta + result`；
- `actual_value/previous_value/change_value` 允许 `null`，`0` 被保留；
- `release_date` 允许 `null`，不能由 observation date 自动填充；
- 未知 status、unit 或多余字段被拒绝；
- metrics 数组支持单指标和 CPI/PPI 复合组。

**Step 2: 写 repository 失败测试**

使用临时 DuckDB 覆盖：

- 相同 `series_id + trade_date` 多个 ingest batch，只取 `created_at/ingest_batch_id` 最新一批；
- 最新一批值为 `null` 时保持 `null`，不能偷偷使用旧批次或上一期；
- `trade_date > start_date` 的 look-ahead 数据被排除；
- 最近两期均保留 0；
- 缺表返回结构化 `relation_missing`，不抛出 500；
- Choice 数据按 `series_id + trade_date` 去重并保留 lineage。

**Step 3: 运行测试确认失败**

```powershell
pytest tests/test_home_macro_release_context_schema.py tests/test_home_macro_release_context_repository.py -q
```

Expected: FAIL，新模块尚不存在。

**Step 4: 实现 schema**

定义：

- `HomeMacroMetric`
- `HomeMacroHistoryItem`
- `HomeMacroCoverage`
- `HomeMacroReleaseContextResult`
- `HomeMacroReleaseContextEnvelope`

状态、单位和 direction 使用受限 Literal；不返回预先拼接好的自由文本数值。

**Step 5: 实现只读 repository**

Repository 使用 `duckdb.connect(path, read_only=True)`。标准化表的 canonical 读取形状：

```sql
with ranked as (
  select *,
         row_number() over (
           partition by series_id, trade_date
           order by created_at desc, ingest_batch_id desc
         ) as rn
  from std_external_macro_daily
  where series_id = ? and trade_date <= ?
)
select *
from ranked
where rn = 1
order by trade_date desc
limit ?
```

Choice 表使用它实际存在的 lineage/run 排序字段建立同样的 canonical 规则。不要改变任何表主键，不删除历史 batch。

**Step 6: 运行测试确认通过**

Run: 同 Step 3。

Expected: PASS。

**Step 7: Commit**

```powershell
git add backend/app/schemas/home_macro_release_context.py backend/app/repositories/home_macro_release_context_repo.py tests/test_home_macro_release_context_schema.py tests/test_home_macro_release_context_repository.py
git commit -m "feat: add homepage macro release read model"
```

---

### Task 4: 在后端完成变动、新鲜度和来源状态

**Files:**
- Create: `backend/app/services/home_macro_release_context_service.py`
- Create: `tests/test_home_macro_release_context_service.py`

**Step 1: 写失败测试**

覆盖：

- 从绑定配置读取中国四个自动 metric；
- `change_value = actual - previous`，仅在两期值和单位都有效时计算；
- `display_unit=pct` 的水平变动使用 `change_unit=pct_point`，PMI 使用 `index_point`；
- `previous_value=null` 时 group 为 `partial`；
- `actual_value=0` 和 `change_value=0` 不丢失；
- 单位不一致时为 `error/invalid`，不输出误导变动；
- 美国未接入组返回 `source_pending` 且所有数值为 `null`；
- 月频使用现有 shared macro policy：`<=45` 天 fresh、`46–100` 天 stale、`>100` 天 expired；
- 季频首版沿用保守的 non-daily policy，宁可显示 stale，不能把过期 GDP 标成 ready；独立季度阈值需另立治理合同后再放宽；
- 全部已绑定表缺失时，中国自动组返回 `error/empty`、美国未接入组保持 `source_pending`，整体仍返回 200，不抛 500；
- 没有任何有效 observation 时，`result_meta.as_of_date=null` 且 `date_basis=null`，禁止使用页面今天、请求窗口或 release date 冒充；
- 有有效 observation 时，`result_meta.as_of_date` 取所有 canonical latest observation 的最大值；
- 行级 `source_name` 来自绑定的 `publisher_name`，`notes` 明确实际 `vendor_name`，不得把 Tushare 采集标成 NBS official artifact；
- `tables_used/evidence_rows` 统计实际使用的 canonical 证据；
- `source_version` 与 `vendor_version` 分别对按 `indicator_key/metric_key` 排序后的真实行级版本集合做稳定 SHA-256 摘要并带固定前缀，混合来源不能写成模糊的 `mixed`；
- `rule_version` 直接使用绑定配置版本，`cache_version=cv_home_macro_release_context_v1`。

**Step 2: 运行测试确认失败**

Run: `pytest tests/test_home_macro_release_context_service.py -q`

Expected: FAIL，service 尚不存在。

**Step 3: 实现最小 service**

- 加载并校验 `config/home_macro_release_bindings.json`；
- 批量向 repository 请求每个 series 最近两期 canonical observations；
- 计算 change、direction、reference period；
- 聚合 coverage 和 warnings；
- 使用 `build_result_envelope`：
  - `trace_id="tr_home_macro_release_context"`
  - `basis="analytical"`
  - `result_kind="home.macro_release_context"`
  - `source_surface="market_data"`
  - `fallback_mode="none"` 或真实的 `latest_snapshot`
- 不修改共享 `ResultMeta`，不新增无效 fallback enum。

**Step 4: 运行测试确认通过**

Run: `pytest tests/test_home_macro_release_context_service.py -q`

Expected: PASS。

**Step 5: Commit**

```powershell
git add backend/app/services/home_macro_release_context_service.py tests/test_home_macro_release_context_service.py
git commit -m "feat: build automated homepage macro context"
```

---

### Task 5: 暴露首页专用 analytical API

**Files:**
- Modify: `backend/app/api/routes/executive.py`
- Create: `tests/test_home_macro_release_context_endpoint.py`
- Modify: `tests/test_executive_dashboard_endpoints.py`
- Modify: `tests/test_result_meta_on_all_ui_endpoints.py`
- Modify: `tests/test_boundary_surface_inventory.py`

**Step 1: 写失败测试**

断言：

- `GET /ui/home/macro-release-context` 使用 `executive/read`；
- 无权限时在调用 service 前返回 403；
- `start_date/end_date` 非法或倒置返回 422；
- `history_limit` 只允许 1–20；
- route 使用严格 `response_model=HomeMacroReleaseContextEnvelope`；
- endpoint 通过 `timed_api_call`；
- empty/stale/partial/source_pending 均返回 200 + 显式状态；
- `result_meta` 满足 analytical envelope 约束。

**Step 2: 运行测试确认失败**

```powershell
pytest tests/test_home_macro_release_context_endpoint.py tests/test_executive_dashboard_endpoints.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_boundary_surface_inventory.py -q
```

Expected: FAIL，路由尚不存在。

**Step 3: 实现最小 route**

在 `executive.py` 增加 typed `date` 参数，不复用 `_normalize_report_date` 的 report-date 语义。处理顺序：

1. `_ensure_executive_read_allowed(auth)`；
2. 校验/补默认自然日窗口；
3. `timed_api_call("/ui/home/macro-release-context", ...)`；
4. 调用 page-local service。

不修改路由注册表、不新增权限动作、不扩展 `/ui/home/snapshot`。

**Step 4: 运行测试确认通过**

Run: 同 Step 2。

Expected: PASS。

**Step 5: Commit**

```powershell
git add backend/app/api/routes/executive.py tests/test_home_macro_release_context_endpoint.py tests/test_executive_dashboard_endpoints.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_boundary_surface_inventory.py
git commit -m "feat: expose homepage macro release context API"
```

---

### Task 6: 接入首页轻量 API client 与延迟 query

**Files:**
- Modify: `frontend/src/api/contracts.ts`
- Modify: `frontend/src/api/executiveClient.ts`
- Modify: `frontend/src/api/homeExecutiveClient.ts`
- Modify: `frontend/src/api/clientContext.ts`
- Modify: `frontend/src/api/queryKeys.ts`
- Create: `frontend/src/features/workbench/dashboard-home/useDashboardHomeMacroReleaseContextQuery.ts`
- Create: `frontend/src/test/HomeMacroReleaseContextClient.test.ts`
- Create: `frontend/src/features/workbench/dashboard-home/useDashboardHomeMacroReleaseContextQuery.test.tsx`
- Modify: `frontend/src/test/ApiClientCompositionBoundary.test.ts`
- Modify: `frontend/src/test/StartupPerformanceGuards.test.ts`

**Step 1: 写失败测试**

覆盖：

- client 正确序列化 `start_date/end_date/history_limit`；
- envelope 原样保留，HTTP 错误透传；
- mock client 返回显式 empty analytical envelope，不包含手工数值；
- query `enabled=false` 时不请求；
- 固定今天 `2026-07-16` 时窗口为 `2026-07-16 → 2026-08-30`；
- `2026-07-16` 只是固定单元测试 fixture，不是生产硬编码日期；
- 明确断言该 query 使用独立的 `today → today+45` 合同，不复用 research calendar 的 `today-7 → today+14`。
- query key 包含 mode、完整日期窗口和 historyLimit；
- 新方法进入 `HOME_EXECUTIVE_METHODS`，但不会进入首页首屏 hydration；
- `frontend/src/api/client.ts` 不新增 endpoint 实现。

**Step 2: 运行测试确认失败**

```powershell
cd frontend
npm run test -- src/test/HomeMacroReleaseContextClient.test.ts src/features/workbench/dashboard-home/useDashboardHomeMacroReleaseContextQuery.test.tsx src/test/ApiClientCompositionBoundary.test.ts src/test/StartupPerformanceGuards.test.ts
```

Expected: FAIL，新 client method/query 尚不存在。

**Step 3: 实现 DTO 和 client**

- 在 `contracts.ts` 镜像后端 DTO；
- 在 `ExecutiveClientMethods`、real/demo client 增加 `getHomeMacroReleaseContext`；
- 在 `HomeExecutiveClientMethods`、real/mock client 加入该方法；
- 在 `HOME_EXECUTIVE_METHODS` 加入方法名；
- 不修改 `client.ts` 的 endpoint 实现；
- mock 只返回空状态。

**Step 4: 实现 query hook**

- `retry: false`
- `staleTime: 60_000`
- 默认 `historyLimit=8`
- 接收 `enabled`
- 测试允许注入 today provider

**Step 5: 运行测试确认通过**

Run: 同 Step 2。

Expected: PASS。

**Step 6: Commit**

```powershell
git add frontend/src/api/contracts.ts frontend/src/api/executiveClient.ts frontend/src/api/homeExecutiveClient.ts frontend/src/api/clientContext.ts frontend/src/api/queryKeys.ts frontend/src/features/workbench/dashboard-home/useDashboardHomeMacroReleaseContextQuery.ts frontend/src/test/HomeMacroReleaseContextClient.test.ts frontend/src/features/workbench/dashboard-home/useDashboardHomeMacroReleaseContextQuery.test.tsx frontend/src/test/ApiClientCompositionBoundary.test.ts frontend/src/test/StartupPerformanceGuards.test.ts
git commit -m "feat: add deferred homepage macro context query"
```

---

### Task 7: 把自动 payload 接入首页 view-model 链

**Files:**
- Modify: `frontend/src/features/workbench/dashboard-home/useDashboardHomeBodyData.ts`
- Modify: `frontend/src/features/workbench/dashboard-home/useDashboardHomeBodyData.test.tsx`
- Modify: `frontend/src/features/workbench/dashboard-home/useDashboardHomeViewModel.ts`
- Modify: `frontend/src/features/workbench/dashboard-home/useDashboardHomeViewModel.test.tsx`
- Modify: `frontend/src/features/workbench/dashboard-home/dashboardHomeBodyView.ts`
- Modify: `frontend/src/features/workbench/dashboard-home/dashboardHomeView.ts`
- Modify: `frontend/src/features/workbench/dashboard-home/dashboardHomeView.test.ts`

**Step 1: 写失败测试**

断言：

- `loadEventFeeds=false` 不请求新接口；
- deferred section 激活后请求一次；
- query 的 payload、meta、loading、error 全部传入 `mapToHomeBodyView`；
- research calendar 未来清单为空时，自动历史仍可独立展示；
- 新 query 不挂到 `loadFormalData`，不延长首屏链路。

**Step 2: 运行测试确认失败**

```powershell
cd frontend
npm run test -- src/features/workbench/dashboard-home/useDashboardHomeBodyData.test.tsx src/features/workbench/dashboard-home/useDashboardHomeViewModel.test.tsx src/features/workbench/dashboard-home/dashboardHomeView.test.ts
```

Expected: FAIL，view-model 尚未携带新 query。

**Step 3: 实现最小接线**

数据链固定为：

```text
getHomeMacroReleaseContext
  -> useDashboardHomeMacroReleaseContextQuery
  -> useDashboardHomeBodyData
  -> useDashboardHomeViewModel
  -> mapToHomeBodyView
  -> buildHomeMacroBriefingModel
```

补齐所有 `useMemo` 依赖，mock body 明确传 empty state。
同步更新 `dashboardHomeView.ts` 中所有直接调用 `buildHomeMacroBriefingModel(...)` 的路径，防止旧签名或旧静态 history 输入在非 body-view 路径继续存活。

**Step 4: 运行测试确认通过**

Run: 同 Step 2。

Expected: PASS。

**Step 5: Commit**

```powershell
git add frontend/src/features/workbench/dashboard-home/useDashboardHomeBodyData.ts frontend/src/features/workbench/dashboard-home/useDashboardHomeBodyData.test.tsx frontend/src/features/workbench/dashboard-home/useDashboardHomeViewModel.ts frontend/src/features/workbench/dashboard-home/useDashboardHomeViewModel.test.tsx frontend/src/features/workbench/dashboard-home/dashboardHomeBodyView.ts frontend/src/features/workbench/dashboard-home/dashboardHomeView.ts frontend/src/features/workbench/dashboard-home/dashboardHomeView.test.ts
git commit -m "feat: thread macro context through homepage model"
```

---

### Task 8: 切换 adapter，移除静态历史数值

**进入条件：** Task 10 必须先达到 `repo-complete`，并在获准测试环境成功执行一次 `--run-once`；中国 PMI/CPI/PPI/GDP 已完成 DuckDB → API tie-out。任一条件未满足，不得删除静态 history。

**Files:**
- Modify: `frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.ts`
- Modify: `frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts`
- Modify: `config/dashboard_macro_release_calendar_2026.json`

**Step 1: 写失败测试**

替换当前 maintained-history 用例，覆盖：

- ready payload 映射实际值、前值、变动、单位、reference period；
- CPI/PPI 复合组可同时展示；
- `null` 显示 `—`，`0` 显示 `0`；
- adapter 只格式化，不重新计算 change；
- stale、fallback、partial、source_pending、error 均映射为可见状态；
- `result_meta.quality_flag/vendor_status/fallback_mode/as_of_date` 不会在 adapter 中丢失；
- future release items 为空时 history 不消失；
- JSON 中不存在 history 时仍能工作；
- API error 时不读取任何静态历史值。

**Step 2: 运行测试确认失败**

```powershell
cd frontend
npm run test -- src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts
```

Expected: FAIL，adapter 仍从 JSON 构造历史值。

**Step 3: 最小修改 adapter**

- 删除 `MacroReleaseCalendarHistoryRow`、`buildReleaseHistoryItems` 和所有 `history` JSON 读取；
- 保留 JSON import 仅用于 Phase A 的未来发布日期元数据；
- 接收后端 payload/meta/query state；
- 使用后端提供的 value/unit/precision/change，前端只做展示格式化；
- 输出聚合的 status/source/as-of/message 字段。

**Step 4: 删除静态 history 数据**

从 `config/dashboard_macro_release_calendar_2026.json` 删除全部 `history` block。不要新增备用静态文件。

**Step 5: 运行测试和静态扫描**

```powershell
cd frontend
npm run test -- src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts
cd ..
rg -n '"history"|"latest_value"|"previous_value"|"change_value"' config/dashboard_macro_release_calendar_2026.json
```

Expected: test PASS；`rg` 无匹配并以 1 退出。

**Step 6: Commit**

```powershell
git add frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.ts frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts config/dashboard_macro_release_calendar_2026.json
git commit -m "feat: replace manual macro history with API data"
```

---

### Task 9: 完成页面状态闭环

**Files:**
- Modify: `frontend/src/features/workbench/dashboard-home/sections/ResearchCalendarSection.tsx`
- Modify: `frontend/src/features/workbench/dashboard-home/sections/ResearchCalendarSection.test.tsx`
- Modify if required: `frontend/src/features/workbench/dashboard-home/dashboardHome.module.css`
- Modify: `frontend/src/test/DashboardHomePage.test.tsx`

**Step 1: 写失败测试**

断言 UI 文案：

- 历史数据子区块正常：`自动观测 · 截至 YYYY-MM-DD · N/M 项`；
- 未来发布日期子区块独立标注为 `发布日期配置 · Phase A 非自动供数` 或等价中性来源文案，不能继承历史数据的自动状态；
- 历史数据 loading：`正在获取自动数据`；
- stale：`数据截至 …，已滞后`；
- partial：显示已覆盖数量和缺口；
- fallback：显示实际来源和降级说明；
- source_pending：`数据源接入中`，不显示 0；
- empty/error：`自动数据暂不可用`；
- 历史子区块不再出现“已维护”“历史值待维护”“当前前瞻清单尚未维护历史值与变动”；未来子区块不再出现“请补充配置清单”式人工待办文案；
- deferred content 到达前不请求，到达后请求一次并显示自动历史；
- 不出现横向溢出。

**Step 2: 运行测试确认失败**

```powershell
cd frontend
npm run test -- src/features/workbench/dashboard-home/sections/ResearchCalendarSection.test.tsx src/test/DashboardHomePage.test.tsx
```

Expected: FAIL，旧维护文案仍存在。

**Step 3: 实现最小展示**

优先复用现有 `dhMacroTrustStrip`、`dhMacroReleaseHistoryNote` 等样式。只有现有 class 不能表达 status badge 时才在 `dashboardHome.module.css` 增加 page-local class；不新增重复 inline styles。

**Step 4: 运行测试确认通过**

Run: 同 Step 2。

Expected: PASS。

**Step 5: Commit**

```powershell
git add frontend/src/features/workbench/dashboard-home/sections/ResearchCalendarSection.tsx frontend/src/features/workbench/dashboard-home/sections/ResearchCalendarSection.test.tsx frontend/src/features/workbench/dashboard-home/dashboardHome.module.css frontend/src/test/DashboardHomePage.test.tsx
git commit -m "fix: surface automated macro data states on homepage"
```

---

### Task 10: 建立自动刷新入口与上线门禁

**Files:**
- Create: `backend/app/tasks/home_macro_release_refresh.py`
- Modify: `backend/app/tasks/worker_bootstrap.py`
- Create: `scripts/home_macro_release_refresh.py`
- Create: `tests/test_home_macro_release_refresh_task.py`
- Create: `tests/test_home_macro_release_refresh_entrypoint.py`
- Create: `docs/templates/home_macro_release_refresh_scheduler_handoff.md`
- Create: `docs/templates/home_macro_release_refresh_go_live_checklist.md`
- Create: `scripts/home_macro_release_refresh_timer_preflight.py`
- Create: `tests/test_home_macro_release_refresh_timer_preflight.py`
- Create: `docs/templates/home_macro_release_refresh_timer_enablement_packet.md`
- Create: `docs/handoff/2026-07-16-home-macro-release-context-timer-preflight-status.md`
- Modify: `docs/MAINTENANCE.md`

**Step 1: 写失败测试**

覆盖：

- actor `refresh_home_macro_release_sources` 被 bootstrap 加载；
- orchestrator 调用 Tushare 宏观 ingest，并使用 `backfill_macro_series(..., series_names=["制造业PMI"], sources_filter=["tushare_macro"], start_date=today-90d, end_date=today)` 刷新 PMI；
- PMI 必须显式传 `series_names`，否则现有行数会使默认扫描跳过该序列；90 天重叠窗口避免 timer 停顿后漏掉月度观察期；
- 无人值守路径禁止使用默认的 NBS pinned-artifact 优先级：旧 artifact 即使缺少最新月份，只要仍返回非空历史行就不会继续尝试 Tushare；
- 既有 NBS 行保持不覆盖，新 Tushare 行必须保留 `source_by_series/vendor_version`，并在行级来源和 warning 中明确实际 vendor，不能伪装为 NBS official artifact；
- orchestrator 返回每个 series 的成功/partial/error；
- 任一必需中国 series 没有推进时 gate 不是 success；
- script 支持 `--dry-run`、`--enqueue`、`--run-once`；
- 结构化输出包含 run id、series、latest observation、materialized rows、freshness、elapsed；
- 不在任务内创建/修改 scheduler base；
- handoff 明确 DuckDB 单写者窗口和首次计划运行证据。
- preflight 在 owner、timer host、write window、log path、rollback 和 evidence 未填写时 fail closed 为 `blocked`；
- enablement packet 不包含 `schtasks /Create`、`crontab` 等擅自安装命令。

**Step 2: 运行测试确认失败**

```powershell
pytest tests/test_home_macro_release_refresh_task.py tests/test_home_macro_release_refresh_entrypoint.py tests/test_home_macro_release_refresh_timer_preflight.py tests/test_worker_bootstrap.py -q
```

Expected: FAIL，自动刷新总入口尚不存在。

**Step 3: 实现一次性、可调度入口**

- task 只编排现有 Tushare ingest 和 Tushare-only PMI backfill，不复制 ETL/解析逻辑，也不修改高影响的 `backfill_macro_series` 内部实现；
- actor 只 enqueue/执行业务 task，不内置周期调度器；
- CLI 的非 0 exit code 对应 partial/blocked/error；
- dry-run 不写 DuckDB；
- 继续使用现有 DuckDB 写锁/单写者规则。

**Step 4: 编写运维 handoff**

仓库交付和外部启用分开验收：

- `repo-complete`：actor、CLI、测试、handoff、enablement packet 和 fail-closed preflight 均已提交；preflight 可以因外部字段未填写而返回预期的 `blocked`。
- `ops-complete`：获得明确授权后，运维填写 owner/timer host/write window/log/rollback，preflight 通过，timer 实际启用并留下首次计划运行证据。

推荐时区和频率：

- Asia/Shanghai `10:30`、`18:30` 每日刷新 CPI/PPI/GDP/PMI；
- 首次启用先 shadow 运行；
- timer 只调用 `--enqueue`，写入仍在 Dramatiq task 内完成；
- preflight 必须在 enable 前执行，post-enable 必须记录 scheduler 配置、日志和首次成功 run id。

执行外部 scheduler 需要单独的用户/运维授权；本计划不擅自创建系统任务。
若尚未获得授权，代码分支可以达到 `repo-complete`，但生产自动化和首页正式切换必须保持 `blocked`，不能宣称 `ops-complete`。

**Step 5: 运行测试确认通过**

Run: 同 Step 2。

Expected: PASS。

**Step 6: Commit**

```powershell
git add backend/app/tasks/home_macro_release_refresh.py backend/app/tasks/worker_bootstrap.py scripts/home_macro_release_refresh.py scripts/home_macro_release_refresh_timer_preflight.py tests/test_home_macro_release_refresh_task.py tests/test_home_macro_release_refresh_entrypoint.py tests/test_home_macro_release_refresh_timer_preflight.py docs/templates/home_macro_release_refresh_scheduler_handoff.md docs/templates/home_macro_release_refresh_timer_enablement_packet.md docs/templates/home_macro_release_refresh_go_live_checklist.md docs/handoff/2026-07-16-home-macro-release-context-timer-preflight-status.md docs/MAINTENANCE.md
git commit -m "feat: add schedulable macro release refresh workflow"
```

---

### Task 11: 全链验证、浏览器验收与切换

**Files:**
- Create: `frontend/tests/playwright/dashboard-home-macro-release-context.spec.mjs`
- Review only: Tasks 0–10 changed files

**Step 1: 后端窄测试**

```powershell
pytest tests/test_tushare_macro_ingest_task.py tests/test_tushare_macro_ingest_service.py tests/test_tushare_macro_ingest_retry.py tests/test_worker_bootstrap.py -q
pytest tests/test_home_macro_release_bindings_contract.py tests/test_home_macro_release_context_schema.py tests/test_home_macro_release_context_repository.py tests/test_home_macro_release_context_service.py tests/test_home_macro_release_context_endpoint.py -q
pytest tests/test_executive_dashboard_endpoints.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_boundary_surface_inventory.py tests/test_dashboard_governance_doc_contract.py -q
```

Expected: 全部 PASS。

**Step 2: 后端 lint**

```powershell
python -m ruff check backend/app/tasks/tushare_macro_ingest.py backend/app/services/tushare_macro_ingest_service.py backend/app/tasks/home_macro_release_refresh.py backend/app/repositories/home_macro_release_context_repo.py backend/app/services/home_macro_release_context_service.py backend/app/schemas/home_macro_release_context.py backend/app/api/routes/executive.py scripts/home_macro_release_refresh.py scripts/home_macro_release_refresh_timer_preflight.py
```

Expected: PASS。

**Step 3: 前端窄测试**

```powershell
cd frontend
npm run test -- src/test/HomeMacroReleaseContextClient.test.ts src/features/workbench/dashboard-home/useDashboardHomeMacroReleaseContextQuery.test.tsx src/features/workbench/dashboard-home/useDashboardHomeBodyData.test.tsx src/features/workbench/dashboard-home/useDashboardHomeViewModel.test.tsx src/features/workbench/dashboard-home/dashboardHomeView.test.ts src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts src/features/workbench/dashboard-home/sections/ResearchCalendarSection.test.tsx src/test/DashboardHomePage.test.tsx src/test/ApiClientCompositionBoundary.test.ts src/test/StartupPerformanceGuards.test.ts
```

Expected: 全部 PASS。

**Step 4: 前端质量门禁**

```powershell
npm run typecheck
npx eslint src/api/contracts.ts src/api/executiveClient.ts src/api/homeExecutiveClient.ts src/api/clientContext.ts src/api/queryKeys.ts src/features/workbench/dashboard-home src/test/HomeMacroReleaseContextClient.test.ts src/test/DashboardHomePage.test.tsx src/test/ApiClientCompositionBoundary.test.ts src/test/StartupPerformanceGuards.test.ts
npm run debt:audit
npm run build
```

Expected: 全部 PASS；debt baseline 不增长。

**Step 5: 写并运行 Playwright**

场景：

1. 页面滚动到 deferred research calendar 区；
2. 中国自动行显示实际值、前值和变动；
3. 美国未接入行显示“数据源接入中”；
4. stale/partial/error fixture 都显示明确状态；
5. 页面不出现“已维护/历史值待维护”；
6. 5888 桌面和窄屏均无横向溢出；
7. 控制台无 error。

Run:

```powershell
cd frontend
$env:MOSS_PLAYWRIGHT_USE_WEB_SERVER="1"
npx playwright test -c playwright.config.mjs tests/playwright/dashboard-home-macro-release-context.spec.mjs
```

Expected: PASS。

**Step 6: 真实数据 tie-out**

在运行中的 `http://127.0.0.1:7888` 调用新接口，并与 DuckDB canonical query 对账：

- 每个 ready metric 的 actual/previous/reference period 一致；
- change 和 unit 一致；
- `as_of_date` 等于响应中最近有效 observation；
- `tables_used/evidence_rows/source_version/vendor_version/rule_version/cache_version` 完整，混合来源摘要可由行级 lineage 重算；
- 无 duplicate period；
- 新 period 落库后，无需改配置即可出现在响应和首页。

**Step 7: GitNexus 变更范围检查**

运行 `gitnexus_detect_changes()`。

Expected: 只影响首页 macro supplemental flow、Tushare macro materialization 和明确的 worker task registration；不影响 `/ui/home/snapshot` 主流程和其他页面。

**Step 8: 独立 review**

- 业务正确性 review：单位、精度、null/0、日期、latest/previous、批次去重、stale/fallback。
- 代码 review：权限、SQL 参数化、DuckDB 连接关闭、query key、首屏性能、状态可访问性。
- 修复发现后重跑 Step 1–7。

**Step 9: Commit**

```powershell
git add frontend/tests/playwright/dashboard-home-macro-release-context.spec.mjs
git commit -m "test: verify automated homepage macro context"
```

---

## 6. 上线顺序

1. 合同、MCP evidence、单位词汇表和失败测试先落地。
2. 完成 GitNexus impact gate；HIGH/CRITICAL 先告知用户。
3. 完成 Tasks 3–5，shadow 发布新 endpoint，不接 UI。
4. 完成 Task 10 的 `repo-complete`，在获准测试环境执行一次 Tushare-only PMI + CPI/PPI/GDP `--run-once`。
5. 对账中国四个指标，并验证既有 NBS 行未覆盖、新 PMI 行明确标记 Tushare vendor；任何缺口都阻断切换。
6. 完成 Tasks 6–7，把 deferred payload 接入全部 view 路径，但仍不删除静态 history。
7. 只有 Gate 4–5 通过后才能执行 Tasks 8–9：删除 JSON history，并分别标注“自动历史数据”和“Phase A 非自动未来日历”。
8. 取得外部 scheduler 授权，填写 enablement packet，preflight 通过后启用 timer。
9. 取得首次计划运行成功证据，达到 `ops-complete`。
10. 部署切换并运行 Playwright、真实数据 tie-out、性能、typecheck、build 和 debt gate。
11. 观察一个实际发布周期后关闭 shadow 标记。

## 7. 回滚策略

- 可回滚：新 query、adapter 接线和 section 渲染。
- 后端 endpoint 可保留，不影响首页主链路。
- 回滚展示必须是“自动数据暂不可用”或隐藏该 supplemental 区块。
- 禁止恢复 `dashboard_macro_release_calendar_2026.json` 的历史数值。
- 禁止回滚或修改 `/ui/home/snapshot`、权限框架、数据库 schema、queue/scheduler/cache base。
- 若自动刷新失败：保留最后一次真实观测，明确显示 stale/last observation；不能伪装成最新。

## 8. 完成定义

### Repo-complete

- MCP evidence 已记录；无法证明的指标保持 `source_pending`。
- `config/dashboard_macro_release_calendar_2026.json` 不含任何 history/latest/previous/change 数值。
- 中国 PMI/CPI/PPI/GDP 的 actual、previous、change、unit、period 与 DuckDB 对账一致。
- 配置、Python schema、API 和 TypeScript contract 的单位 literal 完全一致，`pct` 只在 UI 渲染为 `%`。
- mixed-source `source_version/vendor_version` 摘要可由 canonical 行级 lineage 稳定重算。
- 无有效 observation 时 `as_of_date/date_basis` 均为 `null`，不伪造今天。
- 历史自动状态与未来静态发布日期来源在 UI 上分开标注。
- 美国未接入项显示 `source_pending`，不显示假值或 0。
- loading/empty/stale/fallback/partial/source_pending/error 全部可见。
- 首页首屏请求数量和启动性能门禁不回归。
- `npm run debt:audit` 不增长。
- GitNexus change detection 证明影响范围符合预期。

### Ops-complete

- 外部 scheduler 已获得明确授权，enablement packet 填写完整且 preflight 通过。
- 自动 timer 已启用，并有首次计划运行成功的配置、日志和 run id 证据。
- 新发布期到来后，无需改代码或配置，自动进入标准表、API 和首页。

## 9. 已知残余风险

- 美国正式数据源仍需后续接入；推荐顺序为 BLS、BEA、Federal Reserve、合法授权的 ISM 数据源。
- `std_tushare_eco_cal_event` 未进入 schema registry，Phase A 不把它作为正式历史值或自动未来日历真相。
- NBS PMI 官方 release manifest 仍含人工审核的 URL/hash 元数据，因此无人值守 Phase A 必须强制 `sources_filter=["tushare_macro"]`。若要求官方源本身也完全自动，应另做 NBS 发布页自动发现、可信域校验、artifact hash 归档和修订吸收任务。
- `macro_backfill._insert_rows` 当前会跳过已有 series/date，官方修订吸收是后续治理项，不能在本页任务中顺手扩大修改。
- 自动刷新依赖 Tushare token、网络、Redis/Dramatiq worker 和外部 timer；缺任一项都必须产生 blocked/partial 证据。
- shared freshness policy 没有季度 cadence。首版对 GDP 采用保守状态，后续需单独确认季度 freshness 合同后再放宽。
