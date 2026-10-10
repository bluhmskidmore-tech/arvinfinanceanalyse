# C5 — 脚本生命周期盘点与规范

- 日期：2026-08-12
- 范围：`scripts/*.py`（顶层 147 个）与 `backend/scripts/*.py`（13 个），合计 160 个。不含 `scripts/mcp/`、`scripts/agent_eval/`、`scripts/stitch/` 子目录与 ps1/mjs/cmd 文件（README 中另有说明）。
- 快照说明：盘点开跑时顶层为 146 个；盘点期间并行技术债任务新增了 `check_mypy_baseline.py`（§3 末行 #147），已并入统计。
- 方法：逐个实读全部 159 个脚本的头部（docstring / 前 20 行 / import 面），结合 `git log -1 --format=%cs` 最近提交日期、CI workflow / ps1 wrapper / timer 安装脚本 / `backend/app` 生产 import / `tests/` 配对测试等交叉证据分类。每个分类的实读代表远超 5 个（159 个头部全部实读；另对 `emit_average_balance_governance_record.py`、`emit_pnl_attribution_governance_record.py`、`refresh_system_audit_monitoring.py`、`_run_diagnose_adb_other.py` 等做了全文/深读）。
- 本报告只盘点与建议，不移动、不删除、不重命名任何脚本。归档动作需人工批准后另行执行。

## 1. 分类统计总览

| 分类 | scripts/ | backend/scripts/ | 合计 | 占比 |
| --- | ---: | ---: | ---: | ---: |
| 常驻工具（permanent） | 63 | 6 | 69 | 43.1% |
| 一次性已完成（one-off, done） | 28 | 4 | 32 | 20.0% |
| 状态不明（unclear / 待流程收口） | 50 | 3 | 53 | 33.1% |
| dev 编排（dev orchestration） | 6 | 0 | 6 | 3.8% |
| **合计** | **147** | **13** | **160** | 100% |

同构堆积热点（含于上表）：

| 家族 | 数量 | 现分类 | 说明 |
| --- | ---: | --- | --- |
| `portfolio_home_*` | 26 | 状态不明 | 2026-05-31 portfolio-home 页闭环证据机器，最近活动 2026-08-08 |
| `emit_*_governance_record` | 14 | 状态不明 | 高度同构（12 个标准形 + 2 个变体），见 §7 收敛方案 |
| `check_*_business_owner_approval` | 9 | 常驻 7 / 状态不明 2 | 7 个是 `codex_page_readiness` 就绪 gate 的库依赖 |
| `backfill_*` | 9（scripts 6 + backend 3） | 常驻 7 / 一次性 1 / 状态不明 1 | 多数委托 task/物化路径、可幂等重跑 |
| `calculation_p1_* / system_audit_* / refresh_*snapshot` | 13 | 常驻 9 / 状态不明 4 | 2026-06-10 系统审计监控机器仍在活跃刷新（2026-08-07） |

## 2. 判定准则（证据优先级从高到低）

- **H1 硬接线 → 常驻**：被 `.github/workflows/*.yml`、`install_*_timer.ps1`、`dev-*.ps1`/`codex-*.ps1`、或 `backend/app` 生产代码引用。
- **H2 库依赖 → 常驻**：被 H1 类常驻脚本 `import`（如 `check_*` 被 `codex_page_readiness` 引用、审计快照族被 `refresh_system_audit_monitoring` 引用）。
- **H3 可重复运维入口 → 常驻**：无固定日期钉死、委托 `backend/app/tasks` 或 `core_finance` 官方路径、数据缺口/契约变化时需重跑。
- **H4 钉死单一事件/日期且产物已落盘 → 一次性已完成**：docstring 或常量固定单一 report_date / audit_date / 事故（如 `run_decimal_precision_backfill.py` 钉死 2026-07-31、2025Q1 ADB 对账族、`fix_silent_exceptions.py` 自述一次性）。
- **H5 闭环/审批流程未确认终结 → 状态不明**：脚本本身可再跑，但存在意义绑定某个尚未人工确认收口的治理流程（portfolio-home 闭环、P1 业主决策、emit 治理记录）。
- **H6 dev 环境/协作服务 → dev 编排**。

## 3. 逐脚本盘点 — `scripts/`（146 个）

分类缩写：常驻 = 常驻工具；一次性 = 一次性已完成；不明 = 状态不明；dev = dev 编排。日期为 `git log -1 --format=%cs`。

| # | 脚本 | 最近提交 | 分类 | 用途摘要（读头部推断） |
| ---: | --- | --- | --- | --- |
| 1 | `_run_diagnose_adb_other.py` | 2026-05-05 | 一次性 | 只读执行 `diagnose_adb_liabilities_other.sql`，下钻 ADB 负债“其他”科目 |
| 2 | `api_contract_check.py` | 2026-05-13 | 常驻 | FastAPI OpenAPI 导出与 API 契约检查入口（ci.yml 调用） |
| 3 | `audit_governance_lineage.py` | 2026-07-18 | 常驻 | 审计治理 JSONL 的 source/rule_version 血缘完整性（dev-up/dev-smoke/发布套件调用） |
| 4 | `audit_worktree_scope.py` | 2026-07-18 | 常驻 | 审计 git worktree 变更是否越出授权文件范围（agent 治理 gate） |
| 5 | `average_balance_live_smoke_evidence.py` | 2026-08-08 | 一次性 | 生成 average-balance 页 2026-06-09 现场冒烟证据文档 |
| 6 | `average_balance_owner_evidence_packet.py` | 2026-06-10 | 一次性 | 汇总生成 average-balance 业主证据包（docs/pnl） |
| 7 | `backend_api_inventory.py` | 2026-07-27 | 常驻 | 导出后端 API 路由面清单（json/csv），接口盘点审计用 |
| 8 | `backend_release_suite.py` | 2026-08-04 | 常驻 | 后端发布验证套件编排（ci.yml backend job 主入口） |
| 9 | `backfill_adjusted_returns.py` | 2026-07-06 | 常驻 | 按复权因子重算执行历史复权收益（core_finance 路径，幂等回填） |
| 10 | `backfill_choice_stock_replay_inputs.py` | 2026-05-31 | 常驻 | 回填 Choice 股票回放输入物化（choice_stock_materialize task 路径） |
| 11 | `backfill_csi300_benchmark_from_backup.py` | 2026-07-06 | 一次性 | 从备份 CSV 恢复 CSI300 基准行情（带治理锁的事故恢复） |
| 12 | `backfill_livermore_gate_supplement.py` | 2026-05-31 | 常驻 | 从 CSI300 宏观历史回填 Livermore gate 补充表（缺口告警时重跑） |
| 13 | `backfill_stock_adjustment_factor.py` | 2026-08-06 | 常驻 | 回填/维护股票复权因子表（core_finance schema） |
| 14 | `backfill_yield_curves.py` | 2026-06-08 | 常驻 | 收益率曲线月末锚点批量回填（yield_curve_materialize task 路径） |
| 15 | `balance_movement_freshness_watch.py` | 2026-07-21 | 常驻 | 余额变动读模型日度新鲜度守护（timer 安装脚本调用） |
| 16 | `bond_analysis_live_smoke_evidence.py` | 2026-06-09 | 一次性 | 生成 bond-analysis 页 2026-06-09 冒烟证据文档 |
| 17 | `bond_analysis_owner_evidence_packet.py` | 2026-06-10 | 一次性 | 生成 bond-analysis 业主证据包 |
| 18 | `bootstrap_kpi_postgres.py` | 2026-04-21 | dev | 从 seed JSON 导入 KPI 指标/业主到 Postgres（dev 初始化） |
| 19 | `build_source_audit_artifact.py` | 2026-07-18 | 常驻 | 构建源码审计工件 zip+manifest（source-audit-artifact.yml 调用） |
| 20 | `build_source_manifest_layers.py` | 2026-04-14 | 常驻 | 重建 source manifest 分层记录（dev-governance-maintenance.ps1 调用） |
| 21 | `business_display_coverage_report.py` | 2026-08-08 | 常驻 | 业务展示覆盖率报告（映射既有测试证据；system_audit_pulse 依赖） |
| 22 | `calculation_p1_first_priority_readiness_packet.py` | 2026-08-07 | 不明 | 生成 2026-06-10 审计 P1-10/11 首优先项就绪包 |
| 23 | `calculation_p1_owner_decision_packet.py` | 2026-06-11 | 不明 | 生成 P1 计算项业主决策包（固定 2026-06-10 决策矩阵） |
| 24 | `calculation_p1_owner_meeting_checklist.py` | 2026-06-11 | 不明 | 生成 P1 业主决策会议核对清单 |
| 25 | `calculation_p1_post_owner_execution_plan.py` | 2026-08-07 | 不明 | 生成 P1 业主决策后执行计划 |
| 26 | `capture_candidate_financial_indicator_frontend_fixture.py` | 2026-07-11 | 常驻 | 生成候选财务指标前端演示 fixture（契约变化时重新生成） |
| 27 | `check_average_balance_business_owner_approval.py` | 2026-06-10 | 常驻 | 解析 average-balance 业主审批模板完成度（codex_page_readiness 库依赖） |
| 28 | `check_balance_analysis_business_owner_approval.py` | 2026-06-07 | 常驻 | 同上（balance-analysis 页） |
| 29 | `check_bond_analysis_business_owner_approval.py` | 2026-06-08 | 常驻 | 同上（bond-analysis 页） |
| 30 | `check_ledger_pnl_business_owner_approval.py` | 2026-06-08 | 常驻 | 同上（ledger-pnl 页） |
| 31 | `check_livermore_readiness.py` | 2026-05-31 | 常驻 | 只读核查 Livermore 开仓所需历史与 Choice 股票目录就绪态 |
| 32 | `check_pnl_attribution_business_owner_approval.py` | 2026-06-08 | 常驻 | 同 #27（pnl-attribution 页） |
| 33 | `check_portfolio_home_business_owner_approval.py` | 2026-06-08 | 不明 | 解析 portfolio-home 业主审批模板与 KRD/到期/警示决策（闭环族依赖） |
| 34 | `check_product_category_pnl_business_owner_approval.py` | 2026-06-08 | 常驻 | 同 #27（product-category-pnl 页） |
| 35 | `check_stock_analysis_business_owner_approval.py` | 2026-06-08 | 常驻 | 同 #27（stock-analysis 页） |
| 36 | `choice_funding_probe.py` | 2026-06-10 | 常驻 | 构建 Choice 资金面 EDB 探测计划（只读探针） |
| 37 | `choice_stock_daily_refresh.py` | （未跟踪） | 常驻 | Choice 股票日度物化刷新 operator CLI（timer 安装脚本引用；**git 未跟踪**） |
| 38 | `codex_page_readiness.py` | 2026-08-07 | 常驻 | 页面就绪度报告核心引擎（codex-page-readiness.ps1 与 10+ 脚本依赖） |
| 39 | `compact_source_preview_governance.py` | 2026-04-14 | 常驻 | 压缩 source preview 治理刷新记录（dev-governance-maintenance.ps1） |
| 40 | `compare_formal_snapshot_adb_sources.py` | 2026-05-04 | 一次性 | 只读对比 formal 事实表与快照的 ADB 口径差异（2025Q1 排查） |
| 41 | `copy_choice_stock_asof_from_duckdb.py` | 2026-05-31 | 一次性 | 跨 DuckDB 文件拷贝 Choice 股票 as-of 数据（一次迁移，带锁） |
| 42 | `data_readiness_report.py` | 2026-07-16 | 常驻 | DuckDB 数据就绪度体检（日期/数值范围/新鲜度检查） |
| 43 | `dev_postgres_cluster.py` | 2026-08-07 | dev | 本地 dev Postgres 集群启停/建库/重置（dev-env、dev-postgres-* 调用） |
| 44 | `diagnose_entry_premium.py` | 2026-07-06 | 一次性 | Livermore 入场溢价诊断（产出 2026-07 batch2 报告） |
| 45 | `diagnose_gate_state_flips.py` | 2026-07-06 | 一次性 | 诊断 gate 状态翻转频率与影响（策略研究） |
| 46 | `diagnose_macro_multiplier.py` | 2026-07-06 | 一次性 | 诊断宏观乘数对敞口的影响（策略研究） |
| 47 | `diagnose_overheat_holdings.py` | 2026-07-06 | 一次性 | 诊断过热持仓退出行为（策略研究；有未提交改动） |
| 48 | `diff_zqtz_formal_vs_snapshot.py` | 2026-05-04 | 一次性 | ZQTZ formal vs snapshot 逐券逐日面值核对（2025Q1 排查） |
| 49 | `emit_average_balance_governance_record.py` | 2026-06-09 | 不明 | 生成/预检 average-balance 候选治理记录，可追加 cache_manifest（§7） |
| 50 | `emit_balance_analysis_governance_record.py` | 2026-06-07 | 不明 | 同上（balance-analysis） |
| 51 | `emit_bond_analysis_governance_record.py` | 2026-06-09 | 不明 | 同上（bond-analysis） |
| 52 | `emit_cashflow_projection_governance_record.py` | 2026-06-09 | 不明 | 同上（cashflow-projection） |
| 53 | `emit_concentration_monitor_governance_record.py` | 2026-06-09 | 不明 | 同上（concentration-monitor） |
| 54 | `emit_decision_items_governance_record.py` | 2026-06-09 | 不明 | 同上（decision-items） |
| 55 | `emit_kpi_performance_governance_record.py` | 2026-06-09 | 不明 | 同上（kpi-performance） |
| 56 | `emit_ledger_pnl_governance_record.py` | 2026-06-06 | 不明 | 同上（ledger-pnl；被 2 个快照/证据脚本 import） |
| 57 | `emit_news_events_governance_record.py` | 2026-06-09 | 不明 | 同上（news-events） |
| 58 | `emit_platform_config_governance_record.py` | 2026-06-09 | 不明 | 同上（platform-config） |
| 59 | `emit_pnl_attribution_governance_record.py` | 2026-06-08 | 不明 | 同上（pnl-attribution；变体：额外生成治理审计证据包，358 行） |
| 60 | `emit_pnl_by_business_insights_governance_record.py` | 2026-07-18 | 不明 | 同上（pnl-by-business insights；变体：记录字段更多，275 行） |
| 61 | `emit_stock_analysis_governance_record.py` | 2026-06-09 | 不明 | 同上（stock-analysis） |
| 62 | `emit_team_performance_governance_record.py` | 2026-06-09 | 不明 | 同上（team-performance） |
| 63 | `export_livermore_pretrade_check.py` | 2026-05-31 | 常驻 | 导出 Livermore 盘前检查 CSV（运维导出；有未提交改动） |
| 64 | `export_zqtz_adb_rollup_fixture.py` | 2026-07-06 | 一次性 | 导出 ZQTZ 资产债券分类 rollup 测试 fixture |
| 65 | `governed_phase2_preflight.py` | 2026-04-17 | 不明 | governed phase2 API 端点就绪 HTTP 探针（阶段性预检） |
| 66 | `hermes_bridge_server.py` | 2026-05-24 | dev | Hermes 本地桥接 HTTP 服务（agent 协作） |
| 67 | `hermes_team_dispatch_server.py` | 2026-06-08 | dev | Hermes 团队调度 Web 服务（start-hermes-*.ps1 调用） |
| 68 | `home_macro_release_refresh.py` | 2026-07-18 | 常驻 | 首页宏观发布源刷新 operator CLI（task 路径） |
| 69 | `home_macro_release_refresh_timer_preflight.py` | 2026-07-18 | 常驻 | 首页宏观刷新外部 timer 启用前失败关闭（fail-closed）预检 |
| 70 | `ledger_pnl_owner_evidence_packet.py` | 2026-06-08 | 一次性 | 生成 ledger-pnl 业主证据包 |
| 71 | `list_adb_asset_other_breakdown.py` | 2026-05-05 | 一次性 | 列出资产侧 ADB“其他”明细（与 /average-balance 同源加载逻辑） |
| 72 | `local_secret_hygiene_owner_attestation_packet.py` | 2026-06-11 | 不明 | 生成 2026-06-10 本地密钥卫生业主签署包 |
| 73 | `macro_toolkit_freshness_refresh.py` | 2026-08-10 | 常驻 | 宏观工具箱价格/商品新鲜度刷新 CLI（timer 安装脚本调用） |
| 74 | `macro_toolkit_freshness_refresh_timer_preflight.py` | 2026-07-20 | 常驻 | 宏观工具箱 timer 启用前失败关闭预检 |
| 75 | `nbs_gdp_release_preview.py` | 2026-07-18 | 常驻 | 只读预览国家统计局最新季度 GDP 发布 |
| 76 | `osv_reconciliation_gate.py` | 2026-08-07 | 常驻 | OSV 漏洞扫描对账裁决 gate（ci.yml security job） |
| 77 | `pnl_attribution_owner_evidence_packet.py` | 2026-06-08 | 一次性 | 生成 pnl-attribution 业主证据包 |
| 78 | `portfolio_home_blocker_closure_matrix_check.py` | 2026-07-22 | 不明 | portfolio-home blocker 闭环矩阵一致性检查 |
| 79 | `portfolio_home_business_owner_approval_packet.py` | 2026-08-08 | 不明 | portfolio-home 业主审批包生成 |
| 80 | `portfolio_home_closure_artifact_presence_check.py` | 2026-06-08 | 不明 | 闭环工件在位性检查 |
| 81 | `portfolio_home_closure_artifact_summary.py` | 2026-06-08 | 不明 | 闭环工件现状汇总（族内共享库） |
| 82 | `portfolio_home_closure_scorecard.py` | 2026-07-22 | 不明 | 闭环记分卡构建（族内核心） |
| 83 | `portfolio_home_dependency_consistency_check.py` | 2026-06-08 | 不明 | 记分卡依赖一致性检查 |
| 84 | `portfolio_home_evidence_packet_guard.py` | 2026-08-08 | 不明 | 证据包新鲜度/一致性守卫 |
| 85 | `portfolio_home_evidence_snapshot.py` | 2026-08-08 | 不明 | 证据快照生成（哈希锚定） |
| 86 | `portfolio_home_evidence_snapshot_alignment_check.py` | 2026-06-08 | 不明 | 证据快照对齐检查 |
| 87 | `portfolio_home_full_closure_evidence.py` | 2026-07-22 | 不明 | 全闭环证据构建（直连 DuckDB 取数，族内核心库） |
| 88 | `portfolio_home_full_score_preflight.py` | 2026-07-22 | 不明 | 满分闭环预检 |
| 89 | `portfolio_home_krd_contract_decision_export.py` | 2026-08-08 | 不明 | KRD 契约决策导出（csv/json） |
| 90 | `portfolio_home_krd_remap_review_queue.py` | 2026-06-08 | 不明 | KRD 桶重映射评审队列 |
| 91 | `portfolio_home_limit.py` | 2026-06-08 | 不明 | 非负 limit 参数校验小工具（族内共享库） |
| 92 | `portfolio_home_manifest_consistency.py` | 2026-07-22 | 不明 | manifest/docs 路径与合计一致性工具（族内共享库） |
| 93 | `portfolio_home_matured_outstanding_queue.py` | 2026-07-22 | 不明 | 已到期未清偿持仓队列 |
| 94 | `portfolio_home_maturity_remediation_export.py` | 2026-08-08 | 不明 | 到期数据修复队列导出 |
| 95 | `portfolio_home_maturity_remediation_queue.py` | 2026-07-22 | 不明 | 到期数据修复队列构建 |
| 96 | `portfolio_home_owner_action_packet.py` | 2026-08-08 | 不明 | 业主行动包生成 |
| 97 | `portfolio_home_owner_decision_intake_check.py` | 2026-06-08 | 不明 | 业主决策接收一致性检查 |
| 98 | `portfolio_home_owner_handoff_completeness_check.py` | 2026-08-08 | 不明 | 业主交接完整性检查 |
| 99 | `portfolio_home_owner_handoff_packet.py` | 2026-06-08 | 不明 | 业主交接包生成 |
| 100 | `portfolio_home_owner_input_needed_summary.py` | 2026-08-08 | 不明 | 待业主输入事项摘要 |
| 101 | `portfolio_home_risk_warning_consistency.py` | 2026-07-22 | 不明 | 风险警示与数据一致性检查（直连 DuckDB） |
| 102 | `portfolio_home_score_blocker_consistency_check.py` | 2026-06-08 | 不明 | 得分与 blocker 一致性检查 |
| 103 | `portfolio_home_verification_report_guard.py` | 2026-06-08 | 不明 | 验证报告 blocked 状态守卫（纯函数库） |
| 104 | `product_category_pnl_first_certification_packet.py` | 2026-06-08 | 不明 | 产品分类损益首次认证包生成 |
| 105 | `product_category_pnl_owner_decision_packet.py` | 2026-06-08 | 不明 | 产品分类损益业主决策包生成 |
| 106 | `profile_home_snapshot_service.py` | 2026-06-08 | 一次性 | executive home 快照服务性能剖析 |
| 107 | `profile_stock_analysis_workbench.py` | 2026-07-18 | 一次性 | 股票分析工作台性能/内存剖析 |
| 108 | `publish_macro_toolkit_report_bundle.py` | 2026-07-20 | 常驻 | 打包发布宏观工具箱报告资产 bundle |
| 109 | `refresh_calculation_p1_owner_decision_snapshot.py` | 2026-08-07 | 常驻 | 刷新 P1 业主决策快照（审计监控/严格 gate 依赖） |
| 110 | `refresh_direct_app_mcp_gitnexus_tool_surface_snapshot.py` | 2026-06-10 | 常驻 | 刷新直连 App/MCP/GitNexus 工具面快照（审计监控依赖） |
| 111 | `refresh_ledger_pnl_direct_governance_record_snapshot.py` | 2026-06-11 | 常驻 | 刷新 ledger-pnl 直连治理记录快照（审计监控依赖） |
| 112 | `refresh_local_secret_hygiene_snapshot.py` | 2026-06-10 | 常驻 | 刷新本地密钥卫生快照（审计监控依赖） |
| 113 | `refresh_system_audit_monitoring.py` | 2026-08-07 | 常驻 | 系统审计监控快照集刷新主入口（聚合 6 个子快照） |
| 114 | `refresh_tushare_news_backup.py` | 2026-06-03 | 常驻 | Tushare 新闻备份行刷新 operator 入口 |
| 115 | `refresh_tushare_stock_disclosures.py` | 2026-08-06 | 常驻 | Tushare 股票官方披露刷新（task 路径；有未提交改动） |
| 116 | `repair_choice_news_future_dates.py` | 2026-06-07 | 一次性 | 修复 Choice 新闻未来日期脏数据（task 修复函数封装） |
| 117 | `repair_dev_postgres_bootstrap.py` | 2026-04-14 | dev | 修复 dev Postgres/DuckDB 启动漂移（alembic stamp/upgrade） |
| 118 | `repair_livermore_execution_gaps.py` | 2026-08-06 | 常驻 | 修复 Livermore 候选执行历史缺口（task 路径，反复使用） |
| 119 | `repair_pnl_governance_lineage.py` | 2026-04-17 | 一次性 | 修复 PnL 治理血缘记录缺失字段（一次修复） |
| 120 | `run_accounting_asset_movement_refresh.py` | 2026-06-09 | 常驻 | 会计资产变动刷新 operator 入口（task sync 包装） |
| 121 | `run_batch3_stock_strategy_research.py` | 2026-07-06 | 一次性 | batch3 股票策略研究批跑（研究报告已产出） |
| 122 | `run_decimal_precision_backfill.py` | 2026-08-10 | 一次性 | 2026-07-31 钉死日期/批次的 Decimal 精度回填入口 |
| 123 | `run_fable_extension_study.py` | 2026-08-07 | 常驻 | Fable 扩展研究批跑管线（活跃研究，12 个配套测试文件） |
| 124 | `run_global_data_refresh.py` | 2026-08-06 | 常驻 | 规范严格全链路核心金融数据刷新（fail-fast 主运维入口） |
| 125 | `run_livermore_daily_pretrade_refresh.py` | 2026-07-13 | 常驻 | Livermore 日度盘前刷新编排 |
| 126 | `run_matched_baseline_backfill.py` | 2026-07-06 | 常驻 | Livermore 匹配基线对照收益回填（core_finance 路径） |
| 127 | `run_materialize_pipeline_sync.py` | 2026-07-21 | 常驻 | 同步串行执行物化管线 Steps 5.1–5.5（无 Redis/worker） |
| 128 | `run_portfolio_backtest.py` | 2026-07-20 | 常驻 | 组合回测引擎 CLI（core_finance.portfolio_backtest；有未提交改动） |
| 129 | `run_risk_tensor_materialize.py` | 2026-06-09 | 常驻 | 风险张量物化 operator 入口（task actor） |
| 130 | `seed_cycle_rotation_macro.py` | 2026-05-22 | dev | 周期轮动宏观 fixture 种子（dev/test） |
| 131 | `stock_analysis_owner_evidence_packet.py` | 2026-06-22 | 一次性 | 生成 stock-analysis 业主证据包 |
| 132 | `stock_strategy_health_diagnostic.py` | 2026-07-06 | 常驻 | 股票策略候选过滤健康诊断 |
| 133 | `supplement_livermore_after_close_inputs.py` | 2026-07-02 | 常驻 | 收盘后补充 Livermore 输入（Tushare 兜底） |
| 134 | `supply_chain_security_scan.py` | 2026-06-10 | 常驻 | 供应链安全扫描封装（gitleaks/OSV；ci.yml security job） |
| 135 | `sync_livermore_position_snapshot.py` | 2026-05-31 | 常驻 | 将 Livermore 持仓快照滚动到最新 CSI300 交易日 |
| 136 | `system_audit_blocker_intake_board.py` | 2026-06-11 | 常驻 | 系统审计 blocker 接收看板构建（审计监控依赖） |
| 137 | `system_audit_pulse.py` | 2026-08-07 | 常驻 | 系统审计脉搏聚合报告（readiness/coverage 聚合） |
| 138 | `system_audit_strict_gate_matrix.py` | 2026-06-11 | 常驻 | 系统审计严格 gate 矩阵构建（审计监控依赖） |
| 139 | `tushare_news_backup_timer_preflight.py` | 2026-06-08 | 常驻 | Tushare 新闻备份 timer 启用前只读预检 |
| 140 | `validate_risk_exit_rules.py` | 2026-07-06 | 一次性 | 风险退出规则验证（产出 2026-07 验证报告） |
| 141 | `verify_adb_source_coverage.py` | 2026-05-04 | 一次性 | 只读核对快照行数 vs ADB 服务实际加载（2025Q1 排查） |
| 142 | `verify_decimal_precision_backfill.py` | 2026-08-10 | 一次性 | 2026-07-31 Decimal 回填前后只读强校验器 |
| 143 | `verify_portfolio_home_scorecard_commands.py` | 2026-06-08 | 不明 | 执行记分卡验证命令白名单校验（portfolio 族） |
| 144 | `verify_system_audit_completion_snapshot.py` | 2026-08-07 | 常驻 | 系统审计完成快照校验（P1 清单权威源，多脚本依赖） |
| 145 | `verify_system_audit_monitoring_snapshot.py` | 2026-08-07 | 常驻 | 系统审计监控快照校验 |
| 146 | `walk_forward_threshold_scan.py` | 2026-07-06 | 一次性 | walk-forward 阈值扫描（策略研究） |
| 147 | `check_mypy_baseline.py` | （未跟踪） | 常驻 | mypy 错误棘轮 gate：按文件比对 `mypy_baseline.json`，禁止类型债增长（盘点期间由并行技术债任务新增，字母序应列于 #31 之后） |

注：#147 为盘点期间新增，未按字母序插入以避免全表重编号；§8 行数核对按 147 行计。

## 4. 逐脚本盘点 — `backend/scripts/`（13 个）

| # | 脚本 | 最近提交 | 分类 | 用途摘要 |
| ---: | --- | --- | --- | --- |
| 1 | `audit_caliber_violations.py` | 2026-04-21 | 常驻 | 只读扫描 backend 源码中疑似重复口径规则的内联模式，产出 MD/JSON 报告 |
| 2 | `backfill_crisis_score_inputs.py` | 2026-07-20 | 常驻 | 危机评分输入回填（**被 backend/app/tasks 3 处生产 import**） |
| 3 | `backfill_cross_asset_macro_environment.py` | 2026-05-15 | 常驻 | 跨资产宏观环境序列回填（**被 macro_backfill task 生产 import**） |
| 4 | `backfill_formal_balance.py` | 2026-05-04 | 不明 | 扫描快照缺失日期并批量物化 formal 余额（与 #5 功能重叠） |
| 5 | `batch_materialize_balance.py` | 2026-05-04 | 不明 | 按 report_date 批量物化 fact_formal_* 余额（--dry-run/--audit） |
| 6 | `bootstrap_data_pipeline.py` | 2026-06-14 | 常驻 | 一键从 archive XLS 重建 DuckDB 全部物化（灾备/重建入口） |
| 7 | `caliber_violations_summary.py` | 2026-04-21 | 常驻 | 汇总口径违规计数为 CI 漂移基线（caliber CI gate） |
| 8 | `diagnose_adb_coverage.py` | 2026-05-04 | 一次性 | 检查 ADB 页快照 vs 正式表的 report_date 覆盖率 |
| 9 | `diagnose_balance_calibration.py` | 2026-05-04 | 常驻 | 同日 ZQTZ formal 合计 vs 债券分析净价合计对比（生产代码注释指定的标准诊断入口） |
| 10 | `diagnose_balance_diff.py` | 2026-06-02 | 一次性 | 逐行定位快照与 formal 余额差异来源 |
| 11 | `fix_silent_exceptions.py` | 2026-05-04 | 一次性 | 批量替换 `except: pass` 静默异常为 logger.warning（自述一次性） |
| 12 | `probe_choice_treasury_10y_history.py` | 2026-05-04 | 一次性 | 探测 Choice EDB 国债 10Y 历史深度（自述 One-off） |
| 13 | `reconcile_calibers.py` | 2026-04-21 | 不明 | 口径基线 vs 未来规范迁移的占位对账报告（自述 placeholder） |

## 5. 结构性发现

1. **Lifecycle 头注释 0/159**：`grep "Lifecycle:"` 在两个目录均为 0 命中。已在 `scripts/README.md`、`backend/scripts/README.md` 制定强制头部规范（本次新建）。
2. **19 个脚本把 582 KB 的 MCP 单体当库用**：`scripts/mcp/moss_project_mcp.py`（595,844 字节）被 14 个 `emit_*`、`codex_page_readiness.py`、3 个 `*_owner_evidence_packet.py`、`refresh_ledger_pnl_direct_governance_record_snapshot.py` import（主要取 `DEFAULT_GOVERNANCE_DIR` / `page_governance_record_preflight` / `product_page_trace_bundles` / `resolve_path_env` 等少量符号）。任何 import 都要加载整个单体。建议后续任务把这批共享符号拆出为 `scripts/governance_records/` 或 backend 治理库的稳定小模块（本报告只记录，不实施）。
3. **裸 `duckdb.connect` 使用面广**：`scripts/` 顶层 35 个 .py + `backend/scripts/` 7 个 .py 直接 `duckdb.connect`（其中相当一部分为 `read_only=True`，但写路径也有绕过 task 的直接连接，如 `copy_choice_stock_asof_from_duckdb.py`、`backfill_csi300_benchmark_from_backup.py` 等一次性件带治理锁直写）。规范见两个 README：读一律走 `backend/app/repositories/duckdb_repo.py::read_only_connection`，写一律走 `backend/app/tasks` 物化/task write scope。
4. **backend/app 生产代码反向依赖 backend/scripts（层级反转）**：`backend/app/tasks/crisis_score_inputs_refresh.py`、`backend/app/tasks/macro_toolkit_freshness_refresh.py`、`backend/app/tasks/macro_toolkit_write_refresh.py` import `backend.scripts.backfill_crisis_score_inputs`；`backend/app/tasks/macro_backfill.py` import `backend.scripts.backfill_cross_asset_macro_environment`。这两个"脚本"实质是生产库代码，应迁入 `backend/app/tasks/`（列入待办，未在本任务动）。
5. **1 个常驻脚本未进 git**：`scripts/choice_stock_daily_refresh.py` 与 `scripts/install_choice_stock_daily_refresh_timer.ps1` 均为未跟踪状态，但后者是 Windows 计划任务安装入口且引用前者——存在"计划任务依赖不在版本库"的运维风险，建议尽快提交。
6. **脚本-测试强配对**：约 140+ 个 `tests/test_*.py` 直接 import `scripts.*` 或 `backend.scripts.*`。任何归档移动都会破坏配对测试，必须连同测试一起移动/退役（见 §6 执行注意事项）。
7. **家族同构堆积**：`portfolio_home_*` ×26、`emit_*` ×14、`check_*_business_owner_approval` ×9 三个家族占 49/159 ≈ 31%，都是"每页复制一份"的模板繁殖模式。emit 族收敛方案见 §7；portfolio_home 族建议闭环后整族归档而非重构。

## 6. 归档建议清单（供人工批准后执行）

> 执行约定：目标目录 `scripts/archive/<主题-日期>/` 与 `backend/scripts/archive/`；移动使用 `git mv`（由人工执行，本任务禁止 git 写操作）；每移动一个脚本，其配套测试同步移动到 `tests/archive/`（或直接退役删除，由批准人决定）；移动后跑一次全量 pytest 收集（`pytest --collect-only`）确认无 import 断裂。

### 批次 1 — 建议立即归档（一次性已完成，32 个，风险低）

| 目标目录 | 脚本 | 配套测试（需同步处理） |
| --- | --- | --- |
| `scripts/archive/adb-recon-2026-05/` | `_run_diagnose_adb_other.py`（连同 `diagnose_adb_liabilities_other.sql`）、`compare_formal_snapshot_adb_sources.py`、`diff_zqtz_formal_vs_snapshot.py`、`verify_adb_source_coverage.py`、`list_adb_asset_other_breakdown.py` | 未发现配套测试 |
| `backend/scripts/archive/adb-recon-2026-05/` | `diagnose_adb_coverage.py`、`diagnose_balance_diff.py` | 未发现配套测试 |
| `scripts/archive/strategy-research-2026-07/` | `diagnose_entry_premium.py`、`diagnose_gate_state_flips.py`、`diagnose_macro_multiplier.py`、`diagnose_overheat_holdings.py`、`run_batch3_stock_strategy_research.py`、`walk_forward_threshold_scan.py`、`validate_risk_exit_rules.py` | `test_entry_premium_diagnostic.py`、`test_gate_state_flip_diagnostic.py`、`test_macro_multiplier_diagnostic.py`、`test_overheat_holdings_diagnostic.py`、`test_batch3_stock_strategy_research.py`、`test_walk_forward_threshold_scan.py` |
| `scripts/archive/decimal-backfill-2026-07-31/` | `run_decimal_precision_backfill.py`、`verify_decimal_precision_backfill.py` | `test_decimal_precision_backfill.py`、`test_decimal_precision_backfill_verifier.py` |
| `scripts/archive/one-off-repairs/` | `repair_choice_news_future_dates.py`、`repair_pnl_governance_lineage.py`、`copy_choice_stock_asof_from_duckdb.py`、`backfill_csi300_benchmark_from_backup.py` | `test_pnl_governance_lineage_repair.py`、`test_choice_stock_asof_copy.py`、`test_csi300_benchmark_backfill.py`（`repair_choice_news_future_dates` 相关断言在 `test_choice_news_query.py` 内，需拆分处理） |
| `backend/scripts/archive/one-off-repairs/` | `fix_silent_exceptions.py`、`probe_choice_treasury_10y_history.py` | 未发现配套测试 |
| `scripts/archive/perf-profiling/` | `profile_home_snapshot_service.py`、`profile_stock_analysis_workbench.py` | 未发现配套测试 |
| `scripts/archive/page-closure-evidence-2026-06/` | `average_balance_live_smoke_evidence.py`、`bond_analysis_live_smoke_evidence.py`、`average_balance_owner_evidence_packet.py`、`bond_analysis_owner_evidence_packet.py`、`ledger_pnl_owner_evidence_packet.py`、`pnl_attribution_owner_evidence_packet.py`、`stock_analysis_owner_evidence_packet.py`、`export_zqtz_adb_rollup_fixture.py` | `test_average_balance_live_smoke_evidence.py`、`test_bond_analysis_live_smoke_evidence.py`、`test_average_balance_owner_evidence_packet.py`、`test_bond_analysis_owner_evidence_packet.py`、`test_ledger_pnl_owner_evidence_packet.py`、`test_pnl_attribution_owner_evidence_packet.py`、`test_stock_analysis_owner_evidence_packet.py` |

注意：3 个 owner_evidence_packet 脚本 import 对应 `emit_*`，归档它们不影响 emit 族；但若批次 1 先行、§7 收敛后再归档 emit 族，顺序上无冲突。

### 批次 2 — 条件归档（状态不明，53 个，需业务确认收口）

| 触发条件 | 归档对象 | 目标目录 |
| --- | --- | --- |
| portfolio-home 业主审批闭环正式签署后 | `portfolio_home_*` ×26 + `check_portfolio_home_business_owner_approval.py` + `verify_portfolio_home_scorecard_commands.py`（28 个）及 20+ 个 `tests/test_portfolio_home_*.py` | `scripts/archive/portfolio-home-closure-2026-05-31/` |
| 2026-06-10 系统审计 P1 决策流程全部关闭（`refresh_system_audit_monitoring` 显示无 open P1）后 | `calculation_p1_owner_decision_packet.py`、`calculation_p1_owner_meeting_checklist.py`、`calculation_p1_post_owner_execution_plan.py`、`calculation_p1_first_priority_readiness_packet.py`、`local_secret_hygiene_owner_attestation_packet.py`、`governed_phase2_preflight.py` | `scripts/archive/system-audit-2026-06-10/` |
| §7 emit 收敛方案落地并双跑对比通过后 | `emit_*_governance_record.py` ×14 及 14 个配套测试 | `scripts/archive/governance-records-legacy/` |
| product-category-pnl 认证流程收口后 | `product_category_pnl_first_certification_packet.py`、`product_category_pnl_owner_decision_packet.py` | `scripts/archive/page-closure-evidence-2026-06/` |
| 与 `batch_materialize_balance.py` 二选一（功能重叠，建议保留带 --dry-run/--audit 的后者） | `backend/scripts/backfill_formal_balance.py` | `backend/scripts/archive/` |
| 口径规范迁移方案落地后 | `backend/scripts/reconcile_calibers.py` | `backend/scripts/archive/` |

### 不动清单（75 个）

- 常驻工具 69 个（§3/§4 标"常驻"者）：CI/timer/dev gate/生产 import/活跃运维入口。
- dev 编排 6 个：`bootstrap_kpi_postgres.py`、`dev_postgres_cluster.py`、`hermes_bridge_server.py`、`hermes_team_dispatch_server.py`、`repair_dev_postgres_bootstrap.py`、`seed_cycle_rotation_macro.py`。
- 另：`backend/scripts/backfill_crisis_score_inputs.py` 与 `backfill_cross_asset_macro_environment.py` 虽是"常驻"，但正确归宿是迁入 `backend/app/tasks/`（消除 app→scripts 反向依赖），属独立重构任务，不在归档清单内。

## 7. `emit_*` 14 个同构脚本收敛方案（仅设计，不实现）

### 现状画像

- 14 个脚本合计 ≈ 2,433 行；12 个标准形各 140–159 行，2 个变体（`emit_pnl_attribution` 358 行：额外生成治理审计证据包并注入 approval status；`emit_pnl_by_business_insights` 275 行：记录字段更多）。
- 每个标准形的结构完全一致：`PAGE_SLUG`/`TARGET_STREAM` 常量 → `build_record(created_at)` 返回页面专属静态 dict → `build_payload()`（除 scope/disclaimer/evidence_scope 文案外逐行相同）→ 6 个逐字节相同的工具函数（`record_key`、`records_share_key`、`find_existing_record_line`、`emit_record`、`default_created_at`、`main`）。即每个脚本真正的"页面差异"只有 ~40 行数据，其余 ~110 行是复制的引擎代码。
- 全部依赖 `scripts.mcp.moss_project_mcp` 的 4 个符号（`DEFAULT_GOVERNANCE_DIR`、`page_governance_record_preflight`、`product_page_trace_bundles`、`resolve_path_env`）；变体另用 `page_governance_audit_evidence_packet`、`DEFAULT_DUCKDB_PATH`。
- 14 个配套测试（`tests/test_*_governance_record.py`）逐个 import 各脚本的 `build_record`/`build_payload`。
- 下游消费者：`average_balance_owner_evidence_packet.py`、`ledger_pnl_owner_evidence_packet.py`、`pnl_attribution_owner_evidence_packet.py`、`refresh_ledger_pnl_direct_governance_record_snapshot.py` import 其中 3 个脚本的符号。

### 目标形态：单入口 + 数据化页面规格

```text
scripts/
  emit_page_governance_record.py          # 唯一 CLI 入口
  governance_records/
    __init__.py
    engine.py                             # 共享引擎（现 6 个工具函数 + 通用 build_payload + main 骨架）
    registry.py                           # PAGE_SPECS: dict[str, PageRecordSpec]，14 页注册于此
    specs/
      average_balance.py                  # 每页一个 spec 模块：record 字段、disclaimer、evidence_scope
      ...（14 个，纯数据 + 可选钩子）
```

- **CLI 契约**：`python scripts/emit_page_governance_record.py --page <slug> [--write] [--governance-dir DIR] [--created-at TS]`；`--list-pages` 列出注册页；`--all --dry-run` 支持全页批量预检。退出码保持现有语义（preflight 非 `ready_for_audit_review` → 1），JSON 输出结构与现脚本完全一致。
- **PageRecordSpec**（dataclass，frozen）：`page_slug`、`target_stream`、`build_record(created_at, **evidence) -> dict`、`disclaimer: str`、`evidence_scope: dict`、`extra_cli_args: tuple`（如 pnl_attribution 的 `--duckdb-path`/`--audit-packet-path`）、`post_payload_hook: Callable | None`（pnl_attribution 的审计证据包在此钩子内实现，仅该 spec 启用）。
- **幂等语义不变**：`record_key`（page_id/primary_api/report_date/cache_key 四元组）、`already_exists`/`pending_append`/`appended` 状态机、`sort_keys=True, ensure_ascii=False` 序列化行为逐字节保持——这是治理追加流（`cache_manifest.jsonl`）的对外契约，收敛期间**严禁顺手修改任何 record 内容**。
- **测试收敛**：14 个测试合并为 1 个 registry 驱动的参数化 `tests/test_page_governance_records.py`（`@pytest.mark.parametrize("slug", PAGE_SPECS)`），逐页断言必填字段、preflight ready、幂等语义；变体钩子单独加 2 个用例。
- **MCP 单体解耦（顺带收益）**：19 处 `scripts.mcp.moss_project_mcp` import 收敛为 `governance_records/engine.py` 一处；后续拆库任务只需改一个文件。

### 迁移步骤（人工批准后分四步）

1. 落地 `engine.py + registry.py + specs/`，14 页 spec 从旧脚本机械搬运（不改内容）。
2. **双跑对比**：对 14 页分别执行旧脚本与新入口的 dry-run，`diff` JSON 输出（剔除 `created_at`）必须逐字节一致，留存对比工件。
3. 切换 4 个下游消费者的 import 到 registry/engine；新参数化测试上线、旧 14 个测试退役。
4. 旧 14 个脚本 `git mv` 至 `scripts/archive/governance-records-legacy/`（对应 §6 批次 2）。

### 风险

- emit 是治理写路径（追加 `data/governance/cache_manifest.jsonl`），双跑对比必须在 dry-run 模式完成，不得为验证而真实追加记录。
- `emit_ledger_pnl` 的 `PAGE_SLUG`/`TARGET_STREAM`/`build_payload`/`build_record` 被快照脚本按名 import，切换时需保留等价导出或同步修改调用点。

## 8. 验证：盘点行数 = 实际脚本数

- 实际脚本数：`scripts/*.py` = 147（含 2 个未跟踪：`choice_stock_daily_refresh.py`、`check_mypy_baseline.py`），`backend/scripts/*.py` = 13，合计 160。
- 本报告逐脚本表行数：§3 表 147 行 + §4 表 13 行 = 160 行，与实际一致。
- 复核命令（PowerShell，仓库根目录）：

```powershell
(Get-ChildItem scripts -Filter *.py -File).Count        # 147
(Get-ChildItem backend/scripts -Filter *.py -File).Count # 13
# 报告表行数（去除表头与分隔行）：
(Select-String -Path docs/plans/tech-debt-remediation/C5-scripts-inventory.md -Pattern '^\| +\d+ \|').Count  # 160
```

> 本仓库有多个并行技术债任务在产出脚本；若复核时数量再次漂移，先 `git status --porcelain -- scripts backend/scripts` 找出新增文件，再增补表行。
