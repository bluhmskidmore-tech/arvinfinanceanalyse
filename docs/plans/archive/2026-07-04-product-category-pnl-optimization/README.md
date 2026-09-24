# Product-Category PnL 优化与新分析功能 — 执行包（2026-07-04）

本目录是 `/product-category-pnl` 页面的一轮"保正确优化 + 新增分析计算"任务包。
每个 `T*.md` 是一份可独立领取的任务书，按编号顺序执行。执行者（Codex）在动手前必须完整阅读本 README 的全局护栏。

## 任务清单与顺序

| 任务 | 文件 | 类型 | 依赖 | 建议分支名 |
| --- | --- | --- | --- | --- |
| T1 巨型文件拆分 | `T1-page-model-split.md` | 行为等价重构 | 无 | `refactor/pcp-page-model-split` |
| T2 FTP 情景网格 + 后端盈亏平衡 | `T2-scenario-grid-breakeven.md` | 新功能（scenario 口径） | 无（建议在 T1 后做，减少冲突） | `feat/pcp-scenario-grid` |
| T3 YTD/多视图归因 | `T3-ytd-attribution.md` | 新功能（正式口径扩展） | T2 合并后 | `feat/pcp-ytd-attribution` |
| T4 rate_effect 结构/纯利率分解 | `T4-mix-rate-decomposition.md` | 新功能（analytical-only） | T3 合并后 | `feat/pcp-rate-mix-decomposition` |

T2/T3/T4 都会改 `backend/app/services/product_category_pnl_service.py` 与归因/读模型相关文件，**必须串行**，避免合并冲突与口径互相污染。

## 全局护栏（每个任务都适用，违反即返工）

1. **分层铁律**：`frontend -> api -> services -> (repositories/core_finance) -> storage`。所有公式只进 `backend/app/core_finance/`，API 路径对 DuckDB 只读，写入只走 `backend/app/tasks/`。
2. **前端零金融计算**：前端只做格式化/排序/展示重塑。T2 会**删除**一处现存的前端插值计算（见 T2），此外不得新增任何前端算式。
3. **Decimal**：core_finance 内所有金额/利率运算使用 `decimal.Decimal`，禁止 float 中间量。
4. **测试先行**：每个任务先写失败测试（含手算期望值），再实现，最后全绿。
5. **回归锚**：凡是扩展既有接口，新参数取默认值时响应必须与改动前**逐字段一致**（用现有 flow 测试 + 新增快照断言证明）。
6. **闭合恒等式**：归因类计算必须继承 `closure_error` 传统——分解项之和与实际变动的差异必须显式入 `unexplained_effect` 并断言闭合。
7. **指标治理**：当前 active 指标仅 `MTR-PCP-001`~`MTR-PCP-012`（见 `docs/metric_dictionary.md` §12.3.1）。任何新字段**不得**标注为 formal metric；analytical 输出必须在 payload/meta 中可辨识，且在 `docs/metric_dictionary.md` §15.4 排除清单登记一行（登记为 excluded/candidate，不新造 `MTR-*` 编号）。
8. **口径版本**：不改变既有字段公式则 `rv_product_category_pnl_v1` 不动；一旦既有字段结果会变，必须停下来上报，不得自行 bump。
9. **提交前**：跑 GitNexus `gitnexus_detect_changes()`（如工具可用）；前端改动跑 `npm run lint`、`npm run typecheck`、`npm run debt:audit`；后端跑任务书列出的 pytest 目标。
10. **报告格式**：按仓库 `CLAUDE.md`"任务响应默认结构"输出（变更文件、新增/修改测试、验证命令与结果、风险与影响范围、是否影响正式金融口径、未完成项）。

## 关键代码坐标（公共参考）

- 页面组件：`frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`（约 5253 行）
- 页面 model：`frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts`（约 5052 行）
- 路由：`backend/app/api/routes/product_category_pnl.py`（前缀 `/ui/pnl/product-category`）
- 服务：`backend/app/services/product_category_pnl_service.py`（`AVAILABLE_VIEWS` 在 :57，`YTD_VIEWS` 在 :58）
- 读模型计算：`backend/app/core_finance/product_category_pnl.py`（`calculate_read_model` :165-301；`apply_scenario_to_rows` :304-329；`_calculate_ftp` :557；`_calculate_weighted_yield` :561-568）
- 归因：`backend/app/core_finance/product_category_pnl_attribution.py`（`_build_effects` :114-185；`_three_factor_effects` :188-201；`_days_in_month` :436-438；`_cash_rate` :367-374）
- DuckDB 表：`backend/app/schema_registry/duckdb/08_product_category_pnl.sql`
- 后端测试（仓库根 `tests/`）：`test_product_category_pnl_flow.py`、`test_product_category_pnl_attribution.py`、`test_product_category_formula_boundaries.py`、`test_golden_samples_capture_ready.py`、黄金样本 `tests/golden_samples/GS-PROD-CAT-PNL-A/`
- 前端测试：`frontend/src/test/ProductCategoryPnlPage.test.tsx`、`frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`、同目录 `*.dateSemantics.test.ts`、`frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`、`frontend/src/test/ProductCategoryBranchSwitcher.test.tsx`

## 不在本包范围内（不得顺手做）

- 分类别 FTP 利率曲线（口径变更，需业务 owner 决策）
- 剩余收尾阻塞中的产品决策项（刷新超时文案、扩展校验文案、双排序 rationale——见 `docs/pnl/product-category-remaining-blockers.md`）
- 12 个月滚动归因桥（待 T3 落地后另立任务）
- 任何对 `MTR-PCP-*` 字典行、黄金样本断言语义的修改
