# A1 — ADB 单日窗口 MD5 仿真日均：影响探查与治理落地报告

- 任务：技术债清偿 A1（30 并行专家之一）
- 日期：2026-08-12
- 方法：代码链路排查（rg）+ 本地 DuckDB 只读实测（`data/moss.duckdb`，`read_only=True`）+ 改码前后行为对照。
- 结论先行：**仿真路径真实存在且默认开启**；最近报告日（2026-07-31）单日窗口请求下，**资产 19 行 + 负债 9 行共 28 个分类的"日均"全部为 MD5 合成数**，合成资产日均较真实时点虚高约 5.6%（约 209 亿元）。已按方案落地：默认关闭仿真，单日窗口返回 null 语义 + `avg_unavailable_reason="insufficient_window"`；显式 opt-in 保留（须 owner 签核后才可启用）且继续以 `simulated=true` 全程披露。**合并需 owner 签核。**

---

## 1. 现状锚（改码前验真）

| 锚点 | 声称 | 验真结果 |
|---|---|---|
| `backend/app/services/adb_analysis_service.py:92` | `_stable_factor`（MD5 派生 0.85–1.15 因子） | 存在，行号准确（92–97） |
| 同文件 `:1338` | `simulate_if_single_snapshot: bool = True` | 存在，行号准确（改码前） |
| 同文件 `:1381-1387` | 单快照窗口用 spot×factor 合成日均 | 存在。`simulated = simulate_if_single_snapshot and calendar_days_inclusive <= 1`，为真时 breakdown 各行与 totals 均由合成值构成 |
| `backend/app/core_finance/adb_analytics.py:202-239` | `build_comparison_rows` 含 simulated 分支 | 存在（`:221-222`：`avg = spot × stable_factor_fn(f"{side}:{end_date}:{category}")`） |

触发条件精确表述：**单日日历窗口**（`start_date == end_date`，`calendar_days_inclusive <= 1`），与快照条数无关。多日窗口（含"多日窗口但仅 1 个观测日"的稀疏场景）不走仿真，走 `sample_filled` 样本补齐路径（不在本任务范围）。

## 2. 仿真路径调用链（谁会拿到合成数）

```
GET /api/analysis/adb-comparison          (legacy, backend/app/api/routes/adb_analysis.py:70)
GET /api/analysis/adb/comparison          (backend/app/api/routes/adb_analysis.py:71)
  -> adb_analysis_service.adb_comparison_envelope
  -> _cached_adb_comparison_envelope (lru_cache 32)
  -> _adb_comparison_envelope_uncached
  -> get_adb_comparison(..., top_n)         # 未显式传 simulate_if_single_snapshot，走默认值
  -> core_finance.adb_analytics.build_comparison_rows(simulated=True 时合成)
```

调用方清单（rg `simulate_if_single_snapshot|get_adb_comparison`）：

| 调用方 | 是否显式传参 | 单日窗口下改前行为 | 改后行为 |
|---|---|---|---|
| API `/api/analysis/adb-comparison` + `/api/analysis/adb/comparison` | 否（默认） | 合成日均，`simulated=true` | avg=null + reason |
| `scripts/list_adb_asset_other_breakdown.py:45` | 否（默认） | 合成日均 | avg=null + reason |
| 测试 `tests/test_adb_analysis_api.py` 多个单日窗口用例 | 否（默认） | 合成日均 | 已同步适配（见 §5） |

前端消费方（只读排查，未改动）：

- `frontend/src/api/liabilityAdbClient.ts:759` → 余额分析工作台"日均对比" surface（`balance-analysis.adb-comparison`）与 PnL by Business YTD 视图（`PnlByBusinessPage.tsx`，YTD 为多日窗口，正常不触发仿真）。
- 首页启动预取为多日窗口（`2026-01-01 ~ 报告日`），不触发仿真。
- **会触发仿真的实际场景**：用户在工作台把查询区间选为单日（start==end）。

## 3. 本地 DuckDB 只读实测（最近报告日仿真输出量）

数据源：`data/moss.duckdb`（约 1.68 GB），`duckdb.connect(read_only=True)`。

- formal 表最近报告日：`fact_formal_zqtz_balance_daily` = **2026-07-31**（578 个报告日），`fact_formal_tyw_balance_daily` = **2026-07-31**（577 个报告日），口径 `currency_basis='CNY'`。
- 改码前直接调用 `get_adb_comparison("data/moss.duckdb", 2026-07-31, 2026-07-31)` 实测：

| 指标 | 实测值 | 说明 |
|---|---|---|
| `simulated` | `True` | 默认参数即触发 |
| 合成输出行数 | 资产 19 行 + 负债 9 行 = **28 行** | 每行 `avg_balance` 均为 spot×MD5 因子 |
| `total_spot_assets`（真实） | 370,538,010,245.46 | ≈ 3,705.38 亿 |
| `total_avg_assets`（合成） | 391,434,096,113.71 | ≈ 3,914.34 亿，**虚高 +5.64%（约 +209 亿）** |
| `total_spot_liabilities`（真实） | 175,297,541,760.99 | ≈ 1,752.98 亿 |
| `total_avg_liabilities`（合成） | 168,070,038,085.66 | ≈ 1,680.70 亿，**虚低 −4.12%（约 −72 亿）** |
| 口径 | `formal_calendar` | 全部来自 formal 表，非快照兜底 |

即：任何人对最近报告日发起单日窗口对比请求，页面上 28 个分类的"日均余额"、两个总计日均、以及由其派生的偏离/占比全部是确定性伪随机合成数。该数字可复现（MD5 稳定因子）、看起来合理（±15% 内），**但与任何真实观测无关**。

局限声明：DuckDB 中无 API 请求日志，无法统计历史上单日窗口请求的真实频次；上表是"若发生单日窗口请求，其输出面有多大"的直接测量，不是请求频次统计。

## 4. 治理落地（本次代码变更）

| 文件 | 变更 |
|---|---|
| `backend/app/services/adb_analysis_service.py` | `simulate_if_single_snapshot` 默认 `True → False`；新增 `avg_window_insufficient` 判定；单日窗口下 `total_avg_assets/total_avg_liabilities = None`（时点 totals 改从真实 spot map 求和，不再从合成行求和）；payload 新增 `avg_unavailable_reason: "insufficient_window" | null`（沿用 `sample_filled/sample_fill_method/simulated` 质量字段模式）；`_append_other_row` 对 `total_avg=None` 前置返回；`_empty_comparison_response` 同步补齐字段保持 schema 稳定 |
| `backend/app/core_finance/adb_analytics.py` | `build_comparison_rows` 新增 keyword-only `insufficient_window: bool = False`：为真时各行 `avg`/`deviation` 输出 `None`（fail-visible，缺失≠零≠复读时点），排序回退按 spot；`enrich_breakdown` None-safe（`avg_balance`/`proportion` 传导 `None`） |

保留面（须 owner 签核后才可使用）：`simulate_if_single_snapshot=True` 显式传入时仿真分支仍存在，且继续以 `simulated=true` 披露。当前无任何调用方传入该参数。若 owner 裁决彻底删除仿真，删除 `_stable_factor`、`build_comparison_rows` 的 simulated 分支与该参数即可（单独小改动）。

改后实测（同一 DuckDB，2026-07-31）：

- 单日窗口默认：`simulated=False`、`avg_unavailable_reason="insufficient_window"`、28 行 `avg_balance` 全部 `None`、`total_avg_* = None`、spot 保持真实值。
- 多日窗口（2026-07-01 ~ 07-31）：行为不变（`avg_unavailable_reason=None`，日均正常计算）。
- 显式 opt-in：`simulated=True` 且合成值可见（披露语义保留）。

## 5. 测试变化

新增：

- `tests/test_adb_comparison_rows.py::test_build_comparison_rows_insufficient_window_yields_null_avg`（core_finance 单元：avg/deviation 为 None、spot 保留、`_stable_factor` 不得被调用、排序回退 spot）。
- `tests/test_adb_analysis_api.py::test_adb_comparison_single_snapshot_window_returns_null_avg_with_reason`（单快照 fixture：不产出合成数字、reason 可见、时点保真）。
- `tests/test_adb_analysis_api.py::test_adb_comparison_explicit_simulation_optin_stays_disclosed`（opt-in 披露回归保护）。

既有断言同步适配（4 处，均为单日窗口用例，测试原意不变）：

| 测试 | 原断言 | 新断言 | 性质 |
|---|---|---|---|
| `test_adb_comparison_normalizes_bond_rates_from_percent_inputs` | `simulated is True` | `simulated is False` + reason 断言 | 行为对齐（利率归一化主旨不受影响） |
| `test_adb_comparison_reads_formal_facts_without_snapshot_tables` | `total_avg_assets > 0` | `total_spot_assets > 0` + `total_avg_assets is None` + reason | 测试意图（无快照表 formal 可出数）改用时点验证 |
| `test_adb_comparison_supplements_missing_snapshot_dates_per_source` | `total_avg_assets > 0` | 同上；`total_avg_interbank_liabilities≈50M` 保留 | 同业区间日均不走合成路径，保留 |
| `test_adb_comparison_liability_falls_back_past_blank_sub_type` | `avg_balance > 0` | `spot_balance > 0` | 分类回退主旨不变 |

以上断言变化均为默认行为变化的直接后果，非放宽；如 owner 认为单日窗口应保留其它语义（如 avg=当日观测值而非 null），需裁决后另行调整。

验证命令与结果（仓库根，`.venv`）：

- `python -m pytest tests/test_adb_comparison_rows.py -q` → **6 passed**
- `python -m pytest tests/test_adb_analysis_api.py tests/test_adb_rate_normalize.py -q` → **27 passed**（124s）
- `python -m pytest tests -k "adb" -q` → 见任务最终回复（全量筛选）

## 6. 残余风险与待 owner 裁决事项

1. **前端 totals 归零显示**（中）：`frontend/src/api/liabilityAdbClient.ts:230` `total_avg_assets: Number(raw.total_avg_assets ?? 0)` 会把 `null` 归一为 `0`——单日窗口下前端总计日均将显示 0 而非"不可得"。分类行 `avg_balance` 已是 nullable-safe（`:188`）不受影响。前端不在本任务授权范围；建议后续小改动：totals nullable 化 + 依据 `avg_unavailable_reason` 展示"窗口不足"状态（fail-visible 落到首屏）。
2. **`total_avg_interbank_assets/liabilities` 口径不对称**（低）：同业区间日均由 `_tyw_interval_avg_balances` 独立计算（真实观测，非合成），单日窗口下仍输出数值（=当日值）。与 `total_avg_* = null` 并存可能引起阅读困惑；是否统一为 null 待 owner 裁决。
3. **`scripts/list_adb_asset_other_breakdown.py`**（低）：诊断脚本走默认参数，单日窗口跑该脚本会看到 avg=None；脚本不在授权范围未改，其"其它行拆解"逻辑以 spot 为主，影响有限。
4. **lru_cache 旧缓存**（低）：`_cached_adb_comparison_envelope` maxsize=32 进程内缓存；已部署进程需重启或调用 `clear_adb_comparison_cache()` 后新语义才生效。
5. **仿真分支彻底删除与否**（待裁决）：本次保留显式 opt-in（默认关 + 披露）。若 owner 裁决业务无保留必要，可删 `_stable_factor` 与 simulated 分支；若裁决保留，需按 PRD 补 API meta `synthetic=true` 与前端首屏标注。
