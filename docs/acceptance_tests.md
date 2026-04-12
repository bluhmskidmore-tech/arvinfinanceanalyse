# acceptance_tests.md

## 1. 验收总则

任何涉及正式金融口径的变更，必须同时通过：
- 单元测试
- 集成测试
- 样例数据回归测试
- 关键 API smoke tests

## 2. Phase 1：骨架验收

### 2.1 目录
- 仓库包含 `backend/app/api/`
- 仓库包含 `backend/app/services/`
- 仓库包含 `backend/app/core_finance/`
- 仓库包含 `backend/app/tasks/`
- 仓库包含 `frontend/src/`
- 仓库包含 `docs/`、`tests/`、`config/`

### 2.2 启动
- FastAPI 可启动
- `/health` 返回 200
- 前端可启动并访问首页
- Docker Compose 可启动基础依赖

### 2.3 连接
- PostgreSQL 连接成功
- DuckDB 文件创建成功
- Redis 连接成功或开发模式显式降级

## 3. Phase 2：正式计算验收

### 3.1 H/A/T
- 输入 `可供出售` → `A/FVOCI`
- 输入 `交易性` → `T/FVTPL`
- 输入 `持有至到期` → `H/AC`
- 不可识别输入进入治理异常

### 3.2 516
- 输入 `T损益516=100` → 统一标准口径 `-100`
- 输入 `金额=100, 借贷标识=贷` → ETL 后 `signed_amount` 正确
- 正式层不得再次根据借贷标识翻转

### 3.2A Formal PnL 语义
- AC 的 516 不进入 formal total_pnl
- FVOCI 的 516 不进入 formal total_pnl
- FVTPL 的 516 进入 formal total_pnl
- 517 仅在 formal-recognized realized component / formal event 成立时进入 total_pnl
- manual_adjustment 仅在治理/审批状态字段为 approved 时进入 total_pnl，且判定不得依赖自由文本
- 当前 start-pack 若仍输出 standardized totals，则必须被标注为 start-pack behavior，不得宣称 formal semantics complete

### 3.3 发行类债券排除
- `position_scope=asset` 排除发行类债券
- `position_scope=liability` 仅保留发行类债券
- `position_scope=all` 保留全量

### 3.4 FX
- USD 债券逐日人民币换算正确
- 周末沿用前一营业日中间价
- 缺失营业日中间价时 Formal 失败
- 不允许先均值后换算

### 3.5 日均金额
- `observed`、`locf`、`calendar_zero` 三种 basis 结果可区分
- Formal 与 Analytical basis 不混淆
- 输出 `coverage_ratio` 与 `missing_dates`

### 3.5A 收益率曲线与曲线效应
- `fact_formal_yield_curve_daily` 只允许由 `backend/app/tasks/` 物化写入；`yield_curve_daily` 仅作为读视图暴露
- `treasury` 与 `cdb` 曲线物化结果必须同时带 `vendor_name / vendor_version / source_version`
- AkShare 为主路径；AkShare 不可用时允许 Choice 作为真实 fallback
- service/read path 只允许回退到“请求日及以前”的最近可用曲线，不允许 future-date fallback
- `pnl.bridge` 在 governed curve 可用时，`roll_down / treasury_curve` 不再固定为 0
- `bond_analytics.return_decomposition` 在 governed curve 可用时，`roll_down / rate_effect` 不再固定为 0
- `credit_spread / fx_translation` 在当前 slice 仍允许保持 0，但必须有显式 warning
- 短端点位 `3M / 6M / 9M` 不得在插值前被丢弃
- 至少一组固定 fixture/reference 需要对 `roll_down / treasury_curve / rate_effect` 做数值断言，不能只验非 0

### 3.6 Formal / Scenario / Analytical 隔离
- `basis=formal` 的结果必须同时满足 `formal_use_allowed=true` 且 `scenario_flag=false`
- `basis=scenario` 的结果必须同时满足 `formal_use_allowed=false` 且 `scenario_flag=true`
- `basis=analytical` 的结果必须同时满足 `formal_use_allowed=false` 且 `scenario_flag=false`
- Scenario 结果不得写入 `fact_formal_pnl_fi`、`fact_nonstd_pnl_bridge` 或任何 `fact_formal_*` 表
- Analytical 结果不得冒充 `fact_formal_*`，也不得把 `formal_use_allowed=true` 当作默认值
- `fact_formal_*`、`fact_scenario_*`、`fact_analytical_*` 不能共用同一个物化缓存或同一个表名空间
- 同一 `source_version` / `rule_version` / 过滤条件下，不同 `basis` 必须生成不同的 `cache_key` 和 `cache_version`
- `approval_status` 或同级治理字段必须是 `manual_adjustment` 的 approved 来源，自由文本不算通过
- `517` 的 realized 语义必须来自枚举化 event semantics，不允许把 FVTPL 解释成无条件放行
- 如果设计只依赖强逻辑隔离而不拆 formal-only 事实表与 cache namespace，则判定不通过

### 3.6B ZQTZ / TYW 文档合同对齐

本节只做 assertion by reference，不单独维护第二套 snapshot 合同。

- `zqtz_bond_daily_snapshot` 与 `tyw_interbank_daily_snapshot` 的结构、canonical grain、hard-required lineage、直接允许 / 禁止消费者，以 [data_contracts.md](data_contracts.md) 为准。
- `basis / formal_use_allowed / scenario_flag` 与 cache identity，以 [CACHE_SPEC.md](CACHE_SPEC.md) 为准。
- 若 [data_contracts.md](data_contracts.md) 之外出现独立 snapshot 字段清单、主键清单或 lineage 清单，则判定不通过。
- 若 [CACHE_SPEC.md](CACHE_SPEC.md) 之外出现独立 `basis / formal_use_allowed / scenario_flag` 真值表，则判定不通过。
- [CURRENT_BOUNDARY_HANDOFF_2026-04-10.md](CURRENT_BOUNDARY_HANDOFF_2026-04-10.md) 与 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 只允许保留 docs-only / non-authorization 语言；若复述 snapshot 结构合同，则判定不通过。
- 本轮验证 docs-only contract alignment，必须同时避免以下误写：
  - 把 snapshot 写成已 materialized 的 formal result
  - 把当前已落地的 governed formal compute / materialize / service / API / 首个 workbench consumer 写成 future-only
  - 把 workbench 写成可直接消费 snapshot

### 3.6C ZQTZ / TYW Formal Balance Contract（implemented path + continuing contract）

本节定义已落地 governed formal balance-analysis 的测试归属与继续扩展边界，不构成放宽架构约束的授权。

- `fact_formal_zqtz_balance_daily` 与 `fact_formal_tyw_balance_daily` 的字段、grain、lineage 与允许消费者，以 [data_contracts.md](data_contracts.md) 为准。
- `zqtz / tyw` formal balance 只允许从 snapshot + FX + 治理输入进入 formal fact，不允许从 `phase1_*preview*` 进入 formal fact。
- `invest_type_std` / `accounting_basis` / `position_scope` / `currency_basis` 只允许在 `core_finance/` 中派生。
- `应收投资款项` 必须按正式规则映射到 `H / AC`，不得在 service / UI 中临时特判。
- `currency_basis=CNY` 时，必须验证“先逐日 FX，后逐日 formal amount，最后月均”。
- `position_scope=asset/liability/all` 时，必须验证发行类排除与保留规则。
- `发行类债券` 必须作为 liability-scoped balance row 保留，不得重新并入资产端 `H/A/T`。
- workbook-style balance-analysis 读面必须只消费 `fact_formal_zqtz_balance_daily` / `fact_formal_tyw_balance_daily`，不得回读 snapshot / preview。
- 所有 outward response 必须显式返回 `result_meta`，且 `basis / formal_use_allowed / scenario_flag` 语义与 [CACHE_SPEC.md](CACHE_SPEC.md) 保持一致。
- 当前仓库已实现 governed formal compute / materialize / service / API / 首个 workbench consumer；测试与文档必须据此标注已交付边界，但不得把 snapshot 直读或更多未落地能力写成已完成。

已落地并应持续回归的测试文件：
- `tests/test_balance_analysis_contracts.py`
- `tests/test_balance_analysis_core.py`
- `tests/test_balance_analysis_materialize_flow.py`
- `tests/test_balance_analysis_service.py`
- `tests/test_balance_analysis_api.py`
- `tests/test_balance_analysis_boundary_guards.py`
- `tests/test_balance_analysis_workbook_contract.py`
- `tests/test_balance_analysis_module_registration_flow.py`
- `tests/test_formal_compute_module_registry.py`
- `tests/test_formal_compute_runtime_contract.py`
- `tests/test_formal_compute_result_meta_contract.py`

当前文件级断言：
- `test_balance_analysis_contracts.py` 只校验 contract、grain、消费者边界与 docs 引用关系，不额外替业务宣称超出当前实现面的功能。
- `test_balance_analysis_core.py` 覆盖 H/A/T、FX、发行类排除、月均顺序与 `position_scope` 规则。
- `test_balance_analysis_materialize_flow.py` 明确 formal fact 不能读取 `phase1_*preview*`。
- `test_balance_analysis_service.py` 约束 governed envelope、refresh 状态与 result_meta 语义。
- `test_balance_analysis_api.py` 明确 outward payload 必带 `result_meta`。
- `test_balance_analysis_boundary_guards.py` 保护“formal 公式只能在 `core_finance/`”。
- `test_balance_analysis_workbook_contract.py` 约束 workbook-style governed read model 的表格、分桶与指标结构。
- `test_balance_analysis_module_registration_flow.py` 保护 API / core_finance / task / frontend 的模块注册链路。
- `test_formal_compute_module_registry.py` 约束 formal module descriptor 的 basis / fact identity / duplicate registration fail-closed 行为。
- `test_formal_compute_runtime_contract.py` 约束 shared materialize runtime 的 run record / manifest / writer-failure lineage 语义。
- `test_formal_compute_result_meta_contract.py` 约束 shared formal result helper 的 `result_meta` 与 envelope 语义。

### 3.6D Gate A 测试矩阵与文件级测试设计

本节是 `Task 2A-3` 的测试设计，不构成实现授权。

#### Unit tests：规则函数 / 归属矩阵 / 元数据判定
- 目标：验证单条记录或单个规则函数在不依赖完整 materialize 流程时即可判断正确。
- 重点覆盖：
  - H/A/T 到 formal 归属规则：`AC / FVOCI / FVTPL` 对 `514 / 516 / 517 / manual_adjustment` 的 recognized matrix。
  - `516 signed_amount` 与 `formal recognized total_pnl` 的区分：允许 `fi_pnl_record` 保留 standardized total，但不允许把 standardized total 直接当作 formal total。
  - `517 realized / formal event semantics`：仅枚举化 realized component / formal event 可进入 formal total。
  - `approval_status` 对 `manual_adjustment` 的 gating：只接受治理字段的 approved，不接受自由文本。
  - `basis / formal_use_allowed / scenario_flag` 一致性：三种 basis 下字段必须显式且组合固定。
- 建议复用：
  - `tests/test_pnl_phase2_start_pack.py`
  - `tests/test_pnl_core_finance_contract.py`
  - `tests/test_result_meta_required.py`
- 建议新增：
  - `tests/test_pnl_formal_semantics_contract.py`
  - `tests/test_result_meta_basis_contract.py`
- 建议文件级断言：
  - `test_pnl_phase2_start_pack.py` 继续只验证 standardized layer，不宣称 formal semantics complete。
  - `test_pnl_formal_semantics_contract.py` 新增 matrix-style case：`AC/FVOCI/FVTPL x 514/516/517/manual_adjustment`。
  - `test_pnl_formal_semantics_contract.py` 新增 `517` negative cases：event 未枚举、仅凭 `FVTPL` 标签、无 realized path 时不得进入 formal total。
  - `test_pnl_formal_semantics_contract.py` 新增 `manual_adjustment` negative cases：`approval_status != approved` 或仅有自由文本说明时不得进入 formal total。
  - `test_result_meta_basis_contract.py` 明确三种 basis 的 `scenario_flag` 必须显式出现，且 `formal/scenario/analytical` 分别为 `false/true/false`。

#### Integration tests：materialize / service / cache / lineage 一致性
- 目标：验证跨 task、fact、service、cache、result_meta 的链路一致，不只看单点规则。
- 重点覆盖：
  - `fi_pnl_record -> fact_formal_pnl_fi` 时，formal recognized total 与 standardized total 不混淆。
  - `fact_nonstd_pnl_bridge` 保持 bridge grain，不被 scenario / analytical 结果污染。
  - `basis / formal_use_allowed / scenario_flag` 在 materialize、service response、cache manifest 中一致。
  - formal / scenario / analytical cache isolation：主 `cache_key`、lock key、latest cache version key 都必须带 `basis`。
  - manifest / lineage / meta fields consistency：`trace_id`、`source_version`、`rule_version`、`cache_version`、`basis`、`scenario_flag`、`formal_use_allowed` 不能互相矛盾。
- 建议复用：
  - `tests/test_pnl_materialize_flow.py`
  - `tests/test_pnl_api_contract.py`
  - `tests/test_analysis_service_adapters.py`
  - `tests/test_preview_lineage_rule_trace.py`
  - `tests/test_result_meta_on_all_ui_endpoints.py`
- 建议新增：
  - `tests/test_pnl_basis_isolation_flow.py`
  - `tests/test_cache_basis_isolation.py`
  - `tests/test_lineage_manifest_consistency.py`
- 建议文件级断言：
  - `test_pnl_materialize_flow.py` 扩展 formal fact 断言：`fact_formal_pnl_fi.total_pnl` 代表 recognized total，不回填 standardized total。
  - `test_pnl_api_contract.py` 扩展 `result_meta`：formal / scenario / analytical 三种响应均显式返回 `basis / scenario_flag / formal_use_allowed`。
  - `test_analysis_service_adapters.py` 扩展 scenario 读路径：scenario overlay 不得把结果写回 formal fact 命名空间。
  - `test_cache_basis_isolation.py` 新增缓存隔离断言：同一 `source_version/rule_version/filter_hash` 下，不同 basis 生成不同 `cache_key`、`moss:lock:*`、`moss:meta:latest_cache_version:*`。
  - `test_lineage_manifest_consistency.py` 新增 lineage 断言：manifest、response meta、缓存元信息中的 `basis` 和版本字段必须一致。

#### Regression tests：保护 start-pack 边界与既有 API 合同
- 目标：在引入 formal semantics / isolation / lineage 规则后，不破坏现有 Phase 1 与 start-pack 合同。
- 重点覆盖：
  - 现有 `pnl_materialize -> pnl_service` 链路继续可运行。
  - 已存在的 standardized behavior 若仍保留，必须被标注为 start-pack behavior，而不是冒充 formal complete。
  - 现有 UI/API 必须继续返回 `result_meta`，且新增字段不会破坏旧合同必填项。
- 建议复用：
  - `tests/test_pnl_phase1_boundaries.py`
  - `tests/test_pnl_api_contract.py`
  - `tests/test_result_meta_required.py`
  - `tests/test_result_meta_on_all_ui_endpoints.py`
- 建议新增：
  - `tests/test_pnl_start_pack_regression.py`
  - `tests/test_result_meta_regression.py`
- 建议文件级断言：
  - `test_pnl_start_pack_regression.py` 明确 start-pack 可继续输出 standardized total，但文档/响应不得把它宣称为 formal semantics complete。
  - `test_result_meta_regression.py` 确认新增 `basis / scenario_flag / formal_use_allowed` 后，旧的 `trace_id / source_version / rule_version / cache_version` 必填合同不回退。

#### 现有测试复用建议汇总
- `tests/test_pnl_phase2_start_pack.py`：复用为 standardized layer 回归，不承担完整 formal semantics 验证。
- `tests/test_pnl_core_finance_contract.py`：复用为 core_finance 导出面和 contract smoke。
- `tests/test_pnl_materialize_flow.py`：复用为 formal fact 与 materialize integration 入口。
- `tests/test_pnl_api_contract.py`：复用为 `result_meta` 与 API response contract 入口。
- `tests/test_analysis_service_adapters.py`：复用为 scenario read-path / overlay 入口。
- `tests/test_preview_lineage_rule_trace.py`：复用为 lineage / rule trace 扩展点。
- `tests/test_result_meta_required.py` 与 `tests/test_result_meta_on_all_ui_endpoints.py`：复用为 meta 必填项与跨 endpoint 回归。

#### 新增测试文件建议汇总
- `tests/test_pnl_formal_semantics_contract.py`
- `tests/test_result_meta_basis_contract.py`
- `tests/test_pnl_basis_isolation_flow.py`
- `tests/test_cache_basis_isolation.py`
- `tests/test_lineage_manifest_consistency.py`
- `tests/test_pnl_start_pack_regression.py`
- `tests/test_result_meta_regression.py`

#### 执行边界
- 本节只定义 Gate A 的测试矩阵、文件建议和断言边界。
- 本节不授权新增生产实现，不授权修改 `core_finance`、`services`、`tasks`、`cache` 代码。
- 真正进入编码前，必须先按本节矩阵把测试归属和 fixtures 策略拆成可执行任务单。

### 3.6E QDB GL baseline source-binding + input-contract validation

本节只验证 contract-level admissibility，不构成 normalization、storage、analytical output 或 formal-upstream 授权。

- `总账对账YYYYMM.xlsx` 与 `日均YYYYMM.xlsx` 的 baseline source-binding，以 [data_contracts.md](data_contracts.md) 的 `qdb_gl_baseline_input` 为准。
- 识别失败的文件必须返回 contract-level `fail evidence`，不得静默当作 baseline input。
- canonical sheet 缺失时，必须记为 `source_binding` 失败，而不是下沉为其他检查类别。
- `ledger_reconciliation` 必须检测：
  - header row
  - row-shape
  - required raw fields
  - account-code text preservation
  - currency grouping
  - reconciliation contract
- `ledger_reconciliation` 的 auxiliary trailing columns 可存在，但不得破坏前 7 列 core contract。
- `ledger_reconciliation` 的 row-level reconciliation 允许 `±0.01` rounding tolerance。
- `average_balance` 必须检测：
  - header row
  - row-shape
  - required raw fields
  - account-code text preservation
  - currency grouping
  - `reconciliation_contract = not_applicable`
- `average_balance` 的最后一个 header block 允许无尾部 spacer。
- `average_balance` 以 canonical tuple `(currency_raw, account_code_raw, avg_balance_raw)` 的 admissibility 为准。
- row 内不组成 canonical tuple 的 auxiliary fragments 允许存在；但以有效币种开头的不完整 tuple 必须 fail。
- contract evidence 必须带：
  - `source_file`
  - `source_kind`
  - `report_month`
  - `source_version`
  - `rule_version`
  - `trace_id`
  - `sheet_name`
  - `row_locator`（适用时）
- contract evidence 的 `status_label` 只允许：
  - `pass`
  - `fail`
  - `not_applicable`
- 输出必须保持为 lineage-aware pass/fail evidence，不得产出分析指标、read model 或 materialized target 描述。

本轮对应测试文件：
- `tests/test_qdb_gl_input_contract_validation.py`

## 4. Phase 3：分析深钻验收

### 4.1 cube query
- 支持 `dimensions`
- 支持 `measures`
- 支持 `filters`
- 支持 `drill`
- 支持 `sort`
- 支持 `pagination`

### 4.2 PnL Bridge
- 输出 carry / roll_down / treasury_curve / credit_spread / fx_translation / realized_trading / unrealized_fv / residual
- `explained_pnl` 与 `actual_pnl` 可比较
- `quality_flag` 生成正确

### 4.3 Risk Tensor
- 输出 DV01 / KRD / CS01 / convexity
- 支持发行人、组合、期限桶分组

## 5. Phase 4：前端验收

- 首页为 Claude 风格工作台
- 头寸页支持深钻到单券 / 单笔
- 损益页支持 Formal / Analytical 切换
- 风险页支持期限桶与发行人维度
- 证据面板显示 tables_used / source_version / rule_version / trace_id

## 6. 缓存验收

- 同参数请求命中 Redis 或 DuckDB 物化缓存
- `source_version` 变化后缓存失效
- `rule_version` 变化后缓存失效
- Scenario 不命中 Formal 缓存
- 人工调整后仅相关缓存失效
- API 路径不发生 DuckDB 写入

## 7. 安全与治理验收

- 没有 endpoint 直接写正式金融公式
- 前端没有实现正式金融公式
- 所有正式结果返回 `result_meta`
- Scenario 结果返回 `formal_use_allowed=false`

## 8. 最低回归样例

### 8.1 FI 2025-12
- Formal PnL 汇总结果稳定
- H/A/T 汇总结果稳定

### 8.2 zqtz 2026-03
- 债券月均市值默认排除发行类债券
- USD 债券人民币折算结果稳定

### 8.3 tyw 2026-03
- 同业月均金额可按 observed / locf / calendar_zero 输出

## 9. 交付要求

每次 Codex 输出必须包含：
- 变更文件清单
- 测试清单与结果
- 未完成项
- 风险点
- 是否影响正式金融口径
