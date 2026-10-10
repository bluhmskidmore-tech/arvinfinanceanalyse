# MOSS-V3 测试跳过（Skipped Tests）全面盘点清单

> **生成时间**：2026-08-27\
> **盘点范围**：`tests/` 与 `backend/tests/` 全部测试文件（排除守卫测试本身 `tests/test_ci_skip_registry.py`）\
> **匹配模式**：`@pytest.mark.skip`、`@pytest.mark.skipif`、`pytest.skip(`、`@pytest.mark.xfail`、`pytest.xfail(`、`pytest.importorskip`\
> **审计属性**：纯盘点清单，不改动任何测试代码与业务逻辑。

---

## 1. 统计总览

| 分类编码 | 分类名称 | 判定定义 | 条目数量 | 占比 |
| :--- | :--- | :--- | :---: | :---: |
| **A** | **环境门控合理保留** | 依赖特定操作系统特权（符号链接/硬链接）、外部守护进程（Redis/PostgreSQL）、受治理本地真实源数据/台账工作簿/系统库，或受控回放门禁，逻辑有效且有清晰边界 | **67** | 95.7% |
| **B** | **功能已废弃建议删除** | 被测功能已下线或废弃，测试用例已无维护价值，建议直接删除 | **0** | 0.0% |
| **C** | **理由不明需要业务确认** | 跳过条件存在脆弱性、随机性或设计逻辑存疑，需要业务/架构人员确认预期行为 | **1** | 1.4% |
| **D** | **临时跳过疑似遗忘** | 历史上因功能未就绪添加的前瞻性/临时跳过，功能实际已落地但跳过分支未收敛 | **2** | 2.9% |
| **合计** | — | — | **70** | **100.0%** |

---

## 2. 分类 A —— 环境门控合理保留（67 处）

### 2.1 操作系统与文件系统能力门控（15 处）

此类跳过主要用于在 Windows 无特权环境与 Linux CI 环境之间的兼容性探测。当测试涉及符号链接逃逸防御、硬链接备份校验等安全用例时，若底层操作系统抛出 `OSError`（如 Windows 缺少 `SeCreateSymbolicLinkPrivilege` 或开发者模式未开启），安全地跳过用例。

| 序号 | 位置 | 跳过条件 | 理由摘要 | 恢复条件 / 建议处置 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `tests/test_stock_analysis_page_gap_factor_vendor_dry_run.py:350` | `except OSError: pytest.skip(...)` | 符号链接创建失败（Windows 权限不足） | 合理保留。Linux CI 环境天然激活，本地 Windows 开发机开启开发者模式可激活。 |
| 2 | `tests/test_stock_analysis_page_gap_factor_manifest.py:543` | `except OSError: pytest.skip(...)` | 符号链接创建在当前平台不可用 | 合理保留。用于验证 CLI 拒收输出路径包含符号链接的安全防御。 |
| 3 | `tests/test_stock_analysis_page_gap_manifest_cli.py:351` | `except OSError: pytest.skip(...)` | 符号链接创建在当前平台不可用 | 合理保留。用于验证清单 CLI 拒收符号链接目录输出。 |
| 4 | `tests/test_stock_analysis_page_gap_manifest_cli.py:381` | `except OSError: pytest.skip(...)` | 符号链接创建在当前平台不可用 | 合理保留。用于验证清单 CLI 拒收符号链接 DuckDB 输入。 |
| 5 | `tests/test_stock_analysis_current_rule_factor_write.py:651` | `except OSError: pytest.skip(...)` | 符号链接创建在当前平台不可用 | 合理保留。用于验证因子写入任务阻断符号链接路径逃逸。 |
| 6 | `tests/test_stock_analysis_current_rule_factor_vendor_dry_run.py:427` | `except OSError: pytest.skip(...)` | 符号链接创建在当前平台不可用 | 合理保留。用于验证 dry run 输出路径符号链接阻断。 |
| 7 | `tests/test_stock_analysis_current_rule_factor_vendor_dry_run.py:455` | `except OSError: pytest.skip(...)` | 符号链接创建在当前平台不可用 | 合理保留。用于验证 dry run 数据库别名符号链接阻断。 |
| 8 | `tests/test_stock_analysis_current_rule_factor_manifest_cli.py:402` | `except OSError: pytest.skip(...)` | 符号链接创建在当前平台不可用 | 合理保留。用于验证当前规则因子清单 CLI 符号链接路径阻断。 |
| 9 | `tests/test_stock_analysis_current_rule_cohort_bundle_producer.py:299` | `except (NotImplementedError, OSError): pytest.skip(...)` | 符号链接创建在当前环境不可用 | 合理保留。构建证据包时探测符号链接能力。 |
| 10 | `tests/test_stock_analysis_current_rule_cohort_materialize.py:620` | `except OSError: pytest.skip(...)` | 硬链接创建不可用（`os.link` 失败） | 合理保留。用于验证群组物化拒绝将硬链接作为写前备份。 |
| 11 | `tests/test_macro_report_asset_service.py:158` | `except OSError: pytest.skip(...)` | Windows 主机缺少符号链接创建能力 | 合理保留。用于验证宏观研报 bundle 拒收符号链接产物。 |
| 12 | `tests/test_stock_analysis_theme_overlay_reader.py:888` | `except OSError: pytest.skip(...)` | 文件符号链接创建失败 | 合理保留。用于验证归档对象符号链接 fail-closed 阻断。 |
| 13 | `tests/test_stock_analysis_theme_overlay_archive.py:947` | `except OSError: pytest.skip(...)` | 目录符号链接创建失败 | 合理保留。用于验证主题归档仓库拒收目录符号链接逃逸。 |
| 14 | `tests/test_stock_analysis_theme_overlay_archive.py:1089` | `except OSError: pytest.skip(...)` | 文件符号链接创建失败 | 合理保留。用于验证相同内容的符号链接别名被拒绝。 |
| 15 | `tests/test_ledger_classification_backfill.py:316` | `except OSError: pytest.skip(...)` | 硬链接创建失败（`os.link` 失败） | 合理保留。用于验证台账分类回填计划拒收硬链接目标备份。 |

---

### 2.2 外部服务、可选工具与依赖包门控（13 处）

此类跳过依赖于可选的外部基础设施（如运行中的 Redis 实例、PostgreSQL DSN、可选 CLI 工具），或作为防御性的 `importorskip` 检查。

| 序号 | 位置 | 跳过条件 | 理由摘要 | 恢复条件 / 建议处置 |
| :--- | :--- | :--- | :--- | :--- |
| 16 | `tests/test_formal_compute_lineage.py:878` | `if not sql_dsn: pytest.skip(...)` | 环境变量 `MOSS_TEST_POSTGRES_DSN` 未配置 | 合理保留。CI 环境配置 PostgreSQL 服务容器及 DSN 即自动激活；常规 jsonl 路径已有充分覆盖。 |
| 17 | `tests/test_source_preview_worker_e2e.py:69` | `if redis_server is None: pytest.skip(...)` | 本机 PATH 中缺少 `redis-server` 可执行文件 | 合理保留。真实 Dramatiq Worker E2E 测试需要真实 Broker，CI 安装 Redis 后自动激活。 |
| 18 | `tests/test_source_preview_worker_e2e.py:156` | `if redis_server is None: pytest.skip(...)` | 本机 PATH 中缺少 `redis-server` 可执行文件 | 合理保留。产品分类刷新真实 Worker E2E 测试。 |
| 19 | `tests/test_source_preview_worker_e2e.py:239` | `if redis_server is None: pytest.skip(...)` | 本机 PATH 中缺少 `redis-server` 可执行文件 | 合理保留。余额分析刷新真实 Worker E2E 测试。 |
| 20 | `tests/test_source_preview_worker_e2e.py:324` | `if redis_server is None: pytest.skip(...)` | 本机 PATH 中缺少 `redis-server` 可执行文件 | 合理保留。债券分析刷新真实 Worker E2E 测试。 |
| 21 | `tests/test_ledger_import_worker_e2e.py:97` | `if redis_server is None: pytest.skip(...)` | 本机 PATH 中缺少 `redis-server` 可执行文件 | 合理保留。台账导入 Worker 端到端测试 fixture 门控。 |
| 22 | `tests/test_api_contract_tooling.py:113` | `if executable is None: pytest.skip(...)` | 本机未安装 `schemathesis` CLI | 合理保留。schemathesis 为未纳入 pyproject 的可选工具，命令形状已由同文件离线用例覆盖。 |
| 23 | `tests/test_data_quality_mcp.py:212` | `duckdb = pytest.importorskip("duckdb")` | 防御性检查 `duckdb` 依赖包 | 合理保留。CI 恒定安装，缺失时给出清晰跳过而非 ImportError。 |
| 24 | `tests/test_data_quality_mcp.py:241` | `duckdb = pytest.importorskip("duckdb")` | 防御性检查 `duckdb` 依赖包 | 合理保留。同上。 |
| 25 | `tests/test_project_mcp_servers.py:14257` | `duckdb = pytest.importorskip("duckdb")` | 防御性检查 `duckdb` 依赖包 | 合理保留。构建临时数据目录证据前检查 duckdb。 |
| 26 | `tests/test_project_mcp_servers.py:14381` | `duckdb = pytest.importorskip("duckdb")` | 防御性检查 `duckdb` 依赖包 | 合理保留。同上。 |
| 27 | `tests/test_project_mcp_servers.py:14435` | `duckdb = pytest.importorskip("duckdb")` | 防御性检查 `duckdb` 依赖包 | 合理保留。同上。 |
| 28 | `tests/test_project_mcp_servers.py:14479` | `duckdb = pytest.importorskip("duckdb")` | 防御性检查 `duckdb` 依赖包 | 合理保留。同上。 |

---

### 2.3 本地真实源数据、治理系统库与历史归档回放（35 处）

此类跳过依赖未提交至 Git 仓库的本地受治理真实源（位于 `.gitignore` 中的 `data_input/`、`data/` 或本机真实 `moss.duckdb`），作为正式业务的黄金锚点回放测试。对应逻辑均已由同文件或同目录下的合成（synthetic）用例覆盖。

| 序号 | 位置 | 跳过条件 | 理由摘要 | 恢复条件 / 建议处置 |
| :--- | :--- | :--- | :--- | :--- |
| 29 | `tests/test_macro_toolkit_refresh.py:625` | `if not duckdb_path.exists(): pytest.skip(...)` | 系统 DuckDB 文件（`data/moss.duckdb`）不存在 | 合理保留。真实端到端冒烟测试；常规逻辑已有 tmp_path 合成覆盖。 |
| 30 | `tests/test_macro_model_chain_results.py:551` | `if not REAL_OUTPUT_DIR.is_dir(): pytest.skip(...)` | 本机 `data/macro_toolkit/output/` 目录缺失 | 合理保留。用于与宏观模型真实输出比对，本地生成产物后自动激活。 |
| 31 | `tests/test_ledger_financial_indicator_summary.py:360` | `if source_dir is None: pytest.skip(...)` | 本机受治理台账源目录 `data_input/*总账对账*日均*/` 缺失 | 合理保留。202603 CNX 黄金核对锚点。 |
| 32 | `tests/test_ledger_financial_indicator_summary_cny.py:41` | `if source_dir is None: pytest.skip(...)` | 本机受治理台账源目录 `data_input/*总账对账*日均*/` 缺失 | 合理保留。202603 CNY 恒等校验黄金锚点。 |
| 33 | `tests/test_ledger_import_flow.py:1651` | `if pack_dir is None: pytest.skip(...)` | 真实银行台账包 `sample_ledgers` 目录不可用 | 合理保留。台账含敏感数据不入库，导入管线逻辑已由合成用例覆盖。 |
| 34 | `tests/test_ledger_import_flow.py:1670` | `if missing_samples: pytest.skip(...)` | 7 个特定真实 xls 台账样本缺失 | 合理保留。同上。 |
| 35 | `tests/test_ledger_import_flow.py:1701` | `if sample is None: pytest.skip(...)` | 真实台账样本 `ZQTZSHOW-20260317.xls` 缺失 | 合理保留。同上。 |
| 36 | `tests/test_ledger_analytics_api.py:621` | `if sample is None: pytest.skip(...)` | 真实台账样本 `ZQTZSHOW-20260317.xls` 缺失 | 合理保留。真实台账看板黄金 KPI 断言。 |
| 37 | `tests/test_snapshot_row_parse.py:329` | `if not path.is_file(): pytest.skip(...)` | 本机 `data/archive/ZQTZSHOW/files/` 下历史样本缺失 | 合理保留。针对 44/45/46 列历史版式的真实黄金锚点；合成用例已覆盖解析分支。 |
| 38 | `tests/test_finance_metric_xlsx.py:1086` | `if not ledger.is_file() or not daily.is_file(): pytest.skip(...)` | 真实 202606 源对（总账/日均）不可用 | 合理保留。OOXML 二进制结构与 1944 行黄金行数断言；解析逻辑已由合成覆盖。 |
| 39 | `tests/test_candidate_financial_indicator_period_comparison_service.py:31` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账与日均工作簿 | 合理保留。已有 synthetic 测试走完整 pipeline 供 CI 验证，真实回放保留为黄金锚点。 |
| 40 | `tests/test_candidate_financial_indicator_component_detail_service.py:28` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。组件明细真实源回放断言；envelope 主路径已有 synthetic 覆盖。 |
| 41 | `tests/test_candidate_financial_indicator_component_detail_service.py:77` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。四项核心指标的真实账户对账断言。 |
| 42 | `tests/test_candidate_financial_indicator_component_detail_service.py:102` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。真实投资收益明细 top 账户与单元格坐标验证。 |
| 43 | `tests/test_candidate_financial_indicator_component_detail_service.py:136` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。父级过期时禁止加载真实数据源的防御用例。 |
| 44 | `tests/test_candidate_financial_indicator_component_detail_service.py:179` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。父级桥不可评估时阻断真实源加载的防御用例。 |
| 45 | `tests/test_finance_metric_component_detail.py:70` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。核心计算组件明细真实输入 fixture。 |
| 46 | `tests/test_finance_metric_component_detail.py:111` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。核心计算真实账户精确对账测试。 |
| 47 | `tests/test_finance_metric_component_detail.py:146` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。投资收益 top 账户排序与证据锚点。 |
| 48 | `tests/test_finance_metric_component_detail.py:176` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。同业往来抵消户排除逻辑测试。 |
| 49 | `tests/test_finance_metric_component_detail.py:209` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。科目集合不匹配时的 fail-closed 防御。 |
| 50 | `tests/test_ledger_pnl_net_interest_golden_sample.py:430` | `@pytest.mark.skipif(...)` | 依赖本地 202604/202605/202606 真实总账工作簿 | 合理保留。真实净利息回放与快照一致性黄金断言；同文件已有合成回放。 |
| 51 | `tests/test_qdb_gl_monthly_analysis_core.py:29` | `pytest.mark.skipif(...)` | 依赖本地 `data_input/*总账对账*日均*/` 真实目录 | 合理保留。共用标记装饰 14 个 202603 真实回放用例；内存合成 openpyxl 已覆盖核心计算。 |
| 52 | `tests/test_portfolio_home_blocker_closure_matrix_check.py:26` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页阻塞项收口矩阵检查（带 integration 标记）。 |
| 53 | `tests/test_portfolio_home_business_owner_approval_packet.py:50` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页业务所有者审批包测试。 |
| 54 | `tests/test_portfolio_home_closure_artifact_presence_check.py:25` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页收口工件在场检查。 |
| 55 | `tests/test_portfolio_home_dependency_consistency_check.py:22` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页依赖一致性检查。 |
| 56 | `tests/test_portfolio_home_evidence_packet_guard.py:32` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页证据包守卫测试。 |
| 57 | `tests/test_portfolio_home_evidence_snapshot.py:35` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页证据快照测试。 |
| 58 | `tests/test_portfolio_home_full_score_preflight.py:29` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页满分预检测试。 |
| 59 | `tests/test_portfolio_home_owner_action_packet.py:62` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页所有者行动包测试。 |
| 60 | `tests/test_portfolio_home_owner_decision_intake_check.py:30` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页所有者决策接收检查。 |
| 61 | `tests/test_portfolio_home_owner_handoff_completeness_check.py:26` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页所有者交接完整性检查。 |
| 62 | `tests/test_portfolio_home_owner_handoff_packet.py:35` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页所有者交接包测试。 |
| 63 | `tests/test_portfolio_home_owner_input_needed_summary.py:27` | `pytest.mark.skipif(not DUCKDB.exists(), ...)` | 依赖本地治理库 `data/moss.duckdb` | 合理保留。组合首页所有者待输入摘要测试。 |

---

### 2.4 受控回放门控与参数防守（4 处）

此类跳过属于业务治理规范要求的“非就绪不回放”门禁，或 CLI 参数语义互斥防守。

| 序号 | 位置 | 跳过条件 | 理由摘要 | 恢复条件 / 建议处置 |
| :--- | :--- | :--- | :--- | :--- |
| 64 | `tests/liability_v1_harness.py:96` | `if not MANIFEST_PATH.exists(): pytest.skip(...)` | 负债 V1 回放样本 `manifest.json` 不存在 | 合理保留。从 `manifest.template.json` 复制并填充真实/脱敏样本后激活。 |
| 65 | `tests/liability_v1_harness.py:103` | `if replay_enabled is False: pytest.skip(...)` | `manifest.json` 存在但 `replay_enabled=false` | 合理保留。治理防线，待准真实/真实样本审批就绪后显式打开开关。 |
| 66 | `tests/liability_v1_harness.py:136` | `if not duckdb_path: pytest.skip(...)` | 未设置 `MOSS_DUCKDB_PATH` 环境变量 | 合理保留。回放前需显式指定 DuckDB 路径。 |
| 67 | `tests/test_pytest_temp_isolation.py:74` | `if request.config.option.basetemp is not None: pytest.skip(...)` | 命令行显式传入 `--basetemp` | 合理保留。显式参数覆盖默认进程级 basetemp 断言时的正常语义跳过。 |

---

## 3. 分类 B —— 功能已废弃建议删除（0 处）

经全面扫描，当前代码库中**不存在**因功能废弃而残留的跳过用例。所有跳过用例均对应活跃维护的业务模块或处于演进中的功能。

---

## 4. 分类 C —— 理由不明需要业务确认（1 处）

| 序号 | 位置 | 跳过条件 | 理由摘要 | 恢复条件 / 建议处置 |
| :--- | :--- | :--- | :--- | :--- |
| 68 | `tests/test_api_contract_baseline_gate.py:225` | `if field_name not in schema.get("required", []): pytest.skip("chosen scalar response property is already optional")` | 动态算法选中的 OpenAPI 响应标量字段本身若不是 `required`，则跳过“字段失去 required 约束属于破坏性变更”的自证测试 | **需确认与优化**：当前实现通过启发式选择首个标量属性，若未来 OpenAPI 规范调整导致被选中的字段刚好为 optional，该测试将静默跳过而无法验证 gate 的破坏性检测能力。**建议处置**：改为确定性选取一个明确为 `required` 的字段，或在基线中查找首个 `required` 标量字段进行测试，移除不稳定的 `pytest.skip`。 |

---

## 5. 分类 D —— 临时跳过疑似遗忘（2 处）

| 序号 | 位置 | 跳过条件 | 理由摘要 | 恢复条件 / 建议处置 |
| :--- | :--- | :--- | :--- | :--- |
| 69 | `tests/test_supply_auction_calendar_boundary_guards.py:61` | `if not files: pytest.skip("Dedicated supply/auction feature files are not present in this checkout yet.")` | 前瞻性守卫测试：当 `FUTURE_SUPPLY_AUCTION_FILES` 都不存在时跳过 | **代码已落地，跳过逻辑应收敛**：`backend/app/api/routes/research_calendar.py`、`services/research_calendar_service.py`、`repositories/research_calendar_repo.py`、`schemas/research_calendar.py` 已全部落地。该分支目前永远不会被触发（`files` 非空），属于功能开发完成后的历史前瞻占位残留。**建议处置**：移除 `if not files: pytest.skip(...)` 分支，直接断言落地文件的边界规则。 |
| 70 | `tests/test_supply_auction_calendar_boundary_guards.py:72` | `if not files: pytest.skip("Dedicated supply/auction feature files are not present in this checkout yet.")` | 前瞻性守卫测试：当 `FUTURE_SUPPLY_AUCTION_FILES` 都不存在时跳过 | **代码已落地，跳过逻辑应收敛**：同上。用例验证落地文件保持 Choice News 仅作为 enrichment，相关功能文件已在仓库中就位。**建议处置**：同上，移除临时 feature-gated 跳过分支。 |

---

## 6. 处置行动建议汇总

1. **针对分类 A（67 处）**：
   - 保持现状，继续由 `tests/test_ci_skip_registry.py` 与 `tests/ci_skip_registry.json` 进行基线受控防护。
   - 对部分高价值真实数据回放用例（如 `test_portfolio_home_*.py` 12 个文件、`candidate_financial_indicator` 部分用例），可在未来按计划逐步补充 Synthetic 合成版本，提高 CI 默认运行覆盖率。
2. **针对分类 C（1 处）**：
   - `test_api_contract_baseline_gate.py:225`：在后续契约测试优化批次中，将动态盲选属性改为查找首个明确声明为 `required` 的标量属性，消除潜在的静默跳过风险。
3. **针对分类 D（2 处）**：
   - `test_supply_auction_calendar_boundary_guards.py:61, 72`：在后续测试清理批次中，将 `FUTURE_SUPPLY_AUCTION_FILES` 重命名为 `DEDICATED_SUPPLY_AUCTION_FILES` 并移除前瞻性 `if not files: pytest.skip` 保护分支，转为确定性断言。
