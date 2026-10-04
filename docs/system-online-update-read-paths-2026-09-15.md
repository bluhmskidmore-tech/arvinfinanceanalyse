# 在线更新第二周期：读取接线与完整快照发布边界

## 结论

第一周期已经证明了最小底座：任务局部的 `DuckDBReadSelection` 能把活动库路径解析到独立只读快照，共享入口 `read_only_connection` 与 `DuckDBRepository._connect_read_only` 已接入该解析，隔离测试证明快照读连接打开期间，另一个进程仍能写活动库（`backend/app/repositories/duckdb_read_context.py:28-89`、`backend/app/repositories/duckdb_repo.py:61-92`、`backend/app/repositories/duckdb_repo.py:251-265`、`tests/test_duckdb_online_read_boundary.py:110-147`）。这只证明连接机制成立，不证明 API 已选择完整 generation，也不证明五个代表流程已脱离活动库。

第二周期不能只加一个全局路径替换。一次 API 读取必须固定同一组不可变资产：完整 DuckDB 快照、与该快照同源的冻结 lineage、实际 domain/date coverage，以及现有 PnL publication generation。当前选择对象只有 active path、snapshot path 和 generation，尚未携带后三项；当前 scope 也只是底层上下文，没有 pointer 解析、保留窗口或请求入口激活（`backend/app/repositories/duckdb_read_context.py:28-56`、`backend/app/repositories/duckdb_read_context.py:92-149`）。因此，完整快照 publisher 是下一步的前置条件；在它提交 pointer 之前，API 的 online-required 模式必须 fail closed，不能退回活动库。

本文是严格有界的调用路径核对。证据来自当前工作树和与 HEAD `3ca0bbc438644214878bd789c4322a722c9d6393` 匹配的本地 GitNexus 索引；MCP 证据不可用。下述“证据”是直接代码事实，“推断”是据此形成的最小接线合同。

## 完整快照 publisher：最少安全合同

### 发布时点和调用者

**证据。** `core_financial` 顺序执行 formal balance、bond、risk、formal PnL、product-category、accounting movement、source preview、report-date verify，以及启用 publication 时的 PnL page prepare（`scripts/run_global_data_refresh.py:315-457`、`scripts/run_global_data_refresh.py:459-511`）。所有步骤完成后，它才构造并提交现有 PnL publication，成功结果含 generation 和 manifest hash（`scripts/run_global_data_refresh.py:688-788`）。数据中心把该函数返回的 completed 作为请求完成依据（`backend/app/tasks/data_update_center.py:401-440`）。因此完整快照发布必须成为 `run_global_data_refresh` 的最后一个必需步骤，并在 PnL publication 成功后执行；它失败时，外层数据更新请求必须保持 failed，不能先写 completed。

**证据。** 现有 PnL “financial publication”虽然要求整条全局刷新回执，但实际只复制 `fact_pnl_by_business_page_envelope`，coverage 也只有 `pnl_by_business_page`（`backend/app/tasks/pnl_by_business_page_publication.py:208-229`、`backend/app/tasks/pnl_by_business_page_publication.py:312-342`）。它不能充当五域完整 DuckDB 快照。

**证据。** 当前完整发布只支持 `core_financial`。`balance_daily` 仍正常完成，但在系统读取开关启用时，数据更新回执明确写入 `system_read_publication.status=not_refreshed` 和 `reason=workflow_not_supported`，用户消息同时说明五页继续读取上一个完整 generation（`backend/app/tasks/data_update_center.py:522-535`）。这比沿用旧 PnL generation 拼一个不完整 pack 更安全；单域 freshness 暂不扩成另一套 publisher。

### source cut 与 terminal 证据

**证据。** `run_formal_materialize` 当前在 writer lock 内只执行 materialization；锁于 `execute_materialization()` 返回后释放，而同一 run 的 manifest/completed terminal 要到之后的 `append_many_atomic` 才持久化（`backend/app/tasks/formal_compute_runtime.py:78-88`、`backend/app/tasks/formal_compute_runtime.py:138-199`）。`resolve_completed_formal_build_lineage` 又按 cache key、job、report date 读取 latest completed，而不是按调用方 run id 读取（`backend/app/governance/formal_compute_lineage.py:90-109`）。

**现状。** 正常发布现按前七个核心步骤逐项要求各自的 exact cache key，不能用另一域的 terminal 代替；bootstrap 则独立以当前事实语义选择唯一 terminal，并明确记录 `original_child_run_ids_recovered=false`（`backend/app/tasks/system_read_publication.py:627-709`、`backend/app/tasks/system_read_publication.py:1459-1507`）。余额、Bond、风险、正式 PnL、产品分类、会计变动和 source preview 分别复用现行 producer 语义核验，不把 module 级组合版本与行级同名字段强行等同（`backend/app/tasks/system_read_publication.py:865-1255`）。若无法唯一闭合，资格检查保持失败；它不会伪造旧 child run id，也不会重跑财务步骤。

### generation 内容与单一提交点

**推断，高置信度。** 一个可激活 generation 至少应密封以下内容：

- 独立 DuckDB 文件及 size/SHA-256；源活动库的规范化身份与捕获时间。
- `workflow`、data-update run id、global run id、requested report date，以及按 exact run id 校验后的各 formal terminal 摘要。
- 每个代表域的实际表、date column、覆盖日期和行数。`core_financial` 当前 verify 的候选表来自 `scripts/run_global_data_refresh.py:48-59`，但 publisher 应按读取合同声明 coverage，不能把“文件复制成功”当成域覆盖。
- 与 DuckDB 同一 source cut 的冻结 governance bundle 及每个文件/记录的 digest；至少覆盖 balance/bond/risk/home 所读的 cache build run 与 cache manifest 证据。
- 现有 PnL publication generation、manifest SHA-256 和它声明的 page-date coverage。PnL 不应在完整 pack 内另选 latest。
- reader API/schema 兼容版本、previous generation、retention 和有效性状态。

**证据。** 现有 publisher 已具备可复用的 fail-closed 原语：发布锁与 source writer lock、source dependency 二次校验（`backend/app/tasks/financial_result_publication.py:130-158`），候选关闭后的 manifest/database 校验（`backend/app/tasks/financial_result_publication.py:210-248`），pointer compare-and-swap 和原子替换（`backend/app/tasks/financial_result_publication.py:250-283`），以及表 schema、日期覆盖和最小行数检查（`backend/app/tasks/financial_result_publication.py:476-550`）。第二周期宜复用这些语义，但使用独立的“完整 read pack”root/pointer；不能扩大现有 PnL pointer 的含义。

**现状。** `FinancialPublicationPlan.full_database` 默认关闭；系统 publisher 才显式设为真，并用 `COPY FROM DATABASE` 复制 schema/view/macro，失败路径也显式 `DETACH`，随后复用候选校验、CAS、容量和 retention（`backend/app/tasks/financial_result_publication.py:85-86`、`backend/app/tasks/financial_result_publication.py:353-409`）。源 cut 在导出前与 CAS 前各核验一次；表内容指纹同时保留 count、XOR 和 HUGEINT sum，避免相同重复对替换时 XOR 确定性抵消（`backend/app/tasks/system_read_publication.py:1579-1657`）。Pinned PnL 不只校验文件和 manifest：其 sealed `dependency_versions` 还要与 `_page_source_dependency_validator` 对当前只读源和治理的结果完全一致，两次检查都在同一 writer lock 内（`backend/app/tasks/system_read_publication.py:1409-1456`）。snapshot 完成仍只证明技术一致性和声明覆盖，不代表独立会计对账通过。

正式导出复用现有 `PnlByBusinessTaskResourceScope` 的 `bounded_v1`：活动源锚点只读，候选连接显式设置线程数和内存上限，pointer 前做进程树预算采样；成功或超预算回执都能沿全局刷新步骤保存（`backend/app/tasks/system_read_publication.py:370-388`、`backend/app/tasks/system_read_publication.py:509-548`、`scripts/run_global_data_refresh.py:857-895`）。这项限制覆盖本次完整 COPY，不能拿上一步 PnL 的资源回执替代。

publisher 与读取侧应共用一份不可变 manifest 合同和一个纯读取 loader，而不是共用可变 `settings.duckdb_path`。最小接口可由独立 read-pack 模块提供 `FullReadPackManifest`、`validate_read_pack_candidate(...)` 和 `load_current_read_pack(required=True)`：publisher 用同一 validator 密封候选并只负责原子切 pointer，API loader 每个请求只读 pointer 一次、复核 manifest/文件/digest 后生成包含 snapshot、frozen-governance root、coverage 与 PnL reference 的 `DuckDBReadSelection`。任务侧不得调用 current-pointer loader 来选择写库，读取侧也不得拥有 publish 能力。这样 publisher 与 reader 不会各写一套 manifest 解析和兼容判断，同时仍保持写任务的显式 active scope。

## 六条代表读取路径与第二周期接线

| 入口与直接 caller | 当前读取事实 | 最小接线与缺口 |
| --- | --- | --- |
| `/ui/home/snapshot`：route `home_snapshot` 直接调用 `home_snapshot_envelope`（`backend/app/api/routes/executive.py:133-150`） | `home_snapshot_envelope` 以当前物理文件和治理指纹构造缓存键，miss 时进入 `_compute_home_snapshot_envelope`（`backend/app/services/executive_service.py:3359-3382`、`backend/app/services/executive_service.py:3487-3529`）。compute 先从 `DashboardRepository` 取跨域日期，再并行读取 overview/attribution，随后读取产品分类 headline（`backend/app/services/executive_service.py:2639-2655`、`backend/app/services/executive_service.py:3674-3698`、`backend/app/services/executive_service.py:3701-3774`、`backend/app/services/executive_service.py:3794-3820`）。 | route 或统一 request dependency 必须在业务调用前只解析一次 pack 并激活 context。缓存键必须加入 pack generation、有效 snapshot 物理路径和 frozen-governance identity，不能读取 active 文件指纹。两个 `ThreadPoolExecutor` 都需显式传播选定 context（另一个在 `backend/app/services/executive_service.py:2827-2846`）。 |
| `/ui/balance-analysis/overview`：route 直接调用 `balance_analysis_overview_envelope`（`backend/app/api/routes/balance_analysis.py:148-180`） | service 的 cache key stat 调用方传入的活动路径；repo 数据走已接入共享入口，但 lineage 仍按 live governance 读 latest completed/manifest（`backend/app/services/balance_analysis_service.py:143-173`、`backend/app/services/balance_analysis_service.py:434-458`、`backend/app/services/balance_analysis_service.py:1157-1177`）。 | cache key 改用 effective snapshot identity + generation；`_resolve_balance_build_lineage` 改读 context 中 frozen governance，并按 pack manifest 声明的 exact run/version 核对。route 的显式旧 `generation` 参数是 balance 专用 publication，不应覆盖统一 pack selection。 |
| `/api/bond-analytics/portfolio-headlines`：route 直接调用 `get_portfolio_headlines`（`backend/app/api/routes/bond_analytics.py:228-237`） | service cache key用 `get_settings().duckdb_path` 的活动 mtime，cache miss 经 `_repo()` 再到 `BondAnalyticsRepository.fetch_bond_analytics_rows`（`backend/app/services/bond_analytics_service.py:439-480`、`backend/app/services/bond_analytics_service.py:553-555`、`backend/app/services/bond_analytics_service.py:3024-3070`）。repo 的 `_connect_read_only` 直接 `duckdb.connect(path)`（`backend/app/repositories/bond_analytics_repo.py:487-499`、`backend/app/repositories/bond_analytics_repo.py:1556-1560`）。 | `_connect_read_only` 必须调用 `resolve_effective_read_path` 或共享入口；cache token 改用 effective path + pack generation。空结果降级不得吞掉 `DuckDBOnlineReadRequiredError`，否则 fail-closed 会伪装成“无数据”。 |
| `/api/risk/tensor`：route 直接调用 `risk_tensor_envelope`（`backend/app/api/routes/risk_tensor.py:80-100`） | service cache key同时指纹活动 DuckDB 与 live governance；payload 经 `RiskTensorRepository.fetch_risk_tensor_row`，freshness 又读取 live build-run lineage和同业事实（`backend/app/services/risk_tensor_service.py:51-98`、`backend/app/services/risk_tensor_service.py:214-275`、`backend/app/services/risk_tensor_service.py:502-542`）。repo `_connect_read_only` 直接连接传入路径；bond lineage 直接读 live `GovernanceRepository`（`backend/app/repositories/risk_tensor_repo.py:351-357`、`backend/app/repositories/risk_tensor_repo.py:616-665`、`backend/app/repositories/risk_tensor_repo.py:668-790`、`backend/app/repositories/risk_tensor_repo.py:832-836`）。 | repo 直连、cache identity 和 lineage path 必须全部读取同一 pack。freshness 比较应使用 frozen bond terminal + snapshot 中同业 source/rule，不能一半 frozen、一半 live。 |
| `/api/pnl/by-business-insights`（publication enabled）：route 直接调用 `read_published_pnl_by_business_insights`（`backend/app/api/routes/pnl.py:342-377`） | `open_financial_generation` 打开已密封 publication DB，本身不占用活动 writer；但 `generation=None` 会选当前 PnL pointer，读取后 `_require_current_governance` 又用 live handoff/adjustments 判断 stale（`backend/app/services/pnl_by_business_publication_service.py:47-108`、`backend/app/services/pnl_by_business_publication_service.py:461-529`）。dates 混合 live completed runs 与 retained publications；readiness 同时读 retained publication 和 live run records（`backend/app/services/pnl_by_business_page_dates.py:17-82`、`backend/app/services/pnl_by_business_page_readiness.py:32-97`）。 | active pack 内 payload、dates、readiness 必须都强制使用 pack 声明的 PnL generation/manifest hash。live queue/handoff 可作为“后台进度”附加信息，但不得让新 PnL 在新完整 pack 激活前成为 selectable/ready，也不得使旧 pack 的已密封结果因新 live adjustment 事件被换代。`open_financial_generation` 的 sealed-path 直连是安全例外，不应重定向到主 snapshot。 |
| `/api/data-updates`：route 直接调用 `update_overview`（`backend/app/api/routes/data_updates.py:48-59`） | `update_overview` 将 live queue receipts 与 `financial_dates` 合并；后者通过共享 `read_only_connection` 查询五张活动路径表，前者经 GovernanceRepository 读取 `data_update_run`（`backend/app/services/data_update_service.py:322-331`、`backend/app/repositories/data_update_repo.py:20-27`、`backend/app/repositories/data_update_repo.py:35-53`）。 | 只让 `financial_dates` 使用 pack snapshot；计划任务、权限、请求队列、取消状态和审计继续 live。返回中应披露 pack generation/coverage，避免把 live run status 与旧 snapshot 日期拼成“已刷新可见”的错误结论。 |

## 仍会绕过共享连接的 reachable 直连

除 bond/risk 两个已确认 helper 外，首页路径在一跳内还会触达三类自定义 repository，若不接线，首页仍可能打开活动库：

- `PnlRepository`：首页调用 `list_formal_fi_report_dates`、批量/逐日 YTD 汇总（`backend/app/services/executive_service.py:1565-1644`、`backend/app/services/executive_service.py:879-945`）；对应直连在 `_list_report_dates`、`_sum_total_pnl_through_report_dates` 和逐日 fallback（`backend/app/repositories/pnl_repo.py:1977-2001`、`backend/app/repositories/pnl_repo.py:1619-1656`、`backend/app/repositories/pnl_repo.py:1573-1617`）。
- `LiabilityAnalyticsRepository._connect`：首页 NIM 调用 `list_report_dates`、`fetch_yield_kpis_for_dates`/`fetch_yield_rows_for_dates`（`backend/app/services/executive_service.py:1655-1721`、`backend/app/services/executive_service.py:1072-1209`）；helper 直接连接 self.path（`backend/app/repositories/liability_analytics_repo.py:43-50`、`backend/app/repositories/liability_analytics_repo.py:196-250`、`backend/app/repositories/liability_analytics_repo.py:360-388`、`backend/app/repositories/liability_analytics_repo.py:477-489`）。
- `ProductCategoryPnlRepository`：首页 headline 直接调用 `fetch_home_headline_values`，fallback 还会读正式模型/canonical 数据（`backend/app/services/executive_service.py:2658-2699`、`backend/app/services/executive_service.py:2798-2846`）；fast path 在 `backend/app/repositories/product_category_pnl_repo.py:158-190` 直接连接 self.path。

这些 helper 应统一先解析 effective path，并让 online-required 异常穿透。`DashboardRepository`、`FormalZqtzBalanceMetricsRepository` 和 `BalanceAnalysisRepository` 已继承 `DuckDBRepository`，数据查询可以复用第一周期底座（`backend/app/repositories/dashboard_repo.py:109-137`、`backend/app/repositories/balance_analysis_repo.py:110-119`）。本轮没有核实首页之外这些自定义 repository 的全部调用者，不能据此宣称全仓 direct connect 已收口。

## 缓存、治理与线程边界

首页存在直接读取 governance JSONL 尾部的优化路径，失败后才回到 repository：`_read_recent_cache_build_runs_for_executive_overview` 直接 `open("rb")`，`_read_all_cache_build_runs_for_executive_overview` 使用 `GovernanceRepository`（`backend/app/services/executive_service.py:358-415`、`backend/app/services/executive_service.py:418-470`）。二者都必须从 selection 的 frozen governance root 取数；cache key 也必须含 frozen file digest/generation。balance/risk 的 repository/SQL backend 读取同理，不能只改直接 JSONL。

原生线程不继承 `ContextVar`。startup warmup 在 `warm_home_snapshot_cache_if_configured` 新建线程，`main.py` 又新建周期预热线程；周期线程还会调用 blocking snapshot refresh（`backend/app/services/executive_service.py:3559-3587`、`backend/app/main.py:90-124`）。此外首页 compute 的两个 executor 和产品 headline executor 都会跨线程。最小安全行为是每个预热 pass 开始时解析一次当前 pack，把 selection 显式传入线程/worker 并在其中重新进入 scope；不能让周期线程永久继承启动时的旧 generation，也不能在线模式缺 selection 时静默读 active。

任务和 CLI 边界必须明确清除继承的 read selection，确保写流程使用活动库。`data_update_center.drain_updates` 是计划任务入口，`run_global_data_refresh` 也是同步/CLI入口（`backend/app/tasks/data_update_center.py:274-450`、`scripts/run_global_data_refresh.py:598-688`）。两者应在最外层进入显式 active scope，子任务继承该清除状态；不得改 `get_settings()` 的全局返回值来换路径。

## API 启动门槛

**证据。** API lifespan 在启动阶段调用 `run_startup_storage_migrations`，然后启动首页预热（`backend/app/main.py:156-170`）。该 bootstrap 在 development 环境执行升级写入，在其他环境直接对 `settings.duckdb_path` 做 schema current 检查（`backend/app/storage_bootstrap.py:17-33`）；readiness 函数又直接 `duckdb.connect(active, read_only=True)`（`backend/app/duckdb_schema_bootstrap.py:290-297`、`backend/app/duckdb_schema_bootstrap.py:389-420`）。worker bootstrap 同样调用该公共函数（`backend/app/tasks/worker_bootstrap.py:1-7`）。

**推断，高置信度。** 不能把公共 bootstrap 全局改为快照路径，否则 worker 会对快照执行写任务。API online 模式应先解析并验证完整 pack，再以显式 reader 角色检查 snapshot schema；worker/task 继续检查活动库。API 在 development 分支也不能对活动库做启动升级后再宣称在线读隔离。没有有效 pack、snapshot path、frozen governance 或 PnL reference 时，API readiness 应 fail closed，且不得启动 native prewarm。该门槛只涉及上述直接启动链，本次未核实其余 startup hook。

## 第二周期最小文件/函数清单

publisher/任务侧应优先收口以下现有入口；新建 manifest/pointer 模块时保持独立于 PnL publication root：

- `backend/app/tasks/system_read_publication.py`：正常路径消费七域 exact terminal；独立 bootstrap 只做当前状态资格闭合；完整 COPY、双 source-cut 校验和 pointer 提交均在既有 writer lock 内。
- `scripts/run_global_data_refresh.py::run_global_data_refresh`：在既有 PnL publish 后调用完整 pack publisher，把 exact step receipts、PnL generation/hash 和 verify 证据传入；pack commit 失败则整次请求失败。
- `backend/app/tasks/data_update_center.py::drain_updates`：任务入口显式 active scope；`core_financial` 的 system publish 失败不进入 transient 整链重试，post-CAS 恢复只补元数据；`balance_daily` 明确披露完整 snapshot 未刷新。
- 复用 `backend/app/tasks/financial_result_publication.py` 的 source lock、candidate validate、coverage check、CAS 和 atomic pointer 语义，但不要把五域表塞进现有 PnL-only pointer。

API/read 侧最小接线是：扩展 `duckdb_read_context.py` 的 selection manifest 字段和 resolver；在 API 请求入口只选一次 pack；接入上述 bond/risk/PnL/liability/product-category 直连；把 balance/risk/bond/home cache key 改成 generation-aware；冻结 governance 读取；绑定 PnL dates/readiness/payload；显式传播首页线程；让 API startup 以 reader 角色校验 generation。认证、队列、计划任务和审计保持 live。

## 验证与未核实范围

定向小库现已覆盖完整正常发布和独立 bootstrap 的正向 resolve、纯资格检查不创建目录/pointer、缺域 exact terminal、PnL dependency 漂移、重复对 XOR 抵消、七域 producer 语义、外部文件依赖、pre-CAS 不重跑财务、post-CAS 只恢复元数据，以及不支持 workflow 的陈旧披露（`tests/test_system_read_publication.py:400-553`、`tests/test_system_read_publication.py:823-1210`、`tests/test_system_read_publication.py:1290-1494`）。仍需在隔离服务中验证真实活动库 COPY、旧 pack 并发读取、pointer 前后 generation 切换和 API restart；第一周期连接测试不能替代这些端到端条件。

本轮没有扫描其余 route、所有 repository direct connect、历史审计或全系统指标。Bond 的 terminal source_version 不编码曲线依赖；会计变动只对当前单日报告窗闭合，多日 terminal aggregate 不能映射为任一单日 manifest。source preview 必须复用 producer 的实际选择语义：有批次号时按 exact batch 和权威 source-manifest 原序读取；没有新导入时，`None` 是合法输入，按现有 family、日期、批次、归档路径规则选择，不能强求非空批次号。这些条件未验证时应保留 `PENDING`。市场计划任务及其他独立 writer 尚不会触发完整 snapshot，因此正式全局启用仍应保持 flag 关闭；五个代表页面可在隔离候选服务中验证，但不能据此宣称所有 writer freshness 已闭合。

截至本轮结束，使用正式 dev-env、活动库、权威治理目录和已密封 PnL generation 的两次纯只读 bootstrap 预检都停在 `source_preview.foundation`，返回两个候选；活动库 stat 未变，system pointer 仍不存在，也没有执行 COPY。父代理在暂停后完成定点核查：两个 completed terminal 的 `ingest_batch_id` 都为空，来源版本哈希相同；当前 qualifier 仅在非空 batch 时调用 preview predicate，所以两者均未被验证，返回 `None`，并非两个合格状态冲突。原 producer 合法的无新文件分支尚未被资格检查覆盖。直接证据保存在 `.codex-tmp/system-online-update-20260915/source-preview-null-batch-evidence.json`。后续应复用原选择规则补该分支并增加集成回归，不得重导入、虚构批次号或直接取 latest。

## 第三轮冻结状态说明

前文“应接线”等内容保留第二轮改动前的证据和设计意图，不是当前实现缺项清单。第二轮读取侧、缓存、线程、治理和五页前端接线已完成定向验证并获网页 Pro 局部 ACCEPT，最终独立读取回归为 188 项。第三轮发布器五文件分进程独立回归为 123 项，前端原七文件加首页实际刷新按钮共 279 项通过；真实进程终止恢复两项也已独立通过。最新状态以 `docs/system-online-update-plan-2026-09-15.md` 和 `docs/system-online-update-acceptance-2026-09-15.md` 为准。上述结果没有覆盖正式完整快照发布、候选服务五域浏览器和必要新财务更新，不能据此启用全局开关。
