# Advanced Attribution Bundle — 实现前方案（2026-04-12）

## 文档目的与范围

本文档在 **不实现完整 advanced attribution** 的前提下，给出 `advanced_attribution_bundle` 的 **语义归属、与 governed workbook 的隔离方式、最小可落地切片**，以及 **缺失输入清单**。  

权威边界见：`docs/plans/2026-04-12-balance-analysis-advanced-attribution-boundary.md`、`docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md` §13。

---

## 1. 语义分类结论：Analytical（主）/ Scenario（条件）/ Formal（否）

### 1.1 推荐归类：**Analytical（分析口径）**

**理由（与仓库铁律一致）：**

- `advanced_attribution_bundle` 依赖 **Phase 3 曲线、成交/交易粒度、基准指数** 等（见边界说明与 `bond_analytics_service.PHASE3_WARNING`），这些输入 **不属于** `fact_formal_zqtz_balance_daily` / `fact_formal_tyw_balance_daily` 的正式余额事实链。
- `calc_rules.md` §9「桥接归因」与风险张量描述的是 **解释性分解**（explained vs actual、residual、quality_flag），与 **监管口径 formal PnL** 可区分；在未形成独立「正式归因引擎」与完整契约测试前，应落在 **分析层**，而非 formal。
- `AGENTS.md` 要求 **Formal / Scenario / Analytical 在语义、表、缓存与 `result_meta` 上隔离**；将不成熟归因混入 formal workbook 主链会违反「不得把不成熟的 attribution 逻辑混入现有 governed workbook 正式链路」的约束。

### 1.2 何时可标为 **Scenario**

仅当 bundle 的语义明确为 **情景/冲击**（例如给定利率曲线平移、给定利差冲击下的 **what-if 分解**），且结果 **不写回 formal 事实表**、并在 `result_meta` 中显式 `scenario_flag` / 等价字段时，可将 **该子能力** 归为 Scenario 族。  

默认的「报告期实际解释」仍建议 **Analytical**。

### 1.3 明确 **不是 Formal**

在以下任一条件满足前，`advanced_attribution_bundle` **不得**作为 formal 结果对外宣称：

- 无完整、可回归的曲线/交易/基准 **数据契约** 与 **fixture 测试**；
- `roll_down` / `rate_effect` / `spread_effect` 等仍为零或占位（见 `PHASE3_WARNING`）；
- 无法给出与 `actual_pnl` 对齐的 `explained_pnl` / `residual` / `quality_flag`（见 `calc_rules.md` §9）。

---

## 2. 是否允许进入当前 balance-analysis workbook 主链：**不允许**

### 2.1 产品与测试约束

- 边界文档明确：governed workbook **不得**依赖 `advanced_attribution_bundle`。
- 契约测试 `test_balance_analysis_workbook_does_not_silently_expose_future_gap_sections` 断言：`advanced_attribution_bundle` **不得**出现在 `/ui/balance-analysis/workbook` 返回的 `tables[].key` 中。

### 2.2 与现有 `campisi_breakdown` 的区分

当前 workbook 中的 `campisi_breakdown`（`core_finance/balance_analysis_workbook._build_campisi_table`）是 **基于 formal 余额行** 的简化展示（票息、政策性金融债基准利差 proxy、剩余期限作「久期贡献」标签等），**不是** Phase 3 全量归因。  

`advanced_attribution_bundle` 若并入同一 payload，极易被误读为「与 formal workbook 同级已交付」，故 **禁止**并入 `build_balance_analysis_workbook_payload` 的默认 `tables` 列表。

### 2.3 允许的「邻近」暴露方式（未来实现时）

- **独立 API**（建议 `result_kind` 专用，例如 `balance-analysis.advanced_attribution` 或 `bond-analytics.advanced_attribution_bundle`），或
- **独立 workbench 区块/路由**，通过 **显式 `warnings` / `prerequisites`** 与 formal workbook 区分。

---

## 3. 最小可落地切片（Smallest implementation slice）

以下按 **风险最低、边界最清晰** 排序；每一档都可单独验收，不要求一次做完 Phase 3 全量。

### Slice A — 契约与门禁（文档 + 测试意向，本任务已允许仅文档）

- 冻结 **JSON 信封形状**（sections、每 section 的 `quality_flag`、全局 `warnings`、前置条件枚举）。
- 在 `result_meta` 中强制：`basis != "formal"`（建议 `analytical`），并包含 `rule_version` / `source_version` 的可追溯组合（可引用 bond-analytics 物化版本而非 formal balance manifest）。

### Slice B — 「未就绪」显式响应（后端占位，**非本任务范围**；此处仅定义行为）

- 单一 endpoint 返回 **结构化 `not_ready`**：`missing_inputs[]`、`blocked_components[]`（映射 `PHASE3_WARNING` 中的组件），**不返回**看似真实的分解数值。
- 与 `build_bond_action_attribution_placeholder_envelope` 模式对齐：**占位必须显式**，禁止静默零值冒充完成。
- 若请求显式给出 scenario shock 输入（例如 `treasury_shift_bp` / `spread_shift_bp`），则允许返回 **`basis=scenario` 且 `scenario_flag=true` 的 `not_ready` 合同**；默认无 shock 时仍返回 `analytical`。

### Slice C — 只读拼接（数据就绪后）

- 在 **service 编排层** 只读聚合：bond-analytics 已物化读模型 +（可选）balance 上下文维度（组合/科目），**零写入** `fact_formal_*`。
- 所有计算仍在 **`core_finance/`**（若新增归因公式）或 bond-analytics 既有 core 模块中，**禁止** API/前端补算。

### Slice D — DuckDB 物化缓存（可选）

- 若需性能：新增 **analytical 缓存表**（命名建议带 `analytical` / `cache_` / `bond_analytics` 前缀），**仅**由 `tasks/` 写入；与 formal materialize 任务 **分离**。

---

## 4. 实现时需新增或调整的设计面（清单，非本次编码）

| 层面 | 建议内容 |
|------|----------|
| **表 / 存储** | 归因结果若物化：DuckDB **分析/缓存表**（grain、curve_id、trade_batch、instrument 键需书面定义）；**不**扩展 `fact_formal_zqtz_balance_daily` / `fact_formal_tyw_balance_daily` 承载归因列。 |
| **字段 / 契约** | 与 `calc_rules.md` §9 对齐的 bridge 字段：`carry`、`roll_down`、`treasury_curve`、`credit_spread`、`fx_translation`、`realized_trading`、`unrealized_fv`、`explained_pnl`、`actual_pnl`、`residual`、`residual_ratio`、`quality_flag`。 |
| **Service seam** | 新建或复用 **bond_analytics** 编排入口优先（归因数据源在 Phase 3）；balance-analysis service **仅**在需要组合过滤时做参数传递，**不**复制公式。可选：`get_advanced_attribution_bundle(...)` 返回 analytical envelope。 |
| **result_meta** | `basis: analytical`（或规范允许的枚举）；`result_kind` 专用；`warnings` 数组必填当存在占位；可选 `depends_on: ["bond_analytics_phase3", ...]`。 |
| **Workbook section** | **不**增加 `advanced_attribution_bundle` 到 governed workbook 默认 sections；若 UI 需要并列展示，使用 **独立 result 块** 或独立页面。 |

---

## 5. 缺失输入 → 当前无法「安全落地」全量 bundle 的原因

| 缺失或不足 | 影响 |
|--------------|------|
| **生产级曲线与 instrument 对齐** | `treasury_curve` / `roll_down` / 利率效应无法从正式余额行唯一推出。 |
| **交易级流水 / 持仓变动** | 动作归因、再投资、买卖实现项无法闭合。 |
| **信用利差序列与工具映射** | `spread_effect`、迁移类分解不可靠。 |
| **与损益真值对齐的 `actual_pnl` 同源** | 无法验收 `residual` / `quality_flag`；易沦为展示数字。 |
| **基准指数或可复现基准总收益** | 超额与 Campisi 完整版所需的 benchmark return 链可能断裂。 |

在以上任一项未纳入 **数据契约 + 测试** 前，只允许 Slice A/B 类交付。

---

## 6. 与现有 balance-analysis workbook 的边界隔离（操作级）

1. **代码路径**：不向 `balance_analysis_workbook.build_balance_analysis_workbook_payload` 追加归因 bundle 表项。  
2. **API**：不与 `balance-analysis.workbook` 的 `result_kind` 混用；若合并展示，应在 **聚合端** 显式标注第二段响应为 analytical。  
3. **前端**：只展示服务端返回字段；**禁止**前端补算正式或分析归因指标（`AGENTS.md`）。  
4. **治理缓存**：formal balance 的 manifest / refresh 任务不依赖归因物化任务。  

---

## 7. 风险

| 风险 | 缓解 |
|------|------|
| 产品将 analytical bundle 误认为 formal | 独立 `result_kind` + 固定 `warnings` + 文档/API 说明。 |
| 占位零值被当作真值 | 契约测试 + 与 `PHASE3_WARNING` 一致的显式标注。 |
| 重复实现 Campisi | 命名与 `campisi_breakdown` 区分；advanced bundle 文档中引用边界说明。 |
| 跨模块循环依赖 | 归因入口锚定 bond-analytics / 分析事实表，balance 仅上下文。 |

---

## 8. 是否影响正式金融语义（Formal finance semantics）

**默认不影響**：在遵守上述隔离的前提下，新增 analytical bundle **不改变** `fact_formal_*` 推导、`balance-analysis.workbook` 的 formal `result_meta` 形状，也不改变监管限额等 formal 读模型。  

若未来将部分组件 **升格为 formal**，必须：独立 ADR、扩展 `calc_rules.md` / `data_contracts.md`、完整回归与 **新** formal 测试套件——**超出本文档范围**。

---

## 9. 建议的下一步（非本次实现）

1. 与 `bond_analytics` 团队/模块对齐 Phase 3 **最小数据切片**（曲线日终 + 工具主键）。  
2. 将 Slice A 的 JSON schema 写入独立契约文档或 OpenAPI 扩展描述。  
3. 为 `not_ready` 响应添加 pytest（实现 Slice B 时）。  

---

## 参考锚点

- `backend/app/core_finance/balance_analysis_workbook.py`：`campisi_breakdown` 与 formal 输入边界。  
- `backend/app/services/bond_analytics_service.py`：`PHASE3_WARNING`、占位 envelope。  
- `tests/test_balance_analysis_workbook_contract.py`：`advanced_attribution_bundle` 不得出现在 workbook table keys。  
- `docs/calc_rules.md` §9、§11；`AGENTS.md` 架构铁律。
