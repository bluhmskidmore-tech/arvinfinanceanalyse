# CI 后端 Release Suite 清单

- 权威来源：`scripts/backend_release_suite.py` 的常量 `RELEASE_SUITE_TESTS`、`GOVERNANCE_MCP_FAST_SUITE_TESTS`、`GOVERNANCE_MCP_FULL_SUITE_TESTS`、`EXECUTIVE_RELEASE_SAMPLE_IDS`
- 本文档性质：上述常量的**受控静态镜像**（供评审与检索，不是第二事实源）
- 快照日期：2026-08-12（suite_name：`governed-phase2-backend-release-suite`）
- 门禁分层背景与盲区分析：见 `docs/plans/tech-debt-remediation/B0-ci-gate-layering.md`

## 1. 在 CI 中的位置

| 环节 | 内容 |
| --- | --- |
| 触发 | `.github/workflows/ci.yml` 的 `backend` job（`pull_request` → main；`push` → main / `codex/**`），步骤 `Run bounded backend release suite`：`python scripts/backend_release_suite.py` |
| 第一阶段 | `python -m pytest -q <下方 24 个文件>` |
| 第二阶段 | 治理 MCP 合约：默认 fast profile，`python -m pytest -q -m mcp_fast tests/test_project_mcp_fast_contracts.py` |
| 同 job 补充步骤 | agent harness + 门禁映射守卫（**不在 release suite 脚本内**）：`python -m pytest -q tests/test_agent_eval_spec.py tests/test_agent_eval_reward.py tests/test_agent_eval_collect.py tests/test_caliber_gate_mapping.py`；`Caliber path-trigger gate`（仅 `pull_request`）：`git fetch origin <base_ref>` 后运行 `python scripts/check_caliber_gate.py --base-ref origin/<base_ref>`，PR diff 触及 `CALIBER_GATE_MAP` 中的 core_finance 口径源文件时定向运行对应 caliber 红线测试文件（映射表权威在脚本内，拿不到 base-ref 时 fail-closed 非零退出） |
| 全量兜底 | `backend-full-pytest` job（仅 schedule / push→main）：`python -m pytest -q`，收集 `tests/` + `backend/tests/` 全部测试 |

执行环境（脚本注入，决定套件的证明边界）：

- 临时目录隔离：`MOSS_GOVERNANCE_PATH`、`MOSS_DUCKDB_PATH` 指向一次性 `moss-backend-release-*` 目录
- `MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1`、`MOSS_SKIP_POSTGRES_MIGRATIONS=1`、`MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST=1`
- 即：套件证明 fixture 隔离环境下的合约行为，不证明迁移、真实存储与真实鉴权链路

CLI 表面（`python scripts/backend_release_suite.py --help`）：

| 参数 | 用途 |
| --- | --- |
| `--dry-run` | 打印套件执行计划 JSON（含 pytest 参数与环境），是再生成本清单的依据 |
| `--mcp-profile fast\|full` | fast 为 CI 默认；full 跑 `tests/test_project_mcp_servers.py`，仅在共享 MCP 行为变更或发布检查时手动使用 |
| `--live-governance-dir` | 对指定运行时治理目录做血缘审计，空输入 fail-closed |
| `--governance-audit-output` | 审计摘要输出路径（须与 `--live-governance-dir` 同用） |

## 2. 第一阶段：`RELEASE_SUITE_TESTS`（24 个文件，按脚本顺序）

| # | 文件 | 域 | 保护面 |
| --- | --- | --- | --- |
| 1 | `tests/test_settings_contract.py` | 平台与配置 | governance settings 默认值 / 环境变量覆盖 / helper |
| 2 | `tests/test_health_endpoints.py` | 平台与配置 | 健康检查端点 |
| 3 | `tests/test_positions_api_contract.py` | 业务 API 合约 | 持仓 API 封套 + 快照读取行为 |
| 4 | `tests/test_pnl_api_contract.py` | 业务 API 合约 | PnL API 合约（套件内最大单文件） |
| 5 | `tests/test_pnl_by_business_insights_contract.py` | 业务 API 合约 | 业务条线 PnL 洞察 |
| 6 | `tests/test_pnl_by_business_candidate_insights_contract.py` | 业务 API 合约 | 候选口径（Scenario）洞察 |
| 7 | `tests/test_candidate_period_comparison_contract_alignment.py` | 业务 API 合约 | 候选期间对比合约版本跨层对齐 |
| 8 | `tests/test_risk_tensor_api.py` | 业务 API 合约 | 风险张量 API |
| 9 | `tests/test_balance_analysis_api.py` | 业务 API 合约 | 余额分析 API |
| 10 | `tests/test_bond_analytics_api.py` | 业务 API 合约 | 债券分析 API 封套 + 核心结果字段 |
| 11 | `tests/test_executive_dashboard_endpoints.py` | 业务 API 合约 | 高管仪表盘端点 |
| 12 | `tests/test_cube_query_api.py` | 业务 API 合约 | cube 查询 API |
| 13 | `tests/test_liability_analytics_api.py` | 业务 API 合约 | 负债分析 API |
| 14 | `tests/test_liability_analytics_envelope_contract.py` | 业务 API 合约 | 负债分析响应封套 |
| 15 | `tests/test_result_meta_on_all_ui_endpoints.py` | 跨端点封套 | 所有 UI 端点 `result_meta` / `result` / `basis` 语义 |
| 16 | `tests/test_governance_lineage_audit.py` | 治理与血缘 | 血缘审计脚本行为（脏行检测、无副作用） |
| 17 | `tests/test_governance_doc_contract.py` | 治理与血缘 | 治理文档结构与内容合约 |
| 18 | `tests/test_golden_samples_capture_ready.py` | 黄金样本 | capture-ready 样本存在性 / 元数据 / 字段匹配 / fail-closed 允许清单 |
| 19 | `tests/test_ledger_pnl_net_interest_golden_sample.py` | 黄金样本 | 净利息黄金样本对账 + 生产计算链回放 |
| 20 | `tests/test_executive_release_contract.py` | 黄金样本 | 发布门样本合约（对应 `EXECUTIVE_RELEASE_SAMPLE_IDS`） |
| 21 | `tests/test_golden_sample_release_matrix.py` | 黄金样本 | 样本目录与发布门样本 ID 对齐；守卫套件自身必须包含 exec 合约与漂移检查 |
| 22 | `tests/test_live_route_page_contract_completeness.py` | 跨端点封套 | 活跃路由页面契约完备性 / 显式临时豁免（签核 + burn-down） |
| 23 | `tests/test_backend_dependency_contract.py` | 平台与配置 | 运行时依赖与 dev 依赖分离 |
| 24 | `tests/test_no_finance_logic_in_frontend.py` | 架构边界 | 前端源码不得含正式金融计算 token |

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
4. **部分成员资格有测试守卫**：`tests/test_golden_sample_release_matrix.py` 会断言套件包含 exec 发布合约与漂移检查文件——动这些成员会直接红灯；但它**不守卫本文档**，文档同步靠本节纪律 + 下方校验命令。
5. **一致性校验**（评审 checklist 可直接引用；脚本与文档任一漂移即非零退出）：

```powershell
python -c "import pathlib, re, sys; sys.path.insert(0, '.'); import scripts.backend_release_suite as s; doc = pathlib.Path('docs/ci-release-suite.md').read_text(encoding='utf-8'); allowed = set(s.RELEASE_SUITE_TESTS) | set(s.GOVERNANCE_MCP_FAST_SUITE_TESTS) | set(s.GOVERNANCE_MCP_FULL_SUITE_TESTS) | {'tests/test_agent_eval_spec.py', 'tests/test_agent_eval_reward.py', 'tests/test_agent_eval_collect.py', 'tests/test_caliber_gate_mapping.py'}; referenced = set(re.findall(r'tests/test_[a-z0-9_]+\.py', doc)); missing = sorted(set(s.RELEASE_SUITE_TESTS) - referenced); stale = sorted(referenced - allowed); assert not missing, ('doc missing suite files', missing); assert not stale, ('doc references non-suite files', stale); print('ok: %d suite files documented, no stale references' % len(s.RELEASE_SUITE_TESTS))"
```

评审 checklist 条款（可贴进评审规程）：

> 凡 diff 触及 `scripts/backend_release_suite.py` 的套件常量：核对 `docs/ci-release-suite.md` 是否同 PR 更新，并运行上方一致性校验命令；新增成员核对入库门槛（§5.2），移除成员核对留痕说明（§5.3）。
