# D3 — 本地分支与工作树全量盘点（只读报告）

- 日期：2026-08-12（30 天线：最后提交日期 ≤ 2026-07-12 记为「>30 天」）
- 基准：`codex/V1` @ `9a5afbb2`（规划状态唯一写入点；盘点排除该分支自身）
- 范围：本地分支 248 支（盘点 247）；注册工作树 83 个
- 性质：**纯只读盘点**。本报告不执行任何 `branch -d/-D`、`worktree remove/prune`、`checkout`；文中命令全部为模板，须经 owner 裁决后分批人工执行。
- 采集方法（可复现）：
  - 分支基础数据：`git for-each-ref refs/heads --format='%(refname:short)|%(objectname:short)|%(committerdate:short)'`
  - ahead 数：逐支 `git rev-list --count codex/V1..<branch>`（247 支批量脚本执行）
  - 全合并交叉验证：`git branch --merged codex/V1` 输出与 ahead==0 集合**完全一致**（11 支）
  - 工作树：`git worktree list --porcelain` 逐项解析；对每个存在的目录在其目录下执行 `git -C <path> status --porcelain` 计数；抽样 4 个（含 archive 区 detached、C:/tmp、.codex 临时区）复核退出码均为 0，「0 脏条目」为真实干净而非报错吞没
  - detached HEAD 归属：逐个 `git merge-base --is-ancestor <sha> codex/V1` + `git branch --contains <sha>`
- 快照说明：主工作树脏条目数在采集窗口内由 644 漂移至 651（本仓库正有并行技术债任务写入产物）；本报告按首次扫描 644 记，量级与结论不受影响。处置执行前应重跑清单核对。

## 1. 统计总览

分支（247 支，排除 codex/V1）：

| 分类 | 数量 | 说明 |
| --- | ---: | --- |
| a) 可安全删除（全合并且最后活动 >30 天） | **0** | 全合并共 11 支，但最早活动为 2026-07-16，无一满足 >30 天 |
| a′) 全合并但活动 ≤30 天（暂缓，到期后即为 a 类） | **10** | 3 支 2026-08-19 起、7 支 2026-09-07/08/10 起满足口径（§3） |
| b) 参考保留（锚点 / phase / archive / 主线） | **10** | 含 STATE.md 2026-07-20 指名锚点 3 支（§4） |
| c) 待 owner 裁决（有独有提交） | **227** | 按 11 个主题批次分组（§5） |

工作树（83 个）：

| 指标 | 数量 | 说明 |
| --- | ---: | --- |
| 注册总数 | 83 | 2026-07-20 记录为 72，其后净增 11（08-06 ~ 08-09 批次） |
| 目录缺失（missing / prunable） | **0** | 全部 `Test-Path` 存在，porcelain 无 prunable 标注，无需 `worktree prune` |
| 脏工作树 | **1** | 仅主工作树 F:/MOSS-V3（644 条：M 414 / ?? 226 / D 11；热点 frontend/tests/backend/docs/scripts） |
| detached 工作树 | 24 | 其中 19 个位于 G:/MOSS-V3-worktrees-archive；仅 2 个 HEAD 为真孤儿提交（§6.3） |
| 分支绑定工作树 | 59 | 含主工作树（codex/V1）；58 个非主工作树全部干净 |

与既有认知的差异：

- **「约 11 个工作树含未提交改动」已不成立**：2026-08-09 的 `dirty-*` / `recover-*` 收编批次（对应 §5 C11 组 10 支分支）已把散落脏改动提交成分支，当前 82 个非主工作树全部干净。脏改动现在只集中在主工作树。
- **「全合并可删约 11 支」数量吻合**（全合并恰好 11 支），但其中 1 支是 Phase 02 锚点（保留），且无一满足「>30 天」，故本期 a 类为 0，10 支进入 a′ 暂缓窗口。

## 2. 分类口径

- **a（可安全删除）**：`rev-list --count codex/V1..分支 == 0` 且最后提交 ≤ 2026-07-12。本期为空集。
- **a′（全合并暂缓）**：全合并但活动 ≤30 天。不立即删除，到期复查后作为第一删除批次；表内给出各支满足口径的最早日期。
- **b（参考保留）**：满足其一——① STATE.md 2026-07-20 决策指名（`codex/phase-02-exact-cutoff` 锚点、`codex/pnl-bridge-date-closure` superseded 参考、`codex/phase-03-incremental-rebuild` reference-only）；② 名称含 phase 特征；③ archive-* 归档分支及历史主线 `main`（虽有独有提交，但按用途归入保留，不进入裁决删除流）。
- **c（待 owner 裁决）**：有独有提交（ahead > 0）且不属于 b。按最后活动日期与主题分为 C1 ~ C11 组。
- 与 2026-07-20 决策口径一致：逐支 `rev-list` 验证、**不做 bulk delete**、锚点分支不删。

## 3. a′ — 全合并分支（10 支，暂缓删除）

全部满足 `git branch --merged codex/V1` 与 `rev-list --count == 0` 双重验证。「工作树」列为占用该分支的工作树（删除分支前必须先移除）。

| 分支 | tip | 最后提交 | ahead | 工作树占用 | 满足 >30 天日期 |
| --- | --- | --- | ---: | --- | --- |
| codex/development-audit-remediation | f3aa1e33 | 2026-07-18 | 0 | 无 | 2026-08-18 |
| codex/balance-analysis-date-closure | 982154c4 | 2026-07-19 | 0 | 无 | 2026-08-19 |
| codex/ledger-pnl-auth-closure | ad5c2ca7 | 2026-07-19 | 0 | 无 | 2026-08-19 |
| codex/agent-runtime-reslice-20260806 | 20d5a93b | 2026-08-07 | 0 | G:/MOSS-V3-worktrees/agent-runtime-reslice-20260806 | 2026-09-07 |
| codex/mobile-subnav-visibility-fix-20260807 | 20d5a93b | 2026-08-07 | 0 | G:/MOSS-V3-worktrees/mobile-subnav-visibility-fix-20260807 | 2026-09-07 |
| codex/agent-governance-consistency-20260808 | 5f985f91 | 2026-08-08 | 0 | G:/MOSS-V3-worktrees/agent-governance-consistency-20260808 | 2026-09-08 |
| codex/full-workspace-final-20260808 | 98401154 | 2026-08-08 | 0 | G:/MOSS-V3-worktrees/full-workspace-final-20260808 | 2026-09-08 |
| codex/full-workspace-integration-20260806 | a60f7944 | 2026-08-08 | 0 | G:/MOSS-V3-worktrees/full-workspace-integration-20260806 | 2026-09-08 |
| codex/full-workspace-verification-20260808 | 98401154 | 2026-08-08 | 0 | G:/MOSS-V3-worktrees/full-workspace-verification-20260808 | 2026-09-08 |
| codex/decimal-precision-backfill-clean-00231b13a | 00231b13 | 2026-08-10 | 0 | 无 | 2026-09-10 |

同 tip 说明：full-workspace-final 与 full-workspace-verification 同指 `98401154`；agent-runtime-reslice 与 mobile-subnav-visibility-fix 同指 `20d5a93b`。

## 4. b — 参考保留（10 支）

| 分支 | tip | 最后提交 | ahead | 保留理由 |
| --- | --- | --- | ---: | --- |
| codex/phase-02-exact-cutoff | f791b049 | 2026-07-16 | 0 | STATE.md 2026-07-20 指名：Phase 02 命名锚点（虽全合并仍保留） |
| codex/phase-03-incremental-rebuild | ad28d974 | 2026-07-18 | 6 | STATE.md：Phase 03 技术完成但业务未采纳，reference-only |
| codex/pnl-bridge-date-closure | f70a536c | 2026-07-19 | 1 | STATE.md：superseded（PAGE-BRIDGE-001 相反裁定），仅作参考 |
| codex/phase1-closeout-clean | 388e3090 | 2026-04-11 | 1 | 名称含 phase：Phase 1 收尾快照 |
| codex/frontend-product-category-audit-phase1 | 2aed9a0c | 2026-04-12 | 1 | 名称含 phase：phase1 审计快照 |
| codex/governed-phase2-preflight | 73a93ac7 | 2026-04-17 | 1 | 名称含 phase：Phase 2 预检快照 |
| codex/phase2-cutoff-closeout | cfb8cf32 | 2026-04-18 | 19 | 名称含 phase：Phase 2 cutoff 收尾快照 |
| main | 8b5c0379 | 2026-07-15 | 16 | 历史主线（重置前 main），非清理对象；如需收纳建议打 tag 归档而非删除 |
| codex/archive-main-ahead-2026-04-25 | 21d61e14 | 2026-04-25 | 3 | 显式归档分支（与下一支同 tip） |
| codex/archive-main-before-reset-2026-04-25 | 21d61e14 | 2026-04-25 | 3 | 显式归档分支：main 重置前快照 |

## 5. c — 待 owner 裁决（227 支，按批次分组）

「工作树」列 ✔ 表示该分支当前被某工作树 checkout（删除前须先 `worktree remove`）。

### C1 — 2026-04 月批次（37 支，>100 天无活动，最早裁决候选）

04-11 ~ 04-19（6 支）：

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| batch-a-bond-hardening | 4abb5849 | 2026-04-11 | 1 | |
| batch-b-agent-closeout | 29d52782 | 2026-04-11 | 1 | |
| batch-c-market-data | 9f8e23ac | 2026-04-11 | 2 | |
| codex/adb-research-foundation | 918deb94 | 2026-04-16 | 1 | |
| codex/pnl-runtime-registry-alignment | ca46fd68 | 2026-04-17 | 1 | |
| codex/review-findings-remediation | ea1624c0 | 2026-04-19 | 1 | |

04-25 批次（17 支，page-*/backend-*/docs-*/frontend-*）：

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/backend-calendar-ncd-proxy-chain | cc18cdd7 | 2026-04-25 | 1 | |
| codex/backend-executive-balance-semantics | cb8fb053 | 2026-04-25 | 1 | |
| codex/backend-macro-bond-linkage-research-views | 08070939 | 2026-04-25 | 1 | |
| codex/backend-runtime-coercion-hardening | 4da019e6 | 2026-04-25 | 1 | |
| codex/backend-tushare-token-boundary | 8fe18e96 | 2026-04-25 | 1 | |
| codex/docs-boundary-governance | 39f08290 | 2026-04-25 | 1 | |
| codex/docs-current-state-golden-evidence | b065e6e0 | 2026-04-25 | 1 | |
| codex/frontend-calendar-proxy-consumers | 8b326f11 | 2026-04-25 | 8 | |
| codex/frontend-calendar-proxy-consumers-backend-first-backup | 1a62ff10 | 2026-04-25 | 9 | |
| codex/frontend-calendar-proxy-consumers-stacked-backup | 0c46fce4 | 2026-04-25 | 6 | |
| codex/frontend-news-digest-preview-stability | 4ba53890 | 2026-04-25 | 3 | |
| codex/page-balance-analysis-model | 996684a2 | 2026-04-25 | 1 | |
| codex/page-cashflow-projection-model | dbe3c726 | 2026-04-25 | 1 | |
| codex/page-cross-asset-workbench | a6c95508 | 2026-04-25 | 5 | |
| codex/page-cross-asset-workbench-stacked-backup | e6e29751 | 2026-04-25 | 5 | |
| codex/page-decision-items-workbench | f12fb34c | 2026-04-25 | 1 | |
| codex/page-product-category-pnl-model | 328afebd | 2026-04-25 | 1 | |

04-26 ~ 04-29（14 支，split 批次 + 收尾）：

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/market-data-category-closure | 0dd1fb68 | 2026-04-26 | 4 | |
| codex/page-risk-tensor-frontend | 3e28b662 | 2026-04-26 | 7 | |
| codex/product-category-ytd-clean | 08f6c5ae | 2026-04-27 | 1 | |
| codex/split-balance-movement-fullstack | 3f3d02fe | 2026-04-27 | 1 | |
| codex/split-core-finance-rate-math-semantics | 04842bcc | 2026-04-27 | 1 | |
| codex/split-dev-keepalive-scripts | 59245cb3 | 2026-04-27 | 1 | |
| codex/split-liability-analytics-asset-scope-ui | bc03658f | 2026-04-27 | 1 | |
| codex/split-operations-contribution-summary | 283caf3e | 2026-04-27 | 1 | |
| codex/split-product-category-ftp-scenario | 9b6dfde3 | 2026-04-27 | 1 | |
| codex/split-snapshot-zqtz-grain | ba2e8fca | 2026-04-27 | 1 | |
| codex/agent-payload-contract-fix | eac18661 | 2026-04-29 | 1 | |
| codex/automation-gate-overview | 77836f06 | 2026-04-29 | 1 | |
| codex/workbench-components-closure | d264f19a | 2026-04-29 | 1 | |
| codex/workspace-closeout-followups | 6ff832b7 | 2026-04-29 | 2 | |

### C2 — 2026-05 月零散（5 支）

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| fix/02-rate-unit-heuristic | 8e46e16e | 2026-05-05 | 1 | |
| feat/stock-analysis-stage2-3-mvp | 5cba582b | 2026-05-08 | 1 | |
| codex/dashboard-cockpit-real-data-p1-split | fe06c2b6 | 2026-05-24 | 11 | |
| codex/macro-toolkit-core-split | 08286359 | 2026-05-24 | 1 | |
| codex/dashboard-cockpit-visual-polish | 56200de1 | 2026-05-26 | 2 | |

### C3 — 2026-06 上旬功能/页面批次（16 支，06-01 ~ 06-04）

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/pr4-review-fix | bf7fc43b | 2026-06-01 | 1 | |
| codex/stock-analysis-candidate-cold-path | 8ab10608 | 2026-06-01 | 1 | |
| codex/market-home-cache-warmup | f1349e14 | 2026-06-02 | 1 | |
| codex/product-category-account-drilldown | 3d2e8701 | 2026-06-02 | 4 | |
| codex/product-category-operating-analysis | 5c6b92aa | 2026-06-02 | 3 | |
| codex/readable-text-sql-guard | fae5b4f3 | 2026-06-02 | 2 | |
| codex/risk-tensor-governance-guard | bf8c6c10 | 2026-06-02 | 1 | |
| codex/system-sources-frame-cache | e97efc40 | 2026-06-02 | 1 | |
| codex/agent-eval-scaffold | 68138026 | 2026-06-03 | 1 | |
| codex/frontend-node-tsconfig-build | b7e48ad5 | 2026-06-03 | 4 | |
| codex/macro-toolkit-shadow-frontend | 596fab10 | 2026-06-03 | 2 | |
| codex/macro-toolkit-shadow-scripts | 4040acca | 2026-06-03 | 1 | |
| codex/market-overview-perf-clean | 4f917e5f | 2026-06-03 | 1 | |
| codex/risk-tensor-page-lineage | 4bef804b | 2026-06-03 | 1 | |
| codex/stock-analysis-error-localization | 180c73f7 | 2026-06-03 | 1 | |
| codex/home-startup-bundle | 0398e833 | 2026-06-04 | 7 | |

### C4 — meta-status / closure / aggrid 批次（21 支，2026-06-05，ahead 多为 9）

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/bond-dashboard-meta-status | f3bc6ed4 | 2026-06-05 | 9 | |
| codex/cross-asset-meta-status | 8c5aeda4 | 2026-06-05 | 9 | |
| codex/cube-query-meta-status | ae1371b0 | 2026-06-05 | 9 | |
| codex/decision-items-meta-status | d9466eea | 2026-06-05 | 9 | |
| codex/ledger-pnl-meta-status | c59036f8 | 2026-06-05 | 9 | |
| codex/liability-meta-status | 89050148 | 2026-06-05 | 9 | |
| codex/market-data-meta-status | df61aaa2 | 2026-06-05 | 9 | |
| codex/operations-analysis-meta-status | 0c2cea3d | 2026-06-05 | 9 | |
| codex/pnl-attribution-meta-status | fa8aa97f | 2026-06-05 | 9 | |
| codex/positions-meta-status | 6b9753e6 | 2026-06-05 | 9 | |
| codex/macro-observation-readable | f5c154a9 | 2026-06-05 | 9 | |
| codex/next-page-closure | b4287f67 | 2026-06-05 | 9 | |
| codex/pnl-bridge-state-closure | 1c64430b | 2026-06-05 | 9 | |
| codex/pnl-state-closure | 164f5445 | 2026-06-05 | 9 | |
| codex/risk-tensor-status-closure | f39d3ee8 | 2026-06-05 | 9 | |
| codex/ag-grid-owner-inventory-guard | 2147b034 | 2026-06-05 | 12 | |
| codex/fix-aggrid-institutional-selector | 9e50457b | 2026-06-05 | 10 | |
| codex/fix-formal-pnl-aggrid-selector | 140d6c14 | 2026-06-05 | 11 | |
| codex/home-startup-aggrid-clean | f365885b | 2026-06-05 | 1 | |
| codex/home-startup-aggrid-system-pr | fa55a021 | 2026-06-05 | 9 | |
| codex/home-startup-aggrid-system-review | fa55a021 | 2026-06-05 | 9 | |

同 tip：home-startup-aggrid-system-pr 与 -review 同指 `fa55a021`。

### C5 — recovery 批次（37 支，2026-06-06 / 06-07，ahead 13~15）

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/recovery-dirty-worktree-20260606-b | 104b2732 | 2026-06-06 | 13 | |
| codex/recovery-hermes-team-dispatch-20260607 | 104b2732 | 2026-06-06 | 13 | |
| codex/recovery-page-readiness-scripts-20260607 | 104b2732 | 2026-06-06 | 13 | |
| codex/recovery-readiness-reports-20260607 | 104b2732 | 2026-06-06 | 13 | |
| codex/recovery-tushare-timer-ops-packet-20260607 | 104b2732 | 2026-06-06 | 13 | |
| codex/recovery-agent-toolset-policy-20260607 | 24a313a3 | 2026-06-07 | 14 | |
| codex/recovery-auth-dev-read-bypass-20260607 | 7d37e66b | 2026-06-07 | 14 | |
| codex/recovery-balance-movement-20260606 | 5ea29d77 | 2026-06-07 | 14 | |
| codex/recovery-bond-analysis-20260606 | 774e73cc | 2026-06-07 | 14 | |
| codex/recovery-cashflow-projection-20260606 | d1d5d43a | 2026-06-07 | 14 | |
| codex/recovery-choice-news-events-20260606 | 8254f38c | 2026-06-07 | 14 | |
| codex/recovery-commodity-trade-date-normalize-20260607 | b2ff43a8 | 2026-06-07 | 14 | |
| codex/recovery-concentration-monitor-20260606 | f01de9e9 | 2026-06-07 | 14 | |
| codex/recovery-core-finance-test-cleanup-20260607 | 2c70e95b | 2026-06-07 | 14 | |
| codex/recovery-dashboard-live-route-20260606 | 42e4e984 | 2026-06-07 | 14 | |
| codex/recovery-data-readiness-report-20260607 | b9c4732a | 2026-06-07 | 14 | |
| codex/recovery-dev-worker-runner-20260607 | bdfd7a3c | 2026-06-07 | 14 | |
| codex/recovery-external-data-service-boundary-20260607 | 98971998 | 2026-06-07 | 14 | |
| codex/recovery-gitignore-temp-output-20260607 | c8ef6f35 | 2026-06-07 | 14 | |
| codex/recovery-health-20260607 | 95744d90 | 2026-06-07 | 14 | |
| codex/recovery-hermes-agent-team-launcher-20260607 | 973c20ed | 2026-06-07 | 14 | |
| codex/recovery-kpi-team-performance-20260607 | 616d83e4 | 2026-06-07 | 14 | |
| codex/recovery-ledger-pnl-20260606 | b535a20f | 2026-06-07 | 14 | |
| codex/recovery-liability-adb-balance-20260606 | afedbf1f | 2026-06-07 | 14 | |
| codex/recovery-macro-vendor-refresh-status-20260607 | 7ed9df70 | 2026-06-07 | 14 | |
| codex/recovery-numeric-years-unit-20260607 | 59a536c3 | 2026-06-07 | 14 | |
| codex/recovery-pnl-attribution-20260606 | 3a0c93fc | 2026-06-07 | 14 | |
| codex/recovery-pnl-by-business-adb-zero-20260607 | af20fd2f | 2026-06-07 | 14 | |
| codex/recovery-portfolio-home-20260606 | f49c675f | 2026-06-07 | 14 | |
| codex/recovery-product-category-pnl-20260606 | 756955d1 | 2026-06-07 | 14 | |
| codex/recovery-qdb-gl-monthly-analysis-20260606 | 3a94c9a6 | 2026-06-07 | 14 | |
| codex/recovery-result-meta-cache-key-20260606 | f3b3f9a7 | 2026-06-07 | 14 | |
| codex/recovery-risk-tensor-20260607 | f867e2fa | 2026-06-07 | 14 | |
| codex/recovery-source-preview-idempotency-20260607 | ddf762a3 | 2026-06-07 | 14 | |
| codex/recovery-stock-analysis-20260606 | 6f99ff53 | 2026-06-07 | 14 | |
| codex/recovery-tushare-preflight-status-20260607 | 11a40e65 | 2026-06-07 | 14 | |
| codex/recovery-tushare-timer-ops-packet-on-preflight-20260607 | 441b1b27 | 2026-06-07 | 15 | |

同 tip：`104b2732` 被 5 支 recovery 分支共享（首 5 行），裁决时可合并处理。

### C6 — 2026-06 中下旬零散（8 支，06-07 ~ 06-20）

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/homepage-p0-hardening | aacf3b70 | 2026-06-07 | 2 | |
| codex/homepage-p0-ralph | 4179a6ef | 2026-06-07 | 1 | |
| codex/product-category-pnl-spread-clean | 8ba10be8 | 2026-06-09 | 18 | |
| codex/system-audit-remediation-local-stack-20260610 | 924dc50c | 2026-06-11 | 4 | |
| fix/module-home-risk-adapter-baseline | 8ce34eca | 2026-06-20 | 2 | |
| ui/audit-range-gate | a5d8e6b3 | 2026-06-20 | 1 | |
| ui/audit-range-gate-on-risk-fix | 7a06173d | 2026-06-20 | 11 | |
| ui/polish-kpi-decision-surfaces | 82f6a5b4 | 2026-06-20 | 12 | |

### C7 — 2026-07 月批次（11 支，07-05 ~ 07-30）

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/lane-a-return-10d-build-unblock | aef9813a | 2026-07-05 | 2 | |
| codex/frontend-dependency-slim-round2 | ff165641 | 2026-07-16 | 2 | |
| codex/development-audit-integration | fa320659 | 2026-07-19 | 1 | |
| macro/observation-wiring-v1 | 10530693 | 2026-07-19 | 7 | |
| codex/macro-freshness-hardening | 569dc90c | 2026-07-20 | 1 | |
| codex/risk-tensor-v6-maturity | f801baf3 | 2026-07-23 | 20 | |
| codex/dual-frequency-amount-coverage | f9a9f3d2 | 2026-07-28 | 2 | |
| codex/dual-frequency-blocker-fixes | c0226d58 | 2026-07-28 | 1 | ✔ |
| codex/dual-frequency-input-contract | c7ff303a | 2026-07-28 | 3 | ✔ |
| codex/v1-main-integration | 02b19619 | 2026-07-29 | 6 | ✔ |
| codex/market-data-submit-ready | a43347c5 | 2026-07-30 | 1 | ✔ |

### C8 — 2026-08-04 / 08-05 recovery 边缘批次（7 支）

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/f1-api-task-boundary | 4c98ebbb | 2026-08-04 | 2 | |
| codex/market-overview-contract | 8e1034bf | 2026-08-04 | 3 | |
| codex/precleanup-773-split-seed | a9cb2f2e | 2026-08-04 | 1 | |
| codex/recovery-choice-review-15193ff3 | 15193ff3 | 2026-08-04 | 13 | |
| codex/recovery-accounting-52661186 | 52661186 | 2026-08-05 | 38 | |
| codex/recovery-macro-figma-ui-20260805 | 3318b1e1 | 2026-08-05 | 30 | |
| codex/recovery-macro-theme-tags-f6fcf697 | f6fcf697 | 2026-08-05 | 28 | |

### C9 — agent-N 编号大批次（28 支，2026-08-06，ahead 51~68）

该批次相互堆叠（大 ahead 数系链式提交），且 archive 区 17 个 detached 验证工作树的 HEAD 依赖本组分支托底（§6.3），**裁决本组前不要先删分支**。

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/home-snapshot-degradation-51 | 89637fa1 | 2026-08-06 | 51 | |
| codex/market-data-ncd-coverage-52 | 86650c4c | 2026-08-06 | 52 | |
| codex/market-data-tushare-completeness-53 | 856541c9 | 2026-08-06 | 53 | |
| codex/livermore-gate-async-54 | 4d4721de | 2026-08-06 | 53 | |
| codex/livermore-connection-reuse-55 | 4d4721de | 2026-08-06 | 53 | |
| codex/result-meta-yield-seed-56 | 806ae61d | 2026-08-06 | 54 | |
| codex/stock-analysis-theme-memberships-57 | fba37e3e | 2026-08-06 | 55 | |
| codex/stock-adjustment-choice-universe-59 | aad6bb15 | 2026-08-06 | 56 | |
| codex/agent-pnl-attribution-default-60 | 83e4f174 | 2026-08-06 | 56 | |
| codex/agent-portfolio-contract-61 | b556ec2b | 2026-08-06 | 58 | |
| codex/agent-duration-risk-tensor-62 | a33d72f6 | 2026-08-06 | 59 | |
| codex/agent-pnl-numeric-63 | 0ec6fb1f | 2026-08-06 | 57 | |
| codex/agent-news-routing-64 | a4138e55 | 2026-08-06 | 59 | |
| codex/agent-dev-scope-launcher-66 | 7b26020e | 2026-08-06 | 59 | |
| codex/agent-dev-full-stack-67 | 94082c3c | 2026-08-06 | 60 | |
| codex/pnl-maturity-risk-doc-contract-68 | 13a36c4c | 2026-08-06 | 61 | |
| codex/cleanup-known-test-artifacts-69 | 720f1749 | 2026-08-06 | 62 | |
| codex/agent-mvp-runbook-release-boundary-70 | 6815fd78 | 2026-08-06 | 63 | |
| codex/executive-aum-lineage-warning-71 | 395cddaf | 2026-08-06 | 66 | |
| codex/bond-worker-curve-preparation-72 | 3b6de627 | 2026-08-06 | 63 | |
| codex/agent-news-impact-routing-73 | 3b6de627 | 2026-08-06 | 63 | |
| codex/stock-analysis-mock-ci-74 | 2611ac73 | 2026-08-06 | 64 | |
| codex/backend-api-inventory-counts-75 | 3c7ccd38 | 2026-08-06 | 65 | |
| codex/fable-extension-study-76 | d0caab41 | 2026-08-06 | 64 | |
| codex/choice-css-financial-bulk-77 | 34a179f1 | 2026-08-06 | 66 | |
| codex/bond-worker-curve-prep-78 | d6aa9dcc | 2026-08-06 | 65 | |
| codex/bond-refresh-test-isolation-79 | f57fc7f9 | 2026-08-06 | 68 | ✔ |
| codex/precleanup-773-split-luna | 40802901 | 2026-08-06 | 67 | ✔ |

同 tip：livermore-gate-async-54 = livermore-connection-reuse-55；bond-worker-curve-preparation-72 = agent-news-impact-routing-73。

### C10 — 2026-08-06 ~ 08-08 活跃开发批次（47 支，绝大多数有工作树）

08-06 / 08-07（30 支）：

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/agent-runtime-reslice-20260806-pre-rebase | 858a08d0 | 2026-08-06 | 19 | |
| codex/bond-review-cherrypick-20260806 | 2b18f042 | 2026-08-06 | 2 | ✔ |
| codex/choice-migration-expectation-20260806 | a8cdaa96 | 2026-08-06 | 1 | |
| codex/choice-news-async-secure-20260806 | 5d0712c0 | 2026-08-06 | 2 | ✔ |
| codex/frontend-security-nonmajor-20260806 | 7b5222c1 | 2026-08-06 | 1 | ✔ |
| codex/liability-concentration-p0 | f3d884f3 | 2026-08-06 | 4 | ✔ |
| codex/liability-p0-reslice-20260806 | f04d712b | 2026-08-06 | 5 | ✔ |
| codex/livermore-gate-async-p0 | f33a9f8c | 2026-08-06 | 5 | ✔ |
| codex/market-finance-dirty-finalize-20260806 | ee43d2cc | 2026-08-06 | 1 | ✔ |
| codex/tmp-choice-news-async-review | 2fabbc5d | 2026-08-06 | 1 | |
| codex/tmp-market-review-20260806 | a0f7c343 | 2026-08-06 | 15 | |
| codex/agent-runtime-reviewed-pre-rebase-20260807 | ce18de49 | 2026-08-07 | 23 | |
| codex/akshare-clean-env-fix-20260806 | 2bc807f1 | 2026-08-07 | 3 | ✔ |
| codex/backend-security-upgrade-20260807 | 420d2f89 | 2026-08-07 | 1 | ✔ |
| codex/fable-unique-reslice-20260807 | 6a2423fa | 2026-08-07 | 2 | ✔ |
| codex/finance-metric-reslice-20260806 | cbc36f1c | 2026-08-07 | 16 | ✔ |
| codex/legacy-fixture-assertion-reslice-20260807 | 75bc6ae8 | 2026-08-07 | 2 | ✔ |
| codex/livermore-status-read-scope-fix-20260807 | 87dbd4eb | 2026-08-07 | 1 | ✔ |
| codex/p1-governance-sync-20260806 | 329a324a | 2026-08-07 | 3 | ✔ |
| codex/playwright-a11y-stock-bond-20260807 | 9d5aa8bf | 2026-08-07 | 1 | ✔ |
| codex/playwright-dashboard-market-20260807 | 85cee913 | 2026-08-07 | 1 | ✔ |
| codex/playwright-product-states-20260807 | 67e810f5 | 2026-08-07 | 1 | ✔ |
| codex/pnl-detail-readiness-fix-20260806 | 22ae97b0 | 2026-08-07 | 1 | ✔ |
| codex/pnl-report-date-lineage-reslice-20260807 | b314182d | 2026-08-07 | 2 | ✔ |
| codex/product-category-readiness-fix-20260807 | 5f9f54e8 | 2026-08-07 | 2 | ✔ |
| codex/react-router-security-upgrade-20260807 | 79194c3f | 2026-08-07 | 2 | ✔ |
| codex/route-scope-sync-20260806-rescue | 34f4b384 | 2026-08-07 | 2 | ✔ |
| codex/router-osv-reconciliation-20260807 | f289acba | 2026-08-07 | 1 | ✔ |
| codex/startup-performance-guard-fix-20260807 | 7bd8f04f | 2026-08-07 | 1 | ✔ |
| codex/stock-analysis-mock-ci-reslice-20260806 | 793547d6 | 2026-08-07 | 1 | ✔ |

08-08（17 支）：

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/balance-workbook-amount-drift-20260808 | 6cd9dd19 | 2026-08-08 | 1 | ✔ |
| codex/bond-bundle-isolation | de9fc943 | 2026-08-08 | 1 | ✔ |
| codex/bond-dashboard-lineage-fix-20260808 | a45e2421 | 2026-08-08 | 1 | |
| codex/bond-risk-offline-seed-20260808 | aabbf775 | 2026-08-08 | 1 | ✔ |
| codex/business-contract-drift-fix-20260808 | b561ee67 | 2026-08-08 | 1 | |
| codex/campisi-total-return-fix-20260808 | 5fbcd8e2 | 2026-08-08 | 2 | ✔ |
| codex/finance-boundary-guards-20260808@551c0c04 | a4d4a5e1 | 2026-08-08 | 2 | ✔ |
| codex/full-suite-bond-isolation-20260808 | 93887a51 | 2026-08-08 | 1 | ✔ |
| codex/full-suite-native-scripts-20260808 | b6b6d8aa | 2026-08-08 | 2 | ✔ |
| codex/fx-schema-recovery-20260808 | 31f5b262 | 2026-08-08 | 3 | ✔ |
| codex/golden-sample-drift-20260808 | f5cf4aaf | 2026-08-08 | 2 | |
| codex/portfolio-artifact-path-portability-20260808 | 7e491185 | 2026-08-08 | 2 | ✔ |
| codex/portfolio-closure-artifact-graph-20260808 | e5fff3c5 | 2026-08-08 | 2 | ✔ |
| codex/portfolio-evidence-packet-drift-20260808 | 3817d945 | 2026-08-08 | 5 | ✔ |
| codex/risk_tensor_vendor_failures | fbfa5796 | 2026-08-08 | 1 | ✔ |
| codex/stale-contract-tests-20260808 | ca1b3a49 | 2026-08-08 | 2 | |
| triage/stale-test-contracts-20260808 | f14d6694 | 2026-08-08 | 1 | |

### C11 — 2026-08-09 dirty/recover 收编批次（10 支）

这一批是把此前散落在工作树中的未提交改动收编成提交的产物（因此当前工作树全部干净），裁决核心问题是「这些收编内容是否已回流 / 是否还要回流 codex/V1」。

| 分支 | tip | 最后提交 | ahead | 工作树 |
| --- | --- | --- | ---: | --- |
| codex/dirty-choice-news-health-20260809 | ac1023cf | 2026-08-09 | 2 | ✔ |
| codex/dirty-duckdb-health-20260809 | 9d5ce815 | 2026-08-09 | 1 | ✔ |
| codex/dirty-positions-contract-20260809 | 0099b6a8 | 2026-08-09 | 1 | ✔ |
| codex/dirty-snapshot-decimal-20260809 | 152ff118 | 2026-08-09 | 1 | ✔ |
| codex/frontend-option-two-recovery-20260809 | 9a6ab5bd | 2026-08-09 | 1 | ✔ |
| codex/market-overview-finalized-restore-20260809 | 6a5774a8 | 2026-08-09 | 4 | |
| codex/product-category-confirmed-recovery-20260809 | f456a283 | 2026-08-09 | 1 | ✔ |
| codex/recover-livermore-queued-ui-20260809 | c246868d | 2026-08-09 | 1 | ✔ |
| codex/recover-pnl-lineage-tests-20260809 | dbeaac5b | 2026-08-09 | 1 | ✔ |
| codex/system-dark-theme-recovery-20260809 | 23c26c58 | 2026-08-09 | 2 | ✔ |

## 6. 工作树盘点（83 个）

### 6.1 脏工作树清单（1 个）

| 路径 | 分支 | 脏条目数 | 构成 | 热点目录 |
| --- | --- | ---: | --- | --- |
| F:/MOSS-V3（主工作树） | codex/V1 | 644（快照后漂移至 651） | M 414 / ?? 226 / D 11 | frontend 222、tests 134、backend 107、docs 37、scripts 23、根目录截图若干 |

其余 82 个工作树 `git status --porcelain` 均为 0 条（在各自目录下执行；抽样复核退出码为 0）。

### 6.2 prunable / missing 工作树清单（0 个）

全部 83 个注册目录均存在，`git worktree list --porcelain` 无 prunable 标注。**无需 `git worktree prune`**。

### 6.3 detached 工作树（24 个）

「HEAD 归属」说明移除该工作树后提交是否仍受引用保护：命中分支 tip / 已含于分支历史 = 安全；**无分支包含 = 移除前必须先打 tag**。

活跃区（5 个）：

| 路径 | HEAD | HEAD 归属 |
| --- | --- | --- |
| C:/Users/arvin/.codex/worktrees/ef49/MOSS-V3 | 0cd7d65f9 | 已含于 codex/V1 |
| G:/MOSS-V3-worktrees/bond-refresh-test-isolation-79-verify | 408029011 | 命中 codex/precleanup-773-split-luna tip |
| G:/MOSS-V3-worktrees/bond-worker-curve-prep-78-verify | 0b4022c53 | 含于 codex/bond-refresh-test-isolation-79、codex/precleanup-773-split-luna |
| G:/MOSS-V3-worktrees/frontend-option-two-patch-source-20260809 | 733836203 | **无任何分支包含（孤儿，先 tag）** |
| G:/MOSS-V3-worktrees/react-router-security-upgrade-baseline-54c22001 | 54c22001f | 已含于 codex/V1 |

archive 区 G:/MOSS-V3-worktrees-archive（19 个）：

| 路径（目录名） | HEAD | HEAD 归属 |
| --- | --- | --- |
| agent-dev-full-stack-67-postcommit | feb859b9b | 含于 C9 组（agent-mvp-runbook-70 等） |
| agent-mvp-runbook-release-boundary-70-postcommit | 3b6de6275 | 命中 codex/agent-news-impact-routing-73 / bond-worker-curve-preparation-72 tip |
| bond-worker-curve-preparation-72-base | 3b6de6275 | 同上 |
| cleanup-known-test-artifacts-69-postcommit | 8110cfa5d | 含于 C9 组 |
| home-snapshot-degradation-51-verify | a8159a9e5 | 含于 C9 组（agent-dev-67 等） |
| livermore-connection-reuse-55-verify | 806ae61d4 | 命中 codex/result-meta-yield-seed-56 tip |
| macro-theme-tags-audit-36b3a80c… | f6fcf6978 | 命中 codex/recovery-macro-theme-tags-f6fcf697 tip（C8 组） |
| market-data-ncd-coverage-52-verify | b99d2444f | 含于 C9 组 |
| market-data-tushare-completeness-53-verify | 4d4721deb | 命中 codex/livermore-gate-async-54 / -connection-reuse-55 tip |
| pnl-attribution-risk-coverage-50-verify | 60eec7d6d | 含于 C9 组 |
| pnl-by-business-ftp-fingerprint-49-verify | 2650404d6 | 含于 C9 组 |
| pnl-maturity-risk-doc-contract-68-postcommit | c85f96d87 | 含于 C9 组 |
| stock-analysis-mock-ci-74-verify | d0caab419 | 命中 codex/fable-extension-study-76 tip |
| stock-analysis-theme-memberships-57-verify | 6c8904548 | 含于 C9 组 |
| verify-agent-dev-scope-launcher-66 | 607604aae | 含于 C9 组 |
| verify-agent-pnl-attribution-default-60 | da6af3495 | 含于 C9 组 |
| verify-agent-pnl-numeric-63 | 8cb526195 | 含于 C9 组 |
| verify-agent-portfolio-contract-61 | 0ec6fb1fc | 命中 codex/agent-pnl-numeric-63 tip |
| verify-home-snapshot-degradation-20260805 | e5bad43df | **无任何分支包含（孤儿，先 tag）** |

要点：19 个 archive 区工作树中 17 个的提交由 C9 / C8 组分支托底——**若这些工作树在对应分支删除之后才移除没有问题，但若打算保留提交证据而删除分支，则须先打 tag**。真孤儿仅 2 个（上表加粗）。

### 6.4 分支绑定工作树（59 个，全部干净除主工作树）

| 路径 | 分支 |
| --- | --- |
| F:/MOSS-V3（主，脏 644） | codex/V1 |
| C:/tmp/MOSS-V3-market-data-submit-ready | codex/market-data-submit-ready |
| C:/Users/arvin/.codex/worktrees/2760/MOSS-V3 | codex/market-finance-dirty-finalize-20260806 |
| C:/Users/arvin/.codex/worktrees/772c/MOSS-V3 | codex/precleanup-773-split-luna |
| C:/Users/arvin/.codex/worktrees/campisi-total-return-fix-20260808 | codex/campisi-total-return-fix-20260808 |
| C:/Users/arvin/.config/superpowers/worktrees/MOSS-V3/balance-workbook-amount-drift-20260808 | codex/balance-workbook-amount-drift-20260808 |
| C:/Users/arvin/.config/superpowers/worktrees/MOSS-V3/codex-bond-bundle-isolation | codex/bond-bundle-isolation |
| C:/Users/arvin/.config/superpowers/worktrees/MOSS-V3/dual-frequency-amount-coverage | codex/dual-frequency-input-contract（**目录名与分支名错位**；分支 codex/dual-frequency-amount-coverage 无工作树） |
| C:/Users/arvin/.config/superpowers/worktrees/MOSS-V3/dual-frequency-blocker-fixes | codex/dual-frequency-blocker-fixes |
| C:/Users/arvin/.config/superpowers/worktrees/MOSS-V3/finance-boundary-guards-20260808-551c0c04 | codex/finance-boundary-guards-20260808@551c0c04 |
| C:/Users/arvin/.config/superpowers/worktrees/MOSS-V3/risk_tensor_vendor_failures | codex/risk_tensor_vendor_failures |
| C:/Users/arvin/.config/superpowers/worktrees/MOSS-V3/v1-main-integration | codex/v1-main-integration |
| G:/MOSS-V3-worktrees/agent-governance-consistency-20260808 | codex/agent-governance-consistency-20260808（a′ 已合并） |
| G:/MOSS-V3-worktrees/agent-runtime-reslice-20260806 | codex/agent-runtime-reslice-20260806（a′ 已合并） |
| G:/MOSS-V3-worktrees/akshare-clean-env-fix-20260806 | codex/akshare-clean-env-fix-20260806 |
| G:/MOSS-V3-worktrees/backend-security-upgrade-20260807 | codex/backend-security-upgrade-20260807 |
| G:/MOSS-V3-worktrees/bond-refresh-test-isolation-79 | codex/bond-refresh-test-isolation-79 |
| G:/MOSS-V3-worktrees/bond-review-cherrypick-20260806 | codex/bond-review-cherrypick-20260806 |
| G:/MOSS-V3-worktrees/bond-risk-offline-seed-20260808 | codex/bond-risk-offline-seed-20260808 |
| G:/MOSS-V3-worktrees/choice-news-async-secure-20260806 | codex/choice-news-async-secure-20260806 |
| G:/MOSS-V3-worktrees/dirty-choice-news-health-20260809 | codex/dirty-choice-news-health-20260809 |
| G:/MOSS-V3-worktrees/dirty-duckdb-health-20260809 | codex/dirty-duckdb-health-20260809 |
| G:/MOSS-V3-worktrees/dirty-positions-contract-20260809 | codex/dirty-positions-contract-20260809 |
| G:/MOSS-V3-worktrees/dirty-snapshot-decimal-20260809 | codex/dirty-snapshot-decimal-20260809 |
| G:/MOSS-V3-worktrees/fable-unique-reslice-20260807 | codex/fable-unique-reslice-20260807 |
| G:/MOSS-V3-worktrees/finance-metric-reslice-20260806 | codex/finance-metric-reslice-20260806 |
| G:/MOSS-V3-worktrees/frontend-option-two-recovery-20260809 | codex/frontend-option-two-recovery-20260809 |
| G:/MOSS-V3-worktrees/frontend-security-nonmajor-20260806 | codex/frontend-security-nonmajor-20260806 |
| G:/MOSS-V3-worktrees/full-suite-bond-isolation-20260808 | codex/full-suite-bond-isolation-20260808 |
| G:/MOSS-V3-worktrees/full-suite-native-scripts-20260808 | codex/full-suite-native-scripts-20260808 |
| G:/MOSS-V3-worktrees/full-workspace-final-20260808 | codex/full-workspace-final-20260808（a′ 已合并） |
| G:/MOSS-V3-worktrees/full-workspace-integration-20260806 | codex/full-workspace-integration-20260806（a′ 已合并） |
| G:/MOSS-V3-worktrees/full-workspace-verification-20260808 | codex/full-workspace-verification-20260808（a′ 已合并） |
| G:/MOSS-V3-worktrees/fx-schema-recovery-20260808 | codex/fx-schema-recovery-20260808 |
| G:/MOSS-V3-worktrees/legacy-fixture-assertion-reslice-20260807 | codex/legacy-fixture-assertion-reslice-20260807 |
| G:/MOSS-V3-worktrees/liability-concentration-p0 | codex/liability-concentration-p0 |
| G:/MOSS-V3-worktrees/liability-p0-reslice-20260806 | codex/liability-p0-reslice-20260806 |
| G:/MOSS-V3-worktrees/livermore-gate-async-p0 | codex/livermore-gate-async-p0 |
| G:/MOSS-V3-worktrees/livermore-status-read-scope-fix-20260807 | codex/livermore-status-read-scope-fix-20260807 |
| G:/MOSS-V3-worktrees/mobile-subnav-visibility-fix-20260807 | codex/mobile-subnav-visibility-fix-20260807（a′ 已合并） |
| G:/MOSS-V3-worktrees/p1-governance-sync-20260806 | codex/p1-governance-sync-20260806 |
| G:/MOSS-V3-worktrees/playwright-a11y-stock-bond-20260807 | codex/playwright-a11y-stock-bond-20260807 |
| G:/MOSS-V3-worktrees/playwright-dashboard-market-20260807 | codex/playwright-dashboard-market-20260807 |
| G:/MOSS-V3-worktrees/playwright-product-states-20260807 | codex/playwright-product-states-20260807 |
| G:/MOSS-V3-worktrees/pnl-detail-readiness-fix-20260806 | codex/pnl-detail-readiness-fix-20260806 |
| G:/MOSS-V3-worktrees/pnl-report-date-lineage-reslice-20260807 | codex/pnl-report-date-lineage-reslice-20260807 |
| G:/MOSS-V3-worktrees/portfolio-artifact-path-portability-20260808 | codex/portfolio-artifact-path-portability-20260808 |
| G:/MOSS-V3-worktrees/portfolio-closure-artifact-graph-20260808 | codex/portfolio-closure-artifact-graph-20260808 |
| G:/MOSS-V3-worktrees/portfolio-evidence-packet-drift-20260808 | codex/portfolio-evidence-packet-drift-20260808 |
| G:/MOSS-V3-worktrees/product-category-confirmed-recovery-20260809 | codex/product-category-confirmed-recovery-20260809 |
| G:/MOSS-V3-worktrees/product-category-readiness-fix-20260807 | codex/product-category-readiness-fix-20260807 |
| G:/MOSS-V3-worktrees/react-router-security-upgrade-20260807 | codex/react-router-security-upgrade-20260807 |
| G:/MOSS-V3-worktrees/recover-livermore-queued-ui-20260809 | codex/recover-livermore-queued-ui-20260809 |
| G:/MOSS-V3-worktrees/recover-pnl-lineage-tests-20260809 | codex/recover-pnl-lineage-tests-20260809 |
| G:/MOSS-V3-worktrees/route-scope-sync-20260806-rescue | codex/route-scope-sync-20260806-rescue |
| G:/MOSS-V3-worktrees/router-osv-reconciliation-20260807 | codex/router-osv-reconciliation-20260807 |
| G:/MOSS-V3-worktrees/startup-performance-guard-fix-20260807 | codex/startup-performance-guard-fix-20260807 |
| G:/MOSS-V3-worktrees/stock-analysis-mock-ci-reslice-20260806 | codex/stock-analysis-mock-ci-reslice-20260806 |
| G:/MOSS-V3-worktrees/system-dark-theme-recovery-20260809 | codex/system-dark-theme-recovery-20260809 |

## 7. 分批处置建议（每批 ≤20，命令为模板，一律不在本任务执行）

安全规则（适用于所有批次）：

1. 每支分支删除前重跑 `git rev-list --count codex/V1..<branch>` 复核；已合并用 `git branch -d`，未合并须 owner 逐支签字后用 `git branch -D`。
2. 被工作树占用的分支先 `git worktree remove <path>`（当前全部干净，无需 `--force`）。
3. detached 工作树中 HEAD 无分支包含的（§6.3 加粗 2 个），移除前先 `git tag archive/<名> <sha>`。
4. 不使用循环批删；逐条命令留痕。主工作树 F:/MOSS-V3 不在任何处置范围内。
5. 执行窗口避开并行任务；执行前重跑本报告采集命令做时点核对。

### W-1 — archive 区 detached 工作树退休（19 个，owner 确认验证快照不再需要后）

```powershell
# 孤儿 HEAD 先保全（1 个）
git tag archive/verify-home-snapshot-degradation-20260805 e5bad43df1e348e5b43bde0d2d749438c7adfd5a
# 逐个移除（示例，共 19 条）
git worktree remove "G:/MOSS-V3-worktrees-archive/agent-dev-full-stack-67-postcommit"
git worktree remove "G:/MOSS-V3-worktrees-archive/agent-mvp-runbook-release-boundary-70-postcommit"
# …（其余 17 个见 §6.3 表）
```

### W-2 — 活跃区 detached 工作树退休（5 个，逐个确认用途已结束）

```powershell
git tag archive/frontend-option-two-patch-source-20260809 733836203fc5f65a209aeb249f1659d1c09a5e6d   # 孤儿 HEAD 先保全
git worktree remove "C:/Users/arvin/.codex/worktrees/ef49/MOSS-V3"
git worktree remove "G:/MOSS-V3-worktrees/bond-refresh-test-isolation-79-verify"
git worktree remove "G:/MOSS-V3-worktrees/bond-worker-curve-prep-78-verify"
git worktree remove "G:/MOSS-V3-worktrees/frontend-option-two-patch-source-20260809"
git worktree remove "G:/MOSS-V3-worktrees/react-router-security-upgrade-baseline-54c22001"
```

### B-1a — 全合并分支第一波（3 支，2026-08-19 起满足 >30 天）

```powershell
git rev-list --count codex/V1..codex/development-audit-remediation   # 须为 0
git branch -d codex/development-audit-remediation
git branch -d codex/balance-analysis-date-closure
git branch -d codex/ledger-pnl-auth-closure
```

### B-1b — 全合并分支第二波（7 支，2026-09-10 起全部满足；先移除 6 个占用工作树）

```powershell
git worktree remove "G:/MOSS-V3-worktrees/agent-runtime-reslice-20260806"
git worktree remove "G:/MOSS-V3-worktrees/mobile-subnav-visibility-fix-20260807"
git worktree remove "G:/MOSS-V3-worktrees/agent-governance-consistency-20260808"
git worktree remove "G:/MOSS-V3-worktrees/full-workspace-final-20260808"
git worktree remove "G:/MOSS-V3-worktrees/full-workspace-integration-20260806"
git worktree remove "G:/MOSS-V3-worktrees/full-workspace-verification-20260808"
git branch -d codex/agent-runtime-reslice-20260806 ;  # 以下逐支执行，每支先 rev-list 复核
git branch -d codex/mobile-subnav-visibility-fix-20260807
git branch -d codex/agent-governance-consistency-20260808
git branch -d codex/full-workspace-final-20260808
git branch -d codex/full-workspace-integration-20260806
git branch -d codex/full-workspace-verification-20260808
git branch -d codex/decimal-precision-backfill-clean-00231b13a
```

### B-2 起 — c 类裁决批（owner 逐组签字后执行；未合并须用 -D，模板同上，命令按各组表逐支展开）

| 批次 | 内容 | 支数 | 建议裁决顺序理由 |
| --- | --- | ---: | --- |
| B-2 | C4 组 meta-status ×10 + closure ×4 + macro-observation-readable | 15 | 2026-06-05 后无活动（>60 天），主题单一（页面 meta/状态收口），大概率已被主线取代 |
| B-3 | C4 组 aggrid 系 6 支 | 6 | 同期 aggrid 修复线，与 B-2 一致裁决 |
| B-4 | C5 recovery 批次前半（表内前 19 支，含 104b2732 同 tip 5 支） | 19 | 2026-06-06/07 收编快照，>60 天 |
| B-5 | C5 recovery 批次后半 | 18 | 同上 |
| B-6 | C1 04-25 页面/后端批次 | 17 | >100 天，多为 ahead=1 的单提交尝试 |
| B-7 | C1 其余（04-11 ~ 04-19、04-26 ~ 04-29） | 20 | 同上 |
| B-8 | C2 + C3（05 月 ~ 06-04 零散） | 20（5+16 拆 1 支入 B-9） | >60 天 |
| B-9 | C6 + C7 早段（06 中下旬 + 07 上旬） | ≤20 | 逐支核对（含 ui/*、macro/* 非 codex 前缀线） |
| 暂不排批 | C8 ~ C11（08-04 以来）+ C7 晚段 dual-frequency/v1-main-integration/market-data-submit-ready | 103 | 30 天内活跃或有在用工作树，先裁决「是否回流 V1」，不进入删除流 |

C9 组特别注意：先处置 archive 区依赖工作树（W-1）再裁决分支；若要「删分支、留证据」，须对表内 tip 先打 tag。

## 8. 与 2026-07-20 清理决策的口径一致性（.planning/STATE.md）

- **同口径**：逐支 `rev-list --count codex/V1..branch == 0` 验证后才认定全合并；先盘点后处置；不 bulk delete；每批 ≤20。
- **锚点延续**：`codex/phase-02-exact-cutoff`（Phase 02 命名锚点）、`codex/pnl-bridge-date-closure`（superseded 参考）、`codex/phase-03-incremental-rebuild`（reference-only）继续保留，均入 b 类。
- **07-20 动作已落地核实**：当时退休的 4 个工作树（v1-merge-dateclosure、gs-bal-workbook-a-recapture、lazy-dispatch-proxy-fn、pnl-bridge-date-closure）均不在当前注册表；当时删除的 21 支全合并分支未复活（当前全合并集合为其后新产生的 11 支）。
- **STATE.md 遗留 todo 对上**：「future inventory pass for the remaining ~136 needs-confirm branches（recovery/meta-status/04-25 批次）」即本报告 C1+C4+C5（95 支）及 C2/C3/C6 等 06 月组；本报告将全部 227 支未合并分支纳入 c 类分组，无遗漏。
- 注册工作树从 72（07-20）增至 83，增量来自 08-06 ~ 08-09 的 agent/恢复批次。

## 9. 风险与注意事项

- **主工作树脏改动是最大变量**：644+ 条未提交（含 frontend/tests/backend 大量 M 状态），任何处置动作不得涉及 F:/MOSS-V3；后续批次执行时若这些改动被收编/提交，全合并判定可能变化，须重跑采集。
- **时点快照**：本仓库有 5 个并行技术债任务在写入，分支/工作树数与脏计数会漂移；处置执行前必须重跑报告头部「采集方法」中的命令。
- **同 tip 分支对**（archive-main ×2、full-workspace final/verification、livermore 54/55、curve-72/news-73、aggrid pr/review、recovery 104b2732 ×5、agent-runtime-reslice/mobile-subnav）：裁决一支即可连带决定另一支，建议成对处理。
- **detached 孤儿 HEAD 仅 2 个**（frontend-option-two-patch-source-20260809、verify-home-snapshot-degradation-20260805）：未打 tag 前移除工作树将使提交仅剩 reflog 保护（默认 90 天）。
- 分支名含 `@` 的 `codex/finance-boundary-guards-20260808@551c0c04` 在脚本处理时需引号保护，避免被 shell/git 解析为 revision 语法。
- 本报告未验证各分支独有提交的业务价值（超出 D3 范围）；c 类裁决需要 owner 结合各批次主题判断「回流 / 打 tag 归档 / 直接删除」。
