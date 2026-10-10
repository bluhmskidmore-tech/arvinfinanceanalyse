# MOSS-V3 全系统多角色审计报告（2026-09-02）

## 审计方式

基线 HEAD `bef54b58`，审计对象为磁盘上的工作树（相对 HEAD 有约 546 个已跟踪文件被修改、约 135–168 个未跟踪文件，+21340/−12643 行）。六个只读子代理按角色并行审计：安全与授权边界、后端架构分层、金融计算正确性（core_finance）、前端质量、测试与 CI 健康度、仓库卫生与配置。本次没有可切换的模型，"按难度分级"体现为验证深度：金融计算、安全、分层要求 文件:行号 证据并做独立数值验算；前端与测试要求真实运行 lint / typecheck / vitest / pytest / release suite；仓库卫生用脚本量化。

**重要前提**：审计进行期间（约 17:55–20:20）工作树被另一进程持续修改（`bond_analytics/engine.py`、`common.py`、`bond_duration.py`、`krd.py`、`rate_units.py`、`pnl_bridge.py`、`campisi_attribution_service.py`、`backend_release_suite.py`、`test_no_finance_logic_in_api.py`、`test_service_storage_boundaries.py`、`contracts/openapi/*.json`、`liability-analytics/` 若干 tsx 等），`git status` 从 682 行增至 721 行。所有基于测试运行的结论均受此影响，已在对应条目标注"伪失败"或"待冻结重跑"。

## 一、总体结论

系统主线是健康的：授权基线落实完整（279 条路由仅 3 条 `/health*` 无鉴权，SQL 全部参数化/白名单）；固定收益核心公式（Macaulay/修正久期/凸性/KRD/四效应闭合）经独立数值导数验算正确；前端 lint / typecheck / build / 编码审计 / 债务审计全绿，生产依赖 0 漏洞；后端内部测试 185 全过。

但当前工作树**不可提交、不可作为发布证据**，且存在需要立刻处理的问题：

1. **凭据泄漏（Critical）**：`config/.env` 明文含 Choice 账号密码、Tushare token、Stitch API key；其中 Choice 凭据已随提交 `3cf24a71e` 推送到远端 `origin/master` 顶端，且镜像在 `.omx/logs/turns-2026-04-*.jsonl`。
2. **真实回归（Critical）**：未提交的 DuckDB schema `27_choice_stock_factor_snapshot.sql` 新增 `total_mv/circ_mv` 两列，但生产任务 `choice_stock_materialize.py:2961` 仍按位置插入 16 个值，物化必然 BinderException。
3. **未提交改动失控（Critical）**：一批改动横跨前端 30+ feature 目录、后端 schema/Alembic/RBAC 缓存/settings/release-control 新子系统，混合至少 5 条独立主题，直接触碰 AGENTS.md 列出的受保护边界，无法按页面回滚或评审。
4. **金融口径缺口（High）**：Campisi model 路径把期内买卖现金流直接计入选券效应；信用利差把 `ytm=0`（缺失哨兵）当真实 0% 收益率产出负利差；浮息债按固定利率现金流算久期进入 DV01/KRD。
5. **测试可信度低（High）**：`tests/` 全量 32 失败 + 2 错误（提前中止，下界），其中 5 例在 HEAD 即红；34 个失败只有 2 个文件在 release suite 门禁范围内；release suite 本地 81 分钟而 CI 超时设 20 分钟；本地 venv 是 Python 3.14.2，CI 与 `.python-version` 为 3.11。

## 二、严重度汇总

| 级别 | 数量 | 代表条目 |
|---|---|---|
| Critical | 3 | 凭据入远端历史；schema 变更破坏物化任务；未提交改动越界且测试期间并发编辑 |
| High | 13 | Vite `host: true` 使 loopback 守卫失效；Agent read scope 越权读仓储；services↔tasks 双向依赖；core_finance 含 DuckDB 写入；Campisi 期内交易；ytm=0 负利差；版本升级触发 fail-closed；前端 2 个测试文件确定性失败；删除 74 个页面级用例；ps1 去 BOM 不可解析；HEAD 已红测试；门禁覆盖缺口；.gitignore 吞源文件 |
| Medium | ~25 | 见各分节 |
| Low / Info | ~30 | 见各分节 |

## 三、分领域发现

### 3.1 安全与授权边界（评级：中等偏低风险，开发态可接受，生产态不可直接部署）

**Critical**

- **S-C1 真实凭据落盘并进入远端 Git 历史**。`config/.env:1-3,14` 含 `MOSS_CHOICE_USERNAME/PASSWORD`、`MOSS_TUSHARE_TOKEN`、`STITCH_API_KEY` 真实值。`git log --all -- config/.env` 显示 `3cf24a71e (2026-04-11)` 新增该文件，`git branch -a --contains` 命中 `remotes/origin/master`（`github.com/bluhmskidmore-tech/arvinfinanceanalyse.git`）。文件当前被 `.gitignore:4` 忽略、不在 HEAD 祖先链，但远端 master 顶端可直接读取。**修复**：立即轮换三组凭据；改写或删除远端分支历史；清理 `.omx/logs`。来源：当前文件未跟踪；历史泄漏已提交（远端）。

**High**

- **S-H1 同机 Vite 反代使"仅 loopback"开发守卫失效**。`frontend/vite.config.ts:107` `host: true`，`:110-114` 把 `/ui` `/api` `/health` 代理到 `127.0.0.1:7888` 且未设 `xfwd`；`backend/app/api/deps.py:64-70` 与 `backend/app/api/routes/agent_workspace.py:99-101` 以 `client.host` 是否 loopback 决定 dev bypass；`scripts/dev-agent-api.ps1:8-9` 默认 `MOSS_AGENT_DEV_SCOPE_BYPASS=true`。局域网任意主机访问 `:5888` 即可以 anonymous/viewer 命中所有 `allow_dev_fallback=True` 读路由（`balance_analysis.py:76`、`positions.py:37`、`kpi.py:98` 等 10 处），并在 dev-agent 模式下无 scope 创建/修改 Agent 项目、发起 Hermes 运行。**修复**：proxy 加 `xfwd: true` 或 `server.host` 改 `127.0.0.1`。来源：已提交。
- **S-H2 Agent 读 scope 可越权读其他资源并触发外部 LLM**。`backend/app/api/routes/agent.py:401,447` 对 `/query`、`POST /runs` 仅要求 `agent:read`（`route_policy.py:51` internal 级）；`backend/app/services/agent_service.py:277-314` 的 intent 处理器直接实例化 `BalanceAnalysisRepository`、pnl/risk_tensor/product_pnl 仓储；服务层无 `ensure_user_allowed`。**修复**：为每个 intent 绑定目标资源做 read 校验，或将 `/runs` 提升到 `execute`。来源：已提交。

**Medium**

- **S-M1** `kpi_workbench_service.py:197-212` `raise KpiStorageError(str(exc))` + `routes/kpi.py:86-87` `HTTPException(503, detail=str(exc))`，SQLAlchemy 原始异常（SQL、参数、连接串）回传客户端。
- **S-M2** `routes/macro_toolkit.py:1070-1094` 同步执行宏观脚本（timeout ≤600s）；`macro_toolkit_service.py:474` `env = os.environ.copy()` 透传含密钥的完整环境，`:515-522` 返回未脱敏 stdout/stderr 与绝对路径，`:384` 已有的 `_redact_sensitive_error_text` 未用于此路径。
- **S-M3** 启动守卫、默认凭据（`settings.py:18-19` `moss:moss`、`:148-149` `minioadmin`）全依赖 `environment` 字段（默认 `development`）；`docker-compose.yml:18,53` 固定 `development`，不能直接用于生产。未提交改动把 `environment` 收紧为 Literal，属正向。

**Low / Info**

- **S-L1** `tasks/choice_macro.py:1235-1247` 把 Choice SDK 错误原文写入治理状态并经 `/ui/macro/choice-series/refresh-status` 回传，`config/choice_runtime.py:178` 的 start_options 含 `PassWord=`，若 SDK 回显登录串则密码入库。
- **S-L2** `routes/kpi.py:122-124` CSV 导出无公式转义（`=+-@` 开头单元格）。
- **S-L3** `agent.py:69-85,153-167` "只读"防线是子串黑名单，真正边界在 `action_token.py` HMAC 与 `toolset_policy.py` 白名单。
- **S-I1** 本地 venv `starlette==1.0.0`、`fastapi==0.135.3`，`pyproject.toml:13` 要求 `starlette>=1.3`，`uv.lock` 锁 `1.3.1/0.136.0`——本机环境与锁文件漂移。
- **S-I2** `agent_workspace_service.py:160,455` 对他人资源返回 403 而非 404，可枚举 ID。

**已验证正常**：279 条路由除 `/health*` 外全部挂 `get_auth_context` 并调用 scope 校验（含全部写操作、刷新/回填/导入/导出）；无 `eval/exec/pickle.loads/yaml.load/os.system/shell=True`；subprocess 全部 argv 列表；文件路径 resolve+relative_to 收敛；`build_agent_subprocess_env` 剥离 `MOSS_*`；确认 token HMAC 绑定 user_id 且 15 分钟 TTL；外部 HTTP 全带 timeout；上传 16MB 上限；分页有 `le`；CORS 显式来源列表；前端无 `dangerouslySetInnerHTML/innerHTML/eval`，不注入 `X-User-*`；CI 有 gitleaks v8.30.1 + OSV-Scanner v2.3.0；`npm audit --omit=dev` 0 漏洞；compose 强制 `:?` 必填密码、端口绑 `127.0.0.1`。

### 3.2 后端架构分层与数据边界（评级：B-，主线可控、边线松散）

实际 import 方向矩阵（模块级文件数，括号为函数内延迟 import）：

| 源 \ 目标 | api | services | repositories | core_finance | governance | tasks |
|---|---|---|---|---|---|---|
| api | — | 35 | **2 违规** | 0 | 40 (settings) | 0 |
| services | 0 | — | 81 | 60 | 41 | **1 + 22 文件延迟，违规** |
| repositories | 0 | 0 | — | 15 逆向 | 4 | 0 |
| core_finance | 0 | 0 | 0 | — | (2 延迟) | 0，但 9 模块直接 `import duckdb` |
| governance | 0 | **1 违规** | 4 | 2 | — | **3 违规** |
| tasks | 0（HEAD 有 6 处，本次改动清除） | **22 违规** | 48 | 21 | 64 | — |

**High**

- **A-H1 services↔tasks 双向依赖，写入经 service 中转**。`services/cffex_member_rank_service.py:44,73` import 并调用 `tasks.cffex_member_rank.persist_cffex_member_rank_rows`；`tasks/macro_toolkit_write_refresh.py:53-56` 反向延迟 import 该 service。守卫仍在 tasks 打开，但"谁在写"已不可从目录判断。来源：已提交。
- **A-H2 core_finance 含 DuckDB I/O 与写入**。`core_finance/matched_baseline.py:345` `duckdb.connect(str(path), read_only=dry_run)`，`:43-46` DDL、`:294-301` delete/insert，无 `require_repository_task_write_scope`；`core_finance/macro/toolkit/cffex_member_rank_shared.py:3-11,56` 明示为规避"不得 import repositories"而把读查询下沉到 core_finance，repositories 反向 re-export。`scripts/run_matched_baseline_backfill.py` 可绕过守卫写库。来源：已提交。
- **A-H3 未提交版本升级触发正式读面 fail-closed**。新文件 `core_finance/fixed_income_version_set.py:305,321` 将 `rv_bond_analytics_formal_materialize` v2→v3、`rv_risk_tensor_formal_materialize` v6→v7；`services/risk_tensor_service.py:559-570` 版本不等即返回 "Rematerialize required"。合并后未重物化前 risk_tensor/bond_analytics 全部不可用；该未跟踪文件与 8 个已修改文件必须同笔提交。来源：新增未跟踪 + 未提交。
- **A-H4 未提交改动整体触碰受保护边界**。`storage_bootstrap.py:22-33` 启动迁移按 environment 分叉；`storage_migration_flags.py:22-27` 改变 `MOSS_SKIP_POSTGRES_MIGRATIONS` 语义；`governance/settings.py:107` `environment` 收紧为大小写敏感 Literal；`models/governance.py` 新增 AgentAudit/AgentPrompt；新增 Alembic 迁移 `7d1a2c3e4f50`、`c2e94f6a8b10`；`repositories/release_control_repo.py` 1864 行新子系统；`security/auth_context.py:102-104,122-127` 高风险动作绕过鉴权缓存。对应 `AGENTS.md:15,45-53`。约四成属 formal-compute 主线（精度、lineage、版本集中、路由变薄），约六成属明确排除的"通用基础设施/底层重建"。来源：未提交 + 新增。

**Medium**

- **A-M1** Campisi 正式分解公式落在 services：`campisi_attribution_service.py:1332` `treasury = roll_down + treasury_curve`，`:1341-1353` selection 残差，`:481-489` 利差 bp 推导，`:543` 市值加权 YTM。应迁入 `core_finance/campisi`。
- **A-M2** 16 个 services 文件 `import duckdb`，`macro_vendor_service.py:156`、`macro_toolkit_service.py:1841,1951,2200…` 共 18 处 `duckdb.connect(read_only=True)` 内联 SQL，repositories 层被架空。
- **A-M3** 路由过厚：`routes/macro_toolkit.py` 1773 行、41 个私有函数、`:52-89` 导入 30 余个服务层下划线私有符号；`routes/executive.py:218` 在路由内构造 Repository。
- **A-M4** governance 反向依赖 services/tasks：`governance/stock_analysis_current_rule_version_tuple.py:36-42`、`stock_analysis_*_vendor_receipt.py:19,22`。
- **A-M5** 未提交改动在 `services/pnl_attribution_service.py` 新增 `_sum_tpl_accounting_amount` 等正式 PnL 金额求和，属"补算"扩张，应放 core_finance。
- **A-M6** services 136 文件中 29 个 >800 行、15 个 >1500 行（最大 `market_data_livermore_service.py` 4850 行）；`_duckdb_storage_identity` 在 4 个 service 逐字复制。

**Low / Info**

- **A-L1** `repositories/user_scope_repo.py:11` 新增 import `security.route_policy`，与 `security/auth_context.py:12` 成 security↔repositories 环（未提交）。
- **A-L2** `config/.env:12` `MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1` 实际无效——`storage_migration_flags.py:14` 只读 `os.environ`，pydantic env_file 不注入进程环境。
- **A-L3** `main.py:50` import 期执行 `register_macro_toolkit_read_builders()`；无自定义全局异常处理器、无 request-id 中间件。
- **A-L4** ruff 264 项（F401 233、I001 28、E402 2、B905 1），集中在 `livermore_candidate_history_service.py`（89）、`macro_toolkit_service.py`（69）、`executive_service.py`（39）。
- **A-I1** `perf_logging.py`/`response_cache.py` 迁至 `observability/` 为纯移动，全仓无残留 import，并清除了 HEAD 中 tasks→api 的 6 处反向依赖。**A-I2** Alembic 单 head `c2e94f6a8b10`，链线性，models 与迁移一致。

**静默 fallback 清单**（无日志、无标记暴露给调用方的）：`cffex_member_rank_shared.py:53-61` 文件缺失/表缺失→空 DataFrame；`macro_vendor_service.py:152-153,167-168` 库缺失→`series=[]`；`macro_toolkit_service.py:3419-3420` 治理流读失败→`[]`；`campisi_attribution_service.py:495-506` 曲线缺 3Y→取 on-or-before 最近日期无 `fallback_mode`；`pnl_attribution_service.py:113-114`、`executive_service.py:1425-1426` 仓储探测异常→`False`。已正确暴露的：`bond_analytics_service.py:4281-4299`、`stock_portfolio_construction_service.py:447-476`、`market_overview_service.py:341-348`、`formal_compute_lineage.py:165-173`。

### 3.3 金融计算正确性 core_finance（评级：B，核心公式正确，边界口径与消费链路有实质缺口）

独立验算结论：5Y 4% 半年付 D=4.5695、Dmod=4.4581、C=23.1944 与 −dP/dy/P、d²P/dy²/P 吻合；`estimate_modified_duration(5,−1%,f=2)=5.0251`；krd.py 各桶 ΣKRD 与组合修正久期精确闭合；四/六效应恒等式闭合；负 ytm −95% 判脏、−0.5% 观测；DV01 面值口径与 `calc_rules.md:207-209` 一致；GS-RISK-WARN-B 12.2455→12.5097 与 22 期闭式一致；`GS-*` 重录 approval 均附理由。

**High**

- **F-H1 Campisi model 路径未处理期内交易现金流**（已提交）。`bond_four_effects.py:260,268-271` `total_price_change = mv_end − mv_start … selection_effect = total_return − …`；`campisi_attribution_service.py:672,700,702` 起止并集合并、单边缺失记 0。验算：mv_start=0、mv_end=1e8 → `selection_effect=100000000`。任一月内有增减仓时 model 路径合计与 formal PnL 差额 = 交易金额量级。页面契约 F.1 未声明此限制。**修复**：合并时剔除单边持仓或引入交易流量项并披露。
- **F-H2 信用利差把 `ytm=0` 当真实 0% 收益率**（已提交）。`credit_spread_analysis.py:87` 只排除 `None`，`:239-240` `if ytm == ZERO: return ZERO`，`:113` 利差=(0−基准)×100。engine 把源 `ytm_value=0` 归为 observed 落库为 0，而 `common.py:255` 把 0 视为缺失哨兵走 par 回退——同一个 0 在三处三种语义。3Y 曲线 1.785% → 利差 −178.5bp 并计入加权；`common.py:538-539` 提到 live 库 155 个持仓/529 亿落在 ytm≤0 分支。**修复**：跳过 `ytm==0` 或 `duration_quality_flag=ytm_par_fallback` 行并披露笔数。

**Medium**

- **F-M1 浮息债按固定利率算久期**（已提交）。`engine.py:232` 仅记录 `interest_rate_style`，`:320-332` 对所有行算久期/DV01；`calc_rules.md:335` 声明 `duration_convexity_scope=vanilla_fixed_rate_only`。5Y 浮息券久期≈重定价期 0.25 却按 ~4.5 计入 DV01/KRD。置信度中（浮息占比未知）。
- **F-M2 整期归并容差三方不一致**（未提交、进行中）。`common.py:304-321` 容差改为 `min(N/4+2, 365/f/2−1)` 天；`calc_rules.md:429`、`bond_duration.py:91-92` docstring、`tests/test_bond_duration.py:214-222`、GS-RISK-WARN-B approval 均仍写固定 7 天。新规则下 3Y+5d 年付与 30Y 半年付久期与真实现金流表精确一致（旧规则偏 +2.50%/−1.37%），但 test_bond_duration 单调性用例在 9681→9682 天失败。根因是仅凭 ACT/365 年限反推付息表，结构性修复应复用 `cashflow_projection` 的到期日锚定。

**Low / Info**

- **F-L1** `balance_analysis_workbook.py:847-851` 新规则 `bal_wb_rating_default_001` 引用 "calc_rules 12.3 利率债规则"，该节不存在（12.3 是 tyw 规则）。
- **F-L2** `qdb_gl_monthly_analysis.py:1811-1816` 注释称 rate_effect 吸收交叉项，实为 volume_effect 用本期利率吸收。
- **F-L3** `krd.py:402` DV01 用面值、`:568-571` 情景损益用市值，同模块两种基数。
- **F-I1** `ENGINE_RULE_VERSION` 未随数值行为 bump（materialize rv 已 bump）。**F-I2** `workbench.py:43` `_out` 改 `ROUND_HALF_UP`，与 Python `round` 银行家舍入不同，属口径澄清。

**未提交 core_finance 改动逐文件结论**：`common.py`（负 ytm 不再走 par 回退、整期归并容差改日历规则，Medium）；`engine.py`（`NEGATIVE_YIELD_DIRTY_FLOOR` −20%，rule_version 改由 version_set 提供）；`rate_units.py`（新增 `negative_floor`）；`bond_duration.py`（负 ytm D/(1+y/f)）；`bond_four_effects.py`、`krd.py`、`credit_spread.py`、`pnl_bridge.py`（缺 ytm 行改用生效 ytm，此前少除 1+c/f；`test_krd_golden` 10Y 8.3819→8.5230 附独立推导）；`risk_tensor.py`（仅元数据，有假设行时 quality_flag ok→warning）；`pnl_attribution/workbench.py`（float→Decimal、ROUND_HALF_UP，GS 重录 16−1e−14→16）；`position_sizing.py`（`_as_finite_float` 接受 Decimal，此前 Decimal 输入被当缺失落到 8% 兜底止损，无直接单测）；`livermore_stock_candidates.py`（缺因子行显式 `factor_score=None`，`tests/test_livermore_stock_candidates.py:544` 未同步→失败）；其余为 docstring/去 BOM/委托共享函数。

**歧义清单**（需业务裁定，不应由代码猜）：ytm=0 三种语义；付息频率 `interest_mode.py:46-47,59` 回退年付 vs `campisi.py:343-347`、`krd.py:304`、`credit_spread.py:257` 默认半年付 vs 实证 f=2；roll-down 时间锚 `calc_rules.md:176-181` 按 elapsed_days vs `workbench.py:308,796` 1 年÷12；`workbench.py:774,776` carry=MV×(coupon−FTP) 应为 face×coupon；`campisi.py:329-340` 评级由 asset_class 字串猜、`:50` 缺到期日回退 3Y；`balance_analysis_workbook.py:196-199` 浮盈浮亏含 AC 类无开关。

**黄金样本缺口**（无测试引用的公开函数）：krd `aggregate_krd_by_asset_class`；credit_spread `interpolate_curve_rate`、`compute_spread_scenarios`、`compute_migration_scenarios`、`compute_concentration`、`compute_oci_sensitivity`；read_models `build_concentration`、`summarize_accounting_audit`、`weighted_average_by_market_value`；workbench `build_pnl_attribution_analysis_summary`、`mv_index`；campisi `aggregate_maturity_buckets`、`classify_primary_driver`、`accrued_interest_basis`、`effect_availability_entry`；qdb_gl `compute_deviation`、`generate_alerts`、`build_foreign_currency_rows`、`build_11d_top_rows`；macro/helpers 13 个；position_sizing `build_stock_candidate_position_size_hint`；cashflow_projection `project_zqtz_cashflows`；stock_portfolio_risk `compute_stock_portfolio_risk`。Campisi 无 `GS-*` 样本，无"期内增减仓"用例。

**测试运行**：固收/归因相关三批共 1467 用例，3 失败——`test_livermore_stock_candidates::…missing_factor_data`（期望过期）、`test_bond_duration::test_duration_is_monotonic_in_remaining_days[1],[2]`（测试 7 天助手落后于新容差），均非公式错误。

### 3.4 前端质量（评级：B-，可构建可类型检查，但当前工作树不可提交）

| 命令（frontend/） | 退出码 | 结果 |
|---|---|---|
| `npm run lint` | 0 | 0 错误 0 警告 |
| `npm run typecheck` | 0 | 通过 |
| `npm run test` | 1 | 488 文件 486 过 / 2 败；5543 用例 5342 过 / 4 败 / 197 skip；490s |
| `npm run build` | 0 | 5256 模块，候选指标 guard 通过 |
| `node scripts/audit_encoding_integrity.mjs` | 0 | 4245 文件，U+FFFD 0 |
| `npm run debt:audit` | 0 | 6/6 PASS |
| `npm audit --omit=dev` | 0 | 180 生产依赖，0 漏洞 |

**High**

- **W-H1** `workbenchShellSections.ts:67` 将 `SECTION_SUBNAV_EXCLUDED_SECTION_KEYS` 收窄为 `["dashboard","stock-analysis"]`，`/balance-analysis` 开始渲染子导航，但 `src/test/BalanceAnalysisPage.test.tsx:1404` 仍断言不存在。未提交。
- **W-H2** `MacroToolkitPage.test.tsx:5534` 超时上调到 45s 后仍超时（单跑 238s 文件），全量时同文件另 2 例连带超时。未提交。
- **W-H3** `StockAnalysisPage.test.tsx` 188 个 `it(` → 126（删 74 增 11，−3093 行），被删含 "fails closed when signal confluence cannot be loaded"、"shows staleness banner when quality_flag is not ok"、"surfaces the workbench fallback date"、"renders closed-loop blockers without turning them into trading advice"。9 个新测试文件合计仅 45 例；页面级 stale/fallback 关键词 124→56。AGENTS.md 要求显式披露的 stale/fallback/fail-closed 行为失去集成级守护。未提交。
- **W-H4** 改动越界：298 修改 / 7 删除 / 55 新增，触及 30+ 目录，混合外壳统一、Decimal 精确数值、股票研究台重建、共享原语替换、契约同步测试五类主题。最大 8 个：`styles/dashboardCockpit.css` +90/−2055、`test/StockAnalysisPage.test.tsx` +455/−3093、`StockAnalysisPage.css` +76/−1888、`StockAnalysisPageImpl.tsx` +665/−550、`styles/workbenchDeferredChrome.css` +307/−104、`layouts/WorkbenchShell.tsx` +342/−59、`test/ModuleWorkbenchHomeModel.test.ts` +317/−6、`moduleHomeModel.ts` +241/−60。被删 7 文件无 import 残留。

**Medium**

- **W-M1** null 渲染为 0：`features/pnl/PnlByBusinessPage.tsx:1402,1420` `numeric(row.scale_amount) ?? 0`；`:1464-1467` `current = numeric(row.current_balance) ?? 0; gap = current − adbAvg` 缺失期末被当 0 得到错误差值并在 `:1561` 展示。已提交。
- **W-M2** 前端补算冠以"正式"：`workbench/module-home/moduleHomeModel.ts:1171,1185` 前端 reduce 求和与评级总市值相减输出"正式余额核对差异 X 亿"。已提交。
- **W-M3** `teamPerformancePageModel.ts:372-379` `reduce((s,i)=>s+(i.amountYuan ?? 0))` 求合计，null 行按 0 参与。已提交。
- **W-M4** 契约漂移被 skip 记录未修：新增 `src/test/BalanceContractSync.test.ts:376/779/807` 三个 `it.skip("[已知漂移]…")`——前端 `identity_source` 多 `"system"`；`BalanceMovementPayload` 缺 `unmapped_gl_accounts`；`BalanceMovementDatesPayload` 缺 `upstream_control_report_dates`。
- **W-M5** `market-data/hooks/useMarketDataPageData.ts:169` `placeholderData: keepPreviousQueryData` 且 key 含日期，切日期期间沿用旧数据且无 `isPlaceholderData` 消费。已提交。
- **W-M6** `!important` 共 2260 处（`StockAnalysisPage.css` 445、`MarketDataPage.css` 372、`dashboardHomeOptionTwo.module.css` 338、`workbenchShell.css` 152）；未提交 `workbenchDeferredChrome.css` 再加 `(0,5,0)+!important` 终层压制。

**Low**：`toFixed` 在约 90 个组件 250+ 处违反 `utils/format.ts:113` 约定；`SourcePreviewPage.tsx` 15 处、`crossAssetAnalytics.ts:26-56` 9 处硬编码 hex；工作树 42 个前端文件 CRLF；`.nvmrc`=22 本机 node v24.13.0；`buildHomeBondNewsModel.ts:201` `new Date(value)` 对 `YYYY-MM-DD`（UTC）与带时间（本地）混合排序；`stockAnalysisResearchDeskModel.ts:468-479` 窗口仅 3/5 点即标注 MA5/MA20；`StockAnalysisPageImpl.tsx:954-973` `avgReturn5d` 无消费者。

**前端补算金融指标位置**（DV01/KRD/久期/Campisi 均直读后端，以下为前端自算）：`crossAssetAnalytics.ts:658-659` ERP、`:78-103` Pearson、`:346` 百分位、`:399` 动量、`:523-525` 波动率（已标"展示层试算"）；`productCategoryPnlPageModel.ts:3849-3866,3947-3960` 环比差/bp/命中率；`pnlAttributionViewModel.ts` explainedEffect、coveragePct；`teamPerformancePageModel.ts:372-379`；`moduleHomeModel.ts:1171,1185,3232-3243`；`PnlByBusinessPage.tsx:1464-1467`；`BalanceMovementAnalysisPage.tsx:3712-3723,1134-1139`；`LiabilityCounterpartyBlock.tsx:65`。

**测试覆盖**：所有 feature 目录至少 1 个测试引用；目录内无测试仅靠 `src/test` 的：ledger-dashboard、cube-query、platform-config、publication-showcase、source-preview、agent-lab、news-events、kpi-performance；`prototype/` 为空目录。skip 3 / only 0 / todo 0；Vitest 197 skipped 无法从源码定位。

### 3.5 测试与 CI 健康度（评级：低，本轮结果不能作为发布/合并证据）

| 命令 | 退出码 | 结果 | 耗时 |
|---|---|---|---|
| `pytest backend/tests` | 0 | 185 passed | 24s |
| `pytest -n 6 -x --maxfail=30 tests` | 2 | 8298 passed / 32 failed / 6 skipped / 2 errors，达 maxfail 中止 | 50m37s |
| `scripts/backend_release_suite.py` | 1 | 795 passed / 1 failed / 2 deselected；第一阶段失败即返回，MCP 契约阶段未执行 | 81m30s |

**失败归因**（34 例）：a 代码回归 6、b 测试期望过期 18、c 快照/基线漂移 5、e xdist 共享状态 1、f 并发编辑伪失败 4；其中 5 例在 HEAD 即红。

**Critical**

- **T-C1 测试期间工作树被并发编辑，结果不可信**。`moss_release_suite.txt:43` 的断言文本与当前 `tests/test_service_storage_boundaries.py:357` 不一致（18:53 被改写，现 30 passed）；`test_no_finance_logic_in_api` 运行时为 HEAD 版（子串匹配 `KRD` 命中 `KRDAttributionEnvelope` import 假阳性，18:49 改后 3 passed）；`test_ledger_import_worker_e2e` 1F+2E 因 worker 子进程导入 `engine.py:597` NameError（18:20 被编辑，现可导入）。通过的 8298 例同样不能证明当前工作树正确。**修复**：冻结工作树（或 `git worktree` 副本）后重跑。
- **T-C2 schema 变更破坏生产物化任务**。`backend/app/schema_registry/duckdb/27_choice_stock_factor_snapshot.sql:14-15` 新增 `total_mv/circ_mv`；`backend/app/tasks/choice_stock_materialize.py:2961-2962` `_insert_factor_snapshot` 位置插入 16 值 vs 18 列 → BinderException（`test_choice_stock_materialize` ×3、`test_choice_stock_vendor_era_guard` 失败）。**修复**：改为列名显式插入并补两列；同步 `tests/test_choice_stock_vendor_era_guard.py:555`。未提交。

**High**

- **T-H1** `scripts/start-moss-finance-audit-cluster.ps1` 未提交改动删掉 UTF-8 BOM（36 个 ps1 中唯一有 BOM 者），PowerShell 5.1 按 ANSI 解析中文 → ParserError（`test_hermes_agent_team_launcher` ×2）。
- **T-H2** HEAD 已红且未闭环：`test_caliber_audit_ci_gate[formal_scenario_gate]`（`adb_analysis_service.py:2201`、`agent_run_service.py:1546` 无 justified 标记）、`test_analysis_view_tool` ×2（`validate_filters`、`result_kind=agent.cube_query` 期望未更新）、`test_macro_report_asset_analysis::…names_composition_boundary`、`test_choice_news_query::…future`（夹具把 `2026-09-01` 当未来，时间炸弹）。`backend-full-pytest` scheduled job 应已连续失败。
- **T-H3 门禁覆盖缺口**：34 个失败中 30 个不在 release suite；分层/契约守卫 `test_backend_api_inventory`（代码多出 5 条路由：`/api/liabilities/monthly/detail`、`/api/pnl/basis-bridge`、`/ui/market-overview/snapshot`、`/ui/macro/toolkit/commodity-futures/refresh-status`、`/ui/market-data/stock-analysis/portfolio-construction`，基线未再生成）、`test_caliber_audit_ci_gate`、`test_lazy_task_import_constants`、`test_page_contract_metric_dictionary_completeness`、`test_business_display_coverage_report` 均不在门禁；`scripts/backend_release_suite.py:212-213` 第一阶段失败即返回，MCP 契约阶段被跳过。

**Medium**

- **T-M1** 快照类测试无一键刷新：7 个 `*_matches_generator` + openapi inventory + coverage report，刷新分散在 30+ 脚本的 `--write`/`baseline-update`；82 个测试文件硬引用 130 个 `docs/*.md|json`（`docs/audits` 14 文件、`docs/plans` 5 文件），文档即夹具。
- **T-M2** 运行时漂移：本地 `.venv` 为 Python 3.14.2，CI 与 `.python-version`（未跟踪）为 3.11；`frontend/package.json:7` engines 允许 node 20.19 而 `.nvmrc`=22。
- **T-M3** release suite 本地 81 分钟 vs `ci.yml:20` `timeout-minutes: 20`、`docs/ci-release-suite.md:102`；串行无 `-n`，大头 `test_pnl_api_contract` 773s、`test_golden_samples_capture_ready` 217s；最慢单例多为 PowerShell 子进程（`test_native_dev_scripts` 文件 1826s、`test_codex_page_readiness_gate` 1445s）。
- **T-M4** 其余期望过期类：`adb_insights_api`（路由改 `{code,message}` 结构化错误）、`average_balance_owner_evidence_packet` ×3 与 `capture_average_balance_monthly_golden_candidate` ×3（golden 已含 calibration/trace_id，脚本/测试/doc 未对齐）、`codex_page_readiness_gate`/`page_contract_metric_dictionary_completeness`/`native_dev_scripts` ×2（`docs/page_contracts.md` PAGE-POS-001 增补 MTR 行）、`lazy_task_import_constants`（`routes/adb_analysis.py` 移除 `materialize_balance_analysis_facts` 代理）、`frontend_playwright_smoke_scaffold`（testid 改 `macro-toolkit-cockpit`）、`macro_vendor_refresh_async_contract`（超期 503 契约服务与测试均在改，半成品）、`macro_report_asset_analysis::…after_api_reload`（builders 组合迁到 `api/__init__.py`）。
- **T-M5** 弱断言：`assert … is not None` 532 处/161 文件；`tests/helpers.py:38-39` `except Exception: yield`。

**Low / Info**：`-x --maxfail=30` 使失败数为下界；19 个测试文件含 `F:/` 字面量、28 文件引用 `data/moss.duckdb`（受 `skipif` 与 `ci_skip_registry.json` 守卫）、`test_tushare_news_ingest.py` 6 处 `datetime.now()`；`ci.yml` 弱化点均有注释（`mypy-ratchet` `continue-on-error` `:453`、BLE001 `|| true` `:445`、OSV `continue-on-error` `:806` 有 evaluate 兜底）；未提交 ci.yml 改动仅新增 `release-control-structure` job，`tests/test_ci_workflow_contents.py` 28 passed；6 个 skipped 全部登记在 `tests/ci_skip_registry.json`。

**无测试引用的 services**（135 中 23 个，多为拆分出的 `_support` 子模块）：analytical_bridge_service、credit_spread_analysis_service、executive_service_builders/formatting/home_support、home_macro_period_freshness、liability_knowledge_service、livermore_candidate_history_envelope_support/read_support、livermore_position_snapshot_dispatch_service、macro_toolkit_allocation_snapshot_service、macro_toolkit_presentation、macro_toolkit_service_commodity_inputs/readiness/support、market_data_livermore_service_input_freshness/module_status/official_evidence/support、obsidian_vault、pnl_service_analysis_dims、pnl_service_by_business_support、pnl_service_v1_compat。routes 39 个全部有引用。

### 3.6 仓库卫生、配置与文档（评级：C，可用但明显失控）

**High**

- **R-H1 忽略规则吞掉源文件**。`git ls-files -i -c --exclude-standard` 返回 15 项已跟踪但命中忽略：`config/.env.example`、`frontend/.env.example`（被 `.env.*`）、`frontend/eslint.config.js`（被 `frontend/*.js`）、`.codex/config.toml` + 5 个 SKILL.md（被 `.codex/`）、`docs/plans/artifacts/*`（被 `artifacts/`）、`sample_data/smoke-runtime/*.xls`（被 `*.xls`）。同时 `frontend/.env.development.example`、`.codex/skills/` 4 个新技能、`.codex/agents/` 15 个 toml 因此不出现在 `git status`。**修复**：`.env.*` 加 `!*.env.example`；`.codex/` 拆细；`artifacts/` 锚定为 `/artifacts/`；`frontend/*.js` 加 `!frontend/eslint.config.js`。已提交。
- **R-H2 未提交改动规模失控**：539 M / 9 D / 134 ??（展开 168 文件），含 `governance/release_control.py`、`release_approval.py`、`models/release_control.py`、2 个 Alembic 迁移、`config/release_approval_registry.v1.json`、`config/exact_numeric_compat_registry.v1.json`、30 余个 `tests/test_*.py`。存在拆分计划 `docs/plans/2026-08-27-uncommitted-work-split-plan.md` 但未执行。

**Medium**

- **R-M1** 根目录跟踪生成物 `governance-lineage-audit.json`（含本机绝对路径；`tests/test_ci_workflow_contents.py` 要求 CI 不产出它）。
- **R-M2** docker-compose 与 `CONFIGURATION.md` 漂移：compose 要求 `MOSS_POSTGRES_PASSWORD`/`MOSS_MINIO_ROOT_*` 必填，文档仍写死 `moss:moss@postgres:5432`；`api` 服务无 `ports:` 映射，文档却把 8000 列为对外端口。
- **R-M3** Worker 启动命令四套：GETTING-STARTED `dramatiq worker_bootstrap`、`dev-worker.ps1`/`start_dev.cmd` `dev_worker_runner --threads 4`、compose `--processes 1 --threads 8`。
- **R-M4** 双 venv：README/DEPLOYMENT 要求根 `.venv`，GETTING-STARTED `uv sync --project backend` 落在 `backend/.venv`，两者都存在（根 905 MB）。
- **R-M5** 工作树 259 个 CRLF 文件（扣除合规 ps1/cmd 后 224），`git ls-files --eol` 129 个 `i/lf w/crlf` + 37 个 `w/mixed`，索引 0 CRLF——近期有工具以 CRLF 写文件。
- **R-M6** `.git` 垃圾对象：garbage 45（5.47 MiB）、loose 5198（52.78 MiB）、4 packs 487 MiB。
- **R-M7** docs 顶层失效引用 31 条 + 14 条指向 `D:/MOSS-SYSTEM-V1/` 外机路径（README、AGENTS 及三份入口文档 0 失效）。
- **R-M8** `CURRENT_EFFECTIVE_ENTRYPOINT.md` Last reviewed 2026-04-22，未收录 2026-08/09 的 release-control-plane、market-overview 工作流。

**Low / Info**：`.cursorignore` 未覆盖 `.omx/ .worktrees/ tmp-governance/ unused/ .tmp-agent/ test_output/ output/ .codex*`（合计约 7.4 GB、17 万文件）；`.git/info/exclude` 本地排除 `/.worktrees/` 与 `/docs/GPT55_FRONTEND_DESIGN_CONTEXT.md`；三份 MCP 配置漂移（`.cursor/mcp.json` 缺 moss-data-quality、stitch，playwright 用 `@latest`）；GETTING-STARTED 引用 `docs/ARCHITECTURE.md` 实为 `architecture.md`（Linux/CI 失效）；`config/CODEX_CONFIG_NOTE.md` 与实际不符；`settings.yaml.example` 含机器路径 `F:/EMQuantAPI_Python/python3`；`.gitleaks.toml` 通用 `key = "..."` allowlist 放过裸 `key="<secret>"`；`start_dev.cmd` 是未被文档提及的第三入口；12 个 >1 MB 跟踪文件（7 份 manuscript docx 10.9 MB）；GitNexus `lastCommit=bef54b58`=HEAD 但不含 548 改+168 新+9 删，对 `observability/`、`release_control`、research-desk 的调用者分析不可信。

**根目录与临时目录状态**：`probe*/tmp_*/tmp-*.db`（11 个，~0.7 MB，忽略，删除）；`tmp-risk-overview*.png`、`figma-audit-baseline*.png`（忽略，删除或移入 docs）；`review-*/`（22 MB，忽略，删除）；`wp2-review-tczed8o6/`（7 MB，**未跟踪未忽略**）；`deliverables/`（10 MB docx/pdf，**未跟踪未忽略**）；`logs/`（目录未忽略）；`tmp-governance/`（2.83 GB，**保留**，是本地 Postgres dev cluster）；`test_output/` 491 MB、`.tmp/` 46 MB、`.tmp-agent/` 363 MB、`.codex-tmp/`+`.codex_tmp/` 178 MB、`unused/` 307 MB、`.omx/` 1.86 GB、`.worktrees/` 1.18 GB（`git worktree prune` 后删除）、`.codex/visual-audits/` 120 MB。

**已验证正常**：`.env` 未入库；模板只有占位；`.gitattributes` `* text=auto eol=lf` 且 py/ts/tsx/css/md 显式 lf，ps1/cmd crlf；U+FFFD 0；BOM 仅 6 个未跟踪 csv；`.mcp.json` 7 个脚本均存在；端口 7888/5888/55432 与 8000/5173/5432 在各处一致；`.nvmrc`=22、`.python-version`=3.11 与 CI 一致。

## 四、建议处理顺序

**立刻（今天）**
1. 轮换 Choice / Tushare / Stitch 凭据；处理 `origin/master` 上的 `3cf24a71e` 历史；清理 `.omx/logs`。
2. 停止在同一工作树上并发编辑；冻结后在 `git worktree` 副本重跑 `tests/` 与 release suite，得到可信基线。
3. 修 `choice_stock_materialize.py:2961` 列名显式插入（T-C2）；恢复 `start-moss-finance-audit-cluster.ps1` 的 BOM 或移出中文（T-H1）。

**提交前**
4. 按 `docs/plans/2026-08-27-uncommitted-work-split-plan.md` 拆分未提交改动；`fixed_income_version_set.py` 与 8 个依赖文件同笔提交并附重物化 runbook（A-H3）；受保护边界改动（schema/Alembic/RBAC 缓存/settings/release-control）各自给根因证据。
5. 修 `BalanceAnalysisPage.test.tsx:1404`、拆 `MacroToolkitPage.test.tsx:5534`；逐条对照补回 `StockAnalysisPage.test.tsx` 被删的 stale/fallback/fail-closed 断言（W-H1~H3）。
6. 对齐整期归并容差的代码/文档/测试三方（F-M2）；更新 18 个期望过期测试；重生成 openapi 基线与 coverage report。
7. 修 `.gitignore` 吞源文件规则（R-H1）；`git rm --cached governance-lineage-audit.json`。

**近期（业务裁定后）**
8. Campisi model 路径期内交易处理并在页面契约声明（F-H1）；`ytm=0` 语义统一并在利差中排除（F-H2）；浮息债久期打标或剔除（F-M1）；歧义清单逐条由业务裁定。
9. Vite `xfwd: true` 或 `host: 127.0.0.1`（S-H1）；Agent intent 按资源做 read 校验（S-H2）；KPI 错误脱敏（S-M1）；macro_toolkit 子进程 env 裁剪与 stderr 脱敏（S-M2）。
10. 修 HEAD 已红的 5 个测试；把轻量静态守卫纳入 release suite 并让两阶段都跑；release suite 加 `-n` 或拆分以对齐 20 分钟超时；用 3.11 重建 `.venv`。
11. Campisi 公式与 PnL 求和迁入 core_finance（A-M1、A-M5）；`cffex_member_rank` 写入回归 tasks（A-H1）；`matched_baseline.py` 写段迁至 tasks 加守卫（A-H2）。

## 五、本次审计无法覆盖的项

生产数据中 ytm=0 / 浮息 / 期内交易占比（未访问 data/）；CI 上 release suite 实际耗时与 `backend-full-pytest` scheduled 历史（需 GitHub 访问）；`pip-audit`（venv 未安装）；Playwright a11y 与 `guard:*:live`（需前后端在线）；Choice `EmQuantAPI` 与 Hermes 外部配置的错误回显行为；`origin/master` 是否公开仓库；冻结工作树下 `test_ledger_import_worker_e2e`、`test_choice_stock_materialize`、`test_native_dev_scripts` 的真实结果；Vitest 197 skipped 归因。
