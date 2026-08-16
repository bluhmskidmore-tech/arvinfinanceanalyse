# E4 — core_finance 反向依赖重锚清单 + 首处试点改造

- 生成日期：2026-08-12
- 扫描范围：`backend/app/core_finance/`
- 生成命令：`rg "from backend.app.(repositories|governance|schema_registry)|import backend.app.(repositories|governance|schema_registry)" backend/app/core_finance/`
- 架构红线：core_finance 应为纯计算层，不得 import `repositories` / `governance` / `schema_registry`
- 状态：重锚完成；试点改造 1 处已落地（`module_contracts.py` 反向 import 清零）。余额 **6 处**（改造前 7 处）。

## 与旧单源清单的差异（重锚修正）

| 旧清单条目 | 重锚结论 |
| --- | --- |
| `source_preview_parsers.py:15` | **误报**。实际 import 的是 `backend.app.schemas.source_preview`（纯 DTO 层），不属于 repositories/governance/schema_registry 红线范围。移出清单。 |
| `formal_financial_indicators.py:305` | **新发现**，旧清单缺失。函数内懒加载 `governance.settings.get_settings`。 |
| `matched_baseline.py` / `adjusted_returns.py` "schema_registry 懒加载" | 定性修正：实际为**模块顶层 import**（非懒加载）。维持既有豁免登记（schema 三套账），本批次跳过。 |

## 重锚清单（逐条）

| # | 文件:行号 | 被 import 符号 | 定性 | 改造方案 | 预估 |
| --- | --- | --- | --- | --- | --- |
| 1 | `module_contracts.py:5` | `governance.locks.LockDefinition` | ~~真反向依赖~~（运行时构造，非类型注解，不可 TYPE_CHECKING 豁免） | **已改造（本批次试点）**：删除 `lock_definition` property 与 import；core 保留 `lock_key`/`lock_ttl_seconds` 纯数据，调用方（tasks/services）自行构造 `LockDefinition` | 已完成 |
| 2 | `macro/toolkit/WindPy.py:8` | `repositories.cffex_member_rank_repo.load_member_rank_frame` / `normalize_cffex_contract` / `normalize_trade_date` | 真反向依赖（顶层 import + 运行时调用，`w.wset("cffexmemberrank")` 路径读 DuckDB） | 调用方注入：`_cffex_member_rank_result` 改收注入的 loader/normalizer（或把三个函数下沉为 core 纯函数 + 帧数据入参）。需同步适配 `crowding_cn.py` 的 `connect_wind()` 消费链 | 中（约 0.5–1 天）；当前被阻塞：`cffex_member_rank_repo.py` git 状态为 M（他人修改中）+ macro/toolkit 为活跃域 |
| 3 | `macro/toolkit/scripts/crowding_cn.py:31-32` | `repositories.cffex_member_rank_repo.TABLE_NAME` / `VIEW_NAME`（字符串常量） | 真反向依赖（顶层 import，仅常量） | 方案 a：常量上移到 schema/契约常量位或脚本参数注入；方案 b：脚本本身属分析脚本，可整体迁出 core_finance（`scripts/` 目录归属重定）。倾向 b，与 #2 同批处理 | 小（常量注入约 1 小时）；同 #2 被 repo M 状态与活跃域阻塞 |
| 4 | `macro/toolkit/system_sources.py:155` | `governance.settings.get_settings`（函数内懒加载，`noqa: PLC0415`） | 真反向依赖（运行时兜底：`duckdb_path=None` 时解析系统 DuckDB 路径） | 调用方显式传 `duckdb_path`，删除兜底懒加载。调用面大：`load_series_by_alias`/`resolve_system_duckdb_path` 被 WindPy、crowding_cn、macro toolkit 多脚本与 service 消费，需全链路适配 | 大（1–2 天）；macro/toolkit 活跃域（macro_toolkit_service 等多文件 M），本批次不动 |
| 5 | `formal_financial_indicators.py:305` | `governance.settings.get_settings`（函数内懒加载，`noqa: PLC0415`） | 真反向依赖（运行时读取 `formal_financial_indicators_workbook` 配置兜底） | `build_formal_financial_indicator_contract(*, report_month, source_workbook=None)` 增可选入参，由 service 层解析配置后传入；core 内 `_resolve_source_workbook` 删除 | 小（约 2–3 小时，含调用方 rg 与测试）；formal 域文件干净，可作下一批次候选 |
| 6 | `matched_baseline.py:21` | `schema_registry.duckdb_loader.REGISTRY_DIR` / `parse_registry_sql_text` | 顶层 import；**已登记豁免**（schema 三套账），本批次跳过 | （登记豁免维持）长期方向：`ensure_*_schema` 类函数整体上移 tasks 层 | 跳过 |
| 7 | `adjusted_returns.py:7` | `schema_registry.duckdb_loader.REGISTRY_DIR` / `parse_registry_sql_text` | 同上，**已登记豁免**，跳过 | 同上 | 跳过 |

## 试点改造结果（#1 module_contracts.py）

选择依据：调用面最小（5 文件 6 处属性访问）、core 文件 git 干净、formal-compute mainline 属 Phase 2 默认授权边界、`bond_analytics_service.py:159` 已有 service 侧直接构造 `LockDefinition` 的现成先例。

改动模式：core 函数签名收纯数据（`lock_key: str` + `lock_ttl_seconds: int` 已有），`LockDefinition` 构造上移到调用方（tasks/services 本就合法 import governance）。

### 改动文件

| 文件 | 改动 |
| --- | --- |
| `backend/app/core_finance/module_contracts.py` | 删除 `from backend.app.governance.locks import LockDefinition` 与 `lock_definition` property（core 反向 import 清零） |
| `backend/app/tasks/formal_compute_runtime.py` | `descriptor.lock_definition` → `LockDefinition(key=descriptor.lock_key, ttl_seconds=descriptor.lock_ttl_seconds)`；ttl 取 `descriptor.lock_ttl_seconds` |
| `backend/app/tasks/bond_analytics_materialize.py` | `BOND_ANALYTICS_LOCK` 改为调用方构造（+ import） |
| `backend/app/tasks/risk_tensor_materialize.py` | `RISK_TENSOR_LOCK` 改为调用方构造（+ import） |
| `backend/app/tasks/balance_analysis_materialize.py` | `BALANCE_ANALYSIS_LOCK` 改为调用方构造（+ import） |
| `backend/app/services/balance_analysis_service.py` | `BALANCE_ANALYSIS_LOCK` 改为调用方构造（已有 import；注意：该文件本就处于 M 状态，仅动此一处赋值） |
| `tests/test_formal_compute_module_registry.py` | 补 `lock_ttl_seconds == 900` 断言；新增冷导入纯度测试 `test_module_contracts_import_stays_pure_of_reverse_layers`（防回归） |

### 等价性证明

- `LockDefinition` 为 frozen dataclass（`key` + `ttl_seconds`），改造前 property 产物与改造后调用方构造完全同参：`lock_key` property 与 `lock_ttl_seconds` 字段未动。
- 既有测试 `tests/test_lazy_task_import_constants.py::test_bond_analytics_service_identity_constants_match_task_modules`：service 侧硬编码 `key="lock:duckdb:formal:bond-analytics:materialize"`、`ttl=900`（改造未触碰），断言与 task 侧改造后构造值相等 → 通过即证明改造前后同输入同输出。
- 既有测试 `tests/test_balance_analysis_module_registration_flow.py`：断言 task/service 两侧 `BALANCE_ANALYSIS_LOCK.key == descriptor.lock_key`。
- 既有测试 `tests/test_formal_compute_lineage.py`：`result["lock"] == descriptor.lock_key` 锁定 runtime 加锁行为不变。

### 验证结果（2026-08-12）

- `python -m pytest tests/test_formal_compute_module_registry.py tests/test_lazy_task_import_constants.py tests/test_balance_analysis_module_registration_flow.py tests/test_formal_compute_lineage.py tests/test_risk_tensor_materialize.py -q` → **74 passed, 1 skipped**（skip 为既有 `MOSS_TEST_POSTGRES_DSN not configured` 环境跳过，与本改动无关）
- `ruff check`（6 个改动源文件 + 测试文件）→ All checks passed
- `rg "lock_definition" --type py` 全库 → 属性访问 0 残留（仅剩同名局部变量，不相关）
- `rg` 复扫 `module_contracts.py` → 反向 import **清零**
- GitNexus upstream impact（`FormalComputeModuleDescriptor.lock_definition`）→ risk LOW（property 访问未入图，实际调用面以 rg 为准，已逐一适配）

## 剩余风险与下一步建议

- `balance_analysis_service.py` 处于用户修改中（M），本次仅动 `BALANCE_ANALYSIS_LOCK` 一行赋值，若用户侧改动与该行冲突需在合并时留意。
- 下一批次候选优先级：#5（`formal_financial_indicators.py`，小、干净、formal 域）→ #2/#3（需等 `cffex_member_rank_repo.py` 修改落定、macro/toolkit 域降温后同批处理）→ #4（调用面最大，最后做）。
- #6/#7 维持 schema 三套账豁免登记，不在 E4 范围内重复清偿。
