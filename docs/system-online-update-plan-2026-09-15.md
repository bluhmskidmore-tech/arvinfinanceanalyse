# 系统在线更新与读取协调实施方案

本次修复后台数据中心更新与在线读取争用活动 DuckDB 的共享根因。采用按请求固定的持久只读完整快照，保留任务对活动库的计算权威；只有完整流程与来源核验通过，才切换对外读取版本。本方案不代表全局验收已完成。

## 已核实证据与影响

交接依据为 `docs/system-online-update-handoff-2026-09-15.md`。原损益试点已验收；2026-08-31 的完整财务请求已成功，禁止为本次演示重跑。2026-09-15 本轮重新核对：7888 API 健康，5888 正常监听，数据中心队列就绪，无活跃财务更新请求。正式余额、同业、债券、风险和损益最新日期均为 2026-08-31。（相关执行证据仅保存在本地，公开版本不附原文。）

`.venv/Scripts/python.exe .codex-tmp/system-online-update-20260915/reproduce_lock.py` 已用独立进程和合成数据库复现：正常 `read_only_connection` 持有读取时，writer 出现 IOException 文件占用；读者释放后 writer 成功。首次沙箱运行因临时目录权限失败，批准重跑后成功。没有操作正式业务数据。现有连接有退出关闭机制，不能将此问题描述为连接泄漏。

GitNexus 项目为 `moss-v3-main-current-20260809`，HEAD 与索引 lastCommit 同为 `3ca0bbc438644214878bd789c4322a722c9d6393`。`read_only_connection` 有 43 个直接调用者、84 个上游符号，涉及七类模块，风险 CRITICAL；仓储 `_connect_read_only` 有六个直接调用者，风险 MEDIUM。`get_settings` 有 309 个直接调用者、涉及 41 个流程，风险 CRITICAL，因此不通过修改其全局缓存或替换全局路径实现隔离。`drain_updates` 的直接调用者为正常 `main`；`run_global_data_refresh` 的直接调用者为正常 CLI 与数据中心 `_execute_core`。

当前 DuckDB 大小为 3,668,979,712 字节，任务开始时同盘可用约 14.9 GB。发布前重新计算候选、暂存及保留版本的空间；本轮不删除仍可能被请求使用的版本。初步来源核对比较了 1,250 个已登记当前文件与归档内容，全部一致，没有缺失归档。未登记的 27 份文件均为旧历史资料，不构成自动补算依据。真实新增更新日期或源版本变化暂为 PENDING；已向用户非阻塞询问其他投放目录，实施和隔离验证继续。

## 网页复核与执行预算

网页会话为 https://chatgpt.com/c/6aa791c9-c0b0-83e9-88eb-2ea4002aa3ee ，可见模式已核实为 6 Pro。本次以“NEW TASK — SYSTEM ONLINE UPDATE / READ COORDINATION”提交脱敏技术摘要，明确旧损益三轮复核已经结束。新任务收到 `PLAN_READY`，随后第一轮执行复核收到 `ACCEPT`，范围仅限共享读取边界三文件，允许进入第二轮；不包括正式激活、完整快照、五域接入及真实在线更新。网页评审基于脱敏证据包，没有访问本地文件或执行测试。

第一轮最终版本由 Sol 与 Luna max 分别运行 `.venv/Scripts/python.exe -m pytest -q tests/test_duckdb_online_read_boundary.py tests/test_task_sync_wrapper_contracts.py tests/test_duckdb_repo_scoped_connection.py`，均为 25 项通过（分别 6.58 秒、6.19 秒）。定向 Ruff、差异和 UTF-8 检查通过。Luna 独立回执为 `.codex-tmp/system-online-update-20260915/boundary-audit.json`。`duckdb_repo.py`、新增 `duckdb_read_context.py`、新增边界测试的最终 SHA-256 分别为 `b07f116d8cf9dfee931037109dfd86cf2cf1ff7cf08799fd3ab2e7090d5a2f2d`、`b69125cc07d21e9aa17db7689c8a1ff458632cb77a5a2cbcb43f84eaa4ca20db`、`e6be6da525ddd999f67e68a185f273f11cadc1a0a6f18ba9bb233087db94a936`。首轮合成证据没有写正式数据库或调整服务。

最多三个执行复核周期，同时最多三名子代理。首轮 Sol 实现共享读取上下文，另一名 Sol 只核对固定调用集，Luna max 独立验证；父代理负责网页评审、整合、运行切换及最终验收。保留当前工作区所有已有改动，不提交或推送。

第二轮网页 Pro 已返回 `ACCEPT`，范围为冻结后的读取侧、请求/线程上下文、缓存、五页前端握手和隔离合成证明。复核明确不包括仍在收口的发布资格检查，也不授权正式激活。其要求第三轮补齐完整事实、血缘与损益版本切点、来源组合规则、初始化资格、进程中断恢复、引用产物保留和未支持 writer 的新鲜度披露；真实必要财务更新没有合法来源变化时仍须标为 PENDING。

第二轮读取侧最终独立整合回归为 14 个文件、188 项通过（54.34 秒），前端七文件 236 项通过（7.13 秒）。这组结果排除了仍在修改的发布器测试，不与先前不同时间点的 189 项结果混用。窄范围 Ruff 通过；旧 facade 的 E9/F821 检查通过，全量检查仍有既有导出/import 债务，未扩大清理。

首轮只修改共享连接边界与合成跨进程测试。证明通过后提交执行复核 1，再进入完整生命周期。第二轮完成发布、血缘、路由和线程接入及隔离集成证明。第三轮进行合法必要的在线更新和固定五域验收；若没有真实待更新来源，真实更新门槛保持 PENDING，不能制造变化或重跑已成功整链。

## 核心实现契约

一个完整读取版本绑定不可变 DuckDB、被冻结的结果血缘与依赖版本、各域实际覆盖日期，以及兼容的既有损益发布 generation。使用独立完整读取命名空间，复用现有发布机制的校验、锁、CAS、容量保护和提交恢复能力，不改变既有损益选表发布物的含义。

HTTP 在第一次缓存查找前选择一次版本，整个响应保持该选择。共享 `read_only_connection` 和 `DuckDBRepository._connect_read_only` 只把匹配活动库身份的路径解析为该版本的物理文件；其他显式数据库不受影响。API 中的直接连接与 native 预热线程必须同样接入。上下文未激活时保持既有行为；启用在线读取后，缺失或无效选择必须明确失败，不得回落活动库。任务、命令行、依赖检查、同步计算调用必须显式使用活动库上下文。

队列、认证和运维审计保持实时。数据中心财务日期读取选中的完整版本，正在执行的请求及其目标日期来自实时队列，两者不能混为一谈。冻结结果血缘不能绕过明确撤销/失效；旧结果保留真实日期、状态和既有来源警告。

损益日期、准备状态和结果读取绑定完整读取版本中的既有损益 generation，避免损益先跟随自己的新指针、其他域仍读取旧完整版本。返回读取 generation 头；涉及多个请求的代表性交互在后续请求携带同一代际，只接受受支持的版本标识，不能接受文件路径。不得改变原损益日期与版本协议。

候选通过受控源连接/事务、现有 writer 协调与独立候选库导出。使用安装版本实测支持的 `COPY FROM DATABASE` 等既有 DuckDB 能力保留必要目录对象，禁止直接复制活动库/WAL。检查视图、宏和外部依赖不会逃逸到实时文件。导出发生在成功任务终态之后，核对与本次 run 关联的持久化终态和实际依赖，不能仅凭 latest manifest。若已有关键区无法证明事实与终态匹配，只延长相关正式任务的既有关键区，不新增分布式事务，也不在已持锁任务外层重复获取物理写锁。

父代理已独立核对 DuckDB 官方说明：[进程并发边界](https://duckdb.org/docs/current/connect/concurrency)、[完整数据库复制](https://duckdb.org/docs/current/sql/statements/copy#copy-from-database--to)、[显式 DETACH 与句柄释放](https://duckdb.org/docs/current/sql/statements/attach#detach)。这些说明约束实现方向；安装版本上的合成执行和独立进程释放检查才是本机证明。

发布前失败保留旧版本和实际失败回执。CAS 后回执写入中断应从已提交指针与回执恢复元数据，不能重新执行已成功财务步骤。所有缓存使用固定版本或其有效物理路径；旧请求/预热的迟到结果只能写入旧代际缓存。当前阶段支持已核验状态初始化与成功 `core_financial` 终态发布，其他独立 writer 的刷新覆盖必须明确记录，不得将其静默陈旧结果称为全局新鲜。

## 固定五域验收入口

以下入口已从路由、客户端和页面契约核实，固定后不得删除失败模块。首次单次基线为已有缓存状态，不能声称这些时间是进程冷启动或统计 P95。

| 领域 | 代表性页面 | 读取端点和本轮初始参数 | 首次 HTTP | 首次耗时 ms |
| --- | --- | --- | --- | --- |
| 首页 | `/`（另有既有 `/dashboard`） | `/ui/home/snapshot`，默认严格交集 | 200 | 43 |
| 余额 | `/balance-analysis` | `/ui/balance-analysis/overview?report_date=2026-08-31` | 200 | 326 |
| 债券 | `/bond-analysis` | `/api/bond-analytics/portfolio-headlines?report_date=2026-08-31` | 200 | 477 |
| 风险 | `/risk-tensor` | `/api/risk/tensor?report_date=2026-08-31` | 200 | 293 |
| 损益 | `/pnl-by-business-insights` | `/api/pnl/by-business-insights?year=2026&as_of_date=2026-08-31` | 200 | 38 |

同时覆盖 `/api/data-updates` 和必要的旧损益主流程。首页保持最新完整交集及 `domains_effective_date`；其他页面使用各自实际日期。债券分析页面的 candidate 边界不因本次读取优化而提升。余额资产/负债分别展示，兼容毛额不能冒充单侧值。风险 Numeric 单位和损益确切截止日/比较期规则保持原契约。

已新增只读负载脚本 `scripts/verify_system_online_reads.py`。每个交互先读取首页，再将返回的完整读取 generation 传给余额、债券、风险和损益；每个交互按顺序执行，不把五个域乘成未声明的并发数。脚本只输出请求时间区间、元数据、技术哈希和统计，不提交数据更新。现有正式服务尚未激活完整读取协议，因此下述基线没有 generation 头；后续启用后必须使用 `--require-generation` 硬断言。

本轮已各跑两轮 5/10 并发，共 150 次 GET，HTTP/信封/实际日期检查和逐域业务哈希稳定性均通过。记录排除 `computed_at`、`generated_at` 两个生成时点字段，其余业务字段不排除。5 并发时首页、余额、债券、风险、损益 P95 分别为 153.389、191.430、1204.119、299.155、1125.226 毫秒；10 并发分别为 140.915、632.674、1757.752、335.158、667.129 毫秒。债券和损益出现过一秒以上基线，后续必须保留并分别比较，不将它们从验收集中剔除。证据文件为 `.codex-tmp/system-online-update-20260915/baseline-read-5.json` 和 `baseline-read-10.json`。这些是观察到的热/已有缓存基线，不是冷启动或更新中证明。

正式验收期间 API、前端、worker、监督与计划任务都必须在线。5/10 并发、多个冷/热轮次持续覆盖更新前、中、后；“更新中”应关联实际写连接区间和 CAS，不能只引用 running 标签。无文件占用、非预期 HTTP/契约错误及响应/同一交互混代是硬条件。主要读取 P95 目标不高于一秒，预先固定旧慢端点名单，不事后重分类。临时正常服务隔离测试与正式服务证据分别记录。

跨模块数值核对使用实际币种、单位、持仓范围和比较期；技术哈希只证明一致性，不代替独立会计对账。恢复测试先在合成环境覆盖写入失败、部分提交、依赖变化、CAS 前后中断、旧预热迟到和文件句柄释放。

## 首改证明命令与剩余门槛

首改证明为 `.venv/Scripts/python.exe -m pytest -q tests/test_duckdb_online_read_boundary.py tests/test_task_sync_wrapper_contracts.py`，随后运行现有共享连接测试及改动路径的 Ruff、编译、UTF-8/差异检查。测试需要真实独立进程、事件或管道同步，证明读快照与写活动库确实重叠，并保留旧路径会冲突的对照。

目前尚未实现完整在线机制，也未执行真实新财务更新。后续报告必须区分共享机制、模块接入、正式在线运行及独立业务正确性；这项完成也不代表交接中所有全局开发目标已完成。

## 第二轮局部进展（尚未整体验收）

父代理补齐了五个直接连接仓储：`bond_analytics_repo.py`、`risk_tensor_repo.py`、`liability_analytics_repo.py`、`pnl_repo.py`、`product_category_pnl_repo.py`。只读连接在打开前解析所选物理路径，写连接不变；损益来源版本临时缓存同时使用有效路径作为键。GitNexus 已对两个 helper、负债连接入口、两个仓储类及 37 个内联连接方法逐项做 upstream 查询。风险 helper 有七个直接调用，涉及当前和历史风险路由，风险 MEDIUM；索引未覆盖部分已存在的脏工作区方法，不能将返回零调用者当作无影响。直接代码证据补充了首页和损益链的调用范围。

`.venv/Scripts/python.exe -m pytest -q tests/test_bond_analytics_repo.py tests/test_risk_tensor_repo.py tests/test_pnl_repo_bond_prefix_dual_form.py tests/test_product_category_read_boundary.py tests/test_system_online_read_repositories.py` 为 42 项通过；仓储及新测试 Ruff 通过。新增八项测试包括实际独立进程持有活动库 writer 时五个仓储读取旧快照，以及必需选择缺失时不得返回空数据。只读验收脚本另有六项测试，验证交互固定版本、失败判定、非本地目标拒绝和不能把 phase 标签当作写入重叠证据。

前端 Sol 完成五页交互边界后，父代理发现两处集成缺陷并修复。其一，`coverage_dates` 必须是后端真实的日期数组映射，不能按单个字符串解析；其二，只在导航后 effect 清理旧上下文，会让新页面先以旧上下文发出请求。新增导航测试在改动前失败，改为按 `location.key` 同步重建内部边界后通过。边界测试现为七项通过；前端完整组合、独立审计及实际浏览器联调仍须以最终冻结版本重新确认。

完整逻辑复制的实库只读预检确认活动库包含 70 张用户表、8 个用户视图、无用户宏；2026-09-15 10:02 北京时间后核对可用空间为 15,700,160,512 字节，正式数据库仍为 3,668,979,712 字节。没有正式财务写入或运行配置变更。

初始化证据不能冒充原执行证据：已成功请求的原始回执只保留前八步状态与时间，没有其完整 result/child run id。这项缺口在原 `real-run-technical-proof.json` 的 `schema_omissions` 已明确。初始化将独立核验当前已完成状态并记录新的 bootstrap qualification，不构造不存在的旧步骤回执；普通财务更新发布仍必须使用本次确切步骤及来源切点。任何域无法唯一核验时初始化失败，不能因此重跑已成功金融计算。

Luna 已按修复后的冻结版本独立重跑前端七文件组合，236 项通过；仓储与只读验收脚本组合 48 项通过。额外 150 次正式服务只读 GET 均为 HTTP 200、信封有效且逐域技术哈希稳定；正式服务尚未激活，因此严格 generation 检查仍缺少响应头，这不是已上线证明。独立回执为 `.codex-tmp/system-online-update-20260915/independent-cycle2-partial-audit.json`。

Sol 随后通过最终前端 typecheck、六项 debt audit、隔离生产构建及原候选指标 bundle guard。补齐既有 `/health/live` 活性检查例外后，重新运行前端 236 项组合测试、typecheck 和定向 ESLint，均通过，并重新构建。新构建位于 `.codex-tmp/system-online-update-20260915/accepted-build`，共 306 个文件；最终构建树 SHA-256 为 `f1877f9a71ab309b97173d946696226f089b79cffb865ec6797ac4a9767409a0`，`index.html` SHA-256 为 `1c7147a236849be28bb5d7a5d10b7b898af76f3f09c094227073d820b85008f9`。原运行构建和 `frontend/dist` 未覆盖，尚未选择新运行构建。

父代理新增 `tests/test_system_online_publication_concurrency.py`，真实 governed 子进程写入合成活动库并持有连接，HTTP 中间件在 5/10 worker pool 下持续读取旧完整版本；完整发布的提交前、提交后异常恢复，以及新旧版本请求均有断言。父代理两项通过，Luna 独立两项通过，连同原五仓储与验收脚本组合共 50 项通过。这是合成 HTTP probe，异常由 callback 注入，不是进程 crash，也不替代正式五域在线更新。

`data_update_repo.financial_dates` 已改为先解析有效快照路径再检查存在性，并向外传播必需读取选择异常；普通锁或 schema 错误仍保留既有 error 状态。GitNexus 显示直接调用者只有 `data_update_service.update_overview`，风险 LOW。新增三个边界测试与原 `test_data_updates.py` 合计 58 项通过，Ruff 通过。

2026-09-15T02:24:42Z 的第一次正式只读初始化预检没有匹配到余额领域资格，记录为 PENDING。活动库大小与修改时间不变，完整读取 pointer 仍不存在，没有复制候选或重跑财务。证据为 `.codex-tmp/system-online-update-20260915/bootstrap-preflight.json`。本次按血缘断点追踪核对实际 descriptor、终态、manifest 和事实分区，尚不能把未匹配解释为数据错误或直接忽略。

只读负载脚本新增 `--business-tieout`。根据 `MTR-BAL-001`、`MTR-RSK-001/020/101` 及实际 service 映射，验证首页 AUM 与余额资产端市值、首页与债券 DV01、债券与风险 DV01/市值/行数，以及余额三类金额的资产加负债毛额闭合，共八项；只导出通过状态和绝对容差，不导出金额。金额/DV01 容差为原始单位 0.01，行数容差为零，不改变业务公式。损益洞察无同口径总额字段，不将不同口径强行对应。这些是同源交叉核对，不是独立会计审计，也不提升首页/债券 candidate 的正式边界。

2026-09-15 当前旧运行服务的单次固定样本已通过全部八项核对，六次 GET 全部成功，证据为 `.codex-tmp/system-online-update-20260915/baseline-business-tieout.json`。这只是未激活新协议的基线，不能替代后续 generation/写入重叠检查。脚本十三项单元测试通过，覆盖单位/日期/范围/null/差值异常和金额不落入输出，Ruff 通过；GitNexus 尚无本轮新脚本符号，使用脚本内部调用与十三项测试作为局部影响证据，不将 UNKNOWN 当作零影响。

## 第三轮本地收口记录

读取侧独立冻结清单为 `.codex-tmp/system-online-update-20260915/independent-cycle2-read-side-final-audit.json`，44 个文件条目，SHA-256 为 `445eba2f67426ee871be80f958e88bcf6ab870588d399a8bff6dc40665ed62a4`。所有条目无 BOM、无 U+FFFD。线程池的逐个提交点使用独立上下文副本；六条代表性 leaf recording 均未打开活动路径，不将此范围扩大成所有仓储覆盖。

新增真实进程中断测试 `tests/test_system_read_publication_process_crash.py`，Sol 两项通过。父进程在收到子进程提交阶段信号后终止子进程；提交前恢复保留旧指针并复用 sealed candidate，提交后恢复只返回已提交元数据。两把文件锁在进程退出后可以重新取得。它证明操作系统进程终止和锁释放，不证明断电或文件系统硬件故障；独立复跑另行记录。

2026-09-15 的真实浏览器基线确认主页已有“刷新首页数据”按钮。原新边界虽提供 `refresh`，但真实主页没有使用，清理查询缓存仍会留在旧 generation。已安排最小接入及按钮层回归，未启用新协议时保持原 refetch；新产物另存 `accepted-build-v2`，不能继续把上一构建清单当作这项增量的证明。

完整发布器正在复用余额、债券、损益、产品分类、资产变动和来源预览的原 producer 身份规则，并在写锁内绑定精确 sealed PnL 依赖。正式只读资格预检必须等入口稳定后再运行。没有修改正式事实、重新执行成功财务请求或调整运行开关。临时候选 API 启动脚本也要求已核验完整 pointer 存在；目前尚未启动。

独立 writer 的新鲜度是激活门槛。当前实现仅覆盖已核验状态初始化及 `core_financial` 终态发布；`balance_daily` 将明确披露旧快照未刷新，独立全量 CLI 缺少数据中心请求关联时拒绝执行。市场计划任务等其他 writer 的发布覆盖尚未证明，不能因为固定五域测试通过就对全部 API 宣称实时同步，亦不为此临时重建整个调度框架。

2026-09-15T03:16:58Z 已加载正常 `scripts/dev-env.ps1` 并使用完整 Settings 再做正式只读资格预检。前六个领域已通过，来源预览仍有两个候选，预检保持 PENDING。原预览表按批次保留历史，历史批次存在且身份正确不等于当前读取选择；下一步按既有预览选择规则及确切批次核验，不取任意最新回执。回执仍确认活动数据库 stat 未变、完整 pointer 不存在、没有发布或财务重跑。

03:21:39Z 再次预检仍返回同一来源预览错误，因此按 `pro-codex-loop` 的两次重复阻塞规则暂停资格与上线路径。暂停后的定点只读核对确定：两个 completed terminal 均没有非空 `ingest_batch_id`，且来源版本哈希相同；现 predicate 因要求非空批次而返回 `None`，并不是两个 `True` 冲突。producer 在没有新文件时本来就传 `None`，由 `_select_manifest_rows` 执行既有按 family、日期、批次与归档路径选择。这是资格检查尚未覆盖的合法分支，不是重新导入或补算依据。确切证据为 `.codex-tmp/system-online-update-20260915/source-preview-null-batch-evidence.json`；后续须补该分支和回归，不能虚构批次号。

主页刷新增量已有 43 项页面测试和七项边界测试通过，typecheck、定向 ESLint、debt audit 和 bundle guard 通过。`accepted-build-v2` 共 306 个文件、37,503,158 字节；canonical 文件摘要数组 SHA-256 为 `cabc83a1c7f5e2cd3b684b8aa7df68595daf0357d4635269ef40c5fcccff45e7`。沿上一构建的“相对路径 NUL 文件字节 NUL”口径，树哈希为 `05e5aa6b00488464135540978ed00183f79cc8fd9d26dc71b21ea29d1bf80bb8`。`accepted-build-v2.manifest.json` SHA-256 为 `1e7dc350ebcd886dbfb3c44b2e428561a30b9692f6e6274472221f1d798eee66`，现有运行控制器已验证全部 306 项，未执行选择或切换。

第三轮网页 Pro 已返回 `REVISE`：接受原读取/交互切片保持不变，但要求补 source-preview 合法空批次资格分支及真实 bootstrap 入口回归。独立 writer freshness、合格正式完整 pointer、候选五域浏览器/数值/5及10并发冷暖证明和必要在线更新仍未通过。本轮已用完交接约定的三个执行复核周期，不再盲目重复预检或启用配置。最终独立发布器五文件各进程共 123 项、前端八文件 279 项通过；这些结果不改变 NO-GO。完整接续修复、运行状态和冻结清单见 `docs/system-online-update-continuation-2026-09-15.md`。
