# CI 后端 Release Suite 清单

- 权威来源：`scripts/backend_release_suite.py` 的常量 `RELEASE_SUITE_TESTS`、`GOVERNANCE_MCP_FAST_SUITE_TESTS`、`GOVERNANCE_MCP_FULL_SUITE_TESTS`、`EXECUTIVE_RELEASE_SAMPLE_IDS`
- 本文档性质：上述常量的**受控静态镜像**（供评审与检索，不是第二事实源）
- 快照日期：2026-10-01（suite_name：`governed-phase2-backend-release-suite`）
- 门禁分层背景与盲区分析：见 `docs/plans/tech-debt-remediation/B0-ci-gate-layering.md`

## 1. 在 CI 中的位置

| 环节 | 内容 |
| --- | --- |
| 触发 | `.github/workflows/ci.yml` 的 `backend` job（`pull_request` → main；`push` → main / `codex/**`），步骤 `Run bounded backend release suite`：`python scripts/backend_release_suite.py` |
| 结构门 | `.github/workflows/ci.yml` 的 `release-control-structure` job，名称固定为 `Release Control Structure (not approval)`；先迁移一次性 PostgreSQL 并强制两项 whole-bundle CAS 并发测试零跳过，再运行 `python scripts/check_release_approval_registry.py` 默认结构模式，断言回执中的 `structure_only=true`、`gate_scope=structure_only`、`approval_decision=not_evaluated`、`release_gate_eligible=false`，随后运行 release control、固定收益版本集合、单日期 shadow 和多日期结构证据测试，不执行 `--execute-evidence` |
| 第一阶段 | `python -m pytest -q -m "not excluded_surface_acceptance" <下方 48 个文件>`；黄金阻断审阅包、WP7 隔离演练与固定收益试点预检测试均在默认门内，但对应回执仍固定为非审批、非生产、非放行证据 |
| 第二阶段 | 治理 MCP 合约：默认 fast profile，`python -m pytest -q -m "mcp_fast and not excluded_surface_acceptance" tests/test_project_mcp_fast_contracts.py` |
| 同 job 补充步骤 | agent harness + 门禁映射守卫（**不在 release suite 脚本内**）：`python -m pytest -q tests/test_agent_eval_spec.py tests/test_agent_eval_reward.py tests/test_agent_eval_collect.py tests/test_agent_eval_scoring_integrity.py tests/test_agent_eval_replay.py tests/test_agent_eval_pr_replay.py tests/test_agent_eval_rollout.py tests/test_agent_eval_coverage_report.py tests/test_agent_sql_disclosure_drift.py tests/test_agent_api_contract.py tests/test_agent_audit_log_contract.py tests/test_dexter_agent_service.py tests/test_agent_run_service_lifecycle.py tests/test_agent_run_cancellation_hook.py tests/test_caliber_gate_mapping.py tests/test_ci_workflow_contents.py tests/test_mcp_config_consistency.py`；`Caliber path-trigger gate`（仅 `pull_request`）：`git fetch origin <base_ref>` 后运行 `python scripts/check_caliber_gate.py --base-ref origin/<base_ref>`，PR diff 触及 `CALIBER_GATE_MAP` 中的 core_finance 口径源文件时定向运行对应 caliber 红线测试文件（映射表权威在脚本内，拿不到 base-ref 时 fail-closed 非零退出；2026-08-12 起六个 caliber 红线文件同时是 release suite 无条件成员，路径触发为定向快反、套件成员为无条件兜底，互为双保险） |
| 全量兜底 | `backend-full-pytest` job（仅 schedule / push→main）：`python -m pytest -q`，收集 `tests/` + `backend/tests/` 全部测试 |

执行环境（脚本注入，决定套件的证明边界）：

- 临时目录隔离：`MOSS_GOVERNANCE_PATH`、`MOSS_DUCKDB_PATH` 指向一次性 `moss-backend-release-*` 目录
- `MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1`、`MOSS_SKIP_POSTGRES_MIGRATIONS=1`、`MOSS_SKIP_STORAGE_READINESS_CHECKS=1`、`MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST=1`；迁移跳过与 readiness 跳过分别显式声明，前者不再隐式关闭后者
- marker 过滤：两个阶段默认都带 `not excluded_surface_acceptance`（常量 `EXCLUDED_SURFACE_DEFAULT_MARKER_EXPR`），即 `tests/AGENTS.md` 第 3 层的排除面 feature / workflow / ETL acceptance 不进默认门禁
- 即：套件证明 fixture 隔离环境下的合约行为，不证明迁移、schema readiness、真实存储与真实鉴权链路，也不证明排除面的验收行为
- `release-control-structure` job 单独使用一次性 PostgreSQL 验证 whole-bundle CAS 并发，并证明 registry 结构、release control 状态机/CLI/repo 合约、固定收益 configured-current 版本披露和逐日 shadow 隔离封装仍然成立；它不证明生产迁移或生产授权。多日期测试只证明独立逐日 candidate 的聚合与失败隔离，不证明单 candidate 全历史重建，也不证明正式审批已就绪。当前 authority policy / scope mapping 仍可保持 `PENDING`，只要结构回执继续是 `structure_only` 且 `release_gate_eligible=false`，普通 PR 就不会因此被误判为审批失败或审批通过

CLI 表面（`python scripts/backend_release_suite.py --help`）：

| 参数 | 用途 |
| --- | --- |
| `--dry-run` | 打印套件执行计划 JSON（含 pytest 参数与环境），是再生成本清单的依据 |
| `--mcp-profile fast\|full` | fast 为 CI 默认；full 跑 `tests/test_project_mcp_servers.py`，仅在共享 MCP 行为变更或发布检查时手动使用 |
| `--include-excluded-surfaces` | 解除两个阶段的 `not excluded_surface_acceptance` 过滤，一并运行排除面验收；CI 不使用，仅供本地排查排除面回归 |
| `--live-governance-dir` | 对指定运行时治理目录做血缘审计，空输入 fail-closed |
| `--governance-audit-output` | 审计摘要输出路径（须与 `--live-governance-dir` 同用） |

## 2. 第一阶段：`RELEASE_SUITE_TESTS`（48 个文件，按脚本顺序）

| # | 文件 | 域 | 保护面 |
| --- | --- | --- | --- |
| 1 | `tests/test_backend_release_suite.py` | 门禁选择 | 发布套件选择器与隔离边界 |
| 2 | `tests/test_caliber_gate_mapping.py` | 门禁选择 | 生产路径与测试自身改动触发 |
| 3 | `tests/test_system_online_read_boundary.py` | 在线读取 | 系统代际固定与缓存隔离 |
| 4 | `tests/test_system_online_publication_concurrency.py` | 并发发布 | HTTP读取和发布互斥 |
| 5 | `tests/test_system_read_publication_process_crash.py` | 发布恢复 | 进程崩溃与指针提交恢复 |
| 6 | `tests/test_campisi_formal_bridge_coverage.py` | 归因契约 | 正式桥覆盖和可用性传递 |
| 7 | `tests/test_product_category_read_boundary.py` | 只读边界 | 产品分类只读回退与调整快照 |
| 8 | `tests/test_settings_contract.py` | 平台与配置 | governance settings 默认值 / 环境变量覆盖 / helper |
| 9 | `tests/test_health_endpoints.py` | 平台与配置 | 健康检查端点 |
| 10 | `tests/test_positions_api_contract.py` | 业务 API 合约 | 持仓 API 封套 + 快照读取行为 |
| 11 | `tests/test_pnl_api_contract.py` | 业务 API 合约 | PnL API 合约（套件内最大单文件） |
| 12 | `tests/test_pnl_by_business_insights_contract.py` | 业务 API 合约 | 业务条线 PnL 洞察 |
| 13 | `tests/test_pnl_by_business_candidate_insights_contract.py` | 业务 API 合约 | 候选口径（Scenario）洞察 |
| 14 | `tests/test_candidate_period_comparison_contract_alignment.py` | 业务 API 合约 | 候选期间对比合约版本跨层对齐 |
| 15 | `tests/test_risk_tensor_api.py` | 业务 API 合约 | 风险张量 API |
| 16 | `tests/test_balance_analysis_api.py` | 业务 API 合约 | 余额分析 API |
| 17 | `tests/test_bond_analytics_api.py` | 业务 API 合约 | 债券分析 API 封套 + 核心结果字段 |
| 18 | `tests/test_executive_dashboard_endpoints.py` | 业务 API 合约 | 高管仪表盘端点 |
| 19 | `tests/test_cube_query_api.py` | 业务 API 合约 | cube 查询 API |
| 20 | `tests/test_liability_analytics_api.py` | 业务 API 合约 | 负债分析 API |
| 21 | `tests/test_liability_analytics_envelope_contract.py` | 业务 API 合约 | 负债分析响应封套 |
| 22 | `tests/test_result_meta_on_all_ui_endpoints.py` | 跨端点封套 | 所有 UI 端点 `result_meta` / `result` / `basis` 语义 |
| 23 | `tests/test_governance_lineage_audit.py` | 治理与血缘 | 血缘审计脚本行为（脏行检测、无副作用） |
| 24 | `tests/test_governance_doc_contract.py` | 治理与血缘 | 治理文档结构与内容合约 |
| 25 | `tests/test_golden_samples_capture_ready.py` | 黄金样本 | capture-ready 样本存在性 / 元数据 / 字段匹配 / fail-closed 允许清单 |
| 26 | `tests/test_ledger_pnl_net_interest_golden_sample.py` | 黄金样本 | 净利息黄金样本对账 + 生产计算链回放 |
| 27 | `tests/test_executive_release_contract.py` | 黄金样本 | 发布门样本合约（对应 `EXECUTIVE_RELEASE_SAMPLE_IDS`） |
| 28 | `tests/test_golden_sample_release_matrix.py` | 黄金样本 | 样本目录与发布门样本 ID 对齐；守卫套件自身必须包含 exec 合约与漂移检查 |
| 29 | `tests/test_live_route_page_contract_completeness.py` | 跨端点封套 | 活跃路由页面契约完备性 / 显式临时豁免（签核 + burn-down） |
| 30 | `tests/test_backend_dependency_contract.py` | 平台与配置 | 运行时依赖与 dev 依赖分离 |
| 31 | `tests/test_ci_skip_registry.py` | 平台与配置 | CI 跳过登记表的结构与引用一致性 |
| 32 | `tests/test_api_contract_baseline_gate.py` | 合约门禁 | OpenAPI 破坏性变更门禁的判定逻辑本身：`scripts/api_contract_check.py` 的 `diff_contracts` 对 breaking / additive 的分级，以及 `contracts/openapi/` 基线快照的提交状态、规范序列化、default 面裁剪与豁免条目合法性 |
| 33 | `tests/test_api_response_model_field_preservation.py` | 合约门禁 | 声明 `response_model` 后端点未丢字段：服务层原始 dict 与经模型过滤后的 HTTP 响应字段路径集合必须完全相等；封套 `extra="forbid"` 结构性护栏；黄金样本原样回放 |
| 34 | `tests/test_release_approval_registry.py` | 发布审批 | 审批 registry 结构、命令 allowlist 与运行前置约束 |
| 35 | `tests/test_release_approval_evidence_gate.py` | 发布审批 | 五态 evidence gate、摘要绑定、过期/撤销阻断与无旁路 approve/promote |
| 36 | `tests/test_release_control_golden_blocker_review.py` | 发布审批 | 脱敏 JUnit 阻断索引、样本摘要绑定、成对 owner 路由、安全输出根及“测试全绿仍不可自动审批/放行” |
| 37 | `tests/test_wp7_release_rehearsal.py` | 发布演练 | 合成 whole-bundle promote/rollback、负向探针、路径防绕过和回执复验；明确不产生生产放行证据 |
| 38 | `tests/test_wp7_fixed_income_pilot_preflight.py` | 发布演练 | 固收试点结构化交接包预检、两类回滚分支、安全输出根与“字段齐全仍不可自动授权生产” |
| 39 | `tests/test_no_finance_logic_in_frontend.py` | 架构边界 | 前端源码不得含正式金融计算 token |
| 40 | `tests/test_no_finance_logic_in_api.py` | 架构边界 | API 层不得包含正式金融公式 |
| 41 | `tests/test_api_route_boundaries.py` | 架构边界 | API 路由职责与依赖边界 |
| 42 | `tests/test_service_storage_boundaries.py` | 架构边界 | 服务层不得直连 DuckDB 写路径 |
| 43 | `tests/test_caliber_rule_fx_mid_conversion.py` | 口径红线 | FX 中间价折算口径 |
| 44 | `tests/test_caliber_rule_hat_mapping.py` | 口径红线 | H/A/T 映射口径 |
| 45 | `tests/test_caliber_rule_subject_514_516_517_merge.py` | 口径红线 | 514/516/517 科目合并口径 |
| 46 | `tests/test_caliber_rule_issuance_exclusion.py` | 口径红线 | 发行债排除口径 |
| 47 | `tests/test_caliber_rule_formal_scenario_gate.py` | 口径红线 | Formal-Scenario 门 |
| 48 | `tests/test_caliber_rule_accounting_basis.py` | 口径红线 | 会计口径归一 |

发布门样本 ID（`EXECUTIVE_RELEASE_SAMPLE_IDS`）：`GS-EXEC-OVERVIEW-A`、`GS-EXEC-PNL-ATTR-A`、`GS-EXEC-SUMMARY-A`。

## 3. 第二阶段：治理 MCP 合约

| profile | 文件 | pytest 参数 | 使用场景 |
| --- | --- | --- | --- |
| fast（默认，CI 在用） | `tests/test_project_mcp_fast_contracts.py` | `-q -m mcp_fast` | PR / push 门禁；本地默认 MCP 反馈环 |
| full（手动） | `tests/test_project_mcp_servers.py` | `-q` | 共享 MCP 行为变更、发布检查（`--mcp-profile full`）；nightly 全量 pytest 也会收集 |

## 4. 再生成方法

清单唯一权威是脚本常量。核对 / 再生成时执行：

```powershell
python scripts/backend_release_suite.py --dry-run
```

输出 JSON 的 `pytest_args` 即第一阶段文件序列，`governance_mcp_suite.pytest_args` 即第二阶段，`env` 即注入环境。将其与本文档 §2/§3 表格逐行比对（顺序也应一致）。

## 5. 更新规则

1. **同 PR 同步**：任何增删改 `RELEASE_SUITE_TESTS`、`GOVERNANCE_MCP_*_SUITE_TESTS`、`EXECUTIVE_RELEASE_SAMPLE_IDS` 的 PR，必须在同一 PR 内更新本文档（表格行 + 快照日期），并在 PR 描述注明"套件成员变更"。
2. **入库门槛**：新文件加入 release suite 应满足——属于对外合约面 / 发布门锚点（而非深层单测）、能在脚本注入的隔离环境下运行、无外部服务依赖、运行时间与 `backend` job 20 分钟限时相容。深层单测的 PR 防护走"触达路径定向测试"约定（见 B0 文档 §2），不要靠扩容 release suite 解决。
3. **移除须留痕**：从套件移除文件时，PR 描述必须说明该保护面由什么替代（迁移到别的测试 / 保护面下线）。
4. **成员资格与文档守卫**：`tests/test_golden_sample_release_matrix.py` 会断言套件包含 exec 发布合约与漂移检查文件；`tests/test_ci_workflow_contents.py` 会检查本文档未遗漏 release suite / 治理 MCP 成员、未引用套件与实际 agent harness 之外的测试目标，并单独按顺序核对 harness 清单。表格行号、域与保护面说明仍须人工评审。
5. **一致性校验**（评审 checklist 可直接引用；脚本与文档任一漂移即非零退出）：

```powershell
backend\.venv\Scripts\python.exe -B -m pytest tests/test_ci_workflow_contents.py::test_release_suite_documentation_has_no_missing_or_stale_test_targets tests/test_ci_workflow_contents.py::test_agent_harness_documentation_matches_ci_step_targets -q
```

第一项直接读取 release suite / 治理 MCP 的脚本常量，并以实际 CI harness 目标界定文档可引用的补充测试；第二项解析 `.github/workflows/ci.yml` 中 `Run agent harness tests` 步骤，再与本文档的 harness 清单按顺序比对。脚本常量与实际 CI 步骤仍是唯一权威，文档命令不维护第二份允许清单；§4 的 `--dry-run` 继续用于核对第一、二阶段的顺序和执行环境。

评审 checklist 条款（可贴进评审规程）：

> 凡 diff 触及 `scripts/backend_release_suite.py` 的套件常量或 `.github/workflows/ci.yml` 的 agent harness 步骤：核对 `docs/ci-release-suite.md` 是否同 PR 更新，并运行上方两项一致性校验；新增成员核对入库门槛（§5.2），移除成员核对留痕说明（§5.3）。
