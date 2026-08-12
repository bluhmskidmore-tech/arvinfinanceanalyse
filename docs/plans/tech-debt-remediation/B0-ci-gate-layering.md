# B0 PR 门禁分层方案

- 撰写日期：2026-08-12
- 事实来源（实读核对）：`.github/workflows/ci.yml`、`scripts/backend_release_suite.py`、`pytest.ini`、`backend/pyproject.toml`、`tests/AGENTS.md`、`tests/CLAUDE.md`
- 约束：本文档只交付方案与建议 yaml 片段；`.github/workflows/ci.yml` 由主代理统一整合，本任务不直接修改。

## 0. 现状基线（2026-08-12 实测）

三层门禁现状：

| 层 | 触发 | 内容 | 缺口 |
| --- | --- | --- | --- |
| PR 门禁 | `pull_request` → main、`push` → main / `codex/**` | `backend` job：`scripts/backend_release_suite.py`（24 个测试文件 + MCP fast 合约）+ agent harness 2 文件（`test_agent_eval_spec.py`、`test_agent_eval_reward.py`） | 覆盖约 24/约 700 个后端测试文件（约 3.4%），无 mypy、无后端 ruff |
| 全量兜底 | `schedule`（每日 18:00 UTC）与 push→main | `backend-full-pytest` job：`python -m pytest -q`（collects `tests/` + `backend/tests/`，约 700 个文件） | 失败无通知闭环：不开 issue、不产出摘要工件，红灯依赖有人主动看 Actions |
| 静态检查 | PR/push | 仅前端（`npm run typecheck`、ESLint、debt:audit）；后端只有 `uv lock --check` | `backend/pyproject.toml` 已有 `[tool.ruff]`、`[tool.mypy]` 配置，但 CI 从不执行；且 ruff/mypy 均不在 `[project.optional-dependencies].dev` 中 |

测试文件量（实测）：`tests/` 顶层 685 个 + 子目录 4 个，`backend/tests/` 11 个；release suite 固定 24 个（清单见 §1，与 `docs/ci-release-suite.md` 同源）。

## 1. Release suite 覆盖清单与保护面

权威来源：`scripts/backend_release_suite.py` 的 `RELEASE_SUITE_TESTS`（24 项）+ `GOVERNANCE_MCP_FAST_SUITE_TESTS`。逐文件清单、执行环境与更新规则的可维护版本见 `docs/ci-release-suite.md`（本节按域归类，两处清单必须与脚本常量逐一对得上）。

### 1.1 按域归类（24 文件 + MCP 第二阶段）

**A. 平台与配置合约（3）**

| 文件 | 用例数* | 保护面 |
| --- | --- | --- |
| `tests/test_settings_contract.py` | 19 | governance settings 默认值、环境变量覆盖、helper 行为 |
| `tests/test_health_endpoints.py` | 4 | 健康检查端点可用性 |
| `tests/test_backend_dependency_contract.py` | 1 | `backend/pyproject.toml` 运行时依赖与 dev 依赖分离 |

**B. 核心业务 API 合约（12）**

| 文件 | 用例数* | 保护面 |
| --- | --- | --- |
| `tests/test_positions_api_contract.py` | 15 | 持仓 API 封套 + 快照读取行为 |
| `tests/test_pnl_api_contract.py` | 148 | PnL API 合约（套件内最大单文件） |
| `tests/test_pnl_by_business_insights_contract.py` | 24 | 业务条线 PnL 洞察合约 |
| `tests/test_pnl_by_business_candidate_insights_contract.py` | 14 | 候选口径（Scenario）洞察合约 |
| `tests/test_candidate_period_comparison_contract_alignment.py` | 1 | 候选期间对比合约版本跨层对齐 |
| `tests/test_risk_tensor_api.py` | 13 | 风险张量 API |
| `tests/test_balance_analysis_api.py` | 32 | 余额分析 API |
| `tests/test_bond_analytics_api.py` | 19 | 债券分析 API 封套 + 核心结果字段 |
| `tests/test_liability_analytics_api.py` | 9 | 负债分析 API |
| `tests/test_liability_analytics_envelope_contract.py` | 1 | 负债分析响应封套合约 |
| `tests/test_executive_dashboard_endpoints.py` | 11 | 高管仪表盘端点 |
| `tests/test_cube_query_api.py` | 7 | cube 查询 API |

**C. 跨端点 UI 封套与页面契约（2）**

| 文件 | 用例数* | 保护面 |
| --- | --- | --- |
| `tests/test_result_meta_on_all_ui_endpoints.py` | 9 | 所有 UI 端点 `result_meta` / `result` / `basis` 语义 |
| `tests/test_live_route_page_contract_completeness.py` | 7 | 活跃路由必须有页面契约或带签核/burn-down 元数据的显式临时豁免 |

**D. 治理与血缘（2）**

| 文件 | 用例数* | 保护面 |
| --- | --- | --- |
| `tests/test_governance_lineage_audit.py` | 2 | 治理血缘审计脚本（脏行检测、无副作用、指纹归一） |
| `tests/test_governance_doc_contract.py` | 28 | 治理文档结构与内容合约 |

**E. 黄金样本与发布矩阵（4）**

| 文件 | 用例数* | 保护面 |
| --- | --- | --- |
| `tests/test_golden_samples_capture_ready.py` | 10 | capture-ready 黄金样本存在性、元数据状态、字段匹配、fail-closed 允许清单 |
| `tests/test_ledger_pnl_net_interest_golden_sample.py` | 3 | 净利息黄金样本对账 + 生产计算链回放 |
| `tests/test_executive_release_contract.py` | 4 | `GS-EXEC-OVERVIEW-A` / `GS-EXEC-PNL-ATTR-A` / `GS-EXEC-SUMMARY-A` 三个发布门样本 |
| `tests/test_golden_sample_release_matrix.py` | 3 | 黄金样本目录与 release gate 样本 ID 对齐；**套件自守卫**（断言 release suite 必须包含 exec 合约与漂移检查文件） |

**F. 架构边界守卫（1）**

| 文件 | 用例数* | 保护面 |
| --- | --- | --- |
| `tests/test_no_finance_logic_in_frontend.py` | 1 | 前端源码不得出现正式金融计算 token（`frontend -> api -> services -> core_finance` 边界） |

**第二阶段：治理 MCP 合约（同脚本内顺序执行）**

| profile | 文件 | 用例数* | CI 使用 |
| --- | --- | --- | --- |
| fast（默认） | `tests/test_project_mcp_fast_contracts.py`（`-m mcp_fast`） | 2 | PR 门禁在跑 |
| full | `tests/test_project_mcp_servers.py` | 172 | 仅手动 `--mcp-profile full`；CI 的 PR 阶段不跑（nightly 全量 pytest 会收集到） |

**PR job 内、套件外补充**：agent harness 七文件（`tests/test_agent_eval_spec.py` 14、`tests/test_agent_eval_reward.py` 4、`tests/test_agent_eval_collect.py` 23、`tests/test_agent_eval_scoring_integrity.py` 13、`tests/test_agent_eval_replay.py` 6、`tests/test_caliber_gate_mapping.py` 6、`tests/test_mcp_config_consistency.py` 2，合计 68），以独立步骤直跑 pytest，不经过 release suite 的隔离环境；另有 `Caliber path-trigger gate` 步骤（仅 `pull_request`）按 diff 定向触发 caliber 红线测试。

\* 用例数为 AST 静态统计的 `test_*` 函数数（含类方法，不含参数化展开），2026-08-12 快照，仅供体量参考。

执行环境要点（影响"该套件证明了什么"）：release suite 在临时目录隔离 `MOSS_GOVERNANCE_PATH` / `MOSS_DUCKDB_PATH`，并设 `MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1`、`MOSS_SKIP_POSTGRES_MIGRATIONS=1`、`MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST=1` —— 即它证明的是**fixture 隔离环境下的合约行为**，不证明迁移路径、真实存储与真实鉴权链路。

### 1.2 保护面总结与盲区

**保护面**（PR 阶段有防护）：对外 API 合约与响应封套语义、页面契约完备性、治理文档/血缘审计、黄金样本发布门（4 个样本锚点）、前端无金融逻辑边界、依赖分离合约、MCP fast 合约。一句话：**"对外表面"与"发布门锚点"有防护**。

**盲区**（PR 阶段不设防，仅靠 nightly / main push 全量 pytest 兜底；文件名举例均为 `tests/` 下实际存在文件）：

1. **core_finance 计算引擎深层单测**：Campisi 归因（`test_campisi.py`、`test_campisi_attribution_service.py`、`test_campisi_decision_grade*.py`）、PnL bridge 系列（`test_pnl_bridge_core.py`、`test_pnl_bridge_with_curve.py`、`test_pnl_bridge_curve_effects.py`、`test_pnl_bridge_fx_translation.py` 等）、债券引擎（`test_bond_analytics_engine.py`、`test_bond_analytics_core.py`、`test_bond_analytics_curve_effects.py`）、风险（`test_var_engine.py`、`test_risk_metrics.py`）、宏观模型（`test_macro_model_garch.py`、`test_macro_model_dcc.py`、`test_macro_model_crisis_score.py` 等）、策略（`test_livermore_strategy_core.py`、`test_portfolio_backtest.py`）。**这是最要害的盲区：PR 改数值逻辑时，唯一的数值防线是 4 个黄金样本文件，深度有限。**
2. **services / repositories 层**：`test_bond_analytics_service.py`、`test_risk_tensor_service.py`、`test_balance_analysis_service_boundaries.py`、`test_bond_analytics_repo.py`、`test_duckdb_repo_scoped_connection.py` 等。
3. **物化与任务流**：`test_snapshot_materialize_flow.py`、`test_balance_analysis_materialize_flow.py`、`test_bond_analytics_materialize_flow.py`、`test_snapshot_materialize_manifest_fail_closed.py`、`test_worker_bootstrap.py`。
4. **缓存与启动路径**：`test_api_response_cache.py`、`test_home_snapshot_cache.py`、`test_home_endpoint_response_cache.py`、`test_market_home_warmup.py`、`test_main_lifespan.py`。
5. **vendor / 市场数据**：`test_choice_client_contract.py`、`test_choice_runtime.py`、`test_market_data_livermore_api.py` 及全部 `market_data_livermore_*` / `choice_*` 系列。
6. **agent 链路**（除 eval spec/reward 外）：`test_agent_intent_routing.py`、`test_agent_api_contract.py`、`test_agent_sql_disclosure_drift.py`、`test_agent_enabled_path_smoke.py`。
7. **精度与数据修复**：`test_decimal_precision_backfill.py`、`test_fx_mid_materialize.py`、`test_risk_coupon_window_repair.py`、`test_common_numeric_finite_guard.py`。
8. **dev 基础设施**：`test_dev_postgres_cluster.py`、`test_dev_worker_lifecycle_scripts.py`、`test_native_dev_script_contents.py`。
9. **MCP full 合约**：172 个用例只在 nightly 全量里被收集，PR 改 MCP 服务器实现时 fast 合约（2 用例）是唯一即时防线。
10. **横向盲区**：无 mypy（类型回归）、无后端 ruff（PR 可引入 lint 违规而 CI 全绿）、nightly 红灯无通知闭环（盲区兜底本身可能长期失效而无人察觉）。

分层结论：PR 门禁的设计意图是"合约面 + 发布门锚点"的有界快检（`backend` job 限时 20 分钟），盲区靠 nightly 兜底**在机制上成立，但需要两个补丁**：(a) 盲区与改动的交集在 PR 内用"触达路径定向测试"约定补防（§2、§3）；(b) nightly 失败必须有通知闭环（§4），否则兜底层形同虚设。

## 2. "触达路径定向测试"约定（成品文本）

以下为可直接粘贴进 CONTRIBUTING / PR 模板 / 评审规程的成品段落。现状：仓库尚无 `CONTRIBUTING.md` 与 `.github/PULL_REQUEST_TEMPLATE.md`，落点与建档由主代理统一决定；在此之前评审者可直接引用本节作为规程依据。

> ### 触达路径定向测试（Targeted Tests，必填）
>
> CI 的 PR 门禁只运行有界 release suite（合约面 + 黄金样本锚点，见 `docs/ci-release-suite.md`），**不会**自动运行你改动所触达的深层测试。因此每个涉及后端代码的 PR 必须在描述中包含以下 checklist，且全部勾选后方可合入：
>
> ```markdown
> #### 触达路径定向测试
> - [ ] 我已列出本 PR 改动的每个后端文件所对应的定向测试目标（见下表）。
> - [ ] 我已在本地执行上述全部定向测试并通过：`python -m pytest <targets> -q`。
> - [ ] 改动涉及正式金融计算 / 指标口径（`backend/app/core_finance/**`、H/A/T 映射、发债剔除、FX 中间价、514/516/517 归并、Formal/Scenario 分离）时，我已运行对应引擎测试与相关黄金样本测试，并在 PR 描述附上影响说明。
> - [ ] 没有任何改动文件的定向测试为"无"；若确实无对应测试（新模块 / 纯文档 / 纯注释），我已逐文件写明理由。
>
> | 改动文件 | 定向测试目标 | 执行结果 |
> | --- | --- | --- |
> | （逐行列出） | `tests/...` | passed / 附说明 |
> ```
>
> 定向测试的选择规则（与 `tests/CLAUDE.md` 的最小目标原则一致）：
>
> 1. **改哪层，跑哪层，再跑它的对外合约**：改 `backend/app/api/routes/<x>.py` → 跑该路由对应的 `test_<x>*_api*.py` / `*_contract.py`；改 `backend/app/services/<x>.py` → 跑 `test_<x>_service*.py` 加上其上游 API 合约测试；改 `backend/app/core_finance/<domain>/**` → 跑该域引擎测试（如 `test_pnl_bridge_*.py`、`test_campisi*.py`、`test_bond_analytics_engine.py`）加相关黄金样本。
> 2. **改 schema / 封套** → 额外跑 `tests/test_result_meta_on_all_ui_endpoints.py`。
> 3. **改 `backend/app/tasks/**` 或物化流程** → 跑对应 `*_materialize_flow.py` 与 manifest fail-closed 测试。
> 4. **改测试本身** → 该测试文件即目标。
> 5. **找不到对应测试时**：用 `git log --follow` 查同模块历史 PR 的测试目标，或按命名规则在 `tests/` 中检索模块名；仍无则按 checklist 第 4 条逐文件说明。
> 6. 定向测试**不替代** release suite：CI 仍会运行 `scripts/backend_release_suite.py`；定向测试补的是 release suite 之外的盲区（清单见 `docs/plans/tech-debt-remediation/B0-ci-gate-layering.md` §1.2）。
>
> 评审者义务：对照 PR 的 diff 文件列表抽查定向测试表是否遗漏；发现"改了 core_finance 却只跑合约测试"的 PR 应打回。

待 §3 的映射脚本落地后，上表可由 `python scripts/pr_targeted_tests.py --emit-checklist` 自动生成，人工规则退化为兜底。

## 3. diff→测试映射轻量脚本设计（只设计，不实现）

**目标**：把 §2 的人工映射规则脚本化，输出可执行的 pytest 目标列表与可粘贴的 checklist，供本地与（后续可选的）CI 提示步骤使用。

- 脚本名：`scripts/pr_targeted_tests.py`（与 `scripts/backend_release_suite.py` 同风格：stdlib-only、常量表内聚、可 `--dry-run`）
- 依赖：仅 Python 标准库（`argparse`、`fnmatch`、`json`、`pathlib`、`subprocess`）；Windows/PowerShell 与 Linux CI 均可运行。

**输入**

| 方式 | 说明 |
| --- | --- |
| 默认 | `git diff --name-only $(git merge-base HEAD <--base, 默认 origin/main>)..HEAD` 取改动文件 |
| `--files a.py b.py` | 显式传入（CI 中可直接喂 PR 文件列表，避免依赖本地 git 状态） |

**映射规则表**：脚本内常量 `TARGETED_TEST_RULES: list[tuple[str, tuple[str, ...]]]`（有序，glob → 测试目标元组），全部命中规则取并集；示意条目：

```python
TARGETED_TEST_RULES = [
    ("tests/test_*.py",                       ("{self}",)),                # 改测试即目标
    ("backend/tests/test_*.py",               ("{self}",)),
    ("backend/app/api/routes/positions*.py",  ("tests/test_positions_api_contract.py",)),
    ("backend/app/core_finance/pnl_bridge/**", (
        "tests/test_pnl_bridge_core.py",
        "tests/test_pnl_bridge_with_curve.py",
        "tests/test_ledger_pnl_net_interest_golden_sample.py",
    )),
    ("backend/app/schemas/**",                ("tests/test_result_meta_on_all_ui_endpoints.py",)),
    ("backend/pyproject.toml",                ("tests/test_backend_dependency_contract.py",)),
    ("frontend/**",                           ()),                          # 后端定向测试为空，前端走自身门禁
    # ……逐域补全；首版覆盖 backend/app 顶层每个包至少一条规则
]
```

**输出模式**

| 参数 | 行为 |
| --- | --- |
| `--list`（默认） | 打印去重后的 pytest 目标（一行一个），可直接拼 `python -m pytest ... -q` |
| `--run` | 直接执行 `python -m pytest <targets> -q`，透传退出码 |
| `--emit-checklist` | 输出 §2 格式的 markdown 表格（改动文件 → 目标），供粘贴进 PR 描述 |
| `--json` | 机器可读：`{mapped: {file: [targets]}, unmapped: [...], targets: [...]}` |
| `--strict` | 存在 unmapped 后端文件时退出码非零（CI 门禁模式）；默认仅告警（fail-open） |

**防腐机制**（配套单测，实现时一并交付）：

1. 规则表中每个测试目标文件必须真实存在（防目标随重构失效）。
2. `backend/app/` 下每个一级包至少命中一条规则（防新增模块成映射黑洞）。
3. 规则表 glob 均可被 `fnmatch.translate` 编译（防语法坏损）。

**明确非目标（v1）**：不做 import 图 / AST 反向依赖分析（若日后需要，v2 再评估，且优先复用 GitNexus impact 而非自建）；不替代 release suite；不自动修改 CI 必跑集；不解析 PR 描述（`--emit-checklist` 只生成不校验，PR 描述校验若要做，属于另一个 workflow 关注点）。

**推广路径**：先本地约定工具（§2 checklist 引用它）→ 稳定后可选在 CI 加"提示性"步骤（`--strict` 关闭、只输出建议清单到 job summary）→ 最后才考虑升级为阻断门禁（需主代理决策）。

## 4. schedule 全量失败通知闭环（ci.yml 建议片段）

现状 `backend-full-pytest` 失败后无任何主动通知。建议将该 job 整体替换为下述版本（新增：junit + 控制台日志工件、job summary 摘要、失败自动开/更新 issue）。**本片段交由主代理整合进 `.github/workflows/ci.yml`，本任务不直接修改该文件。**

```yaml
  backend-full-pytest:
    name: Backend Full Pytest
    runs-on: ubuntu-latest
    timeout-minutes: 40
    if: github.event_name == 'schedule' || (github.event_name == 'push' && github.ref == 'refs/heads/main')
    permissions:
      contents: read
      issues: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/pyproject.toml

      - name: Install backend dependencies
        run: pip install -e "./backend[dev]"

      - name: Run full backend pytest suite
        id: full-pytest
        run: |
          mkdir -p test_output/ci
          python -m pytest -q \
            --junitxml=test_output/ci/full-pytest-report.xml \
            2>&1 | tee test_output/ci/full-pytest-console.log
          exit "${PIPESTATUS[0]}"

      - name: Write full pytest summary
        if: always()
        run: |
          {
            echo "## Backend Full Pytest (${GITHUB_EVENT_NAME})"
            echo ""
            echo "- commit: \`${GITHUB_SHA}\`"
            echo "- conclusion: ${{ steps.full-pytest.outcome }}"
            echo ""
            echo '```text'
            tail -n 80 test_output/ci/full-pytest-console.log || echo "(no console log captured)"
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"

      - name: Upload full pytest evidence
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: backend-full-pytest-report
          path: |
            test_output/ci/full-pytest-report.xml
            test_output/ci/full-pytest-console.log
          retention-days: 14
          if-no-files-found: warn

      - name: Open or update failure tracking issue
        if: failure() && github.event_name == 'schedule'
        uses: actions/github-script@v7
        with:
          script: |
            const label = "ci-full-pytest-failure";
            const title = "[CI] Scheduled backend full pytest failed";
            const runUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            const body = [
              `Scheduled full backend pytest failed on \`${context.ref}\`.`,
              "",
              `- Run: ${runUrl}`,
              `- Commit: \`${context.sha}\``,
              "- Evidence artifact: `backend-full-pytest-report` (junit xml + console tail, retained 14 days)",
              "",
              "Triage: see docs/plans/tech-debt-remediation/B0-ci-gate-layering.md §4 (close this issue only after a green scheduled run).",
            ].join("\n");
            try {
              await github.rest.issues.getLabel({ ...context.repo, name: label });
            } catch (error) {
              await github.rest.issues.createLabel({
                ...context.repo,
                name: label,
                color: "b60205",
                description: "Scheduled backend full pytest is red",
              });
            }
            const { data: open } = await github.rest.issues.listForRepo({
              ...context.repo,
              state: "open",
              labels: label,
              per_page: 1,
            });
            if (open.length > 0) {
              await github.rest.issues.createComment({
                ...context.repo,
                issue_number: open[0].number,
                body,
              });
            } else {
              await github.rest.issues.create({
                ...context.repo,
                title,
                body,
                labels: [label],
              });
            }
```

设计说明与闭环规则：

1. **去重**：以 `ci-full-pytest-failure` 标签为锚点——已有 open issue 则追加评论（连续失败不刷屏），否则新建。恢复绿灯后由值守人关闭 issue（关闭动作即"确认已修复"，不建议自动关闭，避免 flaky 掩盖真实回归）。
2. **push→main 失败**不开 issue（GitHub 默认会向提交作者发失败通知），仅 schedule 失败开 issue——schedule 失败没有天然收件人，是通知闭环的核心缺口。若主代理希望 main push 失败也进 issue 流，把条件改为 `failure() && (github.event_name == 'schedule' || (github.event_name == 'push' && github.ref == 'refs/heads/main'))` 即可。
3. **权限**：job 级 `permissions: issues: write` 为新增；仓库若在组织层收紧了默认 `GITHUB_TOKEN` 权限，此处显式声明即可生效，无需 PAT。
4. **摘要工件**：junit xml 可供后续统计 flaky 率；console tail 进 job summary，值守人不用下载工件就能看到失败尾部。
5. **已知并发风险**：顶层 `concurrency: group: ci-${{ github.ref }}` + `cancel-in-progress: true` 意味着 schedule 运行（ref 为 main）可能被同 ref 的 push 取消，造成"nightly 静默缺勤"。建议主代理评估将 group 改为 `ci-${{ github.event_name }}-${{ github.ref }}`（schedule 与 push 互不取消）；本片段不包含该改动，避免与其他专家的 ci.yml 片段冲突。

## 5. mypy job 与后端 ruff job（建议 yaml 占位）

事实前提（实读 `backend/pyproject.toml`）：`[tool.ruff]`（py311、line-length 120、select E/W/F/I/B/UP/S110/S112、tests 有 per-file-ignores）与 `[tool.mypy]`（py311、`ignore_missing_imports = true`）配置**已存在**，但 `ruff`、`mypy` 均不在 `[project.optional-dependencies].dev` 中——因此下述 job 目前**不可直接启用**，必须等专家 14（mypy 基线机制）/ 专家 15（后端 ruff 机制）交付：工具版本 pin、基线文件、门禁包装脚本。占位中以 `TODO(expert-14)` / `TODO(expert-15)` 标注对接点；基线治理遵循 `docs/plans/tech-debt-remediation/D2-baseline-governance.md` 的棘轮规则（基线只降不升，上升需签核）。

```yaml
  backend-typecheck:
    name: Backend Mypy
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/pyproject.toml

      - name: Install backend dependencies
        run: pip install -e "./backend[dev]"

      # TODO(expert-14): mypy 版本 pin —— 首选专家14将 mypy 加入 backend[dev]（则删除本步），
      # 否则在此处 pin：pip install "mypy==<expert-14 指定版本>"
      - name: Install mypy
        run: pip install "mypy==<TODO-expert-14-pinned-version>"

      # TODO(expert-14): 替换为基线门禁入口，预期形如：
      #   python scripts/mypy_gate.py --baseline <expert-14 基线文件路径>
      # 依赖产物：门禁脚本路径、基线文件路径（棘轮式，只降不升，规则见 D2-baseline-governance.md）。
      # 过渡期可由主代理决定加 continue-on-error: true 观察噪声后再转阻断。
      - name: Run mypy (baseline-gated)
        run: python scripts/mypy_gate.py --baseline <TODO-expert-14-baseline-path>
```

```yaml
  backend-lint:
    name: Backend Ruff
    runs-on: ubuntu-latest
    timeout-minutes: 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      # TODO(expert-15): ruff 版本 pin —— 首选专家15将 ruff 加入 backend[dev] 或提供锁定安装方式，
      # 否则在此处 pin：pip install "ruff==<expert-15 指定版本>"
      - name: Install ruff
        run: pip install "ruff==<TODO-expert-15-pinned-version>"

      # 配置自动发现 backend/pyproject.toml 的 [tool.ruff]；
      # TODO(expert-15): 确认执行目录与范围（backend 全量 or 含 tests/），
      # 若存量违规需要基线包装（形如 python scripts/ruff_gate.py --baseline <path>），
      # 以专家15产物为准替换本步；基线遵循 D2 棘轮规则。
      - name: Run ruff check
        run: ruff check backend
```

对接清单（主代理整合时逐项确认）：

| 事项 | 依赖方 | 占位当前值 |
| --- | --- | --- |
| mypy 版本 pin / 进 dev extras | 专家 14 | `<TODO-expert-14-pinned-version>` |
| mypy 门禁脚本 + 基线文件路径 | 专家 14 | `scripts/mypy_gate.py` + `<TODO-expert-14-baseline-path>` |
| ruff 版本 pin / 进 dev extras | 专家 15 | `<TODO-expert-15-pinned-version>` |
| ruff 执行范围与可能的基线包装 | 专家 15 | `ruff check backend` 直跑 |
| 是否过渡期 `continue-on-error` | 主代理 | 未设（建议首周观察模式） |

## 6. 风险与未决事项

1. **ci.yml 整合冲突**：本文档 §4/§5 片段与其他专家的 ci.yml 片段存在同文件合并风险（尤其 `backend-full-pytest` 为整 job 替换）；主代理整合时以 job 为单位合并，`permissions`、`concurrency` 等顶层/共享键需统一裁决。
2. **mypy/ruff 首跑噪声**：两工具从未在 CI 跑过，存量违规规模未知；若专家 14/15 的基线机制未就绪就直接阻断，可能瘫痪所有 PR。建议顺序：基线机制落地 → 观察模式（continue-on-error）→ 阻断。
3. **定向测试约定的执行力**：§2 是纪律约定，无机器强制；在 §3 脚本与 PR 描述校验落地前，依赖评审者抽查，存在漏网概率。
4. **schedule 静默缺勤**：§4 说明 5 的 concurrency 取消问题在通知闭环之外——被取消的 run 不算 failure，不会触发 issue。这是当前分层里唯一"失败都不产生信号"的路径，建议主代理优先裁决。
5. **清单漂移**：§1 与 `docs/ci-release-suite.md` 的 24 文件清单是脚本常量的快照；`tests/test_golden_sample_release_matrix.py` 会守卫套件的部分成员资格，但不会守卫文档同步。文档同步依赖 `docs/ci-release-suite.md` 中的更新规则与评审 checklist（机器校验命令已附在该文档 §5）。
6. **用例数统计口径**：本清单用例数为静态函数计数，参数化展开后的实际执行数更高；如需精确数，以 `python -m pytest <file> --collect-only -q` 为准。
