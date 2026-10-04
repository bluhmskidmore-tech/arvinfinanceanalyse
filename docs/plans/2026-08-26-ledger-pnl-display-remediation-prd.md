# Ledger PnL 页面展示与披露整改 PRD

- 日期：2026-08-26
- 页面：`/ledger-pnl?report_date=2026-07-31&currency=CNX`（PAGE-LEDGER-PNL-001）
- 触发：用户反馈“前端及数据展示及计算有问题”
- 证据来源：三路并行审计（前端展示链路审读、后端计算增量审计、13 个端点运行时实测），基线为 `docs/audits/2026-08-25-ledger-pnl-202607-rule-calculation-review.md`

## 1. 诊断结论

**金额计算无错误。** 六项头部汇总实测与 2026-08-25 基线完全一致；`pytest tests/test_ledger_pnl_routes.py tests/test_ledger_pnl_service.py` 93 项全绿；186 项候选指标、跨期比较、净息桥算术均闭合。

用户体感“有问题”的真实根因是三类**展示与披露缺陷**：

1. **明细噪音（最主要）**：`/api/ledger-pnl/data` 的 3945 行中有 **2009 行是日均侧合成行**（总账期初/期末/损益全 0、`account_name` 为空串，其中 1249 行连日均也为 0），与 1936 行真实总账行混排且无任何来源标记。页面明细表和 `evidence_rows` 因此虚高约一倍，用户看到大量空名 0.00 行。填 0 并集口径本身是 2026-08-12 业务确认过的设计，**不改口径，只补披露**。
2. **负零**：CNX 明细存在 727 个 `"-0.00"`（summary 另有 69 个），系小额负数折算亿元四舍五入产物，展示层未归一化。
3. **呈现细节**：工作簿预览表默认静默截断 5 行无提示；186 项指标目录直接铺开 10 位小数 Decimal 原始串；“增减幅不取绝对值”（复刻工作簿口径）无就近提示；`formatMoney` 兜底分支用 `toFixed`（IEEE 754 舍入）与全页 ROUND_HALF_UP 不一致且无测试。

另发现两个**当前不改数字但高杠杆的结构脆弱点**：总账解析按 sheet 位置切片 `worksheets[:2]` 未校验名称（第 3 个 sheet“青岛地区综本”一旦换序会静默污染全行口径）；同 (科目,币种) 重复键静默后行覆盖前行（候选链路有 duplicate 控制，主账链路无）。

## 2. 本次整改范围

### P0（直接消除用户体感问题）

**R1 合成行披露（后端 + 前端全链路）**

冻结契约（前后端并行实现的依据，字段名不得偏离）：

```text
LedgerPnlDataRow 新增必填字段:
  source_presence: "ledger" | "average_only"
    ledger        = 总账工作簿中真实观测的行
    average_only  = 仅日均工作簿存在、总账侧填 0 的合成行

/data 响应 summary 新增必填字段:
  ledger_evidence_rows: int      # source_presence == "ledger" 的行数
  average_only_row_count: int    # source_presence == "average_only" 的行数
  恒等: ledger_evidence_rows + average_only_row_count == count
```

- 现有 `count`、`evidence_rows` 语义保持不变（并集口径），避免破坏既有基线断言；在 `calculation_basis`/说明字段中显式声明“evidence_rows 为总账∪日均并集口径行数”。
- 判定依据：`build_canonical_facts`（`backend/app/services/product_category_source_service.py`）中缺总账侧填 0 的行即 `average_only`；实现时应在构建 canonical 事实处打标，不得在下游用“三金额全 0”反推。
- 202607 CNX 预期值：`ledger_evidence_rows=1936`、`average_only_row_count=2009`、`count=3945`。
- 前端明细表：默认隐藏 `average_only` 行，提供开关“显示日均侧合成行（N）”；显示时行内加标记；空 `account_name` 不得显示为空白（显示“——（仅日均侧科目）”一类占位）。证据行数文案改为“总账证据行 X · 日均侧合成行 Y”。
- `basis_comparison` 的资产/负债 `metric_evidence_rows`（`backend/app/core_finance/ledger_pnl_analysis.py:244-269`）同步新增 `ledger_evidence_rows` 同语义字段，并在 `calculation_basis` 注明并集口径。

**R2 负零归一化（后端）**

- `yi` 展示字段量化后数值为 0 时输出 `"0.00"` 不带负号；`yuan` 原值字符串保留来源符号不动。
- 参照已有先例 `_serialize_analysis_money`（`backend/app/services/ledger_pnl_service.py:174-187`）。注意 `LedgerMoneyValue` 的 Pydantic 校验器（yi 必须等于 yuan 按 ROUND_HALF_UP 量化）：`Decimal("-0.00") == Decimal("0.00")` 数值相等，需确认校验器兼容或同步调整校验器与其测试。

### P1（展示与防御改进）

**R3 工作簿预览表截断提示（前端）**：`LedgerPnlWorkbookTables.tsx` 的 `WorkbookTable` 加“共 {rows.length} 行，仅显示前 {rowLimit} 行”caption（仅在实际截断时显示），并提供展开全部/收起。

**R4 186 项指标目录精度双态（前端）**：`LedgerPnlCandidateFinancialIndicatorsPanel.tsx` 默认按 ROUND_HALF_UP 显示 4 位小数（复用 `candidatePeriodComparisonModel.ts` 的 `fixedDecimal` BigInt 实现，不得用 `toFixed`/`Number`），hover 或展开显示完整 Decimal 原始串。展示层压缩小数位不属于前端复算，已有跨期表先例。

**R5 增减幅符号提示（前端）**：`LedgerPnlFinancialIndicatorSummaryPanel.tsx` 的“增减幅”列头加就近提示（复用 `RowInfoMarker` 一类既有元素）：“按工作簿口径直接相除、未取绝对值，对比期为负时符号可能与直觉相反”。后端口径不动。

**R6 `formatMoney` 兜底修正（前端）**：删除 `LedgerPnlPage.tsx:175-186` 中 `yuan/1e8 → toFixed(2)` 的前端自算路径（后端契约保证 `yi` 必填合法）；`yi` 缺失/非法直接显示 `--`。补 `yi` 非法场景单测。

**R7 sheet 名称校验（后端，共享服务）**：`product_category_source_service.py:138` 由 `worksheets[:2]` 位置切片改为按名称精确选择（`综本`、`人民币`），名称缺失时 fail loud（抛类型化异常），与候选引擎解析器 `finance_metric_xlsx.py:229` 对齐。该服务被 product-category-pnl 页共享，改动前必须跑 GitNexus 影响分析并回归 product-category 相关测试。

**R8 重复键检测（后端）**：同 (科目,币种) 键重复时不再静默覆盖，至少记录 warning 并保留可观测证据（与候选链路 `ledger.duplicate_full_code` 控制语义对齐）。202607 实测无重复键，本项为防御。

### P2（低风险顺带修正）

**R9**：经营指标表当月源缺失时 `resolved_report_date`/`as_of_date` 回退值由月初 `YYYY-MM-01` 改为自然月末（`ledger_pnl_service.py:765-768`），与全页“报告月解析为月末”口径一致。

## 3. 本次不做（列入后续批次）

| 事项 | 原因 |
| --- | --- |
| `/monthly-analysis/workbook` 9.29s 性能优化 | 独立优化，避免与本次改动叠加风险；建议后续复用 `_FACTS_CACHE` 文件指纹缓存模式 |
| `tables_used` 血缘元数据失真修正 | 涉及全部 envelope 断言，影响面大，需单独批次 |
| `/data`、`/summary` 非月末日期 422 统一 | 现行为被测试显式固化，疑似有意设计，需先在页面契约层裁决 |
| `total_pnl_cnx/cny` 传输 0 改 null 或移除 | 前端未消费，无用户可见影响 |
| 来源锁哈希、19 项人工输入、11 个缺失科目补源、202607 正式契约登记 | 数据治理与业务审批事项，非代码可解决，见基线文档 §10/§12 |
| 同页两区块来源锁 mismatch 降级策略差异 | 需产品/治理裁决后在页面契约登记，不属代码缺陷 |

## 4. 执行拆分

两个执行子代理并行，边界为前后端目录，契约字段以本 PRD §2-R1 冻结定义为准：

- **代理 A（后端）**：R1 后端部分、R2、R7、R8、R9 + 后端测试 + OpenAPI 契约导出同步（如有导出脚本）。改动面：`ledger_pnl_service.py`、`ledger_pnl_read.py`、`product_category_source_service.py`、`ledger_pnl_analysis.py`（及其 schema）、`tests/test_ledger_pnl_*.py`。
- **代理 B（前端）**：R1 前端部分、R3、R4、R5、R6 + 前端契约类型（`balanceLedger.ts`）+ mocks + vitest 测试。改动面：`frontend/src/features/ledger-pnl/**`、`frontend/src/api/contracts/balanceLedger.ts`、`frontend/src/mocks/ledgerPnlMocks.ts`、`frontend/src/test/LedgerPnl*.test.*`。

## 5. 验收标准

- [ ] 六项头部汇总金额与基线完全一致（8296.29 / 7743.67 / 552.61 / 6.42 / 2.75 / 9.18 亿元），任何金额不得变化。
- [ ] `/data` 202607 CNX：`count=3945` 不变，`ledger_evidence_rows=1936`，`average_only_row_count=2009`，恒等成立。
- [ ] 页面明细默认视图不再出现空科目名 0.00 噪音行；切换开关可显示全部并带来源标记。
- [ ] 明细与 summary 的 `yi` 字段不再出现 `"-0.00"`；`yuan` 原值符号不变。
- [ ] `pytest tests/test_ledger_pnl_routes.py tests/test_ledger_pnl_service.py` 全绿（含新增用例：合成行标记与计数、负零归一化、sheet 名称校验、重复键 warning）。
- [ ] product-category 共享链路回归测试全绿（R7 影响面）。
- [ ] 前端 `LedgerPnl*` vitest 全绿（含新增：合成行过滤开关、截断提示、`formatMoney` yi 非法分支、指标目录双态精度）。
- [ ] 前端不新增任何金额/比率业务计算；所有新增展示逻辑仅消费后端字段。
- [ ] candidate/formal 边界、null 语义、warning 状态呈现不回退。
