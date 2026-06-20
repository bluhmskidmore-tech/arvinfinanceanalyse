# 附录：PnL Fixture 与测试门禁矩阵

**性质**：对照表与引用索引。不定义新口径；业务规则以 `docs/calc_rules.md`、`docs/data_contracts.md` 与 `prd-moss-agent-analytics-os.md` 为准。

**路径说明**：下文文件名与测试代码中的字符串一致（UTF-8）。若在仅支持系统本地化编码的控制台中浏览磁盘，中文文件名可能显示为乱码，以仓库内 `tests/` 与 `data_input/` 实际名为准。

---

## 1. `source_family` 与目录布局

| `source_family` | `data_input` 目录 | 典型文件名模式 | DuckDB 预览表（Phase 1） |
|-----------------|-------------------|----------------|---------------------------|
| `pnl` | `pnl/` | `FI损益{YYYYMM}.xls`（或含区间的命名，以解析器为准） | `phase1_pnl_preview_rows`、`phase1_pnl_rule_traces` |
| `pnl_514` | `pnl_514/` | `非标514-{dateRange}.xlsx` | `phase1_nonstd_pnl_preview_rows`、`phase1_nonstd_pnl_rule_traces` |
| `pnl_516` | `pnl_516/` | `非标516-{dateRange}.xlsx` | 同上 |
| `pnl_517` | `pnl_517/` | `非标517-{dateRange}.xlsx` | 同上 |

分桶由目录与 `source_family` 后缀推导（如 `pnl_516` → `516`），与 `docs/data_contracts.md` 中 `journal_type` 约定一致。

---

## 2. FI fixture（`source_family = pnl`）

**数据来源**：`data_input/pnl/` 下 FI 损益类 Excel（示例：`FI损益202512.xls`）。

**对 `summarize_source_file` 的约束**（见 `tests/test_pnl_source_preview_flow.py::test_source_preview_service_summarizes_real_fi_pnl_file`）：

- `source_family == "pnl"`
- `report_date` 与样例文件名推导一致（例：`2025-12-31`）
- `total_rows > 0`，`preview_mode == "tabular"`
- `group_counts` 之和等于 `total_rows`，且包含 `"H"` 等分组键

**预览 API 行字段的下界**（`…/pnl/rows` 首行字段名集合）：至少包含 `ingest_batch_id`、`row_locator`、`report_date`、`instrument_code`、`invest_type_raw`、`portfolio_name`、`cost_center`、`currency`、`manual_review_needed`。

**trace 行**（`…/pnl/traces`）：至少包含 `ingest_batch_id`、`row_locator`、`trace_step`、`field_name`、`field_value`、`derived_label`、`manual_review_needed`。

---

## 3. NonStd 514 / 516 / 517 fixture

### 3.1 仓库内实机样例

`pnl_514`、`pnl_516`、`pnl_517` 目录下均有与命名模式一致的非标分录 xlsx，供导入与人工核对。

### 3.2 测试中合成的 516 工作簿

`tests/test_pnl_source_preview_flow.py` 中 `_write_nonstd_preview_workbook` 按「会计分录详情表」版式写入表头行（`NONSTD_HEADERS`）与两行示例（借贷、科目 `51601010004`、金额等），用于可控的 CI 路径。

**对 `materialize` + 预览链路的约束**（`test_materialize_preview_supports_pnl_and_nonstd_rows_and_traces`）：

- 同批入库可同时包含 `pnl` 与 `pnl_516`
- `materialize_cache_view` 返回的 `preview_sources` 精确为 `{"pnl", "pnl_516"}`
- `phase1_source_preview_summary` 中两行 `family -> total_rows` 与断言一致（FI 行数 &大于 0；516 合成表为 2 行）

**预览 API 非标行**（`…/pnl_516/rows`）：至少包含 `ingest_batch_id`、`row_locator`、`report_date`、`journal_type`、`product_type`、`asset_code`、`account_code`、`dc_flag_raw`、`raw_amount`、`manual_review_needed`。

### 3.3 与 `acceptance_tests` 的 516 口径对齐

`docs/acceptance_tests.md` §3.2 要求：

- `T损益516=100` → 统一标准口径 `-100`
- 金额 + 借贷标识推导的 `signed_amount`；正式层不得再次按借贷翻转  

与 `docs/calc_rules.md` §4 一致。本附录不重复推导公式。

### 3.4 Phase 2 契约测试（xfail 作为“未来 parity 黄金样例”）

`tests/test_pnl_phase2_start_pack.py` 中多个用例标记为 `xfail`，在 `build_nonstd_pnl_bridge_rows` / `build_formal_pnl_fi_fact_rows` 等仍抛出 `NotImplementedError` 时**预期失败**。用例体内已写出目标 `FiPnlRecord`、`NonStdJournalEntry`、`NonStdPnlBridgeRow`、`FormalPnlFiFactRow` 的字段与标量；待实现落地后，这些断言即构成 **core_finance 与数据结构之间的 parity gate**（与 `tests/test_pnl_core_finance_contract.py` 的字段序门禁互补）。

`tests/test_pnl_core_finance_contract.py`：

- 校验导出类型名与 `dataclasses.fields` 顺序与治理字段名一致  
- `build_*` 入口在未实现时须 `raise NotImplementedError` 且信息包含 `Phase 2 /pnl`（与实现阶段边界一致）

---

## 4. Coexistence / cutover fixture（多源族并存）

**场景**：同一 `MOSS_DATA_INPUT_ROOT` 下同时存在同业（TYW）、FI PnL、非标 PnL 等多类源文件，分批入库后不得破坏既有源的 trace 字段闭包。

**覆盖测试**：`test_mixed_family_materialize_does_not_pollute_tyw_trace_contract`

- 布局：`TYWLSHOW-*.xls`、`pnl/FI损益202512.xls`、`pnl_516/` 下合成 `非标516-20260101-0228.xlsx`
- **门禁**：`tyw` 的 trace 响应中，`field_name` 集合须为 `TYW_TRACE_FIELDS` 的子集，且包含 `TYW_PRODUCT_TYPE`  

含义：PnL / NonStd 扩展后，TYW 预览契约不被新列或错误混入污染——属于并存与切换期的**契约隔离**回归，而非业务金额断言。

---

## 5. Expected output 与 parity gate（归纳）

### 5.1 Phase 1：源解析 / 预览 / 分析基线

对 `/ui/preview/source-foundation/{family}/rows` 与 `…/traces`（`family ∈ {pnl, pnl_514, pnl_516, pnl_517}`）：

- HTTP 200  
- `result_meta.formal_use_allowed is False`  
- `result_meta.basis == "analytical"`  

（见 `test_pnl_source_preview_flow` 中断言。）

### 5.2 Phase 2：正式层入口

- 所有正式 PnL 金额语义仅在 `backend/app/core_finance/` 落地；本附录**不要求**改动 API 或测试断言。  
- **Parity gate**：`test_pnl_core_finance_contract`（字段序与占位行为）+ `test_pnl_phase2_start_pack`（xfail 内嵌期望对象）在实现完成后应转为绿；届时与 `docs/data_contracts.md` 同步核对即可。

### 5.3 Phase 3：PnL Bridge（文档验收，非本附录 fixture）

`docs/acceptance_tests.md` §4.2：`explained_pnl` 与 `actual_pnl` 可比较、`quality_flag` 等——属于 bridge 阶段验收，与 §2–4 的源文件 fixture **正交**；此处仅交叉引用。

---

## 6. 权威文档与代码锚点（快速跳转）

| 主题 | 文档 | 测试/代码 |
|------|------|-----------|
| 516 符号与总额 | `docs/calc_rules.md` | `docs/acceptance_tests.md` §3.2 |
| 字段契约 | `docs/data_contracts.md` | `tests/test_pnl_core_finance_contract.py` |
| 事实表名 | `prd-moss-agent-analytics-os.md` §6.2 | — |
| 预览实现 | — | `backend/app/services/source_preview_service.py`（用户约束下本文档不改代码，仅引用） |

---

## 7. Open items（文档侧可见缺口）

- `build_formal_pnl_fi_fact_rows`、`build_nonstd_pnl_bridge_rows` 等 Phase 2 入口仍为 `NotImplementedError`，xfail 用例保持预期失败。  
- 实机 `pnl_514` / `pnl_517` 在部分测试中与 `pnl_516` 对称覆盖程度不一；扩展自动化时应在 `tests/` 中补足与上表对称的断言（**不**在本附录中杜撰数值黄金样例）。  
- PnL Bridge（Phase 3）的 fixture 矩阵若后续落地，应单开小节或新附录，避免与源文件 Phase 1/2 混淆。
